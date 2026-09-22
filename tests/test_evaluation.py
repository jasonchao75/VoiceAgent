"""Tests for the source-backed ASR evaluation dataset and migration."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import inspect
import io
import json
import shutil
import stat
import time
import wave
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import aiosqlite
import httpx
import numpy as np
import pytest
import soundfile as sf  # type: ignore[import-untyped]
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.bots.crypto import BotKeyCipher
from src.evaluation.alignment import align_customer_event, align_customer_event_from_mapping
from src.evaluation.asr_contract import ASRError, ASRResult
from src.evaluation.connections import ASRConnectionError
from src.evaluation.connections import test_asr_connection as run_asr_connection_test
from src.evaluation.dataset import audit_dataset
from src.evaluation.executor import (
    EvaluationBudgetReached,
    EvaluationExecutionError,
    EvaluationRequestOutputTooLarge,
    EvaluationRequestTooLarge,
    EvaluationRunner,
    _asr_error,
    _completion_limit_field,
    _gemini_thinking_config,
    _render_prompt,
    _safe_execution_failure,
    _safe_structured_error,
    _structured_response_format,
    _structured_retry_correction,
)
from src.evaluation.imports import PackageUploadError, extract_package_archive
from src.evaluation.models import (
    EvaluationBatchAction,
    EvaluationBatchCreate,
    EvaluationContextWrite,
    EvaluationReviewSubmit,
    PromptTemplateRestore,
    PromptTemplateWrite,
)
from src.evaluation.pass2_packing import (
    ModelTokenPolicy,
    build_pass_one_unit,
    estimate_tokens,
    pass_one_output_reserve,
)
from src.evaluation.pricing import (
    OfficialPricingService,
    PricingSelection,
    PricingSyncError,
    PricingSyncRequest,
    estimate_llm_cost,
)
from src.evaluation.router import create_evaluation_router
from src.evaluation.storage import EvaluationStore

_VALID_CONVERSATION_ID = "1030000000086002"


def test_qwen_thinking_uses_prompt_json_contract_without_json_mode() -> None:
    """Qwen thinking must not send the provider-incompatible JSON-mode parameter."""
    assert _structured_response_format("qwen", True) is None
    assert _structured_response_format("qwen", True, "qwen3.8-max") == {"type": "json_object"}
    assert _structured_response_format("qwen", False) == {"type": "json_object"}
    assert _structured_response_format("deepseek", True) == {"type": "json_object"}


def test_structured_retry_correction_is_content_free_and_actionable() -> None:
    """A schema retry should tell the model what to repair without echoing its response."""
    correction = _structured_retry_correction(ValueError("Pass 2 group returned no results array"))

    assert "no results array" in correction
    assert "every required item exactly once" in correction
    assert "output only the required JSON object" in correction
    assert _safe_structured_error(json.JSONDecodeError("bad", "{", 1)) == ("schema_invalid_json")
    assert _safe_structured_error(ValueError("Pass 1 group omitted results")) == (
        "schema_contract: Pass 1 group omitted results"
    )
    assert _safe_structured_error(EvaluationRequestTooLarge("too large")) == (
        "preflight_input_limit"
    )
    assert _safe_structured_error(EvaluationRequestOutputTooLarge("too large")) == (
        "preflight_output_limit"
    )
    failure = _safe_execution_failure(
        EvaluationRequestTooLarge("One Pass 2 Case exceeds the pre-dispatch input limit."),
        "pass_2",
    )
    assert failure["category"] == "preflight_input_limit"
    assert failure["retryable"] is False
    output_failure = _safe_execution_failure(
        EvaluationRequestOutputTooLarge(
            "One Pass 2 Case exceeds the pre-dispatch generation limit."
        ),
        "pass_2",
    )
    assert output_failure["category"] == "preflight_output_limit"
    assert output_failure["retryable"] is False


@pytest.mark.asyncio
async def test_pass1_schema_retry_includes_correction_feedback(
    evaluation_store: EvaluationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A later attempt must not resend the same malformed-output request unchanged."""
    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="Corrective retry",
            asr_providers=["elevenlabs"],
            pass_1_model="deepseek-flash",
            pass_2_model="deepseek-flash",
            budget_limit=10,
            idempotency_key="corrective-pass1-retry-001",
        )
    )
    conversation = await evaluation_store.get_conversation(_VALID_CONVERSATION_ID)
    assert conversation is not None
    observed_payloads: list[dict[str, object]] = []
    observed_instructions: list[str | None] = []

    async def llm_json(
        _model_id: str,
        _prompt: str,
        payload: dict[str, object],
        **kwargs: object,
    ) -> dict[str, object]:
        observed_payloads.append(payload)
        observed_instructions.append(cast(str | None, kwargs.get("user_instruction")))
        if len(observed_payloads) == 1:
            raise ValueError("Pass 1 group omitted results")
        return {
            "request_group_id": payload["request_group_id"],
            "results": [
                {
                    "conversation_id": conversation["conversation_id"],
                    "event_results": [
                        {
                            "event_id": event["event_id"],
                            "decision": "pass",
                            "reason": "No ASR issue detected",
                        }
                        for event in conversation["events"]
                        if event["speaker"] == "customer"
                    ],
                    "issues": [],
                }
            ],
        }

    async def no_wait(_seconds: float) -> None:
        return None

    runner = EvaluationRunner(evaluation_store, cast(BotKeyCipher, object()))
    monkeypatch.setattr(runner, "_llm_json", llm_json)
    monkeypatch.setattr(asyncio, "sleep", no_wait)

    await runner._run_pass_one(batch["id"], [conversation])

    assert "retry_correction" not in observed_payloads[0]
    assert observed_instructions[0] is None
    assert "omitted results" in str(observed_instructions[1])
    assert observed_payloads[1] == observed_payloads[0]
    rows = await evaluation_store.checkpoint_rows("evaluation_pass1_runs", batch["id"])
    assert rows[0]["status"] == "completed", rows
    assert rows[0]["attempts"] == 2


@pytest.mark.asyncio
async def test_pass1_retry_reuses_groups_and_skips_completed_membership(
    evaluation_store: EvaluationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A retry should call only the failed frozen first-pass request group."""
    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="Grouped retry",
            asr_providers=["elevenlabs"],
            pass_1_model="deepseek-flash",
            pass_2_model="deepseek-flash",
            budget_limit=10,
            idempotency_key="grouped-pass1-retry-001",
        )
    )
    conversations = [
        {
            "conversation_id": conversation_id,
            "events": [
                {
                    "event_id": "R1",
                    "speaker": "customer",
                    "text": marker * 12_000,
                }
            ],
        }
        for conversation_id, marker in (("C1", "a"), ("C2", "b"))
    ]
    snapshot = batch["snapshot"]
    prompt = str(snapshot["pass_1_prompt"]["content"])
    shared_payload = {
        "evaluation_context": snapshot["evaluation_context"],
        "reference_dictionaries": snapshot["reference_dictionaries"],
        "screening_strategy": snapshot["screening_strategy"],
        "scenario_tags": snapshot["scenario_tags"],
    }
    units = [
        build_pass_one_unit(
            str(conversation["conversation_id"]),
            {
                "conversation_id": conversation["conversation_id"],
                "conversation_history": conversation["events"],
            },
            1,
        )
        for conversation in conversations
    ]
    safety_margin = 1_000
    one_unit_limit = (
        estimate_tokens(prompt)
        + estimate_tokens(shared_payload)
        + max(unit.estimated_input_tokens for unit in units)
        + pass_one_output_reserve(1, 1, ModelTokenPolicy(1_000_000, 100_000, safety_margin))
        + safety_margin
        + 4_096
    )
    policy = ModelTokenPolicy(one_unit_limit, 100_000, safety_margin)
    monkeypatch.setattr(
        "src.evaluation.executor.evaluation_token_policy", lambda _provider, _model=None: policy
    )
    calls: list[str] = []
    attempts: list[tuple[str, int]] = []
    fail_c2 = True

    async def llm_json(
        _model_id: str,
        _prompt: str,
        payload: dict[str, object],
        **kwargs: object,
    ) -> dict[str, object]:
        group_conversations = cast(list[dict[str, object]], payload["conversations"])
        conversation_id = str(group_conversations[0]["conversation_id"])
        calls.append(conversation_id)
        attempts.append((conversation_id, cast(int, kwargs["attempt"])))
        if conversation_id == "C2" and fail_c2:
            raise ValueError("Pass 1 group omitted results")
        return {
            "request_group_id": payload["request_group_id"],
            "results": [
                {
                    "conversation_id": conversation_id,
                    "issues": [],
                    "event_results": [
                        {"event_id": "R1", "decision": "pass", "reason": "No issue."}
                    ],
                }
            ],
        }

    async def no_wait(_seconds: float) -> None:
        return None

    runner = EvaluationRunner(evaluation_store, cast(BotKeyCipher, object()))
    monkeypatch.setattr(runner, "_llm_json", llm_json)
    monkeypatch.setattr(asyncio, "sleep", no_wait)

    await runner._run_pass_one(batch["id"], conversations)
    assert calls.count("C1") == 1
    assert calls.count("C2") == 3

    fail_c2 = False
    await runner._run_pass_one(batch["id"], conversations)
    assert calls.count("C1") == 1
    assert calls.count("C2") == 4
    assert [attempt for conversation_id, attempt in attempts if conversation_id == "C2"] == [
        1,
        2,
        3,
        4,
    ]
    groups = await evaluation_store.pass1_group_rows(batch["id"])
    assert {row["status"] for row in groups} == {"completed"}


def test_focused_screening_accepts_only_unique_p1_candidates() -> None:
    """Focused mode must mean P1 only, not a loose UI label."""
    conversation = {
        "events": [
            {"event_id": "R1", "speaker": "robot"},
            {"event_id": "R2", "speaker": "customer"},
        ]
    }
    valid = {
        "event_results": [
            {"event_id": "R2", "decision": "candidate", "reason": "Needs verification"}
        ],
        "issues": [
            {
                "priority": "P1",
                "target_events": [{"event_id": "R2", "decision": "candidate"}],
            }
        ],
    }
    EvaluationRunner._validate_pass_one(valid, conversation, "focused")

    outside_scope = json.loads(json.dumps(valid))
    outside_scope["issues"][0]["priority"] = "P2"
    with pytest.raises(ValueError, match="outside the screening strategy"):
        EvaluationRunner._validate_pass_one(outside_scope, conversation, "focused")

    duplicate = json.loads(json.dumps(valid))
    duplicate["issues"].append(duplicate["issues"][0])
    with pytest.raises(ValueError, match="duplicate candidate"):
        EvaluationRunner._validate_pass_one(duplicate, conversation, "focused")

    inconsistent = json.loads(json.dumps(valid))
    inconsistent["event_results"][0]["decision"] = "pass"
    with pytest.raises(ValueError, match="disagree"):
        EvaluationRunner._validate_pass_one(inconsistent, conversation, "focused")

    invalid_decision = json.loads(json.dumps(valid))
    invalid_decision["event_results"][0]["decision"] = "maybe"
    with pytest.raises(ValueError, match="invalid event decision"):
        EvaluationRunner._validate_pass_one(invalid_decision, conversation, "focused")


def test_common_asr_contract_rejects_inverted_segments_and_normalizes_errors() -> None:
    """All providers must cross one safe result and error boundary."""
    with pytest.raises(ValueError, match="end precedes start"):
        ASRResult(
            provider="soniox",
            conversation_id="C-1",
            text="hello",
            segments=[
                {
                    "segment_id": "C-1:soniox:0",
                    "start": 2.0,
                    "end": 1.0,
                    "text": "hello",
                }
            ],
        )
    error = ASRError(
        provider="elevenlabs",
        category="timeout",
        retryable=True,
        message="timeout",
    )
    assert "api_key" not in error.model_dump_json()


def test_batch_failure_is_actionable_without_upstream_payloads() -> None:
    """Terminal batch metadata should explain a safe next action and failed stage."""
    failure = _safe_execution_failure(
        EvaluationExecutionError("Missing verified connections: soniox"),
        "pass_1",
    )

    assert failure == {
        "category": "connection_unavailable",
        "message": "Missing verified connections: soniox",
        "stage": "pass_1",
        "retryable": True,
    }
    unexpected = _safe_execution_failure(RuntimeError("secret upstream body"), "pass_2")
    assert unexpected["category"] == "RuntimeError"
    assert "secret upstream body" not in str(unexpected)


def test_asr_failures_keep_actionable_categories_without_upstream_payloads() -> None:
    """ASR checkpoints retain safe reasons but never provider response content."""
    rejected = json.loads(
        _asr_error(
            "speechmatics",
            EvaluationExecutionError("Speechmatics job rejected: secret provider body"),
        )
    )
    empty = json.loads(
        _asr_error(
            "soniox",
            EvaluationExecutionError("Provider returned no transcript for the submitted audio"),
        )
    )

    assert rejected == {
        "provider": "speechmatics",
        "category": "provider_job_rejected",
        "retryable": False,
        "message": "Provider rejected the ASR job. Check the audio and provider settings.",
    }
    assert "secret provider body" not in json.dumps(rejected)
    assert empty["category"] == "empty_transcript"
    assert empty["retryable"] is True


@pytest.mark.asyncio
async def test_guarded_failure_preserves_last_stage_and_progress(
    evaluation_store: EvaluationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A planning failure must not erase completed-stage progress or cost."""
    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="Preserve progress",
            asr_providers=["elevenlabs"],
            pass_1_model="deepseek-chat",
            pass_2_model="deepseek-chat",
            budget_limit=10,
            idempotency_key="preserve-progress-001",
        )
    )
    await evaluation_store.set_batch_state(
        batch["id"],
        status="running",
        stage="pass_2",
        progress=75,
        cost=1.25,
    )
    runner = EvaluationRunner(evaluation_store, cast(BotKeyCipher, object()))

    async def fail_planning(_batch_id: str) -> None:
        raise EvaluationRequestOutputTooLarge(
            "One Pass 2 Case exceeds the pre-dispatch generation limit."
        )

    monkeypatch.setattr(runner, "_run", fail_planning)

    await runner._run_guarded(batch["id"])

    updated = await evaluation_store.get_batch(batch["id"])
    assert updated is not None
    assert updated["status"] == "partially_failed"
    assert updated["stage"] == "pass_2"
    assert updated["progress"] == 75
    assert updated["cost"] == 1.25
    assert updated["snapshot"]["execution_failure"]["category"] == ("preflight_output_limit")


def test_runtime_prompts_use_frozen_slots_and_render_without_residue() -> None:
    """Approved templates must expose and replace every runtime session variable."""
    from src.evaluation.prompts import PASS_ONE_SYSTEM_PROMPT, PASS_TWO_SYSTEM_PROMPT

    pass_one_payload = {
        "request_group_id": "P1G0001-test",
        "conversations": [
            {
                "conversation_id": "C1",
                "conversation_history": [{"event_id": "R1", "text": "hello"}],
            }
        ],
        "full_audio_context_asr": [],
        "evaluation_context": {"name": "Acceptance"},
        "reference_dictionaries": [],
        "screening_strategy": "focused",
        "scenario_tags": [],
    }
    rendered = _render_prompt(PASS_ONE_SYSTEM_PROMPT, pass_one_payload)
    assert "{{" not in rendered
    assert '"event_id":"R1"' in rendered
    assert len(PASS_ONE_SYSTEM_PROMPT) > 2_000
    assert "{{request_group_id}}" in PASS_ONE_SYSTEM_PROMPT
    assert "{{conversations}}" in PASS_ONE_SYSTEM_PROMPT
    assert '"results"' in PASS_ONE_SYSTEM_PROMPT
    assert "{{request_group_id}}" in PASS_TWO_SYSTEM_PROMPT
    assert "{{candidate_case}}" in PASS_TWO_SYSTEM_PROMPT
    assert "{{full_audio_context_asr}}" in PASS_TWO_SYSTEM_PROMPT
    assert '"results"' in PASS_TWO_SYSTEM_PROMPT
    assert '"positioning_quality"' in PASS_TWO_SYSTEM_PROMPT
    assert "唯一质检目标是检测线上 ASR" in PASS_ONE_SYSTEM_PROMPT
    assert "用户没有回答当前问题" in PASS_ONE_SYSTEM_PROMPT
    assert "中性 ASR 质检维度" in PASS_TWO_SYSTEM_PROMPT
    assert "不得描述用户没有回答" in PASS_TWO_SYSTEM_PROMPT

    with pytest.raises(ValueError, match="unresolved runtime slots"):
        _render_prompt(PASS_TWO_SYSTEM_PROMPT, pass_one_payload)


def test_runtime_image_packages_active_prompt_fixtures() -> None:
    """The production image must contain every Prompt loaded during app startup."""
    root = Path(__file__).resolve().parents[1]
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    dockerignore = (root / ".dockerignore").read_text(encoding="utf-8")
    assert "riyadbank-pass-1-system-prompt-v2.md" in dockerfile
    assert "riyadbank-pass-2-system-prompt-v2.md" in dockerfile
    assert "riyadbank-event-aligner-system-prompt-v1.md" in dockerfile
    assert (
        "!openspec/changes/add-asr-automated-evaluation/fixtures/riyadbank-event-aligner-system-prompt-v1.md"
        in dockerignore
    )


def test_llm_cost_estimate_preserves_supplier_currency() -> None:
    """Qwen cost stays in CNY while USD providers remain in USD."""
    qwen_cost, qwen_currency = estimate_llm_cost(
        "qwen",
        "qwen-plus",
        input_tokens=1_000_000,
        cached_input_tokens=0,
        reasoning_tokens=100_000,
        output_tokens=200_000,
    )
    deepseek_cost, deepseek_currency = estimate_llm_cost(
        "deepseek",
        "deepseek-chat",
        input_tokens=1_000_000,
        cached_input_tokens=0,
        reasoning_tokens=100_000,
        output_tokens=200_000,
    )

    assert qwen_currency == "CNY"
    assert qwen_cost == pytest.approx(1.4)
    assert deepseek_currency == "USD"
    assert deepseek_cost == pytest.approx(0.66)


def test_playback_range_uses_exact_user_event_boundaries() -> None:
    """Review playback must use the same pure-user interval sent to evaluation ASR."""
    conversation = {
        "user_audio": {"duration_s": 30.0},
        "issues": [],
        "events": [
            {"event_id": "R1", "speaker": "robot", "time_s": 8.0},
            {"event_id": "R2", "speaker": "customer", "time_s": 10.0},
            {"event_id": "R3", "speaker": "robot", "time_s": 12.0},
        ],
    }
    evidence = [
        {
            "event_id": "R2",
            "result": {
                "source_clip": {"start_s": 9.82, "end_s": 11.25},
                "segments": [
                    {"segment_id": "C1:soniox:1", "start": 10.0, "end": 11.0},
                    {"segment_id": "C1:speechmatics:2", "start": 9.5, "end": 12.0},
                ],
            },
        }
    ]

    resolved = EvaluationStore._playback_range(
        conversation,
        {
            "event_id": "R2",
            "recommended_listening_segment_ids": [
                "C1:soniox:1",
                "C1:speechmatics:2",
            ],
        },
        evidence,
    )
    fallback = EvaluationStore._playback_range(
        conversation,
        {
            "event_id": "R1",
            "recommended_listening_segment_ids": [],
        },
        evidence,
    )

    assert resolved == (9.82, 11.25, "exact", True)
    assert fallback == (0.0, 0.0, "unavailable", False)


def _full_call_alignment_results() -> list[dict[str, object]]:
    """Return two agreeing diarized timelines for alignment regressions."""
    results: list[dict[str, object]] = []
    for provider, offset in (("soniox", 0.0), ("speechmatics", 0.1)):
        segments = []
        for index, (text, speaker, start_s, end_s) in enumerate(
            (
                ("Welcome to the bank", "agent", 1.0, 2.5),
                ("yes please", "customer", 4.0, 5.0),
                ("Which branch do you need", "agent", 6.5, 8.0),
            )
        ):
            segments.append(
                {
                    "segment_id": f"C-1:{provider}:{index}",
                    "start": start_s + offset,
                    "end": end_s + offset,
                    "speaker": speaker,
                    "text": text,
                }
            )
        results.append({"provider": provider, "text": "", "segments": segments})
    return results


def _event_alignment_mapping(event_id: str = "R2") -> dict[str, object]:
    """Return a validated-model-shaped mapping to real provider turn IDs."""
    return {
        "conversation_id": "C-1",
        "event_id": event_id,
        "providers": [
            {
                "provider": "soniox",
                "status": "mapped",
                "turn_id": "C-1:soniox:turn:1",
            },
            {
                "provider": "speechmatics",
                "status": "mapped",
                "turn_id": "C-1:speechmatics:turn:1",
            },
        ],
    }


