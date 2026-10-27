"""Bounded native RTP-to-PCM evidence for the development-only RTC candidate.

These coordinates are server decoder provenance, not microphone timestamps.
The original codec, resampler, track and PCM are never replaced with new audio.
"""

from __future__ import annotations

import hashlib
import uuid
from collections import OrderedDict, deque
from contextvars import ContextVar
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

import numpy as np
from av import AudioFrame

_active_ssrc: ContextVar[int | None] = ContextVar("td_ingress_ssrc", default=None)


@dataclass(frozen=True, slots=True)
class _Packet:
    pts: int
    rtp_timestamp: int
    ssrc: int
    digest: str


class RTPInputLedger:
    """Retain exact native packet and decoded extents with an explicit connection identity."""

    def __init__(self, *, limit: int = 256) -> None:
        """Initialize bounded evidence; reject an invalid retention budget."""
        if type(limit) is not int or limit < 1:
            raise ValueError("Invalid ingress evidence budget")
        self.connection_id = uuid.uuid4().hex
        self.limit = limit
        self._encoded: OrderedDict[int, _Packet] = OrderedDict()
        self._decoded: OrderedDict[int, tuple[int, _Packet]] = OrderedDict()
        self._conflicts: deque[int] = deque(maxlen=limit)
        self._ssrc: int | None = None
        self.unavailable_reason: str | None = None

    @property
    def retained_counts(self) -> tuple[int, int]:
        """Return bounded record counts without exposing audio payloads."""
        return len(self._encoded), len(self._decoded)

    def observe_ssrc(self, ssrc: int) -> None:
        """Reject mixed jitter origins from the first received packet, before prefetch emits."""
        if type(ssrc) is not int or not 0 <= ssrc < 2**32:
            return
        if self._ssrc is not None and self._ssrc != ssrc:
            self.unavailable_reason = "ssrc_changed"
            self._encoded.clear()
            self._decoded.clear()
        self._ssrc = ssrc

    def record_encoded(self, *, pts: int, rtp_timestamp: int, ssrc: int, payload: bytes) -> None:
        """Bind the actual jitter-buffer payload to its native mapped decoder PTS."""
        if (
            type(pts) is not int
            or pts < 0
            or type(rtp_timestamp) is not int
            or not 0 <= rtp_timestamp < 2**32
            or type(ssrc) is not int
            or not 0 <= ssrc < 2**32
            or not payload
        ):
            return
        self.observe_ssrc(ssrc)
        if self.unavailable_reason is not None:
            return
        packet = _Packet(pts, rtp_timestamp, ssrc, hashlib.sha256(payload).hexdigest())
        if pts in self._conflicts:
            return
        previous = self._encoded.get(pts)
        if previous is not None and previous != packet:
            self._encoded.pop(pts, None)
            self._decoded.pop(pts, None)
            self._conflicts.append(pts)
            return
        self._encoded[pts] = packet
        while len(self._encoded) > self.limit:
            self._encoded.popitem(last=False)

    def record_decoded(self, frame: Any) -> None:
        """Accept only actual Opus-clock decoded frames with a matching encoded origin."""
        if (
            self.unavailable_reason is not None
            or not isinstance(frame, AudioFrame)
            or frame.sample_rate != 48000
            or frame.time_base != Fraction(1, 48000)
            or type(frame.pts) is not int
            or frame.samples <= 0
        ):
            return
        packet = self._encoded.get(frame.pts)
        if packet is None or frame.pts in self._conflicts:
            return
        record = (frame.pts + frame.samples, packet)
        previous = self._decoded.get(frame.pts)
        if previous is not None and previous != record:
            self._decoded.pop(frame.pts, None)
            self._conflicts.append(frame.pts)
            return
        self._decoded[frame.pts] = record
        while len(self._decoded) > self.limit:
            self._decoded.popitem(last=False)

    def cover(self, start: int, end: int) -> list[dict[str, Any]] | None:
        """Prove an entire processed media interval, rejecting gaps or overlapping origins.

        Args:
            start: Exact processed start on the native 48kHz media clock.
            end: Exclusive processed end on the same clock.

        Returns:
            Packet extents and payload hashes, or None for any unproven sample.
        """
        if (
            self.unavailable_reason is not None
            or type(start) is not int
            or type(end) is not int
            or start < 0
            or end <= start
        ):
            return None
        cursor = start
        result = []
        for pts, (tail, packet) in sorted(self._decoded.items()):
            if tail <= start or pts >= end:
                continue
            first, last = max(start, pts), min(end, tail)
            if first != cursor or pts in self._conflicts:
                return None
            result.append(
                {
                    "connection_id": self.connection_id,
                    "ssrc": packet.ssrc,
                    "rtp_timestamp": packet.rtp_timestamp,
                    "payload_sha256": packet.digest,
                    "decoded_start": pts,
                    "decoded_end": tail,
                    "segment_start": first,
                    "segment_end": last,
                }
            )
            cursor = last
        return result if cursor == end and len(result) <= 64 else None


