"""Production regressions promoted from independent r87 review (B1/B2/D-080)."""

from src.asr.transcript import TranscriptLedger
from src.asr.turn_events import SourceNormalizer
from src.pipeline.identifier import IdentifierVocabulary
from src.pipeline.turn_detection import TurnClock, WaitPolicy


def test_distinct_english_segments_preserve_identifier_word_boundaries():
    """Two provider segments must not turn two valid words into one unknown word."""
    normalizer = SourceNormalizer("deepgram", "nova-3", sample_rate=16000)
    ledger = TranscriptLedger()
    for index, text in enumerate(("one", "two")):
        payload = {
            "start": index,
            "duration": 1,
            "is_final": True,
            "channel": {
                "alternatives": [
                    {
                        "transcript": text,
                        "words": [{"word": text, "start": index, "end": index + 1}],
                    }
                ]
            },
        }
        for segment in normalizer.normalize(payload):
            ledger.apply(segment)
    vocabulary = IdentifierVocabulary({"1": ["one"], "2": ["two"]})
    assert vocabulary.normalize(ledger.view().text) == "12", ledger.view().text


def test_partial_word_coverage_cannot_resolve_a_final_extent():
    """Missing timed words must not silently remove a negation from a Final."""
    ledger = TranscriptLedger()
    normalizer = SourceNormalizer("deepgram", "nova-3", sample_rate=16000)
    for segment in normalizer.normalize(
        {
            "start": 0,
            "duration": 1,
            "is_final": False,
            "channel": {"alternatives": [{"transcript": "I agree"}]},
        }
    ):
        ledger.apply(segment)
    original = ledger.consume()
    for segment in normalizer.normalize(
        {
            "start": 0,
            "duration": 2,
            "is_final": True,
            "channel": {
                "alternatives": [
                    {
                        "transcript": "I do not agree now",
                        "words": [
                            {"word": "I", "start": 0, "end": 0.1},
                            {"word": "do"},
                            {"word": "not"},
                            {"word": "agree", "start": 0.4, "end": 0.9},
                            {"word": "now", "start": 1.1, "end": 1.5},
                        ],
                    }
                ]
            },
        }
    ):
        ledger.apply(segment)
    assert normalizer.missing_reason is None
    assert ledger.resolve_snapshot(original) is None


def test_revised_semantic_target_is_not_bypassed_by_old_final_window():
    """An active old Final window cannot authorize an earlier revised-text commit."""
    clock = TurnClock(WaitPolicy(600, 2500, 200, 0.5, 0.8))
    token = clock.pause(0)
    clock.transcript(token, "done", final=False)
    clock.semantic(token, 600, text_revision=clock.text_revision)
    assert clock.poll(600) is None
    clock.transcript(token, "actually I also want", final=False)
    clock.semantic(token, 2000, text_revision=clock.text_revision)
    assert clock.poll(800) is None
