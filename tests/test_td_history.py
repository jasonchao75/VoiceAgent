"""HISTORY-01: Partial submission is not fabricated ASR Final evidence."""

from pipecat.frames.frames import LLMContextFrame, LLMTextFrame, TranscriptionFrame
from pipecat.processors.aggregators.llm_context import LLMContext

from src.history.capture import CallCapture
from src.history.models import TurnMetric
from src.history.storage import HistoryStore


def test_renderer_causal_coordinates_accept_network_reordering_but_reject_impossible_samples():
    """Receipt arrival can reorder; output sample coordinates cannot contradict each other."""
    for terminal in ("task_finished", "task_stopped"):
        for terminal_first in (False, True):
            capture = CallCapture(provider="openai", model="fixture")
            capture.record_td_event(
                {
                    "event": "playback_task_prepared",
                    "playback_id": "p",
                    "response_id": "1:1",
                    "turn_id": 1,
                    "kind": "normal",
                }
            )
            calls = []
            capture.playback_listener = lambda *args, calls=calls: calls.append(args)
            clock = {"render_sample_rate": 24000, "render_clock_id": "a" * 32}
            start = ("task_started", 128, 1000)
            finish = (terminal, 500, 1499)
            first, second = (finish, start) if terminal_first else (start, finish)
            assert capture.playback_receipt(
                "p", first[0], first[1], 10, render_frame=first[2], **clock
            )
            before = list(capture.td_events)
            assert not capture.playback_receipt(
                "p", second[0], second[1], 20, render_frame=second[2], **clock
            )
            assert capture.td_events == before and len(calls) == 1
            # A 500-sample task needs at least [1000, 1500); gaps may make it longer.
            valid_frame = 999 if terminal_first else 1500
            assert capture.playback_receipt(
                "p", second[0], second[1], 20, render_frame=valid_frame, **clock
            )


def test_late_render_receipt_explains_missing_clock_on_its_original_turn_only():
    """Observed rendering and measured cross-clock latency are different evidence levels."""
    from pipecat.frames.frames import TTSAudioRawFrame, TTSStartedFrame, UserStartedSpeakingFrame

    capture = CallCapture(provider="openai", model="fixture")
    for turn_id in (7, 8):
        capture.observe(UserStartedSpeakingFrame())
        commit = TranscriptionFrame("12", "", "")
        commit.metadata.update(td_commit=True, td_source_final=False, td_turn_id=turn_id)
        capture.observe(commit)
        capture.observe(LLMContextFrame(LLMContext()))
        capture.observe(LLMTextFrame("answer"))
        capture.observe(TTSStartedFrame())
        capture.observe(TTSAudioRawFrame(bytes(256), 24000, 1))
    capture.record_td_event(
        {
            "event": "playback_task_prepared",
            "playback_id": "old",
            "turn_id": 7,
            "response_id": "7:1",
            "kind": "normal",
        }
    )
    assert capture.playback_receipt(
        "old",
        "task_started",
        128,
        15,
        render_frame=1024,
        render_sample_rate=24000,
        render_clock_id="a" * 32,
    )
    metrics = capture.metrics_snapshot()
    assert metrics[0].incomplete_reason == "render_clock_uncorrelated"
    assert metrics[1].incomplete_reason == "client_playback_unconfirmed"
    assert all(row.playback_ms is None and row.turn_to_playback_ms is None for row in metrics)


def test_partial_commit_keeps_final_latency_unknown_but_records_llm_work():
    """A user turn and LLM latency can exist before the source has finalized."""
    capture = CallCapture(provider="openai", model="gpt-4.1-mini")
    source = TranscriptionFrame("12", "", "")
    source.metadata["td_source_only"] = True
    capture.observe(source)
    assert capture.turns == []
    committed = TranscriptionFrame("12", "", "")
    committed.metadata.update(td_commit=True, td_source_final=False)
    capture.observe(committed)
    capture.observe(LLMContextFrame(LLMContext()))
    capture.observe(LLMTextFrame("answer"))
    turns, metrics = capture.finalize()
    assert turns[0].text == "12"
    assert len(metrics) == 1
    assert metrics[0].asr_final_latency_ms is None
    assert metrics[0].asr_final_reason == "partial_at_td_commit"
    assert metrics[0].llm_first_token_ms is not None


