"""LLM diagnostic classification and reasoning capability tests."""

from __future__ import annotations

import pytest

from src.llm.capabilities import get_model_capability
from src.llm.diagnostics import classify_llm_failure


@pytest.mark.parametrize(
    ("error", "category"),
    [
        (TimeoutError(), "timeout"),
        (ConnectionError(), "connection_failed"),
        (RuntimeError(), "upstream_error"),
    ],
)
def test_safe_failure_categories(error: Exception, category: str) -> None:
    """Arbitrary exception details should collapse into bounded categories."""
    actual, summary, suggestion = classify_llm_failure(error)
    assert actual == category
    assert summary
    assert suggestion


def test_gemini_low_latency_profiles_are_explicit() -> None:
    """Gemini 2.5 disables thinking while 3.x uses its documented minimum."""
    two_five = get_model_capability("google_gemini", "gemini-2.5-flash-lite")
    three = get_model_capability("google_gemini", "gemini-3.6-flash")
    assert two_five is not None
    assert (two_five.control_name, two_five.control_value) == ("thinking_budget", 0)
    assert two_five.expected_status == "confirmed_off"
    assert three is not None
    assert (three.control_name, three.control_value) == ("thinking_level", "minimal")
    assert three.expected_status == "minimized"
    assert get_model_capability("custom", "unknown") is None