def test_full_call_diarization_consensus_ignores_excel_time() -> None:
    """Changing an unreliable workbook timestamp must not move the event interval."""
    events = [
        {"event_id": "R1", "speaker": "robot", "text": "Welcome to the bank", "time_s": 1},
        {"event_id": "R2", "speaker": "customer", "text": "yes please", "time_s": 999},
        {
            "event_id": "R3",
            "speaker": "robot",
            "text": "Which branch do you need",
            "time_s": -50,
        },
    ]

    first = align_customer_event(events, "R2", _full_call_alignment_results())
    events[1]["time_s"] = -1000
    second = align_customer_event(events, "R2", _full_call_alignment_results())

    assert first == second
    assert first["start_s"] == pytest.approx(4.1)
    assert first["end_s"] == pytest.approx(5.0)
    assert first["excel_time_used"] is False
    assert first["consensus_providers"] == ["soniox", "speechmatics"]


def test_pass2_full_call_context_keeps_only_target_and_direct_neighbors() -> None:
    """Pass 2 must not receive unrelated turns from a long full-call transcript."""
    conversation_id = "C-BOUNDED"
    provider_result = {
        "provider": "soniox",
        "segments": [
            {
                "segment_id": f"s{index}",
                "start": float(index * 2),
                "end": float(index * 2 + 1),
                "speaker": "A" if index % 2 == 0 else "B",
                "text": f"turn-{index}",
            }
            for index in range(7)
        ],
    }
    mapping = {
        "event_id": "R4",
        "providers": [
            {
                "provider": "soniox",
                "status": "mapped",
                "turn_id": f"{conversation_id}:soniox:turn:3",
            }
        ],
    }

    bounded = EvaluationRunner._bounded_full_call_evidence(
        conversation_id,
        [provider_result],
        mapping,
    )

    turns = bounded[0]["turns"]
    assert [turn["turn_id"] for turn in turns] == [
        f"{conversation_id}:soniox:turn:2",
        f"{conversation_id}:soniox:turn:3",
        f"{conversation_id}:soniox:turn:4",
    ]
    assert all("turn-0" not in turn["text"] and "turn-6" not in turn["text"] for turn in turns)


@pytest.mark.parametrize(
    ("provider_intervals", "expected_start", "expected_end"),
    [
        (((26.70, 27.22), (26.91, 27.39)), 26.70, 27.39),
        (((18.94, 20.48), (19.05, 19.11), (18.86, 19.18)), 18.86, 20.48),
        (((45.10, 45.78), (45.16, 45.87), (45.57, 45.82)), 45.10, 45.87),
    ],
)
def test_event_aligner_uses_provider_union_for_r6_r7_r13_regressions(
    provider_intervals: tuple[tuple[float, float], ...],
    expected_start: float,
    expected_end: float,
) -> None:
    """Provider boundary differences must widen, never intersect, the final interval."""
    providers = ("elevenlabs", "soniox", "speechmatics")[: len(provider_intervals)]
    results: list[dict[str, object]] = []
    mappings: list[dict[str, object]] = []
    for provider, (start_s, end_s) in zip(providers, provider_intervals, strict=True):
        text = "Two two one" if provider == "elevenlabs" else "2 2 1"
        results.append(
            {
                "provider": provider,
                "segments": [
                    {"start": 0.0, "end": 1.0, "speaker": "A", "text": "agent"},
                    {"start": start_s, "end": end_s, "speaker": "B", "text": text},
                ],
            }
        )
        mappings.append(
            {
                "provider": provider,
                "status": "mapped",
                "turn_id": f"C-1:{provider}:turn:1",
            }
        )
    trace = align_customer_event_from_mapping(
        [{"event_id": "R6", "speaker": "customer", "text": "Two to. One."}],
        "R6",
        results,
        {"conversation_id": "C-1", "event_id": "R6", "providers": mappings},
    )

    assert trace["start_s"] == pytest.approx(expected_start)
    assert trace["end_s"] == pytest.approx(expected_end)
    assert trace["boundary_rule"] == "event_aligner_provider_union_v1"


def test_full_call_diarization_consensus_requires_two_providers() -> None:
    """One diarized provider cannot establish a source interval by itself."""
    events = [
        {"event_id": "R1", "speaker": "robot", "text": "Welcome to the bank"},
        {"event_id": "R2", "speaker": "customer", "text": "yes please"},
        {"event_id": "R3", "speaker": "robot", "text": "Which branch do you need"},
    ]
    with pytest.raises(ValueError, match="Fewer than two"):
        align_customer_event(events, "R2", _full_call_alignment_results()[:1])

    duplicate = _full_call_alignment_results()[0]
    with pytest.raises(ValueError, match="Fewer than two"):
        align_customer_event(events, "R2", [duplicate, duplicate])


def test_full_call_diarization_consensus_rejects_non_overlapping_intervals() -> None:
    """Nearby but non-overlapping provider turns must not count as agreement."""
    events = [
        {"event_id": "R1", "speaker": "robot", "text": "Welcome to the bank"},
        {"event_id": "R2", "speaker": "customer", "text": "yes please"},
        {"event_id": "R3", "speaker": "robot", "text": "Which branch do you need"},
    ]
    results = _full_call_alignment_results()
    for segment in cast(list[dict[str, object]], results[1]["segments"]):
        if segment["text"] == "yes please":
            segment["start"] = 5.1
            segment["end"] = 6.1

    with pytest.raises(ValueError, match="Fewer than two"):
        align_customer_event(events, "R2", results)


def test_full_call_diarization_consensus_rejects_bridged_three_provider_conflict() -> None:
    """One broad interval cannot hide two incompatible two-provider interpretations."""
    events = [
        {"event_id": "R1", "speaker": "robot", "text": "Welcome to the bank"},
        {"event_id": "R2", "speaker": "customer", "text": "yes please"},
        {"event_id": "R3", "speaker": "robot", "text": "Which branch do you need"},
    ]

    def result(provider: str, start_s: float, end_s: float) -> dict[str, object]:
        return {
            "provider": provider,
            "segments": [
                {"start": 0.0, "end": 1.0, "speaker": "A", "text": "Welcome to the bank"},
                {"start": start_s, "end": end_s, "speaker": "B", "text": "yes please"},
                {
                    "start": 7.0,
                    "end": 8.0,
                    "speaker": "A",
                    "text": "Which branch do you need",
                },
            ],
        }

    results = [
        result("soniox", 2.0, 6.0),
        result("speechmatics", 2.0, 4.0),
        result("elevenlabs", 4.1, 6.0),
    ]
    with pytest.raises(ValueError, match="competing event intervals"):
        align_customer_event(events, "R2", results)


def test_user_track_refinement_is_bounded_by_asr_consensus(tmp_path: Path) -> None:
    """Noise outside the ASR interval must not redirect user-track validation."""
    sample_rate = 8_000
    samples = np.full(sample_rate * 10, 0.006, dtype=np.float32)
    samples[: sample_rate * 2] = 0.2
    start = round(4.12 * sample_rate)
    end = round(4.88 * sample_rate)
    timeline = np.arange(end - start, dtype=np.float32) / sample_rate
    samples[start:end] = 0.12 * np.sin(2 * np.pi * 220 * timeline)
    source = tmp_path / "user.wav"
    sf.write(source, samples, sample_rate, subtype="PCM_16")

    trace = EvaluationStore._validate_and_refine_user_interval(source, start_s=4.0, end_s=5.0)

    assert float(trace["speech_start_s"]) == pytest.approx(4.12, abs=0.03)
    assert float(trace["speech_end_s"]) == pytest.approx(4.88, abs=0.03)
    assert 3.65 <= float(trace["start_s"]) <= 4.0
    assert 5.0 <= float(trace["end_s"]) <= 5.35


def test_user_track_refinement_rejects_noise_only_interval(tmp_path: Path) -> None:
    """Steady background noise must not validate an ASR consensus interval as speech."""
    sample_rate = 8_000
    samples = np.full(sample_rate * 8, 0.01, dtype=np.float32)
    source = tmp_path / "noise.wav"
    sf.write(source, samples, sample_rate, subtype="PCM_16")

    with pytest.raises(ValueError, match="No validated user signal"):
        EvaluationStore._validate_and_refine_user_interval(source, start_s=3.0, end_s=5.0)


@pytest.mark.asyncio
async def test_case_asr_clip_uses_pure_user_event_interval(
    evaluation_store: EvaluationStore,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The provider input must use diarization consensus, not the workbook timestamp."""
    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="Pure user clip",
            asr_providers=["soniox", "speechmatics"],
            pass_1_model="deepseek-chat",
            pass_2_model="deepseek-chat",
            budget_limit=10,
            idempotency_key="pure-user-clip-001",
        )
    )
    sample_rate = 8_000
    samples = np.full(sample_rate * 10, 0.004, dtype=np.float32)
    start = round(4.1 * sample_rate)
    end = round(4.9 * sample_rate)
    timeline = np.arange(end - start, dtype=np.float32) / sample_rate
    samples[start:end] = 0.12 * np.sin(2 * np.pi * 220 * timeline)
    source = tmp_path / "C-1.wav"
    sf.write(source, samples, sample_rate, subtype="PCM_16")
    conversation = {
        "conversation_id": "C-1",
        "user_audio": {"duration_s": 10.0},
        "issues": [],
        "events": [
            {
                "event_id": "R1",
                "speaker": "robot",
                "text": "Welcome to the bank",
                "time_s": 500.0,
            },
            {"event_id": "R2", "speaker": "customer", "text": "yes please", "time_s": -1.0},
            {
                "event_id": "R3",
                "speaker": "robot",
                "text": "Which branch do you need",
                "time_s": 900.0,
            },
        ],
    }

    async def get_conversation(_conversation_id: str) -> dict[str, object]:
        return conversation

    monkeypatch.setattr(evaluation_store, "get_conversation", get_conversation)
    monkeypatch.setattr(evaluation_store, "conversation_user_audio_path", lambda _value: source)
    path, trace = await evaluation_store.prepare_case_asr_clip(
        str(batch["id"]),
        "C-1",
        "R2",
        _full_call_alignment_results(),
        _event_alignment_mapping(),
    )

    assert path.is_file()
    assert trace["source"].startswith("user_record/")
    assert trace["boundary_rule"] == "event_aligner_provider_union_v1"
    assert trace["excel_time_used"] is False
    assert trace["consensus_providers"] == ["soniox", "speechmatics"]
    assert trace["speech_start_s"] <= trace["speech_end_s"]
    with wave.open(str(path), "rb") as audio:
        duration = audio.getnframes() / audio.getframerate()
    assert duration == pytest.approx(float(trace["end_s"]) - float(trace["start_s"]), abs=0.002)
    assert duration < 2.0


@pytest.mark.asyncio
async def test_case_asr_clip_rejects_unreliable_shared_timeline(
    evaluation_store: EvaluationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A timeline warning must fail the Case instead of falling back to mixed audio."""
    conversation = await evaluation_store.get_conversation(_VALID_CONVERSATION_ID)
    assert conversation is not None
    event = next(item for item in conversation["events"] if item["speaker"] == "customer")
    conversation["issues"] = [{"issue_type": "audio_timeline_mismatch"}]

    async def mismatched(_conversation_id: str) -> dict[str, object]:
        return conversation

    monkeypatch.setattr(evaluation_store, "get_conversation", mismatched)
    with pytest.raises(ValueError, match="not aligned"):
        await evaluation_store.prepare_case_asr_clip(
            "mismatched-timeline",
            _VALID_CONVERSATION_ID,
            str(event["event_id"]),
            [],
            {},
        )


@pytest.mark.asyncio
async def test_run_asr_checkpoints_invalid_timeline_without_provider_dispatch(
    evaluation_store: EvaluationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid source alignment must persist failure without sending mixed audio."""
    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="Invalid timeline ASR",
            asr_providers=["elevenlabs"],
            pass_1_model="deepseek-chat",
            pass_2_model="deepseek-chat",
            budget_limit=10,
            idempotency_key="invalid-timeline-asr-001",
        )
    )
    conversation = await evaluation_store.get_conversation(_VALID_CONVERSATION_ID)
    assert conversation is not None
    event = next(item for item in conversation["events"] if item["speaker"] == "customer")
    conversation["issues"] = [{"issue_type": "audio_timeline_mismatch"}]
    dispatched_event_ids: list[str | None] = []

    async def mismatched(_conversation_id: str) -> dict[str, object]:
        return conversation

    async def context_only_dispatch(
        *_args: object, **kwargs: object
    ) -> tuple[dict[str, object], str]:
        dispatched_event_ids.append(cast(str | None, kwargs.get("event_id")))
        return {
            "text": "agent customer",
            "segments": [
                {"start": 0.0, "end": 0.5, "speaker": "S1", "text": "agent"},
                {"start": 0.6, "end": 1.0, "speaker": "S2", "text": "customer"},
            ],
        }, "context-job"

    monkeypatch.setattr(evaluation_store, "get_conversation", mismatched)
    runner = EvaluationRunner(evaluation_store, cast(BotKeyCipher, object()))
    monkeypatch.setattr(runner, "_transcribe", context_only_dispatch)

    async def map_event(*_args: object) -> dict[tuple[str, str], dict[str, object]]:
        return {
            (_VALID_CONVERSATION_ID, str(event["event_id"])): {
                "conversation_id": _VALID_CONVERSATION_ID,
                "event_id": str(event["event_id"]),
                "providers": [],
            }
        }

    monkeypatch.setattr(runner, "_run_event_alignment", map_event)
    await runner._run_asr(
        str(batch["id"]),
        batch,
        [{"conversation_id": _VALID_CONVERSATION_ID, "event_id": event["event_id"]}],
    )

    rows = await evaluation_store.checkpoint_rows("evaluation_case_asr_runs", str(batch["id"]))
    assert dispatched_event_ids == [None]
    assert len(rows) == 1
    assert rows[0]["status"] == "failed"
    assert rows[0]["attempts"] == 0
    assert rows[0]["result"] is None


@pytest.mark.asyncio
async def test_empty_event_transcript_is_not_saved_as_provider_success(
    evaluation_store: EvaluationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A completed remote job with no transcript is an invalid ASR result."""
    runner = EvaluationRunner(evaluation_store, cast(BotKeyCipher, object()))

    async def empty_result(*_args: object, **_kwargs: object) -> tuple[dict[str, object], None]:
        return {"text": "", "segments": []}, None

    async def fake_key(_provider: str) -> tuple[str, str]:
        return "https://example.test", "test-key"

    monkeypatch.setattr(runner, "_elevenlabs", empty_result)
    monkeypatch.setattr(runner, "_key", fake_key)
    source = evaluation_store.conversation_user_audio_path(_VALID_CONVERSATION_ID)
    assert source is not None
    with pytest.raises(EvaluationExecutionError, match="no transcript"):
        await runner._transcribe(
            "empty-result",
            "elevenlabs",
            source,
            _VALID_CONVERSATION_ID,
            1,
            event_id="R1",
        )


@pytest.mark.asyncio
async def test_asr_connection_probe_is_real_and_secret_safe() -> None:
    """ASR checks must call the official authenticated endpoint without returning keys."""
    observed: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(request)
        return httpx.Response(200, json={"models": []}, request=request)

    result = await run_asr_connection_test(
        "soniox",
        "secret-test-key",
        transport=httpx.MockTransport(handler),
    )

    assert result["success"] is True
    assert observed[0].url == "https://api.soniox.com/v1/models"
    assert observed[0].headers["Authorization"] == "Bearer secret-test-key"
    assert "secret-test-key" not in json.dumps(result)

    with pytest.raises(ASRConnectionError, match="Unsupported ASR provider"):
        await run_asr_connection_test("unknown", "secret-test-key")


@pytest.mark.asyncio
async def test_elevenlabs_probe_checks_batch_scribe_permission() -> None:
    """ElevenLabs checks must not require unrelated user-profile access."""
    observed: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(request)
        return httpx.Response(200, json={"token": "discarded-token"}, request=request)

    result = await run_asr_connection_test(
        "elevenlabs",
        "restricted-scribe-key",
        transport=httpx.MockTransport(handler),
    )

    assert observed[0].method == "POST"
    assert observed[0].url == ("https://api.elevenlabs.io/v1/single-use-token/batch_scribe")
    assert observed[0].headers["xi-api-key"] == "restricted-scribe-key"
    assert "discarded-token" not in json.dumps(result)
    assert "restricted-scribe-key" not in json.dumps(result)


@pytest.mark.asyncio
async def test_asr_capability_state_is_persisted_and_safe(
    evaluation_store: EvaluationStore,
) -> None:
    """New capabilities start pending and expose no credential material."""
    initial = await evaluation_store.list_asr_capabilities()
    assert {item["provider"] for item in initial} == {
        "soniox",
        "speechmatics",
        "elevenlabs",
    }
    assert all(item["status"] == "pending" for item in initial)
    assert all(item["available"] is False for item in initial)
    assert "api_key" not in json.dumps(initial)

    verified = await evaluation_store.set_asr_capability_validation(
        "soniox",
        status="verified",
        diagnostic_id="diag-soniox",
        summary="Authenticated official endpoint",
    )
    assert verified["available"] is True
    assert verified["validation"] == {
        "endpoint_authenticated": True,
        "contract_validated": True,
        "summary": "Authenticated official endpoint",
    }
    assert await evaluation_store.unavailable_asr_providers(["soniox", "elevenlabs"]) == [
        "elevenlabs"
    ]


@pytest.mark.asyncio
async def test_batch_api_rejects_unverified_asr_capability(
    evaluation_store: EvaluationStore,
) -> None:
    """A new batch cannot freeze resources that have not been verified."""
    app = FastAPI()
    app.include_router(create_evaluation_router(evaluation_store))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/evaluation/batches",
            json={
                "name": "Capability gate",
                "context_key": "riyadbank",
                "screening_strategy": "focused",
                "asr_providers": ["elevenlabs"],
                "pass_1_model": "deepseek-chat",
                "pass_2_model": "deepseek-chat",
                "budget_limit": 10,
                "idempotency_key": "capability-gate-test",
            },
        )
    assert response.status_code == 409
    assert "elevenlabs" in response.json()["detail"]


@pytest.mark.asyncio
async def test_speechmatics_job_is_deleted_after_result(tmp_path: Path) -> None:
    """A completed Speechmatics batch job must be removed from remote storage."""
    audio_path = tmp_path / "conversation.mp3"
    audio_path.write_bytes(b"test-audio")
    observed: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append((request.method, request.url.path))
        if request.method == "POST":
            assert b'"diarization": "speaker"' in request.content
            return httpx.Response(200, json={"id": "job-123"}, request=request)
        if request.method == "DELETE":
            return httpx.Response(204, request=request)
        if request.url.path.endswith("/transcript"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "start_time": 1.0,
                            "end_time": 1.5,
                            "alternatives": [{"content": "hello", "speaker": "S1"}],
                        }
                    ]
                },
                request=request,
            )
        return httpx.Response(
            200,
            json={"job": {"status": "done"}},
            request=request,
        )

    runner = EvaluationRunner(cast(EvaluationStore, None), None)
    result, job_id = await runner._speechmatics(
        "https://asr.api.speechmatics.com",
        "secret",
        audio_path,
        "conversation-1",
        transport=httpx.MockTransport(handler),
    )

    assert job_id == "job-123"
    assert result["remote_cleanup"] == "completed"
    assert result["segments"][0]["segment_id"] == "conversation-1:speechmatics:0"
    assert observed[-1] == ("DELETE", "/v2/jobs/job-123")


@pytest.mark.asyncio
async def test_soniox_requests_speaker_diarization(tmp_path: Path) -> None:
    """A Soniox full-call job must explicitly request speaker diarization."""
    audio_path = tmp_path / "conversation.mp3"
    audio_path.write_bytes(b"test-audio")
    observed_payload: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/v1/files":
            return httpx.Response(200, json={"id": "file-123"}, request=request)
        if request.method == "POST" and request.url.path == "/v1/transcriptions":
            observed_payload.update(cast(dict[str, object], json.loads(request.content)))
            return httpx.Response(200, json={"id": "job-123"}, request=request)
        if request.method == "GET" and request.url.path.endswith("/transcript"):
            return httpx.Response(
                200,
                json={
                    "tokens": [
                        {
                            "start_ms": 1000,
                            "end_ms": 1500,
                            "speaker": "1",
                            "text": "hello",
                        }
                    ]
                },
                request=request,
            )
        if request.method == "GET":
            return httpx.Response(200, json={"status": "completed"}, request=request)
        return httpx.Response(204, request=request)

    runner = EvaluationRunner(cast(EvaluationStore, None), None)
    result, job_id = await runner._soniox(
        "https://api.soniox.test",
        "secret",
        audio_path,
        "conversation-1",
        transport=httpx.MockTransport(handler),
    )

    assert job_id == "job-123"
    assert observed_payload["enable_speaker_diarization"] is True
    assert result["segments"][0]["speaker"] == "1"


