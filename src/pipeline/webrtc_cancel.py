"""Clear unsent PCM on interruption while preserving the existing WebRTC RTP track."""

from __future__ import annotations

import asyncio
from collections import deque

from pipecat.frames.frames import Frame, InterruptionFrame
from pipecat.processors.frame_processor import FrameDirection
from pipecat.transports.smallwebrtc.transport import (
    RawAudioTrack,
    SmallWebRTCOutputTransport,
    SmallWebRTCTransport,
)


def clear_pending_rtp_audio(track: RawAudioTrack | None) -> int:
    """Purge the locked SDK's extra queue after its output writer is cancelled.

    Args:
        track: Existing RTP source, or None before connection readiness.

    Returns:
        Number of unsent 10ms chunks removed; never a client playback receipt.

    Raises:
        RuntimeError: If the pinned SDK queue contract has changed.
    """
    if track is None:
        return 0
    queue = getattr(track, "_chunk_queue", None)
    if not isinstance(track, RawAudioTrack) or not isinstance(queue, deque):
        raise RuntimeError("Unsupported WebRTC audio queue contract")
    if any(
        not isinstance(entry, tuple)
        or len(entry) != 2
        or not isinstance(entry[0], bytes)
        or (entry[1] is not None and not isinstance(entry[1], asyncio.Future))
        for entry in queue
    ):
        raise RuntimeError("Unsupported WebRTC audio queue entries")
    removed = len(queue)
    # No await: the SDK recv coroutine cannot interleave with this queue drain.
    while queue:
        _, waiter = queue.popleft()
        if waiter is not None and not waiter.done():
            waiter.set_result(False)
    return removed


class CancellableRTPOutput(SmallWebRTCOutputTransport):
    """Extend SDK interruption cleanup to its track's unsent PCM queue."""

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        """Run native writer cancellation before purging its remaining track data.

        Args:
            frame: Native SDK frame; no audio format or route changes.
            direction: Existing pipeline direction.
        """
        await super().process_frame(frame, direction)
        if isinstance(frame, InterruptionFrame):
            clear_pending_rtp_audio(self._client._audio_output_track)


class CancellableRTPTransport(SmallWebRTCTransport):
    """Keep the existing connection/input and replace only output queue cleanup."""

    _output: CancellableRTPOutput | None

    def output(self) -> CancellableRTPOutput:
        """Return the native RTP output with the extra cancellation cleanup."""
        if self._output is None:
            self._output = CancellableRTPOutput(self._client, self._params, name=self._input_name)
        return self._output
