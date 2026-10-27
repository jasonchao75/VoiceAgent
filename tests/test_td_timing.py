"""Fake-clock contracts for TIME-01/02 and JEV-01/02."""

from importlib import import_module, util

import pytest


def types():
    """Load the real controller only after checking the required behavior exists."""
    assert util.find_spec("src.pipeline.turn_detection") is not None, "Custom TD timing is absent"
    return import_module("src.pipeline.turn_detection")


def test_distribution_fusion_subtracts_elapsed_once():
    """The frozen 825/375 example uses the entire Choice distribution."""
    td = types()
    policy = td.WaitPolicy(600, 2500, 200, 0.5, 0.8)
    result = policy.fuse(
        0.9,
        {"complete": 0.8, "incomplete": 0.2},
        {"complete": 700, "incomplete": 1500},
        elapsed_ms=450,
    )
    assert result.noul_ms == pytest.approx(790)
    assert result.choice_ms == pytest.approx(860)
    assert result.target_ms == pytest.approx(825)
    assert result.remaining_ms == pytest.approx(375)


@pytest.mark.parametrize(
    "probabilities",
    [
        {"complete": 0.8},
        {"complete": float("nan"), "incomplete": 0.2},
        {"complete": -0.1, "incomplete": 1.1},
        {"complete": 0.4, "incomplete": 0.4},
    ],
)
def test_invalid_distribution_never_becomes_valid_wait(probabilities):
    """Missing/invalid probabilities cannot become a fabricated semantic decision."""
    td = types()
    with pytest.raises(ValueError):
        td.WaitPolicy(600, 2500, 200, 0.5, 0.8).fuse(
            0.9, probabilities, {"complete": 700, "incomplete": 1500}, elapsed_ms=450
        )


def test_independent_maximum_and_single_submission():
    """A missing Jev result and missing Final cannot extend the deadline."""
    td = types()
    clock = td.TurnClock(td.WaitPolicy(600, 2500, 200, 0.5, 0.8))
    token = clock.pause(1000)
    clock.transcript(token, "latest", final=False)
    assert clock.poll(3499) is None
    assert clock.poll(3500).text == "latest"
    assert clock.poll(3501) is None


def test_final_wait_begins_after_semantic_target_and_is_bounded():
    """Final wait is a separate window starting only once the target permits ending."""
    td = types()
    clock = td.TurnClock(td.WaitPolicy(600, 2500, 200, 0.5, 0.8))
    token = clock.pause(0)
    clock.transcript(token, "partial", final=False)
    clock.semantic(token, 700, text_revision=clock.text_revision)
    assert clock.poll(699) is None
    assert clock.poll(700) is None
    assert clock.poll(899) is None
    clock.transcript(token, "partial", final=True)
    assert clock.poll(899).text == "partial"


def test_resume_invalidates_late_results_and_commit_race():
    """Old semantic results, transcript and deadline cannot commit newer speech."""
    td = types()
    clock = td.TurnClock(td.WaitPolicy(600, 2500, 200, 0.5, 0.8))
    old = clock.pause(0)
    clock.transcript(old, "old", final=True)
    clock.resume()
    assert not clock.semantic(old, 600, text_revision=clock.text_revision)
    assert not clock.transcript(old, "late old", final=True)
    assert clock.poll(2500) is None
    current = clock.pause(2500)
    clock.transcript(current, "new", final=True)
    assert clock.poll(4999) is None
    assert clock.poll(5000).text == "new"


def test_revision_invalidates_semantic_result_but_not_hard_deadline():
    """A text update must not reuse Jev's verdict for the old text."""
    td = types()
    clock = td.TurnClock(td.WaitPolicy(600, 2500, 200, 0.5, 0.8))
    token = clock.pause(0)
    clock.transcript(token, "old", final=False)
    clock.semantic(token, 600, text_revision=clock.text_revision)
    clock.transcript(token, "revised", final=True)
    assert clock.poll(1000) is None
    assert clock.poll(2500).text == "revised"


def test_media_gap_and_empty_text_cannot_commit():
    """Disconnected or backlogged input is not evidence of continuous silence."""
    td = types()
    clock = td.TurnClock(td.WaitPolicy(600, 2500, 200, 0.5, 0.8))
    token = clock.pause(0)
    assert clock.poll(2500) is None
    clock.transcript(token, "text", final=True)
    clock.media_healthy = False
    assert clock.poll(2600) is None


def test_delayed_semantic_result_is_bound_to_text_revision():
    """A cancelled HTTP request may still return after the transcript changed."""
    td = types()
    clock = td.TurnClock(td.WaitPolicy(600, 2500, 200, 0.5, 0.8))
    token = clock.pause(0)
    clock.transcript(token, "old", final=False)
    old_revision = clock.text_revision
    clock.transcript(token, "new", final=True)
    assert not clock.semantic(token, 600, text_revision=old_revision)
    assert clock.poll(1000) is None
    assert clock.poll(2500).text == "new"


def test_final_deadline_cannot_authorize_revised_text_without_a_new_semantic_result():
    """D-080 invalidates old authorization while preserving the original hard deadline."""
    td = types()
    clock = td.TurnClock(td.WaitPolicy(600, 2500, 200, 0.5, 0.8))
    token = clock.pause(0)
    clock.transcript(token, "old", final=False)
    clock.semantic(token, 600, text_revision=clock.text_revision)
    assert clock.poll(600) is None
    clock.transcript(token, "new", final=False)
    assert clock.poll(800) is None
    assert clock.poll(2499) is None
    assert clock.poll(2500).text == "new"


def test_revised_target_delays_commit_without_restarting_the_final_window():
    """D-080 waits for the new target but does not add a fresh Final window after it."""
    td = types()
    clock = td.TurnClock(td.WaitPolicy(600, 2500, 200, 0.5, 0.8))
    token = clock.pause(0)
    clock.transcript(token, "old", final=False)
    clock.semantic(token, 600, text_revision=clock.text_revision)
    assert clock.poll(600) is None
    clock.transcript(token, "new", final=False)
    clock.semantic(token, 2000, text_revision=clock.text_revision)
    assert clock.poll(800) is None
    assert clock.poll(1999) is None
    assert clock.poll(2000).text == "new"
