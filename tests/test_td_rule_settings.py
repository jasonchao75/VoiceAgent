"""M1/M3: frozen explicit priority settings survive Bot and session snapshots."""

import pytest
from pydantic import ValidationError

from src.asr.td_config import CustomTDSettings
from tests.test_td_config import td_settings


def priority_settings():
    """Fixture choices are explicit inputs, not calibrated deployment defaults."""
    return {
        "enabled": True,
        "keywords": ["编号", "account number"],
        "vocabulary": [
            {"value": "1", "aliases": ["1", "one", "一"]},
            {"value": "2", "aliases": ["2", "two", "二"]},
            {"value": "3", "aliases": ["3", "three", "三"]},
        ],
        "wpm_threshold": 90,
        "pause_ms": 350,
        "unit_gap_ms": 50,
        "collection": {
            "target_length": 3,
            "timeout_ms": 8000,
            "overflow_pause_ms": 350,
            "incomplete_text": "请继续念完整编号",
            "overflow_text": "编号位数超过目标，请确认",
        },
    }


def test_explicit_priority_settings_are_frozen_and_serializable():
    value = CustomTDSettings.model_validate({**td_settings(), "priority_rule": priority_settings()})
    assert value.priority_rule.collection.target_length == 3
    restored = CustomTDSettings.model_validate_json(value.model_dump_json())
    assert restored.priority_rule == value.priority_rule
    with pytest.raises(ValidationError):
        value.priority_rule.pause_ms = 5


@pytest.mark.parametrize(
    "field", ["keywords", "vocabulary", "wpm_threshold", "pause_ms", "unit_gap_ms"]
)
def test_enabled_priority_rule_does_not_invent_missing_required_fields(field):
    rule = priority_settings()
    del rule[field]
    with pytest.raises(ValidationError):
        CustomTDSettings.model_validate({**td_settings(), "priority_rule": rule})


def test_disabled_rule_keeps_draft_and_aliases_cannot_be_ambiguous():
    rule = priority_settings()
    rule["enabled"] = False
    value = CustomTDSettings.model_validate({**td_settings(), "priority_rule": rule})
    assert value.priority_rule.keywords == ("编号", "account number")
    rule["vocabulary"][1]["aliases"].append("ONE")
    with pytest.raises(ValidationError):
        CustomTDSettings.model_validate({**td_settings(), "priority_rule": rule})
