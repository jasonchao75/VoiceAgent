"""Focused tests for reasoning-model connectivity diagnostics."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from src.llm.diagnostics import (
    DiagnosticConfig,
    _diagnose_gemini,
    _diagnose_openai,
    _diagnose_qwen_dashscope,
    classify_llm_failure,
)


class _AsyncChunks:
    def __init__(self, chunks: list[Any]) -> None:
        self._chunks = chunks

    def __aiter__(self) -> _AsyncChunks:
        self._iterator = iter(self._chunks)
        return self

    async def __anext__(self) -> Any:
        try:
            return next(self._iterator)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


@pytest.mark.asyncio
async def test_gemini_diagnostic_accepts_reasoning_only_response_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A reachable reasoning model must not fail only because visible text is empty."""
    observed: dict[str, Any] = {}

    class Models:
        async def generate_content_stream(self, **kwargs: Any) -> _AsyncChunks:
            observed.update(kwargs)
            usage = SimpleNamespace(thoughts_token_count=12)
            return _AsyncChunks([SimpleNamespace(text=None, usage_metadata=usage)])

    class AsyncClient:
        def __init__(self) -> None:
            self.models = Models()

        async def aclose(self) -> None:
            return None

    class Client:
        def __init__(self, **_kwargs: Any) -> None:
            self.aio = AsyncClient()

    monkeypatch.setattr("src.llm.diagnostics.genai.Client", Client)
    first_ms, _total_ms, reasoning_tokens = await _diagnose_gemini(
        DiagnosticConfig(
            provider="google_gemini",
            base_url="https://generativelanguage.googleapis.com",
            model="gemini-3.8-flash",
            api_key="test-gemini-key",
        )
    )

    assert first_ms is None
    assert reasoning_tokens == 12
    assert observed["config"].max_output_tokens == 256


@pytest.mark.asyncio
async def test_openai_compatible_diagnostic_accepts_reasoning_only_response_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Qwen-style streams may prove access before emitting a visible answer token."""
    observed: dict[str, Any] = {}

    class Completions:
        async def create(self, **kwargs: Any) -> _AsyncChunks:
            observed.update(kwargs)
            usage = SimpleNamespace(completion_tokens_details=SimpleNamespace(reasoning_tokens=20))
            return _AsyncChunks([SimpleNamespace(choices=[], usage=usage)])

    class Client:
        def __init__(self, **kwargs: Any) -> None:
            observed["client"] = kwargs
            self.chat = SimpleNamespace(completions=Completions())

        async def close(self) -> None:
            return None

    monkeypatch.setattr("src.llm.diagnostics.AsyncOpenAI", Client)
    first_ms, _total_ms, reasoning_tokens = await _diagnose_openai(
        DiagnosticConfig(
            provider="qwen",
            base_url="https://example.invalid/v1",
            model="qwen3.8-max",
            api_key="test-qwen-key",
        )
    )

    assert first_ms is None
    assert reasoning_tokens == 20
    assert observed["max_completion_tokens"] == 256
    assert observed["client"]["max_retries"] == 0


@pytest.mark.parametrize(
    ("status", "category"),
    [
        (400, "invalid_configuration"),
        (401, "authentication_failed"),
        (404, "model_unavailable"),
        (429, "rate_limited"),
    ],
)
def test_native_http_status_errors_keep_actionable_categories(
    status: int,
    category: str,
) -> None:
    """Native httpx failures must preserve safe status-based diagnostics."""
    request = httpx.Request("POST", "https://dashscope.aliyuncs.com/api/v1")
    response = httpx.Response(status, request=request)
    failure = httpx.HTTPStatusError("upstream error", request=request, response=response)

    assert classify_llm_failure(failure)[0] == category


@pytest.mark.asyncio
async def test_native_qwen_diagnostic_uses_total_cap_without_fake_first_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A synchronous native response proves connectivity but not first-token latency."""
    observed: dict[str, Any] = {}

    class Client:
        def __init__(self, **kwargs: Any) -> None:
            observed["client"] = kwargs

        async def __aenter__(self) -> Client:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def post(self, url: str, **kwargs: Any) -> httpx.Response:
            observed.update(url=url, **kwargs)
            request = httpx.Request("POST", url)
            return httpx.Response(
                200,
                request=request,
                json={
                    "output": {"choices": [{"message": {"content": [{"text": "OK"}]}}]},
                    "usage": {"input_tokens": 8, "output_tokens": 1},
                },
            )

    monkeypatch.setattr("src.llm.diagnostics.httpx.AsyncClient", Client)
    first_ms, total_ms, reasoning_tokens = await _diagnose_qwen_dashscope(
        DiagnosticConfig(
            provider="custom",
            base_url="https://dashscope.aliyuncs.com/api/v1",
            model="qwen3.8-max",
            api_key="test-qwen-key",
        )
    )

    assert first_ms is None
    assert total_ms >= 0
    assert reasoning_tokens is None
    assert observed["url"].endswith("/multimodal-generation/generation")
    assert observed["json"]["parameters"]["max_completion_tokens"] == 256
