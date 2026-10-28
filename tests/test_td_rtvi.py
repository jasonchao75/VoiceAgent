"""Verify caption identity independently from TD's private LLM submission."""

from unittest.mock import AsyncMock

import pytest
from pipecat.frames.frames import InterimTranscriptionFrame, TranscriptionFrame
from pipecat.observers.base_observer import FramePushed
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.processors.frameworks.rtvi import RTVIObserver

from src.pipeline.td_rtvi import TDRTVIProcessor
from src.pipeline.td_strategies import TDSubmissionFrame


@pytest.mark.asyncio
@pytest.mark.parametrize("custom,expected", [(False, 4), (True, 3)])
@pytest.mark.parametrize("final_first", [True, False])
async def test_private_submission_is_not_a_second_caption(
    custom: bool, expected: int, final_first: bool
) -> None:
    """Retain interim and two genuinely distinct same-text utterances; skip TD copy only."""
    observer = TDRTVIProcessor().create_rtvi_observer() if custom else RTVIObserver()
    observer.send_rtvi_message = AsyncMock()
    source = FrameProcessor()
    frames = [
        InterimTranscriptionFrame("hello", "user", "1"),
        TranscriptionFrame("hello", "user", "2"),
        TDSubmissionFrame("hello", "user", "2", authority=object()),
        TranscriptionFrame("hello", "user", "3"),
    ]
    if not final_first:
        frames[1], frames[2] = frames[2], frames[1]
    for frame in frames:
        event = FramePushed(source, source, frame, FrameDirection.DOWNSTREAM, 0)
        await observer.on_push_frame(event)
        await observer.on_push_frame(event)
    assert observer.send_rtvi_message.await_count == expected
    messages = [call.args[0] for call in observer.send_rtvi_message.await_args_list]
    assert all(message.data.text == "hello" for message in messages)
    assert messages[0].data.final is False
