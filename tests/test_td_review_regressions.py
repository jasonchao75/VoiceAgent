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


def test_local_source_can_expand_but_a_real_submission_restores_the_strict_fence():
    """Local source ownership must never weaken the ordinary LLM boundary contract."""
    normalizer = SourceNormalizer("deepgram", "nova-3", sample_rate=16000)
    ledger = TranscriptLedger()

    def apply(text, duration):
        """Feed a single whole-word snapshot with explicit provider timing."""
        for segment in normalizer.normalize(
            {
                "start": 0,
                "duration": duration,
                "is_final": False,
                "channel": {
                    "alternatives": [
                        {"transcript": text, "words": [{"word": text, "start": 0, "end": duration}]}
                    ]
                },
            }
        ):
            ledger.apply(segment)

    apply("12", 1)
    first = ledger.consume_local()
    apply("123", 2)
    expanded = ledger.resolve_snapshot(first, require_final=False, expand_local=True)
    assert expanded.text == "123"
    assert ledger.view().missing_reason is None and ledger.view().text == ""
    ledger.freeze_submission(expanded)
    apply("1234", 3)
    assert ledger.view().missing_reason == "cross_commit_word_overlaps_boundary"
    assert ledger.resolve_snapshot(expanded, require_final=False, expand_local=True) is None
