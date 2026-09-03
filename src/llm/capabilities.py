"""Verified provider and model capabilities for low-latency LLM use."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ReasoningStatus = Literal["confirmed_off", "not_applicable", "minimized", "detected", "unverified"]


@dataclass(frozen=True, slots=True)
class ModelCapability:
    """One verified model's provider-specific low-latency controls."""

    provider: str
    model: str
    control_name: str | None
    control_value: str | int | None
    expected_status: ReasoningStatus
    verified_at: str


MODEL_CAPABILITIES: dict[tuple[str, str], ModelCapability] = {
    ("openai", "gpt-4.1-mini"): ModelCapability(
        "openai", "gpt-4.1-mini", None, None, "not_applicable", "2026-09-02"
    ),
    ("openai", "gpt-4.1"): ModelCapability(
        "openai", "gpt-4.1", None, None, "not_applicable", "2026-09-02"
    ),
    ("openai", "gpt-5-mini"): ModelCapability(
        "openai", "gpt-5-mini", "reasoning_effort", "minimal", "minimized", "2026-09-02"
    ),
    ("google_gemini", "gemini-2.5-flash-lite"): ModelCapability(
        "google_gemini",
        "gemini-2.5-flash-lite",
        "thinking_budget",
        0,
        "confirmed_off",
        "2026-09-02",
    ),
    ("google_gemini", "gemini-2.5-flash"): ModelCapability(
        "google_gemini", "gemini-2.5-flash", "thinking_budget", 0, "confirmed_off", "2026-09-02"
    ),
    ("google_gemini", "gemini-3.5-flash-lite"): ModelCapability(
        "google_gemini",
        "gemini-3.5-flash-lite",
        "thinking_level",
        "minimal",
        "minimized",
        "2026-09-02",
    ),
    ("google_gemini", "gemini-3.6-flash"): ModelCapability(
        "google_gemini", "gemini-3.6-flash", "thinking_level", "minimal", "minimized", "2026-09-02"
    ),
}


def get_model_capability(provider: str, model: str) -> ModelCapability | None:
    """Return a verified capability without guessing from a model name."""
    return MODEL_CAPABILITIES.get((provider, model))
