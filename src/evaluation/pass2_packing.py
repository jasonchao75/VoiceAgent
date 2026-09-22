"""Deterministic request packing for evaluation LLM stages."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ModelTokenPolicy:
    """Conservative token limits used before a paid request is dispatched."""

    context_limit: int
    max_output_tokens: int
    safety_margin: int
    reasoning_reserve: int = 16_384
    max_input_tokens: int | None = None


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


@dataclass(frozen=True)
class PassOneUnit:
    """One indivisible conversation prepared for first-pass screening."""

    conversation_id: str
    payload: dict[str, Any]
    user_event_count: int
    estimated_input_tokens: int


@dataclass(frozen=True)
class PassOneGroup:
    """One stable first-pass request group."""

    group_id: str
    idempotency_key: str
    units: tuple[PassOneUnit, ...]
    estimated_input_tokens: int
    reserved_output_tokens: int

    @property
    def conversation_ids(self) -> tuple[str, ...]:
        """Return frozen conversation membership in request order."""
        return tuple(unit.conversation_id for unit in self.units)


@dataclass(frozen=True)
class EventAlignmentUnit:
    """One complete conversation prepared for semantic event alignment."""

    conversation_id: str
    payload: dict[str, Any]
    target_event_count: int
    provider_count: int
    estimated_input_tokens: int


@dataclass(frozen=True)
class EventAlignmentGroup:
    """One stable Event Aligner request containing whole conversations."""

    group_id: str
    idempotency_key: str
    units: tuple[EventAlignmentUnit, ...]
    estimated_input_tokens: int
    reserved_output_tokens: int

    @property
    def conversation_ids(self) -> tuple[str, ...]:
        """Return frozen conversation membership in request order."""
        return tuple(unit.conversation_id for unit in self.units)


EVALUATION_CONTEXT_LIMIT = 131_072
EVALUATION_INPUT_LIMIT = 65_536
EVALUATION_OUTPUT_LIMIT = 32_768
EVALUATION_SAFETY_MARGIN = 32_768
FIXED_EVALUATION_USER_MESSAGE = (
    "Evaluate the evidence in the system prompt and return only the required JSON object."
)
_MESSAGE_PROTOCOL_OVERHEAD = 1_024


_PROVIDER_POLICIES = {
    # Safe operating ceilings, not advertised maxima. DeepSeek's current official
    # context is larger; keeping headroom protects structured output and reasoning.
    "deepseek": ModelTokenPolicy(840_000, 128_000, 32_000, 24_000),
    "gemini": ModelTokenPolicy(800_000, 64_000, 32_000, 36_000),
    "gpt": ModelTokenPolicy(96_000, 32_000, 16_000),
    "qwen": ModelTokenPolicy(96_000, 32_000, 16_000, 20_000),
    "azure_gpt": ModelTokenPolicy(96_000, 32_000, 16_000),
    "openrouter": ModelTokenPolicy(96_000, 32_000, 16_000),
}


def model_token_policy(provider: str, model_id: str | None = None) -> ModelTokenPolicy:
    """Return the conservative policy for one verified provider/model pair."""
    if provider == "qwen" and (model_id or "").casefold().startswith("qwen3.8-"):
        return ModelTokenPolicy(1_000_000, 131_072, 32_768, 32_768)
    try:
        return _PROVIDER_POLICIES[provider]
    except KeyError as exc:
        raise ValueError(f"No verified token policy for provider: {provider}") from exc


def evaluation_token_policy(provider: str, model_id: str | None = None) -> ModelTokenPolicy:
    """Apply the shared Pass 1/Pass 2 envelope below provider-specific limits."""
    provider_policy = model_token_policy(provider, model_id)
    context_limit = min(provider_policy.context_limit, EVALUATION_CONTEXT_LIMIT)
    max_output_tokens = min(provider_policy.max_output_tokens, EVALUATION_OUTPUT_LIMIT)
    safety_margin = min(EVALUATION_SAFETY_MARGIN, max(0, context_limit - max_output_tokens))
    max_input_tokens = min(
        EVALUATION_INPUT_LIMIT,
        max(0, context_limit - max_output_tokens - safety_margin),
    )
    if max_input_tokens <= 0:
        raise ValueError(f"Model cannot satisfy the evaluation token envelope: {provider}")
    return ModelTokenPolicy(
        context_limit=context_limit,
        max_output_tokens=max_output_tokens,
        safety_margin=safety_margin,
        reasoning_reserve=min(provider_policy.reasoning_reserve, max_output_tokens),
        max_input_tokens=max_input_tokens,
    )


def estimate_tokens(value: object) -> int:
    """Overestimate multilingual JSON tokens from UTF-8 bytes.

    A byte upper bound is intentionally conservative for Arabic, CJK and ASCII and
    avoids silently under-packing an unknown custom model tokenizer.
    """
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return max(1, len(encoded))


def render_prompt(template: str, payload: dict[str, Any]) -> str:
    """Replace every declared runtime slot with its exact serialized value."""
    rendered = template
    for key, value in payload.items():
        rendered = rendered.replace(
            f"{{{{{key}}}}}",
            json.dumps(value, ensure_ascii=False, separators=(",", ":")),
        )
    unresolved = sorted(set(part.split("}}", 1)[0] for part in rendered.split("{{")[1:]))
    if unresolved:
        raise ValueError("Prompt has unresolved runtime slots: " + ", ".join(unresolved))
    return rendered


def final_request_input_tokens(
    system_prompt_template: str,
    payload: dict[str, Any],
    *,
    user_message: str = FIXED_EVALUATION_USER_MESSAGE,
) -> int:
    """Return a conservative upper bound for the exact final message pair."""
    rendered = render_prompt(system_prompt_template, payload)
    return estimate_tokens(rendered) + estimate_tokens(user_message) + _MESSAGE_PROTOCOL_OVERHEAD


def input_limit(policy: ModelTokenPolicy) -> int:
    """Return the explicit input cap after provider and shared-envelope limits."""
    derived = max(0, policy.context_limit - policy.safety_margin)
    return min(policy.max_input_tokens or derived, derived)


def build_pass_one_payload(
    request_group_id: str,
    units: list[PassOneUnit] | tuple[PassOneUnit, ...],
    shared_payload: dict[str, Any],
) -> dict[str, Any]:
    """Build the single canonical Pass 1 runtime payload."""
    return {
        "request_group_id": request_group_id,
        "conversations": [unit.payload for unit in units],
        **shared_payload,
    }


def build_pass_two_payload(
    request_group_id: str,
    units: list[ConversationUnit] | tuple[ConversationUnit, ...],
    shared_payload: dict[str, Any],
) -> dict[str, Any]:
    """Build one de-duplicated Pass 2 payload from internal Case units."""
    return {
        "request_group_id": request_group_id,
        **shared_payload,
        "candidate_case": [
            candidate for unit in units for candidate in unit.payload.get("candidate_cases", [])
        ],
        "conversation_history": [
            {
                "conversation_id": unit.conversation_id,
                "events": unit.payload.get("conversation_history", []),
            }
            for unit in units
        ],
        "production_transcript": [
            {
                "conversation_id": unit.conversation_id,
                "events": unit.payload.get("production_transcripts", {}),
            }
            for unit in units
        ],
        "full_audio_context_asr": [
            {
                "conversation_id": unit.conversation_id,
                "events": unit.payload.get("full_audio_context_asr", []),
            }
            for unit in units
        ],
        "asr_results": [
            {
                "conversation_id": unit.conversation_id,
                "events": unit.payload.get("asr_results", []),
            }
            for unit in units
        ],
    }


def output_reserve(case_count: int, policy: ModelTokenPolicy) -> int:
    """Reserve visible JSON plus Thinking tokens for a request group."""
    if case_count <= 0:
        return 0
    visible_json = case_count * 768
    reasoning = max(policy.reasoning_reserve, case_count * 256)
    return visible_json + reasoning


def pass_one_output_reserve(
    conversation_count: int,
    user_event_count: int,
    policy: ModelTokenPolicy,
) -> int:
    """Reserve grouped JSON output for first-pass conversation and event results."""
    if conversation_count <= 0 or user_event_count < 0:
        return 0
    visible_json = conversation_count * 512 + user_event_count * 192
    return min(policy.max_output_tokens + 1, max(4_096, visible_json))


def event_alignment_output_reserve(
    units: list[EventAlignmentUnit], policy: ModelTokenPolicy
) -> int:
    """Reserve structured mappings for every target event and ASR provider."""
    if not units:
        return 0
    visible_json = sum(
        768 + unit.target_event_count * max(2, unit.provider_count) * 320 for unit in units
    )
    return min(policy.max_output_tokens + 1, max(4_096, visible_json))


def build_event_alignment_unit(
    conversation_id: str,
    payload: dict[str, Any],
    target_event_count: int,
    provider_count: int,
) -> EventAlignmentUnit:
    """Create one measured Event Aligner unit without splitting a conversation."""
    if not conversation_id or target_event_count <= 0 or provider_count <= 0:
        raise ValueError("Event Aligner unit requires targets and providers")
    return EventAlignmentUnit(
        conversation_id=conversation_id,
        payload=payload,
        target_event_count=target_event_count,
        provider_count=provider_count,
        estimated_input_tokens=estimate_tokens(payload),
    )


def pack_event_alignment_units(
    *,
    batch_id: str,
    units: list[EventAlignmentUnit],
    system_prompt: str,
    policy: ModelTokenPolicy,
) -> list[EventAlignmentGroup]:
    """Prefer one batch request, otherwise use the fewest safe whole-call groups."""
    prompt_tokens = estimate_tokens(system_prompt)

    def fits(candidate: list[EventAlignmentUnit]) -> bool:
        # The frozen template embeds the payload and the provider also receives the
        # same JSON as the user message, so reserve both copies before dispatch.
        input_tokens = prompt_tokens + 2 * sum(unit.estimated_input_tokens for unit in candidate)
        output_tokens = event_alignment_output_reserve(candidate, policy)
        return (
            output_tokens <= policy.max_output_tokens
            and input_tokens + output_tokens + policy.safety_margin <= policy.context_limit
        )

    ordered = sorted(
        units,
        key=lambda unit: (unit.estimated_input_tokens, unit.conversation_id),
        reverse=True,
    )
    for unit in ordered:
        if not fits([unit]):
            raise ValueError(
                f"Conversation exceeds Event Aligner token limit: {unit.conversation_id}"
            )
    if not ordered:
        return []
    if fits(ordered):
        packed = [ordered]
    else:
        greedy: list[list[EventAlignmentUnit]] = []
        for unit in ordered:
            placements = [
                (index, [*members, unit])
                for index, members in enumerate(greedy)
                if fits([*members, unit])
            ]
            if placements:
                best_index, _ = min(
                    placements,
                    key=lambda placement: (
                        policy.context_limit
                        - prompt_tokens
                        - sum(item.estimated_input_tokens for item in placement[1])
                        - event_alignment_output_reserve(placement[1], policy),
                        placement[0],
                    ),
                )
                greedy[best_index].append(unit)
            else:
                greedy.append([unit])

        best = [list(members) for members in greedy]
        available_context = policy.context_limit - prompt_tokens - policy.safety_margin
        total_input = 2 * sum(unit.estimated_input_tokens for unit in ordered)
        total_visible_output = sum(
            768 + unit.target_event_count * max(2, unit.provider_count) * 320 for unit in ordered
        )
        lower_bound = max(
            1,
            math.ceil((total_input + total_visible_output) / available_context),
            math.ceil(total_visible_output / policy.max_output_tokens),
        )
        if lower_bound >= len(best):
            packed = best
        else:
            seen_states: set[tuple[int, tuple[tuple[int, int, int], ...]]] = set()

            def search(index: int, candidate_groups: list[list[EventAlignmentUnit]]) -> None:
                nonlocal best
                if len(candidate_groups) >= len(best):
                    return
                if index == len(ordered):
                    best = [list(members) for members in candidate_groups]
                    return
                signature = tuple(
                    sorted(
                        (
                            sum(item.estimated_input_tokens for item in members),
                            sum(item.target_event_count for item in members),
                            len(members),
                        )
                        for members in candidate_groups
                    )
                )
                state = (index, signature)
                if state in seen_states:
                    return
                seen_states.add(state)
                unit = ordered[index]
                tried: set[tuple[int, int, int]] = set()
                for members in candidate_groups:
                    aggregate = (
                        sum(item.estimated_input_tokens for item in members),
                        sum(item.target_event_count for item in members),
                        len(members),
                    )
                    if aggregate in tried or not fits([*members, unit]):
                        continue
                    tried.add(aggregate)
                    members.append(unit)
                    search(index + 1, candidate_groups)
                    members.pop()
                if len(candidate_groups) + 1 < len(best):
                    candidate_groups.append([unit])
                    search(index + 1, candidate_groups)
                    candidate_groups.pop()

            search(0, [])
            packed = best

    for members in packed:
        members.sort(key=lambda unit: unit.conversation_id)
    packed.sort(key=lambda members: members[0].conversation_id)
    result: list[EventAlignmentGroup] = []
    seen: set[str] = set()
    for index, members in enumerate(packed, start=1):
        conversation_ids = tuple(unit.conversation_id for unit in members)
        if seen.intersection(conversation_ids):
            raise ValueError("Event Aligner packing produced duplicate conversations")
        seen.update(conversation_ids)
        membership = json.dumps(conversation_ids, ensure_ascii=False, separators=(",", ":"))
        digest = hashlib.sha256(f"{batch_id}:event-aligner:{membership}".encode()).hexdigest()
        result.append(
            EventAlignmentGroup(
                group_id=f"EAG{index:04d}-{digest[:12]}",
                idempotency_key=digest,
                units=tuple(members),
                estimated_input_tokens=prompt_tokens
                + 2 * sum(unit.estimated_input_tokens for unit in members),
                reserved_output_tokens=event_alignment_output_reserve(members, policy),
            )
        )
    if seen != {unit.conversation_id for unit in units}:
        raise ValueError("Event Aligner packing omitted conversations")
    return result


def build_pass_one_unit(
    conversation_id: str,
    payload: dict[str, Any],
    user_event_count: int,
) -> PassOneUnit:
    """Create one measured first-pass unit without splitting its conversation."""
    if not conversation_id or user_event_count < 0:
        raise ValueError("Pass 1 unit requires a valid conversation")
    return PassOneUnit(
        conversation_id=conversation_id,
        payload=payload,
        user_event_count=user_event_count,
        estimated_input_tokens=estimate_tokens(payload),
    )


def pack_pass_one_units(
    *,
    batch_id: str,
    units: list[PassOneUnit],
    system_prompt: str,
    shared_payload: dict[str, Any],
    policy: ModelTokenPolicy,
) -> list[PassOneGroup]:
    """Pack complete conversations into deterministic first-pass request groups."""
    placeholder_group_id = "P1G0000-000000000000"
    fixed_input_tokens = (
        estimate_tokens(system_prompt)
        + estimate_tokens(shared_payload)
        + estimate_tokens(FIXED_EVALUATION_USER_MESSAGE)
        + _MESSAGE_PROTOCOL_OVERHEAD
    )

    def fits(candidate: list[PassOneUnit]) -> bool:
        input_tokens = max(
            final_request_input_tokens(
                system_prompt,
                build_pass_one_payload(placeholder_group_id, candidate, shared_payload),
            ),
            fixed_input_tokens + sum(unit.estimated_input_tokens for unit in candidate),
        )
        output_tokens = pass_one_output_reserve(
            len(candidate),
            sum(unit.user_event_count for unit in candidate),
            policy,
        )
        return (
            input_tokens <= input_limit(policy)
            and output_tokens <= policy.max_output_tokens
            and input_tokens + output_tokens + policy.safety_margin <= policy.context_limit
        )

    ordered = sorted(
        units,
        key=lambda unit: (unit.estimated_input_tokens, unit.conversation_id),
        reverse=True,
    )
    for unit in ordered:
        if not fits([unit]):
            raise ValueError(f"Conversation exceeds Pass 1 token limit: {unit.conversation_id}")

    if fits(ordered):
        groups = [ordered]
    else:
        # Start with a deterministic best-fit upper bound, then use branch-and-bound
        # to prove the smallest safe group count. Conversation counts are small and
        # symmetric aggregate states are memoized, so the exact search stays bounded.
        greedy: list[list[PassOneUnit]] = []
        for unit in ordered:
            placements = [
                (index, [*members, unit])
                for index, members in enumerate(greedy)
                if fits([*members, unit])
            ]
            if placements:
                best_index, _candidate = min(
                    placements,
                    key=lambda placement: (
                        policy.context_limit
                        - final_request_input_tokens(
                            system_prompt,
                            build_pass_one_payload(
                                placeholder_group_id, placement[1], shared_payload
                            ),
                        )
                        - pass_one_output_reserve(
                            len(placement[1]),
                            sum(item.user_event_count for item in placement[1]),
                            policy,
                        ),
                        placement[0],
                    ),
                )
                greedy[best_index].append(unit)
            else:
                greedy.append([unit])

        best = [list(members) for members in greedy]
        fixed_input = fixed_input_tokens
        available_context = min(
            input_limit(policy) - fixed_input,
            policy.context_limit - fixed_input - policy.safety_margin,
        )
        total_input = sum(unit.estimated_input_tokens for unit in ordered)
        total_visible_output = sum(512 + unit.user_event_count * 192 for unit in ordered)
        lower_bound = max(
            1,
            math.ceil((total_input + total_visible_output) / available_context),
            math.ceil(total_visible_output / policy.max_output_tokens),
        )
        if lower_bound >= len(best):
            groups = best
        else:
            seen_states: set[tuple[int, tuple[tuple[int, int, int], ...]]] = set()

            def search(index: int, candidate_groups: list[list[PassOneUnit]]) -> None:
                nonlocal best
                if len(candidate_groups) >= len(best):
                    return
                remaining_input = sum(item.estimated_input_tokens for item in ordered[index:])
                free_context = sum(
                    max(
                        0,
                        available_context
                        - sum(item.estimated_input_tokens for item in members)
                        - sum(512 + item.user_event_count * 192 for item in members),
                    )
                    for members in candidate_groups
                )
                remaining_output = sum(
                    512 + item.user_event_count * 192 for item in ordered[index:]
                )
                extra_groups = max(
                    0,
                    math.ceil(
                        max(0, remaining_input + remaining_output - free_context)
                        / available_context
                    ),
                )
                if len(candidate_groups) + extra_groups >= len(best):
                    return
                if index == len(ordered):
                    best = [list(members) for members in candidate_groups]
                    return
                signature = tuple(
                    sorted(
                        (
                            sum(item.estimated_input_tokens for item in members),
                            sum(item.user_event_count for item in members),
                            len(members),
                        )
                        for members in candidate_groups
                    )
                )
                state = (index, signature)
                if state in seen_states:
                    return
                seen_states.add(state)

                unit = ordered[index]
                tried: set[tuple[int, int, int]] = set()
                for members in candidate_groups:
                    aggregate = (
                        sum(item.estimated_input_tokens for item in members),
                        sum(item.user_event_count for item in members),
                        len(members),
                    )
                    if aggregate in tried or not fits([*members, unit]):
                        continue
                    tried.add(aggregate)
                    members.append(unit)
                    search(index + 1, candidate_groups)
                    members.pop()
                if len(candidate_groups) + 1 < len(best):
                    candidate_groups.append([unit])
                    search(index + 1, candidate_groups)
                    candidate_groups.pop()

            search(0, [])
            groups = best

    for members in groups:
        members.sort(key=lambda unit: unit.conversation_id)
    groups.sort(key=lambda members: members[0].conversation_id)

    result: list[PassOneGroup] = []
    seen: set[str] = set()
    for index, members in enumerate(groups, start=1):
        conversation_ids = tuple(unit.conversation_id for unit in members)
        if seen.intersection(conversation_ids):
            raise ValueError("Pass 1 packing produced duplicate conversations")
        seen.update(conversation_ids)
        membership = json.dumps(conversation_ids, ensure_ascii=False, separators=(",", ":"))
        digest = hashlib.sha256(f"{batch_id}:pass1:{membership}".encode()).hexdigest()
        result.append(
            PassOneGroup(
                group_id=f"P1G{index:04d}-{digest[:12]}",
                idempotency_key=digest,
                units=tuple(members),
                estimated_input_tokens=max(
                    final_request_input_tokens(
                        system_prompt,
                        build_pass_one_payload(
                            f"P1G{index:04d}-{digest[:12]}", members, shared_payload
                        ),
                    ),
                    fixed_input_tokens + sum(unit.estimated_input_tokens for unit in members),
                ),
                reserved_output_tokens=pass_one_output_reserve(
                    len(members),
                    sum(unit.user_event_count for unit in members),
                    policy,
                ),
            )
        )
    if seen != {unit.conversation_id for unit in units}:
        raise ValueError("Pass 1 packing omitted conversations")
    return result


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
    shared_payload: dict[str, Any] | None = None,
) -> list[PassTwoGroup]:
    """Pack units into the minimum safe number of deterministic request groups."""
    shared_payload = shared_payload or {}
    placeholder_group_id = "G0000-000000000000"
    fixed_input_tokens = (
        estimate_tokens(system_prompt)
        + estimate_tokens(shared_payload)
        + estimate_tokens(FIXED_EVALUATION_USER_MESSAGE)
        + _MESSAGE_PROTOCOL_OVERHEAD
    )
    ordered = sorted(units, key=lambda unit: unit.conversation_id)
    groups: list[list[ConversationUnit]] = []

    def fits(candidate: list[ConversationUnit]) -> bool:
        if len({unit.conversation_id for unit in candidate}) != len(candidate):
            return False
        input_tokens = max(
            final_request_input_tokens(
                system_prompt,
                build_pass_two_payload(placeholder_group_id, candidate, shared_payload),
            ),
            fixed_input_tokens + sum(unit.estimated_input_tokens for unit in candidate),
        )
        cases = sum(len(unit.case_keys) for unit in candidate)
        reserved_output = output_reserve(cases, policy)
        return (
            input_tokens <= input_limit(policy)
            and reserved_output <= policy.max_output_tokens
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
            input_tokens = max(
                final_request_input_tokens(
                    system_prompt,
                    build_pass_two_payload(placeholder_group_id, candidate, shared_payload),
                ),
                fixed_input_tokens + sum(unit.estimated_input_tokens for unit in candidate),
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
                estimated_input_tokens=max(
                    final_request_input_tokens(
                        system_prompt,
                        build_pass_two_payload(
                            f"G{index:04d}-{digest[:12]}", members, shared_payload
                        ),
                    ),
                    fixed_input_tokens + sum(unit.estimated_input_tokens for unit in members),
                ),
                reserved_output_tokens=output_reserve(len(case_keys), policy),
            )
        )
    expected = {case for unit in units for case in unit.case_keys}
    if seen != expected:
        raise ValueError("Pass 2 packing omitted Cases")
    return result


def split_group(
    *,
    batch_id: str,
    parent: PassTwoGroup,
    system_prompt: str,
    policy: ModelTokenPolicy,
    shared_payload: dict[str, Any] | None = None,
) -> tuple[PassTwoGroup, ...]:
    """Split a failed group at a complete-conversation boundary.

    The split is deterministic so a restart produces the same child identities.
    A single conversation is intentionally indivisible because its full history is
    required to judge every Case in that conversation.
    """
    if len(parent.units) < 2:
        return ()
    ordered = sorted(parent.units, key=lambda unit: unit.conversation_id)
    total_weight = sum(
        unit.estimated_input_tokens + unit.reserved_output_tokens for unit in ordered
    )
    running_weight = 0
    split_index = 1
    best_distance: int | None = None
    for index, unit in enumerate(ordered[:-1], start=1):
        running_weight += unit.estimated_input_tokens + unit.reserved_output_tokens
        distance = abs(total_weight - 2 * running_weight)
        if best_distance is None or distance < best_distance:
            best_distance = distance
            split_index = index
    children: list[PassTwoGroup] = []
    for side, members in zip(
        ("left", "right"),
        (ordered[:split_index], ordered[split_index:]),
        strict=True,
    ):
        child = pack_units(
            batch_id=f"{batch_id}:split:{parent.group_id}:{side}",
            units=list(members),
            system_prompt=system_prompt,
            policy=policy,
            shared_payload=shared_payload,
        )
        if len(child) != 1:
            raise ValueError("Adaptive Pass 2 split produced an unstable child group")
        children.append(child[0])
    return children[0], children[1]
