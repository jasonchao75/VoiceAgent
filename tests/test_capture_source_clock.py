"""D-073 input sample identity must survive gaps without guessing a clock."""

from src.history.source_clock import CaptureSampleLedger


def test_exact_input_offsets_map_across_capture_pause_without_interpolation():
    """A pause in capture frames must not be flattened into continuous wall time."""
    ledger = CaptureSampleLedger()
    assert ledger.append(
        160, clock_id="a" * 32, sample_rate=16000, source_spans=[(1000, 80), (2000, 80)]
    )
    assert ledger.locate(40) == ("a" * 32, 16000, 1040)
    assert ledger.locate(80) is None  # The discontinuity has two possible endpoints.
    assert ledger.locate(81) == ("a" * 32, 16000, 2001)
    assert ledger.locate(160) == ("a" * 32, 16000, 2080)


def test_unproven_input_advances_offset_and_does_not_inherit_previous_clock():
    """Missing metadata never shifts later evidence onto earlier microphone audio."""
    ledger = CaptureSampleLedger()
    assert ledger.append(160, clock_id="a" * 32, sample_rate=16000, source_spans=[(1000, 160)])
    assert not ledger.append(160)
    assert ledger.locate(200) is None
    assert ledger.append(160, clock_id="b" * 32, sample_rate=16000, source_spans=[(500, 160)])
    assert ledger.locate(400) == ("b" * 32, 16000, 580)
    assert ledger.locate(320) is None


def test_bad_counts_replay_and_retention_fail_closed():
    """Invalid provenance consumes its actual PCM length and retention stays bounded."""
    ledger = CaptureSampleLedger(max_spans=2)
    assert not ledger.append(100, clock_id="a" * 32, sample_rate=16000, source_spans=[(0, 99)])
    assert ledger.locate(50) is None
    for start in (1000, 1100, 1200):
        assert ledger.append(100, clock_id="a" * 32, sample_rate=16000, source_spans=[(start, 100)])
    assert ledger.locate(150) is None
    assert not ledger.append(100, clock_id="a" * 32, sample_rate=16000, source_spans=[(1200, 100)])
    assert ledger.locate(450) is None


def test_actual_capture_consumes_wire_identity_and_rejects_shifted_offsets():
    """The production capture cannot align metadata to the wrong received PCM chunk."""
    import json

    from pipecat.frames.frames import InputAudioRawFrame

    from src.history.capture import CallCapture

    capture = CallCapture(provider="test", model="test")

    def audio(offset, start):
        frame = InputAudioRawFrame(bytes(320), 16000, 1)
        frame.name = "voice-agent-input-v1:" + json.dumps(
            {
                "clock_id": "a" * 32,
                "sample_rate": 16000,
                "offset": offset,
                "spans": [[start, 160]],
            }
        )
        return frame

    capture.observe(audio(0, 1000))
    assert capture.input_samples.locate(80) == ("a" * 32, 16000, 1080)
    capture.observe(audio(0, 1160))
    assert capture.input_samples.locate(200) is None
    capture.observe(audio(320, 1320))
    assert capture.input_samples.locate(400) == ("a" * 32, 16000, 1400)
    assert capture.metrics_snapshot() == []


def test_capture_clock_nonce_cannot_be_used_as_render_anchor():
    """Input/output clocks share server units but never nonce authority."""
    from src.history.capture import CallCapture

    capture = CallCapture(provider="test", model="test")
    nonce = capture.capture_clock.issue("a" * 32, 16000)
    assert not capture.ack_render_clock(nonce, "a" * 32, 16000, 100)
    assert capture.ack_capture_clock(nonce, "a" * 32, 16000, 100)
    assert capture.render_clock.observation(nonce) is None


def test_e2e_uses_frozen_source_bounds_after_long_td_wait(monkeypatch):
    """Source bounds survive Tmax and are subtracted as intervals, never midpoints."""
    import json

    from pipecat.frames.frames import InputAudioRawFrame

    from src.history.capture import CallCapture

    now = [0.0]
    monkeypatch.setattr(CallCapture, "elapsed_ms", lambda self: now[0])
    capture = CallCapture(provider="test", model="test")
    frame = InputAudioRawFrame(bytes(4000), 16000, 1)
    frame.name = "voice-agent-input-v1:" + json.dumps(
        {
            "clock_id": "a" * 32,
            "sample_rate": 16000,
            "offset": 0,
            "spans": [[0, 2000]],
        }
    )
    capture.observe(frame)
    before = capture.capture_clock.issue("a" * 32, 16000)
    now[0] = 10
    assert capture.ack_capture_clock(before, "a" * 32, 16000, 0)
    capture.record_td_event(
        {"event": "candidate_created", "turn_id": 1, "speech_end_audio_ms": 31.25}
    )
    now[0] = 100
    after = capture.capture_clock.issue("a" * 32, 16000)
    now[0] = 110
    assert capture.ack_capture_clock(after, "a" * 32, 16000, 2000)
    now[0] = 5000
    capture.record_td_event({"event": "td_commit", "turn_id": 1})
    capture.record_td_event(
        {
            "event": "playback_task_prepared",
            "turn_id": 1,
            "response_id": "1:1",
            "playback_id": "task",
            "kind": "normal",
        }
    )
    first = capture.render_clock.issue("b" * 32, 24000)
    now[0] = 5010
    assert capture.ack_render_clock(first, "b" * 32, 24000, 100)
    assert capture.playback_receipt(
        "task",
        "task_started",
        1,
        1,
        render_clock_id="b" * 32,
        render_sample_rate=24000,
        render_frame=200,
    )
    now[0] = 5100
    last = capture.render_clock.issue("b" * 32, 24000)
    now[0] = 5110
    assert capture.ack_render_clock(last, "b" * 32, 24000, 300)
    evidence = next(x for x in capture.td_events if x["event"] == "e2e_timing_bounds")
    assert evidence["e2e_range"]["lower_ms"] == 4890
    assert evidence["e2e_range"]["upper_ms"] == 5110
    assert evidence["e2e_range"]["origin"] == "vad_speech_end_source_sample"
    assert evidence["source_coordinates"]["first_frame"] == 500
    assert len(evidence["source_anchors"]) == len(evidence["render_anchors"]) == 2
