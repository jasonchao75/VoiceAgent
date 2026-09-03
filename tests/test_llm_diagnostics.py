"""LLM diagnostic classification and reasoning capability tests."""

from __future__ import annotations

import pytest

from src.llm.capabilities import get_model_capability
from src.llm.diagnostics import classify_llm_failure, extract_error_meta


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


class FakeSdkError(Exception):
    """Mimics an OpenAI-style provider error."""

    def __init__(self) -> None:
        super().__init__("bad request")
        self.status_code = 500
        self.code = "internal_error"


class FakeResponseError(Exception):
    """Mimics errors where metadata lives on a nested response object."""

    class Response:
        status_code = 400
        code = "invalid_model"

    def __init__(self) -> None:
        super().__init__("nope")
        self.response = self.Response()


def test_extract_error_meta_reads_status_and_codes() -> None:
    """Safe metadata is pulled from common SDK shapes without exposing bodies."""
    status, error_type, provider_code = extract_error_meta(FakeSdkError())
    assert status == 500
    assert error_type == "FakeSdkError"
    assert provider_code == "internal_error"


def test_extract_error_meta_falls_back_to_response_object() -> None:
    """Nested response attributes are used when top-level code is absent."""
    status, error_type, provider_code = extract_error_meta(FakeResponseError())
    assert status == 400
    assert error_type == "FakeResponseError"
    assert provider_code == "invalid_model"


def test_extract_error_meta_handles_plain_exceptions() -> None:
    """Plain exceptions return the type name and no status or provider code."""
    status, error_type, provider_code = extract_error_meta(RuntimeError("boom"))
    assert status is None
    assert error_type == "RuntimeError"
    assert provider_code is None