def bind_receiver_coordinates(receiver: Any, ledger: RTPInputLedger) -> Any:
    """Observe the pinned receiver's synchronous timestamp-map/decoder-queue boundary.

    Returns:
        A callback restoring only this receiver instance's original methods/queue.
    """
    mapper = receiver._RTCRtpReceiver__timestamp_mapper
    original_map = mapper.map
    original_handler = receiver._handle_rtp_packet
    original_queue = receiver._RTCRtpReceiver__decoder_queue
    pending: tuple[int, int, int | None] | None = None

    def mapped(timestamp: int) -> int:
        """Keep the original mapper result and its actual packet-handler SSRC context."""
        nonlocal pending
        value = original_map(timestamp)
        pending = (timestamp, value, _active_ssrc.get())
        return value

    class DecoderQueue:
        """Forward unchanged queue items to the already-running native decoder thread."""

        def put(self, item: Any, *args: Any, **kwargs: Any) -> Any:
            """Record before enqueue; teardown sentinels keep their native meaning."""
            nonlocal pending
            proof, pending = pending, None
            if item is not None and proof is not None:
                codec, frame = item
                timestamp, pts, ssrc = proof
                if (
                    codec.mimeType.lower() == "audio/opus"
                    and frame.timestamp == pts
                    and ssrc is not None
                ):
                    ledger.record_encoded(
                        pts=pts, rtp_timestamp=timestamp, ssrc=ssrc, payload=frame.data
                    )
            return original_queue.put(item, *args, **kwargs)

        def __getattr__(self, name: str) -> Any:
            """Preserve all other native queue operations."""
            return getattr(original_queue, name)

    async def receive(packet: Any, *args: Any, **kwargs: Any) -> Any:
        """Retain per-handler ownership even when the native receiver awaits NACK/PLI."""
        ledger.observe_ssrc(packet.ssrc)
        token = _active_ssrc.set(packet.ssrc)
        try:
            return await original_handler(packet, *args, **kwargs)
        finally:
            _active_ssrc.reset(token)

    queue = DecoderQueue()
    mapper.map = mapped
    receiver._handle_rtp_packet = receive
    receiver._RTCRtpReceiver__decoder_queue = queue

    def restore() -> None:
        """Restore only hooks still owned by this observer."""
        if mapper.map is mapped:
            mapper.map = original_map
        if receiver._handle_rtp_packet is receive:
            receiver._handle_rtp_packet = original_handler
        if receiver._RTCRtpReceiver__decoder_queue is queue:
            receiver._RTCRtpReceiver__decoder_queue = original_queue

    return restore


async def observe_native_reader(
    client: Any, ledger: RTPInputLedger, *, native_reader: Any = None
) -> Any:
    """Add exact processed-PCM evidence while yielding the untouched locked SDK frames."""
    original_resampler = client._audio_in_resampler
    recorded: deque[tuple[str, dict[str, Any] | None]] = deque(maxlen=64)

    class Resampler:
        """Observe actual processed AV timestamps, including previous packet carry-over."""

        def resample(self, frame: Any) -> Any:
            """Return original resampler outputs and retain only bounded hash/extent proof."""
            # The SDK may install or replace its track after this reader starts.
            # Observe the actual decoded input here instead of pinning an early track object.
            ledger.record_decoded(frame)
            frames = original_resampler.resample(frame)
            for processed in frames:
                proof = None
                if (
                    processed.pts is not None
                    and processed.time_base is not None
                    and processed.sample_rate == 16000
                    and processed.layout.name == "mono"
                ):
                    position = processed.pts * processed.time_base * 48000
                    duration = Fraction(processed.samples * 48000, processed.sample_rate)
                    if position.denominator == duration.denominator == 1:
                        start, end = int(position), int(position + duration)
                        packets = ledger.cover(start, end)
                        if packets is not None:
                            proof = {
                                "processed_start": start,
                                "processed_end": end,
                                "source_rate": 48000,
                                "sample_rate": 16000,
                                "samples": processed.samples,
                                "packets": packets,
                            }
                pcm = processed.to_ndarray().astype(np.int16).tobytes()
                recorded.append((hashlib.sha256(pcm).hexdigest(), proof))
            return frames

    resampler = Resampler()
    client._audio_in_resampler = resampler
    try:
        async for frame in (native_reader or client.read_audio_frame)():
            evidence = recorded.popleft() if recorded else None
            if evidence is not None and evidence[0] == hashlib.sha256(frame.audio).hexdigest():
                if evidence[1] is not None:
                    frame.metadata["td_rtp_input"] = evidence[1]
                else:
                    frame.metadata["td_rtp_input_unavailable"] = "encoded_source_unavailable"
            else:
                frame.metadata["td_rtp_input_unavailable"] = "processed_pcm_unproven"
            yield frame
    finally:
        if client._audio_in_resampler is resampler:
            client._audio_in_resampler = original_resampler


def install_candidate_input(transport: Any, connection: Any) -> RTPInputLedger:
    """Observe only a development candidate's receiver and original native input reader.

    Args:
        transport: The existing SmallWebRTC transport before its input reader starts.
        connection: Its owning negotiated peer connection.

    Returns:
        A bounded coordinate ledger; unsupported receiver shapes leave evidence missing.
    """
    ledger = RTPInputLedger()
    transport.td_rtp_input_ledger = ledger
    audio = [
        item.receiver
        for item in connection._pc.getTransceivers()
        if item.kind == "audio" and getattr(item, "receiver", None) is not None
    ]
    if len(audio) != 1:
        return ledger
    receiver = audio[0]
    if not all(
        hasattr(receiver, name)
        for name in (
            "_RTCRtpReceiver__timestamp_mapper",
            "_RTCRtpReceiver__decoder_queue",
            "_handle_rtp_packet",
        )
    ):
        return ledger
    restore_receiver = bind_receiver_coordinates(receiver, ledger)
    client = transport._client
    original = client.read_audio_frame

    async def read() -> Any:
        """Preserve native setup/teardown and restore the per-connection observation hooks."""
        try:
            async for frame in observe_native_reader(client, ledger, native_reader=original):
                yield frame
        finally:
            restore_receiver()
            if client.read_audio_frame is read:
                client.read_audio_frame = original

    client.read_audio_frame = read
    connection.send_app_message(
        {
            "label": "voice-agent-playback",
            "event": "input_source_epoch",
            "connection_id": ledger.connection_id,
        }
    )
    return ledger
