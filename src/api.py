"""FastAPI application for session creation, catalogs, telemetry, and audio WebSockets."""

from __future__ import annotations

import asyncio
import base64
import binascii
import logging
import os
import secrets
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

from src.config import load_llm_provider_catalog, load_runtime_config, load_voice_catalog
from src.observability import SessionEventBuffer
from src.pipeline import run_voice_agent_session
from src.session import (
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
        if scope["type"] != "http" or scope.get("path") == "/health":
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
    if len(password) < 16 or password == "SET_A_STRONG_PASSWORD_BEFORE_DEPLOY":
        raise RuntimeError("VoiceAgent Basic Auth password must be at least 16 characters")
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
    event_buffers: dict[str, SessionEventBuffer] = {}

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        stop = asyncio.Event()

        async def purge_loop() -> None:
            while not stop.is_set():
                try:
                    await asyncio.wait_for(stop.wait(), timeout=15.0)
                except TimeoutError:
                    await store.purge_expired()

        task = asyncio.create_task(purge_loop(), name="session-token-purge")
        try:
            yield
        finally:
            stop.set()
            await task
            await store.close_all()
            event_buffers.clear()

    app = FastAPI(title="English Flux Voice Agent", version="0.1.0", lifespan=lifespan)
    app.state.runtime = runtime
    app.state.voice_catalog = voices
    app.state.llm_catalog = llm_providers
    app.state.session_store = store
    app.state.event_buffers = event_buffers
    app.state.tts_registry = tts_registry

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
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
                "system_prompt": runtime.system_prompt,
                "opening_script": runtime.opening_script,
                "flux_voice": runtime.tts.voice,
                "audio": runtime.audio.model_dump(),
            },
            "flux_voices": voices.model_dump(),
            "llm_providers": llm_providers.model_dump(),
        }

    @app.post("/api/sessions", response_model=SessionResponse, status_code=201)
    async def create_session(request: SessionRequest, http_request: Request) -> SessionResponse:
        _validate_session_origin(http_request, _allowed_origins())
        try:
            lease = await store.create(
                request=request,
                runtime=runtime,
                voice_catalog=voices,
                llm_catalog=llm_providers,
            )
        except SessionCapacityError as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        event_buffers[lease.session_id] = SessionEventBuffer()
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
        try:
            await run_voice_agent_session(
                websocket=websocket,
                lease=lease,
                runtime=runtime,
                tts_registry=tts_registry,
                allowed_origins=_allowed_origins(),
                event_buffer=event_buffers[lease.session_id],
            )
        except WebSocketDisconnect:
            logger.info("websocket_closed session_id=%s", lease.session_id)
        except Exception as exc:
            # Provider errors can contain request metadata; expose only the error class.
            logger.error(
                "session_failed session_id=%s error_type=%s",
                lease.session_id,
                type(exc).__name__,
            )
            if websocket.client_state.name != "DISCONNECTED":
                await websocket.close(code=1011, reason="Voice service error")
        finally:
            await store.close(lease.session_id)
            event_buffers.pop(lease.session_id, None)

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