@pytest.mark.asyncio
async def test_official_pricing_requires_matching_source_evidence() -> None:
    """Official sync should return reviewed rates only while source evidence matches."""

    def handler(request: httpx.Request) -> httpx.Response:
        pages = {
            "soniox.com": "Speech-to-Text API pricing async $0.10/hour",
            "www.speechmatics.com": "Batch Melia 1 $0.129/hr",
            "elevenlabs.io": "Scribe v2 $0.22 Price per hour",
            "api-docs.deepseek.com": ("deepseek-flash deepseek-v4.1-flash $0.006 $0.3 $1.2"),
        }
        return httpx.Response(200, text=pages[request.url.host], request=request)

    service = OfficialPricingService(transport=httpx.MockTransport(handler))
    asr = await service.sync(PricingSyncRequest(scope="asr"))
    asr_items = cast(list[dict[str, object]], asr["items"])
    assert [item["unit_price"] for item in asr_items] == [0.10, 0.129, 0.22]

    llm = await service.sync(
        PricingSyncRequest(
            scope="llm",
            selections=[PricingSelection(provider="DeepSeek", model="DeepSeek/deepseek-flash")],
        )
    )
    llm_items = cast(list[dict[str, object]], llm["items"])
    assert llm_items[0]["model"] == "deepseek-flash"
    assert llm_items[0]["input_per_1m"] == 0.30
    assert llm_items[0]["cached_input_per_1m"] == 0.006
    assert llm_items[0]["output_per_1m"] == 1.20


@pytest.mark.asyncio
async def test_official_pricing_does_not_overwrite_when_evidence_changes() -> None:
    """A changed official page should fail closed rather than apply stale numbers."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="pricing page changed", request=request)

    service = OfficialPricingService(transport=httpx.MockTransport(handler))
    with pytest.raises(PricingSyncError, match="existing draft prices were not overwritten"):
        await service.sync(PricingSyncRequest(scope="asr"))


def _source_root() -> Path:
    return Path(__file__).resolve().parents[1] / "benchmarks" / "RiyadBankConversation"


@pytest.fixture(autouse=True)
def require_private_evaluation_fixture(request: pytest.FixtureRequest) -> None:
    """Skip only private-data integration tests in clean repository checkouts."""
    required_history = _source_root() / "conversation_history" / f"{_VALID_CONVERSATION_ID}.xlsx"
    if required_history.is_file():
        return
    function = getattr(request.node, "function", None)
    source = inspect.getsource(function) if function is not None else ""
    requires_dataset = "evaluation_store" in request.fixturenames or any(
        token in source for token in ("_source_root", "_VALID_CONVERSATION_ID")
    )
    if requires_dataset:
        pytest.skip("private Evaluation source fixture is not available")


def _write_package_zip(
    path: Path,
    *,
    include_record: bool = True,
    invalid_workbook: bool = False,
    invalid_record: bool = False,
) -> None:
    """Create a one-conversation upload package from real repository sources."""
    source = _source_root()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        history = f"conversation_history/{_VALID_CONVERSATION_ID}.xlsx"
        archive.writestr(
            history,
            b"not-an-xlsx" if invalid_workbook else source.joinpath(history).read_bytes(),
        )
        if include_record:
            record = f"record/{_VALID_CONVERSATION_ID}.mp3"
            archive.writestr(
                record,
                b"not-an-mp3" if invalid_record else source.joinpath(record).read_bytes(),
            )
        user_record = f"user_record/{_VALID_CONVERSATION_ID}.wav"
        archive.writestr(user_record, source.joinpath(user_record).read_bytes())


@pytest.fixture
async def evaluation_store(tmp_path: Path) -> EvaluationStore:
    """Create an isolated store over the repository's 56-call source dataset."""
    store = EvaluationStore(
        tmp_path / "evaluation.db",
        _source_root(),
    )
    await store.initialize()
    return store


@pytest.mark.asyncio
async def test_display_translation_sends_only_source_text_and_does_not_persist_it(
    evaluation_store: EvaluationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Display translation must exclude UI copy and leave source events unchanged."""
    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="Display translation",
            asr_providers=["elevenlabs"],
            pass_1_model="deepseek-chat",
            pass_2_model="deepseek-chat",
            budget_limit=10,
            idempotency_key="display-translation-batch",
        )
    )
    runner = EvaluationRunner(evaluation_store, None)
    observed: dict[str, object] = {}

    async def fake_llm_json(
        model_id: str,
        system_prompt: str,
        payload: dict[str, object],
        **kwargs: object,
    ) -> dict[str, object]:
        observed.update(
            model_id=model_id,
            system_prompt=system_prompt,
            payload=payload,
            kwargs=kwargs,
        )
        return {
            "translations": [
                {"index": 0, "translation_zh": "您好"},
                {"index": 1, "translation_zh": "我是金卡客户"},
            ]
        }

    monkeypatch.setattr(runner, "_llm_json", fake_llm_json)
    source_texts = ["Hello", "أنا عميلة ذهبية"]
    before = await evaluation_store.get_conversation(_VALID_CONVERSATION_ID)
    result = await runner.translate_for_display(str(batch["id"]), source_texts)
    after = await evaluation_store.get_conversation(_VALID_CONVERSATION_ID)

    assert result == {
        "translations": ["您好", "我是金卡客户"],
        "provider": "deepseek",
        "model_id": "deepseek-chat",
        "ephemeral": True,
        "evidence": False,
        "partial": False,
        "failed_count": 0,
    }
    assert observed["payload"] == {
        "source_texts": [
            {"index": 0, "text": "Hello"},
            {"index": 1, "text": "أنا عميلة ذهبية"},
        ]
    }
    assert "关闭弹窗" not in json.dumps(observed, ensure_ascii=False, default=str)
    assert observed["kwargs"]["stage"] == "display_translation"  # type: ignore[index]
    assert observed["kwargs"]["pause_batch_on_budget_rejection"] is False  # type: ignore[index]
    assert observed["kwargs"]["disable_thinking"] is True  # type: ignore[index]
    assert before == after

    batch_before = await evaluation_store.get_batch(str(batch["id"]))
    assert batch_before is not None
    status_before = batch_before["status"]
    admitted = await evaluation_store.reserve_budget(
        idempotency_key="display-translation-over-budget",
        batch_id=str(batch["id"]),
        estimated_usd=100,
        pause_batch_on_rejection=False,
    )
    batch_after = await evaluation_store.get_batch(str(batch["id"]))
    assert batch_after is not None
    status_after = batch_after["status"]
    assert admitted is False
    assert status_after == status_before


def test_gemini_38_uses_verified_thinking_level_when_minimized() -> None:
    """Gemini 3.8 rejects the legacy zero-budget control used by 2.5 models."""
    config = _gemini_thinking_config(
        "gemini-3.8-flash",
        thinking=False,
        disable_thinking=True,
    )

    assert config is not None
    assert str(config.thinking_level).casefold().endswith("low")
    assert config.thinking_budget is None


def test_qwen38_compatible_mode_caps_reasoning_plus_answer_tokens() -> None:
    """Compatible Qwen 3.8 must use the same total-output ceiling as native mode."""
    assert _completion_limit_field("qwen", "qwen3.8-max") == "max_completion_tokens"
    assert _completion_limit_field("qwen", "qwen-plus") == "max_tokens"


@pytest.mark.asyncio
async def test_qwen38_provider_resolution_does_not_require_prior_custom_registration(
    evaluation_store: EvaluationStore,
) -> None:
    """The predefined Qwen 3.8 model must reach its saved Qwen connection."""
    runner = EvaluationRunner(evaluation_store, cast(BotKeyCipher, object()))

    assert await runner._model_provider("qwen3.8-max") == "qwen"


@pytest.mark.asyncio
async def test_display_translation_retries_then_splits_malformed_large_group(
    evaluation_store: EvaluationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Malformed full-group output must recover through bounded stable chunks."""
    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="Display translation split recovery",
            asr_providers=["elevenlabs"],
            pass_1_model="deepseek-chat",
            pass_2_model="deepseek-chat",
            budget_limit=10,
            idempotency_key="display-translation-split",
        )
    )
    runner = EvaluationRunner(evaluation_store, None)
    calls: list[dict[str, object]] = []
    four_item_attempts = 0

    async def fake_llm_json(
        model_id: str,
        system_prompt: str,
        payload: dict[str, object],
        **kwargs: object,
    ) -> dict[str, object]:
        nonlocal four_item_attempts
        calls.append({"payload": payload, "kwargs": kwargs})
        source_texts = cast(list[dict[str, object]], payload["source_texts"])
        if len(source_texts) == 6:
            return {"not_translations": []}
        if len(source_texts) == 4:
            four_item_attempts += 1
            if four_item_attempts == 1:
                return {"translations": []}
        return {
            "translations": [
                {
                    "index": index,
                    "translation_zh": f"译文-{item['text']}",
                }
                for index, item in enumerate(source_texts)
            ]
        }

    monkeypatch.setattr(runner, "_llm_json", fake_llm_json)
    texts = [f"阿语-{index}" for index in range(6)]
    result = await runner.translate_for_display(str(batch["id"]), texts)

    assert result["translations"] == [f"译文-{text}" for text in texts]
    assert result["partial"] is False
    assert result["failed_count"] == 0
    assert [
        len(cast(list[object], cast(dict[str, object], call["payload"])["source_texts"]))
        for call in calls
    ] == [6, 6, 4, 4, 2]
    assert [cast(dict[str, object], call["kwargs"])["attempt"] for call in calls] == [
        1,
        2,
        1,
        2,
        1,
    ]


@pytest.mark.asyncio
async def test_display_translation_returns_per_text_fallback_after_retries_exhausted(
    evaluation_store: EvaluationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exhausted chunks must preserve ordering and return per-text unavailable slots."""
    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="Display translation exhausted retries",
            asr_providers=["elevenlabs"],
            pass_1_model="deepseek-chat",
            pass_2_model="deepseek-chat",
            budget_limit=10,
            idempotency_key="display-translation-exhausted",
        )
    )
    runner = EvaluationRunner(evaluation_store, None)
    calls: list[tuple[int, int]] = []

    async def fake_llm_json(
        model_id: str,
        system_prompt: str,
        payload: dict[str, object],
        **kwargs: object,
    ) -> dict[str, object]:
        source_texts = cast(list[dict[str, object]], payload["source_texts"])
        calls.append((len(source_texts), cast(int, kwargs["attempt"])))
        return {"translations": []}

    monkeypatch.setattr(runner, "_llm_json", fake_llm_json)
    result = await runner.translate_for_display(str(batch["id"]), ["نص"] * 6)
    assert result["translations"] == [None] * 6
    assert result["partial"] is True
    assert result["failed_count"] == 6
    assert calls == [(6, 1), (6, 2), (4, 1), (4, 2), (2, 1), (2, 2)]


@pytest.mark.asyncio
async def test_display_translation_keeps_successful_chunks_when_later_chunk_fails(
    evaluation_store: EvaluationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One malformed chunk must not discard translations from a successful chunk."""
    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="Display translation partial chunks",
            asr_providers=["elevenlabs"],
            pass_1_model="deepseek-chat",
            pass_2_model="deepseek-chat",
            budget_limit=10,
            idempotency_key="display-translation-partial",
        )
    )
    runner = EvaluationRunner(evaluation_store, None)

    async def fake_llm_json(
        model_id: str,
        system_prompt: str,
        payload: dict[str, object],
        **kwargs: object,
    ) -> dict[str, object]:
        source_texts = cast(list[dict[str, object]], payload["source_texts"])
        if len(source_texts) == 4:
            return {
                "translations": [
                    {"index": index, "translation_zh": f"译文-{item['text']}"}
                    for index, item in enumerate(source_texts)
                ]
            }
        return {"translations": []}

    monkeypatch.setattr(runner, "_llm_json", fake_llm_json)
    texts = [f"阿语-{index}" for index in range(6)]
    result = await runner.translate_for_display(str(batch["id"]), texts)
    assert result["translations"] == [
        *(f"译文-{text}" for text in texts[:4]),
        None,
        None,
    ]
    assert result["partial"] is True
    assert result["failed_count"] == 2


@pytest.mark.asyncio
async def test_display_translation_does_not_retry_budget_rejection(
    evaluation_store: EvaluationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A rejected budget must stop before retry or chunk fallback can add cost."""
    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="Display translation budget stop",
            asr_providers=["elevenlabs"],
            pass_1_model="deepseek-chat",
            pass_2_model="deepseek-chat",
            budget_limit=10,
            idempotency_key="display-translation-budget-stop",
        )
    )
    runner = EvaluationRunner(evaluation_store, None)
    calls = 0

    async def fake_llm_json(*args: object, **kwargs: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        raise EvaluationBudgetReached("budget rejected")

    monkeypatch.setattr(runner, "_llm_json", fake_llm_json)
    with pytest.raises(EvaluationBudgetReached, match="budget rejected"):
        await runner.translate_for_display(str(batch["id"]), ["نص"] * 6)
    assert calls == 1


@pytest.mark.asyncio
async def test_display_translation_api_uses_injected_translator(
    evaluation_store: EvaluationStore,
) -> None:
    """The authenticated route should validate bounds and return an ephemeral result."""
    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="Display translation route",
            asr_providers=["elevenlabs"],
            pass_1_model="deepseek-chat",
            pass_2_model="deepseek-chat",
            budget_limit=10,
            idempotency_key="display-translation-route-batch",
        )
    )
    observed: dict[str, object] = {}

    async def translate(batch_id: str, texts: list[str]) -> dict[str, object]:
        observed.update(batch_id=batch_id, texts=texts)
        return {
            "translations": ["中文对照"],
            "provider": "deepseek",
            "model_id": "deepseek-chat",
            "ephemeral": True,
            "evidence": False,
        }

    app = FastAPI()
    app.include_router(
        create_evaluation_router(
            evaluation_store,
            translate_for_display=translate,
        )
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/evaluation/batches/{batch['id']}/display-translation",
            json={"texts": ["Original source transcript"]},
        )

    assert response.status_code == 200
    assert response.json()["translations"] == ["中文对照"]
    assert observed == {
        "batch_id": batch["id"],
        "texts": ["Original source transcript"],
    }


async def _prepare_pending_review(
    store: EvaluationStore,
    *,
    run_key: str,
) -> tuple[dict[str, object], dict[str, object]]:
    """Materialize one pending review without calling any external provider."""
    batch = await store.create_batch(
        EvaluationBatchCreate(
            name="Pending review run",
            asr_providers=["elevenlabs"],
            pass_1_model="deepseek-chat",
            pass_2_model="deepseek-chat",
            budget_limit=10,
            idempotency_key=run_key,
        )
    )
    conversation = await store.get_conversation(_VALID_CONVERSATION_ID)
    assert conversation is not None
    event = next(item for item in conversation["events"] if item["speaker"] == "customer")
    event_id = str(event["event_id"])
    await store.checkpoint_result(
        "evaluation_pass1_runs",
        (batch["id"], _VALID_CONVERSATION_ID),
        status="completed",
        attempts=1,
        result={
            "issues": [
                {
                    "issue_id": "I1",
                    "title": "Digit check",
                    "priority": "P1",
                    "target_events": [
                        {
                            "event_id": event_id,
                            "decision": "candidate",
                            "verification_question": "What digits did the customer say?",
                        }
                    ],
                }
            ],
            "event_results": [],
        },
    )
    await store.checkpoint_result(
        "evaluation_case_asr_runs",
        (batch["id"], "elevenlabs", _VALID_CONVERSATION_ID, event_id),
        status="completed",
        attempts=1,
        result={
            "text": "example",
            "source_clip": {
                "start_s": float(event["time_s"]) - 0.5,
                "end_s": float(event["time_s"]) + 1.0,
            },
            "segments": [
                {
                    "segment_id": "elevenlabs-1",
                    "start": event["time_s"],
                    "end": event["time_s"] + 1,
                    "text": "example",
                }
            ],
        },
        remote_job_id="job-pending-review",
    )
    await store.checkpoint_result(
        "evaluation_pass2_runs",
        (batch["id"], _VALID_CONVERSATION_ID, event_id),
        status="completed",
        attempts=1,
        result={
            "event_id": event_id,
            "decision": "Needs manual audio review",
            "reference_text": None,
            "scenario_tag": "numbers",
            "manual_review_question": "Confirm the spoken digits.",
        },
    )
    assert await store.materialize_pass2_results(str(batch["id"])) == (1, 0)
    await store.freeze_preliminary_report(str(batch["id"]))
    current = await store.set_batch_state(
        str(batch["id"]),
        status="awaiting_review",
        stage="manual_review",
        progress=92,
        review_total=1,
    )
    review = (await store.list_reviews())[0]
    return current, review


@pytest.mark.asyncio
async def test_audit_only_batch_is_excluded_from_formal_outputs(
    evaluation_store: EvaluationStore,
) -> None:
    """Audit-only evidence must not appear as a report, review, or Benchmark result."""
    batch, review = await _prepare_pending_review(
        evaluation_store,
        run_key="audit-only-run",
    )
    async with aiosqlite.connect(evaluation_store.database_path) as connection:
        await connection.execute(
            """INSERT INTO evaluation_benchmarks (
               id,batch_id,conversation_id,event_id,case_type,source,language,
               scenario_tag,label,audio_start_s,audio_end_s,positioning_quality,created_at
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "BM-AUDIT-ONLY",
                batch["id"],
                review["conversation_id"],
                review["event_id"],
                "bad",
                "ai",
                "ar",
                "numbers",
                "audit evidence",
                0.0,
                1.0,
                "exact",
                "2026-09-17T00:00:00+00:00",
            ),
        )
        await connection.commit()

    isolated = await evaluation_store.mark_batch_audit_only(
        str(batch["id"]),
        reason="PD-010",
    )
    assert isolated["result_disposition"] == "audit_only"
    assert isolated["report_type"] is None
    assert isolated["audit_report_type"] == "preliminary"
    assert await evaluation_store.list_reviews("pending") == []
    assert (await evaluation_store.list_benchmarks(limit=20))["total"] == 0
    assert (await evaluation_store.summary())["benchmark_count"] == 0

    app = FastAPI()
    app.include_router(create_evaluation_router(evaluation_store))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        report = await client.get(f"/api/evaluation/batches/{batch['id']}/report")
        assert report.status_code == 409
        assert "audit-only" in report.json()["detail"]
        evidence = await client.get(f"/api/evaluation/batches/{batch['id']}/audit-evidence")
        assert evidence.status_code == 200
        assert evidence.json()["audit_only"] is True
        assert evidence.json()["formal_report"] is False
        deleted = await client.request(
            "DELETE",
            f"/api/evaluation/batches/{batch['id']}",
            json={
                "expected_version": isolated["version"],
                "idempotency_key": "delete-audit-only-command",
            },
        )
        assert deleted.status_code == 200
        assert deleted.json() == {"id": batch["id"], "deleted": True}

    assert await evaluation_store.get_batch(str(batch["id"])) is None
    async with aiosqlite.connect(evaluation_store.database_path) as connection:
        review_count = (
            await (
                await connection.execute(
                    "SELECT COUNT(*) FROM evaluation_reviews WHERE batch_id=?",
                    (batch["id"],),
                )
            ).fetchone()
        )[0]
        benchmark_count = (
            await (
                await connection.execute(
                    "SELECT COUNT(*) FROM evaluation_benchmarks WHERE batch_id=?",
                    (batch["id"],),
                )
            ).fetchone()
        )[0]
    assert review_count == 0
    assert benchmark_count == 0


@pytest.mark.asyncio
async def test_scenario_tags_are_versioned_tombstoned_and_restart_safe(
    evaluation_store: EvaluationStore,
) -> None:
    """Tag mutations must preserve versions and hide tombstones from new work."""
    seeded = await evaluation_store.list_scenario_tags()
    assert len(seeded) == 5
    assert {tag["enabled"] for tag in seeded} == {True, False}

    app = FastAPI()
    app.include_router(create_evaluation_router(evaluation_store))
    payload: dict[str, object] = {
        "name_en": "Speaker overlap",
        "name_zh": "说话人重叠",
        "description_en": "Agent speech overlaps the customer channel.",
        "description_zh": "坐席语音与用户声道重叠。",
        "tag_type": "acoustic",
        "examples": ["agent leakage"],
    }
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        created = await client.post("/api/evaluation/scenario-tags", json=payload)
        assert created.status_code == 201
        tag = created.json()
        assert tag["current_version"] == 1

        payload.update(
            {
                "description_en": "Agent or robot speech overlaps the customer channel.",
                "expected_version": 1,
            }
        )
        updated = await client.put(f"/api/evaluation/scenario-tags/{tag['id']}", json=payload)
        assert updated.status_code == 200
        assert updated.json()["current_version"] == 2

        disabled = await client.patch(
            f"/api/evaluation/scenario-tags/{tag['id']}/status",
            json={"enabled": False, "expected_version": 2},
        )
        assert disabled.status_code == 200
        assert disabled.json()["enabled"] is False

        deleted = await client.delete(
            f"/api/evaluation/scenario-tags/{tag['id']}",
            params={"expected_version": 2},
        )
        assert deleted.status_code == 204
        assert tag["id"] not in {
            current["id"] for current in (await client.get("/api/evaluation/scenario-tags")).json()
        }

    async with aiosqlite.connect(evaluation_store.database_path) as database:
        versions = await (
            await database.execute(
                "SELECT COUNT(*) FROM evaluation_scenario_tag_versions WHERE tag_id=?",
                (tag["id"],),
            )
        ).fetchone()
        tombstone = await (
            await database.execute(
                "SELECT deleted_at FROM evaluation_scenario_tags WHERE id=?",
                (tag["id"],),
            )
        ).fetchone()
    assert versions == (2,)
    assert tombstone is not None and tombstone[0]


