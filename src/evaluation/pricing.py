"""Verify public ASR and LLM list prices against fixed official sources."""

from __future__ import annotations

import asyncio
import html
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator


class PricingSyncError(RuntimeError):
    """Raised when an official price cannot be verified without guessing."""


class PricingSelection(BaseModel):
    """One exact provider and model selected in the pricing table."""

    model_config = ConfigDict(extra="forbid")
    provider: Literal["Gemini", "GPT", "Qwen", "DeepSeek", "Azure GPT", "OpenRouter"]
    model: str = Field(min_length=1, max_length=160)


class PricingSyncRequest(BaseModel):
    """Request a fresh verification for ASR or selected LLM list prices."""

    model_config = ConfigDict(extra="forbid")
    scope: Literal["asr", "llm"]
    selections: list[PricingSelection] = Field(default_factory=list, max_length=2)

    @model_validator(mode="after")
    def validate_scope(self) -> PricingSyncRequest:
        """Require exact LLM selections and reject irrelevant ASR selections."""
        if self.scope == "llm" and not self.selections:
            raise ValueError("LLM pricing sync requires at least one selected model")
        if self.scope == "asr" and self.selections:
            raise ValueError("ASR pricing sync does not accept LLM selections")
        return self


@dataclass(frozen=True)
class OfficialRate:
    """One reviewed public list-price record and its verification evidence."""

    provider: str
    model: str
    currency: str
    source_url: str
    source_label: str
    evidence_patterns: tuple[str, ...]
    billing_unit: str | None = None
    unit_price: float | None = None
    input_per_1m: float | None = None
    cached_input_per_1m: float | None = None
    output_per_1m: float | None = None
    note: str = "Public list price; contract and volume rates may differ."


_ASR_RATES = (
    OfficialRate(
        provider="Soniox",
        model="stt-async-v5",
        currency="USD",
        billing_unit="audio_hour",
        unit_price=0.10,
        source_url="https://soniox.com/pricing",
        source_label="Soniox official pricing",
        evidence_patterns=(r"speech.to.text", r"0\.10\s*/?\s*hour", r"async"),
        note="Official async equivalent; Soniox bills underlying audio/text tokens.",
    ),
    OfficialRate(
        provider="Speechmatics",
        model="melia-1",
        currency="USD",
        billing_unit="audio_hour",
        unit_price=0.129,
        source_url="https://www.speechmatics.com/pricing",
        source_label="Speechmatics official pricing",
        evidence_patterns=(r"batch\s+melia\s+1", r"0\.129\s*/\s*hr"),
    ),
    OfficialRate(
        provider="ElevenLabs",
        model="scribe-v2",
        currency="USD",
        billing_unit="audio_hour",
        unit_price=0.22,
        source_url="https://elevenlabs.io/pricing/api",
        source_label="ElevenLabs official API pricing",
        evidence_patterns=(r"scribe\s+v2", r"0\.22", r"price\s+per\s+hour"),
    ),
)

