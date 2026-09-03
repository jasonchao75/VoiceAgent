"""FastAPI application for session creation, catalogs, telemetry, and audio WebSockets."""

from __future__ import annotations

import asyncio
import base64
import binascii
import logging
import os
import secrets
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.datastructures import Headers
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from src.bots.crypto import BotKeyCipher, StorageKeyError
from src.bots.models import (
    BotConfigFields,
    BotCreateRequest,
    BotResponse,
    BotUpdateRequest,
)
from src.bots.storage import BotStore
from src.bots.validation import validate_bot_config
from src.config import load_llm_provider_catalog, load_runtime_config, load_voice_catalog
from src.history import AudioRecorder, CallCapture, HistoryStore
from src.history.models import CallDetail, CallListResponse
from src.llm.diagnostics import (
    DiagnosticConfig,
    LLMDiagnosticRequest,
    LLMDiagnosticResult,
    classify_llm_failure,
    run_llm_diagnostic,
)
from src.observability import SessionEventBuffer
from src.pipeline import run_voice_agent_session
from src.session import (
    BotSessionRequest,
    SessionCapacityError,
    SessionRequest,
    SessionStore,
    SessionTokenError,
)
from src.tts import create_default_tts_registry

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"

logging.basicConfig(
    level=getattr(logging, os.getenv("VOICE_AGENT_LOG_LEVEL", "INFO").upper(), logging.INFO)
)