@pytest.mark.asyncio
async def test_context_versions_and_prompt_contract_are_persisted_in_batch_snapshot(
    evaluation_store: EvaluationStore,
) -> None:
    """New batches must freeze persisted configuration instead of module fixtures."""
    contexts = await evaluation_store.list_contexts()
    seeded = contexts[0]
    payload = EvaluationContextWrite(
        name=seeded["name"],
        business_scope=seeded["business_scope"],
        business_background_and_objective="Persisted objective for this acceptance run.",
        standard_business_flow=seeded["standard_business_flow"],
        terms_and_key_entities=seeded["terms_and_key_entities"],
        dialogue_and_decision_rules=seeded["dialogue_and_decision_rules"],
        known_asr_risks=seeded["known_asr_risks"],
        dictionary_version_ids=seeded["dictionary_version_ids"],
        expected_version=seeded["current_version"],
    )
    updated = await evaluation_store.write_context(payload, seeded["id"])
    assert updated["current_version"] == 4

    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="Frozen configuration run",
            asr_providers=["soniox"],
            pass_1_model="qwen-plus",
            pass_2_model="qwen-plus",
            budget_limit=10,
            idempotency_key="frozen-configuration-run",
        )
    )
    assert batch["context_name"].endswith("v4")
    assert (
        batch["snapshot"]["evaluation_context"]["business_background_and_objective"]
        == "Persisted objective for this acceptance run."
    )
    assert batch["snapshot"]["reference_dictionaries"][0]["version"] == "v1"
    assert batch["snapshot"]["pass_1_prompt"]["current_version"] == 1
    expected_expiry = str(int(batch["created_at"][:4]) + 10) + batch["created_at"][4:]
    assert batch["snapshot"]["retention"] == {
        "class": "evaluation_10y",
        "expires_at": expected_expiry,
        "automatic_cleanup_before_expiry": False,
    }

    prompt = next(
        item
        for item in await evaluation_store.prompt_templates()
        if item["template_key"] == "pass_1"
    )
    updated_prompt = await evaluation_store.update_prompt_template(
        "pass_1",
        PromptTemplateWrite(
            content=prompt["content"] + "\nKeep the issues and event_results contract.",
            expected_version=1,
        ),
    )
    assert updated_prompt["current_version"] == 2
    async with aiosqlite.connect(evaluation_store.database_path) as database:
        versions = await (
            await database.execute(
                """SELECT COUNT(*) FROM evaluation_prompt_template_versions
                   WHERE template_key='pass_1'"""
            )
        ).fetchone()
    assert versions == (2,)


@pytest.mark.asyncio
async def test_prompt_history_restore_and_contract_validation(
    evaluation_store: EvaluationStore,
) -> None:
    """Prompt history must remain immutable and restore by appending a version."""
    original = next(
        item
        for item in await evaluation_store.prompt_templates()
        if item["template_key"] == "pass_2"
    )
    changed_content = original["content"] + "\nUse concise evidence explanations."
    changed = await evaluation_store.update_prompt_template(
        "pass_2",
        PromptTemplateWrite(content=changed_content, expected_version=1),
    )
    assert changed["current_version"] == 2

    history = await evaluation_store.prompt_template_versions("pass_2")
    assert [item["version"] for item in history] == [2, 1]
    assert history[0]["is_current"] is True
    assert history[1]["content"] == original["content"]

    restored = await evaluation_store.restore_prompt_template(
        "pass_2",
        PromptTemplateRestore(source_version=1, expected_version=2),
    )
    assert restored["current_version"] == 3
    assert restored["content"] == original["content"]
    history = await evaluation_store.prompt_template_versions("pass_2")
    assert [item["version"] for item in history] == [3, 2, 1]
    assert history[1]["content"] == changed_content

    with pytest.raises(RuntimeError, match="changed"):
        await evaluation_store.restore_prompt_template(
            "pass_2",
            PromptTemplateRestore(source_version=1, expected_version=2),
        )
    with pytest.raises(LookupError, match="version"):
        await evaluation_store.restore_prompt_template(
            "pass_2",
            PromptTemplateRestore(source_version=99, expected_version=3),
        )
    with pytest.raises(ValueError, match="confidence"):
        await evaluation_store.update_prompt_template(
            "pass_2",
            PromptTemplateWrite(
                content=original["content"] + '\n{"confidence": 0.9}',
                expected_version=3,
            ),
        )


@pytest.mark.asyncio
async def test_batch_worker_lease_blocks_duplicates_and_recovers_expiry(
    evaluation_store: EvaluationStore,
) -> None:
    """Only one process may own a batch until its durable lease expires."""
    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="Lease test",
            asr_providers=["soniox"],
            pass_1_model="deepseek-chat",
            pass_2_model="deepseek-chat",
            budget_limit=10,
            idempotency_key="lease-test-batch",
        )
    )

    assert await evaluation_store.acquire_batch_lease(batch["id"], "worker-a")
    assert not await evaluation_store.acquire_batch_lease(batch["id"], "worker-b")
    assert await evaluation_store.renew_batch_lease(batch["id"], "worker-a")
    await evaluation_store.release_batch_lease(batch["id"], "worker-a")
    assert await evaluation_store.acquire_batch_lease(batch["id"], "worker-b", ttl_seconds=-1)
    assert await evaluation_store.acquire_batch_lease(batch["id"], "worker-c")


@pytest.mark.asyncio
async def test_source_audit_uses_real_files(
    evaluation_store: EvaluationStore,
) -> None:
    """The audit should expose source facts without manufactured result metrics."""
    fixture = evaluation_store.fixture_status()
    audit = evaluation_store.dataset_audit()
    summary = await evaluation_store.summary()

    assert fixture["valid"] is True
    assert fixture["matched_conversations"] == 56
    assert fixture["counts"] == {
        "conversation_history": 56,
        "record": 56,
        "user_record": 56,
    }
    assert fixture["provider_results"] == "not_run"
    assert audit["event_count"] == 853
    assert audit["user_event_count"] == 381
    assert audit["robot_event_count"] == 472
    assert audit["valid_conversations"] == 56
    assert len(audit["issues"]) == 55
    assert audit["blocking_issue_count"] == 0
    assert audit["warning_count"] == 55
    assert audit["blocking_issues"] == []
    assert {issue["issue_type"] for issue in audit["warnings"]} == {
        "decreasing_event_time",
        "event_outside_audio",
    }
    assert summary["suspected_numerator"] is None
    assert summary["source_user_events"] == 381
    assert summary["valid_user_events"] is None
    assert summary["benchmark_count"] == 0


@pytest.mark.asyncio
async def test_conversation_uses_actual_arabic_transcript(
    evaluation_store: EvaluationStore,
) -> None:
    """Conversation details must come from the workbook, including Excel row IDs."""
    conversation = await evaluation_store.get_conversation("1030000000091506")

    assert conversation is not None
    assert conversation["detected_language"] == "ar"
    assert conversation["event_count"] == 22
    event = next(item for item in conversation["events"] if item["event_id"] == "R18")
    assert event == {
        "event_id": "R18",
        "source_row": 18,
        "time_s": pytest.approx(74.818),
        "speaker": "customer",
        "text": "أقول لك أنا، أنا عميلة الهدية.",
    }
    assert conversation["record_audio"]["duration_s"] == pytest.approx(
        102.8,
        abs=0.02,
    )


@pytest.mark.asyncio
async def test_full_conversation_audio_is_resolved_safely(
    evaluation_store: EvaluationStore,
) -> None:
    """Playback paths should resolve real files without allowing path traversal."""
    audio = evaluation_store.conversation_audio_path("1030000000091506")
    user_audio = evaluation_store.conversation_user_audio_path("1030000000091506")

    assert audio is not None and audio.name == "1030000000091506.mp3"
    assert audio.stat().st_size > 1000
    assert user_audio is not None and user_audio.name == "1030000000091506.wav"
    assert user_audio.stat().st_size > 1000
    assert evaluation_store.conversation_audio_path("../1030000000091506") is None
    assert evaluation_store.conversation_user_audio_path("../1030000000091506") is None


def test_scenario_labels_map_to_the_correct_stable_taxonomy() -> None:
    """Customer-tier evidence must never be stored under the branch-name tag."""
    assert EvaluationStore._scenario_key("客户类别") == "customer_tier"
    assert EvaluationStore._scenario_key("Customer tier") == "customer_tier"
    assert EvaluationStore._scenario_key("分行名称与城市") == "branches"
    assert EvaluationStore._scenario_key("unknown model label") == "unclassified"


@pytest.mark.asyncio
async def test_reference_warnings_allow_batch_without_fake_results(
    evaluation_store: EvaluationStore,
) -> None:
    """Timeline warnings must allow a real run without manufacturing results."""
    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="Real source run",
            asr_providers=["soniox", "speechmatics", "elevenlabs"],
            pass_1_model="gemini-3.8-flash",
            pass_2_model="gpt-5-mini",
            budget_limit=10,
            idempotency_key="real-run-001",
        )
    )

    assert batch["status"] == "running"
    assert batch["stage"] == "pass_1"
    assert batch["snapshot"]["mock_external_calls"] is False
    assert batch["snapshot"]["provider_execution"] == "queued"
    assert len(await evaluation_store.list_batches()) == 1
    assert await evaluation_store.list_reviews() == []
    assert (await evaluation_store.list_benchmarks())["total"] == 0


@pytest.mark.asyncio
async def test_batch_actions_are_optimistic_and_idempotent(
    evaluation_store: EvaluationStore,
) -> None:
    """User retries must replay transitions without advancing versions twice."""
    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="Batch action lifecycle",
            asr_providers=["soniox"],
            pass_1_model="gemini-3.8-flash",
            pass_2_model="gpt-5-mini",
            budget_limit=10,
            idempotency_key="batch-action-lifecycle-create",
        )
    )
    pause = EvaluationBatchAction(
        action="pause",
        expected_version=int(batch["version"]),
        idempotency_key="batch-action-lifecycle-pause",
    )
    paused = await evaluation_store.act_on_batch(str(batch["id"]), pause)
    replayed = await evaluation_store.act_on_batch(str(batch["id"]), pause)
    assert paused == replayed
    assert paused["status"] == "paused"

    resumed = await evaluation_store.act_on_batch(
        str(batch["id"]),
        EvaluationBatchAction(
            action="resume",
            expected_version=int(paused["version"]),
            idempotency_key="batch-action-lifecycle-resume",
        ),
    )
    assert resumed["status"] == "running"
    stopped = await evaluation_store.act_on_batch(
        str(batch["id"]),
        EvaluationBatchAction(
            action="stop",
            expected_version=int(resumed["version"]),
            idempotency_key="batch-action-lifecycle-stop",
        ),
    )
    assert stopped["status"] == "stopped"
    with pytest.raises(RuntimeError, match="changed"):
        await evaluation_store.act_on_batch(
            str(batch["id"]),
            EvaluationBatchAction(
                action="resume",
                expected_version=int(paused["version"]),
                idempotency_key="batch-action-lifecycle-stale",
            ),
        )


@pytest.mark.asyncio
async def test_batch_delete_requires_safe_terminal_state_and_preserves_source(
    evaluation_store: EvaluationStore,
) -> None:
    """Deletion removes batch-owned state but never orphans active work or source data."""
    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="Mistaken batch",
            asr_providers=["soniox"],
            pass_1_model="gemini-3.8-flash",
            pass_2_model="gpt-5-mini",
            budget_limit=10,
            idempotency_key="delete-safe-create",
        )
    )
    with pytest.raises(RuntimeError, match="Stop"):
        await evaluation_store.delete_batch(
            str(batch["id"]),
            expected_version=int(batch["version"]),
            idempotency_key="delete-active-command",
        )

    stopped = await evaluation_store.act_on_batch(
        str(batch["id"]),
        EvaluationBatchAction(
            action="stop",
            expected_version=int(batch["version"]),
            idempotency_key="delete-safe-stop",
        ),
    )
    deleted = await evaluation_store.delete_batch(
        str(batch["id"]),
        expected_version=int(stopped["version"]),
        idempotency_key="delete-safe-command",
    )
    replayed = await evaluation_store.delete_batch(
        str(batch["id"]),
        expected_version=int(stopped["version"]),
        idempotency_key="delete-safe-command",
    )

    assert deleted == replayed == {"id": batch["id"], "deleted": True}
    assert await evaluation_store.get_batch(str(batch["id"])) is None
    assert await evaluation_store.get_conversation(_VALID_CONVERSATION_ID) is not None
    async with aiosqlite.connect(evaluation_store.database_path) as connection:
        tombstone = await (
            await connection.execute(
                """SELECT metadata_json FROM evaluation_audit
                   WHERE action='batch.deleted' AND object_id=?""",
                (batch["id"],),
            )
        ).fetchone()
    assert tombstone is not None
    assert json.loads(tombstone[0]) == {"audit_only": False, "prior_status": "stopped"}


@pytest.mark.asyncio
async def test_batch_delete_allows_awaiting_review_after_confirmation(
    evaluation_store: EvaluationStore,
) -> None:
    """A finished run awaiting review is safe to delete explicitly."""
    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="Reviewed later",
            asr_providers=["soniox"],
            pass_1_model="gemini-3.8-flash",
            pass_2_model="gpt-5-mini",
            budget_limit=10,
            idempotency_key="delete-awaiting-create",
        )
    )
    awaiting_review = await evaluation_store.set_batch_state(
        str(batch["id"]),
        status="awaiting_review",
        stage="manual_review",
        progress=100,
    )

    deleted = await evaluation_store.delete_batch(
        str(batch["id"]),
        expected_version=int(awaiting_review["version"]),
        idempotency_key="delete-awaiting-command",
    )

    assert deleted == {"id": batch["id"], "deleted": True}
    assert await evaluation_store.get_batch(str(batch["id"])) is None
    assert await evaluation_store.get_conversation(_VALID_CONVERSATION_ID) is not None


@pytest.mark.asyncio
async def test_batch_delete_allows_completed_partial_terminal_state(
    evaluation_store: EvaluationStore,
) -> None:
    """A terminal partial report is deletable through the supported cleanup path."""
    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="Partial report rerun",
            asr_providers=["soniox"],
            pass_1_model="gemini-3.8-flash",
            pass_2_model="gpt-5-mini",
            budget_limit=10,
            idempotency_key="delete-partial-create",
        )
    )
    completed_partial = await evaluation_store.set_batch_state(
        str(batch["id"]),
        status="completed_partial",
        stage="completed",
        progress=100,
    )

    deleted = await evaluation_store.delete_batch(
        str(batch["id"]),
        expected_version=int(completed_partial["version"]),
        idempotency_key="delete-partial-command",
    )

    assert deleted == {"id": batch["id"], "deleted": True}
    assert await evaluation_store.get_batch(str(batch["id"])) is None
    assert await evaluation_store.get_conversation(_VALID_CONVERSATION_ID) is not None


@pytest.mark.asyncio
async def test_batch_freezes_fx_version_and_ledger_converts_without_losing_cny(
    evaluation_store: EvaluationStore,
) -> None:
    """Mixed-currency ledgers retain original amounts and freeze one USD conversion."""
    saved = await evaluation_store.save_pricing_version(
        cny_to_usd=0.15,
        source_note="Finance-approved acceptance rate",
    )
    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="Mixed currency run",
            asr_providers=["soniox"],
            pass_1_model="qwen-plus",
            pass_2_model="deepseek-chat",
            budget_limit=10,
            idempotency_key="mixed-currency-run",
        )
    )
    assert batch["snapshot"]["pricing_version"]["version"] == saved["version"]
    await evaluation_store.record_cost_entry(
        idempotency_key="mixed-currency-run:qwen",
        batch_id=str(batch["id"]),
        category="llm",
        provider="qwen",
        stage="pass_1",
        input_tokens=100,
        estimated_cost=10,
        currency="CNY",
    )
    await evaluation_store.record_cost_entry(
        idempotency_key="mixed-currency-run:soniox",
        batch_id=str(batch["id"]),
        category="asr",
        provider="soniox",
        stage="evaluation_asr",
        audio_seconds=60,
        estimated_cost=1,
        currency="USD",
    )

    ledger = await evaluation_store.cost_summary(str(batch["id"]))
    qwen = ledger["llm"][0]
    assert qwen["currency"] == "CNY"
    assert qwen["estimated_cost"] == pytest.approx(10)
    assert qwen["fx_to_usd"] == pytest.approx(0.15)
    assert qwen["converted_usd"] == pytest.approx(1.5)
    assert ledger["total_usd"] == pytest.approx(2.5)
    refreshed = await evaluation_store.get_batch(str(batch["id"]))
    assert refreshed is not None
    assert refreshed["cost"] == pytest.approx(2.5)


@pytest.mark.asyncio
async def test_pricing_version_freezes_reviewed_rates_and_default_budget(
    evaluation_store: EvaluationStore,
) -> None:
    """Saved rates and the default hard limit must survive reloads and freeze per batch."""
    current = await evaluation_store.active_pricing_version()
    llm_rates = [dict(item) for item in current["rates"]["llm"]]
    deepseek = next(
        item
        for item in llm_rates
        if item["provider"] == "DeepSeek" and item["model"] == "deepseek-flash"
    )
    deepseek["input_per_1m"] = 0.31
    deepseek["cached_input_per_1m"] = 0.031
    deepseek["output_per_1m"] = 1.21
    saved = await evaluation_store.save_pricing_version(
        cny_to_usd=0.15,
        source_note="Reviewed acceptance rates",
        default_batch_budget=12.5,
        asr_rates=current["rates"]["asr"],
        llm_rates=llm_rates,
    )
    assert saved["default_batch_budget"] == pytest.approx(12.5)
    assert next(
        item
        for item in saved["rates"]["llm"]
        if item["provider"] == "DeepSeek" and item["model"] == "deepseek-flash"
    )["input_per_1m"] == pytest.approx(0.31)

    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="Frozen reviewed prices",
            asr_providers=["soniox"],
            pass_1_model="deepseek-chat",
            pass_2_model="deepseek-chat",
            budget_limit=saved["default_batch_budget"],
            idempotency_key="frozen-reviewed-prices",
        )
    )
    assert batch["snapshot"]["pricing_version"]["version"] == saved["version"]
    amount, currency = EvaluationRunner._frozen_llm_cost(
        batch,
        "deepseek",
        "deepseek-chat",
        input_tokens=1_000_000,
        cached_input_tokens=0,
        reasoning_tokens=100_000,
        output_tokens=200_000,
    )
    assert amount == pytest.approx(0.31 + 0.3 * 1.21)
    assert currency == "USD"


@pytest.mark.asyncio
async def test_context_default_and_availability_are_persisted_without_rewriting_versions(
    evaluation_store: EvaluationStore,
) -> None:
    """Only enabled contexts are selectable and exactly one protected default remains."""
    initial = (await evaluation_store.list_contexts())[0]
    with pytest.raises(ValueError, match="another default"):
        await evaluation_store.set_context_status(
            str(initial["id"]),
            enabled=False,
            is_default=None,
            expected_version=int(initial["current_version"]),
        )

    created = await evaluation_store.write_context(
        EvaluationContextWrite(
            context_key="second_context",
            name="Second context",
            business_scope="A second business scope",
            business_background_and_objective="Validate default selection behavior.",
            standard_business_flow="Receive, verify, and route the request.",
            terms_and_key_entities="Branch, customer, and transfer.",
            dialogue_and_decision_rules="Use source evidence only.",
            known_asr_risks="Mixed-language names and digits.",
            dictionary_version_ids=[],
        )
    )
    selected = await evaluation_store.set_context_status(
        str(created["id"]),
        enabled=None,
        is_default=True,
        expected_version=int(created["current_version"]),
    )
    assert selected["is_default"] is True
    assert selected["enabled"] is True
    assert selected["current_version"] == created["current_version"]

    disabled = await evaluation_store.set_context_status(
        str(initial["id"]),
        enabled=False,
        is_default=None,
        expected_version=int(initial["current_version"]),
    )
    assert disabled["enabled"] is False
    with pytest.raises(ValueError, match="unavailable"):
        await evaluation_store.context_snapshot(str(initial["context_key"]))


@pytest.mark.asyncio
async def test_budget_reservations_atomically_stop_before_the_next_external_call(
    evaluation_store: EvaluationStore,
) -> None:
    """Concurrent workers cannot reserve beyond the batch's frozen hard limit."""
    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="Budget reservation run",
            asr_providers=["soniox"],
            pass_1_model="deepseek-chat",
            pass_2_model="deepseek-chat",
            budget_limit=0.01,
            idempotency_key="budget-reservation-run",
        )
    )
    assert batch["snapshot"]["pricing_version"]["rates"]["asr"]
    assert batch["status"] == "running"
    outcomes = await asyncio.gather(
        evaluation_store.reserve_budget(
            idempotency_key="reserve-a",
            batch_id=str(batch["id"]),
            estimated_usd=0.006,
        ),
        evaluation_store.reserve_budget(
            idempotency_key="reserve-b",
            batch_id=str(batch["id"]),
            estimated_usd=0.006,
        ),
    )
    assert sorted(outcomes) == [False, True]
    paused = await evaluation_store.get_batch(str(batch["id"]))
    assert paused is not None
    assert paused["status"] == "budget_paused"
    await evaluation_store.release_budget("reserve-a")
    await evaluation_store.release_budget("reserve-b")
    resumed = await evaluation_store.act_on_batch(
        str(batch["id"]),
        EvaluationBatchAction(
            action="resume",
            expected_version=int(paused["version"]),
            idempotency_key="budget-reservation-resume",
        ),
    )
    assert resumed["status"] == "running"


