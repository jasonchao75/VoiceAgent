"""D-049: first matching Final replaces a submitted Partial without meaning judgment."""

from importlib import import_module, util

import pytest


def controller():
    """Require the production response revision boundary."""
    assert util.find_spec("src.pipeline.response_revision") is not None, "Final restart absent"
    return import_module("src.pipeline.response_revision").ResponseRevisions()


@pytest.mark.parametrize("final", ["我要办理", "我要办理。", "我不要办理"])
def test_first_final_always_restarts_submitted_partial(final):
    """Identical, formatting-only and changed-meaning Finals all restart (D-049)."""
    state = controller()
    old = state.submit(turn_id="t1", source_ids=((0, "s1"),), text="我要办理", final=False)
    result = state.finalize(turn_id="t1", source_ids=((0, "s1"),), revision=2, text=final)
    assert result.cancel_response_id == old.response_id
    assert result.new_response.text == final
    assert result.new_response.turn_id == old.turn_id
    assert state.user_submission_count == 1
    assert not state.accepts_output(old.response_id)
    assert state.accepts_output(result.new_response.response_id)
    assert state.finalize(turn_id="t1", source_ids=((0, "s1"),), revision=2, text=final) is None
    assert (
        state.finalize(turn_id="t1", source_ids=((0, "s1"),), revision=3, text=final + ".") is None
    )


def test_stale_and_foreign_final_do_not_cancel_current_response():
    """A new speech generation fences old Final even before its next submission."""
    state = controller()
    old = state.submit(turn_id="t1", source_ids=((0, "a"),), text="old", final=False)
    assert state.finalize(turn_id="t1", source_ids=((1, "a"),), revision=2, text="foreign") is None
    state.begin_speech()
    assert state.finalize(turn_id="t1", source_ids=((0, "a"),), revision=2, text="late") is None
    assert not state.accepts_output(old.response_id)


def test_final_submission_does_not_restart_and_side_effects_are_once():
    """A Final-first turn and a replayed tool side effect do not trigger more work."""
    state = controller()
    state.submit(turn_id="t1", source_ids=((0, "a"),), text="final", final=True)
    assert state.finalize(turn_id="t1", source_ids=((0, "a"),), revision=2, text="final.") is None
    assert state.claim_operation("t1", "clear_identifier", ((0, "a"),))
    assert not state.claim_operation("t1", "clear_identifier", ((0, "a"),))