_LLM_RATES = {
    ("Gemini", "gemini-2.5-flash-lite"): OfficialRate(
        provider="Gemini",
        model="gemini-2.5-flash-lite",
        currency="USD",
        input_per_1m=0.10,
        cached_input_per_1m=0.01,
        output_per_1m=0.40,
        source_url="https://ai.google.dev/gemini-api/docs/pricing",
        source_label="Google Gemini API pricing",
        evidence_patterns=(r"gemini\s+2\.5\s+flash.lite", r"\$0\.10", r"\$0\.40"),
    ),
    ("Gemini", "gemini-2.5-flash"): OfficialRate(
        provider="Gemini",
        model="gemini-2.5-flash",
        currency="USD",
        input_per_1m=0.30,
        cached_input_per_1m=0.03,
        output_per_1m=2.50,
        source_url="https://ai.google.dev/gemini-api/docs/pricing",
        source_label="Google Gemini API pricing",
        evidence_patterns=(r"gemini\s+2\.5\s+flash", r"\$0\.30", r"\$2\.50"),
    ),
    ("Gemini", "gemini-3.8-flash"): OfficialRate(
        provider="Gemini",
        model="gemini-3.8-flash",
        currency="USD",
        input_per_1m=0.75,
        cached_input_per_1m=0.075,
        output_per_1m=3.75,
        source_url="https://ai.google.dev/gemini-api/docs/pricing",
        source_label="Google Gemini API pricing",
        evidence_patterns=(r"gemini\s+3\.8\s+flash", r"\$0\.75", r"\$3\.75"),
        note="Introductory standard rate through 2026-12-31.",
    ),
    ("GPT", "gpt-4.1-mini"): OfficialRate(
        provider="GPT",
        model="gpt-4.1-mini",
        currency="USD",
        input_per_1m=0.40,
        cached_input_per_1m=0.10,
        output_per_1m=1.60,
        source_url="https://developers.openai.com/api/docs/models/gpt-4.1-mini",
        source_label="OpenAI API model pricing",
        evidence_patterns=(r"gpt.4\.1\s+mini", r"\$0\.40", r"\$1\.60"),
    ),
    ("GPT", "gpt-4.1"): OfficialRate(
        provider="GPT",
        model="gpt-4.1",
        currency="USD",
        input_per_1m=2.00,
        cached_input_per_1m=0.50,
        output_per_1m=8.00,
        source_url="https://developers.openai.com/api/docs/models/gpt-4.1",
        source_label="OpenAI API model pricing",
        evidence_patterns=(r"gpt.4\.1", r"\$2\.00", r"\$8\.00"),
    ),
    ("GPT", "gpt-5-mini"): OfficialRate(
        provider="GPT",
        model="gpt-5-mini",
        currency="USD",
        input_per_1m=0.25,
        cached_input_per_1m=0.025,
        output_per_1m=2.00,
        source_url="https://developers.openai.com/api/docs/models/gpt-5-mini",
        source_label="OpenAI API model pricing",
        evidence_patterns=(r"gpt.5\s+mini", r"\$0\.25", r"\$2\.00"),
    ),
    ("DeepSeek", "deepseek-flash"): OfficialRate(
        provider="DeepSeek",
        model="deepseek-flash",
        currency="USD",
        input_per_1m=0.30,
        cached_input_per_1m=0.006,
        output_per_1m=1.20,
        source_url="https://api-docs.deepseek.com/quick_start/pricing",
        source_label="DeepSeek API pricing",
        evidence_patterns=(
            r"deepseek.flash",
            r"deepseek.v4\.1.flash",
            r"\$0\.006",
            r"\$0\.3",
            r"\$1\.2",
        ),
        note=(
            "Peak ceiling used for budget safety; weekday off-peak rates are 50% lower "
            "outside 01:00–04:00 and 06:00–10:00 UTC."
        ),
    ),
    ("DeepSeek", "deepseek-v4-pro"): OfficialRate(
        provider="DeepSeek",
        model="deepseek-v4-pro",
        currency="USD",
        input_per_1m=1.32,
        cached_input_per_1m=0.044,
        output_per_1m=3.96,
        source_url="https://api-docs.deepseek.com/quick_start/pricing",
        source_label="DeepSeek API pricing",
        evidence_patterns=(
            r"deepseek.v4.pro",
            r"\$0\.044",
            r"\$1\.32",
            r"\$3\.96",
        ),
        note=(
            "Peak ceiling used for budget safety; weekday off-peak rates are 50% lower "
            "outside 01:00–04:00 and 06:00–10:00 UTC."
        ),
    ),
    ("Qwen", "qwen-plus"): OfficialRate(
        provider="Qwen",
        model="qwen-plus",
        currency="CNY",
        input_per_1m=0.80,
        cached_input_per_1m=0.16,
        output_per_1m=2.00,
        source_url="https://help.aliyun.com/zh/model-studio/qwen-plus",
        source_label="Alibaba Cloud Model Studio pricing",
        evidence_patterns=(
            r"qwen.plus",
            r"输入（缓存命中）\s+0\.16",
            r"输入\s+0\.8",
            r"输出\s+2",
        ),
        note="China (Beijing), non-thinking, input up to 128K; cache hit is 20% of input.",
    ),
    ("Qwen", "qwen-turbo"): OfficialRate(
        provider="Qwen",
        model="qwen-turbo",
        currency="CNY",
        input_per_1m=0.30,
        output_per_1m=0.60,
        source_url="https://help.aliyun.com/zh/model-studio/model-pricing",
        source_label="Alibaba Cloud Model Studio pricing",
        evidence_patterns=(r"qwen.turbo", r"0\.3\s*元", r"0\.6\s*元"),
        note=(
            "China (Beijing), non-thinking output; the public pricing row does "
            "not state a cache-hit rate."
        ),
    ),
}

_MODEL_ALIASES = {
    ("DeepSeek", "deepseek-v4-flash"): "deepseek-flash",
    ("DeepSeek", "deepseek-chat"): "deepseek-flash",
    ("DeepSeek", "deepseek-reasoner"): "deepseek-v4-pro",
}


