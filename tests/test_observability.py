"""Safe interruption and first-audio timing tests."""

import pytest
from pipecat.frames.frames import InterruptionFrame, TTSAudioRawFrame
from pipecat.observers.base_observer import FramePushed
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from src.observability import SessionEventBuffer, SessionTimingObserver


@pytest.mark.asyncio
async def test_interruption_and_tts_audio_are_recorded_once_per_frame() -> None:
    """Expose timing signals without storing transcript text or audio bytes."""
    buffer = SessionEventBuffer()
    observer = SessionTimingObserver(session_id="safe-session-id", event_sink=buffer.add)
    processor = FrameProcessor(name="test-processor")
    frames = [
        InterruptionFrame(),
        TTSAudioRawFrame(audio=b"\x00\x00", sample_rate=24_000, num_channels=1),
    ]
    for frame in frames:
        pushed = FramePushed(
            source=processor,
            destination=processor,
            frame=frame,
            direction=FrameDirection.DOWNSTREAM,
            timestamp=0,
        )
        await observer.on_push_frame(pushed)
        await observer.on_push_frame(pushed)

    events = buffer.snapshot()
    assert [event["event"] for event in events] == ["interruption", "tts_first_audio"]
    assert all("audio" not in event for event in events)
