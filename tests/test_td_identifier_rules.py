"""NUM-01/02: strict priority routing and business WPM from actual word intervals."""

from importlib import import_module, util

import pytest

from src.asr.td_config import IdentifierRuleSettings
from src.asr.transcript import SourceSegment, TimedWord, TranscriptView
from tests.test_td_identifier import collection
from tests.test_td_rule_settings import priority_settings


def policy():
    assert util.find_spec("src.pipeline.identifier_rules") is not None, "Priority runtime absent"
    return import_module("src.pipeline.identifier_rules").IdentifierRules(
        IdentifierRuleSettings.model_validate(priority_settings()), collection()
    )


def snapshot(text, *, words=(), final=True, source="a"):
    return TranscriptView(text, final, (SourceSegment(0, source, 1, 0, 3000, text, final, words),))


def test_keyword_gate_and_full_input_format_are_required_before_collection():
    rules = policy()
    assert rules.evaluate(snapshot("12"), "请确认").path == "ordinary"
    assert rules.collection.value == ""
    assert rules.evaluate(snapshot("one moment"), "请提供编号").path == "ordinary"
    assert rules.collection.value == ""
    assert rules.evaluate(snapshot("号码123"), "请提供编号").path == "ordinary"
    assert rules.collection.value == ""


def test_business_units_ignore_asr_token_count_and_window_trailing_silence():
    rules = policy()
    # One ASR token contains two digits: 2 units in 1 second, not 1 token / 3s window.
    evaluated = rules.evaluate(snapshot("12", words=(TimedWord("12", 0, 1000),)), "请提供编号")
    assert evaluated.units == 2 and evaluated.wpm == 120
    assert evaluated.path == "incomplete" and not evaluated.echo_eligible
    assert rules.collection.value == "12"


def test_slow_single_unit_and_unknown_timing_still_collect_without_fake_wpm():
    rules = policy()
    slow = rules.evaluate(snapshot("1", words=(TimedWord("1", 0, 2000),)), "编号")
    assert slow.units == 1 and slow.wpm == 30 and slow.echo_eligible
    unknown = rules.evaluate(snapshot("12"), "编号")
    assert unknown.wpm is None and not unknown.echo_eligible
    assert unknown.timing_reason == "word_timing_unavailable"
    assert rules.collection.value == "12"


def test_partial_mixed_revision_withdraws_local_value_without_extracting_digits():
    rules = policy()
    rules.evaluate(snapshot("12", final=False), "编号")
    mixed = TranscriptView(
        "123，嗯，12", False, (SourceSegment(0, "a", 2, 0, 3000, "123，嗯，12", False),)
    )
    assert rules.evaluate(mixed, "编号").path == "ordinary"
    assert rules.collection.value == ""


@pytest.mark.parametrize("text,expected", [("hello", 1), ("你好", 2), ("1234", 4)])
def test_business_unit_definition_is_independent_of_provider_tokens(text, expected):
    """Use the exact Delta examples without expanding the strict identifier vocabulary."""
    module = import_module("src.pipeline.identifier_rules")
    assert module.business_units(text) == expected


def test_retained_revision_cannot_consume_new_collection_permission():
    """Only actual new input may use the success captured at speech start."""
    from dataclasses import replace

    rules = policy()
    original = snapshot("123")
    rules.evaluate(original, "编号")
    rules.committed()
    assert rules.collection.successful
    rules.begin_input()
    revised = TranscriptView("321", True, (replace(original.segments[0], revision=2, text="321"),))
    rules.evaluate(revised, "编号", allow_new_collection=False)
    assert rules.collection.value == "321" and rules.collection.generation == 0
    assert rules.can_begin_collection()