async def test_actual_td_events_survive_history_restart(tmp_path):
    """Persist distinct candidate and commit evidence atomically with existing history."""
    store = HistoryStore(tmp_path)
    await store.initialize()
    await store.start_call(
        call_id="td-fixture",
        bot_id=None,
        bot_name=None,
        llm_provider="openai",
        llm_model="fixture",
        asr_provider="deepgram",
        asr_model="flux-general-en",
        language="en",
        sample_rate=16000,
        channels=1,
    )
    events = [
        {"event": "candidate_created", "turn_id": 1, "candidate": 1, "audio_ms": 1000},
        {"event": "td_commit", "turn_id": 1, "source_final": False, "text": "12"},
        {
            "event": "playback_renderer_receipt",
            "turn_id": 1,
            "render_frame": 1024,
            "render_sample_rate": 24000,
            "render_clock_id": "c" * 32,
        },
    ]
    await store.finish_call(
        call_id="td-fixture",
        status="completed",
        duration_ms=1000,
        turns=[],
        metrics=[
            TurnMetric(turn_index=0, playback_ms=20, playback_evidence="client_render_confirmed")
        ],
        recording_path=None,
        recording_status="not_applicable",
        td_events=events,
    )
    restarted = HistoryStore(tmp_path)
    await restarted.initialize()
    detail = await restarted.get_call("td-fixture")
    assert detail.td_events == events
    assert detail.metrics[0].playback_evidence == "client_render_confirmed"


def test_legacy_playback_numbers_are_explicitly_unverified_not_client_render_evidence():
    """A stored numeric value alone does not prove the provenance of browser playback."""
    from src.history.models import TurnMetric

    legacy = TurnMetric(turn_index=0, playback_ms=20, turn_to_playback_ms=500)
    assert legacy.playback_evidence == "unverified_client_report"
    assert legacy.playback_ms == 20 and legacy.turn_to_playback_ms == 500
    missing = TurnMetric(turn_index=1)
    assert missing.playback_evidence == "missing"


async def test_legacy_database_null_evidence_preserves_value_and_marks_unverified(tmp_path):
    """Migrated records retain their numbers without claiming a new confirmation."""
    import aiosqlite

    await test_actual_td_events_survive_history_restart(tmp_path)
    store = HistoryStore(tmp_path)
    async with aiosqlite.connect(store.database_path) as database:
        await database.execute("UPDATE turn_metrics SET playback_evidence = NULL")
        await database.commit()
    detail = await store.get_call("td-fixture")
    assert detail.metrics[0].playback_ms == 20
    assert detail.metrics[0].playback_evidence == "unverified_client_report"


def test_no_client_ack_is_unknown_not_proof_that_playback_never_started():
    """P11 keeps missing client evidence separate from server-side synthesis completion."""
    from pipecat.frames.frames import TTSAudioRawFrame, TTSStartedFrame

    capture = CallCapture(provider="openai", model="gpt-4.1-mini")
    capture.chat_text("hello")
    capture.observe(LLMContextFrame(LLMContext()))
    capture.observe(LLMTextFrame("answer"))
    capture.observe(TTSStartedFrame())
    capture.observe(TTSAudioRawFrame(b"\x00\x00" * 160, 16000, 1))
    metric = capture.finalize()[1][0]
    assert metric.playback_ms is None
    assert metric.incomplete_reason == "client_playback_unconfirmed"


def test_bounded_td_history_exposes_dropped_events_instead_of_silent_loss():
    """A long call must preserve its retained facts and declare missing later evidence."""
    capture = CallCapture(provider="openai", model="gpt-4.1-mini")
    for index in range(10002):
        capture.record_td_event({"event": "source_transcript", "source_revision": index})
    assert len(capture.td_events) == 10001
    assert capture.td_events[9999]["source_revision"] == 9999
    assert capture.td_events[-1]["event"] == "td_evidence_truncated"
    assert capture.td_events[-1]["dropped_events"] == 2


