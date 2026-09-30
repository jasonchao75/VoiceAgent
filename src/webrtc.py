"""Session-bound Small WebRTC signaling and lifecycle management."""

from __future__ import annotations

import asyncio
import logging
import secrets
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from typing import Any, Protocol

from aiortc import RTCIceServer
from loguru import logger as pipecat_logger
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.smallwebrtc.request_handler import (
    SmallWebRTCPatchRequest,
    SmallWebRTCRequest,
    SmallWebRTCRequestHandler,
)

from src.session import SessionLease, SessionStore, SessionTokenError

logger = logging.getLogger(__name__)


class WebRTCRequestHandler(Protocol):
    """Structural contract used by the protected upstream handler adapter."""

    async def handle_web_request(
        self,
        request: SmallWebRTCRequest,
        callback: Callable[[SmallWebRTCConnection], Awaitable[None]],
    ) -> dict[str, str] | None:
        """Negotiate an offer and invoke the connection callback."""

    async def handle_patch_request(self, request: SmallWebRTCPatchRequest) -> None:
        """Apply trickled ICE candidates to an existing peer connection."""

    async def close(self) -> None:
        """Close all peer connections held by the handler."""


ConnectionRunner = Callable[
    [SessionLease, SmallWebRTCConnection],
    Coroutine[Any, Any, None],
]


@dataclass(slots=True)
class WebRTCBinding:
    """One claimed capability bound to exactly one peer and pipeline task."""

    session_id: str
    pc_id: str
    connection: SmallWebRTCConnection
    task: asyncio.Task[None]


def suppress_sensitive_webrtc_logs() -> None:
    """Disable upstream signaling logs that can include SDP, candidates, or IPs."""
    pipecat_logger.disable("pipecat.transports.smallwebrtc")


