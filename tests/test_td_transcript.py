"""Deterministic source-range scenarios from ASR-01 and ASR-03."""

from importlib import import_module, util

import pytest


def ledger_types():
    """Require the production transcript boundary, rather than a test-only model."""
    assert util.find_spec("src.asr.transcript") is not None, "TD source range ledger is absent"
    module = import_module("src.asr.transcript")
    return module.TranscriptLedger, module.SourceSegment, module.TimedWord


def test_partial_replaces_and_late_final_preserves_tail():
    """An older final cannot finalize or erase newer speech."""
    Ledger, Segment, _ = ledger_types()
    ledger = Ledger()
    ledger.apply(Segment(0, "a", 1, 0, 1000, "1", False))
    ledger.apply(Segment(0, "a", 2, 0, 1000, "123", False))
    ledger.apply(Segment(0, "b", 1, 1000, 2000, "45", False))
    ledger.apply(Segment(0, "a", 3, 0, 1000, "123", True))
    assert ledger.view().text == "12345"
    assert ledger.view().final is False
    ledger.apply(Segment(0, "b", 2, 1000, 2000, "456", True))
    assert ledger.view().text == "123456"
    assert ledger.view().final is True


def test_duplicate_out_of_order_and_reconnect():
    """Revision identity and connection identity prevent stale writes."""
    Ledger, Segment, _ = ledger_types()
    ledger = Ledger()
    assert ledger.apply(Segment(0, "a", 2, 0, 500, "12", True))
    assert not ledger.apply(Segment(0, "a", 2, 0, 500, "12", True))
    assert not ledger.apply(Segment(0, "a", 1, 0, 500, "1", False))
    ledger.reconnect()
    assert not ledger.apply(Segment(0, "a", 99, 0, 500, "old", True))
    ledger.apply(Segment(1, "a", 1, 0, 500, "12", False))
    assert ledger.view().text == "1212"
    assert not ledger.view().final


def test_provider_turn_crosses_td_commit_without_repeating_prefix():
    """Consumed audio is excluded using word positions, never string prefix guesses."""
    Ledger, Segment, Word = ledger_types()
    ledger = Ledger()
    words = (Word("12", 0, 500),)
    ledger.apply(Segment(0, "a", 1, 0, 500, "12", False, words))
    snapshot = ledger.consume()
    assert snapshot.text == "12"
    ledger.apply(Segment(0, "a", 2, 0, 1000, "1212", False, words + (Word("12", 600, 1000),)))
    assert ledger.view().text == "12"
    assert ledger.consume().text == "12"
    assert ledger.view().text == ""


def test_unknown_cross_commit_range_is_explicitly_unavailable():
    """No word timing means a crossing snapshot cannot safely be split."""
    Ledger, Segment, _ = ledger_types()
    ledger = Ledger()
    ledger.apply(Segment(0, "a", 1, 0, 500, "12", False))
    ledger.consume()
    ledger.apply(Segment(0, "a", 2, 0, 1000, "1234", False))
    assert ledger.view().text == ""
    assert ledger.view().missing_reason == "cross_commit_word_timing_unavailable"


def test_real_repetition_and_formatting_revision():
    """Different audio with identical text remains distinct; formatting replaces."""
    Ledger, Segment, _ = ledger_types()
    ledger = Ledger()
    ledger.apply(Segment(0, "a", 1, 0, 500, "12", True))
    ledger.apply(Segment(0, "b", 1, 500, 1000, "12", True))
    ledger.apply(Segment(0, "a", 2, 0, 500, "12,", True))
    assert ledger.view().text == "12,12"


def test_invalid_audio_range_is_rejected():
    """Malformed timing cannot become speed evidence."""
    _, Segment, Word = ledger_types()
    with pytest.raises(ValueError):
        Segment(0, "a", 1, 900, 500, "12", False)
    with pytest.raises(ValueError):
        Word("1", float("nan"), 10)


def test_final_for_second_commit_never_restores_first_commit_prefix():
    """One provider source may span two TD submissions; Final resolves each exact extent."""
    from src.asr.transcript import SourceSegment, TimedWord, TranscriptLedger

    ledger = TranscriptLedger()
    ledger.apply(SourceSegment(0, "a", 1, 0, 1000, "12", False))
    first = ledger.consume()
    words = (
        TimedWord("1", 0, 500),
        TimedWord("2", 500, 1000),
        TimedWord("3", 1000, 1500),
        TimedWord("4", 1500, 2000),
    )
    ledger.apply(SourceSegment(0, "a", 2, 0, 2000, "1234", False, words))
    second = ledger.consume()
    assert second.text == "34"
    ledger.apply(SourceSegment(0, "a", 3, 0, 2000, "1234", True, words))
    assert ledger.resolve_snapshot(first).text == "12"
    assert ledger.resolve_snapshot(second).text == "34"
    assert second.segments[0].start_ms == 1000
    assert ledger.view().text == ""


def test_resolved_final_preserves_submitted_extent_as_well_as_text():
    """Tool/source consumers must not receive the provider's larger extent as authority."""
    from src.asr.transcript import SourceSegment, TimedWord, TranscriptLedger

    ledger = TranscriptLedger()
    ledger.apply(SourceSegment(0, "a", 1, 0, 1000, "1", False))
    committed = ledger.consume()
    ledger.apply(
        SourceSegment(
            0, "a", 2, 0, 2000, "12", True, (TimedWord("1", 0, 1000), TimedWord("2", 1000, 2000))
        )
    )
    resolved = ledger.resolve_snapshot(committed)
    assert resolved.text == "1"
    assert resolved.segments[0].end_ms == 1000
    assert resolved.segments[0].text == "1"


