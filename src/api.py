"""FastAPI application for session creation, catalogs, telemetry, and audio WebSockets."""

from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import os
import secrets
import time
import uuid
import wave
from collections import deque
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal, TypedDict, cast
from urllib.parse import parse_qsl, urlparse

import httpx
from aiortc import RTCIceServer
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pipecat.transports.smallwebrtc.request_handler import (
    SmallWebRTCPatchRequest,
    SmallWebRTCRequest,
)
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
from starlette.responses import Response
from starlette.websockets import WebSocketState

from src.asr import create_default_asr_registry
from src.asr.catalog import discover_asr_model_catalog
from src.asr.config import ASRProvider, asr_provider_catalog
from src.asr.transcript import ASRSourceEvidenceError
from src.auth import (
    AUTH_COOKIE,
    AuthSessionStore,
    LoginAttemptLimiter,
    ProductAuthMiddleware,
    safe_return_path,
)
from src.bots.crypto import BotKeyCipher, StorageKeyError
from src.bots.models import (
    BotConfigFields,
    BotCreateRequest,
    BotRecord,
    BotResponse,
    BotUpdateRequest,
)
from src.bots.storage import BotStore
from src.bots.validation import validate_asr_account_catalog, validate_bot_config
from src.config import TTSConfig, load_llm_provider_catalog, load_runtime_config, load_voice_catalog
from src.evaluation import EvaluationStore, create_evaluation_router
from src.evaluation.connections import ASRConnectionError, test_asr_connection
from src.evaluation.executor import EvaluationRunner
from src.evaluation.models import EvaluationConnectionTestRequest
from src.history import AudioRecorder, CallCapture, HistoryStore
from src.history.models import CallDetail, CallListResponse
from src.llm.diagnostics import (
    DiagnosticConfig,
    LLMDiagnosticRequest,
    LLMDiagnosticResult,
    classify_llm_failure,
    run_llm_diagnostic,
)
from src.llm.qwen_dashscope import is_qwen_dashscope_host, validate_qwen_base_url
from src.observability import SessionEventBuffer
from src.pipeline import (
    create_small_webrtc_transport,
    run_voice_agent_pipeline,
    run_voice_agent_session,
)
from src.publication import DemoPublicationStore, PublishedDemo, ShareState
from src.session import (
    BotSessionRequest,
    SessionCapacityError,
    SessionLease,
    SessionRequest,
    SessionStore,
    SessionTokenError,
)
from src.tts import create_default_tts_registry
from src.tts.echo_cache import EchoAudioCache, fingerprint, tts_for_bot, units_for_values
from src.tts.unit_synthesis import synthesize_unit
from src.webrtc import SessionBoundSmallWebRTCHandler


def _azure_deployment_from_url(value: str) -> str:
    """Validate one exact Azure OpenAI chat-completions URL and return deployment."""
    parsed = urlparse(value)
    path_parts = [part for part in parsed.path.split("/") if part]
    valid_path = (
        len(path_parts) == 5
        and path_parts[:2] == ["openai", "deployments"]
        and path_parts[3:] == ["chat", "completions"]
    )
    api_versions = [value for key, value in parse_qsl(parsed.query) if key == "api-version"]
    if (
        parsed.scheme != "https"
        or not (parsed.hostname or "").endswith(".openai.azure.com")
        or not valid_path
        or len(api_versions) != 1
    ):
        raise ValueError(
            "Use one complete Azure OpenAI deployment chat-completions URL with api-version"
        )
    return path_parts[2]


logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"

logging.basicConfig(
    level=getattr(logging, os.getenv("VOICE_AGENT_LOG_LEVEL", "INFO").upper(), logging.INFO)
)


def _basic_auth_credentials() -> tuple[str, str] | None:
    """Load optional public-demo credentials and reject partial configuration."""
    username = os.getenv("VOICE_AGENT_BASIC_AUTH_USERNAME", "").strip()
    password = os.getenv("VOICE_AGENT_BASIC_AUTH_PASSWORD", "")
    if not username and not password:
        return None
    if not username or not password:
        raise RuntimeError("Both VoiceAgent Basic Auth variables must be configured")
    if len(password) < 8 or password == "SET_A_STRONG_PASSWORD_BEFORE_DEPLOY":
        raise RuntimeError("VoiceAgent Basic Auth password must be at least 8 characters")
    return username, password


class SessionResponse(BaseModel):
    """Non-secret response used to establish the one authorized WebSocket."""

    session_id: str
    session_token: str
    websocket_path: str
    expires_in_seconds: int


class EchoGenerateRequest(BaseModel):
    """Generate configured units only; keys and arbitrary synthesis text are never accepted."""

    model_config = ConfigDict(extra="forbid")
    units: tuple[str, ...] | None = None
    expected_fingerprint: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class PublishRequest(BaseModel):
    """Public copy saved with one immutable Bot publication."""

    model_config = ConfigDict(extra="forbid")
    public_title: str = Field(min_length=1, max_length=80)
    public_description: str = Field(default="", max_length=240)

    @field_validator("public_title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        """Normalize public copy while rejecting whitespace-only titles."""
        title = value.strip()
        if not title:
            raise ValueError("Public title is required")
        return title


class PublicSessionRequest(BaseModel):
    """Zero-configuration admission body for a public mobile call."""

    model_config = ConfigDict(extra="forbid")
    protocol_version: Literal["1"] = "1"


class PublicSessionResponse(BaseModel):
    """Short-lived capability used only for Small WebRTC signaling."""

    session_id: str
    connection_url: str
    ice_servers: list[dict[str, str]]
    expires_in_seconds: int
    playback_mode: Literal["native", "rtp_candidate"] = "native"


class PublicDemoEvent(BaseModel):
    """Non-identifying pre-session funnel event from one active demo page."""

    model_config = ConfigDict(extra="forbid")
    event: Literal["mobile_demo_view", "mobile_call_start_click", "mobile_mic_permission"]
    elapsed_ms: float = Field(ge=0, le=600_000)
    result: Literal["granted", "denied", "unavailable"] | None = None


def _asr_language_snapshot(lease: SessionLease) -> str:
    """Summarize the selected ASR language contract for call history."""
    options = lease.config.asr.options
    if lease.session_type == "chat_test":
        return "not_applicable"
    if lease.config.asr.model == "flux-general-en":
        return "en"
    language = options.get("language")
    if isinstance(language, str) and language:
        return language
    hints = options.get("language_hints") or options.get("language_codes")
    if isinstance(hints, list) and hints:
        return ",".join(str(item) for item in hints)
    return "automatic"


def _asr_context_mode_snapshot(lease: SessionLease) -> Literal["off", "agent", "full"]:
    """Describe the provider context features enabled for this call."""
    if lease.session_type == "chat_test":
        return "off"
    options = lease.config.asr.options
    if lease.config.asr.provider == "assemblyai":
        if not options.get("agent_context_enabled", True):
            return "off"
        return "full" if options.get("user_context_carryover_enabled", True) else "agent"
    return "off"


class LoginRequest(BaseModel):
    """Credentials submitted by the product-owned login page."""

    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=200)
    password: SecretStr = Field(min_length=1, max_length=500)
    next: str = Field(default="/", max_length=2000)


class PlaybackClockProbe(BaseModel):
    """One live-session challenge for a single immutable render clock."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    clock_kind: Literal["render", "capture"] = "render"
    render_clock_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    render_sample_rate: int = Field(ge=8000, le=384000, strict=True)


class PlaybackClockAck(PlaybackClockProbe):
    """A frame observation made after receiving the server's opaque challenge."""

    render_frame: int = Field(ge=0, le=9_007_199_254_740_991, strict=True)


class RTPCaptureRecord(BaseModel):
    """One native sender report; it carries neither audio nor free-form metadata."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    clock_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    ssrc: int = Field(ge=0, lt=2**32, strict=True)
    rtp_timestamp: int = Field(ge=0, lt=2**32, strict=True)
    payload_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    capture_time_ms: float = Field(strict=True, ge=-562949953421311, le=562949953421311)
    capture_clock: Literal["worker_performance"]


class RTPCaptureBatch(BaseModel):
    """A bounded report batch tied to a server-created connection epoch."""

    model_config = ConfigDict(extra="forbid")
    connection_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    records: list[RTPCaptureRecord] = Field(min_length=1, max_length=16)


class PlaybackReceipt(BaseModel):
    """A bounded task-specific render acknowledgement, with no transcript or audio."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    playback_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    event: Literal["task_started", "task_finished", "task_stopped", "task_failed"]
    rendered_samples: int = Field(ge=0, le=691200000)
    elapsed_ms: float = Field(ge=0, le=7_200_000)
    request_id: str | None = Field(default=None, max_length=128)
    evidence_source: Literal["audio_worklet_render"]
    failure_reason: Literal["render_queue_limit"] | None = None
    render_frame: int | None = Field(default=None, ge=0, le=9_007_199_254_740_991, strict=True)
    render_sample_rate: int | None = Field(default=None, ge=8000, le=384000, strict=True)
    render_clock_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")

    @model_validator(mode="after")
    def complete_render_clock(self) -> PlaybackReceipt:
        """Require one complete optional clock without inventing fields for legacy clients."""
        fields = (self.render_frame, self.render_sample_rate, self.render_clock_id)
        if any(value is not None for value in fields) and any(value is None for value in fields):
            raise ValueError("Render clock coordinates must be supplied together")
        return self


class PlaybackDiagnostics(BaseModel):
    """Bounded playback state without payloads, transcripts, tokens or arbitrary text."""

    model_config = ConfigDict(extra="forbid")
    client_build: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.-]{1,100}$")
    worker_build: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.-]{1,100}$")
    packets: int | None = Field(default=None, ge=0, le=10_000_000, strict=True)
    mappings: int | None = Field(default=None, ge=0, le=10_000_000, strict=True)
    decoded: int | None = Field(default=None, ge=0, le=10_000_000, strict=True)
    pending_packets: int | None = Field(default=None, ge=0, le=100, strict=True)
    pending_mappings: int | None = Field(default=None, ge=0, le=100, strict=True)
    matched_packets: int | None = Field(default=None, ge=0, le=100, strict=True)
    decoding: bool | None = Field(default=None, strict=True)
    head_state: Literal["empty", "matched", "missing_silence", "missing_task"] | None = None
    target_kind: Literal["unknown", "silence", "task"] | None = None
    target_has_packet: bool | None = Field(default=None, strict=True)
    target_has_mapping: bool | None = Field(default=None, strict=True)
    native_received: int | None = Field(default=None, ge=0, le=10_000_000, strict=True)
    native_lost: int | None = Field(default=None, ge=0, le=10_000_000, strict=True)
    native_discarded: int | None = Field(default=None, ge=0, le=10_000_000, strict=True)
    native_stats_age_ms: int | None = Field(default=None, ge=0, le=7_200_000, strict=True)
    max_decode_ms: int | None = Field(default=None, ge=0, le=7_200_000, strict=True)
    max_intake_gap_ms: int | None = Field(default=None, ge=0, le=7_200_000, strict=True)