def _normalize_model(provider: str, model: str) -> str:
    """Remove a UI provider prefix and resolve documented compatibility aliases."""
    value = model.strip()
    prefix = f"{provider}/"
    if value.casefold().startswith(prefix.casefold()):
        value = value[len(prefix) :].strip()
    normalized = value.casefold()
    return _MODEL_ALIASES.get((provider, normalized), normalized)


def estimate_llm_cost(
    provider: str,
    model: str,
    *,
    input_tokens: int,
    cached_input_tokens: int,
    reasoning_tokens: int,
    output_tokens: int,
) -> tuple[float | None, str]:
    """Estimate one response in its supplier currency from reviewed list rates."""
    provider_names = {
        "gemini": "Gemini",
        "gpt": "GPT",
        "qwen": "Qwen",
        "deepseek": "DeepSeek",
    }
    canonical_provider = provider_names.get(provider.casefold(), provider)
    rate = _LLM_RATES.get((canonical_provider, _normalize_model(canonical_provider, model)))
    if rate is None:
        return None, "USD"
    uncached_tokens = max(0, input_tokens - cached_input_tokens)
    amount = (
        uncached_tokens * float(rate.input_per_1m or 0)
        + cached_input_tokens * float(rate.cached_input_per_1m or rate.input_per_1m or 0)
        + (output_tokens + reasoning_tokens) * float(rate.output_per_1m or 0)
    ) / 1_000_000
    return amount, rate.currency


def pricing_catalog() -> dict[str, list[dict[str, object]]]:
    """Return the reviewed model-specific rates ready for an immutable snapshot."""

    def public_rate(rate: OfficialRate) -> dict[str, object]:
        item = asdict(rate)
        item.pop("evidence_patterns")
        return item

    return {
        "asr": [public_rate(rate) for rate in _ASR_RATES],
        "llm": [public_rate(rate) for rate in _LLM_RATES.values()],
    }


def _searchable_page(content: str) -> str:
    """Make server-rendered and embedded page text comparable without an HTML parser."""
    decoded = html.unescape(content).casefold()
    without_tags = re.sub(r"<[^>]+>", " ", decoded)
    return re.sub(r"\s+", " ", without_tags)


class OfficialPricingService:
    """Fetch allow-listed official pages and return rates only when evidence still matches."""

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    async def sync(
        self,
        request: PricingSyncRequest,
        *,
        timeout: float = 12.0,
    ) -> dict[str, object]:
        """Verify requested list prices against their current official source pages."""
        rates = self._resolve_rates(request)
        pages = await self._fetch_pages({rate.source_url for rate in rates}, timeout=timeout)
        for rate in rates:
            page = _searchable_page(pages[rate.source_url])
            missing = [
                pattern
                for pattern in rate.evidence_patterns
                if re.search(pattern, page, flags=re.IGNORECASE) is None
            ]
            if missing:
                raise PricingSyncError(
                    f"Official pricing evidence changed for {rate.provider} {rate.model}; "
                    "existing draft prices were not overwritten"
                )
        checked_at = datetime.now(UTC).isoformat()
        items = []
        for rate in rates:
            item = asdict(rate)
            item.pop("evidence_patterns")
            item["checked_at"] = checked_at
            items.append(item)
        return {"scope": request.scope, "checked_at": checked_at, "items": items}

    def _resolve_rates(self, request: PricingSyncRequest) -> tuple[OfficialRate, ...]:
        if request.scope == "asr":
            return _ASR_RATES
        resolved: list[OfficialRate] = []
        for selection in request.selections:
            model = _normalize_model(selection.provider, selection.model)
            rate = _LLM_RATES.get((selection.provider, model))
            if rate is None:
                raise PricingSyncError(
                    f"No reviewed official list price is available for "
                    f"{selection.provider}/{model}; enter a contract price manually"
                )
            resolved.append(rate)
        return tuple(resolved)

    async def _fetch_pages(self, urls: set[str], *, timeout: float) -> dict[str, str]:
        headers = {"User-Agent": "VoiceAgent-PricingVerifier/1.0"}
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                headers=headers,
                transport=self._transport,
            ) as client:
                ordered_urls = sorted(urls)
                responses = await asyncio.gather(*(client.get(url) for url in ordered_urls))
            pages: dict[str, str] = {}
            for source_url, response in zip(ordered_urls, responses, strict=True):
                response.raise_for_status()
                pages[source_url] = response.text
            return pages
        except httpx.HTTPError as exc:
            raise PricingSyncError(
                "An official pricing page could not be verified; existing draft prices "
                "were not overwritten"
            ) from exc
