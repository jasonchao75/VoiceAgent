"""Native Qwen DashScope request and response contract tests."""

from __future__ import annotations

import pytest

from src.llm.qwen_dashscope import (
    is_native_dashscope_url,
    native_dashscope_generation_url,
    native_dashscope_request,
    parse_native_dashscope_response,
    validate_qwen_base_url,
)


def test_prem_native_endpoint_is_supported_for_qwen38() -> None:
    """The user's China-premium native endpoint must route Qwen 3.8 correctly."""
    base_url = validate_qwen_base_url("https://prem.dashscope.aliyuncs.com/api/v1/")

    assert base_url == "https://prem.dashscope.aliyuncs.com/api/v1"
    assert is_native_dashscope_url(base_url) is True
    assert native_dashscope_generation_url(base_url, "qwen3.8-max") == (
        "https://prem.dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
    )

    shared_base_url = validate_qwen_base_url("https://dashscope.aliyuncs.com/api/v1")
    assert is_native_dashscope_url(shared_base_url) is True
    assert native_dashscope_generation_url(shared_base_url, "qwen3.8-max") == (
        "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
    )


def test_qwen_endpoint_rejects_untrusted_hosts_and_paths() -> None:
    """Editable Qwen URLs must not turn the backend into an arbitrary proxy."""
    with pytest.raises(ValueError, match="approved HTTPS DashScope host"):
        validate_qwen_base_url("https://example.com/api/v1")
    with pytest.raises(ValueError, match="must end"):
        validate_qwen_base_url("https://prem.dashscope.aliyuncs.com/other")


def test_native_qwen_request_supports_thinking_and_parses_usage() -> None:
    """Native execution must preserve Thinking and structured text accounting."""
    request = native_dashscope_request(
        model="qwen3.8-max",
        system_prompt="Return JSON.",
        user_message='{"value":1}',
        max_output_tokens=4096,
        enable_thinking=True,
        reasoning_effort="medium",
        structured_json=True,
    )

    assert request["parameters"] == {
        "result_format": "message",
        "max_completion_tokens": 4096,
        "enable_thinking": True,
        "reasoning_effort": "medium",
        "response_format": {"type": "json_object"},
    }
    text, usage = parse_native_dashscope_response(
        {
            "output": {"choices": [{"message": {"content": [{"text": '{"ok":true}'}]}}]},
            "usage": {
                "input_tokens": 12,
                "output_tokens": 34,
                "prompt_tokens_details": {"cached_tokens": 5},
                "output_tokens_details": {"reasoning_tokens": 20},
            },
        }
    )
    assert text == '{"ok":true}'
    assert usage == {
        "input_tokens": 12,
        "cached_input_tokens": 5,
        "output_tokens": 34,
        "reasoning_tokens": 20,
    }


def test_native_qwen_request_accepts_strict_response_schema() -> None:
    """A call-specific JSON Schema must replace generic JSON Object mode."""
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "choice",
            "strict": True,
            "schema": {"type": "object", "additionalProperties": False},
        },
    }

    request = native_dashscope_request(
        model="qwen3.8-max",
        system_prompt="Choose one legal value.",
        user_message="{}",
        max_output_tokens=256,
        enable_thinking=False,
        structured_json=True,
        response_format=response_format,
    )

    assert request["parameters"]["response_format"] == response_format


def test_native_qwen38_caps_total_output_for_both_passes() -> None:
    """Qwen 3.8 must cap combined reasoning and answer tokens in every pass."""
    for thinking in (False, True):
        request = native_dashscope_request(
            model="qwen3.8-max",
            system_prompt="Return JSON.",
            user_message="{}",
            max_output_tokens=256,
            enable_thinking=thinking,
            structured_json=True,
        )
        assert request["parameters"]["max_completion_tokens"] == 256
        assert "max_tokens" not in request["parameters"]
        assert request["parameters"]["enable_thinking"] is thinking
        assert request["parameters"]["response_format"] == {"type": "json_object"}

    legacy = native_dashscope_request(
        model="qwen-plus",
        system_prompt="Return JSON.",
        user_message="{}",
        max_output_tokens=256,
        enable_thinking=False,
    )
    assert legacy["parameters"]["max_tokens"] == 256
    assert "max_completion_tokens" not in legacy["parameters"]
