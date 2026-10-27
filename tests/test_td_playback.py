"""P01-P11: serial playback and client evidence boundaries."""

from importlib import import_module, util


def arbiter():
    """Require the actual session arbiter rather than testing a priority list fixture."""
    assert util.find_spec("src.pipeline.playback") is not None, "Playback arbiter absent"
    return import_module("src.pipeline.playback").PlaybackArbiter()


def queue(player, identity, **kwargs):
    """Prepare one source-owned task without treating it as played."""
    return player.enqueue(
        playback_id=identity,
        kind="echo",
        generation=0,
        source_id="a",
        revision=1,
        source_order=1,
        **kwargs,
    )


def test_send_is_unknown_until_actual_client_start_and_serial_finish():
    player = arbiter()
    queue(player, "a")
    player.enqueue(
        playback_id="b", kind="echo", generation=0, source_id="b", revision=1, source_order=2
    )
    task = player.dispatch()
    assert task.playback_id == "a" and task.status == "sent_unknown"
    assert task.started is False and player.dispatch() is None
    assert player.client_started("other") is False
    assert player.client_started("a")
    assert task.started and task.status == "playing"
    assert player.dispatch() is None
    assert player.client_finished("a")
    assert player.dispatch().playback_id == "b"


def test_latest_unplayed_revision_replaces_old_task_without_false_playback():
    player = arbiter()
    old = queue(player, "a1")
    newest = player.enqueue(
        playback_id="a2", kind="echo", generation=0, source_id="a", revision=2, source_order=1
    )
    assert old.status == "cancelled_unplayed" and old.started is False
    assert player.dispatch() is newest
    assert (
        player.enqueue(
            playback_id="duplicate",
            kind="echo",
            generation=0,
            source_id="a",
            revision=2,
            source_order=1,
        )
        is None
    )


def test_normal_ready_skips_unplayed_final_echo_but_never_claims_unknown_was_unplayed():
    player = arbiter()
    final_echo = queue(player, "echo", final_segment=True)
    normal = player.enqueue(
        playback_id="normal",
        kind="normal",
        generation=0,
        source_id="response",
        revision=1,
        source_order=2,
    )
    assert final_echo.status == "cancelled_unplayed"
    assert player.dispatch() is normal
    player.client_finished("normal")
    unknown = player.enqueue(
        playback_id="unknown",
        kind="echo",
        generation=0,
        source_id="c",
        revision=1,
        source_order=3,
        final_segment=True,
    )
    assert player.dispatch() is unknown
    player.enqueue(
        playback_id="next",
        kind="normal",
        generation=0,
        source_id="response2",
        revision=1,
        source_order=4,
    )
    assert unknown.status == "sent_unknown" and player.dispatch() is None


def test_previous_correction_precedes_new_echo_and_overflow_skips_unplayed_tail():
    player = arbiter()
    queue(player, "new")
    previous = player.enqueue(
        playback_id="correction",
        kind="correction",
        generation=0,
        source_id="previous",
        revision=2,
        source_order=0,
    )
    assert player.dispatch() is previous
    player.client_finished("correction")
    overflow = player.enqueue(
        playback_id="overflow",
        kind="overflow",
        generation=0,
        source_id="reminder",
        revision=1,
        source_order=2,
    )
    assert player.tasks["new"].status == "cancelled_unplayed"
    assert player.dispatch() is overflow


def test_continuation_preserves_active_echo_but_clear_requires_stop_ack_before_next():
    player = arbiter()
    active = queue(player, "active")
    player.dispatch()
    player.client_started("active")
    player.user_speech()
    assert active.status == "playing"
    player.clear(1)
    assert active.status == "stop_requested" and active.started
    assert player.stop_requests == ["active"]
    assert (
        player.enqueue(
            playback_id="late", kind="echo", generation=0, source_id="a", revision=2, source_order=1
        )
        is None
    )
    newer = player.enqueue(
        playback_id="new", kind="echo", generation=1, source_id="b", revision=1, source_order=2
    )
    assert player.dispatch() is None
    player.client_finished("active")
    assert player.dispatch() is newer


def test_interrupting_normal_response_cancels_pending_echoes_and_preserves_unknown_fact():
    player = arbiter()
    normal = player.enqueue(
        playback_id="normal",
        kind="normal",
        generation=0,
        source_id="response",
        revision=1,
        source_order=1,
    )
    player.dispatch()
    queue(player, "pending")
    player.user_speech()
    assert normal.status == "stop_requested" and normal.started is False
    assert player.tasks["pending"].status == "cancelled_unplayed"
    player.close()
    assert normal.status == "ended_unknown" and normal.started is False
    assert player.dispatch() is None


def test_ready_order_does_not_restore_echo_after_normal_or_overflow():
    """P03/P01 must hold when a delayed audio synthesis completes after its replacement."""
    for kind in ("normal", "overflow"):
        player = arbiter()
        player.enqueue(
            playback_id="answer",
            kind=kind,
            generation=0,
            source_id="response",
            revision=1,
            source_order=2,
        )
        echo = queue(player, "late", final_segment=True)
        assert echo.status == "cancelled_unplayed"
        assert player.dispatch().playback_id == "answer"
        player.client_finished("answer")
        assert player.dispatch() is None


def test_collection_clear_preserves_ordinary_response_for_independent_response_validation():
    player = arbiter()
    ordinary = player.enqueue(
        playback_id="clear-answer",
        kind="normal",
        generation=0,
        source_id="current-response",
        revision=1,
        source_order=2,
    )
    queue(player, "old-echo")
    player.clear(1)
    assert ordinary.status == "queued"
    assert player.tasks["old-echo"].status == "cancelled_unplayed"
    assert player.dispatch() is ordinary


def test_renderer_failure_is_not_recorded_as_successful_completion():
    player = arbiter()
    queue(player, "a")
    player.dispatch()
    assert player.client_finished("a", event="task_failed")
    assert player.tasks["a"].status == "failed"


def test_explicit_renderer_stop_is_preserved_without_a_server_stop_request():
    player = arbiter()
    queue(player, "a")
    player.dispatch()
    assert player.client_finished("a", event="task_stopped")
    assert player.tasks["a"].status == "stopped"