@pytest.mark.asyncio
async def test_execution_checkpoints_materialize_real_manual_review(
    evaluation_store: EvaluationStore,
) -> None:
    """Restart checkpoints must project a Pass 2 manual decision into the review queue."""
    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="Checkpoint run",
            asr_providers=["elevenlabs"],
            pass_1_model="deepseek-chat",
            pass_2_model="deepseek-chat",
            budget_limit=10,
            idempotency_key="checkpoint-run-001",
        )
    )
    conversation = await evaluation_store.get_conversation(_VALID_CONVERSATION_ID)
    assert conversation is not None
    event = next(item for item in conversation["events"] if item["speaker"] == "customer")
    event_id = str(event["event_id"])
    incomplete_event = next(
        item
        for item in conversation["events"]
        if item["speaker"] == "customer" and str(item["event_id"]) != event_id
    )
    await evaluation_store.checkpoint_result(
        "evaluation_pass1_runs",
        (batch["id"], _VALID_CONVERSATION_ID),
        status="completed",
        attempts=1,
        result={
            "issues": [
                {
                    "issue_id": "I1",
                    "title": "数字需核验",
                    "priority": "P1",
                    "target_events": [
                        {
                            "event_id": event_id,
                            "decision": "candidate",
                            "verification_question": "用户实际说了什么？",
                        },
                        {
                            "event_id": str(incomplete_event["event_id"]),
                            "decision": "candidate",
                            "verification_question": "第二个事件尚未完成第二轮。",
                        },
                    ],
                }
            ],
            "event_results": [],
        },
    )
    await evaluation_store.checkpoint_result(
        "evaluation_case_asr_runs",
        (batch["id"], "elevenlabs", _VALID_CONVERSATION_ID, event_id),
        status="completed",
        attempts=1,
        result={
            "text": "example",
            "segments": [
                {
                    "segment_id": "elevenlabs-1",
                    "start": event["time_s"],
                    "end": event["time_s"] + 1,
                    "text": "example",
                }
            ],
        },
        remote_job_id="job-1",
    )
    await evaluation_store.checkpoint_result(
        "evaluation_case_asr_runs",
        (
            batch["id"],
            "elevenlabs",
            _VALID_CONVERSATION_ID,
            str(incomplete_event["event_id"]),
        ),
        status="completed",
        attempts=1,
        result={
            "text": "raw ASR evidence",
            "source_clip": {
                "start_s": float(incomplete_event["time_s"]) - 0.5,
                "end_s": float(incomplete_event["time_s"]) + 1.0,
            },
            "segments": [],
        },
        remote_job_id="job-2",
    )
    await evaluation_store.checkpoint_result(
        "evaluation_pass2_runs",
        (batch["id"], _VALID_CONVERSATION_ID, event_id),
        status="completed",
        attempts=1,
        result={
            "event_id": event_id,
            "decision": "Needs manual audio review",
            "reference_text": None,
            "scenario_tag": "数字与分行代码",
            "manual_review_question": "请回听确认数字。",
            "vendor_evidence": [
                {
                    "provider": "elevenlabs",
                    "segment_ids": ["elevenlabs-1"],
                    "quoted_text": "case-level evidence",
                    "relationship_to_history": "ambiguous",
                }
            ],
            "proposed_tag": {
                "type": "semantic",
                "name_en": "Digit ambiguity",
                "name_zh": "数字歧义",
                "description_en": "Use when a digit sequence has conflicting evidence.",
                "description_zh": "用于数字序列存在冲突证据的情况。",
            },
        },
    )

    review_count, benchmark_count = await evaluation_store.materialize_pass2_results(batch["id"])
    await evaluation_store.checkpoint_result(
        "evaluation_asr_runs",
        (batch["id"], "speechmatics", _VALID_CONVERSATION_ID),
        status="failed",
        attempts=6,
        error=(
            '{"provider":"speechmatics","category":"provider_job_failed",'
            '"retryable":true,"message":"secret upstream body"}'
        ),
    )
    await evaluation_store.checkpoint_result(
        "evaluation_case_asr_runs",
        (
            batch["id"],
            "soniox",
            _VALID_CONVERSATION_ID,
            str(incomplete_event["event_id"]),
        ),
        status="failed",
        attempts=3,
        error=(
            '{"provider":"soniox","category":"timeout",'
            '"retryable":true,"message":"customer transcript must not leak"}'
        ),
    )
    await evaluation_store.set_batch_state(
        batch["id"],
        status="awaiting_review",
        stage="manual_review",
        progress=92,
        review_total=review_count,
    )
    assert await evaluation_store.latest_report(batch["id"]) is None
    await evaluation_store.set_batch_state(
        batch["id"],
        status="partially_failed",
        stage="failed",
        progress=90,
        snapshot_updates={
            "execution_failure": {
                "stage": "pass_2",
                "message": "One request group failed",
                "retryable": True,
            }
        },
    )
    partial = await evaluation_store.freeze_preliminary_report(batch["id"], persist=False)
    assert partial["report_type"] == "partial_results"
    assert partial["ephemeral"] is True
    assert partial["payload"]["non_final"] is True
    assert partial["payload"]["failed_stage"] == "pass_2"
    assert partial["payload"]["evaluated_case_count"] == 1
    assert partial["payload"]["incomplete_case_count"] == 1
    assert partial["payload"]["asr_failures"] == [
        {
            "provider": "speechmatics",
            "scope": "full_call_context",
            "conversation_id": _VALID_CONVERSATION_ID,
            "event_id": None,
            "attempts": 6,
            "category": "provider_job_failed",
            "retryable": True,
            "message": "Provider ASR job failed before producing a usable result.",
        },
        {
            "provider": "soniox",
            "scope": "event_clip",
            "conversation_id": _VALID_CONVERSATION_ID,
            "event_id": str(incomplete_event["event_id"]),
            "attempts": 3,
            "category": "timeout",
            "retryable": True,
            "message": "Provider request timed out. Retry the failed ASR work.",
        },
    ]
    assert "secret upstream body" not in json.dumps(partial)
    assert "customer transcript must not leak" not in json.dumps(partial)
    assert await evaluation_store.latest_report(batch["id"]) is None
    await evaluation_store.set_batch_state(
        batch["id"],
        status="awaiting_review",
        stage="manual_review",
        progress=92,
    )
    report = await evaluation_store.freeze_preliminary_report(batch["id"])

    assert (review_count, benchmark_count) == (1, 0)
    assert report is not None
    assert report["report_type"] == "preliminary"
    assert report["payload"]["candidate_count"] == 2
    assert report["payload"]["evaluated_case_count"] == 1
    assert report["payload"]["incomplete_case_count"] == 1
    assert report["payload"]["decision_counts"]["Needs manual audio review"] == 1
    completed_case = next(
        item for item in report["payload"]["cases"] if item["event_id"] == event_id
    )
    assert completed_case["production_transcript"] == event["text"]
    assert completed_case["evaluation_asr"] == {"elevenlabs": "case-level evidence"}
    incomplete_case = next(
        item
        for item in report["payload"]["cases"]
        if item["event_id"] == str(incomplete_event["event_id"])
    )
    assert incomplete_case["evaluation_asr"] == {"elevenlabs": "raw ASR evidence"}
    assert incomplete_case["audio_available"] is True
    assert report["payload"]["source_user_events"] >= report["payload"]["valid_user_events"]
    assert report["payload"]["language_distribution"] == [{"name": "ar", "count": 1}]
    assert report["payload"]["production_asr_observations"][0]["case_keys"] == [
        [_VALID_CONVERSATION_ID, event_id]
    ]
    assert (await evaluation_store.freeze_preliminary_report(batch["id"]))["report_id"] == report[
        "report_id"
    ]
    recovered_batch = await evaluation_store.get_batch(batch["id"])
    assert recovered_batch is not None
    assert recovered_batch["report_type"] == "preliminary"
    assert recovered_batch["snapshot"]["latest_report_id"] == report["report_id"]
    async with aiosqlite.connect(evaluation_store.database_path) as database:
        stale_snapshot = dict(recovered_batch["snapshot"])
        stale_snapshot.pop("latest_report_id", None)
        stale_snapshot.pop("latest_report_type", None)
        await database.execute(
            "UPDATE evaluation_batches SET report_type=NULL,snapshot_json=? WHERE id=?",
            (json.dumps(stale_snapshot), batch["id"]),
        )
        await database.commit()
    await evaluation_store.recover_missing_preliminary_reports()
    repaired_batch = await evaluation_store.get_batch(batch["id"])
    assert repaired_batch is not None
    assert repaired_batch["report_type"] == "preliminary"
    assert repaired_batch["snapshot"]["latest_report_id"] == report["report_id"]
    summary = await evaluation_store.summary()
    assert summary["suspected_numerator"] == 1
    assert summary["valid_user_events"] == repaired_batch["denominator"]
    assert summary["suspected_rate"] == round(1 / repaired_batch["denominator"] * 100, 1)
    reviews = await evaluation_store.list_reviews()
    assert reviews[0]["conversation_id"] == _VALID_CONVERSATION_ID
    assert reviews[0]["providers"][0]["text"] == "example"
    assert reviews[0]["issue_en"] == "Branch code needs audio confirmation"
    assert not any("\u4e00" <= character <= "\u9fff" for character in reviews[0]["question_en"])

    async with aiosqlite.connect(evaluation_store.database_path) as database:
        row = await (
            await database.execute(
                "SELECT payload_json FROM evaluation_reviews WHERE id=?", (reviews[0]["id"],)
            )
        ).fetchone()
        assert row is not None
        legacy_payload = json.loads(row[0])
        legacy_payload["issue_en"] = "分行代码可能识别错误"
        legacy_payload["question_en"] = "请回听用户实际说了什么？"
        await database.execute(
            "UPDATE evaluation_reviews SET payload_json=? WHERE id=?",
            (json.dumps(legacy_payload, ensure_ascii=False), reviews[0]["id"]),
        )
        await database.commit()

    reviews = await evaluation_store.list_reviews()
    assert reviews[0]["issue_en"] == "Branch code needs audio confirmation"
    assert reviews[0]["question_en"] == "Which digits or code did the customer actually say?"
    assert reviews[0]["issue_zh"] == "分行代码需要回听确认"

    submitted = await evaluation_store.submit_review(
        reviews[0]["id"],
        EvaluationReviewSubmit(
            decision="bad",
            label="Two two one",
            language="en",
            scenario_tag="numbers",
            expected_version=reviews[0]["version"],
            idempotency_key="review-final-report-test",
        ),
    )
    assert submitted["remaining"] == 0
    final = await evaluation_store.latest_report(batch["id"])
    assert final is not None
    assert final["version"] == 2
    assert final["report_type"] == "final"
    assert final["payload"]["manual_decision_counts"]["Bad Case"] == 1
    assert final["payload"]["cases"][0]["reference_text"] == "Two two one"
    assert final["payload"]["cases"][0]["label_status"] == "Manual labeled"

    await evaluation_store.record_cost_entry(
        idempotency_key=f"{batch['id']}:asr:elevenlabs:{_VALID_CONVERSATION_ID}",
        batch_id=batch["id"],
        category="asr",
        provider="elevenlabs",
        stage="evaluation_asr",
        audio_seconds=60,
        estimated_cost=0.22,
    )
    await evaluation_store.record_cost_entry(
        idempotency_key=f"{batch['id']}:pass2:group-1:1",
        batch_id=batch["id"],
        category="llm",
        provider="deepseek",
        stage="pass_2",
        input_tokens=1200,
        reasoning_tokens=300,
        output_tokens=180,
    )
    ledger = await evaluation_store.cost_summary(batch["id"])
    assert ledger["asr"][0]["audio_seconds"] == 60
    assert ledger["asr"][0]["estimated_cost"] == pytest.approx(0.22)
    assert ledger["llm"][0]["input_tokens"] == 1200
    assert ledger["llm"][0]["reasoning_tokens"] == 300
    trace_id = await evaluation_store.record_telemetry(
        batch_id=batch["id"],
        stage="pass_2",
        event="llm_request",
        provider="deepseek",
        outcome="completed",
        attempt=2,
        latency_ms=125.5,
        queue_depth=3,
    )
    await evaluation_store.record_telemetry(
        batch_id=batch["id"],
        stage="pass_2",
        event="schema_failure",
        provider="deepseek",
        outcome="failed",
        attempt=1,
        latency_ms=15,
        trace_id=trace_id,
    )
    telemetry = await evaluation_store.telemetry_summary(batch["id"])
    assert telemetry["schema_failures"] == 1
    assert telemetry["costs"]["total_usd"] == pytest.approx(0.22)
    request_counter = next(row for row in telemetry["counters"] if row["event"] == "llm_request")
    assert request_counter["retries"] == 1
    assert request_counter["max_queue_depth"] == 3
    assert telemetry["recent_traces"][0]["trace_id"] == trace_id

    proposed = report["payload"]["proposed_tags"][0]
    created_tag = await evaluation_store.create_proposed_tag(
        report["report_id"], proposed["proposal_key"]
    )
    assert created_tag["name_en"] == "Digit ambiguity"
    assert (
        await evaluation_store.create_proposed_tag(report["report_id"], proposed["proposal_key"])
    )["id"] == created_tag["id"]
    benchmark = (await evaluation_store.list_benchmarks(limit=1))["items"][0]
    revisions = await evaluation_store.benchmark_revisions(benchmark["id"])
    assert len(revisions) == 2
    assert revisions[0]["scenario_tag"] == "numbers"
    assert revisions[1]["scenario_tag"].startswith("custom-")
    filtered = await evaluation_store.list_benchmarks(
        case_type="bad",
        search=str(benchmark["conversation_id"]),
        limit=20,
        offset=0,
    )
    assert filtered["total"] == 1
    corrected = await evaluation_store.update_benchmark(
        str(benchmark["id"]),
        label="Two two one.",
        language="en",
        scenario_tag="numbers",
        expected_revision=int(benchmark["revision"]),
    )
    assert corrected["revision"] == 3
    assert len(await evaluation_store.benchmark_revisions(str(benchmark["id"]))) == 3


@pytest.mark.asyncio
async def test_early_review_completion_is_idempotent(
    evaluation_store: EvaluationStore,
) -> None:
    """A retried early-completion command must return the frozen response unchanged."""
    batch, _review = await _prepare_pending_review(
        evaluation_store,
        run_key="early-completion-run",
    )
    app = FastAPI()
    app.include_router(create_evaluation_router(evaluation_store))
    command = {
        "expected_version": batch["version"],
        "idempotency_key": "complete-review-command",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post(
            f"/api/evaluation/batches/{batch['id']}/complete-review",
            json=command,
        )
        repeated = await client.post(
            f"/api/evaluation/batches/{batch['id']}/complete-review",
            json=command,
        )

    assert first.status_code == 200
    assert repeated.status_code == 200
    assert repeated.json() == first.json()
    assert first.json()["report_type"] == "final_partial"
    assert first.json()["payload"]["review_pending"] == 1
    assert (await evaluation_store.list_benchmarks())["total"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("batch_status", ["paused", "partially_failed"])
async def test_incomplete_batch_can_finish_with_current_results_without_retry(
    evaluation_store: EvaluationStore,
    batch_status: str,
) -> None:
    """A force finish must freeze only durable results and never resume execution."""
    batch, review = await _prepare_pending_review(
        evaluation_store,
        run_key="finish-current-results-run",
    )
    paused = await evaluation_store.set_batch_state(
        str(batch["id"]),
        status=batch_status,
        stage="evaluation_asr",
        progress=53,
        cost=1.25,
    )
    app = FastAPI()
    app.include_router(create_evaluation_router(evaluation_store))
    command = {
        "expected_version": paused["version"],
        "idempotency_key": "finish-current-results-command",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post(
            f"/api/evaluation/batches/{batch['id']}/complete-with-current-results",
            json=command,
        )
        repeated = await client.post(
            f"/api/evaluation/batches/{batch['id']}/complete-with-current-results",
            json=command,
        )

    assert first.status_code == 200
    assert repeated.json() == first.json()
    report = first.json()
    assert report["report_type"] == "final_partial"
    assert report["payload"]["completion_mode"] == "current_results"
    assert report["payload"]["partial_coverage"] is True
    assert report["payload"]["review_pending"] == 1
    assert report["payload"]["result_excluded_count"] == 1
    assert report["payload"]["cases"][0]["decision"] == "Not completed"
    assert report["payload"]["cases"][0]["label_status"] == "Excluded as unreviewed"
    final_batch = await evaluation_store.get_batch(str(batch["id"]))
    assert final_batch is not None
    assert final_batch["status"] == "completed_partial"
    assert final_batch["stage"] == "completed"
    assert final_batch["progress"] == 100
    assert final_batch["cost"] == pytest.approx(1.25)
    pass_two = await evaluation_store.checkpoint_rows(
        "evaluation_pass2_runs",
        str(batch["id"]),
    )
    assert len(pass_two) == 1
    assert pass_two[0]["status"] == "completed"
    pending_reviews = await evaluation_store.list_reviews("pending")
    assert [item["id"] for item in pending_reviews] == [review["id"]]


@pytest.mark.asyncio
async def test_running_batch_cannot_finish_with_current_results(
    evaluation_store: EvaluationStore,
) -> None:
    """Operators must pause active work before freezing partial coverage."""
    batch, _review = await _prepare_pending_review(
        evaluation_store,
        run_key="reject-running-finish-current-run",
    )
    running = await evaluation_store.set_batch_state(
        str(batch["id"]),
        status="running",
        stage="pass_2",
        progress=75,
    )
    app = FastAPI()
    app.include_router(create_evaluation_router(evaluation_store))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            f"/api/evaluation/batches/{batch['id']}/complete-with-current-results",
            json={
                "expected_version": running["version"],
                "idempotency_key": "reject-running-finish-command",
            },
        )

    assert response.status_code == 422
    current = await evaluation_store.get_batch(str(batch["id"]))
    assert current is not None
    assert current["status"] == "running"
    latest = await evaluation_store.latest_report(str(batch["id"]))
    assert latest is not None
    assert latest["report_type"] == "preliminary"


@pytest.mark.asyncio
async def test_unclear_review_is_excluded_from_benchmark(
    evaluation_store: EvaluationStore,
) -> None:
    """Unclear decisions remain auditable but never create a Benchmark sample."""
    batch, review = await _prepare_pending_review(
        evaluation_store,
        run_key="unclear-review-run",
    )
    result = await evaluation_store.submit_review(
        str(review["id"]),
        EvaluationReviewSubmit(
            decision="unclear",
            label=None,
            language="ar",
            scenario_tag="numbers",
            expected_version=int(str(review["version"])),
            idempotency_key="unclear-review-command",
        ),
    )

    assert result["remaining"] == 0
    assert (await evaluation_store.list_benchmarks())["total"] == 0
    report = await evaluation_store.latest_report(str(batch["id"]))
    assert report is not None
    assert report["payload"]["manual_decision_counts"]["Unclear"] == 1
    assert report["payload"]["cases"][0]["label_status"] == "Excluded as unclear"


@pytest.mark.asyncio
async def test_execution_progress_uses_real_checkpoint_counts(
    evaluation_store: EvaluationStore,
) -> None:
    """Polling state should expose real completed and failed item counts."""
    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="Progress run",
            asr_providers=["elevenlabs"],
            pass_1_model="deepseek-chat",
            pass_2_model="deepseek-chat",
            budget_limit=10,
            idempotency_key="progress-run-001",
        )
    )
    await evaluation_store.checkpoint_result(
        "evaluation_pass1_runs",
        (batch["id"], "conversation-a"),
        status="completed",
        attempts=1,
        result={"issues": [], "event_results": []},
    )
    await evaluation_store.checkpoint_result(
        "evaluation_pass1_runs",
        (batch["id"], "conversation-b"),
        status="failed",
        attempts=3,
        error="timeout",
    )

    updated = await evaluation_store.refresh_execution_progress(
        batch["id"],
        table="evaluation_pass1_runs",
        stage="pass_1",
        total=4,
        progress_start=20,
        progress_end=45,
    )

    assert updated["progress"] == 26
    assert updated["snapshot"]["execution_status"]["pass_1"] == {
        "completed": 1,
        "failed": 1,
        "finished": 2,
        "pending": 2,
        "total": 4,
    }