class SessionBoundSmallWebRTCHandler:
    """Bind Small WebRTC signaling to single-use VoiceAgent session capabilities."""

    def __init__(
        self,
        *,
        session_store: SessionStore,
        handler: WebRTCRequestHandler | None = None,
        ice_servers: list[RTCIceServer] | None = None,
        offer_timeout_seconds: float = 10.0,
    ) -> None:
        """Create a protected signaling boundary.

        Args:
            session_store: Shared store enforcing expiry, capacity, and single-use claims.
            handler: Optional upstream-compatible handler used by tests.
            ice_servers: Optional STUN-only server configuration for aiortc.
            offer_timeout_seconds: Maximum time allowed for local offer negotiation.
        """
        self._session_store = session_store
        suppress_sensitive_webrtc_logs()
        self._handler = handler or SmallWebRTCRequestHandler(ice_servers=ice_servers)
        self._offer_timeout_seconds = offer_timeout_seconds
        self._bindings: dict[str, WebRTCBinding] = {}
        self._lock = asyncio.Lock()
        self._closing = False

    async def offer(
        self,
        *,
        capability: str,
        request: SmallWebRTCRequest,
        run_connection: ConnectionRunner,
    ) -> dict[str, str]:
        """Claim one session and negotiate its first WebRTC offer.

        Args:
            capability: Opaque single-use session token from the URL.
            request: Browser SDP offer.
            run_connection: Coroutine that owns the pipeline and call lifecycle.

        Returns:
            Sanitized SDP answer produced by Pipecat.

        Raises:
            RuntimeError: If shutdown started or the upstream callback was not registered.
            SessionTokenError: If the capability is missing, expired, or already claimed.
        """
        if self._closing:
            raise RuntimeError("WebRTC signaling is shutting down")
        if request.pc_id is not None:
            return await self._restart_offer(
                capability=capability,
                request=request,
            )
        lease = await self._session_store.claim(capability)
        registered = False
        offer_complete = asyncio.Event()

        async def register(connection: SmallWebRTCConnection) -> None:
            nonlocal registered
            task = asyncio.create_task(
                run_connection(lease, connection),
                name=f"mobile-webrtc-{lease.session_id}",
            )
            binding = WebRTCBinding(
                session_id=lease.session_id,
                pc_id=connection.pc_id,
                connection=connection,
                task=task,
            )
            async with self._lock:
                if self._closing or capability in self._bindings:
                    task.cancel()
                    raise RuntimeError("WebRTC session registration failed")
                self._bindings[capability] = binding
                registered = True
            task.add_done_callback(
                lambda completed: asyncio.create_task(
                    self._finish_binding_after_offer(capability, completed, offer_complete),
                    name=f"mobile-webrtc-cleanup-{lease.session_id}",
                )
            )

        try:
            answer = await asyncio.wait_for(
                self._handler.handle_web_request(request, register),
                timeout=self._offer_timeout_seconds,
            )
            if not registered or answer is None:
                raise RuntimeError("WebRTC pipeline registration failed")
            binding = self._bindings[capability]
            answer_pc_id = answer.get("pc_id", "")
            if not answer_pc_id or not secrets.compare_digest(answer_pc_id, binding.pc_id):
                raise RuntimeError("WebRTC peer registration mismatch")
            offer_complete.set()
            return answer
        except Exception:
            offer_complete.set()
            await self._discard_binding(capability, fallback_session_id=lease.session_id)
            raise

    async def _restart_offer(
        self,
        *,
        capability: str,
        request: SmallWebRTCRequest,
    ) -> dict[str, str]:
        """Renegotiate an existing peer without reclaiming its session lease."""
        async with self._lock:
            binding = self._bindings.get(capability)
        if (
            binding is None
            or request.pc_id is None
            or not secrets.compare_digest(binding.pc_id, request.pc_id)
        ):
            raise SessionTokenError("Session authorization is invalid")

        async def reject_new_connection(_connection: SmallWebRTCConnection) -> None:
            raise RuntimeError("WebRTC restart attempted to register a new pipeline")

        answer = await asyncio.wait_for(
            self._handler.handle_web_request(request, reject_new_connection),
            timeout=self._offer_timeout_seconds,
        )
        if answer is None:
            raise RuntimeError("WebRTC restart negotiation failed")
        answer_pc_id = answer.get("pc_id", "")
        if not answer_pc_id or not secrets.compare_digest(answer_pc_id, binding.connection.pc_id):
            raise RuntimeError("WebRTC peer registration mismatch")
        async with self._lock:
            current = self._bindings.get(capability)
            if current is not binding:
                raise RuntimeError("WebRTC restart registration changed")
            binding.pc_id = answer_pc_id
        return answer

    async def patch(
        self,
        *,
        capability: str,
        request: SmallWebRTCPatchRequest,
    ) -> None:
        """Apply ICE candidates only to the peer registered by this capability.

        Args:
            capability: Opaque capability that created the peer connection.
            request: Candidate patch containing the claimed peer identifier.

        Raises:
            PermissionError: If the capability or peer identifier does not match.
        """
        async with self._lock:
            binding = self._bindings.get(capability)
        if binding is None or not secrets.compare_digest(binding.pc_id, request.pc_id):
            raise PermissionError("WebRTC session authorization is invalid")
        await self._handler.handle_patch_request(request)

    async def close(self) -> None:
        """Stop accepting offers, cancel pipelines, and close all peer connections."""
        self._closing = True
        async with self._lock:
            bindings = list(self._bindings.items())
            self._bindings.clear()
        for _, binding in bindings:
            binding.task.cancel()
        if bindings:
            await asyncio.gather(
                *(binding.task for _, binding in bindings),
                return_exceptions=True,
            )
            await asyncio.gather(
                *(binding.connection.disconnect() for _, binding in bindings),
                return_exceptions=True,
            )
        await self._handler.close()
        for _, binding in bindings:
            await self._session_store.close(binding.session_id)

    async def _finish_binding(
        self,
        capability: str,
        task: asyncio.Task[None],
    ) -> None:
        """Release registry state after the pipeline task reaches a terminal state."""
        try:
            error = task.exception() if not task.cancelled() else None
        except asyncio.InvalidStateError:
            return
        if error is not None:
            logger.error(
                "mobile_webrtc_pipeline_failed error_type=%s",
                type(error).__name__,
            )
        await self._discard_binding(capability)

    async def _finish_binding_after_offer(
        self,
        capability: str,
        task: asyncio.Task[None],
        offer_complete: asyncio.Event,
    ) -> None:
        """Delay task cleanup until the offer response has consumed its binding."""
        await offer_complete.wait()
        await self._finish_binding(capability, task)

    async def _discard_binding(
        self,
        capability: str,
        *,
        fallback_session_id: str | None = None,
    ) -> None:
        """Remove one binding and clear its lease without logging signaling data."""
        async with self._lock:
            binding = self._bindings.pop(capability, None)
        session_id = binding.session_id if binding is not None else fallback_session_id
        if binding is not None:
            if not binding.task.done():
                binding.task.cancel()
                await asyncio.gather(binding.task, return_exceptions=True)
            try:
                await binding.connection.disconnect()
            except Exception as exc:
                logger.warning(
                    "mobile_webrtc_disconnect_failed session_id=%s error_type=%s",
                    binding.session_id,
                    type(exc).__name__,
                )
        if session_id is not None:
            await self._session_store.close(session_id)
