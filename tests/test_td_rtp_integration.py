"""Development-only native output binding preserves identity and control extents."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pipecat.frames.frames import OutputTransportMessageFrame

from src.pipeline.audio_identity import audio_frame_type


@pytest.mark.asyncio
async def test_native_output_binding_preserves_task_and_extent():
    """The actual output writer must not reduce task audio to anonymous bytes."""
    from src.pipeline.rtp_mapping import MappedRawAudioTrack, RTPTaskLedger
    from src.pipeline.rtp_output import bind_candidate_output

    track = MappedRawAudioTrack(24000, RTPTaskLedger())
    controls = []
    output = SimpleNamespace(write_audio_frame=AsyncMock(), send_message=AsyncMock())
    bind_candidate_output(output, track, controls.append)
    frame_type = audio_frame_type(playback_id="a" * 32, kind="normal", response_id="1:1")
    pending = asyncio.create_task(output.write_audio_frame(frame_type(bytes(960), 24000, 1)))
    await asyncio.sleep(0)
    assert not pending.done()
    assert len(track._chunk_queue) == 2
    await track.recv()
    await track.recv()
    assert await pending
    await output.send_message(
        OutputTransportMessageFrame(
            message={
                "label": "voice-agent-playback",
                "event": "task_end",
                "playback_id": "a" * 32,
            }
        )
    )
    assert len(track._chunk_queue) == 0
    assert controls[-1]["expected_samples"] == 960
    track.stop()


@pytest.mark.asyncio
async def test_native_track_replacement_is_mapped_before_sender_use():
    """SDK track installation and output share the same provenance-owning object."""
    from unittest.mock import Mock

    from src.pipeline.rtp_mapping import MappedRawAudioTrack
    from src.pipeline.rtp_output import install_candidate_transport

    native = SimpleNamespace(_sample_rate=24000, stop=Mock())
    sender = SimpleNamespace(
        track=SimpleNamespace(kind="audio"), transport=SimpleNamespace(_send_rtp=AsyncMock())
    )
    connection = SimpleNamespace(
        _pc=SimpleNamespace(getTransceivers=lambda: [SimpleNamespace(kind="audio", sender=sender)]),
        replace_audio_track=Mock(),
        send_app_message=Mock(),
    )
    original_replace = connection.replace_audio_track
    output = SimpleNamespace(write_audio_frame=AsyncMock(), send_message=AsyncMock())
    transport = SimpleNamespace(_client=SimpleNamespace(), output=lambda: output)
    install_candidate_transport(transport, connection)
    connection.replace_audio_track(native)
    mapped = transport._client._audio_output_track
    assert isinstance(mapped, MappedRawAudioTrack)
    original_replace.assert_called_once_with(mapped)
    native.stop.assert_called_once()
    mapped.stop()


@pytest.mark.asyncio
async def test_negotiated_audio_sender_without_initial_track_can_be_bound():
    """A real native audio transceiver has a sender before it has any source track."""
    from aiortc import RTCPeerConnection

    from src.pipeline.rtp_output import install_candidate_transport

    peer = RTCPeerConnection()
    transceiver = peer.addTransceiver("audio", direction="sendrecv")
    assert transceiver.sender.track is None
    connection = SimpleNamespace(
        _pc=peer,
        replace_audio_track=lambda track: transceiver.sender.replaceTrack(track),
        send_app_message=lambda message: None,
    )
    output = SimpleNamespace(write_audio_frame=AsyncMock(), send_message=AsyncMock())
    transport = SimpleNamespace(_client=SimpleNamespace(), output=lambda: output)
    from pipecat.transports.smallwebrtc.transport import RawAudioTrack

    from src.pipeline.rtp_mapping import MappedRawAudioTrack

    track = RawAudioTrack(24000)
    try:
        install_candidate_transport(transport, connection)
        connection.replace_audio_track(track)
        assert isinstance(transceiver.sender.track, MappedRawAudioTrack)
    finally:
        track.stop()
        await peer.close()
