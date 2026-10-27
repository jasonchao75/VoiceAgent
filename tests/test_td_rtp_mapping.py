"""D-064 mapping owns actual dequeued samples, never arrival-time guesses."""

import pytest
from aiortc.rtp import RtpPacket

from src.pipeline.rtp_mapping import MappedRawAudioTrack, RTPTaskLedger


@pytest.mark.asyncio
async def test_native_dequeue_retains_task_across_silence_and_queue_cancel():
    """Unsent cancelled chunks cannot move a later task onto the wrong clock."""
    ledger = RTPTaskLedger()
    track = MappedRawAudioTrack(24000, ledger)
    await track.recv()
    first = track.add_task_audio(bytes(960), "partial-A")
    await track.recv()
    # Remove only unsent native data, as the production cancellation hook does.
    _, waiter = track._chunk_queue.popleft()
    waiter.set_result(False)
    second = track.add_task_audio(bytes(480), "final-B")
    await track.recv()
    assert first.result() is False
    assert second.result() is True
    assert ledger.sources == [
        {"start": 0, "end": 480, "task": None},
        {"start": 480, "end": 960, "task": "partial-A"},
        {"start": 960, "end": 1440, "task": "final-B"},
    ]
    track.stop()


def test_packet_uses_actual_codec_origin_and_keeps_mixed_task_spans():
    """A packet crossing A/B is not assigned to whichever input triggered encode."""
    ledger = RTPTaskLedger()
    ledger.record_source(0, 720, 24000, "A")
    ledger.record_source(720, 720, 24000, "B")
    ledger.record_encoded(b"opus-A", 648, 960)
    packet = RtpPacket(payload_type=111, sequence_number=9, timestamp=4294967200)
    packet.ssrc = 33
    packet.payload = b"opus-A"
    mapping = ledger.bind_rtp(packet)
    assert mapping["source_start"] == 648
    assert mapping["spans"] == [
        {"start": 648, "end": 1440, "task": "A"},
        {"start": 1440, "end": 1608, "task": "B"},
    ]
    ledger.record_encoded(b"opus-B", 1608, 960)
    packet.timestamp = (4294967200 + 960) % 2**32
    packet.payload = b"opus-B"
    assert ledger.bind_rtp(packet)["source_start"] == 1608


def test_payload_or_timestamp_mismatch_never_produces_mapping():
    """Identity must match exact codec output and the same RTP coordinate origin."""
    ledger = RTPTaskLedger()
    ledger.record_source(0, 4800, 48000, "A")
    ledger.record_encoded(b"expected", 0, 960)
    packet = RtpPacket(payload_type=111, sequence_number=1, timestamp=100)
    packet.payload = b"foreign"
    with pytest.raises(ValueError, match="payload"):
        ledger.bind_rtp(packet)
    packet.payload = b"expected"
    ledger.bind_rtp(packet)
    ledger.record_encoded(b"second", 960, 960)
    packet.payload = b"second"
    packet.timestamp = 1061
    with pytest.raises(ValueError, match="timestamp"):
        ledger.bind_rtp(packet)


def test_consumed_source_evidence_does_not_exhaust_a_long_session():
    """Already-bound packet source records are retired without losing the next span."""
    ledger = RTPTaskLedger()
    for index in range(10010):
        start = index * 960
        ledger.record_source(start, 960, 48000, "A")
        payload = str(index).encode()
        ledger.record_encoded(payload, start, 960)
        packet = RtpPacket(
            payload_type=111, sequence_number=index % 65536, timestamp=(100 + start) % 2**32
        )
        packet.ssrc = 33
        packet.payload = payload
        assert ledger.bind_rtp(packet)["spans"] == [
            {"start": start, "end": start + 960, "task": "A"}
        ]
        assert len(ledger.sources) <= 1

    with pytest.raises(ValueError, match="Source clock gap"):
        ledger.record_source(10010 * 960 + 1, 960, 48000, "A")
