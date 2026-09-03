"""Bounded background FLAC recording for user input audio."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import soundfile as sf  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


class AudioRecorder:
    """Write PCM chunks to FLAC outside the real-time frame callback."""

    def __init__(self, path: Path, *, sample_rate: int, max_chunks: int = 256) -> None:
        """Initialize a recorder without opening its output file."""
        self.path = path
        self.sample_rate = sample_rate
        self.status = "pending"
        self.error: str | None = None
        self._queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=max_chunks)
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Create the destination directory and start the writer task."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.status = "recording"
        self._task = asyncio.create_task(self._run(), name=f"recording-{self.path.stem}")

    def push(self, audio: bytes) -> None:
        """Queue one PCM chunk or fail the recording safely on overflow."""
        if self.status != "recording":
            return
        try:
            self._queue.put_nowait(audio)
        except asyncio.QueueFull:
            self.status = "failed"
            self.error = "recording_queue_overflow"
            if self._task is not None:
                self._task.cancel()

    async def stop(self) -> None:
        """Flush queued audio and close the file."""
        if self._task is None:
            return
        if self.status == "failed":
            self._task.cancel()
        else:
            await self._queue.put(None)
        try:
            await self._task
        except asyncio.CancelledError:
            await asyncio.to_thread(self.path.unlink, missing_ok=True)
        self._task = None

    async def _run(self) -> None:
        try:
            with sf.SoundFile(
                self.path,
                mode="w",
                samplerate=self.sample_rate,
                channels=1,
                subtype="PCM_16",
                format="FLAC",
            ) as output:
                while True:
                    chunk = await self._queue.get()
                    if chunk is None:
                        break
                    await asyncio.to_thread(output.buffer_write, chunk, dtype="int16")
            if self.status == "recording":
                self.status = "available"
        except Exception:
            logger.exception("recording_failed recording_id=%s", self.path.stem)
            self.status = "failed"
            self.error = "recording_write_failed"
