"""RTP ingress evidence must preserve native PCM and prove resampler packet boundaries."""

from fractions import Fraction
from types import SimpleNamespace

import av
import pytest
from pipecat.transports.smallwebrtc.transport import SmallWebRTCClient


def audio_frame(pts):
    """Create deterministic decoded stereo samples on the actual Opus clock."""
    frame = av.AudioFrame(format="s16", layout="stereo", samples=960)
    frame.sample_rate = 48000
    frame.time_base = Fraction(1, 48000)
    frame.pts = pts
    frame.planes[0].update(b"\x00\x10" * 1920)
    return frame


class Track:
    """Supply actual decoded AV frames without opening any transport."""

    def __init__(self):
        """Use three adjoining packets, enough to expose resampling carry-over."""
        self.frames = iter([audio_frame(pts) for pts in (0, 960, 1920)])

    async def recv(self):
        """Return the same native frame object the reader consumes."""
        return next(self.frames)


def native_client(frames=None):
    """Construct only the locked reader state; no connection or codec is replaced."""
    client = object.__new__(SmallWebRTCClient)
    client._audio_in_resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
    client._audio_in_layout = "mono"
    client._audio_in_channels = 1
    client._in_sample_rate = 16000
    client._audio_input_track = Track()
    if frames is not None:
        client._audio_input_track.frames = iter(frames)
    return client


