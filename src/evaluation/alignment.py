"""Align historical dialogue events to diarized full-call ASR timelines."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from itertools import combinations
from typing import Any

_ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]")
_NON_WORD = re.compile(r"[^\w\u0600-\u06ff]+", re.UNICODE)
_UNKNOWN_SPEAKERS = {"", "none", "null", "unknown", "uu"}


@dataclass(frozen=True)
class _Turn:
    """One adjacent same-speaker span from a provider timeline."""

    start_s: float
    end_s: float
    speaker: str
    text: str
    segment_ids: tuple[str, ...]


def build_turn_catalog(
    conversation_id: str, provider_results: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Expose stable selectable turn IDs while retaining server-side timestamps."""
    providers: list[dict[str, Any]] = []
    lookup: dict[str, dict[str, Any]] = {}
    seen_providers: set[str] = set()
    for provider_result in provider_results:
        provider = str(provider_result.get("provider") or "")
        if not provider or provider in seen_providers:
            continue
        seen_providers.add(provider)
        turns: list[dict[str, Any]] = []
        for index, turn in enumerate(_provider_turns(provider_result)):
            turn_id = f"{conversation_id}:{provider}:turn:{index}"
            item = {
                "turn_id": turn_id,
                "speaker": turn.speaker,
                "start_s": turn.start_s,
                "end_s": turn.end_s,
                "text": turn.text,
            }
            turns.append(item)
            lookup[turn_id] = {
                **item,
                "provider": provider,
                "segment_ids": list(turn.segment_ids),
                "turn_index": index,
            }
        providers.append({"provider": provider, "turns": turns})
    return providers, lookup


def align_customer_event_from_mapping(
    events: list[dict[str, Any]],
    event_id: str,
    provider_results: list[dict[str, Any]],
    event_mapping: dict[str, Any],
) -> dict[str, Any]:
    """Validate selected real turn IDs and return their non-contracting union."""
    target_index = next(
        (index for index, event in enumerate(events) if str(event.get("event_id")) == event_id),
        None,
    )
    if target_index is None or events[target_index].get("speaker") != "customer":
        raise ValueError("Target event is not a customer event")
    if str(event_mapping.get("event_id") or "") != event_id:
        raise ValueError("Event Aligner mapping does not match the target event")
    _providers, lookup = build_turn_catalog(
        str(event_mapping.get("conversation_id") or "conversation"), provider_results
    )
    provider_rows = event_mapping.get("providers")
    if not isinstance(provider_rows, list):
        raise ValueError("Event Aligner omitted provider mappings")
    accepted: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in provider_rows:
        if not isinstance(row, dict):
            raise ValueError("Event Aligner provider mapping must be an object")
        provider = str(row.get("provider") or "")
        status = str(row.get("status") or "")
        if not provider or provider in seen:
            raise ValueError("Event Aligner returned a missing or duplicate provider")
        seen.add(provider)
        if status != "mapped":
            failures.append({"provider": provider, "reason": status or "missing"})
            continue
        turn_id = str(row.get("turn_id") or "")
        turn = lookup.get(turn_id)
        if turn is None or turn["provider"] != provider:
            raise ValueError("Event Aligner selected an unknown provider turn_id")
        accepted.append(dict(turn))

    consensus_candidates: list[list[dict[str, Any]]] = []
    for size in range(2, len(accepted) + 1):
        for subset_tuple in combinations(accepted, size):
            subset = list(subset_tuple)
            if max(float(item["start_s"]) for item in subset) < min(
                float(item["end_s"]) for item in subset
            ):
                consensus_candidates.append(subset)
    if not consensus_candidates:
        raise ValueError("Fewer than two Event Aligner provider turns overlap")
    largest_size = max(len(candidate) for candidate in consensus_candidates)
    largest = [candidate for candidate in consensus_candidates if len(candidate) == largest_size]
    unique_memberships = {
        tuple(sorted(str(item["turn_id"]) for item in candidate)) for candidate in largest
    }
    if len(unique_memberships) != 1:
        raise ValueError("Event Aligner provider turns form competing intervals")
    consensus = largest[0]
    consensus_ids = {str(item["turn_id"]) for item in consensus}
    for item in accepted:
        if str(item["turn_id"]) not in consensus_ids:
            failures.append(
                {"provider": str(item["provider"]), "reason": "excluded_no_overlap"}
            )
    start_s = min(float(item["start_s"]) for item in consensus)
    end_s = max(float(item["end_s"]) for item in consensus)
    if start_s < 0 or end_s <= start_s:
        raise ValueError("Event Aligner union interval is invalid")
    return {
        "start_s": start_s,
        "end_s": end_s,
        "consensus_start_s": max(float(item["start_s"]) for item in consensus),
        "consensus_end_s": min(float(item["end_s"]) for item in consensus),
        "boundary_rule": "event_aligner_provider_union_v1",
        "consensus_providers": [str(item["provider"]) for item in consensus],
        "provider_alignments": consensus,
        "provider_failures": failures,
        "excel_time_used": False,
    }