class BasicAuthMiddleware:
    """Protect public HTTP routes while leaving health and tokenized WebSockets usable."""

    def __init__(self, app: ASGIApp, *, username: str, password: str) -> None:
        """Initialize constant-time Basic Auth checks.

        Args:
            app: Wrapped ASGI application.
            username: Deployment-only HTTP Basic username.
            password: Deployment-only HTTP Basic password.
        """
        self._app = app
        self._username = username
        self._password = password

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Challenge unauthorized HTTP requests and pass other scopes through."""
        if (
            scope["type"] != "http"
            or scope.get("path") == "/health"
            or self._uses_session_bearer_auth(scope)
        ):
            await self._app(scope, receive, send)
            return

        authorization = Headers(scope=scope).get("authorization", "")
        if self._is_authorized(authorization):
            await self._app(scope, receive, send)
            return

        response = PlainTextResponse(
            "Authentication required",
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="VoiceAgent Demo", charset="UTF-8"'},
        )
        await response(scope, receive, send)

    @staticmethod
    def _uses_session_bearer_auth(scope: Scope) -> bool:
        """Leave session telemetry authorization to its single-use bearer token.

        Basic Auth must not challenge these requests because browsers interpret
        that challenge as a fresh login prompt, even when a valid bearer token
        was supplied by the active voice session.
        """
        parts = scope.get("path", "").rstrip("/").split("/")
        return len(parts) == 5 and parts[1:3] == ["api", "sessions"] and parts[4] == "events"

    def _is_authorized(self, authorization: str) -> bool:
        """Validate one Basic Authorization header without logging credentials."""
        scheme, separator, encoded = authorization.partition(" ")
        if not separator or scheme.lower() != "basic":
            return False
        try:
            decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError, ValueError):
            return False
        username, separator, password = decoded.partition(":")
        if not separator:
            return False
        username_matches = secrets.compare_digest(username, self._username)
        password_matches = secrets.compare_digest(password, self._password)
        return username_matches and password_matches


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


class BrowserEvent(BaseModel):
    """Whitelisted browser playback event used for interruption timing."""

    model_config = ConfigDict(extra="forbid")
    event: str = Field(pattern="^(first_playback|audio_stopped|browser_interruption)$")
    elapsed_ms: float = Field(ge=0, le=7_200_000)


def _allowed_origins() -> list[str]:
    raw = os.getenv(
        "VOICE_AGENT_ALLOWED_ORIGINS",
        "http://localhost:8000,http://127.0.0.1:8000,http://localhost:5173,http://127.0.0.1:5173",
    )
    return [item.strip() for item in raw.split(",") if item.strip()]


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


def create_app() -> FastAPI:
    """Create an application with validated configuration and isolated state."""
    runtime = load_runtime_config()
    voices = load_voice_catalog()
    llm_providers = load_llm_provider_catalog()
    store = SessionStore(
        token_ttl_seconds=runtime.session.pending_token_ttl_seconds,
        max_sessions=runtime.session.max_concurrent_sessions,
    )
    tts_registry = create_default_tts_registry()
    bot_store = BotStore(_bot_data_dir() / "bots.db")
    bot_cipher = BotKeyCipher.from_env()
    event_buffers: dict[str, SessionEventBuffer] = {}
    call_captures: dict[str, CallCapture] = {}
    history_store = HistoryStore(_bot_data_dir())

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await bot_store.initialize()
        await history_store.initialize()
        await history_store.cleanup()
        stop = asyncio.Event()

        async def purge_loop() -> None:
            while not stop.is_set():
                try:
                    await asyncio.wait_for(stop.wait(), timeout=15.0)
                except TimeoutError:
                    await store.purge_expired()
                    await history_store.cleanup()

        task = asyncio.create_task(purge_loop(), name="session-token-purge")
        try:
            yield
        finally:
            stop.set()
            await task
            await store.close_all()
            event_buffers.clear()
            call_captures.clear()

    app = FastAPI(title="English Flux Voice Agent", version="0.1.0", lifespan=lifespan)
    app.state.runtime = runtime
    app.state.voice_catalog = voices
    app.state.llm_catalog = llm_providers
    app.state.session_store = store
    app.state.event_buffers = event_buffers
    app.state.tts_registry = tts_registry
    app.state.bot_store = bot_store
    app.state.bot_cipher = bot_cipher
    app.state.history_store = history_store

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
    )
    basic_auth = _basic_auth_credentials()
    if basic_auth is not None:
        app.add_middleware(
            BasicAuthMiddleware,
            username=basic_auth[0],
            password=basic_auth[1],
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
            "pending_sessions": pending,
            "active_sessions": active,
        }

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
        }

    def _config_fields(request: BotCreateRequest | BotUpdateRequest) -> BotConfigFields:
        """Strip write-only key fields before persistence."""
        return BotConfigFields.model_validate(
            request.model_dump(exclude={"save_keys", "deepgram_api_key", "llm_api_key"})
        )

    def _validate_bot_payload(config: BotConfigFields) -> None:
        try:
            validate_bot_config(
                config=config,
                voice_catalog=voices,
                llm_catalog=llm_providers,
                tts_providers=tts_registry.providers,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None

    def _encrypt_bot_keys(
        request: BotCreateRequest | BotUpdateRequest,
    ) -> tuple[str | None, str | None]:
        """Encrypt a submitted key pair, or (None, None) when not saving keys."""
        if not request.save_keys:
            return None, None
        if bot_cipher is None:
            raise HTTPException(
                status_code=400,
                detail="Saving API keys is disabled: VOICE_AGENT_STORAGE_KEY is not configured",
            )
        assert request.deepgram_api_key is not None and request.llm_api_key is not None
        return (
            bot_cipher.encrypt(request.deepgram_api_key),
            bot_cipher.encrypt(request.llm_api_key),
        )

    @app.get("/api/bots", response_model=list[BotResponse])
    async def list_bots() -> list[BotResponse]:
        return [BotResponse.from_record(record) for record in await bot_store.list()]

    @app.post("/api/bots", response_model=BotResponse, status_code=201)
    async def create_bot(request: BotCreateRequest) -> BotResponse:
        _validate_bot_payload(request)
        encrypted_deepgram_key, encrypted_llm_key = _encrypt_bot_keys(request)
        record = await bot_store.create(
            config=_config_fields(request),
            encrypted_deepgram_key=encrypted_deepgram_key,
            encrypted_llm_key=encrypted_llm_key,
        )
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
        _validate_bot_payload(request)
        if not request.save_keys:
            encrypted_pair: tuple[str | None, str | None] = (None, None)
        elif request.deepgram_api_key is None:
            # No key fields means keep the stored ciphertext untouched.
            if not existing.has_saved_keys:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "This bot has no saved keys to keep; "
                        "provide both API keys or disable save_keys"
                    ),
                )
            encrypted_pair = (existing.encrypted_deepgram_key, existing.encrypted_llm_key)
        else:
            encrypted_pair = _encrypt_bot_keys(request)
        record = await bot_store.update(
            bot_id,
            config=_config_fields(request),
            encrypted_deepgram_key=encrypted_pair[0],
            encrypted_llm_key=encrypted_pair[1],
        )
        assert record is not None
        return BotResponse.from_record(record)

    @app.delete("/api/bots/{bot_id}", status_code=204)
    async def delete_bot(bot_id: str) -> None:
        if not await bot_store.delete(bot_id):
            raise HTTPException(status_code=404, detail="Bot not found")

    async def _resolve_session_request(
        request: SessionRequest | BotSessionRequest,
    ) -> SessionRequest:
        """Map a bot-based session request onto the canonical inline shape."""
        if isinstance(request, SessionRequest):
            return request
        record = await bot_store.get(request.bot_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Bot not found")
        if record.has_saved_keys:
            if request.deepgram_api_key is not None or request.llm_api_key is not None:
                raise HTTPException(
                    status_code=422,
                    detail="This bot already has saved keys; do not submit session keys",
                )
            if bot_cipher is None:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "This bot has saved keys but VOICE_AGENT_STORAGE_KEY is not configured"
                    ),
                )
            assert (
                record.encrypted_deepgram_key is not None and record.encrypted_llm_key is not None
            )
            try:
                deepgram_key = bot_cipher.decrypt(record.encrypted_deepgram_key)
                llm_key = bot_cipher.decrypt(record.encrypted_llm_key)
            except StorageKeyError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from None
        else:
            if request.deepgram_api_key is None or request.llm_api_key is None:
                raise HTTPException(
                    status_code=422,
                    detail="This bot has no saved keys; provide both API keys for this session",
                )
            deepgram_key = request.deepgram_api_key
            llm_key = request.llm_api_key
        return SessionRequest(
            deepgram_api_key=deepgram_key,
            llm_api_key=llm_key,
            llm_provider=record.llm_provider,
            llm_base_url=record.llm_base_url,
            llm_model=record.llm_model,
            reasoning_mode=record.reasoning_mode,
            system_prompt=record.system_prompt,
            opening_script=record.opening_script,
            flux_voice=record.tts_voice,
        )

    async def _resolve_diagnostic(request: LLMDiagnosticRequest) -> DiagnosticConfig:
        """Resolve a diagnostic request without returning or persisting its key."""
        if request.bot_id:
            record = await bot_store.get(request.bot_id)
            if record is None:
                raise HTTPException(status_code=404, detail="Bot not found")
            key = request.llm_api_key
            if record.has_saved_keys:
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
            return DiagnosticConfig(
                provider=record.llm_provider,
                base_url=record.llm_base_url,
                model=record.llm_model,
                api_key=key.get_secret_value(),
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
            deepgram_api_key=validation_key,
            llm_api_key=request.llm_api_key,
            llm_provider=request.llm_provider,
            llm_base_url=request.llm_base_url,
            llm_model=request.llm_model,
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
            timeout=validated.llm.timeout_seconds,
        )

    @app.post("/api/llm/diagnostics", response_model=LLMDiagnosticResult)
    async def diagnose_llm(
        request: LLMDiagnosticRequest, http_request: Request
    ) -> LLMDiagnosticResult:
        _validate_session_origin(http_request, _allowed_origins())
        config = await _resolve_diagnostic(request)
        result = await run_llm_diagnostic(config)
        logger.info(
            "llm_diagnostic diagnostic_id=%s provider=%s host=%s model=%s category=%s",
            result.diagnostic_id,
            result.provider,
            result.base_url_host,
            result.model,
            result.category,
        )
        return result

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
        await history_store.start_call(
            call_id=lease.session_id,
            bot_id=bot_id,
            bot_name=bot_name,
            llm_provider=lease.config.llm.provider,
            llm_model=lease.config.llm.model,
            asr_provider=runtime.asr.provider,
            asr_model=runtime.asr.model,
            language=runtime.language,
            sample_rate=runtime.audio.input_sample_rate,
            channels=runtime.audio.channels,
        )
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
        try:
            lease = await store.get_active(session_id=session_id, token=token)
        except SessionTokenError:
            raise HTTPException(
                status_code=401, detail="Session authorization is invalid"
            ) from None
        event_buffers[session_id].add(event.event, event.elapsed_ms)
        capture = call_captures.get(session_id)
        if capture is not None:
            capture.browser_event(event.event, event.elapsed_ms)
        logger.info(
            "browser_event session_id=%s event=%s elapsed_ms=%.1f",
            lease.session_id,
            event.event,
            event.elapsed_ms,
        )

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

    @app.websocket("/api/ws/{token}")
    async def voice_websocket(websocket: WebSocket, token: str) -> None:
        try:
            lease = await store.claim(token)
        except SessionTokenError:
            await websocket.accept()
            await websocket.close(code=4401, reason="Session token is invalid or expired")
            return

        await websocket.accept()
        recording_path = history_store.recordings_dir / f"{uuid.uuid4()}.flac"
        recorder = AudioRecorder(recording_path, sample_rate=runtime.audio.input_sample_rate)
        await recorder.start()
        capture = CallCapture(
            provider=lease.config.llm.provider,
            model=lease.config.llm.model,
            recorder=recorder,
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
                tts_registry=tts_registry,
                allowed_origins=_allowed_origins(),
                event_buffer=event_buffers[lease.session_id],
                call_capture=capture,
            )
        except WebSocketDisconnect:
            call_status = "disconnected"
            logger.info("websocket_closed session_id=%s", lease.session_id)
        except Exception as exc:
            call_status = "failed"
            error_category, _, _ = classify_llm_failure(exc)
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
            if websocket.client_state.name != "DISCONNECTED":
                await websocket.close(code=1011, reason="Voice service error")
        finally:
            await recorder.stop()
            turns, metrics = capture.finalize()
            await history_store.finish_call(
                call_id=lease.session_id,
                status=call_status,
                duration_ms=(time.monotonic() - capture.started) * 1000,
                turns=turns,
                metrics=metrics,
                recording_path=recording_path,
                recording_status=recorder.status,
                error_category=error_category,
                diagnostic_id=diagnostic_id,
            )
            await store.close(lease.session_id)
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
            candidate = FRONTEND_DIST / path
            if path and candidate.is_file() and FRONTEND_DIST in candidate.resolve().parents:
                return FileResponse(candidate)
            return FileResponse(FRONTEND_DIST / "index.html")

    return app


app = create_app()