def test_renderer_receipts_require_prepared_identity_and_never_target_current_turn():
    from src.history.capture import CallCapture

    capture = CallCapture(provider="fixture", model="fixture")
    acknowledgements = []
    capture.playback_listener = lambda *args: acknowledgements.append(args)
    assert hasattr(capture, "playback_receipt"), "Task-bound renderer capture absent"
    assert not capture.playback_receipt("unknown", "task_started", 128, 1.0)
    capture.record_td_event(
        {
            "event": "playback_task_prepared",
            "playback_id": "known",
            "response_id": "1:2",
            "kind": "normal",
        }
    )
    assert not capture.playback_receipt("known", "task_started", 0, 1.0)
    assert capture.playback_receipt("known", "task_started", 128, 1.0)
    assert capture._current.browser_playback_ms is None
    assert capture.playback_receipt("known", "task_stopped", 128, 2.0)
    assert not capture.playback_receipt("known", "task_stopped", 64, 3.0)
    receipts = [
        event for event in capture.td_events if event["event"] == "playback_renderer_receipt"
    ]
    assert len(receipts) == 2
    assert all(event["response_id"] == "1:2" for event in receipts)
    assert receipts[0]["evidence_source"] == "audio_worklet_render"
    assert acknowledgements == [("known", "task_started"), ("known", "task_stopped")]


def test_renderer_failure_reason_is_preserved_without_raw_error_text():
    from src.history.capture import CallCapture

    capture = CallCapture(provider="fixture", model="fixture")
    capture.record_td_event(
        {"event": "playback_task_prepared", "playback_id": "known", "kind": "normal"}
    )
    assert capture.playback_receipt(
        "known", "task_failed", 0, 1.0, failure_reason="render_queue_limit"
    )
    assert capture.td_events[-1]["failure_reason"] == "render_queue_limit"


def test_final_replacement_retains_each_generated_response_with_original_turn_identity():
    from pipecat.frames.frames import LLMFullResponseEndFrame

    capture = CallCapture(provider="openai", model="fixture")
    user = TranscriptionFrame("12", "", "")
    user.metadata.update(td_commit=True, td_source_final=False, td_turn_id=7)
    capture.observe(user)
    capture.observe(LLMContextFrame(LLMContext()))
    for response_id, text in [("7:1", "old partial answer"), ("7:2", "Final answer")]:
        frame = LLMTextFrame(text)
        frame.metadata.update(td_turn_id="7", td_response_id=response_id)
        capture.observe(frame)
        # First version may be interrupted without an LLMFullResponseEndFrame.
    capture.observe(LLMFullResponseEndFrame())
    evidence = [e for e in capture.td_events if e["event"] == "conversation_utterance"]
    assert [(e["role"], e["turn_id"], e.get("response_id"), e["text"]) for e in evidence] == [
        ("user", 7, None, "12"),
        ("assistant", "7", "7:1", "old partial answer"),
        ("assistant", "7", "7:2", "Final answer"),
    ]
    assert evidence[0]["history_metric_index"] == 0
    assert len(capture.finalize()[1]) == 1


def test_legacy_playback_event_cannot_manufacture_td_render_latency():
    """Legacy current-turn telemetry cannot correlate an identified TD render clock."""
    from pipecat.frames.frames import TTSAudioRawFrame, TTSStartedFrame

    capture = CallCapture(provider="openai", model="fixture")
    committed = TranscriptionFrame("hello", "", "")
    committed.metadata.update(td_commit=True, td_source_final=False, td_turn_id=7)
    capture.observe(committed)
    capture.observe(LLMContextFrame(LLMContext()))
    capture.observe(LLMTextFrame("answer"))
    capture.observe(TTSStartedFrame())
    capture.observe(TTSAudioRawFrame(bytes(256), 24000, 1))
    capture.browser_event("first_playback", 10)
    metric = capture.metrics_snapshot()[0]
    assert metric.playback_ms is None
    assert metric.server_to_playback_ms is None
    assert metric.incomplete_reason == "client_playback_unconfirmed"