@pytest.mark.asyncio
async def test_locked_reader_pcm_is_identical_and_processed_pts_keep_previous_packet_tail():
    """The second 16k chunk starts in packet zero, despite raw.pts naming packet one."""
    from src.pipeline.rtp_input import RTPInputLedger, observe_native_reader

    baseline = native_client().read_audio_frame()
    expected = [await anext(baseline) for _ in range(3)]
    await baseline.aclose()
    client = native_client()
    ledger = RTPInputLedger()
    for index in range(3):
        ledger.record_encoded(
            pts=index * 960,
            rtp_timestamp=10000 + index * 960,
            ssrc=7,
            payload=f"packet{index}".encode(),
        )
    reader = observe_native_reader(client, ledger)
    actual = [await anext(reader) for _ in range(3)]
    await reader.aclose()
    assert [(x.audio, x.sample_rate, x.num_channels, x.pts) for x in actual] == [
        (x.audio, x.sample_rate, x.num_channels, x.pts) for x in expected
    ]
    assert [len(x.audio) // 2 for x in actual] == [304, 320, 320]
    second = actual[1].metadata["td_rtp_input"]
    assert second["processed_start"] == 912
    assert second["processed_end"] == 1872
    assert [
        (p["rtp_timestamp"], p["segment_start"], p["segment_end"]) for p in second["packets"]
    ] == [(10000, 912, 960), (10960, 960, 1872)]
    assert second["samples"] == 320
    assert second["source_rate"] == 48000


@pytest.mark.asyncio
async def test_missing_packet_evidence_does_not_guess_an_origin_or_change_pcm():
    """Decoder/resampler positions alone cannot prove an RTP payload's source."""
    from src.pipeline.rtp_input import RTPInputLedger, observe_native_reader

    client = native_client()
    reader = observe_native_reader(client, RTPInputLedger())
    first = await anext(reader)
    await reader.aclose()
    assert len(first.audio) == 608
    assert "td_rtp_input" not in first.metadata
    assert first.metadata["td_rtp_input_unavailable"] == "encoded_source_unavailable"


def test_decoded_gaps_remain_gaps_and_records_are_bounded():
    """A missing packet must not be filled by interpolating neighbouring media clocks."""
    from src.pipeline.rtp_input import RTPInputLedger

    ledger = RTPInputLedger(limit=2)
    for pts in (0, 1920):
        ledger.record_encoded(pts=pts, rtp_timestamp=100 + pts, ssrc=7, payload=b"opus")
        ledger.record_decoded(audio_frame(pts))
    assert ledger.cover(912, 2000) is None
    for pts in (2880, 3840, 4800):
        ledger.record_encoded(pts=pts, rtp_timestamp=100 + pts, ssrc=7, payload=b"opus")
        ledger.record_decoded(audio_frame(pts))
    assert ledger.cover(0, 20) is None
    assert ledger.retained_counts == (2, 2)


@pytest.mark.asyncio
async def test_native_timestamp_mapper_wrap_is_bound_to_exact_codec_payload_before_dequeue():
    """Use the actual aiortc mapper and queue boundary without touching payloads."""
    import queue

    from aiortc.rtcrtpreceiver import TimestampMapper
    from aiortc.rtp import RtpPacket

    from src.pipeline.rtp_input import RTPInputLedger, bind_receiver_coordinates

    receiver = SimpleNamespace(
        _RTCRtpReceiver__timestamp_mapper=TimestampMapper(),
        _RTCRtpReceiver__decoder_queue=queue.Queue(),
    )
    codec = SimpleNamespace(mimeType="audio/opus")

    async def receive(packet, arrival_time_ms):
        """Mirror the pinned synchronous map/put boundary with real aiortc types."""
        mapped = receiver._RTCRtpReceiver__timestamp_mapper.map(packet.timestamp)
        receiver._RTCRtpReceiver__decoder_queue.put(
            (codec, SimpleNamespace(timestamp=mapped, data=packet.payload))
        )

    receiver._handle_rtp_packet = receive
    ledger = RTPInputLedger()
    restore = bind_receiver_coordinates(receiver, ledger)
    try:
        for timestamp in (2**32 - 480, 480):
            packet = RtpPacket(
                payload_type=111, timestamp=timestamp, ssrc=7, payload=b"unchanged opus"
            )
            await receiver._handle_rtp_packet(packet, 100)
            queued = receiver._RTCRtpReceiver__decoder_queue.get_nowait()
            assert queued[1].data is packet.payload
        ledger.record_decoded(audio_frame(960))
        proof = ledger.cover(960, 1000)
        assert proof[0]["rtp_timestamp"] == 480
        assert proof[0]["ssrc"] == 7
        import hashlib

        assert proof[0]["payload_sha256"] == hashlib.sha256(b"unchanged opus").hexdigest()
    finally:
        restore()
    assert receiver._handle_rtp_packet is receive


def test_only_the_authorized_development_candidate_installs_ingress_observation(monkeypatch):
    """Ordinary/native callers must keep the original transport and input path."""
    from unittest.mock import Mock

    from src.pipeline import rtp_input, rtp_output, webrtc_cancel
    from src.pipeline.voice_agent import create_small_webrtc_transport

    runtime = SimpleNamespace(
        audio=SimpleNamespace(input_sample_rate=16000, output_sample_rate=24000, channels=1)
    )
    transport = SimpleNamespace()
    monkeypatch.setattr(webrtc_cancel, "CancellableRTPTransport", lambda **kwargs: transport)
    output = Mock()
    ingress = Mock()
    monkeypatch.setattr(rtp_output, "install_candidate_transport", output)
    monkeypatch.setattr(rtp_input, "install_candidate_input", ingress)
    connection = object()
    assert (
        create_small_webrtc_transport(connection=connection, runtime=runtime, custom_td=True)
        is transport
    )
    ingress.assert_not_called()
    assert (
        create_small_webrtc_transport(
            connection=connection, runtime=runtime, custom_td=True, candidate_playback=True
        )
        is transport
    )
    ingress.assert_called_once_with(transport, connection)


@pytest.mark.asyncio
async def test_observer_preserves_the_native_null_frame_tolerance():
    """Missing native frames remain a temporary gap, not an observer exception."""
    from src.pipeline.rtp_input import RTPInputLedger, observe_native_reader

    reader = observe_native_reader(native_client([None, audio_frame(0)]), RTPInputLedger())
    frame = await anext(reader)
    await reader.aclose()
    assert len(frame.audio) == 608
    assert "td_rtp_input" not in frame.metadata


@pytest.mark.asyncio
async def test_actual_opus_decoder_and_resampler_prove_ingress_without_changing_native_pcm():
    """Follow real locked codec PTS and payloads, rather than assuming decoder placement."""
    import hashlib

    from aiortc.codecs.opus import OpusDecoder, OpusEncoder
    from aiortc.jitterbuffer import JitterFrame
    from aiortc.rtcrtpreceiver import TimestampMapper

    from src.pipeline.rtp_input import RTPInputLedger, observe_native_reader

    encoder = OpusEncoder()
    packets = []
    for index in range(4):
        payloads, pts = encoder.encode(audio_frame(index * 960))
        packets.extend((payload, (pts + 123456) % 2**32) for payload in payloads)
    assert len(packets) >= 3

    def decode(ledger=None):
        """Use independent decoder state for baseline and observed byte comparisons."""
        decoder, mapper = OpusDecoder(), TimestampMapper()
        frames = []
        for payload, timestamp in packets:
            mapped = mapper.map(timestamp)
            if ledger is not None:
                ledger.record_encoded(pts=mapped, rtp_timestamp=timestamp, ssrc=7, payload=payload)
            frames.extend(decoder.decode(JitterFrame(data=payload, timestamp=mapped)))
        return frames

    baseline = native_client(decode()).read_audio_frame()
    expected = [await anext(baseline) for _ in range(3)]
    await baseline.aclose()
    ledger = RTPInputLedger()
    reader = observe_native_reader(native_client(decode(ledger)), ledger)
    actual = [await anext(reader) for _ in range(3)]
    await reader.aclose()
    assert [frame.audio for frame in actual] == [frame.audio for frame in expected]
    second = actual[1].metadata["td_rtp_input"]
    assert len(second["packets"]) == 2
    assert [p["payload_sha256"] for p in second["packets"]] == [
        hashlib.sha256(payload).hexdigest() for payload, _ in packets[:2]
    ]


def test_ssrc_change_rejects_the_entire_ambiguous_jitter_origin_without_changing_audio():
    """The packet that releases jitter output is not necessarily its original SSRC."""
    from src.pipeline.rtp_input import RTPInputLedger

    ledger = RTPInputLedger()
    ledger.observe_ssrc(7)
    ledger.observe_ssrc(8)
    ledger.record_encoded(pts=0, rtp_timestamp=1, ssrc=8, payload=b"old queued packet")
    ledger.record_decoded(audio_frame(0))
    assert ledger.cover(0, 10) is None
    assert ledger.unavailable_reason == "ssrc_changed"


@pytest.mark.asyncio
async def test_late_native_track_assignment_keeps_exact_rtp_provenance_and_pcm():
    """The locked SDK can install its real track after the input reader has begun."""
    import asyncio

    from src.pipeline.rtp_input import RTPInputLedger, observe_native_reader

    baseline = native_client().read_audio_frame()
    expected = await anext(baseline)
    await baseline.aclose()
    client, ledger = native_client(), RTPInputLedger()
    native_track = client._audio_input_track
    client._audio_input_track = None
    for index in range(3):
        ledger.record_encoded(
            pts=index * 960,
            rtp_timestamp=10000 + index * 960,
            ssrc=7,
            payload=f"packet{index}".encode(),
        )
    reader = observe_native_reader(client, ledger)
    pending = asyncio.create_task(anext(reader))
    try:
        await asyncio.sleep(0)
        assert not pending.done()
        client._audio_input_track = native_track
        frame = await asyncio.wait_for(pending, 1)
        assert (frame.audio, frame.sample_rate, frame.pts) == (
            expected.audio,
            expected.sample_rate,
            expected.pts,
        )
        assert frame.metadata.get("td_rtp_input"), frame.metadata
        assert frame.metadata["td_rtp_input"]["packets"][0]["rtp_timestamp"] == 10000
        assert client._audio_input_track is native_track
    finally:
        pending.cancel()
        await reader.aclose()


@pytest.mark.asyncio
async def test_native_track_replacement_is_observed_without_pinning_the_old_track():
    """A lifecycle replacement on the same connection retains only its proven native extents."""
    from src.pipeline.rtp_input import RTPInputLedger, observe_native_reader

    client, ledger = native_client(), RTPInputLedger()
    for index in range(3):
        ledger.record_encoded(
            pts=index * 960,
            rtp_timestamp=10000 + index * 960,
            ssrc=7,
            payload=f"packet{index}".encode(),
        )
    reader = observe_native_reader(client, ledger)
    try:
        await anext(reader)
        replacement = Track()
        replacement.frames = iter([audio_frame(960), audio_frame(1920)])
        client._audio_input_track = replacement
        frame = await anext(reader)
        assert frame.metadata.get("td_rtp_input"), frame.metadata
        assert client._audio_input_track is replacement
        assert [part["rtp_timestamp"] for part in frame.metadata["td_rtp_input"]["packets"]] == [
            10000,
            10960,
        ]
    finally:
        await reader.aclose()