@pytest.mark.asyncio
async def test_pass2_progress_separates_suspects_from_existing_good_controls(
    evaluation_store: EvaluationStore,
) -> None:
    """Historical Good controls must not inflate the suspect retry denominator."""
    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="Stable suspect progress",
            asr_providers=["elevenlabs"],
            pass_1_model="deepseek-chat",
            pass_2_model="deepseek-chat",
            budget_limit=10,
            idempotency_key="stable-suspect-progress-001",
        )
    )
    suspect_keys = {(f"S-{index}", "R1") for index in range(38)}
    for index, key in enumerate(sorted(suspect_keys)):
        await evaluation_store.checkpoint_result(
            "evaluation_pass2_runs",
            (batch["id"], key[0], key[1]),
            status="completed" if index < 11 else "failed",
            attempts=1,
            result={"origin": "suspect_candidate"} if index < 11 else None,
            error=None if index < 11 else "timeout",
        )
    for index in range(6):
        await evaluation_store.checkpoint_result(
            "evaluation_pass2_runs",
            (batch["id"], f"G-{index}", "R1"),
            status="completed",
            attempts=1,
            result={"origin": "additional_good_pool"},
        )

    updated = await evaluation_store.refresh_pass2_progress(
        batch["id"], suspect_case_keys=suspect_keys
    )

    assert updated["snapshot"]["execution_status"]["pass_2"] == {
        "completed": 11,
        "failed": 27,
        "finished": 38,
        "pending": 0,
        "total": 38,
    }
    assert updated["snapshot"]["pass_2_good_status"] == {
        "completed": 6,
        "failed": 0,
        "finished": 6,
        "pending": 0,
        "total": 6,
    }


@pytest.mark.asyncio
async def test_batch_creation_rejects_selected_model_without_frozen_price(
    evaluation_store: EvaluationStore,
) -> None:
    """A verified model cannot start paid work without an immutable rate."""
    before = len(await evaluation_store.list_batches())

    with pytest.raises(ValueError, match="qwen3.8-max.*Cost settings"):
        await evaluation_store.create_batch(
            EvaluationBatchCreate(
                name="Missing Qwen price",
                asr_providers=["soniox"],
                pass_1_model="qwen3.8-max",
                pass_2_model="qwen3.8-max",
                budget_limit=10,
                idempotency_key="missing-qwen-price",
            )
        )

    assert len(await evaluation_store.list_batches()) == before


@pytest.mark.asyncio
async def test_saved_deepseek_alias_price_allows_batch_creation(
    evaluation_store: EvaluationStore,
) -> None:
    """A UI compatibility alias must match the same canonical frozen price."""
    current = await evaluation_store.active_pricing_version()
    deepseek_rate = next(
        dict(rate)
        for rate in current["rates"]["llm"]
        if rate["provider"] == "DeepSeek" and rate["model"] == "deepseek-flash"
    )
    deepseek_rate["model"] = "deepseek-v4-flash"

    saved = await evaluation_store.save_pricing_version(
        cny_to_usd=float(current["cny_to_usd"]),
        source_note="DeepSeek alias pricing",
        llm_rates=[deepseek_rate],
    )
    assert any(
        rate["provider"] == "DeepSeek" and rate["model"] == "deepseek-flash"
        for rate in saved["rates"]["llm"]
    )
    assert saved["rates"]["llm_selections"] == [
        {"provider": "DeepSeek", "model": "deepseek-v4-flash"}
    ]

    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="DeepSeek alias priced",
            asr_providers=["soniox"],
            pass_1_model="deepseek-v4-flash",
            pass_2_model="deepseek-v4-flash",
            budget_limit=10,
            idempotency_key="deepseek-alias-price",
        )
    )
    assert batch["snapshot"]["pass_1_model"] == "deepseek-v4-flash"


@pytest.mark.asyncio
async def test_pricing_save_preserves_previously_configured_models(
    evaluation_store: EvaluationStore,
) -> None:
    """Editing two pricing rows must not remove other model rates from the catalog."""
    current = await evaluation_store.active_pricing_version()
    deepseek_rate = next(
        dict(rate)
        for rate in current["rates"]["llm"]
        if rate["provider"] == "DeepSeek" and rate["model"] == "deepseek-flash"
    )
    await evaluation_store.save_pricing_version(
        cny_to_usd=float(current["cny_to_usd"]),
        source_note="Add DeepSeek pricing",
        llm_rates=[deepseek_rate],
    )
    saved = await evaluation_store.save_pricing_version(
        cny_to_usd=float(current["cny_to_usd"]),
        source_note="Edit Gemini pricing",
        llm_rates=[
            {
                "provider": "Gemini",
                "model": "gemini-3.8-flash",
                "currency": "USD",
                "input_per_1m": 0.75,
                "cached_input_per_1m": 0.075,
                "output_per_1m": 3.75,
            }
        ],
    )

    configured = {(rate["provider"], rate["model"]) for rate in saved["rates"]["llm"]}
    assert ("DeepSeek", "deepseek-flash") in configured
    assert ("Gemini", "gemini-3.8-flash") in configured
    assert saved["rates"]["llm_selections"] == [{"provider": "Gemini", "model": "gemini-3.8-flash"}]


@pytest.mark.asyncio
async def test_existing_deepseek_alias_price_version_remains_compatible(
    evaluation_store: EvaluationStore,
) -> None:
    """Existing versions saved before canonicalization must remain usable."""
    missing = await evaluation_store._models_without_frozen_prices(
        {
            "rates": {
                "llm": [
                    {
                        "provider": "DeepSeek",
                        "model": "deepseek-v4-flash",
                        "currency": "USD",
                        "input_per_1m": 0.30,
                        "cached_input_per_1m": 0.006,
                        "output_per_1m": 1.20,
                    }
                ]
            }
        },
        ["deepseek-v4-flash"],
    )
    assert missing == []

    amount, currency = EvaluationRunner._frozen_llm_cost(
        {
            "snapshot": {
                "pricing_version": {
                    "rates": {
                        "llm": [
                            {
                                "provider": "DeepSeek",
                                "model": "deepseek-v4-flash",
                                "currency": "USD",
                                "input_per_1m": 0.30,
                                "cached_input_per_1m": 0.006,
                                "output_per_1m": 1.20,
                            }
                        ]
                    }
                }
            }
        },
        "deepseek",
        "deepseek-v4-flash",
        input_tokens=1_000_000,
        cached_input_tokens=0,
        reasoning_tokens=0,
        output_tokens=1_000_000,
    )
    assert amount == pytest.approx(1.5)
    assert currency == "USD"


@pytest.mark.asyncio
async def test_all_pass_one_failures_stop_before_asr(
    evaluation_store: EvaluationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fully failed first pass becomes retryable instead of an empty ASR run."""
    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="Pass one failed",
            asr_providers=["soniox"],
            pass_1_model="deepseek-chat",
            pass_2_model="deepseek-chat",
            budget_limit=10,
            idempotency_key="all-pass-one-failed",
        )
    )
    conversation = await evaluation_store.get_conversation(_VALID_CONVERSATION_ID)
    assert conversation is not None
    runner = EvaluationRunner(evaluation_store, cast(BotKeyCipher, object()))
    asr_called = False

    async def one_conversation() -> list[dict[str, object]]:
        return [conversation]

    async def connections_ok(_batch: dict[str, object]) -> None:
        return None

    async def failed_pass_one(
        _batch_id: str,
        _conversations: list[dict[str, object]],
    ) -> None:
        await evaluation_store.checkpoint_result(
            "evaluation_pass1_runs",
            (batch["id"], _VALID_CONVERSATION_ID),
            status="failed",
            attempts=3,
            error="EvaluationExecutionError",
        )

    async def should_not_run_asr(*_args: object, **_kwargs: object) -> None:
        nonlocal asr_called
        asr_called = True

    monkeypatch.setattr(evaluation_store, "source_conversations", one_conversation)
    monkeypatch.setattr(runner, "_validate_connections", connections_ok)
    monkeypatch.setattr(runner, "_run_pass_one", failed_pass_one)
    monkeypatch.setattr(runner, "_run_asr", should_not_run_asr)

    await runner._run(batch["id"])

    updated = await evaluation_store.get_batch(batch["id"])
    assert updated is not None
    assert updated["status"] == "partially_failed"
    assert updated["stage"] == "failed"
    assert updated["snapshot"]["execution_failure"]["category"] == "pass_1_failed"
    assert asr_called is False


@pytest.mark.asyncio
async def test_zero_candidate_first_pass_completes_without_asr(
    evaluation_store: EvaluationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A valid empty candidate set freezes a report and completes at 100 percent."""
    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="No candidates",
            asr_providers=["soniox"],
            pass_1_model="deepseek-chat",
            pass_2_model="deepseek-chat",
            budget_limit=10,
            idempotency_key="zero-candidate-pass-one",
        )
    )
    conversation = await evaluation_store.get_conversation(_VALID_CONVERSATION_ID)
    assert conversation is not None
    runner = EvaluationRunner(evaluation_store, cast(BotKeyCipher, object()))
    asr_called = False

    async def one_conversation() -> list[dict[str, object]]:
        return [conversation]

    async def connections_ok(_batch: dict[str, object]) -> None:
        return None

    async def empty_pass_one(
        _batch_id: str,
        _conversations: list[dict[str, object]],
    ) -> None:
        await evaluation_store.checkpoint_result(
            "evaluation_pass1_runs",
            (batch["id"], _VALID_CONVERSATION_ID),
            status="completed",
            attempts=1,
            result={
                "issues": [],
                "event_results": [
                    {
                        "event_id": event["event_id"],
                        "decision": "pass",
                        "reason": "No ASR concern",
                    }
                    for event in conversation["events"]
                    if event["speaker"] == "customer"
                ],
            },
        )

    async def should_not_run_asr(*_args: object, **_kwargs: object) -> None:
        nonlocal asr_called
        asr_called = True

    monkeypatch.setattr(evaluation_store, "source_conversations", one_conversation)
    monkeypatch.setattr(runner, "_validate_connections", connections_ok)
    monkeypatch.setattr(runner, "_run_pass_one", empty_pass_one)
    monkeypatch.setattr(runner, "_run_asr", should_not_run_asr)

    await runner._run(batch["id"])

    updated = await evaluation_store.get_batch(batch["id"])
    assert updated is not None
    assert updated["status"] == "completed"
    assert updated["stage"] == "completed"
    assert updated["progress"] == 100
    assert updated["report_type"] == "preliminary"
    assert asr_called is False


@pytest.mark.asyncio
async def test_all_provider_failure_stops_affected_conversation_before_pass_two(
    evaluation_store: EvaluationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No Pass 2 conclusion may be created without any evaluation-ASR evidence."""
    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="All providers failed",
            asr_providers=["soniox", "speechmatics", "elevenlabs"],
            pass_1_model="deepseek-chat",
            pass_2_model="deepseek-chat",
            budget_limit=10,
            idempotency_key="all-provider-failure-001",
        )
    )
    conversation = await evaluation_store.get_conversation(_VALID_CONVERSATION_ID)
    assert conversation is not None
    event = next(item for item in conversation["events"] if item["speaker"] == "customer")
    runner = EvaluationRunner(evaluation_store, cast(BotKeyCipher, object()))

    async def one_conversation() -> list[dict[str, object]]:
        return [conversation]

    async def connections_ok(_batch: dict[str, object]) -> None:
        return None

    async def pass_one(_batch_id: str, _conversations: list[dict[str, object]]) -> None:
        await evaluation_store.checkpoint_result(
            "evaluation_pass1_runs",
            (batch["id"], _VALID_CONVERSATION_ID),
            status="completed",
            attempts=1,
            result={
                "event_results": [{"event_id": event["event_id"], "decision": "candidate"}],
                "issues": [
                    {
                        "issue_id": "I1",
                        "title": "Needs evidence",
                        "priority": "P1",
                        "target_events": [
                            {
                                "event_id": event["event_id"],
                                "decision": "candidate",
                                "verification_question": "What was said?",
                            }
                        ],
                    }
                ],
            },
        )

    async def all_asr_failed(
        batch_id: str,
        run_batch: dict[str, object],
        _candidates: list[dict[str, object]],
    ) -> None:
        for provider in cast(list[str], run_batch["providers"]):
            await evaluation_store.checkpoint_result(
                "evaluation_asr_runs",
                (batch_id, provider, _VALID_CONVERSATION_ID),
                status="failed",
                attempts=3,
                error="timeout",
            )

    monkeypatch.setattr(evaluation_store, "source_conversations", one_conversation)
    monkeypatch.setattr(runner, "_validate_connections", connections_ok)
    monkeypatch.setattr(runner, "_run_pass_one", pass_one)
    monkeypatch.setattr(runner, "_run_asr", all_asr_failed)

    await runner._run(batch["id"])

    updated = await evaluation_store.get_batch(batch["id"])
    assert updated is not None
    assert updated["status"] == "partially_failed"
    assert updated["stage"] == "evaluation_asr"
    assert updated["snapshot"]["asr_unavailable_conversations"] == [_VALID_CONVERSATION_ID]
    assert await evaluation_store.checkpoint_rows("evaluation_pass2_runs", batch["id"]) == []
    assert await evaluation_store.list_reviews() == []
    assert (await evaluation_store.list_benchmarks())["total"] == 0


@pytest.mark.asyncio
async def test_partial_pass_two_materializes_completed_results(
    evaluation_store: EvaluationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Completed decisions remain usable when a sibling Case fails."""
    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="Mixed Pass 2 outcome",
            asr_providers=["elevenlabs"],
            pass_1_model="deepseek-chat",
            pass_2_model="deepseek-chat",
            budget_limit=10,
            idempotency_key="mixed-pass-two-outcome-001",
        )
    )
    conversation = await evaluation_store.get_conversation(_VALID_CONVERSATION_ID)
    assert conversation is not None
    events = [item for item in conversation["events"] if item["speaker"] == "customer"][:2]
    assert len(events) == 2
    runner = EvaluationRunner(evaluation_store, cast(BotKeyCipher, object()))

    async def one_conversation() -> list[dict[str, object]]:
        return [conversation]

    async def connections_ok(_batch: dict[str, object]) -> None:
        return None

    async def pass_one(_batch_id: str, _conversations: list[dict[str, object]]) -> None:
        await evaluation_store.checkpoint_result(
            "evaluation_pass1_runs",
            (batch["id"], _VALID_CONVERSATION_ID),
            status="completed",
            attempts=1,
            result={
                "event_results": [
                    {"event_id": item["event_id"], "decision": "candidate"} for item in events
                ],
                "issues": [
                    {
                        "issue_id": "I1",
                        "title": "Needs evidence",
                        "priority": "P1",
                        "target_events": [
                            {
                                "event_id": item["event_id"],
                                "decision": "candidate",
                                "verification_question": "What was said?",
                            }
                            for item in events
                        ],
                    }
                ],
            },
        )

    async def asr_results(
        batch_id: str,
        _batch: dict[str, object],
        candidates: list[dict[str, object]],
    ) -> None:
        for candidate in candidates:
            event_id = str(candidate["event_id"])
            event = next(item for item in events if item["event_id"] == event_id)
            await evaluation_store.checkpoint_result(
                "evaluation_case_asr_runs",
                (batch_id, "elevenlabs", _VALID_CONVERSATION_ID, event_id),
                status="completed",
                attempts=1,
                result={
                    "text": str(event["text"]),
                    "segments": [
                        {
                            "segment_id": f"segment-{event_id}",
                            "start": 0.0,
                            "end": 1.0,
                            "text": str(event["text"]),
                        }
                    ],
                },
            )

    async def mixed_pass_two(
        batch_id: str,
        _batch: dict[str, object],
        _conversations: list[dict[str, object]],
        _candidates: list[dict[str, object]],
        *,
        plan_key: str,
    ) -> None:
        assert plan_key == "suspects"
        await evaluation_store.checkpoint_result(
            "evaluation_pass2_runs",
            (batch_id, _VALID_CONVERSATION_ID, str(events[0]["event_id"])),
            status="completed",
            attempts=1,
            result={
                "event_id": str(events[0]["event_id"]),
                "decision": "Needs manual audio review",
                "reference_text": None,
                "scenario_tag": "numbers",
                "manual_review_question": "Confirm the spoken digits.",
            },
        )
        await evaluation_store.checkpoint_result(
            "evaluation_pass2_runs",
            (batch_id, _VALID_CONVERSATION_ID, str(events[1]["event_id"])),
            status="failed",
            attempts=3,
            error="provider timeout",
        )

    monkeypatch.setattr(evaluation_store, "source_conversations", one_conversation)
    monkeypatch.setattr(runner, "_validate_connections", connections_ok)
    monkeypatch.setattr(runner, "_run_pass_one", pass_one)
    monkeypatch.setattr(runner, "_run_asr", asr_results)
    monkeypatch.setattr(runner, "_run_pass_two", mixed_pass_two)

    await runner._run(batch["id"])

    updated = await evaluation_store.get_batch(batch["id"])
    assert updated is not None
    assert updated["status"] == "partially_failed"
    assert updated["review_total"] == 1
    assert len(await evaluation_store.list_reviews()) == 1
    assert await evaluation_store.latest_report(batch["id"]) is None


@pytest.mark.asyncio
async def test_single_provider_success_continues_and_preserves_failed_evidence(
    evaluation_store: EvaluationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One successful ASR is sufficient while failed provider rows remain retryable."""
    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="Partial provider evidence",
            asr_providers=["soniox", "speechmatics", "elevenlabs"],
            pass_1_model="deepseek-chat",
            pass_2_model="deepseek-chat",
            budget_limit=10,
            idempotency_key="single-provider-success-001",
        )
    )
    conversation = await evaluation_store.get_conversation(_VALID_CONVERSATION_ID)
    assert conversation is not None
    event = next(item for item in conversation["events"] if item["speaker"] == "customer")
    runner = EvaluationRunner(evaluation_store, cast(BotKeyCipher, object()))

    async def one_conversation() -> list[dict[str, object]]:
        return [conversation]

    async def connections_ok(_batch: dict[str, object]) -> None:
        return None

    async def pass_one(_batch_id: str, _conversations: list[dict[str, object]]) -> None:
        await evaluation_store.checkpoint_result(
            "evaluation_pass1_runs",
            (batch["id"], _VALID_CONVERSATION_ID),
            status="completed",
            attempts=1,
            result={
                "event_results": [{"event_id": event["event_id"], "decision": "candidate"}],
                "issues": [
                    {
                        "issue_id": "I1",
                        "title": "Needs evidence",
                        "priority": "P1",
                        "target_events": [
                            {
                                "event_id": event["event_id"],
                                "decision": "candidate",
                                "verification_question": "What was said?",
                            }
                        ],
                    }
                ],
            },
        )

    async def partial_asr(
        batch_id: str,
        _run_batch: dict[str, object],
        _candidates: list[dict[str, object]],
    ) -> None:
        await evaluation_store.checkpoint_result(
            "evaluation_case_asr_runs",
            (batch_id, "soniox", _VALID_CONVERSATION_ID, str(event["event_id"])),
            status="completed",
            attempts=1,
            result={
                "text": event["text"],
                "segments": [
                    {
                        "segment_id": f"{_VALID_CONVERSATION_ID}:soniox:0",
                        "start": event["time_s"],
                        "end": event["time_s"] + 1,
                        "text": event["text"],
                    }
                ],
            },
        )
        for provider in ("speechmatics", "elevenlabs"):
            await evaluation_store.checkpoint_result(
                "evaluation_case_asr_runs",
                (batch_id, provider, _VALID_CONVERSATION_ID, str(event["event_id"])),
                status="failed",
                attempts=3,
                error="timeout",
            )

    async def pass_two(
        batch_id: str,
        _run_batch: dict[str, object],
        _conversations: list[dict[str, object]],
        candidates: list[dict[str, object]],
        *,
        plan_key: str,
    ) -> None:
        assert plan_key == "suspects"
        assert len(candidates) == 1
        await evaluation_store.checkpoint_result(
            "evaluation_pass2_runs",
            (batch_id, _VALID_CONVERSATION_ID, event["event_id"]),
            status="completed",
            attempts=1,
            result={
                "conversation_id": _VALID_CONVERSATION_ID,
                "event_id": event["event_id"],
                "decision": "Good Case",
                "reference_text": event["text"],
                "scenario_tag": "branches",
                "recommended_listening_segment_ids": [f"{_VALID_CONVERSATION_ID}:soniox:0"],
                "positioning_quality": "exact",
            },
        )

    monkeypatch.setattr(evaluation_store, "source_conversations", one_conversation)
    monkeypatch.setattr(runner, "_validate_connections", connections_ok)
    monkeypatch.setattr(runner, "_run_pass_one", pass_one)
    monkeypatch.setattr(runner, "_run_asr", partial_asr)
    monkeypatch.setattr(runner, "_run_pass_two", pass_two)

    await runner._run(batch["id"])

    updated = await evaluation_store.get_batch(batch["id"])
    assert updated is not None
    assert updated["status"] == "completed"
    assert updated["snapshot"]["asr_unavailable_conversations"] == []
    asr_rows = await evaluation_store.checkpoint_rows("evaluation_case_asr_runs", batch["id"])
    assert sum(row["status"] == "completed" for row in asr_rows) == 1
    assert sum(row["status"] == "failed" for row in asr_rows) == 2
    assert (await evaluation_store.list_benchmarks())["total"] == 1


@pytest.mark.asyncio
async def test_asr_job_is_user_event_scoped_and_reused_after_retry(
    evaluation_store: EvaluationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every Case gets one provider job and a resumed worker reuses both results."""
    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="Reuse ASR job",
            asr_providers=["elevenlabs"],
            pass_1_model="deepseek-chat",
            pass_2_model="deepseek-chat",
            budget_limit=10,
            idempotency_key="reuse-asr-job-001",
        )
    )
    calls = 0

    async def transcribe(
        _batch_id: str,
        _provider: str,
        _path: Path,
        conversation_id: str,
        _attempt: int,
        *,
        event_id: str | None = None,
    ) -> tuple[dict[str, object], str]:
        nonlocal calls
        calls += 1
        segments = [
            {
                "segment_id": f"{conversation_id}:elevenlabs:0",
                "start": 0.0,
                "end": 0.4,
                "speaker": "S1" if event_id is None else None,
                "text": "agent" if event_id is None else "evidence",
            }
        ]
        if event_id is None:
            segments.append(
                {
                    "segment_id": f"{conversation_id}:elevenlabs:1",
                    "start": 0.5,
                    "end": 1.0,
                    "speaker": "S2",
                    "text": "customer",
                }
            )
        return {
            "text": "agent customer" if event_id is None else "evidence",
            "segments": segments,
        }, ("remote-job-1")

    runner = EvaluationRunner(evaluation_store, cast(BotKeyCipher, object()))
    monkeypatch.setattr(runner, "_transcribe", transcribe)

    async def map_events(*_args: object) -> dict[tuple[str, str], dict[str, object]]:
        return {
            (_VALID_CONVERSATION_ID, event_id): {
                "conversation_id": _VALID_CONVERSATION_ID,
                "event_id": event_id,
                "providers": [],
            }
            for event_id in customer_event_ids
        }

    monkeypatch.setattr(runner, "_run_event_alignment", map_events)
    source = evaluation_store.conversation_user_audio_path(_VALID_CONVERSATION_ID)
    assert source is not None

    async def prepare_clip(
        _batch_id: str,
        _conversation_id: str,
        _event_id: str,
        _full_call_results: list[dict[str, object]],
        _event_mapping: dict[str, object],
    ) -> tuple[Path, dict[str, object]]:
        return source, {"start_s": 0.0, "end_s": 1.0}

    monkeypatch.setattr(evaluation_store, "prepare_case_asr_clip", prepare_clip)
    conversation = await evaluation_store.get_conversation(_VALID_CONVERSATION_ID)
    assert conversation is not None
    customer_event_ids = [
        str(item["event_id"]) for item in conversation["events"] if item["speaker"] == "customer"
    ][:2]
    candidates = [
        {"conversation_id": _VALID_CONVERSATION_ID, "event_id": event_id}
        for event_id in customer_event_ids
    ]

    await runner._run_asr(batch["id"], batch, candidates)
    await runner._run_asr(batch["id"], batch, candidates)

    assert calls == 3
    context_rows = await evaluation_store.checkpoint_rows("evaluation_asr_runs", batch["id"])
    assert len(context_rows) == 1
    assert context_rows[0]["result"]["scope"] == "full_call_context"
    rows = await evaluation_store.checkpoint_rows("evaluation_case_asr_runs", batch["id"])
    assert len(rows) == 2
    assert all(row["remote_job_id"] == "remote-job-1" for row in rows)