def test_correlated_render_range_stays_on_original_response_without_inventing_e2e(monkeypatch):
    """Late anchors can complete playback evidence without manufacturing a speech-end clock."""
    from pipecat.frames.frames import TTSAudioRawFrame, TTSStartedFrame, UserStartedSpeakingFrame

    now = [0.0]
    monkeypatch.setattr(CallCapture, "elapsed_ms", lambda self: now[0])
    capture = CallCapture(provider="openai", model="fixture")
    commit = TranscriptionFrame("hello", "", "")
    commit.metadata.update(td_commit=True, td_source_final=False, td_turn_id=7)
    capture.observe(commit)
    capture.observe(LLMContextFrame(LLMContext()))
    text = LLMTextFrame("answer")
    text.metadata.update(td_turn_id=7, td_response_id="7:1")
    capture.observe(text)
    capture.observe(TTSStartedFrame())
    capture.observe(TTSAudioRawFrame(bytes(256), 24000, 1))
    now[0] = 90
    before = capture.render_clock.issue("a" * 32, 48000)
    now[0] = 100
    capture.record_td_event(
        {
            "event": "playback_task_prepared",
            "playback_id": "p",
            "turn_id": 7,
            "response_id": "7:1",
            "kind": "normal",
        }
    )
    now[0] = 110
    assert capture.ack_render_clock(before, "a" * 32, 48000, 1000)
    now[0] = 140
    assert capture.playback_receipt(
        "p",
        "task_started",
        128,
        999,
        render_frame=1500,
        render_sample_rate=48000,
        render_clock_id="a" * 32,
    )
    capture.observe(UserStartedSpeakingFrame())
    next_commit = TranscriptionFrame("next", "", "")
    next_commit.metadata.update(td_commit=True, td_source_final=False, td_turn_id=8)
    capture.observe(next_commit)
    now[0] = 150
    after = capture.render_clock.issue("a" * 32, 48000)
    now[0] = 180
    assert capture.ack_render_clock(after, "a" * 32, 48000, 2000)
    metrics = capture.metrics_snapshot()
    timing = metrics[0].timing_ranges["playback"]
    assert (timing.lower_ms, timing.upper_ms) == (0, 80)
    assert timing.response_id == "7:1"
    assert timing.anchor_ids == (before, after)
    assert timing.origin == "server_audio_task_prepared"
    assert metrics[1].timing_ranges == {}
    assert metrics[0].playback_ms is None
    assert metrics[0].turn_to_playback_ms is None
    assert "e2e" not in metrics[0].timing_ranges
    assert any(
        row["event"] == "playback_timing_bounds" and row["response_id"] == "7:1"
        for row in capture.td_events
    )


async def test_measured_ranges_survive_storage_restart_without_backfilling_legacy_rows(tmp_path):
    """D-073 preserves interval evidence independently of nullable legacy scalar metrics."""
    from src.history.models import LatencyInterval

    store = HistoryStore(tmp_path)
    await store.initialize()
    await store.start_call(
        call_id="range",
        bot_id=None,
        bot_name=None,
        llm_provider="openai",
        llm_model="fixture",
        asr_provider="deepgram",
        asr_model="flux-general-en",
        language="en",
        sample_rate=16000,
        channels=1,
    )
    interval = LatencyInterval(
        lower_ms=5,
        upper_ms=25,
        playback_id="a" * 32,
        response_id="7:1",
        anchor_ids=("b" * 32, "c" * 32),
        source="authenticated_worklet_causal_bracket",
        origin="server_audio_task_prepared",
    )
    await store.finish_call(
        call_id="range",
        status="completed",
        duration_ms=1000,
        turns=[],
        metrics=[
            TurnMetric(turn_index=0, timing_ranges={"playback": interval}),
            TurnMetric(turn_index=1),
        ],
        recording_path=None,
        recording_status="not_applicable",
    )
    restarted = HistoryStore(tmp_path)
    await restarted.initialize()
    detail = await restarted.get_call("range")
    assert detail.metrics[0].timing_ranges["playback"] == interval
    assert detail.metrics[0].playback_ms is None
    assert detail.metrics[1].timing_ranges == {}


def test_idle_clock_sampling_cannot_fill_persistent_conversation_evidence(monkeypatch):
    """Only anchors used by actual task ranges belong in durable conversation evidence."""
    now = [0.0]
    monkeypatch.setattr(CallCapture, "elapsed_ms", lambda self: now[0])
    capture = CallCapture(provider="openai", model="fixture")
    for index in range(100):
        sample = capture.render_clock.issue("a" * 32, 48000)
        now[0] += 1
        assert capture.ack_render_clock(sample, "a" * 32, 48000, index * 128)
    assert capture.td_events == []
