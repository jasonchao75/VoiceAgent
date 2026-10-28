"""Serialize prepared audio through the existing transport until matching renderer evidence."""

from __future__ import annotations

import asyncio
import math
import uuid
from collections import deque
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any, cast

from pipecat.frames.frames import (
    CancelFrame,
    EndFrame,
    ErrorFrame,
    Frame,
    InterruptionFrame,
    OutputTransportMessageFrame,
    OutputTransportMessageUrgentFrame,
    StartFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from src.pipeline.audio_identity import TaskAudioFrame, audio_frame_type
from src.pipeline.playback import PlaybackArbiter, PlaybackKind
from src.pipeline.response_revision import ResponseRevisions


@dataclass
class _AudioBuffer:
    """One task's pending PCM; production end and actual render end are separate."""

    identity: dict[str, Any]
    valid: Callable[[], bool]
    frames: deque[TaskAudioFrame] = field(default_factory=deque)
    ended: bool = False
    end_sent: bool = False
    started_sending: bool = False
    failed: bool = False


class SerialAudioOutput(FrameProcessor):
    """One session output authority with bounded buffering and explicit unknown playback."""

    def __init__(
        self,
        *,
        responses: ResponseRevisions,
        evidence_sink: Callable[[dict[str, Any]], None] | None = None,
        max_buffer_bytes: int = 24000 * 2 * 60,
        stop_confirmation_timeout: float = 5.0,
    ) -> None:
        """Create a nonblocking actor; no completion is inferred from server audio sends."""
        super().__init__()
        self.responses = responses
        self._sink = evidence_sink
        self.arbiter = PlaybackArbiter(evidence_sink)
        self._buffers: dict[str, _AudioBuffer] = {}
        self._descriptors: dict[str, dict[str, Any]] = {}
        self._invalidated: set[str] = set()
        self._source_failures: dict[str, str] = {}
        self._wake = asyncio.Event()
        self._pump_task: asyncio.Task[None] | None = None
        self._jobs: dict[str, asyncio.Task[None]] = {}
        self._closed = False
        self._bytes = 0
        self._sent_bytes: dict[str, int] = {}
        self._limit = max_buffer_bytes
        self._order = 0
        self._source_orders: dict[tuple[int, str], int] = {}
        self._stop_cursor = 0
        self._stop_timeout = stop_confirmation_timeout
        self._stop_guards: dict[str, asyncio.Task[None]] = {}
        if max_buffer_bytes < 2:
            raise ValueError("Output buffer must hold PCM samples")
        if not math.isfinite(stop_confirmation_timeout) or stop_confirmation_timeout <= 0:
            raise ValueError("Stop confirmation timeout must be positive and finite")

    async def _guard_stop_confirmation(self, playback_id: str) -> None:
        """Fail the session if a requested renderer stop remains unconfirmed.

        Args:
            playback_id: The immutable active task whose real stop is required.
        """
        try:
            await asyncio.sleep(self._stop_timeout)
            task = self.arbiter._active
            if (
                not self._closed
                and task is not None
                and task.playback_id == playback_id
                and task.status == "stop_requested"
            ):
                self._record(
                    "playback_stop_unconfirmed",
                    playback_id=playback_id,
                    reason="client_stop_confirmation_timeout",
                )
                self._closed = True
                self._wake.set()
                await self.push_error(
                    error_msg="Audio playback stop could not be verified",
                    force_treat_as_permanent=True,
                )
        finally:
            self._stop_guards.pop(playback_id, None)

    def _record(self, event: str, **fields: Any) -> None:
        """Keep original identities and failures without asserting audible playback."""
        if self._sink:
            self._sink({"event": event, **fields})

    def _drop_buffer(self, playback_id: str) -> None:
        """Free queued samples without erasing prepared/started facts in the arbiter."""
        buffer = self._buffers.pop(playback_id, None)
        if buffer:
            self._bytes -= sum(len(frame.audio) for frame in buffer.frames)
        job = self._jobs.get(playback_id)
        if job and not job.done() and job is not asyncio.current_task():
            job.cancel()

    def source_failure(self, playback_id: str) -> str | None:
        """Return a source failure type without inventing a renderer outcome.

        Args:
            playback_id: Immutable original audio job identity.

        Returns:
            The captured exception class name, or None when no source failure occurred.
        """
        return self._source_failures.get(playback_id)

    def source_order(self, source_id: str, generation: int) -> int:
        """Share one logical order for observed input ranges and ready ordinary responses."""
        key = (generation, source_id)
        if key not in self._source_orders:
            self._order += 1
            self._source_orders[key] = self._order
        return self._source_orders[key]

    def clear(self, generation: int) -> None:
        """Invalidate old collection jobs and await actual stop for any sent identifier audio."""
        self.arbiter.clear(generation)
        for identity, task in list(self.arbiter.tasks.items()):
            if task.status == "cancelled_unplayed":
                self._drop_buffer(identity)
        for identity, descriptor in list(self._descriptors.items()):
            if descriptor["kind"] != "normal" and descriptor["generation"] != generation:
                job = self._jobs.get(identity)
                if job and not job.done():
                    job.cancel()
        self._wake.set()

    def receipt(self, playback_id: str, event: str) -> bool:
        """Release only matching active output after a real renderer terminal event."""
        task = self.arbiter.tasks.get(playback_id)
        if task is None:
            return False
        if task.status in {"finished", "stopped", "failed", "ended_started", "ended_unknown"}:
            return True
        if self.arbiter._active is not task:
            return False
        if event == "task_started":
            accepted = self.arbiter.client_started(playback_id)
        elif event in {"task_finished", "task_stopped", "task_failed"}:
            buffer = self._buffers.get(playback_id)
            if event == "task_finished" and (buffer is None or not buffer.end_sent):
                return False
            accepted = self.arbiter.client_finished(playback_id, event=event)
            if accepted:
                guard = self._stop_guards.pop(playback_id, None)
                if guard:
                    guard.cancel()
                self._drop_buffer(playback_id)
        else:
            return False
        self._wake.set()
        return accepted

    async def stream_audio(
        self,
        *,
        playback_id: str,
        kind: PlaybackKind,
        generation: int,
        source_id: str,
        revision: int,
        source_order: int,
        samples: AsyncIterator[bytes],
        valid: Callable[[], bool],
        sample_rate: int = 24000,
        final_segment: bool = False,
        reserve_order: bool = False,
        turn_id: int | None = None,
    ) -> None:
        """Prepare async cached/recovered audio; late results never bypass source fences."""
        self._descriptors[playback_id] = {
            "kind": kind,
            "generation": generation,
            "source_id": source_id,
            "revision": revision,
            "source_order": source_order,
            "valid": valid,
            "final_segment": final_segment,
            "turn_id": turn_id,
        }
        self._jobs[playback_id] = asyncio.current_task()  # type: ignore[assignment]
        cls = audio_frame_type(playback_id=playback_id, kind=kind, response_id=None)
        try:
            # Reserve source order before any asynchronous cache read can overtake it.
            if reserve_order:
                await self._audio(cls(b"", sample_rate, 1))
            async for pcm in samples:
                if self._closed or (kind != "normal" and generation != self.arbiter.generation):
                    return
                task = self.arbiter.tasks.get(playback_id)
                if (task is None or task.status == "queued") and not valid():
                    return
                if task and task.status not in {"queued", "sent_unknown", "playing"}:
                    return
                await self._audio(cls(pcm, sample_rate, 1))
            self._end(playback_id)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._source_failures[playback_id] = type(error).__name__
            self._record(
                "playback_source_failed",
                playback_id=playback_id,
                error_type=type(error).__name__,
                turn_id=turn_id,
                source_id=source_id,
                collection_generation=generation,
            )
            buffer = self._buffers.get(playback_id)
            task = self.arbiter.tasks.get(playback_id)
            if buffer is not None:
                buffer.failed = True
                self._bytes -= sum(len(frame.audio) for frame in buffer.frames)
                buffer.frames.clear()
            if task is not None:
                if task.status == "queued":
                    self.arbiter._cancel_unplayed(task)
                    self._drop_buffer(playback_id)
                elif self.arbiter._active is task:
                    # Already-sent PCM remains unknown until an actual stop receipt.
                    self.arbiter._request_stop(task)
            self._wake.set()
            await self.push_frame(ErrorFrame(error="Identifier echo audio resource unavailable"))
        finally:
            self._jobs.pop(playback_id, None)

    async def _audio(self, frame: TaskAudioFrame) -> None:
        """Buffer without blocking ASR/Jev; overflow is diagnosed rather than silently growing."""
        identity = dict(frame.task_identity)
        playback_id = str(identity["playback_id"])
        if self._closed or playback_id in self._invalidated:
            return
        buffer = self._buffers.get(playback_id)
        if buffer is None:
            if playback_id in self.arbiter.tasks:
                return
            self._order += 1
            response_id = identity["response_id"]
            descriptor = self._descriptors.get(playback_id, {})
            valid = descriptor.get(
                "valid", lambda: response_id is None or self.responses.accepts_output(response_id)
            )
            if not valid():
                self._invalidated.add(playback_id)
                return
            task = self.arbiter.enqueue(
                playback_id=playback_id,
                kind=cast(PlaybackKind, identity["kind"]),
                generation=descriptor.get("generation", self.arbiter.generation),
                source_id=descriptor.get("source_id", "response:" + playback_id),
                revision=descriptor.get("revision", 1),
                source_order=descriptor.get("source_order", self._order),
                final_segment=descriptor.get("final_segment", False),
            )
            if task is None:
                return
            buffer = _AudioBuffer(identity, valid)
            self._buffers[playback_id] = buffer
            if descriptor:
                self._record(
                    "playback_task_prepared",
                    **identity,
                    turn_id=descriptor.get("turn_id"),
                    source_id=descriptor.get("source_id"),
                    source_revision=descriptor.get("revision"),
                    collection_generation=descriptor.get("generation"),
                )
        task = self.arbiter.tasks[playback_id]
        if buffer.failed or task.status in {
            "cancelled_unplayed",
            "stop_requested",
            "finished",
            "stopped",
        }:
            return
        if self._bytes + len(frame.audio) > self._limit:
            buffer.failed = True
            self._record(
                "playback_buffer_failed",
                playback_id=playback_id,
                reason="server_output_queue_limit",
            )
            if task.status == "queued":
                self.arbiter._cancel_unplayed(task)
                self._drop_buffer(playback_id)
            else:
                self.arbiter._request_stop(task)
            await self.push_frame(ErrorFrame(error="Voice output queue limit exceeded"))
        elif frame.audio:
            buffer.frames.append(frame)
            self._bytes += len(frame.audio)
        self._wake.set()

    def _end(self, playback_id: str) -> None:
        """Mark source EOS, not renderer completion."""
        buffer = self._buffers.get(playback_id)
        if buffer:
            buffer.ended = True
            self._wake.set()

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        """Route only one task's PCM; unrelated control/media continue asynchronously."""
        await super().process_frame(frame, direction)
        if direction != FrameDirection.DOWNSTREAM:
            await self.push_frame(frame, direction)
            return
        if isinstance(frame, StartFrame):
            self._pump_task = asyncio.create_task(self._run_pump())
        elif isinstance(frame, (CancelFrame, EndFrame)):
            self._closed = True
            self.arbiter.close()
            guards = list(self._stop_guards.values())
            for guard in guards:
                guard.cancel()
            await asyncio.gather(*guards, return_exceptions=True)
            self._stop_guards.clear()
            for job in list(self._jobs.values()):
                job.cancel()
            if self._pump_task:
                self._pump_task.cancel()
                await asyncio.gather(self._pump_task, return_exceptions=True)
            await asyncio.gather(*list(self._jobs.values()), return_exceptions=True)
            self._buffers.clear()
            self._bytes = 0
        elif isinstance(frame, TaskAudioFrame):
            await self._audio(frame)
            return
        elif isinstance(frame, (TTSStartedFrame, TTSStoppedFrame)):
            return
        elif (
            isinstance(frame, (OutputTransportMessageFrame, OutputTransportMessageUrgentFrame))
            and frame.message.get("label") == "voice-agent-playback"
        ):
            identity = frame.message.get("playback_id")
            if frame.message.get("event") == "task_end":
                self._end(identity)
            elif frame.message.get("event") == "stop_task":
                task = self.arbiter.tasks.get(identity)
                if task is None:
                    self._invalidated.add(identity)
                elif task.status == "queued":
                    self.arbiter._cancel_unplayed(task)
                    self._drop_buffer(identity)
                elif self.arbiter._active is task:
                    self.arbiter._request_stop(task)
                self._wake.set()
            return
        elif isinstance(frame, InterruptionFrame):
            self.arbiter.user_speech()
            for task in self.arbiter.tasks.values():
                if task.status == "queued" and task.kind == "normal":
                    self.arbiter._cancel_unplayed(task)
            self._wake.set()
            return
        await self.push_frame(frame, direction)

    async def _run_pump(self) -> None:
        """Surface background transport failures through the existing pipeline error channel."""
        try:
            await self._pump()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._record("playback_pump_failed", error_type=type(error).__name__)
            await self.push_error(
                error_msg="Voice output failed", exception=error, force_treat_as_permanent=True
            )

    def revalidate(self) -> None:
        """Wake queued-source validation after an ASR revision without touching played facts."""
        self._wake.set()

    async def _pump(self) -> None:
        """Send asynchronously, retaining the serial slot until matching client evidence."""
        while not self._closed:
            await self._wake.wait()
            if self._closed:
                return
            self._wake.clear()
            for identity, buffer in list(self._buffers.items()):
                task = self.arbiter.tasks[identity]
                if task.status == "queued" and not buffer.valid():
                    self.arbiter._cancel_unplayed(task)
                if task.status == "cancelled_unplayed":
                    self._drop_buffer(identity)
                elif self.arbiter._active is task and task.kind == "normal" and not buffer.valid():
                    self.arbiter._request_stop(task)
            while self._stop_cursor < len(self.arbiter.stop_requests):
                identity = self.arbiter.stop_requests[self._stop_cursor]
                self._stop_cursor += 1
                self._stop_guards[identity] = asyncio.create_task(
                    self._guard_stop_confirmation(identity)
                )
                await self.push_frame(
                    OutputTransportMessageUrgentFrame(
                        message={
                            "label": "voice-agent-playback",
                            "event": "stop_task",
                            "playback_id": identity,
                            "request_id": uuid.uuid4().hex,
                        }
                    )
                )
                await self.push_frame(InterruptionFrame())
            active = self.arbiter._active or self.arbiter.dispatch()
            if active is None or active.status == "stop_requested":
                continue
            active_buffer = self._buffers.get(active.playback_id)
            if active_buffer is None:
                continue
            if not active_buffer.started_sending:
                active_buffer.started_sending = True
                await self.push_frame(TTSStartedFrame(context_id=active.playback_id))
            while (
                active_buffer.frames
                and self.arbiter._active is active
                and active.status != "stop_requested"
            ):
                frame = active_buffer.frames.popleft()
                self._bytes -= len(frame.audio)
                self._sent_bytes[active.playback_id] = self._sent_bytes.get(
                    active.playback_id, 0
                ) + len(frame.audio)
                await self.push_frame(frame)
            if (
                active_buffer.ended
                and not active_buffer.frames
                and not active_buffer.end_sent
                and active.status != "stop_requested"
            ):
                active_buffer.end_sent = True
                await self.push_frame(TTSStoppedFrame(context_id=active.playback_id))
                await self.push_frame(
                    OutputTransportMessageFrame(
                        message={
                            "label": "voice-agent-playback",
                            "event": "task_end",
                            "playback_id": active.playback_id,
                        }
                    )
                )
