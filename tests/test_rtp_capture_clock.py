"""D073 RTC ingress joins native reported capture time only to proven PCM ranges."""

import copy
import json
from pathlib import Path


def recorded():
    """Reuse actual r86 native packet/decoder/resampler evidence, not invented offsets."""
    return json.loads((Path(__file__).parent / "fixtures/td-rtp-capture-v1.json").read_text())


def ledger(now, data):
    """Register only the exact forwarded chunks before browser metadata arrives."""
    from src.history.rtp_source import RTPCaptureLedger

    result = RTPCaptureLedger(now_ms=lambda: now[0])
    epoch = data["proofs"][0]["packets"][0]["connection_id"]
    result.begin_epoch(epoch)
    offset = 0
    for proof in data["proofs"]:
        assert result.observe(offset, proof["samples"], proof)
        offset += proof["samples"]
    return result, epoch


def test_recorded_native_ranges_wait_for_metadata_and_preserve_fractional_clock_envelope():
    """At sample320 the resampler reaches the same point through two adjacent RTP packets."""
    data, now = recorded(), [0.0]
    source, epoch = ledger(now, data)
    assert source.locate_sample(320) is None
    assert source.add_records(epoch, data["records"])
    point = source.locate_sample(320)
    assert point is not None
    assert (point.lower_frame, point.upper_frame) == (3536, 3536)
    assert len(point.proofs) >= 2
    fractional = copy.deepcopy(data)
    for row in fractional["records"]:
        row["capture_time_ms"] += 0.013
    source, epoch = ledger(now, fractional)
    assert source.add_records(epoch, fractional["records"])
    point = source.locate_sample(321)
    assert point.lower_frame < point.upper_frame
    assert (point.lower_frame, point.upper_frame) == (3537, 3538)


def test_epoch_hash_conflict_and_expiration_never_fill_unknown_or_retarget_a_packet():
    """A delayed valid-looking packet cannot overwrite source identity or an old epoch."""
    data, now = recorded(), [0.0]
    source, epoch = ledger(now, data)
    wrong = copy.deepcopy(data["records"])
    for row in wrong:
        row["payload_sha256"] = "0" * 64
    assert source.add_records(epoch, wrong)
    assert source.locate_sample(320) is None
    assert source.add_records(epoch, data["records"])
    assert source.locate_sample(320) is not None
    changed = copy.deepcopy(data["records"])
    for row in changed:
        row["clock_id"] = "b" * 32
    assert not source.add_records(epoch, changed)
    assert source.locate_sample(320).clock_id == data["records"][0]["clock_id"]
    source.begin_epoch("c" * 32)
    assert not source.add_records(epoch, data["records"])
    assert source.locate_sample(320) is None
    source, epoch = ledger(now, data)
    assert source.add_records(epoch, data["records"])
    now[0] = 2001
    assert source.locate_sample(320) is None
    assert source.add_records(epoch, data["records"])
    assert source.locate_sample(320) is None


def test_rtp_source_boundary_freezes_before_maximum_wait_and_joins_only_render_facts(monkeypatch):
    """Old source anchors may expire after commit; their sealed evidence must stay immutable."""
    from pipecat.frames.frames import InputAudioRawFrame

    from src.history.capture import CallCapture

    now, data = [0.0], recorded()
    monkeypatch.setattr(CallCapture, "elapsed_ms", lambda self: now[0])
    capture = CallCapture(provider="fixture", model="fixture")
    epoch = data["proofs"][0]["packets"][0]["connection_id"]
    capture.rtp_source.begin_epoch(epoch)
    for proof in data["proofs"]:
        frame = InputAudioRawFrame(bytes(proof["samples"] * 2), 16000, 1)
        frame.metadata["td_rtp_input"] = proof
        capture.observe(frame)
    assert capture.accept_rtp_packet_records(epoch, data["records"])
    clock = data["records"][0]["clock_id"]
    before = capture.capture_clock.issue(clock, 16000)
    now[0] = 10
    assert capture.ack_capture_clock(before, clock, 16000, 3000)
    capture.record_td_event(
        {"event": "candidate_created", "turn_id": 1, "speech_end_audio_ms": 31.25}
    )
    now[0] = 100
    after = capture.capture_clock.issue(clock, 16000)
    now[0] = 110
    assert capture.ack_capture_clock(after, clock, 16000, 5000)
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
    event = next(x for x in capture.td_events if x["event"] == "e2e_timing_bounds")
    assert event["e2e_range"]["lower_ms"] == 4890
    assert event["e2e_range"]["upper_ms"] == 5110
    assert event["source_coordinates"]["first_frame"] == 3716
    assert event["source_coordinates"]["coordinate_kind"] == "browser_reported_rtp_capture_time"
    assert event["source_coordinates"]["mapping_spans"][0]["payload_sha256"]
