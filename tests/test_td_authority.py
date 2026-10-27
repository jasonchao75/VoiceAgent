"""M1-4: provider endpoints and SDK defaults cannot bypass the custom authority."""

from pipecat.frames.frames import (
    ProposedUserStoppedSpeakingFrame,
    TranscriptionFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.turns.types import ProcessFrameResult

from src.pipeline.td_strategies import TDCommitFrame, TDStopStrategy, custom_aggregator_params


async def test_stop_strategy_rejects_provider_and_foreign_commit():
    """Only the session coordinator can stop a user turn; Final is text evidence."""
    authority = object()
    strategy = TDStopStrategy(authority)
    stops = []

    async def capture(**kwargs):
        stops.append(kwargs)

    strategy.trigger_user_turn_stopped = capture
    for frame in [
        ProposedUserStoppedSpeakingFrame(),
        UserStoppedSpeakingFrame(),
        TranscriptionFrame("text", "", ""),
        TDCommitFrame(authority=object()),
    ]:
        assert await strategy.process_frame(frame) == ProcessFrameResult.CONTINUE
    assert stops == []
    assert (
        await strategy.process_frame(TDCommitFrame(authority=authority)) == ProcessFrameResult.STOP
    )
    assert stops == [{"enable_user_speaking_frames": False}]


def test_no_sdk_timer_or_smart_turn_in_custom_aggregator():
    """Native service metadata must not silently restore the default strategy chain."""
    params = custom_aggregator_params(object())
    assert params.audio_idle_timeout == 0
    assert params.user_turn_stop_timeout == float("inf")
    assert len(params.user_turn_strategies.stop) == 1
    assert isinstance(params.user_turn_strategies.stop[0], TDStopStrategy)
