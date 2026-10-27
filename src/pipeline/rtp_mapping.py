"""D-064 isolated RTP candidate: immutable sample/codec/wire provenance.

This adapter is deliberately not selected by the production transport. It uses
the pinned native queue and codec, recording ownership only at actual dequeue.
"""

from __future__ import annotations

import hashlib
from collections import deque
from contextvars import ContextVar
from typing import Any

from aiortc.codecs.opus import OpusEncoder
from aiortc.rtp import RtpPacket
from pipecat.transports.smallwebrtc.transport import RawAudioTrack


class RTPTaskLedger:
    """Join exact codec payloads to source samples on the Opus 48kHz clock."""

    def __init__(self) -> None:
        """Initialize bounded candidate records and an unknown RTP origin."""
        self.sources: list[dict[str, Any]] = []
        self._encoded: deque[tuple[str, int, int]] = deque()
        self._origin: int | None = None
        self._ssrc: int | None = None
        self._source_end: int | None = None

    def record_source(self, pts: int, samples: int, rate: int, task: str | None) -> None:
        """Record samples returned by the native track, including explicit silence.

        Raises:
            ValueError: If this finite candidate cannot prove exact coordinates.
        """
        if rate not in {16000, 24000, 48000} or pts < 0 or samples <= 0:
            raise ValueError("Unsupported candidate source coordinates")
        if task is not None and (not isinstance(task, str) or not task or len(task) > 128):
            raise ValueError("Invalid candidate task identity")
        scale = 48000 // rate
        start, end = pts * scale, (pts + samples) * scale
        if len(self.sources) >= 10000 or (
            self._source_end is not None and start != self._source_end
        ):
            raise ValueError("Source clock gap or candidate record limit")
        self.sources.append({"start": start, "end": end, "task": task})
        self._source_end = end

    def record_encoded(self, payload: bytes, pts: int, duration: int) -> None:
        """Retain the real codec PTS before aiortc removes its negative origin.

        Raises:
            ValueError: If codec evidence is invalid or its queue is unbounded.
        """
        if not payload or duration <= 0 or len(self._encoded) >= 100:
            raise ValueError("Invalid or excessive encoded evidence")
        self._encoded.append((hashlib.sha256(payload).hexdigest(), pts, duration))

    def bind_rtp(self, packet: RtpPacket) -> dict[str, Any]:
        """Bind an actual serialized RTP packet; never accept guessed task labels.

        Returns:
            A control-only record with sample spans and payload digest, no audio.

        Raises:
            ValueError: If payload, SSRC, clock or source coverage is unproven.
        """
        if not self._encoded:
            raise ValueError("RTP payload has no codec evidence")
        digest, pts, duration = self._encoded[0]
        if hashlib.sha256(packet.payload).hexdigest() != digest:
            raise ValueError("RTP payload differs from codec evidence")
        origin = (packet.timestamp - pts) % 2**32
        if self._origin is not None and (origin != self._origin or packet.ssrc != self._ssrc):
            raise ValueError("RTP timestamp or SSRC differs from codec coordinates")
        spans = []
        cursor = max(0, pts)
        for source in self.sources:
            start, end = max(cursor, source["start"]), min(pts + duration, source["end"])
            if end > start:
                if start != cursor:
                    raise ValueError("Unproven source sample gap")
                spans.append({"start": start, "end": end, "task": source["task"]})
                cursor = end
        if cursor != pts + duration:
            raise ValueError("Unproven source sample tail")
        self._origin, self._ssrc = origin, packet.ssrc
        self._encoded.popleft()
        # Future packets retain their overlapping tail; consumed source cannot grow forever.
        self.sources = [source for source in self.sources if source["end"] > pts + duration]
        return {
            "version": 1,
            "rtp_timestamp": packet.timestamp,
            "ssrc": packet.ssrc,
            "payload_sha256": digest,
            "source_start": pts,
            "samples": duration,
            "priming_samples": max(0, -pts),
            "spans": spans,
        }


class _TaskQueue(deque):
    """Keep an immutable identity beside each native entry, including cancelled data."""

    def __init__(self, owner: MappedRawAudioTrack) -> None:
        """Bind one queue to its owning native track."""
        super().__init__()
        self.owner = owner
        self.identities: deque[str | None] = deque()

    def append(self, entry: Any) -> None:
        """Capture the binding synchronously when the SDK creates each chunk."""
        super().append(entry)
        self.identities.append(self.owner._adding_task)

    def popleft(self) -> Any:
        """Cancelled pops retire identities but never count as source playback."""
        entry = super().popleft()
        identity = self.identities.popleft()
        received = self.owner._receiving.get()
        if received is not None:
            received.append(identity)
        return entry


class MappedRawAudioTrack(RawAudioTrack):
    """Keep native PCM, pacing and silence while observing actual dequeue ownership."""

    def __init__(self, sample_rate: int, ledger: RTPTaskLedger) -> None:
        """Bind this isolated track to one connection-local source ledger."""
        super().__init__(sample_rate)
        self.ledger = ledger
        self._adding_task: str | None = None
        self._receiving: ContextVar[list[str | None] | None] = ContextVar(
            "rtp_native_receive", default=None
        )
        self._chunk_queue = _TaskQueue(self)

    def add_task_audio(self, audio: bytes, task: str) -> Any:
        """Enqueue task PCM through the unchanged SDK method and native waiter."""
        self._adding_task = task
        try:
            return super().add_audio_bytes(audio)
        finally:
            self._adding_task = None

    async def recv(self) -> Any:
        """Record native returned frames; queue cancellation in other tasks is excluded."""
        received: list[str | None] = []
        token = self._receiving.set(received)
        try:
            frame = await super().recv()
        finally:
            self._receiving.reset(token)
        if len(received) > 1:
            raise ValueError("Native track dequeue contract changed")
        self.ledger.record_source(
            frame.pts, frame.samples, frame.sample_rate, received[0] if received else None
        )
        return frame


class MappedOpusEncoder(OpusEncoder):
    """Observe actual pinned codec output before the native sender rebases PTS."""

    first_packet_pts: int | None

    def __init__(self, ledger: RTPTaskLedger) -> None:
        """Retain the native codec and resampler settings without extra dependencies."""
        super().__init__()
        self.ledger = ledger

    def encode(self, frame: Any, force_keyframe: bool = False) -> Any:
        """Mirror the pinned encoder's resampling and record its real packets."""
        packets = []
        for output in self.resampler.resample(frame):
            packets.extend(self.codec.encode(output))
        if self.first_packet_pts is None and packets:
            self.first_packet_pts = packets[0].pts
        for packet in packets:
            if packet.pts is None or packet.duration is None:
                raise ValueError("Native codec omitted packet coordinates")
            self.ledger.record_encoded(bytes(packet), packet.pts, packet.duration)
        if packets:
            pts, origin = packets[0].pts, self.first_packet_pts
            if pts is None or origin is None:
                raise ValueError("Native codec omitted origin")
            return [bytes(packet) for packet in packets], pts - origin
        return [], None
