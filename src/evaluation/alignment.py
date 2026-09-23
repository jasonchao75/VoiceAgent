"""Align historical dialogue events to diarized full-call ASR timelines."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from hashlib import sha256
from itertools import combinations
from pathlib import Path
from typing import Any

import soundfile as sf  # type: ignore[import-untyped]

_ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]")
_NON_WORD = re.compile(r"[^\w\u0600-\u06ff]+", re.UNICODE)
_UNKNOWN_SPEAKERS = {"", "none", "null", "unknown", "uu"}
_DIGIT_WORDS = {
    "zero": "0",
    "oh": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "صفر": "0",
    "واحد": "1",
    "واحدة": "1",
    "اثنان": "2",
    "اثنين": "2",
    "ثلاثة": "3",
    "اربعة": "4",
    "أربعة": "4",
    "خمسة": "5",
    "ستة": "6",
    "سبعة": "7",
    "ثمانية": "8",
    "تسعة": "9",
}
_AUDIO_ISLAND_DETECTOR_VERSION = "rms-silence-v1"


def normalize_alignment_text(value: str) -> dict[str, Any]:
    """Keep raw text plus comparable normalized, digit, and numeric forms."""
    normalized = _normalize_text(value)
    digits: list[str] = []
    for token in normalized.split():
        mapped = _DIGIT_WORDS.get(token)
        if mapped is not None:
            digits.append(mapped)
            continue
        for character in token:
            try:
                digits.append(str(unicodedata.digit(character)))
            except (TypeError, ValueError):
                continue
    digit_sequence = "|".join(digits) if digits else None
    return {
        "raw": value,
        "normalized": normalized,
        "digit_sequence": digit_sequence,
        "numeric_value": int("".join(digits)) if digits else None,
    }


def detect_audio_islands(
    source: Path,
    conversation_id: str,
) -> list[dict[str, Any]]:
    """Freeze ordered speech islands directly from one pure-user WAV track."""
    import numpy as np

    data, sample_rate = sf.read(source, always_2d=True, dtype="float32")
    if len(data) == 0 or sample_rate <= 0:
        raise ValueError("Pure-user WAV contains no audio frames")
    mono = np.max(np.abs(data), axis=1)
    frame_seconds = 0.02
    frame_size = max(1, round(sample_rate * frame_seconds))
    frame_count = int(np.ceil(len(mono) / frame_size))
    padded = np.pad(mono, (0, frame_count * frame_size - len(mono)))
    framed = padded.reshape(frame_count, frame_size)
    rms = np.sqrt(np.mean(np.square(framed), axis=1))
    noise = float(np.percentile(rms, 30))
    peak = float(np.percentile(rms, 99))
    threshold = max(0.0015, noise * 3.0, peak * 0.08)
    active = rms >= threshold
    max_gap_frames = max(1, round(0.25 / frame_seconds))
    active_indices = np.flatnonzero(active)
    for left, right in zip(active_indices[:-1], active_indices[1:], strict=False):
        if 1 < right - left <= max_gap_frames + 1:
            active[left : right + 1] = True
    minimum_frames = max(1, round(0.12 / frame_seconds))
    components: list[tuple[int, int]] = []
    start: int | None = None
    for index, is_active in enumerate((*active.tolist(), False)):
        if is_active and start is None:
            start = index
        elif not is_active and start is not None:
            if index - start >= minimum_frames:
                components.append((start, index))
            start = None
    duration = len(data) / sample_rate
    islands: list[dict[str, Any]] = []
    for start_frame, end_frame in components:
        start_s = max(0.0, start_frame * frame_seconds - 0.08)
        end_s = min(duration, end_frame * frame_seconds + 0.12)
        if islands and start_s <= float(islands[-1]["end_s"]):
            islands[-1]["end_s"] = end_s
            islands[-1]["features"]["active_frame_count"] += end_frame - start_frame
            continue
        islands.append(
            {
                "island_id": f"{conversation_id}:island:{len(islands)}",
                "ordinal": len(islands),
                "start_s": round(start_s, 6),
                "end_s": round(end_s, 6),
                "detector_version": _AUDIO_ISLAND_DETECTOR_VERSION,
                "parameters": {
                    "frame_ms": 20,
                    "max_gap_ms": 250,
                    "minimum_active_ms": 120,
                    "leading_pad_ms": 80,
                    "trailing_pad_ms": 120,
                    "threshold": threshold,
                },
                "features": {
                    "active_frame_count": end_frame - start_frame,
                    "peak_rms": peak,
                    "noise_rms": noise,
                },
            }
        )
    return islands


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
            failures.append({"provider": str(item["provider"]), "reason": "excluded_no_overlap"})
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


def _overlap_seconds(
    left_start: float,
    left_end: float,
    right_start: float,
    right_end: float,
) -> float:
    """Return the positive overlap between two half-open timeline intervals."""
    return max(0.0, min(left_end, right_end) - max(left_start, right_start))


def _adjacent_robot_context(
    events: list[dict[str, Any]],
    event: dict[str, Any],
) -> dict[str, str]:
    """Return nearest worksheet robot text on either side without using time."""
    try:
        event_index = next(index for index, item in enumerate(events) if item is event)
    except StopIteration:
        return {"previous": "", "following": ""}
    previous = next(
        (
            str(item.get("text") or "")
            for item in reversed(events[:event_index])
            if item.get("speaker") == "robot"
        ),
        "",
    )
    following = next(
        (
            str(item.get("text") or "")
            for item in events[event_index + 1 :]
            if item.get("speaker") == "robot"
        ),
        "",
    )
    return {"previous": previous, "following": following}


def _provider_consistency(provider_evidence: list[dict[str, Any]]) -> float:
    """Measure agreement between provider texts selected for one frozen island."""
    similarities = [
        _text_similarity(str(left.get("text") or ""), str(right.get("text") or ""))
        for left, right in combinations(provider_evidence, 2)
    ]
    return sum(similarities) / len(similarities) if similarities else 0.0


def _provider_evidence_conflicts(provider_evidence: list[dict[str, Any]]) -> list[str]:
    """Return only strong deterministic conflicts; weaker differences remain ranking evidence."""
    reasons: list[str] = []
    digit_sequences = {
        str(item.get("text_forms", {}).get("digit_sequence"))
        for item in provider_evidence
        if item.get("text_forms", {}).get("digit_sequence")
    }
    if len(digit_sequences) > 1:
        reasons.append("provider_digit_conflict")
    if any(item.get("inferred_role") == "robot" for item in provider_evidence):
        reasons.append("provider_turn_role_conflict")
    pairwise = [
        _text_similarity(str(left.get("text") or ""), str(right.get("text") or ""))
        for left, right in combinations(provider_evidence, 2)
    ]
    if pairwise and max(pairwise) < 0.08:
        reasons.append("provider_semantic_conflict")
    return reasons


def _event_island_score(
    event: dict[str, Any],
    provider_evidence: list[dict[str, Any]],
    robot_context: dict[str, str],
) -> dict[str, Any]:
    """Rank one already-legal pair and retain auditable evidence components."""
    event_forms = normalize_alignment_text(str(event.get("text") or ""))
    similarities: list[float] = []
    digit_matches = 0
    context_scores: list[float] = []
    for evidence in provider_evidence:
        turn_forms = evidence["text_forms"]
        similarities.append(_text_similarity(event_forms["raw"], turn_forms["raw"]))
        if (
            event_forms["digit_sequence"]
            and event_forms["digit_sequence"] == turn_forms["digit_sequence"]
        ):
            digit_matches += 1
        provider_context = evidence.get("adjacent_context") or {}
        for direction in ("previous", "following"):
            historical_text = robot_context.get(direction, "")
            provider_text = str(provider_context.get(direction) or "")
            if historical_text and provider_text:
                context_scores.append(_text_similarity(historical_text, provider_text))
    customer_text_score = sum(similarities) / len(similarities) if similarities else 0.0
    digit_score = min(0.5, digit_matches * 0.25)
    robot_context_score = sum(context_scores) / len(context_scores) if context_scores else 0.0
    provider_consistency = _provider_consistency(provider_evidence)
    total = (
        customer_text_score + digit_score + robot_context_score * 0.65 + provider_consistency * 0.35
    )
    return {
        "total": round(total, 6),
        "customer_text": round(customer_text_score, 6),
        "digit_match": round(digit_score, 6),
        "adjacent_robot_context": round(robot_context_score, 6),
        "cross_provider_consistency": round(provider_consistency, 6),
        "historical_robot_context": {
            key: normalize_alignment_text(value) for key, value in robot_context.items() if value
        },
    }


def _assignment_paths(event_count: int, island_count: int) -> list[tuple[int, ...]]:
    """Enumerate bounded monotonic paths, including adjacent event merges."""
    if event_count <= 0 or island_count <= 0:
        return []
    if island_count == 1:
        return [(0,) * event_count]
    if event_count == island_count:
        return [tuple(range(event_count))]
    if event_count > island_count:
        if event_count > 24:
            return []
        paths: list[tuple[int, ...]] = []
        for boundaries in combinations(range(1, event_count), island_count - 1):
            starts = (0, *boundaries)
            ends = (*boundaries, event_count)
            paths.append(
                tuple(
                    island_index
                    for island_index, (start, end) in enumerate(zip(starts, ends, strict=True))
                    for _ in range(start, end)
                )
            )
            if len(paths) > 20_000:
                return []
        return paths
    if island_count > 24:
        return []
    return [tuple(path) for path in combinations(range(island_count), event_count)]


def build_audio_first_cases(
    conversation_id: str,
    events: list[dict[str, Any]],
    target_event_ids: list[str],
    islands: list[dict[str, Any]],
    provider_results: list[dict[str, Any]],
    minimum_provider_projections: int = 2,
    selected_assignment: tuple[int, ...] | None = None,
    selected_provider_turn_ids: dict[str, dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Map ordered historical events to frozen islands and project provider turns."""
    target_set = set(target_event_ids)
    customer_events = [event for event in events if event.get("speaker") == "customer"]
    missing = target_set - {str(event.get("event_id")) for event in customer_events}
    if missing:
        raise ValueError("Target event is not a customer event")
    if not islands:
        return []

    provider_by_island: dict[int, list[dict[str, Any]]] = {
        index: [] for index in range(len(islands))
    }
    turn_islands: dict[str, set[int]] = {}
    for provider_result in provider_results:
        provider = str(provider_result.get("provider") or "")
        if not provider:
            continue
        provider_turns = _provider_turns(provider_result)
        ordered_mapping = _ordered_alignment(events, provider_turns)
        speaker_roles = _speaker_roles(events, provider_turns, ordered_mapping)
        inferred_roles: list[str] = []
        for turn in provider_turns:
            role_scores = speaker_roles.get(turn.speaker, {})
            robot_score = float(role_scores.get("robot", 0.0))
            customer_score = float(role_scores.get("customer", 0.0))
            if robot_score >= customer_score + 0.15:
                inferred_roles.append("robot")
            elif customer_score >= robot_score + 0.15:
                inferred_roles.append("customer")
            else:
                inferred_roles.append("unknown")
        for turn_index, turn in enumerate(provider_turns):
            turn_id = f"{conversation_id}:{provider}:turn:{turn_index}"
            overlaps = []
            for island_index, island in enumerate(islands):
                overlap = _overlap_seconds(
                    turn.start_s,
                    turn.end_s,
                    float(island["start_s"]),
                    float(island["end_s"]),
                )
                if overlap > 0:
                    overlaps.append((island_index, overlap))
            turn_islands[turn_id] = {item[0] for item in overlaps}
            for island_index, overlap in overlaps:
                provider_by_island[island_index].append(
                    {
                        "provider": provider,
                        "turn_id": turn_id,
                        "turn_index": turn_index,
                        "speaker": turn.speaker,
                        "start_s": turn.start_s,
                        "end_s": turn.end_s,
                        "text": turn.text,
                        "text_forms": normalize_alignment_text(turn.text),
                        "inferred_role": inferred_roles[turn_index],
                        "speaker_role_scores": {
                            key: round(float(value), 6)
                            for key, value in speaker_roles.get(turn.speaker, {}).items()
                        },
                        "adjacent_context": {
                            "previous": (
                                provider_turns[turn_index - 1].text
                                if turn_index > 0 and inferred_roles[turn_index - 1] == "robot"
                                else ""
                            ),
                            "following": (
                                provider_turns[turn_index + 1].text
                                if turn_index + 1 < len(provider_turns)
                                and inferred_roles[turn_index + 1] == "robot"
                                else ""
                            ),
                        },
                        "overlap_s": round(overlap, 6),
                        "segment_ids": list(turn.segment_ids),
                    }
                )

    selected_evidence: dict[int, list[dict[str, Any]]] = {}
    spanning_islands: set[int] = set()
    for island_index, rows in provider_by_island.items():
        by_provider: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            by_provider.setdefault(str(row["provider"]), []).append(row)
        selected: list[dict[str, Any]] = []
        for _provider, candidates in sorted(by_provider.items()):
            candidates.sort(
                key=lambda item: (
                    {"customer": 0, "unknown": 1, "robot": 2}.get(
                        str(item.get("inferred_role")), 1
                    ),
                    -float(item["overlap_s"]),
                    int(item["turn_index"]),
                )
            )
            provider = str(candidates[0]["provider"])
            requested_turn_id = (
                (selected_provider_turn_ids or {})
                .get(str(islands[island_index]["island_id"]), {})
                .get(provider)
            )
            chosen = next(
                (item for item in candidates if str(item["turn_id"]) == str(requested_turn_id)),
                candidates[0],
            )
            best = dict(chosen)
            best["status"] = "mapped"
            selected.append(best)
            if len(turn_islands[str(best["turn_id"])]) > 1:
                spanning_islands.update(turn_islands[str(best["turn_id"])])
        selected_evidence[island_index] = selected

    robot_contexts = [_adjacent_robot_context(events, event) for event in customer_events]
    scores = [
        [
            _event_island_score(
                event,
                selected_evidence[island_index],
                robot_contexts[event_index],
            )
            for island_index in range(len(islands))
        ]
        for event_index, event in enumerate(customer_events)
    ]
    paths = _assignment_paths(len(customer_events), len(islands))
    if not paths:
        # Persist an ordered best-effort shape for manual review without claiming success.
        denominator = max(1, len(customer_events) - 1)
        path = tuple(
            min(len(islands) - 1, round(index * (len(islands) - 1) / denominator))
            for index in range(len(customer_events))
        )
        ambiguous_path = True
        candidate_paths = [path]
    else:
        ranked = sorted(
            (
                (
                    sum(float(scores[index][island]["total"]) for index, island in enumerate(path)),
                    path,
                )
                for path in paths
            ),
            key=lambda item: (-item[0], item[1]),
        )
        candidate_paths = [
            candidate_path
            for score, candidate_path in ranked[:8]
            if ranked[0][0] - score < 0.15 or candidate_path == ranked[0][1]
        ]
        if selected_assignment is not None:
            if selected_assignment not in paths:
                raise ValueError("Selected assignment is not a legal monotonic path")
            path = selected_assignment
            ambiguous_path = False
        else:
            path = ranked[0][1]
            ambiguous_path = len(ranked) > 1 and (
                ranked[0][0] <= 0.0 or ranked[0][0] - ranked[1][0] < 0.15
            )

    assignment_candidates = [
        {
            "assignment_id": f"assignment-{index}",
            "path": list(candidate_path),
            "score": round(
                sum(
                    float(scores[event_index][island_index]["total"])
                    for event_index, island_index in enumerate(candidate_path)
                ),
                6,
            ),
            "event_islands": [
                {
                    "event_id": str(event["event_id"]),
                    "island_id": str(islands[island_index]["island_id"]),
                    "ranking_evidence": scores[event_index][island_index],
                }
                for event_index, (event, island_index) in enumerate(
                    zip(customer_events, candidate_path, strict=True)
                )
            ],
        }
        for index, candidate_path in enumerate(candidate_paths)
    ]

    grouped_events: dict[int, list[dict[str, Any]]] = {}
    for event, island_index in zip(customer_events, path, strict=True):
        grouped_events.setdefault(island_index, []).append(event)
    cases: list[dict[str, Any]] = []
    for island_index, source_events in sorted(grouped_events.items()):
        source_event_ids = [str(event["event_id"]) for event in source_events]
        target_ids = [event_id for event_id in source_event_ids if event_id in target_set]
        if not target_ids:
            continue
        island = islands[island_index]
        case_identity = "|".join((conversation_id, str(island["island_id"]), *source_event_ids))
        evidence = selected_evidence.get(island_index, [])
        status = "deterministic_aligned"
        ambiguity_reasons: list[str] = []
        if ambiguous_path:
            ambiguity_reasons.append("non_unique_monotonic_assignment")
        if island_index in spanning_islands:
            ambiguity_reasons.append("provider_turn_spans_multiple_islands")
        if len({str(item["provider"]) for item in evidence}) < minimum_provider_projections:
            ambiguity_reasons.append("fewer_than_two_provider_projections")
        ambiguity_reasons.extend(_provider_evidence_conflicts(evidence))
        ambiguity_reasons = list(dict.fromkeys(ambiguity_reasons))
        if ambiguity_reasons:
            status = "ambiguous"
        elif selected_assignment is not None or selected_provider_turn_ids:
            status = "llm_assisted_aligned"
        cases.append(
            {
                "case_id": f"CASE-{sha256(case_identity.encode()).hexdigest()[:20]}",
                "conversation_id": conversation_id,
                "primary_event_id": source_event_ids[0],
                "target_event_ids": target_ids,
                "source_event_ids": source_event_ids,
                "audio_island_id": str(island["island_id"]),
                "start_s": float(island["start_s"]),
                "end_s": float(island["end_s"]),
                "boundary_rule": "pure_user_audio_island_v1",
                "alignment_method": (
                    "llm_assisted_audio_first_v1"
                    if selected_assignment is not None or selected_provider_turn_ids
                    else "monotonic_audio_first_v1"
                ),
                "alignment_status": status,
                "ambiguity_reasons": ambiguity_reasons,
                "historical_time_used": False,
                "historical_text_forms": [
                    normalize_alignment_text(str(event.get("text") or ""))
                    for event in source_events
                ],
                "ranking_evidence": [
                    {
                        "event_id": str(event["event_id"]),
                        "island_id": str(island["island_id"]),
                        **scores[customer_events.index(event)][island_index],
                    }
                    for event in source_events
                ],
                "providers": evidence,
                "provider_candidates": provider_by_island.get(island_index, []),
                "all_island_evidence": {
                    str(islands[index]["island_id"]): rows
                    for index, rows in selected_evidence.items()
                },
                "full_event_assignment": [
                    {
                        "event_id": str(event["event_id"]),
                        "island_id": str(islands[assigned_island]["island_id"]),
                    }
                    for event, assigned_island in zip(customer_events, path, strict=True)
                ],
                "all_ranking_evidence": [
                    {
                        "event_id": str(event["event_id"]),
                        "island_id": str(islands[candidate_island]["island_id"]),
                        **scores[event_index][candidate_island],
                    }
                    for event_index, event in enumerate(customer_events)
                    for candidate_island in range(len(islands))
                ],
                "assignment_candidates": assignment_candidates,
                "island": island,
            }
        )
    return cases


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