class BrowserEvent(BaseModel):
    """Whitelisted browser playback event used for interruption timing."""

    model_config = ConfigDict(extra="forbid")
    event: str = Field(
        pattern="^(first_playback|audio_stopped|browser_interruption|chat_text|mobile_webrtc_connected|mobile_call_end|mobile_call_error)$"
    )
    elapsed_ms: float = Field(ge=0, le=7_200_000)
    text: str | None = Field(default=None, max_length=10000)
    candidate_type: Literal["host", "srflx", "prflx", "relay", "unknown"] | None = None
    network_type: Literal["slow-2g", "2g", "3g", "4g", "unknown"] | None = None
    end_reason: Literal["user", "disconnect", "provider", "connection"] | None = None
    stage: Literal["permission", "session", "signaling", "live"] | None = None
    safe_error_category: (
        Literal[
            "microphone_unavailable",
            "session_unavailable",
            "connection_failed",
            "call_interrupted",
            "asr_source_evidence_unavailable",
            "playback_unsupported",
            "playback_failed",
        ]
        | None
    ) = None

    playback_diagnostics: PlaybackDiagnostics | None = None

    playback_failure_reason: (
        Literal[
            "payload_identity_mismatch",
            "decode_sequence_gap",
            "decode_deadline",
            "invalid_decode_slice",
            "decode_job_unproven",
            "invalid_mapping",
            "duplicate_mapping",
            "mapping_queue_limit",
            "packet_deadline",
            "missing_ssrc",
            "packet_queue_limit",
            "mapping_deadline",
            "transform_stream_error",
            "decoder_unavailable",
            "playback_worker_unavailable",
            "multiple_receiver_transform",
            "decoder_error",
            "decode_job_unowned_output",
            "invalid_task_extent",
            "decoded_extent_overflow",
            "playback_receipt_unconfirmed",
            "invalid_playback_control",
            "remote_audio_start_failed",
            "unknown_playback_failure",
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def text_is_only_allowed_for_chat(self) -> BrowserEvent:
        """Prevent mobile telemetry from carrying transcript or arbitrary text."""
        if self.playback_diagnostics is not None and self.event != "mobile_call_error":
            raise ValueError("Playback diagnostics require a call failure event")
        if self.event.startswith("mobile_") and self.text is not None:
            raise ValueError("Mobile telemetry cannot include text")
        return self


class ShortWindowRateLimiter:
    """Bound public traffic with opaque, automatically pruned client buckets."""

    def __init__(
        self,
        *,
        limit: int,
        window_seconds: float = 60,
        clock: Callable[[], float] = time.monotonic,
        salt: bytes | None = None,
    ) -> None:
        """Initialize one process-local limiter without retaining raw identifiers."""
        self._limit = limit
        self._window_seconds = window_seconds
        self._clock = clock
        self._salt = salt or secrets.token_bytes(32)
        self._buckets: dict[bytes, deque[float]] = {}

    @property
    def active_bucket_count(self) -> int:
        """Return the number of currently retained short-window buckets."""
        return len(self._buckets)

    def allow(self, *, scope: str, public_id: str, client: str) -> bool:
        """Consume one attempt after pruning every expired opaque bucket."""
        now = self._clock()
        cutoff = now - self._window_seconds
        for bucket_key, timestamps in list(self._buckets.items()):
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if not timestamps:
                self._buckets.pop(bucket_key, None)
        material = f"{scope}\0{public_id}\0{client}".encode()
        key = hashlib.sha256(self._salt + material).digest()
        attempts = self._buckets.setdefault(key, deque())
        if len(attempts) >= self._limit:
            return False
        attempts.append(now)
        return True


class VoiceDiscoveryRequest(BaseModel):
    """Secret-bearing ElevenLabs voice search request."""

    model_config = ConfigDict(extra="forbid")
    api_key: SecretStr | None = Field(default=None, min_length=8, max_length=500)
    bot_id: str | None = Field(default=None, min_length=1, max_length=100)
    search: str = Field(default="", max_length=100)
    page_token: str | None = Field(default=None, max_length=500)
    page_size: int = Field(default=30, ge=1, le=100)


class ASRCatalogDiscoveryRequest(BaseModel):
    """Credential source for one explicit account-catalog refresh."""

    model_config = ConfigDict(extra="forbid")
    provider: str = Field(pattern="^(speechmatics|soniox)$")
    bot_id: str | None = Field(default=None, min_length=1, max_length=100)
    api_key: SecretStr | None = Field(default=None, min_length=8, max_length=500)


class EncryptedBotKeys(TypedDict):
    """Exact encrypted columns shared by Bot create and update."""

    encrypted_jev_key: str | None
    jev_key_endpoint: str | None
    encrypted_deepgram_key: str | None
    llm_key_provider: str | None
    encrypted_llm_key: str | None
    encrypted_elevenlabs_key: str | None
    asr_key_provider: str | None
    encrypted_asr_key: str | None
    tts_key_provider: str | None
    encrypted_tts_key: str | None


def _allowed_origins() -> list[str]:
    raw = os.getenv(
        "VOICE_AGENT_ALLOWED_ORIGINS",
        "http://localhost:8000,http://127.0.0.1:8000,http://localhost:5173,http://127.0.0.1:5173",
    )
    return [item.strip() for item in raw.split(",") if item.strip()]


def _ice_server_urls() -> list[str]:
    """Load explicit STUN URLs while preserving the no-TURN product decision."""
    urls = [
        item.strip() for item in os.getenv("VOICE_AGENT_STUN_URLS", "").split(",") if item.strip()
    ]
    if any(not url.startswith(("stun:", "stuns:")) for url in urls):
        raise RuntimeError("VOICE_AGENT_STUN_URLS accepts only stun: or stuns: URLs")
    return urls


def _validate_webrtc_deployment(ice_server_urls: list[str]) -> None:
    """Fail closed when production would advertise an unreachable WebRTC path."""
    if os.getenv("VOICE_AGENT_DEPLOYMENT_ENVIRONMENT", "local") != "production":
        return
    if not ice_server_urls:
        raise RuntimeError("production WebRTC requires VOICE_AGENT_STUN_URLS")
    if os.getenv("VOICE_AGENT_WEBRTC_HOST_NETWORK", "").lower() != "true":
        raise RuntimeError("production WebRTC requires Linux host networking")


def _validate_session_origin(request: Request, allowed_origins: list[str]) -> None:
    """Permit loopback HTTP for local acceptance and require HTTPS everywhere else."""
    origin = request.headers.get("Origin", "")
    if origin not in allowed_origins:
        raise HTTPException(status_code=403, detail="This page origin is not allowed")
    parsed = urlparse(origin)
    loopback_hosts = {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme != "https" and parsed.hostname not in loopback_hosts:
        raise HTTPException(
            status_code=400,
            detail="BYOK session creation requires HTTPS outside local loopback",
        )


def _bot_data_dir() -> Path:
    """Locate the writable directory holding the bot database."""
    return Path(os.getenv("VOICE_AGENT_DATA_DIR", str(PROJECT_ROOT / "data")))


def _evaluation_data_dir() -> Path:
    """Keep Evaluation state independently mountable in production."""
    return Path(os.getenv("VOICE_AGENT_EVALUATION_DATA_DIR", str(_bot_data_dir())))


def create_app(*, development_rtp_candidate: bool = False) -> FastAPI:
    """Create an application with validated configuration and isolated state."""
    runtime = load_runtime_config()
    voices = load_voice_catalog()
    llm_providers = load_llm_provider_catalog()
    store = SessionStore(
        token_ttl_seconds=runtime.session.pending_token_ttl_seconds,
        max_sessions=runtime.session.max_concurrent_sessions,
    )
    tts_registry = create_default_tts_registry()
    asr_registry = create_default_asr_registry()
    bot_store = BotStore(_bot_data_dir() / "bots.db")
    echo_cache = EchoAudioCache(_bot_data_dir() / "echo-audio")
    publication_store = DemoPublicationStore(_bot_data_dir() / "bots.db", echo_cache)
    bot_cipher = BotKeyCipher.from_env()
    ice_server_urls = _ice_server_urls()
    _validate_webrtc_deployment(ice_server_urls)
    webrtc_handler = SessionBoundSmallWebRTCHandler(
        session_store=store,
        ice_servers=[RTCIceServer(urls=url) for url in ice_server_urls] or None,
    )
    event_buffers: dict[str, SessionEventBuffer] = {}
    call_captures: dict[str, CallCapture] = {}
    history_store = HistoryStore(_bot_data_dir())
    evaluation_store = EvaluationStore(
        _evaluation_data_dir() / "evaluation.db",
        PROJECT_ROOT / "benchmarks" / "RiyadBankConversation",
    )
    evaluation_runner = EvaluationRunner(evaluation_store, bot_cipher)
    website_auth = _basic_auth_credentials()
    auth_sessions = AuthSessionStore()
    login_limiter = LoginAttemptLimiter()
    public_session_limiter = ShortWindowRateLimiter(limit=10)
    public_event_limiter = ShortWindowRateLimiter(limit=60)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await bot_store.initialize()
        await publication_store.initialize()
        await history_store.initialize()
        await evaluation_store.initialize()
        await evaluation_runner.resume_pending()
        await history_store.cleanup()
        stop = asyncio.Event()

        async def purge_loop() -> None:
            while not stop.is_set():
                try:
                    await asyncio.wait_for(stop.wait(), timeout=15.0)
                except TimeoutError:
                    await store.purge_expired()
                    for session_id in await store.drain_expired_session_ids():
                        event_buffers.pop(session_id, None)
                        await history_store.finish_call(
                            call_id=session_id,
                            status="expired",
                            duration_ms=0,
                            turns=[],
                            metrics=[],
                            recording_path=None,
                            recording_status="not_started",
                        )
                    await history_store.cleanup()

        task = asyncio.create_task(purge_loop(), name="session-token-purge")
        try:
            yield
        finally:
            stop.set()
            await task
            await webrtc_handler.close()
            await store.close_all()
            await evaluation_runner.close()
            await echo_cache.close()
            event_buffers.clear()
            call_captures.clear()

    app = FastAPI(title="English Flux Voice Agent", version="0.1.0", lifespan=lifespan)
    app.state.runtime = runtime
    app.state.voice_catalog = voices
    app.state.llm_catalog = llm_providers
    app.state.session_store = store
    app.state.event_buffers = event_buffers
    app.state.tts_registry = tts_registry
    app.state.echo_cache = echo_cache

    async def echo_synthesize(
        unit: str,
        config: TTSConfig,
        rate: int,
        *,
        timeout: float,
        api_key: str,
    ) -> bytes:
        """Use existing adapters with a separate fixed-setting synthesis lifecycle."""
        return await synthesize_unit(tts_registry, api_key, unit, config, rate, timeout=timeout)

    app.state.echo_synthesize = echo_synthesize
    app.state.asr_registry = asr_registry
    app.state.bot_store = bot_store
    app.state.publication_store = publication_store
    app.state.webrtc_handler = webrtc_handler
    app.state.bot_cipher = bot_cipher
    app.state.history_store = history_store
    app.state.evaluation_store = evaluation_store
    app.state.evaluation_runner = evaluation_runner
    app.state.auth_sessions = auth_sessions

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
    )
    if website_auth is not None:
        app.add_middleware(
            ProductAuthMiddleware,
            sessions=auth_sessions,
        )

    app.include_router(
        create_evaluation_router(
            evaluation_store,
            start_batch=evaluation_runner.start,
            handle_batch_action=evaluation_runner.handle_action,
            translate_for_display=evaluation_runner.translate_for_display,
        )
    )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # FastAPI's default response includes raw rejected input, which may contain BYOK keys.
        safe_errors = [
            {"location": list(error["loc"]), "message": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": safe_errors})

    @app.get("/health")
    async def health() -> dict[str, object]:
        pending, active = await store.counts()
        return {
            "status": "ok",
            "pipecat": "1.8.1",
            "tts_providers": tts_registry.providers,
            "asr_models": asr_registry.models,
            "pending_sessions": pending,
            "active_sessions": active,
        }

    @app.get("/login", include_in_schema=False)
    async def login_page() -> Response:
        """Serve the product-owned sign-in page without a native browser challenge."""
        login_file = FRONTEND_DIST / "login.html"
        if login_file.is_file():
            return FileResponse(login_file)
        return HTMLResponse(
            "<h1>VoiceAgent Demo</h1><p>The login page has not been built yet.</p>",
            status_code=503,
        )

    @app.post("/api/auth/login")
    async def website_login(payload: LoginRequest, request: Request) -> Response:
        """Create a revocable website session after constant-time credential checks."""
        if website_auth is None:
            return JSONResponse({"next": safe_return_path(payload.next), "auth_enabled": False})
        client = request.client.host if request.client else "unknown"
        if not login_limiter.allow(client):
            return JSONResponse(
                {"detail": "Too many sign-in attempts. Please wait and try again."},
                status_code=429,
            )
        username_ok = secrets.compare_digest(payload.username, website_auth[0])
        password_ok = secrets.compare_digest(payload.password.get_secret_value(), website_auth[1])
        if not username_ok or not password_ok:
            login_limiter.fail(client)
            return JSONResponse(
                {"detail": "We could not sign you in. Check the shared details and try again."},
                status_code=401,
            )
        login_limiter.clear(client)
        token, idle_expires_at, absolute_expires_at = auth_sessions.create()
        response = JSONResponse(
            {
                "next": safe_return_path(payload.next),
                "idle_expires_at": idle_expires_at,
                "absolute_expires_at": absolute_expires_at,
            }
        )
        response.set_cookie(
            AUTH_COOKIE,
            token,
            max_age=auth_sessions.idle_seconds,
            httponly=True,
            secure=True,
            samesite="strict",
            path="/",
        )
        return response

    @app.get("/api/auth/session")
    async def website_session(request: Request) -> dict[str, object]:
        """Return safe expiry metadata and refresh activity through middleware."""
        if website_auth is None:
            return {"auth_enabled": False}
        return {
            "auth_enabled": True,
            "idle_expires_at": request.state.auth_idle_expires_at,
            "absolute_expires_at": request.state.auth_absolute_expires_at,
        }

    @app.post("/api/auth/logout", status_code=204)
    async def website_logout(request: Request) -> Response:
        """Revoke the current website session and clear its browser Cookie."""
        token = request.cookies.get(AUTH_COOKIE, "")
        auth_sessions.revoke(token)
        response = Response(status_code=204)
        response.delete_cookie(AUTH_COOKIE, path="/", secure=True, samesite="strict")
        return response

    @app.get("/api/catalogs")
    async def catalogs() -> dict[str, object]:
        return {
            "defaults": {
                "llm_provider": runtime.llm.provider,
                "llm_base_url": runtime.llm.base_url,
                "llm_model": runtime.llm.model,
                "reasoning_mode": runtime.llm.reasoning_mode,
                "system_prompt": runtime.system_prompt,
                "opening_script": runtime.opening_script,
                "flux_voice": runtime.tts.voice,
                "audio": runtime.audio.model_dump(),
            },
            "flux_voices": voices.model_dump(),
            "llm_providers": llm_providers.model_dump(),
            "asr_providers": asr_provider_catalog(),
        }

    @app.post("/api/asr/catalog")
    async def discover_asr_catalog(request: ASRCatalogDiscoveryRequest) -> dict[str, object]:
        """Return an account-filtered provider catalog without exposing its key."""
        if request.api_key is not None:
            raise HTTPException(
                status_code=422,
                detail="Save the Bot ASR key before refreshing its account catalog",
            )
        if request.bot_id is None:
            raise HTTPException(
                status_code=400,
                detail="Save the Bot before refreshing its account catalog",
            )
        record = await bot_store.get(request.bot_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Bot not found")
        if record.asr_provider != request.provider:
            raise HTTPException(
                status_code=400,
                detail="Save the selected ASR provider before refreshing its catalog",
            )
        if not record.has_asr_key:
            raise HTTPException(
                status_code=400,
                detail="This Bot has no saved key for the selected ASR provider",
            )
        if bot_cipher is None or record.encrypted_asr_key is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Saved ASR key is unavailable because VOICE_AGENT_STORAGE_KEY is not configured"
                ),
            )
        try:
            key = bot_cipher.decrypt(record.encrypted_asr_key).get_secret_value()
        except StorageKeyError:
            raise HTTPException(
                status_code=400, detail="Saved ASR key cannot be decrypted"
            ) from None
        try:
            catalog = await discover_asr_model_catalog(request.provider, key)
            await bot_store.set_asr_account_catalog(request.bot_id, catalog)
            return catalog
        except (httpx.HTTPError, RuntimeError, ValueError) as exc:
            logger.warning(
                "asr_catalog_discovery_failed provider=%s error_type=%s",
                request.provider,
                type(exc).__name__,
            )
            raise HTTPException(status_code=502, detail="ASR catalog discovery failed") from None

    def _config_fields(request: BotCreateRequest | BotUpdateRequest) -> BotConfigFields:
        """Strip write-only key fields before persistence."""
        return BotConfigFields.model_validate(
            request.model_dump(
                exclude={
                    "save_keys",
                    "save_jev_key",
                    "jev_api_key",
                    "save_asr_key",
                    "save_tts_key",
                    "save_llm_key",
                    "asr_api_key",
                    "tts_api_key",
                    "deepgram_api_key",
                    "llm_api_key",
                    "elevenlabs_api_key",
                }
            )
        )

    def _validate_bot_payload(
        config: BotConfigFields, account_catalog: dict[str, object] | None = None
    ) -> None:
        try:
            validate_bot_config(
                config=config,
                voice_catalog=voices,
                llm_catalog=llm_providers,
                tts_providers=tts_registry.providers,
            )
            validate_asr_account_catalog(config, account_catalog)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None

    def _encrypt_bot_key(value: SecretStr | None) -> str | None:
        """Encrypt one submitted component key without exposing its value."""
        if value is None:
            return None
        if bot_cipher is None:
            raise HTTPException(
                status_code=400,
                detail="Saving API keys is disabled: VOICE_AGENT_STORAGE_KEY is not configured",
            )
        return bot_cipher.encrypt(value)

    async def _key_columns(
        request: BotCreateRequest | BotUpdateRequest,
        *,
        existing: object | None = None,
    ) -> EncryptedBotKeys:
        """Resolve independent keep, replace, or clear state for every component."""
        existing_record = existing if isinstance(existing, BotRecord) else None

        async def resolve(
            *,
            component: Literal["asr", "tts", "llm"],
            should_save: bool,
            submitted: SecretStr | None,
            provider: str,
            previous_provider: str | None,
            previous_ciphertext: str | None,
        ) -> tuple[str | None, str | None]:
            if not should_save:
                return None, None
            if submitted is not None:
                return provider, _encrypt_bot_key(submitted)
            if previous_provider == provider and previous_ciphertext is not None:
                return previous_provider, previous_ciphertext
            if existing_record is not None:
                stored = await publication_store.get_credential(
                    existing_record.id, component, provider
                )
                if stored is not None:
                    return provider, stored
            return None, None

        asr_provider, encrypted_asr = await resolve(
            component="asr",
            should_save=request.save_asr,
            submitted=request.effective_asr_key,
            provider=request.asr_provider,
            previous_provider=existing_record.asr_key_provider if existing_record else None,
            previous_ciphertext=existing_record.encrypted_asr_key if existing_record else None,
        )
        tts_provider, encrypted_tts = await resolve(
            component="tts",
            should_save=request.save_tts,
            submitted=request.effective_tts_key,
            provider=request.tts_provider,
            previous_provider=existing_record.tts_key_provider if existing_record else None,
            previous_ciphertext=existing_record.encrypted_tts_key if existing_record else None,
        )
        llm_provider, encrypted_llm = await resolve(
            component="llm",
            should_save=request.save_llm,
            submitted=request.llm_api_key,
            provider=request.llm_provider,
            previous_provider=existing_record.llm_key_provider if existing_record else None,
            previous_ciphertext=existing_record.encrypted_llm_key if existing_record else None,
        )
        jev_endpoint = request.td_config.jev.endpoint if request.td_config else None
        encrypted_jev = None
        if request.save_jev_key is not False:
            if request.jev_api_key is not None and request.save_jev_key is True:
                if jev_endpoint is None:
                    raise HTTPException(
                        status_code=400, detail="Jev connection settings are required"
                    )
                encrypted_jev = _encrypt_bot_key(request.jev_api_key)
            elif existing_record and existing_record.jev_key_endpoint == jev_endpoint:
                encrypted_jev = existing_record.encrypted_jev_key
        encrypted_deepgram = (
            encrypted_tts
            if tts_provider == "deepgram_flux"
            else encrypted_asr
            if asr_provider == "deepgram"
            else None
        )
        encrypted_elevenlabs = encrypted_tts if tts_provider == "elevenlabs" else None
        return {
            "encrypted_jev_key": encrypted_jev,
            "jev_key_endpoint": jev_endpoint if encrypted_jev else None,
            "encrypted_deepgram_key": encrypted_deepgram,
            "llm_key_provider": llm_provider,
            "encrypted_llm_key": encrypted_llm,
            "encrypted_elevenlabs_key": encrypted_elevenlabs,
            "asr_key_provider": asr_provider,
            "encrypted_asr_key": encrypted_asr,
            "tts_key_provider": tts_provider,
            "encrypted_tts_key": encrypted_tts,
        }

    async def _sync_selected_credentials(
        bot_id: str,
        request: BotCreateRequest | BotUpdateRequest,
        encrypted_keys: EncryptedBotKeys,
    ) -> None:
        """Persist selected provider credentials without deleting other providers."""
        changes = (
            (
                "asr",
                request.asr_provider,
                request.save_asr,
                encrypted_keys["encrypted_asr_key"],
            ),
            (
                "tts",
                request.tts_provider,
                request.save_tts,
                encrypted_keys["encrypted_tts_key"],
            ),
            (
                "llm",
                request.llm_provider,
                request.save_llm,
                encrypted_keys["encrypted_llm_key"],
            ),
        )
        for component, provider, should_save, encrypted_key in changes:
            await publication_store.sync_credential(
                bot_id=bot_id,
                component=cast(Literal["asr", "tts", "llm"], component),
                provider=provider,
                should_save=should_save,
                encrypted_key=encrypted_key,
            )

    @app.get("/api/bots", response_model=list[BotResponse])
    async def list_bots() -> list[BotResponse]:
        return [BotResponse.from_record(record) for record in await bot_store.list()]

    @app.post("/api/bots", response_model=BotResponse, status_code=201)
    async def create_bot(request: BotCreateRequest) -> BotResponse:
        _validate_bot_payload(request)
        encrypted_keys = await _key_columns(request)
        record = await bot_store.create(
            config=_config_fields(request),
            **encrypted_keys,
        )
        await _sync_selected_credentials(record.id, request, encrypted_keys)
        return BotResponse.from_record(record)

    @app.get("/api/bots/{bot_id}", response_model=BotResponse)
    async def get_bot(bot_id: str) -> BotResponse:
        record = await bot_store.get(bot_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Bot not found")
        return BotResponse.from_record(record)

    @app.put("/api/bots/{bot_id}", response_model=BotResponse)
    async def update_bot(bot_id: str, request: BotUpdateRequest) -> BotResponse:
        existing = await bot_store.get(bot_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Bot not found")
        preserved_catalog = (
            existing.asr_account_catalog
            if existing.asr_provider == request.asr_provider
            and existing.asr_model == request.asr_model
            and request.save_asr
            and request.effective_asr_key is None
            and existing.has_asr_key
            else None
        )
        _validate_bot_payload(request, preserved_catalog)
        encrypted_keys = await _key_columns(request, existing=existing)
        record = await bot_store.update(
            bot_id,
            config=_config_fields(request),
            asr_account_catalog=preserved_catalog,
            **encrypted_keys,
        )
        assert record is not None
        await _sync_selected_credentials(record.id, request, encrypted_keys)
        return BotResponse.from_record(record)

    @app.delete("/api/bots/{bot_id}", status_code=204)
    async def delete_bot(bot_id: str) -> None:
        if not await bot_store.delete(bot_id):
            raise HTTPException(status_code=404, detail="Bot not found")

    def _share_payload(state: ShareState, http_request: Request) -> dict[str, object]:
        """Serialize a protected share state without leaking its snapshot."""
        public_id = state.public_id
        public_url = (
            f"{str(http_request.base_url).rstrip('/')}/demo/{public_id}" if public_id else None
        )
        return {
            "bot_id": state.bot_id,
            "bot_name": state.bot_name,
            "public_id": public_id,
            "public_url": public_url,
            "title": state.title,
            "description": state.description,
            "active": state.active,
            "published": state.published,
            "available": bool(state.available and bot_cipher is not None),
            "revision": state.revision,
            "published_at": state.published_at,
            "unpublished_changes": state.unpublished_changes,
        }

    async def echo_record(bot_id: str) -> BotRecord:
        """Read the currently saved configuration before any asset operation."""
        record = await bot_store.get(bot_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Bot not found")
        return record

    async def echo_status(record: BotRecord) -> dict[str, object]:
        """Return verifiable per-unit state and the exact effective TTS fingerprint."""
        rule = record.td_config.priority_rule if record.td_config else None
        units = (
            tuple(dict.fromkeys(units_for_values(row.value for row in rule.vocabulary)))
            if rule
            else ()
        )
        config = tts_for_bot(record)
        rows = await echo_cache.status(record.id, units, config, runtime.audio.output_sample_rate)
        return {
            "fingerprint": fingerprint(config, runtime.audio.output_sample_rate),
            "enabled": bool(rule and rule.enabled),
            "assets": [
                row.public() if row else {"unit": unit, "status": "missing", "url": None}
                for unit, row in zip(units, rows, strict=True)
            ],
        }

    @app.get("/api/bots/{bot_id}/echo-audio")
    async def get_echo_audio(bot_id: str) -> dict[str, object]:
        """Inspect current audio integrity without making any provider request."""
        return await echo_status(await echo_record(bot_id))

    @app.post("/api/bots/{bot_id}/echo-audio/generate")
    async def generate_echo_audio(bot_id: str, payload: EchoGenerateRequest) -> dict[str, object]:
        """Explicit user action prepares only missing units from the saved vocabulary."""
        record = await echo_record(bot_id)
        rule = record.td_config.priority_rule if record.td_config else None
        if rule is None or not rule.enabled:
            raise HTTPException(
                status_code=400, detail="Enable identifier rules before generating audio"
            )
        config = tts_for_bot(record)
        current_fp = fingerprint(config, runtime.audio.output_sample_rate)
        if payload.expected_fingerprint is not None and payload.expected_fingerprint != current_fp:
            raise HTTPException(
                status_code=409, detail="TTS settings changed; reload before generating audio"
            )
        units = tuple(dict.fromkeys(units_for_values(row.value for row in rule.vocabulary)))
        selected = payload.units if payload.units is not None else units
        if not selected or not set(selected).issubset(units):
            raise HTTPException(
                status_code=400, detail="Select audio units from the saved vocabulary"
            )
        ciphertext = await publication_store.get_credential(record.id, "tts", record.tts_provider)
        if bot_cipher is None or ciphertext is None:
            raise HTTPException(
                status_code=400, detail="Save the selected TTS key before generating audio"
            )
        try:
            key = bot_cipher.decrypt(ciphertext).get_secret_value()
        except StorageKeyError:
            raise HTTPException(
                status_code=400, detail="Saved TTS key cannot be decrypted"
            ) from None

        async def render(
            unit: str,
            settings: TTSConfig,
            rate: int,
            *,
            timeout: float,
        ) -> bytes:
            """Keep the credential behind the server boundary, outside durable resource metadata."""
            return await app.state.echo_synthesize(
                unit, settings, rate, timeout=timeout, api_key=key
            )

        await echo_cache.prepare(
            record.id, selected, config, runtime.audio.output_sample_rate, render, timeout=20.0
        )
        return await echo_status(record)

    @app.get("/api/echo-assets/{version}")
    async def preview_echo_audio(version: str) -> Response:
        """Serve verified permanent PCM in a real WAV container for row-level listening."""
        try:
            asset = await echo_cache.asset(version)
            pcm = await echo_cache.read(asset)
        except ValueError:
            raise HTTPException(status_code=404, detail="Audio resource unavailable") from None

        def wav_bytes() -> bytes:
            """Container conversion never joins encoded file headers or blocks the event loop."""
            output = io.BytesIO()
            with wave.open(output, "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(asset.sample_rate)
                wav.writeframes(pcm)
            return output.getvalue()

        return Response(
            await asyncio.to_thread(wav_bytes),
            media_type="audio/wav",
            headers={"Cache-Control": "private, max-age=31536000, immutable"},
        )

    @app.get("/api/bots/{bot_id}/share")
    async def get_bot_share(bot_id: str, http_request: Request) -> dict[str, object]:
        """Return protected publication state for the formal Share page."""
        record = await bot_store.get(bot_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Bot not found")
        return _share_payload(await publication_store.share_state(record), http_request)

    @app.post("/api/bots/{bot_id}/publish")
    async def publish_bot(
        bot_id: str, payload: PublishRequest, http_request: Request
    ) -> dict[str, object]:
        """Publish an immutable Bot snapshot and stable public locator."""
        record = await bot_store.get(bot_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Bot not found")
        _validate_bot_payload(record, record.asr_account_catalog)
        if bot_cipher is None:
            raise HTTPException(
                status_code=400,
                detail="Publishing requires VOICE_AGENT_STORAGE_KEY",
            )
        try:
            state = await publication_store.publish(
                record,
                title=payload.public_title.strip(),
                description=payload.public_description.strip(),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return _share_payload(state, http_request)

    async def _set_share_active(
        bot_id: str, active: bool, http_request: Request
    ) -> dict[str, object]:
        record = await bot_store.get(bot_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Bot not found")
        if not await publication_store.set_active(bot_id, active):
            raise HTTPException(status_code=409, detail="Publish this Bot before sharing it")
        return _share_payload(await publication_store.share_state(record), http_request)

    @app.post("/api/bots/{bot_id}/share/enable")
    async def enable_bot_share(bot_id: str, http_request: Request) -> dict[str, object]:
        """Enable an existing stable public link."""
        return await _set_share_active(bot_id, True, http_request)

    @app.post("/api/bots/{bot_id}/share/disable")
    async def disable_bot_share(bot_id: str, http_request: Request) -> dict[str, object]:
        """Disable new calls without changing the public locator."""
        return await _set_share_active(bot_id, False, http_request)

    async def _resolve_session_request(
        request: SessionRequest | BotSessionRequest,
    ) -> SessionRequest:
        """Map a bot-based session request onto the canonical inline shape."""
        if isinstance(request, SessionRequest):
            return request
        record = await bot_store.get(request.bot_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Bot not found")
        try:
            validate_asr_account_catalog(record, record.asr_account_catalog)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        inline_asr = request.asr_api_key or (
            request.deepgram_api_key if record.asr_provider == "deepgram" else None
        )
        inline_tts: SecretStr | None
        if request.tts_api_key is not None:
            inline_tts = request.tts_api_key
        elif record.tts_provider == "elevenlabs":
            inline_tts = request.elevenlabs_api_key
        else:
            inline_tts = request.deepgram_api_key

        def resolve_component_key(
            *,
            label: str,
            saved: bool,
            ciphertext: str | None,
            inline: SecretStr | None,
            required: bool = True,
        ) -> SecretStr | None:
            if saved:
                if inline is not None:
                    raise HTTPException(
                        status_code=422,
                        detail=f"This bot already has a saved {label} key",
                    )
                if bot_cipher is None or ciphertext is None:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Saved {label} key is unavailable because "
                            "VOICE_AGENT_STORAGE_KEY is not configured"
                        ),
                    )
                try:
                    return bot_cipher.decrypt(ciphertext)
                except StorageKeyError as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from None
            if inline is None and required:
                raise HTTPException(
                    status_code=422,
                    detail=f"Provide a {label} API key for this session",
                )
            return inline

        asr_key = resolve_component_key(
            label="ASR",
            saved=record.has_asr_key,
            ciphertext=record.encrypted_asr_key,
            inline=inline_asr,
            required=request.session_type != "chat_test",
        )
        tts_key = resolve_component_key(
            label="TTS",
            saved=record.has_tts_key,
            ciphertext=record.encrypted_tts_key,
            inline=inline_tts,
        )
        llm_key = resolve_component_key(
            label="LLM",
            saved=record.has_llm_key,
            ciphertext=record.encrypted_llm_key,
            inline=request.llm_api_key,
        )
        assert tts_key is not None and llm_key is not None
        jev_key = None
        if record.turn_detection_source == "self_developed" and request.session_type != "chat_test":
            jev_key = resolve_component_key(
                label="Jev",
                saved=record.has_jev_key,
                ciphertext=record.encrypted_jev_key,
                inline=request.jev_api_key,
                required=True,
            )
        return SessionRequest(
            session_type=request.session_type,
            asr_api_key=asr_key,
            tts_api_key=tts_key,
            llm_api_key=llm_key,
            llm_provider=record.llm_provider,
            llm_base_url=record.llm_base_url,
            llm_model=record.llm_model,
            llm_temperature=record.llm_temperature,
            reasoning_mode=record.reasoning_mode,
            llm_max_response_tokens=record.llm_max_response_tokens,
            llm_request_timeout_seconds=record.llm_request_timeout_seconds,
            system_prompt=record.system_prompt,
            opening_script=record.opening_script,
            fallback_script=record.fallback_script,
            asr_provider=cast(ASRProvider, record.asr_provider),
            asr_model=record.asr_model,
            turn_detection_source=record.turn_detection_source,
            asr_options=record.asr_options,
            td_config=record.td_config,
            jev_api_key=jev_key,
            asr_language_hints=record.asr_language_hints,
            asr_eot_threshold=record.asr_eot_threshold,
            asr_eot_timeout_ms=record.asr_eot_timeout_ms,
            asr_keyterms=record.asr_keyterms,
            asr_profanity_filter=record.asr_profanity_filter,
            asr_numerals=record.asr_numerals,
            asr_redact=record.asr_redact,
            flux_voice=record.tts_voice,
            tts_provider=cast(Literal["deepgram_flux", "elevenlabs"], record.tts_provider),
            tts_model=record.tts_model,
            tts_text_aggregation=record.tts_text_aggregation
            or ("sentence" if record.tts_provider == "elevenlabs" else "token"),
            tts_speed=record.tts_speed,
            tts_dynamic_speed_enabled=record.tts_dynamic_speed_enabled,
            tts_speed_step=record.tts_speed_step,
            tts_expressivity=record.tts_expressivity,
            tts_model_improvement_opt_out=record.tts_model_improvement_opt_out,
            tts_stability=record.tts_stability,
            tts_similarity_boost=record.tts_similarity_boost,
            tts_style=record.tts_style,
            tts_use_speaker_boost=record.tts_use_speaker_boost,
            tts_text_normalization=record.tts_text_normalization,
        )

    @app.post("/api/tts/elevenlabs/voices")
    async def discover_elevenlabs_voices(
        request: VoiceDiscoveryRequest, http_request: Request
    ) -> dict[str, object]:
        """Proxy a sanitized, timeout-bounded ElevenLabs account voice query."""
        _validate_session_origin(http_request, _allowed_origins())
        api_key = request.api_key
        if api_key is None and request.bot_id:
            record = await bot_store.get(request.bot_id)
            if record is None:
                raise HTTPException(status_code=404, detail="Bot not found")
            if (
                not record.has_tts_key
                or record.tts_provider != "elevenlabs"
                or bot_cipher is None
                or record.encrypted_tts_key is None
            ):
                raise HTTPException(status_code=422, detail="Provide an ElevenLabs API key")
            try:
                api_key = bot_cipher.decrypt(record.encrypted_tts_key)
            except StorageKeyError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from None
        if api_key is None:
            raise HTTPException(status_code=422, detail="Provide an ElevenLabs API key")
        params: dict[str, str | int] = {"page_size": request.page_size}
        if request.search.strip():
            params["search"] = request.search.strip()
        if request.page_token:
            params["next_page_token"] = request.page_token
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "https://api.elevenlabs.io/v2/voices",
                    headers={"xi-api-key": api_key.get_secret_value()},
                    params=params,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = 401 if exc.response.status_code in {401, 403} else 502
            detail = (
                "ElevenLabs API key was rejected"
                if status == 401
                else "ElevenLabs voice service failed"
            )
            raise HTTPException(status_code=status, detail=detail) from None
        except httpx.HTTPError:
            raise HTTPException(
                status_code=502, detail="ElevenLabs voice service is unavailable"
            ) from None
        payload = response.json()
        safe_voices = []
        for voice in payload.get("voices", []):
            labels = voice.get("labels") if isinstance(voice.get("labels"), dict) else {}
            safe_voices.append(
                {
                    "voice_id": voice.get("voice_id", ""),
                    "name": voice.get("name", "Unnamed voice"),
                    "category": voice.get("category") or "Unspecified",
                    "labels": {
                        key: str(labels.get(key) or "Unspecified")
                        for key in ("language", "accent", "gender")
                    },
                    "preview_url": voice.get("preview_url"),
                }
            )
        return {
            "voices": safe_voices,
            "has_more": bool(payload.get("has_more")),
            "next_page_token": payload.get("next_page_token"),
        }

    async def _resolve_diagnostic(request: LLMDiagnosticRequest) -> DiagnosticConfig:
        """Resolve a diagnostic request without returning or persisting its key."""
        if request.bot_id:
            record = await bot_store.get(request.bot_id)
            if record is None:
                raise HTTPException(status_code=404, detail="Bot not found")
            key = request.llm_api_key
            if record.has_llm_key:
                if key is not None:
                    raise HTTPException(
                        status_code=422,
                        detail="This bot already has a saved LLM key",
                    )
                if bot_cipher is None or record.encrypted_llm_key is None:
                    raise HTTPException(status_code=400, detail="Saved LLM key is unavailable")
                try:
                    key = bot_cipher.decrypt(record.encrypted_llm_key)
                except StorageKeyError as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from None
            if key is None:
                raise HTTPException(status_code=422, detail="Provide an LLM key for this test")
            model = (request.llm_model or record.llm_model).strip()
            provider = next(
                (item for item in llm_providers.providers if item.id == record.llm_provider),
                None,
            )
            if provider is None:
                raise HTTPException(status_code=422, detail="Unknown LLM provider")
            if not provider.supports_custom_model and model not in provider.recommended_models:
                raise HTTPException(
                    status_code=422,
                    detail="Select an LLM model from the server catalog",
                )
            return DiagnosticConfig(
                provider=record.llm_provider,
                base_url=record.llm_base_url,
                model=model,
                api_key=key.get_secret_value(),
                temperature=(
                    request.llm_temperature
                    if request.llm_temperature is not None
                    else record.llm_temperature
                ),
                reasoning_mode=request.reasoning_mode or record.reasoning_mode,
                timeout=runtime.llm.timeout_seconds,
            )

        if not all(
            [request.llm_provider, request.llm_base_url, request.llm_model, request.llm_api_key]
        ):
            raise HTTPException(
                status_code=422,
                detail="Provide bot_id or the complete inline LLM configuration",
            )
        assert request.llm_api_key is not None
        assert request.llm_provider is not None
        assert request.llm_base_url is not None
        assert request.llm_model is not None
        validation_key = "diagnostic-placeholder-key"
        inline = SessionRequest(
            deepgram_api_key=SecretStr(validation_key),
            llm_api_key=request.llm_api_key,
            llm_provider=request.llm_provider,
            llm_base_url=request.llm_base_url,
            llm_model=request.llm_model,
            llm_temperature=(
                request.llm_temperature if request.llm_temperature is not None else 0.7
            ),
            reasoning_mode=request.reasoning_mode or "provider_default",
            system_prompt="Diagnostic only.",
            opening_script="",
            flux_voice=runtime.tts.voice,
        )
        validated = await store.build_config(
            request=inline,
            runtime=runtime,
            voice_catalog=voices,
            llm_catalog=llm_providers,
        )
        return DiagnosticConfig(
            provider=validated.llm.provider,
            base_url=validated.llm.base_url,
            model=validated.llm.model,
            api_key=request.llm_api_key.get_secret_value(),
            temperature=validated.llm.temperature,
            reasoning_mode=validated.llm.reasoning_mode,
            timeout=validated.llm.timeout_seconds,
        )

    def _evaluation_provider(config: DiagnosticConfig) -> str | None:
        """Map a validated connection onto the product's evaluation providers."""
        if config.provider == "google_gemini":
            return "Gemini"
        if config.provider == "openai":
            return "GPT"
        if config.provider != "custom":
            return None
        host = (urlparse(config.base_url).hostname or "").lower()
        if is_qwen_dashscope_host(config.base_url):
            return "Qwen"
        if host == "api.deepseek.com" or host.endswith(".deepseek.com"):
            return "DeepSeek"
        return None

    @app.post("/api/llm/diagnostics", response_model=LLMDiagnosticResult)
    async def diagnose_llm(
        request: LLMDiagnosticRequest, http_request: Request
    ) -> LLMDiagnosticResult:
        _validate_session_origin(http_request, _allowed_origins())
        config = await _resolve_diagnostic(request)
        evaluation_provider = _evaluation_provider(config)
        if request.register_for_evaluation_catalog and evaluation_provider is None:
            raise HTTPException(
                status_code=422,
                detail="This endpoint is not a supported evaluation model provider",
            )
        result = await run_llm_diagnostic(config)
        if request.register_for_evaluation_catalog and result.success:
            assert evaluation_provider is not None
            await evaluation_store.register_llm_model(
                provider=evaluation_provider,
                model_id=result.model,
                base_url_host=result.base_url_host,
                diagnostic_id=result.diagnostic_id,
            )
            result.evaluation_catalog_registered = True
            result.evaluation_provider = evaluation_provider
        logger.info(
            "llm_diagnostic diagnostic_id=%s provider=%s host=%s model=%s "
            "category=%s error_type=%s provider_code=%s",
            result.diagnostic_id,
            result.provider,
            result.base_url_host,
            result.model,
            result.category,
            result.error_type or "none",
            result.provider_error_code or "none",
        )
        return result

    @app.post("/api/evaluation/connections/{provider}/test-and-save")
    async def test_and_save_evaluation_connection(
        provider: str,
        payload: EvaluationConnectionTestRequest,
        http_request: Request,
    ) -> dict[str, object]:
        """Test one provider for real and atomically persist its encrypted key."""
        _validate_session_origin(http_request, _allowed_origins())
        definitions = {
            "soniox": ("asr", "https://api.soniox.com", None),
            "speechmatics": ("asr", "https://asr.api.speechmatics.com", None),
            "elevenlabs": ("asr", "https://api.elevenlabs.io", None),
            "gemini": ("llm", "https://generativelanguage.googleapis.com", "google_gemini"),
            "gpt": ("llm", "https://api.openai.com/v1", "openai"),
            "azure_gpt": ("llm", "", "azure_openai"),
            "openrouter": ("llm", "https://openrouter.ai/api/v1", "custom"),
            "qwen": (
                "llm",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "custom",
            ),
            "deepseek": ("llm", "https://api.deepseek.com", "custom"),
        }
        normalized_provider = provider.strip().lower()
        definition = definitions.get(normalized_provider)
        if definition is None:
            raise HTTPException(status_code=404, detail="Unsupported evaluation provider")
        if bot_cipher is None:
            raise HTTPException(
                status_code=400,
                detail="Saving connections is disabled: VOICE_AGENT_STORAGE_KEY is not configured",
            )
        kind, default_base_url, llm_provider = definition
        stored = await evaluation_store.get_connection(normalized_provider)
        key = payload.api_key
        if key is None and stored is not None:
            try:
                key = bot_cipher.decrypt(str(stored["encrypted_api_key"]))
            except StorageKeyError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from None
        if key is None:
            raise HTTPException(status_code=422, detail="Enter an API key before testing")
        base_url = (payload.base_url or (stored or {}).get("base_url") or default_base_url).rstrip(
            "/"
        )
        if normalized_provider == "azure_gpt":
            try:
                azure_deployment = _azure_deployment_from_url(base_url)
            except ValueError as exc:
                raise HTTPException(
                    status_code=422,
                    detail=str(exc),
                ) from None
        elif normalized_provider == "qwen":
            try:
                base_url = validate_qwen_base_url(base_url)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from None
        elif base_url.lower() != default_base_url.lower():
            raise HTTPException(
                status_code=422,
                detail="Use the configured official endpoint for this provider",
            )
        secret = key.get_secret_value()
        if kind == "asr":
            try:
                result = await test_asr_connection(normalized_provider, secret, timeout=10.0)
            except ASRConnectionError as exc:
                failed = {
                    "success": False,
                    "category": exc.category,
                    "diagnostic_id": str(uuid.uuid4()),
                    "summary": str(exc),
                    "suggestion": "Check the key, account access, and provider status.",
                    "provider": normalized_provider,
                    "base_url": base_url,
                }
                await evaluation_store.set_asr_capability_validation(
                    normalized_provider,
                    status="unavailable",
                    diagnostic_id=str(failed["diagnostic_id"]),
                    summary=str(exc),
                )
                return failed
        else:
            if not payload.model_id:
                raise HTTPException(status_code=422, detail="Choose a model before testing")
            if normalized_provider == "azure_gpt":
                config = DiagnosticConfig(
                    provider="azure_openai",
                    base_url=base_url,
                    model=azure_deployment,
                    api_key=key.get_secret_value(),
                    temperature=0,
                )
            else:
                request = LLMDiagnosticRequest(
                    llm_provider=llm_provider,
                    llm_base_url=base_url,
                    llm_model=payload.model_id,
                    llm_api_key=key,
                    reasoning_mode="provider_default",
                    register_for_evaluation_catalog=payload.register_for_evaluation_catalog,
                )
                config = await _resolve_diagnostic(request)
            diagnostic = await run_llm_diagnostic(config)
            result = diagnostic.model_dump()
            if not diagnostic.success:
                return result
            if payload.register_for_evaluation_catalog:
                evaluation_provider = {
                    "azure_gpt": "Azure GPT",
                    "openrouter": "OpenRouter",
                }.get(normalized_provider) or _evaluation_provider(config)
                if evaluation_provider is None:
                    raise HTTPException(
                        status_code=422,
                        detail="This endpoint is not a supported evaluation model provider",
                    )
                await evaluation_store.register_llm_model(
                    provider=evaluation_provider,
                    model_id=diagnostic.model,
                    base_url_host=diagnostic.base_url_host,
                    diagnostic_id=diagnostic.diagnostic_id,
                )
                result["evaluation_catalog_registered"] = True
                result["evaluation_provider"] = evaluation_provider
        saved = await evaluation_store.save_connection(
            provider=normalized_provider,
            kind=kind,
            base_url=base_url,
            encrypted_api_key=bot_cipher.encrypt(key),
            diagnostic_id=str(result["diagnostic_id"]),
            model_id=payload.model_id,
        )
        capability = None
        if kind == "asr":
            capability = await evaluation_store.set_asr_capability_validation(
                normalized_provider,
                status="verified",
                diagnostic_id=str(result["diagnostic_id"]),
                summary=str(result.get("summary") or "Endpoint and capability contract verified"),
            )
        logger.info(
            "evaluation_connection_saved provider=%s kind=%s diagnostic_id=%s",
            normalized_provider,
            kind,
            result["diagnostic_id"],
        )
        return {**result, "connection": saved, "capability": capability}

    def _published_session_request(demo: PublishedDemo) -> SessionRequest:
        """Resolve one immutable snapshot with the Bot's current referenced keys."""
        if not demo.available or bot_cipher is None:
            raise HTTPException(status_code=409, detail="This demo is temporarily unavailable")
        try:
            config = BotConfigFields.model_validate_json(demo.config_json)
            asr_key = bot_cipher.decrypt(demo.encrypted_asr_key or "")
            tts_key = bot_cipher.decrypt(demo.encrypted_tts_key or "")
            llm_key = bot_cipher.decrypt(demo.encrypted_llm_key or "")
        except (StorageKeyError, ValueError):
            raise HTTPException(
                status_code=409, detail="This demo is temporarily unavailable"
            ) from None
        payload = config.model_dump()
        payload.pop("name")
        payload["flux_voice"] = payload.pop("tts_voice")
        return SessionRequest(
            **payload,
            session_type="mobile_web_call",
            asr_api_key=asr_key,
            tts_api_key=tts_key,
            llm_api_key=llm_key,
            jev_api_key=(
                bot_cipher.decrypt(demo.encrypted_jev_key)
                if config.turn_detection_source == "self_developed" and demo.encrypted_jev_key
                else None
            ),
        )

    async def _start_history(
        lease: SessionLease, *, bot_id: str | None, bot_name: str | None
    ) -> None:
        """Create one history row using the shared transport-independent lease."""
        await history_store.start_call(
            call_id=lease.session_id,
            bot_id=bot_id,
            bot_name=bot_name,
            session_type=lease.session_type,
            llm_provider=lease.config.llm.provider,
            llm_model=lease.config.llm.model,
            tts_provider=lease.config.tts.provider,
            tts_model=lease.config.tts.model,
            tts_voice=lease.config.tts.voice,
            tts_text_aggregation=lease.config.tts.text_aggregation,
            asr_provider=lease.config.asr.provider,
            asr_model=lease.config.asr.model,
            language=_asr_language_snapshot(lease),
            context_mode=_asr_context_mode_snapshot(lease),
            sample_rate=runtime.audio.input_sample_rate,
            channels=runtime.audio.channels,
        )

    @app.get("/api/public/demos/{public_id}")
    async def get_public_demo(public_id: str) -> Response:
        """Return only safe display metadata for one public locator."""
        demo = await publication_store.get_public(public_id)
        if demo is None:
            raise HTTPException(status_code=404, detail="Demo not found")
        return JSONResponse(
            {
                "public_id": demo.public_id,
                "title": demo.title,
                "description": demo.description,
                "active": demo.active,
                "available": demo.available and bot_cipher is not None,
            },
            headers={"Cache-Control": "no-store"},
        )

    @app.post("/api/public/demos/{public_id}/events", status_code=204)
    async def public_demo_event(
        public_id: str,
        event: PublicDemoEvent,
        http_request: Request,
    ) -> Response:
        """Record a bounded, non-identifying pre-session funnel event."""
        _validate_session_origin(http_request, _allowed_origins())
        demo = await publication_store.get_public(public_id)
        if demo is None or not demo.active:
            raise HTTPException(status_code=404, detail="Demo not found")
        if (event.event == "mobile_mic_permission") != (event.result is not None):
            raise HTTPException(status_code=422, detail="Event result is invalid")
        client = http_request.client.host if http_request.client else "unknown"
        if not public_event_limiter.allow(scope="event", public_id=public_id, client=client):
            raise HTTPException(status_code=429, detail="Too many events")
        demo_ref = hashlib.sha256(public_id.encode("utf-8")).hexdigest()[:12]
        logger.info(
            "public_demo_event demo_ref=%s event=%s elapsed_ms=%.1f result=%s",
            demo_ref,
            event.event,
            event.elapsed_ms,
            event.result or "none",
        )
        return Response(status_code=204, headers={"Cache-Control": "no-store"})

    @app.post(
        "/api/public/demos/{public_id}/sessions",
        response_model=PublicSessionResponse,
        status_code=201,
    )
    async def create_public_session(
        public_id: str,
        _payload: PublicSessionRequest,
        http_request: Request,
        response: Response,
    ) -> PublicSessionResponse:
        """Create a zero-configuration mobile call from the published snapshot."""
        response.headers["Cache-Control"] = "no-store"
        _validate_session_origin(http_request, _allowed_origins())
        demo = await publication_store.get_public(public_id)
        if demo is None or not demo.active:
            raise HTTPException(status_code=404, detail="Demo not found")
        client = http_request.client.host if http_request.client else "unknown"
        if not public_session_limiter.allow(scope="session", public_id=public_id, client=client):
            raise HTTPException(status_code=429, detail="Too many call attempts")
        resolved = _published_session_request(demo)
        try:
            lease = await store.create(
                request=resolved,
                runtime=runtime,
                voice_catalog=voices,
                llm_catalog=llm_providers,
                bot_id=demo.bot_id,
            )
        except SessionCapacityError as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        event_buffers[lease.session_id] = SessionEventBuffer()
        await _start_history(lease, bot_id=demo.bot_id, bot_name=demo.bot_name)
        return PublicSessionResponse(
            session_id=lease.session_id,
            connection_url=f"/api/public/webrtc/{lease.token}",
            playback_mode=("rtp_candidate" if _uses_task_playback(lease) else "native"),
            ice_servers=[{"urls": url} for url in ice_server_urls],
            expires_in_seconds=runtime.session.pending_token_ttl_seconds,
        )

    def _uses_task_playback(lease: SessionLease) -> bool:
        """Keep the announced protocol and all RTP clock/playback wiring consistent."""
        rule = lease.config.td_config.priority_rule if lease.config.td_config else None
        return lease.config.asr.turn_detection_source == "self_developed" and (
            development_rtp_candidate or bool(rule and rule.enabled)
        )

    async def _run_mobile_connection(lease: SessionLease, connection: Any) -> None:
        """Own recording, history, and cleanup for one negotiated mobile call."""
        recording_path = history_store.recordings_dir / f"{uuid.uuid4()}.flac"
        recorder = AudioRecorder(recording_path, sample_rate=runtime.audio.input_sample_rate)
        await recorder.start()
        capture = CallCapture(
            provider=lease.config.llm.provider,
            model=lease.config.llm.model,
            recorder=recorder,
            chat_mode=False,
        )
        call_captures[lease.session_id] = capture
        status = "completed"
        error_category = None
        diagnostic_id = None
        try:
            transport = create_small_webrtc_transport(
                connection=connection,
                runtime=runtime,
                custom_td=lease.config.asr.turn_detection_source == "self_developed",
                candidate_playback=_uses_task_playback(lease),
            )
            if _uses_task_playback(lease) and hasattr(transport, "td_rtp_input_ledger"):
                capture.rtp_source.begin_epoch(transport.td_rtp_input_ledger.connection_id)
            await run_voice_agent_pipeline(
                playback_protocol=("webrtc_candidate" if _uses_task_playback(lease) else "webrtc"),
                transport=transport,
                lease=lease,
                runtime=runtime,
                asr_registry=asr_registry,
                tts_registry=tts_registry,
                event_buffer=event_buffers[lease.session_id],
                call_capture=capture,
                echo_cache=echo_cache,
            )
        except asyncio.CancelledError:
            status = "disconnected"
            raise
        except Exception as exc:
            status = "failed"
            error_category = (
                ASRSourceEvidenceError.code
                if isinstance(exc, ASRSourceEvidenceError)
                else classify_llm_failure(exc)[0]
            )
            diagnostic_id = str(uuid.uuid4())
            logger.error(
                "mobile_session_failed session_id=%s diagnostic_id=%s category=%s error_type=%s",
                lease.session_id,
                diagnostic_id,
                error_category,
                type(exc).__name__,
            )
            raise
        finally:
            browser_failure = next(
                (item for item in capture.td_events if item.get("event") == "browser_call_failed"),
                None,
            )
            if browser_failure is not None:
                status = "failed"
                error_category = (
                    error_category
                    or browser_failure.get("safe_error_category")
                    or "connection_failed"
                )
            await recorder.stop()
            turns, metrics = capture.finalize()
            await history_store.finish_call(
                call_id=lease.session_id,
                status=status,
                duration_ms=(time.monotonic() - capture.started) * 1000,
                turns=turns,
                metrics=metrics,
                td_events=capture.td_events,
                recording_path=recording_path,
                recording_status=recorder.status,
                error_category=error_category,
                diagnostic_id=diagnostic_id,
            )
            await store.close(lease.session_id)
            event_buffers.pop(lease.session_id, None)
            call_captures.pop(lease.session_id, None)

    @app.post("/api/public/webrtc/{capability}")
    async def webrtc_offer(
        capability: str,
        payload: SmallWebRTCRequest,
        http_request: Request,
        response: Response,
    ) -> dict[str, str]:
        """Negotiate one offer after atomically claiming its session capability."""
        response.headers["Cache-Control"] = "no-store"
        _validate_session_origin(http_request, _allowed_origins())
        try:
            return await webrtc_handler.offer(
                capability=capability,
                request=payload,
                run_connection=_run_mobile_connection,
            )
        except SessionTokenError:
            raise HTTPException(
                status_code=401, detail="Session authorization is invalid"
            ) from None
        except RuntimeError:
            raise HTTPException(
                status_code=503, detail="Voice connection could not start"
            ) from None
        except TimeoutError:
            raise HTTPException(status_code=504, detail="Voice connection timed out") from None

    @app.patch("/api/public/webrtc/{capability}", status_code=204)
    async def webrtc_patch(
        capability: str, payload: SmallWebRTCPatchRequest, http_request: Request
    ) -> Response:
        """Apply ICE candidates only to the capability-bound peer."""
        _validate_session_origin(http_request, _allowed_origins())
        try:
            await webrtc_handler.patch(capability=capability, request=payload)
        except PermissionError:
            raise HTTPException(
                status_code=401, detail="Session authorization is invalid"
            ) from None
        return Response(status_code=204)

    @app.post("/api/sessions", response_model=SessionResponse, status_code=201)
    async def create_session(
        request: SessionRequest | BotSessionRequest, http_request: Request
    ) -> SessionResponse:
        _validate_session_origin(http_request, _allowed_origins())
        resolved = await _resolve_session_request(request)
        try:
            lease = await store.create(
                request=resolved,
                runtime=runtime,
                voice_catalog=voices,
                llm_catalog=llm_providers,
                bot_id=request.bot_id if isinstance(request, BotSessionRequest) else None,
            )
        except SessionCapacityError as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        event_buffers[lease.session_id] = SessionEventBuffer()
        bot_id = request.bot_id if isinstance(request, BotSessionRequest) else None
        bot_name = None
        if bot_id is not None:
            bot_record = await bot_store.get(bot_id)
            bot_name = bot_record.name if bot_record is not None else None
        await _start_history(lease, bot_id=bot_id, bot_name=bot_name)
        return SessionResponse(
            session_id=lease.session_id,
            session_token=lease.token,
            websocket_path=f"/api/ws/{lease.token}",
            expires_in_seconds=runtime.session.pending_token_ttl_seconds,
        )

    @app.post("/api/sessions/{session_id}/events", status_code=204)
    async def browser_event(session_id: str, event: BrowserEvent, request: Request) -> None:
        token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        if not token:
            raise HTTPException(status_code=401, detail="Missing session authorization")
        if event.event == "mobile_call_error" and event.stage == "signaling":
            try:
                cancelled = await store.cancel_pending(session_id=session_id, token=token)
            except SessionTokenError:
                raise HTTPException(
                    status_code=401, detail="Session authorization is invalid"
                ) from None
            if cancelled is not None:
                event_buffers.pop(session_id, None)
                await history_store.finish_call(
                    call_id=session_id,
                    status="failed",
                    duration_ms=0,
                    turns=[],
                    metrics=[],
                    recording_path=None,
                    recording_status="not_started",
                    error_category=event.safe_error_category or "connection_failed",
                    td_events=[
                        {
                            "event": "browser_call_failed",
                            "stage": event.stage,
                            "safe_error_category": event.safe_error_category,
                            "playback_failure_reason": event.playback_failure_reason,
                            "playback_diagnostics": event.playback_diagnostics.model_dump(
                                exclude_none=True
                            )
                            if event.playback_diagnostics
                            else None,
                        }
                    ],
                )
                logger.info(
                    "pending_session_cancelled session_id=%s safe_error_category=%s "
                    "playback_failure_reason=%s",
                    session_id,
                    event.safe_error_category or "connection_failed",
                    event.playback_failure_reason or "none",
                )
                return
        try:
            lease = await store.get_active(session_id=session_id, token=token)
        except SessionTokenError:
            raise HTTPException(
                status_code=401, detail="Session authorization is invalid"
            ) from None
        if event.event == "mobile_call_error" and event.playback_diagnostics is not None:
            logger.info(
                "playback_diagnostics session_id=%s state=%s",
                session_id,
                event.playback_diagnostics.model_dump(exclude_none=True),
            )
        event_buffers[session_id].add(event.event, event.elapsed_ms)
        capture = call_captures.get(session_id)
        if capture is not None:
            if event.event == "chat_text" and event.text:
                capture.chat_text(event.text)
            else:
                capture.browser_event(event.event, event.elapsed_ms)
        if capture is not None and event.event == "mobile_call_error":
            capture.record_td_event(
                {
                    "event": "browser_call_failed",
                    "stage": event.stage,
                    "safe_error_category": event.safe_error_category,
                    "playback_failure_reason": event.playback_failure_reason,
                    "playback_diagnostics": event.playback_diagnostics.model_dump(exclude_none=True)
                    if event.playback_diagnostics
                    else None,
                }
            )
        logger.info(
            "browser_event session_id=%s event=%s elapsed_ms=%.1f candidate_type=%s "
            "network_type=%s end_reason=%s stage=%s safe_error_category=%s "
            "playback_failure_reason=%s",
            lease.session_id,
            event.event,
            event.elapsed_ms,
            event.candidate_type or "none",
            event.network_type or "none",
            event.end_reason or "none",
            event.stage or "none",
            event.safe_error_category or "none",
            event.playback_failure_reason or "none",
        )

        if event.event == "mobile_call_error":
            # Browser teardown is not guaranteed to signal a peer that is still negotiating.
            try:
                await webrtc_handler.cancel_session(capability=token, session_id=session_id)
                history = await history_store.get_call(session_id)
                if history is not None and history.ended_at is None:
                    # A cancelled offer may never start the pipeline/capture finally block.
                    await history_store.finish_call(
                        call_id=session_id,
                        status="failed",
                        duration_ms=0,
                        turns=[],
                        metrics=[],
                        recording_path=None,
                        recording_status="not_started",
                        error_category=event.safe_error_category or "connection_failed",
                        td_events=[
                            {
                                "event": "browser_call_failed",
                                "stage": event.stage,
                                "safe_error_category": event.safe_error_category,
                                "playback_failure_reason": event.playback_failure_reason,
                                "playback_diagnostics": event.playback_diagnostics.model_dump(
                                    exclude_none=True
                                )
                                if event.playback_diagnostics
                                else None,
                            }
                        ],
                    )
                    event_buffers.pop(session_id, None)
            except SessionTokenError:
                pass  # A concurrent disconnect already released this same authenticated lease.

    async def clock_capture(session_id: str, request: Request) -> CallCapture:
        """Resolve only an authenticated live capture; clock requests cannot create one."""
        token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        try:
            await store.get_active(session_id=session_id, token=token)
        except SessionTokenError:
            raise HTTPException(
                status_code=401, detail="Session authorization is invalid"
            ) from None
        capture = call_captures.get(session_id)
        if capture is None:
            raise HTTPException(status_code=409, detail="Live capture is not ready")
        return capture

    @app.post("/api/sessions/{session_id}/playback-clock", status_code=201)
    async def playback_clock_probe(
        session_id: str,
        probe: PlaybackClockProbe,
        request: Request,
    ) -> dict[str, str]:
        """Issue a bounded render challenge without waiting on any audio processing."""
        capture = await clock_capture(session_id, request)
        try:
            ledger = (
                capture.capture_clock if probe.clock_kind == "capture" else capture.render_clock
            )
            sample_id = ledger.issue(probe.render_clock_id, probe.render_sample_rate)
        except ValueError:
            raise HTTPException(status_code=429, detail="Render clock probe rejected") from None
        return {"sample_id": sample_id}

    @app.post("/api/sessions/{session_id}/rtp-input", status_code=204)
    async def rtp_capture_batch(
        session_id: str,
        batch: RTPCaptureBatch,
        request: Request,
    ) -> Response:
        """Match only an authenticated live connection, never client-created PCM extents."""
        capture = await clock_capture(session_id, request)
        if not capture.accept_rtp_packet_records(
            batch.connection_id,
            [record.model_dump() for record in batch.records],
        ):
            raise HTTPException(status_code=409, detail="RTC capture source rejected")
        return Response(status_code=204)

    @app.post("/api/sessions/{session_id}/playback-clock/{sample_id}", status_code=204)
    async def playback_clock_ack(
        session_id: str,
        sample_id: str,
        ack: PlaybackClockAck,
        request: Request,
    ) -> Response:
        """Retain the first valid causal observation; replay cannot refresh its bounds."""
        capture = await clock_capture(session_id, request)
        acknowledge = (
            capture.ack_capture_clock if ack.clock_kind == "capture" else capture.ack_render_clock
        )
        if not acknowledge(
            sample_id,
            ack.render_clock_id,
            ack.render_sample_rate,
            ack.render_frame,
        ):
            raise HTTPException(status_code=409, detail="Render clock acknowledgement is invalid")
        return Response(status_code=204)

    @app.post("/api/sessions/{session_id}/playback-events", status_code=204)
    async def playback_event(session_id: str, event: PlaybackReceipt, request: Request) -> Response:
        """Require this live session and its original prepared audio task identity."""
        token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        try:
            await store.get_active(session_id=session_id, token=token)
        except SessionTokenError:
            raise HTTPException(
                status_code=401, detail="Session authorization is invalid"
            ) from None
        capture = call_captures.get(session_id)
        if capture is None or not capture.playback_receipt(
            event.playback_id,
            event.event,
            event.rendered_samples,
            event.elapsed_ms,
            event.request_id,
            failure_reason=event.failure_reason,
            render_frame=event.render_frame,
            render_sample_rate=event.render_sample_rate,
            render_clock_id=event.render_clock_id,
        ):
            raise HTTPException(status_code=409, detail="Audio task acknowledgement is invalid")
        return Response(status_code=204)

    @app.get("/api/sessions/{session_id}/events")
    async def session_events(session_id: str, request: Request) -> dict[str, object]:
        token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        try:
            await store.get_active(session_id=session_id, token=token)
        except SessionTokenError:
            raise HTTPException(
                status_code=401, detail="Session authorization is invalid"
            ) from None
        return {"events": event_buffers[session_id].snapshot()}

    @app.get("/api/sessions/{session_id}/metrics")
    async def session_metrics(session_id: str, request: Request) -> dict[str, object]:
        """Return in-progress Turn metrics for adjacent live-test rendering."""
        token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        try:
            lease = await store.get_active(session_id=session_id, token=token)
        except SessionTokenError:
            raise HTTPException(
                status_code=401, detail="Session authorization is invalid"
            ) from None
        capture = call_captures.get(session_id)
        return {
            "session_type": lease.session_type,
            "metrics": [] if capture is None else capture.metrics_snapshot(),
        }

    @app.websocket("/api/ws/{token}")
    async def voice_websocket(websocket: WebSocket, token: str) -> None:
        try:
            lease = await store.claim(token)
        except SessionTokenError:
            await websocket.accept()
            await websocket.close(code=4401, reason="Session token is invalid or expired")
            return

        await websocket.accept()
        is_chat = lease.session_type == "chat_test"
        recording_path = history_store.recordings_dir / f"{uuid.uuid4()}.flac"
        recorder = (
            None
            if is_chat
            else AudioRecorder(recording_path, sample_rate=runtime.audio.input_sample_rate)
        )
        if recorder is not None:
            await recorder.start()
        capture = CallCapture(
            provider=lease.config.llm.provider,
            model=lease.config.llm.model,
            recorder=recorder,
            chat_mode=is_chat,
        )
        call_captures[lease.session_id] = capture
        call_status = "completed"
        error_category = None
        diagnostic_id = None
        try:
            await run_voice_agent_session(
                websocket=websocket,
                lease=lease,
                runtime=runtime,
                asr_registry=asr_registry,
                tts_registry=tts_registry,
                allowed_origins=_allowed_origins(),
                event_buffer=event_buffers[lease.session_id],
                call_capture=capture,
                echo_cache=echo_cache,
            )
        except WebSocketDisconnect:
            call_status = "disconnected"
            logger.info("websocket_closed session_id=%s", lease.session_id)
        except Exception as exc:
            call_status = "failed"
            error_category = (
                ASRSourceEvidenceError.code
                if isinstance(exc, ASRSourceEvidenceError)
                else classify_llm_failure(exc)[0]
            )
            diagnostic_id = str(uuid.uuid4())
            # Provider errors can contain request metadata; expose only the error class
            # and message. The message is needed for diagnosing endpoint/model issues.
            logger.error(
                "session_failed session_id=%s diagnostic_id=%s category=%s error_type=%s",
                lease.session_id,
                diagnostic_id,
                error_category,
                type(exc).__name__,
            )
            if (
                websocket.client_state != WebSocketState.DISCONNECTED
                and websocket.application_state != WebSocketState.DISCONNECTED
            ):
                await websocket.close(code=1011, reason="Voice service error")
        finally:
            try:
                if recorder is not None:
                    await recorder.stop()
                turns, metrics = capture.finalize()
                recording_status = "not_applicable" if recorder is None else recorder.status
                await history_store.finish_call(
                    call_id=lease.session_id,
                    status=call_status,
                    duration_ms=(time.monotonic() - capture.started) * 1000,
                    turns=turns,
                    metrics=metrics,
                    td_events=capture.td_events,
                    recording_path=None if is_chat else recording_path,
                    recording_status=recording_status,
                    error_category=error_category,
                    diagnostic_id=diagnostic_id,
                )
            finally:
                try:
                    await store.close(lease.session_id)
                finally:
                    event_buffers.pop(lease.session_id, None)
                    call_captures.pop(lease.session_id, None)

    @app.get("/api/history", response_model=CallListResponse)
    async def list_history(limit: int = 50, offset: int = 0) -> CallListResponse:
        if not 1 <= limit <= 100 or offset < 0:
            raise HTTPException(status_code=422, detail="Invalid pagination")
        return await history_store.list_calls(limit=limit, offset=offset)

    @app.get("/api/history/{call_id}", response_model=CallDetail)
    async def get_history(call_id: str) -> CallDetail:
        call = await history_store.get_call(call_id)
        if call is None:
            raise HTTPException(status_code=404, detail="Call not found")
        return call

    @app.get("/api/history/{call_id}/recording")
    async def get_history_recording(call_id: str) -> FileResponse:
        path = await history_store.recording_path(call_id)
        if path is None:
            raise HTTPException(status_code=404, detail="Recording not available")
        return FileResponse(path, media_type="audio/flac", filename=f"{call_id}.flac")

    @app.delete("/api/history/{call_id}", status_code=204)
    async def delete_history(call_id: str) -> None:
        if not await history_store.delete_call(call_id):
            raise HTTPException(status_code=404, detail="Call not found")

    if FRONTEND_DIST.exists():
        assets_dir = FRONTEND_DIST / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        async def spa_fallback(path: str) -> FileResponse:
            if path.startswith("demo/") and len(path.split("/")) == 2:
                return FileResponse(
                    FRONTEND_DIST / "demo.html", headers={"Cache-Control": "no-store"}
                )
            candidate = FRONTEND_DIST / path
            if path and candidate.is_file() and FRONTEND_DIST in candidate.resolve().parents:
                return FileResponse(
                    candidate,
                    headers={"Cache-Control": "no-store"} if candidate.suffix == ".html" else None,
                )
            return FileResponse(FRONTEND_DIST / "index.html")

    return app


app = create_app()