def _normalize_text(value: str) -> str:
    """Normalize multilingual transcript text for approximate alignment."""
    normalized = unicodedata.normalize("NFKC", value).casefold().replace("ـ", "")
    normalized = _ARABIC_DIACRITICS.sub("", normalized)
    for source, replacement in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ٱ", "ا"), ("ى", "ي")):
        normalized = normalized.replace(source, replacement)
    return " ".join(_NON_WORD.sub(" ", normalized).split())


def _text_similarity(left: str, right: str) -> float:
    """Return a character-and-token similarity robust to punctuation differences."""
    normalized_left = _normalize_text(left)
    normalized_right = _normalize_text(right)
    if not normalized_left or not normalized_right:
        return 0.0
    compact_left = normalized_left.replace(" ", "")
    compact_right = normalized_right.replace(" ", "")
    character_score = SequenceMatcher(None, compact_left, compact_right).ratio()
    left_tokens = set(normalized_left.split())
    right_tokens = set(normalized_right.split())
    token_score = len(left_tokens & right_tokens) / max(1, len(left_tokens | right_tokens))
    containment_score = 0.0
    if compact_left in compact_right or compact_right in compact_left:
        containment_score = min(len(compact_left), len(compact_right)) / max(
            len(compact_left), len(compact_right)
        )
    return max(character_score, token_score, containment_score)


