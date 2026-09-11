"""Deepgram Flux TTS adapter with confirmed runtime configuration updates."""

from __future__ import annotations

import asyncio
from typing import Any

from pipecat.services.deepgram.flux.tts import DeepgramFluxTTSService


class ConfirmedDeepgramFluxTTSService(DeepgramFluxTTSService):
    """Wait for Flux to accept or reject each serialized Configure request."""

    def __init__(self, *, configure_timeout: float = 2.0, **kwargs: Any) -> None:
        """Initialize the service with a bounded Configure acknowledgement timeout."""
        super().__init__(**kwargs)
        self._configure_timeout = configure_timeout
        self._configure_result: asyncio.Future[None] | None = None

    async def _send_configure(self) -> None:
        """Send speed and return only after Flux confirms the new value."""
        if not self._transport_is_active():
            raise ConnectionError("Flux connection is not active")
        if self._configure_result is not None:
            raise RuntimeError("A Flux Configure request is already pending")

        loop = asyncio.get_running_loop()
        result = loop.create_future()
        self._configure_result = result
        speed = self._settings.speed if self._settings.speed is not None else 1.0
        try:
            await self._transport_send_json({"type": "Configure", "speed": speed})
            await asyncio.wait_for(result, timeout=self._configure_timeout)
        finally:
            self._configure_result = None

    async def _handle_message(self, msg: dict[str, Any]) -> None:
        """Resolve the one in-flight Configure request from its protocol result."""
        result = self._configure_result
        if result is not None and not result.done():
            if msg.get("type") == "ConfigureSuccess":
                result.set_result(None)
            elif msg.get("type") == "ConfigureFailure":
                result.set_exception(
                    RuntimeError(f"Flux rejected speed configuration: {msg.get('code', 'unknown')}")
                )
        await super()._handle_message(msg)

    async def _disconnect(self) -> None:
        """Fail a pending update when the provider connection disappears."""
        result = self._configure_result
        if result is not None and not result.done():
            result.set_exception(ConnectionError("Flux disconnected during Configure"))
        await super()._disconnect()