@pytest.mark.asyncio
async def test_run_asr_replaces_legacy_non_diarized_context_checkpoint(
    evaluation_store: EvaluationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A resumed batch must replace a completed pre-diarization full-call result."""
    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="Refresh legacy ASR context",
            asr_providers=["elevenlabs"],
            pass_1_model="deepseek-chat",
            pass_2_model="deepseek-chat",
            budget_limit=10,
            idempotency_key="refresh-legacy-context-001",
        )
    )
    conversation = await evaluation_store.get_conversation(_VALID_CONVERSATION_ID)
    assert conversation is not None
    event_id = str(
        next(item["event_id"] for item in conversation["events"] if item["speaker"] == "customer")
    )
    await evaluation_store.checkpoint_result(
        "evaluation_asr_runs",
        (str(batch["id"]), "elevenlabs", _VALID_CONVERSATION_ID),
        status="completed",
        attempts=1,
        result={
            "text": "legacy context",
            "segments": [{"start": 0.0, "end": 1.0, "speaker": None, "text": "legacy context"}],
            "scope": "full_call_context",
        },
        remote_job_id="legacy-job",
    )
    calls: list[tuple[int, str | None]] = []

    async def transcribe(
        _batch_id: str,
        _provider: str,
        _path: Path,
        _conversation_id: str,
        attempt: int,
        *,
        event_id: str | None = None,
    ) -> tuple[dict[str, object], str]:
        calls.append((attempt, event_id))
        if event_id is not None:
            return {
                "text": "event",
                "segments": [{"start": 0.0, "end": 1.0, "text": "event"}],
            }, "event-job"
        return {
            "text": "agent customer",
            "segments": [
                {"start": 0.0, "end": 0.4, "speaker": "S1", "text": "agent"},
                {"start": 0.5, "end": 1.0, "speaker": "S2", "text": "customer"},
            ],
        }, "replacement-job"

    source = evaluation_store.conversation_user_audio_path(_VALID_CONVERSATION_ID)
    assert source is not None

    async def prepare_clip(
        _batch_id: str,
        _conversation_id: str,
        _event_id: str,
        full_call_results: list[dict[str, object]],
        _event_mapping: dict[str, object],
    ) -> tuple[Path, dict[str, object]]:
        assert full_call_results[0]["diarization_contract"] == "speaker_timestamps_v1"
        return source, {"start_s": 0.0, "end_s": 1.0}

    runner = EvaluationRunner(evaluation_store, cast(BotKeyCipher, object()))
    monkeypatch.setattr(runner, "_transcribe", transcribe)
    monkeypatch.setattr(evaluation_store, "prepare_case_asr_clip", prepare_clip)

    async def map_event(*_args: object) -> dict[tuple[str, str], dict[str, object]]:
        return {
            (_VALID_CONVERSATION_ID, event_id): {
                "conversation_id": _VALID_CONVERSATION_ID,
                "event_id": event_id,
                "providers": [],
            }
        }

    monkeypatch.setattr(runner, "_run_event_alignment", map_event)

    await runner._run_asr(
        str(batch["id"]),
        batch,
        [{"conversation_id": _VALID_CONVERSATION_ID, "event_id": event_id}],
    )

    assert calls == [(2, None), (1, event_id)]
    context_rows = await evaluation_store.checkpoint_rows("evaluation_asr_runs", str(batch["id"]))
    assert context_rows[0]["remote_job_id"] == "replacement-job"
    assert context_rows[0]["attempts"] == 2
    assert context_rows[0]["result"]["diarization_contract"] == "speaker_timestamps_v1"


@pytest.mark.asyncio
async def test_completed_unusable_diarization_attempts_remain_in_cost_ledger(
    evaluation_store: EvaluationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Completed paid responses stay charged even when their diarization is unusable."""
    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="Charge unusable diarization",
            asr_providers=["elevenlabs"],
            pass_1_model="deepseek-chat",
            pass_2_model="deepseek-chat",
            budget_limit=10,
            idempotency_key="charge-unusable-diarization-001",
        )
    )
    conversation = await evaluation_store.get_conversation(_VALID_CONVERSATION_ID)
    assert conversation is not None
    event_id = str(
        next(item["event_id"] for item in conversation["events"] if item["speaker"] == "customer")
    )
    calls = 0

    async def transcribe(*_args: object, **_kwargs: object) -> tuple[dict[str, object], str]:
        nonlocal calls
        calls += 1
        return {
            "text": "one speaker only",
            "segments": [{"start": 0.0, "end": 1.0, "speaker": "S1", "text": "one speaker only"}],
        }, f"completed-job-{calls}"

    runner = EvaluationRunner(evaluation_store, cast(BotKeyCipher, object()))
    monkeypatch.setattr(runner, "_transcribe", transcribe)

    await runner._run_asr(
        str(batch["id"]),
        batch,
        [{"conversation_id": _VALID_CONVERSATION_ID, "event_id": event_id}],
    )

    assert calls == 3
    context_rows = await evaluation_store.checkpoint_rows("evaluation_asr_runs", str(batch["id"]))
    assert context_rows[0]["status"] == "failed"
    assert context_rows[0]["attempts"] == 3
    ledger = await evaluation_store.cost_summary(str(batch["id"]))
    assert ledger["asr"][0]["calls"] == 3
    assert ledger["asr"][0]["estimated_cost"] > 0


@pytest.mark.asyncio
async def test_pass2_group_checkpoint_freezes_membership(
    evaluation_store: EvaluationStore,
) -> None:
    """Pass 2 request retries must retain group membership and accounting."""
    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="Grouped run",
            asr_providers=["elevenlabs"],
            pass_1_model="deepseek-flash",
            pass_2_model="deepseek-flash",
            budget_limit=10,
            idempotency_key="grouped-run-001",
        )
    )
    await evaluation_store.checkpoint_pass2_group(
        batch_id=batch["id"],
        group_id="G0001-example",
        idempotency_key="stable-membership",
        conversation_ids=["C1", "C2"],
        case_keys=[("C1", "R1"), ("C2", "R3")],
        estimated_input_tokens=1234,
        reserved_output_tokens=5678,
        status="failed",
        attempts=3,
        error="timeout",
    )

    rows = await evaluation_store.pass2_group_rows(batch["id"])

    assert rows[0]["conversation_ids"] == ["C1", "C2"]
    assert rows[0]["case_keys"] == [["C1", "R1"], ["C2", "R3"]]
    assert rows[0]["status"] == "failed"


@pytest.mark.asyncio
async def test_pass2_retry_reuses_failed_frozen_group(
    evaluation_store: EvaluationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resuming Pass 2 must retry the original group instead of repacking its Cases."""
    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="Frozen group retry",
            asr_providers=["elevenlabs"],
            pass_1_model="deepseek-flash",
            pass_2_model="deepseek-flash",
            budget_limit=10,
            idempotency_key="frozen-group-retry-001",
        )
    )
    conversation = await evaluation_store.get_conversation(_VALID_CONVERSATION_ID)
    assert conversation is not None
    event = next(item for item in conversation["events"] if item["speaker"] == "customer")
    event_id = str(event["event_id"])
    await evaluation_store.checkpoint_result(
        "evaluation_case_asr_runs",
        (batch["id"], "elevenlabs", _VALID_CONVERSATION_ID, event_id),
        status="completed",
        attempts=1,
        result={
            "text": str(event["text"]),
            "segments": [
                {
                    "segment_id": "segment-1",
                    "start": 0.0,
                    "end": 1.0,
                    "text": str(event["text"]),
                }
            ],
        },
    )
    await evaluation_store.checkpoint_result(
        "evaluation_asr_runs",
        (batch["id"], "elevenlabs", _VALID_CONVERSATION_ID),
        status="completed",
        attempts=1,
        result={
            "scope": "full_call_context",
            "text": "complete call context",
            "segments": [
                {"segment_id": "ctx-0", "start": 0.0, "end": 1.0, "speaker": "A", "text": "Prompt"},
                {
                    "segment_id": "ctx-1",
                    "start": 1.0,
                    "end": 2.0,
                    "speaker": "B",
                    "text": str(event["text"]),
                },
                {
                    "segment_id": "ctx-2",
                    "start": 2.0,
                    "end": 3.0,
                    "speaker": "A",
                    "text": "Follow-up",
                },
            ],
        },
    )
    await evaluation_store.checkpoint_result(
        "evaluation_event_alignment_runs",
        (batch["id"], _VALID_CONVERSATION_ID),
        status="completed",
        attempts=1,
        result={
            "conversation_id": _VALID_CONVERSATION_ID,
            "events": [
                {
                    "event_id": event_id,
                    "providers": [
                        {
                            "provider": "elevenlabs",
                            "status": "mapped",
                            "turn_id": f"{_VALID_CONVERSATION_ID}:elevenlabs:turn:1",
                        }
                    ],
                }
            ],
        },
    )
    runner = EvaluationRunner(evaluation_store, cast(BotKeyCipher, object()))
    attempts: list[int] = []
    observed_contexts: list[object] = []

    async def provider(_model_id: str) -> str:
        return "deepseek"

    async def fail_request(*args: object, **kwargs: object) -> dict[str, object]:
        attempts.append(cast(int, kwargs["attempt"]))
        observed_contexts.append(cast(dict[str, object], args[2])["full_audio_context_asr"])
        raise EvaluationExecutionError("temporary provider failure")

    async def no_wait(_seconds: float) -> None:
        return None

    monkeypatch.setattr(runner, "_model_provider", provider)
    monkeypatch.setattr(runner, "_llm_json", fail_request)
    monkeypatch.setattr(asyncio, "sleep", no_wait)
    candidates = [
        {
            "conversation_id": _VALID_CONVERSATION_ID,
            "event_id": event_id,
            "origin": "suspect_candidate",
        }
    ]

    await runner._run_pass_two(batch["id"], batch, [conversation], candidates, plan_key="suspects")
    first = await evaluation_store.pass2_group_rows(batch["id"])
    await runner._run_pass_two(batch["id"], batch, [conversation], candidates, plan_key="suspects")
    second = await evaluation_store.pass2_group_rows(batch["id"])

    assert len(first) == len(second) == 1
    assert second[0]["group_id"] == first[0]["group_id"]
    assert second[0]["case_keys"] == first[0]["case_keys"]
    assert second[0]["status"] == "failed"
    assert attempts == [1, 2, 3, 4, 5, 6]
    first_context = cast(list[dict[str, object]], observed_contexts[0])[0]
    context_events = cast(list[dict[str, object]], first_context["events"])
    providers = cast(list[dict[str, object]], context_events[0]["providers"])
    assert providers[0]["target_turn_id"] == (f"{_VALID_CONVERSATION_ID}:elevenlabs:turn:1")
    assert len(cast(list[object], providers[0]["turns"])) == 3


@pytest.mark.asyncio
async def test_pass2_preflight_splits_one_large_conversation_by_case(
    evaluation_store: EvaluationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One large conversation must become stable Case subsets before any paid request."""
    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="Preflight Case split",
            asr_providers=["elevenlabs"],
            pass_1_model="deepseek-flash",
            pass_2_model="deepseek-flash",
            budget_limit=10,
            idempotency_key="preflight-case-split-001",
        )
    )
    source = await evaluation_store.get_conversation(_VALID_CONVERSATION_ID)
    assert source is not None
    customer_events = [event for event in source["events"] if event["speaker"] == "customer"][:2]
    assert len(customer_events) == 2
    conversation = {
        **source,
        "events": [
            {**event, "text": str(event.get("text") or "") + "h" * 500}
            for event in source["events"]
        ],
    }
    candidates = [
        {
            "conversation_id": _VALID_CONVERSATION_ID,
            "event_id": str(event["event_id"]),
            "origin": "suspect_candidate",
        }
        for event in customer_events
    ]
    for index, event in enumerate(customer_events):
        await evaluation_store.checkpoint_result(
            "evaluation_case_asr_runs",
            (batch["id"], "elevenlabs", _VALID_CONVERSATION_ID, str(event["event_id"])),
            status="completed",
            attempts=1,
            result={
                "text": "z" * 4_000,
                "segments": [
                    {
                        "segment_id": f"case-segment-{index}",
                        "start": 0.0,
                        "end": 1.0,
                        "text": "z" * 4_000,
                    }
                ],
            },
        )
    snapshot = dict(batch["snapshot"])
    snapshot.update(
        {
            "evaluation_context": {},
            "reference_dictionaries": [],
            "scenario_tags": [],
            "screening_strategy": "focused",
            "pass_2_prompt": {
                "content": (
                    "{{request_group_id}}{{candidate_case}}{{conversation_history}}"
                    "{{production_transcript}}{{full_audio_context_asr}}{{asr_results}}"
                    "{{evaluation_context}}{{reference_dictionaries}}"
                    "{{screening_strategy}}{{scenario_tags}}"
                )
            },
        }
    )
    batch = {**batch, "snapshot": snapshot}
    observed_case_counts: list[int] = []

    async def provider(_model_id: str) -> str:
        return "deepseek"

    async def fail_request(*args: object, **_kwargs: object) -> dict[str, object]:
        payload = cast(dict[str, object], args[2])
        observed_case_counts.append(len(cast(list[object], payload["candidate_case"])))
        raise EvaluationExecutionError("test-only provider failure")

    async def no_wait(_seconds: float) -> None:
        return None

    monkeypatch.setattr(
        runner := EvaluationRunner(evaluation_store, cast(BotKeyCipher, object())),
        "_model_provider",
        provider,
    )
    monkeypatch.setattr(runner, "_llm_json", fail_request)
    monkeypatch.setattr(asyncio, "sleep", no_wait)
    monkeypatch.setattr(
        "src.evaluation.executor.evaluation_token_policy",
        lambda _provider, _model=None: ModelTokenPolicy(
            40_000,
            20_000,
            5_000,
            reasoning_reserve=4_000,
            max_input_tokens=22_000,
        ),
    )

    await runner._run_pass_two(batch["id"], batch, [conversation], candidates, plan_key="suspects")

    groups = await evaluation_store.pass2_group_rows(batch["id"])
    assert len(groups) == 2
    assert all(len(row["case_keys"]) == 1 for row in groups)
    assert observed_case_counts == [1, 1, 1, 1, 1, 1]


@pytest.mark.asyncio
async def test_pass2_safe_group_failure_does_not_trigger_paid_recursive_split(
    evaluation_store: EvaluationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A preflight-safe schema failure keeps stable membership without paid splitting."""
    batch = await evaluation_store.create_batch(
        EvaluationBatchCreate(
            name="Adaptive grouped retry",
            asr_providers=["elevenlabs"],
            pass_1_model="deepseek-flash",
            pass_2_model="deepseek-flash",
            budget_limit=10,
            idempotency_key="adaptive-grouped-retry-001",
        )
    )
    source = await evaluation_store.get_conversation(_VALID_CONVERSATION_ID)
    assert source is not None
    event = next(item for item in source["events"] if item["speaker"] == "customer")
    event_id = str(event["event_id"])
    conversations = []
    candidates = []
    for conversation_id in ("C-SPLIT-1", "C-SPLIT-2"):
        conversation = json.loads(json.dumps(source))
        conversation["conversation_id"] = conversation_id
        conversations.append(conversation)
        candidates.append(
            {
                "conversation_id": conversation_id,
                "event_id": event_id,
                "origin": "suspect_candidate",
            }
        )
        await evaluation_store.checkpoint_result(
            "evaluation_case_asr_runs",
            (batch["id"], "elevenlabs", conversation_id, event_id),
            status="completed",
            attempts=1,
            result={
                "text": str(event["text"]),
                "segments": [
                    {
                        "segment_id": "segment-1",
                        "start": 0.0,
                        "end": 1.0,
                        "text": str(event["text"]),
                    }
                ],
            },
        )
        await evaluation_store.checkpoint_result(
            "evaluation_asr_runs",
            (batch["id"], "elevenlabs", conversation_id),
            status="completed",
            attempts=1,
            result={"scope": "full_call_context", "text": "context", "segments": []},
        )
    runner = EvaluationRunner(evaluation_store, cast(BotKeyCipher, object()))
    calls: list[tuple[str, ...]] = []

    async def provider(_model_id: str) -> str:
        return "deepseek"

    async def grouped_request(*args: object, **kwargs: object) -> dict[str, object]:
        payload = cast(dict[str, object], args[2])
        grouped = cast(list[dict[str, object]], payload["conversation_history"])
        membership = tuple(str(item["conversation_id"]) for item in grouped)
        calls.append(membership)
        raise ValueError("Pass 2 references unknown ASR segments")

    async def no_wait(_seconds: float) -> None:
        return None

    monkeypatch.setattr(runner, "_model_provider", provider)
    monkeypatch.setattr(runner, "_llm_json", grouped_request)
    monkeypatch.setattr(asyncio, "sleep", no_wait)

    await runner._run_pass_two(batch["id"], batch, conversations, candidates, plan_key="suspects")
    first_calls = list(calls)
    await runner._run_pass_two(batch["id"], batch, conversations, candidates, plan_key="suspects")

    assert len(first_calls) == 3
    assert len(calls) == 6
    assert all(len(membership) == 2 for membership in calls)
    groups = await evaluation_store.pass2_group_rows(batch["id"])
    assert len(groups) == 1
    assert groups[0]["status"] == "failed"
    results = await evaluation_store.checkpoint_rows("evaluation_pass2_runs", batch["id"])
    assert len(results) == 2
    assert all(row["status"] == "failed" for row in results)


@pytest.mark.asyncio
async def test_initialize_purges_legacy_simulated_results(tmp_path: Path) -> None:
    """The one-time migration should delete result rows while retaining source files."""
    database_path = tmp_path / "evaluation.db"
    fixture_root = _source_root()
    store = EvaluationStore(database_path, fixture_root)
    await store.initialize()

    async with aiosqlite.connect(database_path) as connection:
        await connection.execute(
            "DELETE FROM evaluation_meta WHERE key = ?",
            ("real_source_migration_v1",),
        )
        await connection.execute(
            """
            INSERT INTO evaluation_batches (
                id,name,context_name,input_count,status,stage,progress,
                suspected_numerator,denominator,excluded_count,cost,budget,
                review_total,review_completed,report_type,simulation_started_at,
                providers_json,snapshot_json,created_at,updated_at,version
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "EV-FAKE",
                "Synthetic",
                "Synthetic context",
                56,
                "completed",
                "completed",
                100,
                23,
                381,
                0,
                3.18,
                10.0,
                4,
                4,
                "synthetic",
                "2026-09-16T00:00:00Z",
                json.dumps(["fake-provider"]),
                json.dumps({"mock": True}),
                "2026-09-16T00:00:00Z",
                "2026-09-16T00:00:00Z",
                1,
            ),
        )
        await connection.execute(
            """
            INSERT INTO evaluation_reviews (
                id,fixture_key,batch_id,payload_json,status,decision,label,
                language,scenario_tag,reviewed_at,version
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "REV-FAKE",
                "fake-fixture",
                "EV-FAKE",
                json.dumps(
                    {
                        "conversation_id": "1030000000091506",
                        "event_id": "R18",
                        "production_transcript": "Fake English transcript",
                        "start_s": 1.0,
                        "end_s": 2.0,
                    }
                ),
                "pending",
                None,
                None,
                "en",
                "Synthetic",
                None,
                1,
            ),
        )
        await connection.execute(
            """
            INSERT INTO evaluation_benchmarks (
                id,batch_id,conversation_id,event_id,case_type,source,language,
                scenario_tag,label,audio_start_s,audio_end_s,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "BM-FAKE",
                "EV-FAKE",
                "1030000000091506",
                "R18",
                "bad",
                "ai",
                "en",
                "Synthetic",
                "Fake English transcript",
                1.0,
                2.0,
                "2026-09-16T00:00:00Z",
            ),
        )
        await connection.commit()
    migrated_store = EvaluationStore(database_path, fixture_root)
    await migrated_store.initialize()

    assert await migrated_store.list_batches() == []
    assert await migrated_store.list_reviews() == []
    assert (await migrated_store.list_benchmarks())["total"] == 0
    assert await migrated_store.get_conversation("1030000000091506") is not None
    assert len(list(fixture_root.joinpath("record").glob("*.mp3"))) == 56
    assert len(list(fixture_root.joinpath("user_record").glob("*.wav"))) == 56