def test_final_word_crossing_owned_boundary_does_not_silently_shorten_input():
    """Reject a word straddling ownership even when other words fit the old extent."""
    TranscriptLedger, SourceSegment, TimedWord = ledger_types()
    ledger = TranscriptLedger()
    ledger.apply(SourceSegment(0, "a", 1, 0, 1000, "12", False))
    committed = ledger.consume()
    ledger.apply(
        SourceSegment(
            0,
            "a",
            2,
            0,
            2000,
            "123",
            True,
            (TimedWord("1", 0, 500), TimedWord("2", 500, 1500), TimedWord("3", 1500, 2000)),
        )
    )
    assert ledger.resolve_snapshot(committed) is None


def test_cross_commit_partial_word_coverage_cannot_silently_erase_a_word():
    from src.asr.transcript import SourceSegment, TimedWord, TranscriptLedger

    ledger = TranscriptLedger()
    ledger.apply(SourceSegment(0, "a", 1, 0, 100, "1", False, (TimedWord("1", 0, 100),)))
    ledger.consume()
    ledger.apply(
        SourceSegment(
            0, "a", 2, 0, 300, "123", False, (TimedWord("1", 0, 100), TimedWord("3", 200, 300))
        )
    )
    view = ledger.view()
    assert view.text == ""
    assert view.missing_reason == "cross_commit_word_timing_incomplete"


def test_sample_equivalent_consumed_edge_keeps_final_prefix_and_new_tail_separate():
    """The D-062 boundary must not duplicate an old word or erase its new tail."""
    from dataclasses import replace

    from src.asr.transcript import SourceSegment, TimedWord, TranscriptLedger

    ledger = TranscriptLedger()
    old = SourceSegment(
        0,
        "stream-source",
        1,
        0,
        2639.9999,
        "one",
        False,
        (TimedWord("one", 0, 2640),),
        sample_rate=16000,
    )
    ledger.apply(old)
    submitted = ledger.consume()
    updated = replace(
        old,
        revision=2,
        end_ms=2800,
        text="one six",
        final=True,
        words=(TimedWord("one", 0, 2640), TimedWord("six", 2640, 2800)),
    )
    ledger.apply(updated)
    assert ledger.view().text == "six"
    assert ledger.view().missing_reason is None
    resolved = ledger.resolve_snapshot(submitted)
    assert resolved is not None and resolved.text == "one"
    assert resolved.segments[0].end_ms == 2639.9999
    # A word genuinely crossing that PCM boundary remains unsplittable.
    ledger.apply(
        replace(
            updated, revision=3, words=(TimedWord("one", 0, 2700), TimedWord("six", 2700, 2800))
        )
    )
    assert ledger.view().missing_reason == "cross_commit_word_overlaps_boundary"
    assert ledger.resolve_snapshot(submitted) is None


@pytest.mark.parametrize(
    ("parts", "expected"),
    [
        (["one", "two"], "one two"),
        (["one ", "two"], "one two"),
        (["one", " two"], "one two"),
        (["一", "二"], "一二"),
        (["12", "34"], "1234"),
        (["hello,", "world"], "hello, world"),
    ],
)
def test_segment_join_preserves_word_boundaries_without_rewriting_spacing(parts, expected):
    """Independent word segments need boundaries; digits and unspaced scripts do not."""
    Ledger, Segment, _ = ledger_types()
    ledger = Ledger()
    for index, text in enumerate(parts):
        ledger.apply(Segment(0, str(index), 1, index * 1000, (index + 1) * 1000, text, True))
    assert ledger.view().text == expected
    assert ledger.resolve_snapshot(ledger.view()).text == expected


def test_soniox_subword_segments_keep_provider_token_spacing():
    """A subword token is not an independent word; only the provider inserts its spaces."""
    from src.asr.turn_events import SourceNormalizer

    ledger = ledger_types()[0]()
    normalizer = SourceNormalizer("soniox", "stt-rt-v5", sample_rate=16000)
    for segment in normalizer.normalize(
        {
            "tokens": [
                {"text": text, "start_ms": i * 100, "end_ms": (i + 1) * 100, "is_final": True}
                for i, text in enumerate(["hel", "lo", " world"])
            ]
        }
    ):
        ledger.apply(segment)
    assert ledger.view().text == "hello world"


def test_cross_commit_and_final_slice_keep_original_english_word_spacing():
    """Timed word selection must use the original covered text instead of concatenating words."""
    Ledger, Segment, Word = ledger_types()
    ledger = Ledger()
    ledger.apply(Segment(0, "a", 1, 0, 1000, "one two", False))
    first = ledger.consume()
    words = tuple(
        Word(text, index * 500, (index + 1) * 500)
        for index, text in enumerate(["one", "two", "three", "four"])
    )
    ledger.apply(Segment(0, "a", 2, 0, 2000, "one two three four", True, words))
    assert ledger.view().text == "three four"
    assert ledger.resolve_snapshot(first).text == "one two"
