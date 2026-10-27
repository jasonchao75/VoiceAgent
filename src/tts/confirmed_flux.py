"""Deepgram Flux TTS adapter with confirmed runtime configuration updates."""

from __future__ import annotations

import asyncio
import math
from collections.abc import AsyncGenerator
from typing import Any

from pipecat.frames.frames import Frame
from pipecat.services.deepgram.flux.tts import DeepgramFluxTTSService


class ConfirmedDeepgramFluxTTSService(DeepgramFluxTTSService):
    """Confirm configuration and fence untagged audio across provider interruptions."""

    def __init__(
        self, *, configure_timeout: float = 2.0, interrupt_timeout: float = 2.0, **kwargs: Any
    ) -> None:
        """Initialize the service with a bounded Configure acknowledgement timeout."""
        if not math.isfinite(interrupt_timeout) or interrupt_timeout <= 0:
            raise ValueError("Flux interrupt timeout must be positive and finite")
        super().__init__(**kwargs)
        self._configure_timeout = configure_timeout
        self._configure_result: asyncio.Future[None] | None = None
        self._interrupt_timeout = interrupt_timeout
        self._interrupt_ready = asyncio.Event()
        self._interrupt_ready.set()
        self._interrupt_deadline = 0.0
        self._interrupt_error: str | None = None
        self._interrupt_sender: asyncio.Task[None] | None = None
        self._interrupt_senders: set[asyncio.Task[None]] = set()
        self._interrupt_generation = 0
        self._interrupt_confirmed_generation = 0

    async def on_audio_context_interrupted(self, context_id: str) -> None:
        """Send one Interrupt; raw bytes cannot identify their abandoned speech turn."""
        if self._interrupt_error or not self._interrupt_ready.is_set():
            return
        if not self._transport_is_active():
            return
        self._interrupt_ready.clear()
        self._interrupt_deadline = asyncio.get_running_loop().time() + self._interrupt_timeout
        # The SDK forwards InterruptionFrame only after this hook returns.
        self._interrupt_generation += 1
        self._interrupt_sender = asyncio.create_task(
            self._send_interrupt(self._interrupt_generation, self._interrupt_deadline)
        )
        self._interrupt_senders.add(self._interrupt_sender)
        self._interrupt_sender.add_done_callback(self._interrupt_senders.discard)

    async def _send_interrupt(self, generation: int, deadline: float) -> None:
        """Bound network backpressure without holding up the local playback-stop frame."""
        try:
            # The pinned provider hook only sends Interrupt; queue cleanup belongs to its caller.
            await asyncio.wait_for(
                self._transport_send_json({"type": "Interrupt"}),
                max(0, deadline - asyncio.get_running_loop().time()),
            )
        except Exception:
            # A received ACK proves the old write crossed the wire even if drain is still pending.
            if (
                generation == self._interrupt_generation
                and generation != self._interrupt_confirmed_generation
                and self._interrupt_error is None
            ):
                self._interrupt_error = "send_failed"
                self._interrupt_ready.set()

    async def _handle_audio(self, audio: bytes) -> None:
        """Discard in-flight old bytes until the provider proves its cancellation boundary."""
        if self._interrupt_error or not self._interrupt_ready.is_set():
            return
        await super()._handle_audio(audio)

    async def run_tts(self, text: str, context_id: str) -> AsyncGenerator[Frame | None, None]:
        """Bound the next Speak by the original Interrupt deadline, never by a new timer."""
        if not self._interrupt_ready.is_set() and not self._interrupt_error:
            remaining = self._interrupt_deadline - asyncio.get_running_loop().time()
            try:
                await asyncio.wait_for(self._interrupt_ready.wait(), max(0, remaining))
            except TimeoutError:
                self._interrupt_error = "ack_timeout"
        if self._interrupt_error:
            await self.push_error(
                "Flux interruption acknowledgement unconfirmed",
                force_treat_as_permanent=True,
            )
            return
        async for frame in super().run_tts(text, context_id):
            yield frame

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
        kind = msg.get("type")
        if not self._interrupt_ready.is_set():
            if kind == "SpeechMetadata":
                # Old completion must not close the newly allocated local context.
                return
            if kind == "SpeechInterrupted" or (
                kind == "Warning" and msg.get("code") in {"NO_ACTIVE_SPEECH", "NO_AUDIO_GENERATED"}
            ):
                if asyncio.get_running_loop().time() > self._interrupt_deadline:
                    self._interrupt_error = "ack_timeout"
                else:
                    self._interrupt_confirmed_generation = self._interrupt_generation
                self._interrupt_ready.set()
            elif kind == "Error":
                self._interrupt_error = "provider_error"
                self._interrupt_ready.set()
        if self._interrupt_error and kind in {
            "SpeechStarted",
            "SpeechMetadata",
            "SpeechInterrupted",
        }:
            return
        result = self._configure_result
        if result is not None and not result.done():
            if msg.get("type") == "ConfigureSuccess":
                result.set_result(None)
            elif msg.get("type") == "ConfigureFailure":
                result.set_exception(
                    RuntimeError(f"Flux rejected speed configuration: {msg.get('code', 'unknown')}")
                )
        await super()._handle_message(msg)

    async def _cancel_interrupt_sender(self) -> None:
        """Join the session-owned sender so it cannot survive service teardown."""
        senders = [task for task in self._interrupt_senders if task is not asyncio.current_task()]
        self._interrupt_sender = None
        for task in senders:
            task.cancel()
        await asyncio.gather(*senders, return_exceptions=True)
        self._interrupt_senders.difference_update(senders)

    async def cleanup(self) -> None:
        """Never leave a detached provider control task behind after pipeline cleanup."""
        await self._cancel_interrupt_sender()
        await super().cleanup()

    async def _disconnect(self) -> None:
        """Fail pending configuration/cancellation when the provider connection disappears."""
        if not self._interrupt_ready.is_set():
            self._interrupt_error = self._interrupt_error or "disconnected"
            self._interrupt_ready.set()
        result = self._configure_result
        if result is not None and not result.done():
            result.set_exception(ConnectionError("Flux disconnected during Configure"))
        await self._cancel_interrupt_sender()
        await super()._disconnect()