def _provider_turns(result: dict[str, Any]) -> list[_Turn]:
    """Collapse provider word tokens into timestamped same-speaker turns."""
    normalized: list[tuple[float, float, str, str, str]] = []
    previous_speaker = ""
    for index, segment in enumerate(result.get("segments") or []):
        if not isinstance(segment, dict):
            continue
        try:
            start_s = float(segment["start"])
            end_s = float(segment["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if start_s < 0 or end_s <= start_s:
            continue
        text = str(segment.get("text") or "").strip()
        if not _normalize_text(text):
            continue
        speaker = str(segment.get("speaker") or "").strip()
        if speaker.casefold() in _UNKNOWN_SPEAKERS:
            speaker = previous_speaker
        if not speaker:
            continue
        previous_speaker = speaker
        segment_id = str(segment.get("segment_id") or f"segment-{index}")
        normalized.append((start_s, end_s, speaker, text, segment_id))
    normalized.sort(key=lambda item: (item[0], item[1]))
    turns: list[_Turn] = []
    for start_s, end_s, speaker, text, segment_id in normalized:
        previous = turns[-1] if turns else None
        same_turn = (
            previous is not None
            and previous.speaker == speaker
            and start_s - previous.end_s <= 1.25
        )
        if same_turn:
            assert previous is not None
            turns[-1] = _Turn(
                start_s=previous.start_s,
                end_s=max(previous.end_s, end_s),
                speaker=speaker,
                text=f"{previous.text} {text}".strip(),
                segment_ids=(*previous.segment_ids, segment_id),
            )
        else:
            turns.append(
                _Turn(
                    start_s=start_s,
                    end_s=end_s,
                    speaker=speaker,
                    text=text,
                    segment_ids=(segment_id,),
                )
            )
    return turns


def _ordered_alignment(
    events: list[dict[str, Any]], turns: list[_Turn]
) -> dict[int, tuple[int, float]]:
    """Align ordered worksheet events to ordered ASR turns without using event time."""
    event_count = len(events)
    turn_count = len(turns)
    scores = [
        [_text_similarity(str(event.get("text") or ""), turn.text) for turn in turns]
        for event in events
    ]
    dp = [[float("-inf")] * (turn_count + 1) for _ in range(event_count + 1)]
    action = [[""] * (turn_count + 1) for _ in range(event_count + 1)]
    dp[0][0] = 0.0
    for event_index in range(event_count + 1):
        for turn_index in range(turn_count + 1):
            current = dp[event_index][turn_index]
            if current == float("-inf"):
                continue
            if event_index < event_count and current - 0.12 > dp[event_index + 1][turn_index]:
                dp[event_index + 1][turn_index] = current - 0.12
                action[event_index + 1][turn_index] = "skip_event"
            if turn_index < turn_count and current - 0.06 > dp[event_index][turn_index + 1]:
                dp[event_index][turn_index + 1] = current - 0.06
                action[event_index][turn_index + 1] = "skip_turn"
            if event_index < event_count and turn_index < turn_count:
                similarity = scores[event_index][turn_index]
                match_value = current + similarity * 1.4 - 0.35
                if match_value > dp[event_index + 1][turn_index + 1]:
                    dp[event_index + 1][turn_index + 1] = match_value
                    action[event_index + 1][turn_index + 1] = "match"
    mapping: dict[int, tuple[int, float]] = {}
    event_index = event_count
    turn_index = turn_count
    while event_index or turn_index:
        step = action[event_index][turn_index]
        if step == "match":
            similarity = scores[event_index - 1][turn_index - 1]
            if similarity >= 0.35:
                mapping[event_index - 1] = (turn_index - 1, similarity)
            event_index -= 1
            turn_index -= 1
        elif step == "skip_event":
            event_index -= 1
        elif step == "skip_turn":
            turn_index -= 1
        else:
            break
    return mapping


def _speaker_roles(
    events: list[dict[str, Any]],
    turns: list[_Turn],
    mapping: dict[int, tuple[int, float]],
) -> dict[str, dict[str, float]]:
    """Infer anonymous provider speaker roles from aligned historical turns."""
    roles: dict[str, dict[str, float]] = {}
    for event_index, (turn_index, similarity) in mapping.items():
        if similarity < 0.48:
            continue
        role = str(events[event_index].get("speaker") or "")
        if role not in {"robot", "customer"}:
            continue
        scores = roles.setdefault(turns[turn_index].speaker, {"robot": 0.0, "customer": 0.0})
        scores[role] += similarity
    return roles


def _target_turn(
    events: list[dict[str, Any]],
    turns: list[_Turn],
    mapping: dict[int, tuple[int, float]],
    roles: dict[str, dict[str, float]],
    target_index: int,
) -> tuple[int, float, str]:
    """Resolve one customer event from direct text or its aligned turn neighbors."""
    direct = mapping.get(target_index)
    if direct is not None:
        turn_index, similarity = direct
        role_scores = roles.get(turns[turn_index].speaker, {})
        if similarity >= 0.42 and role_scores.get("customer", 0.0) >= role_scores.get("robot", 0.0):
            return turn_index, similarity, "direct_text_order"

    previous_turn = max(
        (
            turn_index
            for event_index, (turn_index, similarity) in mapping.items()
            if event_index < target_index and similarity >= 0.48
        ),
        default=-1,
    )
    following_turn = min(
        (
            turn_index
            for event_index, (turn_index, similarity) in mapping.items()
            if event_index > target_index and similarity >= 0.48
        ),
        default=len(turns),
    )
    candidates: list[tuple[int, float]] = []
    target_text = str(events[target_index].get("text") or "")
    for turn_index in range(previous_turn + 1, following_turn):
        turn = turns[turn_index]
        role_scores = roles.get(turn.speaker, {})
        if role_scores.get("robot", 0.0) > role_scores.get("customer", 0.0):
            continue
        candidates.append((turn_index, _text_similarity(target_text, turn.text)))
    if not candidates:
        raise ValueError("No customer speaker turn exists between aligned conversation turns")
    candidates.sort(key=lambda item: item[1], reverse=True)
    if len(candidates) > 1 and candidates[0][1] - candidates[1][1] < 0.08:
        raise ValueError("Full-call transcript maps the customer event to multiple speaker turns")
    if candidates[0][1] < 0.25 and len(candidates) > 1:
        raise ValueError("Customer event text is insufficient to select one diarized turn")
    return candidates[0][0], candidates[0][1], "neighbor_order_role"


def _provider_alignment(
    provider: str,
    events: list[dict[str, Any]],
    target_index: int,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Align one provider's diarized full-call transcript to a target event."""
    turns = _provider_turns(result)
    if len(turns) < 2 or len({turn.speaker for turn in turns}) < 2:
        raise ValueError("Provider did not return a usable diarized speaker timeline")
    mapping = _ordered_alignment(events, turns)
    roles = _speaker_roles(events, turns, mapping)
    turn_index, similarity, method = _target_turn(events, turns, mapping, roles, target_index)
    turn = turns[turn_index]
    role_scores = roles.get(turn.speaker, {"robot": 0.0, "customer": 0.0})
    return {
        "provider": provider,
        "start_s": turn.start_s,
        "end_s": turn.end_s,
        "speaker": turn.speaker,
        "segment_ids": list(turn.segment_ids),
        "text_similarity": round(similarity, 6),
        "alignment_method": method,
        "speaker_role_scores": {
            "robot": round(role_scores.get("robot", 0.0), 6),
            "customer": round(role_scores.get("customer", 0.0), 6),
        },
    }


def align_customer_event(
    events: list[dict[str, Any]],
    event_id: str,
    provider_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a two-provider consensus interval for one customer event.

    Args:
        events: Ordered worksheet events. Event timestamps are intentionally ignored.
        event_id: Target customer event identifier.
        provider_results: Completed full-call provider results including normalized segments.

    Returns:
        A traceable provider-consensus interval and its contributing alignments.

    Raises:
        ValueError: If the target is invalid or fewer than two providers agree.
    """
    target_index = next(
        (index for index, event in enumerate(events) if str(event.get("event_id")) == event_id),
        None,
    )
    if target_index is None or events[target_index].get("speaker") != "customer":
        raise ValueError("Target event is not a customer event")
    alignments: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    seen_providers: set[str] = set()
    for provider_result in provider_results:
        provider = str(provider_result.get("provider") or "")
        if not provider or provider in seen_providers:
            failures.append(
                {"provider": provider, "reason": "Provider identity is missing or duplicated"}
            )
            continue
        seen_providers.add(provider)
        try:
            alignments.append(_provider_alignment(provider, events, target_index, provider_result))
        except ValueError as exc:
            failures.append({"provider": provider, "reason": str(exc)})
    consensus_candidates: list[tuple[list[dict[str, Any]], float, float]] = []
    for size in range(2, len(alignments) + 1):
        for subset_tuple in combinations(alignments, size):
            subset = list(subset_tuple)
            common_start = max(float(item["start_s"]) for item in subset)
            common_end = min(float(item["end_s"]) for item in subset)
            if common_start < common_end:
                consensus_candidates.append((subset, common_start, common_end))
    if not consensus_candidates:
        raise ValueError("Fewer than two full-call ASR providers agree on the customer event")
    largest_size = max(len(candidate[0]) for candidate in consensus_candidates)
    largest = [candidate for candidate in consensus_candidates if len(candidate[0]) == largest_size]
    if len(largest) != 1:
        raise ValueError("Full-call ASR providers produced competing event intervals")
    consensus, start_s, end_s = largest[0]
    if start_s < 0 or end_s <= start_s or end_s - start_s > 20.0:
        raise ValueError("Full-call ASR consensus interval is invalid")
    return {
        "start_s": start_s,
        "end_s": end_s,
        "consensus_start_s": start_s,
        "consensus_end_s": end_s,
        "boundary_rule": "full_call_diarization_consensus_v1",
        "consensus_providers": [str(item["provider"]) for item in consensus],
        "provider_alignments": alignments,
        "provider_failures": failures,
        "excel_time_used": False,
    }
