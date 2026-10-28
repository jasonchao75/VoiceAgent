"""Server-serialized RTP output without task renderer acknowledgements."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    OutputAudioRawFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
)

from src.pipeline.serial_output import SerialAudioOutput


class NativeSerialAudioOutput(SerialAudioOutput):
    """Await native track consumption while retaining unknown client playback facts."""

    def __init__(
        self,
        *,
        write: Callable[[OutputAudioRawFrame], Awaitable[bool]],
        cancel_audio: Callable[[], Awaitable[None]],
        **kwargs: Any,
    ) -> None:
        """Bind the existing native transport; never send a second audio copy."""
        super().__init__(**kwargs)
        self._native_write = write
        self._native_cancel = cancel_audio

    def _release(self, identity: str, *, stopped: bool) -> None:
        """Release server sequencing without inventing a renderer terminal event."""
        task = self.arbiter.tasks[identity]
        task.status = "send_cancelled" if stopped else "send_completed"
        self.arbiter._record(task, "playback_server_" + task.status)
        self.arbiter._active = None
        self._drop_buffer(identity)
        self._wake.set()

    async def _write_block(
        self,
        frame: OutputAudioRawFrame,
        valid: Callable[[], bool],
        identity: str,
    ) -> bool:
        """Cancel a blocked track write on invalidation rather than waiting five seconds."""
        writer = asyncio.ensure_future(self._native_write(frame))
        wake: asyncio.Task[bool] | None = None
        deadline = asyncio.get_running_loop().time() + 5.0
        try:
            while not writer.done():
                active = self.arbiter._active
                if (
                    self._closed
                    or not valid()
                    or active is None
                    or active.status == "stop_requested"
                ):
                    return False
                wake = asyncio.create_task(self._wake.wait())
                done, _ = await asyncio.wait(
                    {writer, wake},
                    timeout=max(0, deadline - asyncio.get_running_loop().time()),
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if not done:
                    raise TimeoutError("Native RTP write stalled")
                if wake in done:
                    self._wake.clear()
                wake.cancel()
                await asyncio.gather(wake, return_exceptions=True)
                wake = None
            if not writer.result():
                raise RuntimeError("Native RTP audio unavailable")
            return True
        finally:
            if wake:
                wake.cancel()
            if not writer.done():
                writer.cancel()
            await asyncio.gather(writer, *([wake] if wake else []), return_exceptions=True)

    async def _pump(self) -> None:
        """Keep at most 20ms in native track; interruptions are checked every write."""
        while not self._closed:
            await self._wake.wait()
            self._wake.clear()
            for identity, queued_buffer in list(self._buffers.items()):
                task = self.arbiter.tasks[identity]
                if not queued_buffer.valid():
                    if task.status == "queued":
                        self.arbiter._cancel_unplayed(task)
                    elif self.arbiter._active is task:
                        self.arbiter._request_stop(task)
                if task.status == "cancelled_unplayed":
                    self._drop_buffer(identity)
            active = self.arbiter._active or self.arbiter.dispatch()
            if active is None:
                continue
            identity = active.playback_id
            buffer = self._buffers.get(identity)
            if buffer is None:
                continue
            if active.status == "stop_requested":
                await self._native_cancel()
                await self.broadcast_frame(BotStoppedSpeakingFrame)
                self._release(identity, stopped=True)
                continue
            if buffer.frames:
                if not buffer.started_sending:
                    buffer.started_sending = True
                    await self.push_frame(TTSStartedFrame(context_id=identity))
                    await self.broadcast_frame(BotStartedSpeakingFrame)
                frame = buffer.frames.popleft()
                self._bytes -= len(frame.audio)
                block = frame.sample_rate // 50 * 2
                if frame.num_channels != 1 or len(frame.audio) % 2:
                    raise ValueError("Native output requires mono PCM16")
                for offset in range(0, len(frame.audio), block):
                    if self._closed or active.status == "stop_requested" or not buffer.valid():
                        self.arbiter._request_stop(active)
                        break
                    pcm = frame.audio[offset : offset + block]
                    quantum = frame.sample_rate // 100 * 2
                    pcm += b"\0" * ((-len(pcm)) % quantum)
                    # The pinned SDK future resolves when RawAudioTrack consumes the PCM.
                    self._sent_bytes[identity] = self._sent_bytes.get(identity, 0) + len(pcm)
                    ok = await self._write_block(
                        OutputAudioRawFrame(pcm, frame.sample_rate, 1),
                        buffer.valid,
                        identity,
                    )
                    if not ok:
                        self.arbiter._request_stop(active)
                        break
                self._wake.set()
            elif buffer.ended:
                await self.push_frame(TTSStoppedFrame(context_id=identity))
                if buffer.started_sending:
                    await self.broadcast_frame(BotStoppedSpeakingFrame)
                self._release(identity, stopped=False)