@pytest.mark.asyncio
async def test_full_upload_stages_invalid_candidate_then_repairs_atomically(
    tmp_path: Path,
) -> None:
    """A blocked package must not replace active data; a scoped repair may activate it."""
    store = EvaluationStore(tmp_path / "evaluation.db", _source_root())
    await store.initialize()
    archive = tmp_path / "candidate.zip"
    _write_package_zip(archive, include_record=False)

    blocked = await store.import_dataset_upload(archive, archive.name)

    assert blocked["active"] is False
    assert blocked["conversation_count"] == 1
    assert {issue["issue_type"] for issue in blocked["issues"]} == {"missing_file"}
    assert store.fixture_status()["conversation_count"] == 56
    pending = store.pending_dataset_status()
    assert pending is not None and pending["dataset_id"] == blocked["dataset_id"]

    repair = _source_root() / "record" / f"{_VALID_CONVERSATION_ID}.mp3"
    activated = await store.import_dataset_upload(
        repair,
        repair.name,
        repair=True,
        candidate_id=str(blocked["dataset_id"]),
    )

    assert activated["active"] is True
    assert activated["valid"] is True
    assert store.fixture_status()["conversation_count"] == 1
    assert store.pending_dataset_status() is None

    restarted = EvaluationStore(tmp_path / "evaluation.db", _source_root())
    await restarted.initialize()
    assert restarted.fixture_status()["conversation_count"] == 1
    assert await restarted.get_conversation(_VALID_CONVERSATION_ID) is not None


@pytest.mark.asyncio
async def test_discard_pending_dataset_removes_only_unstarted_candidate(
    tmp_path: Path,
) -> None:
    """Opening a clean draft must not replace or remove the active dataset."""
    database_path = tmp_path / "evaluation.db"
    store = EvaluationStore(database_path, _source_root())
    await store.initialize()
    archive = tmp_path / "candidate.zip"
    _write_package_zip(archive, include_record=False)
    blocked = await store.import_dataset_upload(archive, archive.name)
    candidate_root = store.upload_root / str(blocked["dataset_id"])

    assert candidate_root.exists()
    fixture = await store.discard_pending_dataset()

    assert fixture["conversation_count"] == 56
    assert fixture["valid"] is True
    assert store.pending_dataset_status() is None
    assert not candidate_root.exists()

    restarted = EvaluationStore(database_path, _source_root())
    await restarted.initialize()
    assert restarted.pending_dataset_status() is None
    assert restarted.fixture_status()["conversation_count"] == 56


def test_archive_staging_rejects_traversal_symlinks_and_duplicates(tmp_path: Path) -> None:
    """Archive-owned paths must never escape or alias the managed staging root."""
    target = tmp_path / "target"
    target.mkdir()
    traversal = tmp_path / "traversal.zip"
    with zipfile.ZipFile(traversal, "w") as archive:
        archive.writestr("../escape.xlsx", b"bad")
    with pytest.raises(PackageUploadError, match="unsafe path"):
        extract_package_archive(traversal, target)
    assert not tmp_path.joinpath("escape.xlsx").exists()

    symlink = tmp_path / "symlink.zip"
    with zipfile.ZipFile(symlink, "w") as archive:
        info = zipfile.ZipInfo("conversation_history/123.xlsx")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(info, "../../escape")
    with pytest.raises(PackageUploadError, match="symlinks"):
        extract_package_archive(symlink, target)

    duplicate = tmp_path / "duplicate.zip"
    with pytest.warns(UserWarning, match="Duplicate name"):
        with zipfile.ZipFile(duplicate, "w") as archive:
            archive.writestr("record/123.mp3", b"one")
            archive.writestr("record/123.mp3", b"two")
    with pytest.raises(PackageUploadError, match="duplicate path"):
        extract_package_archive(duplicate, target)


def test_audit_reports_malformed_undecodable_and_timeline_failures(tmp_path: Path) -> None:
    """Content validation should classify repairable workbook and audio failures."""
    source = _source_root()

    malformed = tmp_path / "malformed"
    for folder in ("conversation_history", "record", "user_record"):
        malformed.joinpath(folder).mkdir(parents=True)
    malformed.joinpath("conversation_history", f"{_VALID_CONVERSATION_ID}.xlsx").write_bytes(
        b"not-an-xlsx"
    )
    shutil.copyfile(
        source / "record" / f"{_VALID_CONVERSATION_ID}.mp3",
        malformed / "record" / f"{_VALID_CONVERSATION_ID}.mp3",
    )
    shutil.copyfile(
        source / "user_record" / f"{_VALID_CONVERSATION_ID}.wav",
        malformed / "user_record" / f"{_VALID_CONVERSATION_ID}.wav",
    )
    malformed_audit = audit_dataset(malformed, expected_conversations=None)
    assert "invalid_workbook" in {
        issue["issue_type"] for issue in malformed_audit.to_dict()["issues"]
    }

    audio_failure = tmp_path / "audio-failure"
    shutil.copytree(source, audio_failure)
    audio_failure.joinpath("record", "1030000000086004.mp3").write_bytes(b"not-an-mp3")
    with wave.open(
        str(audio_failure / "user_record" / f"{_VALID_CONVERSATION_ID}.wav"),
        "wb",
    ) as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\x00\x00" * 8000)
    audio_audit = audit_dataset(audio_failure)
    issue_types = {issue["issue_type"] for issue in audio_audit.to_dict()["issues"]}
    assert "invalid_audio" in issue_types
    assert "audio_timeline_mismatch" in issue_types


@pytest.mark.asyncio
async def test_upload_and_repair_download_routes(tmp_path: Path) -> None:
    """The browser-facing API should accept multipart upload and return repair artifacts."""
    store = EvaluationStore(tmp_path / "evaluation.db", _source_root())
    await store.initialize()
    app = FastAPI()
    app.include_router(create_evaluation_router(store))
    archive = tmp_path / "candidate.zip"
    _write_package_zip(archive, include_record=False)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        uploaded = await client.post(
            "/api/evaluation/dataset/upload",
            files={"file": (archive.name, archive.read_bytes(), "application/zip")},
        )
        assert uploaded.status_code == 200
        payload = uploaded.json()
        assert payload["active"] is False

        issues = await client.get(
            "/api/evaluation/dataset/issues.csv",
            params={"candidate_id": payload["dataset_id"]},
        )
        assert issues.status_code == 200
        assert "missing_file" in issues.text
        assert "expected_path" in issues.text
        assert "severity" in issues.text

        template = await client.get("/api/evaluation/dataset/template")
        assert template.status_code == 200
        with zipfile.ZipFile(io.BytesIO(template.content)) as bundle:
            assert "UPLOAD_INSTRUCTIONS.txt" in bundle.namelist()


@pytest.mark.asyncio
async def test_benchmark_export_is_durable_async_and_downloadable(
    evaluation_store: EvaluationStore,
) -> None:
    """ZIP generation should expose a durable job before an authenticated download."""
    async with aiosqlite.connect(evaluation_store.database_path) as connection:
        await connection.executemany(
            """INSERT INTO evaluation_benchmarks (
                   id,batch_id,conversation_id,event_id,case_type,source,language,
                   scenario_tag,label,audio_start_s,audio_end_s,positioning_quality,created_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [
                (
                    "BM-EXPORT",
                    "EV-EXPORT",
                    _VALID_CONVERSATION_ID,
                    "R2",
                    "good",
                    "manual",
                    "ar",
                    "branch_names",
                    "expected transcript",
                    0.0,
                    1.0,
                    "exact",
                    "2026-09-17T00:00:00+00:00",
                ),
                (
                    "BM-MISSING-AUDIO",
                    "EV-EXPORT",
                    "missing-conversation",
                    "R4",
                    "bad",
                    "manual",
                    "en",
                    "numbers",
                    "missing audio transcript",
                    0.0,
                    1.0,
                    "exact",
                    "2026-09-17T00:00:01+00:00",
                ),
            ],
        )
        await connection.commit()
    await evaluation_store.finalize_benchmark_clip("BM-EXPORT")
    await evaluation_store.finalize_benchmark_clip("BM-MISSING-AUDIO")

    app = FastAPI()
    app.include_router(create_evaluation_router(evaluation_store))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        started = await client.post(
            "/api/evaluation/benchmarks/export",
            json={"sample_ids": ["BM-EXPORT", "BM-MISSING-AUDIO"]},
        )
        assert started.status_code == 202
        export = started.json()
        assert export["status"] == "pending"
        assert "artifact_path" not in export

        for _ in range(100):
            status = await client.get(export["status_url"])
            export = status.json()
            if export["status"] != "pending":
                break
            await asyncio.sleep(0.01)

        assert export["status"] == "ready", export
        downloaded = await client.get(export["download_url"])
        assert downloaded.status_code == 200
        with zipfile.ZipFile(io.BytesIO(downloaded.content)) as bundle:
            assert "benchmark.csv" in bundle.namelist()
            assert "manifest.csv" in bundle.namelist()
            assert any(name.endswith("/BM-EXPORT.wav") for name in bundle.namelist())
            assert "BM-MISSING-AUDIO" in bundle.read("manifest.csv").decode("utf-8-sig")
    async with aiosqlite.connect(evaluation_store.database_path) as connection:
        audit = await (
            await connection.execute(
                """SELECT metadata_json FROM evaluation_audit
                   WHERE action='benchmark_export.downloaded' AND object_id=?""",
                (export["id"],),
            )
        ).fetchone()
    assert audit is not None
    assert json.loads(audit[0]) == {"sample_count": 2}


@pytest.mark.asyncio
async def test_benchmark_clip_state_and_corrections_are_persisted(
    evaluation_store: EvaluationStore,
) -> None:
    """Managed clips become playable and corrections retain immutable history."""
    benchmark_id = "BM-LIFECYCLE"
    async with aiosqlite.connect(evaluation_store.database_path) as connection:
        await connection.execute(
            """INSERT INTO evaluation_benchmarks (
               id,batch_id,conversation_id,event_id,case_type,source,language,
               scenario_tag,label,audio_start_s,audio_end_s,positioning_quality,created_at
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                benchmark_id,
                "EV-LIFECYCLE",
                _VALID_CONVERSATION_ID,
                "R2",
                "bad",
                "manual",
                "ar",
                "branch_names",
                "first label",
                0.0,
                1.0,
                "exact",
                "2026-09-17T00:00:00+00:00",
            ),
        )
        await evaluation_store._append_benchmark_revision(connection, benchmark_id)
        await connection.commit()
    await evaluation_store.finalize_benchmark_clip(benchmark_id)
    managed_clip = await evaluation_store.benchmark_audio_path(benchmark_id)
    assert managed_clip is not None and managed_clip.is_file()

    app = FastAPI()
    app.include_router(create_evaluation_router(evaluation_store))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        audio = await client.get(f"/api/evaluation/benchmarks/{benchmark_id}/audio")
        assert audio.status_code == 200
        assert audio.headers["content-type"].startswith("audio/")
        updated = await client.patch(
            f"/api/evaluation/benchmarks/{benchmark_id}",
            json={
                "label": "corrected label",
                "language": "mixed",
                "scenario_tag": "numbers",
                "expected_revision": 1,
            },
        )
        assert updated.status_code == 200
        assert updated.json()["revision"] == 2
        searched = await client.get("/api/evaluation/benchmarks?search=corrected")
        assert searched.status_code == 200
        assert [item["id"] for item in searched.json()["items"]] == [benchmark_id]
        assert searched.json()["items"][0]["audio_url"].endswith(
            f"/benchmarks/{benchmark_id}/audio"
        )
        conflict = await client.patch(
            f"/api/evaluation/benchmarks/{benchmark_id}",
            json={
                "label": "stale label",
                "language": "en",
                "scenario_tag": "numbers",
                "expected_revision": 1,
            },
        )
        assert conflict.status_code == 409
        revisions = await client.get(f"/api/evaluation/benchmarks/{benchmark_id}/revisions")
        assert [row["label"] for row in revisions.json()] == [
            "first label",
            "corrected label",
        ]
        deleted = await client.delete(f"/api/evaluation/benchmarks/{benchmark_id}")
        assert deleted.status_code == 200
        assert deleted.json() == {"id": benchmark_id, "deleted": True}
        deleted_audio = await client.get(f"/api/evaluation/benchmarks/{benchmark_id}/audio")
        assert deleted_audio.status_code == 404
        assert (
            await client.get(f"/api/evaluation/benchmarks/{benchmark_id}/revisions")
        ).status_code == 404
        assert (await client.get(f"/api/evaluation/benchmarks?search={benchmark_id}")).json()[
            "total"
        ] == 0
        repeated = await client.delete(f"/api/evaluation/benchmarks/{benchmark_id}")
        assert repeated.status_code == 404
    assert not managed_clip.exists()
    assert await evaluation_store.get_conversation(_VALID_CONVERSATION_ID) is not None
    async with aiosqlite.connect(evaluation_store.database_path) as connection:
        actions = {
            row[0]
            for row in await (
                await connection.execute(
                    """SELECT action FROM evaluation_audit
                       WHERE object_id=?""",
                    (benchmark_id,),
                )
            ).fetchall()
        }
    assert {
        "benchmark_audio.played",
        "benchmark.viewed",
        "benchmark.updated",
        "benchmark.deleted",
    } <= actions


@pytest.mark.asyncio
async def test_elevenlabs_webhook_verifies_signature_and_is_idempotent(
    evaluation_store: EvaluationStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only a signed Scribe callback may complete the durable correlation row."""
    secret = "test-webhook-secret"
    monkeypatch.setenv("ELEVENLABS_STT_WEBHOOK_SECRET", secret)
    payload = {
        "type": "speech_to_text_transcription",
        "data": {
            "request_id": "scribe-request-1",
            "webhook_metadata": {"correlation_id": "evaluation:EV-1:C-1:1"},
            "transcription": {
                "text": "hello",
                "words": [
                    {
                        "type": "word",
                        "text": "hello",
                        "start": 0.0,
                        "end": 0.5,
                    }
                ],
            },
        },
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = str(int(time.time()))
    digest = hmac.new(secret.encode(), timestamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
    signature = f"t={timestamp},v0={digest}"
    app = FastAPI()
    app.include_router(create_evaluation_router(evaluation_store))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        invalid = await client.post(
            "/api/evaluation/webhooks/elevenlabs",
            content=raw,
            headers={"content-type": "application/json", "elevenlabs-signature": "bad"},
        )
        headers = {
            "content-type": "application/json",
            "elevenlabs-signature": signature,
        }
        first = await client.post(
            "/api/evaluation/webhooks/elevenlabs", content=raw, headers=headers
        )
        duplicate = await client.post(
            "/api/evaluation/webhooks/elevenlabs", content=raw, headers=headers
        )

    assert invalid.status_code == 401
    assert first.json() == {"status": "received"}
    assert duplicate.json() == {"status": "received"}
    job = await evaluation_store.get_elevenlabs_job("evaluation:EV-1:C-1:1")
    assert job is not None
    assert job["status"] == "completed"
    assert job["result"]["text"] == "hello"


@pytest.mark.asyncio
async def test_elevenlabs_webhook_rejects_malformed_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A signed callback must still carry a valid structured correlation value."""
    secret = "test-webhook-secret-secondary"
    monkeypatch.setenv("ELEVENLABS_STT_WEBHOOK_SECRET", secret)
    store = EvaluationStore(tmp_path / "evaluation.db", _source_root())
    await store.initialize()
    app = FastAPI()
    app.include_router(create_evaluation_router(store))
    payload = {
        "type": "speech_to_text_transcription",
        "data": {
            "request_id": "req-malformed",
            "webhook_metadata": "{not-json",
            "transcription": {"text": "hello", "words": []},
        },
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = str(int(datetime.now(UTC).timestamp()))
    signature = hmac.new(
        secret.encode(), timestamp.encode() + b"." + raw, hashlib.sha256
    ).hexdigest()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/evaluation/webhooks/elevenlabs",
            content=raw,
            headers={
                "content-type": "application/json",
                "elevenlabs-signature": f"t={timestamp},v0={signature}",
            },
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_elevenlabs_adapter_recovers_webhook_result_without_resubmitting(
    evaluation_store: EvaluationStore,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A resumed worker should reuse its correlated webhook result."""
    monkeypatch.setenv("ELEVENLABS_STT_WEBHOOK_ID", "webhook-1")
    monkeypatch.setenv("ELEVENLABS_STT_WEBHOOK_SECRET", "secret")
    correlation_id = "evaluation:EV-1:C-1:1"
    await evaluation_store.complete_elevenlabs_job(
        request_id="scribe-request-1",
        correlation_id=correlation_id,
        result={
            "text": "hello",
            "words": [{"type": "word", "text": "hello", "start": 0.0, "end": 0.5}],
        },
        error=None,
    )
    runner = EvaluationRunner(evaluation_store, None)
    result, request_id = await runner._elevenlabs(
        "https://api.elevenlabs.io",
        "unused-test-key",
        tmp_path / "unused.mp3",
        "C-1",
        correlation_id=correlation_id,
    )

    assert request_id == "scribe-request-1"
    assert result["text"] == "hello"
    assert result["segments"][0]["segment_id"] == "C-1:elevenlabs:0"


@pytest.mark.asyncio
async def test_elevenlabs_adapter_uses_synchronous_fallback_without_webhook(
    evaluation_store: EvaluationStore,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Local acceptance without a public callback should use the documented sync response."""
    monkeypatch.delenv("ELEVENLABS_STT_WEBHOOK_ID", raising=False)
    monkeypatch.delenv("ELEVENLABS_STT_WEBHOOK_SECRET", raising=False)
    audio_path = tmp_path / "call.mp3"
    audio_path.write_bytes(b"test-audio")

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "text": "fallback",
                "words": [{"type": "word", "text": "fallback", "start": 0.0, "end": 0.5}],
            }

    class FakeClient:
        def __init__(self, *, timeout: float) -> None:
            assert timeout == 300

        async def __aenter__(self) -> FakeClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, *args: object, **kwargs: object) -> FakeResponse:
            assert kwargs["data"] == {"model_id": "scribe_v2", "diarize": "true"}
            return FakeResponse()

    monkeypatch.setattr("src.evaluation.executor.httpx.AsyncClient", FakeClient)
    runner = EvaluationRunner(evaluation_store, None)
    result, request_id = await runner._elevenlabs(
        "https://api.elevenlabs.io",
        "unused-test-key",
        audio_path,
        "C-2",
        correlation_id="evaluation:EV-1:C-2:1",
    )

    assert request_id is None
    assert result["text"] == "fallback"
