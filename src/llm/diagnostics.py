"""Safe, user-visible LLM connectivity diagnostics."""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from google import genai
from google.genai import types
from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from src.llm.capabilities import ReasoningStatus, get_model_capability


class LLMDiagnosticRequest(BaseModel):
    """One explicit, potentially billable LLM connectivity check."""

    model_config = ConfigDict(extra="forbid")

    bot_id: str | None = Field(default=None, max_length=100)
    llm_provider: str | None = Field(default=None, max_length=50)
    llm_base_url: str | None = Field(default=None, max_length=500)
    llm_model: str | None = Field(default=None, max_length=200)
    llm_api_key: SecretStr | None = Field(default=None, min_length=8, max_length=500)


class LLMDiagnosticResult(BaseModel):
    """Public diagnostic result with no credentials or upstream body."""

    diagnostic_id: str
    success: bool
    category: str
    summary: str
    suggestion: str
    provider: str
    base_url_host: str
    model: str
    first_token_ms: float | None = None
    total_ms: float
    reasoning_control: str | None = None
    reasoning_tokens: int | None = None
    reasoning_status: ReasoningStatus


@dataclass(frozen=True, slots=True)
class DiagnosticConfig:
    """Resolved secret and non-secret settings for one diagnostic call."""

    provider: str
    base_url: str
    model: str
    api_key: str
    timeout: float = 15.0


def classify_llm_failure(exc: Exception) -> tuple[str, str, str]:
    """Map arbitrary SDK failures onto a bounded, actionable taxonomy."""
    status = getattr(exc, "status_code", None)
    name = type(exc).__name__.lower()
    if status in {401, 403} or "authentication" in name or "permission" in name:
        return (
            "authentication_failed",
            "The provider rejected this API key.",
            "Check the key and model access.",
        )
    if status == 404 or "notfound" in name:
        return (
            "model_unavailable",
            "The configured model was not found.",
            "Check the exact model ID and account access.",
        )
    if status == 429 or "ratelimit" in name or "resourceexhausted" in name:
        return (
            "rate_limited",
            "The provider rate-limited the request.",
            "Check quota or retry later.",
        )
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)) or "timeout" in name:
        return (
            "timeout",
            "The provider did not respond before the timeout.",
            "Retry or choose a faster model.",
        )
    if "connection" in name or "connect" in name or "ssl" in name or "dns" in name:
        return (
            "connection_failed",
            "The server could not connect to the provider.",
            "Check the endpoint and provider status.",
        )
    if status == 400:
        return (
            "invalid_configuration",
            "The provider rejected the model parameters.",
            "Check the model and reasoning settings.",
        )
    return (
        "upstream_error",
        "The provider returned an unexpected error.",
        "Use the diagnostic ID to correlate server logs.",
    )


def _reasoning_result(
    *, provider: str, model: str, reasoning_tokens: int | None
) -> tuple[str | None, ReasoningStatus]:
    capability = get_model_capability(provider, model)
    if capability is None:
        return None, "unverified"
    control = (
        f"{capability.control_name}={capability.control_value}" if capability.control_name else None
    )
    if reasoning_tokens is not None and reasoning_tokens > 0:
        return control, "detected"
    if capability.expected_status == "confirmed_off" and reasoning_tokens is None:
        return control, "unverified"
    return control, capability.expected_status


