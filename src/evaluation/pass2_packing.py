"""Deterministic, conversation-atomic packing for Pass 2 requests."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ModelTokenPolicy:
    """Conservative token limits used before a paid request is dispatched."""

    context_limit: int
    max_output_tokens: int
    safety_margin: int


@dataclass(frozen=True)
class ConversationUnit:
    """One indivisible conversation with every Case and evidence item."""

    conversation_id: str
    payload: dict[str, Any]
    case_keys: tuple[tuple[str, str], ...]
    estimated_input_tokens: int
    reserved_output_tokens: int


@dataclass(frozen=True)
class PassTwoGroup:
    """One external request group with stable identity and membership."""

    group_id: str
    idempotency_key: str
    units: tuple[ConversationUnit, ...]
    estimated_input_tokens: int
    reserved_output_tokens: int

    @property
    def case_keys(self) -> tuple[tuple[str, str], ...]:
        """Flatten the unique Case keys in deterministic request order."""
        return tuple(case for unit in self.units for case in unit.case_keys)


_PROVIDER_POLICIES = {
    # Safe operating ceilings, not advertised maxima. DeepSeek's current official
    # context is larger; keeping headroom protects structured output and reasoning.
    "deepseek": ModelTokenPolicy(840_000, 128_000, 32_000),
    "gemini": ModelTokenPolicy(800_000, 64_000, 32_000),
    "gpt": ModelTokenPolicy(96_000, 32_000, 16_000),
    "qwen": ModelTokenPolicy(96_000, 32_000, 16_000),
    "azure_gpt": ModelTokenPolicy(96_000, 32_000, 16_000),
    "openrouter": ModelTokenPolicy(96_000, 32_000, 16_000),
}


def model_token_policy(provider: str) -> ModelTokenPolicy:
    """Return the frozen conservative policy for one verified provider."""
    try:
        return _PROVIDER_POLICIES[provider]
    except KeyError as exc:
        raise ValueError(f"No verified token policy for provider: {provider}") from exc


def estimate_tokens(value: object) -> int:
    """Overestimate multilingual JSON tokens from UTF-8 bytes.

    A byte upper bound is intentionally conservative for Arabic, CJK and ASCII and
    avoids silently under-packing an unknown custom model tokenizer.
    """
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return max(1, len(encoded))


def output_reserve(case_count: int, policy: ModelTokenPolicy) -> int:
    """Reserve visible JSON plus Thinking tokens for a request group."""
    if case_count <= 0:
        return 0
    visible_json = case_count * 768
    reasoning = max(16_384, case_count * 256)
    return visible_json + reasoning


def build_unit(
    conversation_id: str,
    payload: dict[str, Any],
    case_keys: list[tuple[str, str]],
    policy: ModelTokenPolicy,
) -> ConversationUnit:
    """Create a measured atomic unit and reject duplicate or missing membership."""
    normalized = tuple((str(conversation), str(event)) for conversation, event in case_keys)
    if not normalized or len(set(normalized)) != len(normalized):
        raise ValueError("Pass 2 unit must contain unique Cases")
    if {key[0] for key in normalized} != {conversation_id}:
        raise ValueError("Pass 2 unit cannot mix conversations")
    reserved_output = output_reserve(len(normalized), policy)
    if reserved_output > policy.max_output_tokens:
        raise ValueError(f"Conversation exceeds Pass 2 output limit: {conversation_id}")
    return ConversationUnit(
        conversation_id=conversation_id,
        payload=payload,
        case_keys=normalized,
        estimated_input_tokens=estimate_tokens(payload),
        reserved_output_tokens=reserved_output,
    )


def pack_units(
    *,
    batch_id: str,
    units: list[ConversationUnit],
    system_prompt: str,
    policy: ModelTokenPolicy,
) -> list[PassTwoGroup]:
    """Pack units into the minimum safe number of deterministic request groups."""
    prompt_tokens = estimate_tokens(system_prompt)
    ordered = sorted(units, key=lambda unit: unit.conversation_id)
    groups: list[list[ConversationUnit]] = []

    def fits(candidate: list[ConversationUnit]) -> bool:
        input_tokens = prompt_tokens + sum(unit.estimated_input_tokens for unit in candidate)
        cases = sum(len(unit.case_keys) for unit in candidate)
        reserved_output = output_reserve(cases, policy)
        return (
            reserved_output <= policy.max_output_tokens
            and input_tokens + reserved_output + policy.safety_margin <= policy.context_limit
        )

    # Largest-first best fit avoids a fixed conversation count and minimizes paid
    # groups for the common case while keeping stable ordering for restart safety.
    ordered = sorted(
        ordered,
        key=lambda unit: unit.estimated_input_tokens + unit.reserved_output_tokens,
        reverse=True,
    )
    for unit in ordered:
        if not fits([unit]):
            raise ValueError(f"Conversation exceeds Pass 2 token limit: {unit.conversation_id}")
        best_index: int | None = None
        best_remaining: int | None = None
        for index, members in enumerate(groups):
            candidate = [*members, unit]
            if not fits(candidate):
                continue
            input_tokens = prompt_tokens + sum(
                member.estimated_input_tokens for member in candidate
            )
            cases = sum(len(member.case_keys) for member in candidate)
            remaining = (
                policy.context_limit
                - input_tokens
                - output_reserve(cases, policy)
                - policy.safety_margin
            )
            if best_remaining is None or remaining < best_remaining:
                best_index = index
                best_remaining = remaining
        if best_index is None:
            groups.append([unit])
        else:
            groups[best_index].append(unit)
    for members in groups:
        members.sort(key=lambda unit: unit.conversation_id)
    groups.sort(key=lambda members: members[0].conversation_id)

    result: list[PassTwoGroup] = []
    seen: set[tuple[str, str]] = set()
    for index, members in enumerate(groups, start=1):
        case_keys = tuple(case for unit in members for case in unit.case_keys)
        if seen.intersection(case_keys):
            raise ValueError("Pass 2 packing produced duplicate Cases")
        seen.update(case_keys)
        membership = json.dumps(case_keys, ensure_ascii=False, separators=(",", ":"))
        digest = hashlib.sha256(f"{batch_id}:{membership}".encode()).hexdigest()
        result.append(
            PassTwoGroup(
                group_id=f"G{index:04d}-{digest[:12]}",
                idempotency_key=digest,
                units=tuple(members),
                estimated_input_tokens=prompt_tokens
                + sum(unit.estimated_input_tokens for unit in members),
                reserved_output_tokens=output_reserve(len(case_keys), policy),
            )
        )
    expected = {case for unit in units for case in unit.case_keys}
    if seen != expected:
        raise ValueError("Pass 2 packing omitted Cases")
    return result
