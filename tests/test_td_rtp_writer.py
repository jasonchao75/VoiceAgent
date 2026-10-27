"""RTP control EOS is gated by actual decoded sample coverage at the receiver."""

import pytest

from src.pipeline.audio_identity import audio_frame_type
from src.pipeline.rtp_mapping import MappedRawAudioTrack, RTPTaskLedger
from src.pipeline.rtp_output import RTPCandidateWriter


@pytest.mark.asyncio
async def test_writer_counts_exact_render_extent_and_stops_unsent_source():
    """EOS advertises an immutable total; cancellation is not called client stop."""
    track = MappedRawAudioTrack(24000, RTPTaskLedger())
    controls = []
    writer = RTPCandidateWriter(track, controls.append)
    cls = audio_frame_type(playback_id="A", kind="normal", response_id="1:1")
    writer.audio(cls(bytes(960), 24000, 1))
    writer.control({"event": "task_end", "playback_id": "A"})
    assert controls[-1]["expected_samples"] == 960
    assert len(track._chunk_queue) == 2
    writer.control({"event": "stop_task", "playback_id": "A", "request_id": "stop-A"})
    assert controls[-1] == {"event": "stop_task", "playback_id": "A", "request_id": "stop-A"}
    assert len(track._chunk_queue) == 0
    writer.audio(cls(bytes(480), 24000, 1))
    assert len(track._chunk_queue) == 0
    assert not any(item.get("event") == "task_stopped" for item in controls)
    track.stop()