async def _diagnose_openai(config: DiagnosticConfig) -> tuple[float, float, int | None]:
    capability = get_model_capability(config.provider, config.model)
    extra: dict[str, object] = {}
    if capability and capability.control_name == "reasoning_effort":
        extra["reasoning_effort"] = capability.control_value
    client = AsyncOpenAI(api_key=config.api_key, base_url=config.base_url.rstrip("/") + "/")
    started = time.monotonic()
    first_token: float | None = None
    reasoning_tokens: int | None = None
    try:
        async with asyncio.timeout(config.timeout):
            stream = await client.chat.completions.create(
                model=config.model,
                messages=[{"role": "user", "content": "Reply with OK."}],
                max_completion_tokens=8,
                stream=True,
                stream_options={"include_usage": True},
                **extra,
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content and first_token is None:
                    first_token = time.monotonic()
                if chunk.usage and chunk.usage.completion_tokens_details:
                    reasoning_tokens = chunk.usage.completion_tokens_details.reasoning_tokens
    finally:
        await client.close()
    finished = time.monotonic()
    if first_token is None:
        raise RuntimeError("Provider returned no text token")
    return (first_token - started) * 1000, (finished - started) * 1000, reasoning_tokens


async def _diagnose_gemini(config: DiagnosticConfig) -> tuple[float, float, int | None]:
    capability = get_model_capability(config.provider, config.model)
    thinking = None
    if capability and capability.control_name == "thinking_budget":
        assert isinstance(capability.control_value, int)
        thinking = types.ThinkingConfig(
            thinking_budget=capability.control_value, include_thoughts=False
        )
    elif capability and capability.control_name == "thinking_level":
        thinking = types.ThinkingConfig(
            thinking_level=str(capability.control_value), include_thoughts=False
        )
    client = genai.Client(api_key=config.api_key)
    started = time.monotonic()
    first_token: float | None = None
    reasoning_tokens: int | None = None
    try:
        async with asyncio.timeout(config.timeout):
            stream = await client.aio.models.generate_content_stream(
                model=config.model,
                contents="Reply with OK.",
                config=types.GenerateContentConfig(
                    max_output_tokens=8,
                    thinking_config=thinking,
                ),
            )
            async for chunk in stream:
                if getattr(chunk, "text", None) and first_token is None:
                    first_token = time.monotonic()
                usage: Any = getattr(chunk, "usage_metadata", None)
                thoughts = getattr(usage, "thoughts_token_count", None) if usage else None
                if thoughts is not None:
                    reasoning_tokens = int(thoughts)
    finally:
        await client.aio.aclose()
    finished = time.monotonic()
    if first_token is None:
        raise RuntimeError("Provider returned no text token")
    return (first_token - started) * 1000, (finished - started) * 1000, reasoning_tokens


async def run_llm_diagnostic(config: DiagnosticConfig) -> LLMDiagnosticResult:
    """Run one minimal provider call and return a secret-safe result."""
    diagnostic_id = str(uuid.uuid4())
    started = time.monotonic()
    host = urlparse(config.base_url).hostname or "native-api"
    try:
        if config.provider == "google_gemini":
            first_ms, total_ms, reasoning_tokens = await _diagnose_gemini(config)
        else:
            first_ms, total_ms, reasoning_tokens = await _diagnose_openai(config)
        control, reasoning_status = _reasoning_result(
            provider=config.provider, model=config.model, reasoning_tokens=reasoning_tokens
        )
        return LLMDiagnosticResult(
            diagnostic_id=diagnostic_id,
            success=True,
            category="ok",
            summary="The model returned a streamed text response.",
            suggestion="This configuration is ready for a voice session.",
            provider=config.provider,
            base_url_host=host,
            model=config.model,
            first_token_ms=round(first_ms, 1),
            total_ms=round(total_ms, 1),
            reasoning_control=control,
            reasoning_tokens=reasoning_tokens,
            reasoning_status=reasoning_status,
        )
    except Exception as exc:
        category, summary, suggestion = classify_llm_failure(exc)
        control, reasoning_status = _reasoning_result(
            provider=config.provider, model=config.model, reasoning_tokens=None
        )
        return LLMDiagnosticResult(
            diagnostic_id=diagnostic_id,
            success=False,
            category=category,
            summary=summary,
            suggestion=suggestion,
            provider=config.provider,
            base_url_host=host,
            model=config.model,
            total_ms=round((time.monotonic() - started) * 1000, 1),
            reasoning_control=control,
            reasoning_status=reasoning_status,
        )
