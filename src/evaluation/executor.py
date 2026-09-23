"""Restart-safe execution of the two-pass ASR evaluation workflow."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, cast

import httpx
from google import genai
from google.genai import types
from openai import AsyncOpenAI

from src.bots.crypto import BotKeyCipher
from src.evaluation.alignment import build_turn_catalog
from src.evaluation.asr_contract import ASRError, ASRResult
from src.evaluation.pass2_packing import (
    FIXED_EVALUATION_USER_MESSAGE,
    build_event_alignment_unit,
    build_pass_one_payload,
    build_pass_one_unit,
    build_pass_two_payload,
    build_unit,
    estimate_tokens,
    evaluation_token_policy,
    final_request_input_tokens,
    input_limit,
    model_token_policy,
    pack_event_alignment_units,
    pack_pass_one_units,
    pack_units,
    render_prompt,
)
from src.evaluation.pricing import normalize_pricing_model_id
from src.evaluation.prompts import (
    EVALUATION_CONTEXT,
    EVENT_ALIGNER_SYSTEM_PROMPT,
    PASS_ONE_SYSTEM_PROMPT,
    PASS_TWO_SYSTEM_PROMPT,
    REFERENCE_DICTIONARIES,
    SCENARIO_TAGS,
)
from src.evaluation.storage import EvaluationStore
from src.llm.capabilities import get_model_capability
from src.llm.qwen_dashscope import (
    is_native_dashscope_url,
    native_dashscope_generation_url,
    native_dashscope_request,
    parse_native_dashscope_response,
)

logger = logging.getLogger(__name__)

_ASR_HOURLY_USD = {"soniox": 0.10, "speechmatics": 0.129, "elevenlabs": 0.22}
_ASR_PROVIDER_CONCURRENCY = {"soniox": 2, "speechmatics": 2, "elevenlabs": 2}


def _audio_media_type(path: Path) -> str:
    """Return the supported upload media type for an evaluation audio file."""
    return "audio/wav" if path.suffix.casefold() == ".wav" else "audio/mpeg"


class EvaluationExecutionError(RuntimeError):
    """An execution failure safe to persist without upstream response bodies."""


class EvaluationBudgetReached(EvaluationExecutionError):
    """Raised before dispatch when the next request would exceed the frozen budget."""


class EvaluationRequestTooLarge(EvaluationExecutionError):
    """Raised before dispatch when a final request violates its frozen input cap."""


class EvaluationRequestOutputTooLarge(EvaluationExecutionError):
    """Raised before dispatch when one unit cannot fit its generation cap."""


def _parse_json(text: str) -> dict[str, Any]:
    """Parse a JSON object while tolerating an accidental Markdown fence."""
    value = text.strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[-1]
        value = value.rsplit("```", 1)[0]
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("Model response must be one JSON object")
    return parsed


def _render_prompt(template: str, payload: dict[str, Any]) -> str:
    """Replace every declared runtime slot with its exact serialized session value."""
    return render_prompt(template, payload)


def _gemini_thinking_config(
    model_id: str,
    *,
    thinking: bool,
    disable_thinking: bool,
) -> types.ThinkingConfig | None:
    """Build only controls verified for the selected Gemini model generation."""
    if thinking:
        return types.ThinkingConfig(thinking_budget=-1, include_thoughts=False)
    if not disable_thinking:
        return None
    capability = get_model_capability("google_gemini", model_id)
    if capability and capability.control_name == "thinking_level":
        return types.ThinkingConfig(
            thinking_level=str(capability.control_value),
            include_thoughts=False,
        )
    return types.ThinkingConfig(thinking_budget=0, include_thoughts=False)


def _completion_limit_field(provider: str, model_id: str) -> str:
    """Select the provider field that caps total generated tokens when supported."""
    if provider == "deepseek":
        return "max_tokens"
    if provider == "qwen" and not model_id.casefold().startswith("qwen3.8-"):
        return "max_tokens"
    return "max_completion_tokens"


def _safe_error(exc: Exception) -> str:
    """Return a bounded error category without leaking request data or credentials."""
    status = getattr(exc, "status_code", None)
    if status in {401, 403}:
        return "authentication_failed"
    if status == 429:
        return "rate_limited"
    if status == 400:
        return "bad_request"
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError, httpx.TimeoutException)):
        return "timeout"
    return type(exc).__name__[:80]


def _structured_response_format(
    provider: str,
    thinking: bool,
    model_id: str | None = None,
) -> dict[str, str] | None:
    """Use JSON mode only where the provider accepts it with the chosen reasoning mode."""
    # Older Qwen models reject JSON mode with Thinking. Qwen 3.8 explicitly
    # supports their combination, while schema checks remain authoritative.
    if provider == "qwen" and thinking and not (model_id or "").casefold().startswith("qwen3.8-"):
        return None
    return {"type": "json_object"}


def _safe_execution_failure(exc: Exception, stage: str) -> dict[str, object]:
    """Describe a batch failure without retaining upstream bodies or credentials."""
    category = _safe_error(exc)
    message = "The evaluation stopped unexpectedly. Retry the batch or contact support."
    retryable = True
    if category == "authentication_failed":
        message = "Provider authentication failed. Recheck the saved connection, then retry."
        retryable = False
    elif category == "rate_limited":
        message = "A provider rate limit was reached. Retry after the limit resets."
    elif category == "timeout":
        message = "A provider request timed out. Retry the failed work."
    elif isinstance(exc, EvaluationBudgetReached):
        category = "budget_reached"
        message = "The frozen batch budget cannot admit the next external request."
        retryable = False
    elif isinstance(exc, EvaluationRequestTooLarge):
        category = "preflight_input_limit"
        message = str(exc).strip()[:240]
        retryable = False
    elif isinstance(exc, EvaluationRequestOutputTooLarge):
        category = "preflight_output_limit"
        message = str(exc).strip()[:240]
        retryable = False
    elif isinstance(exc, EvaluationExecutionError):
        controlled_message = str(exc).strip()[:240]
        lowered = controlled_message.lower()
        if "missing verified connections" in lowered or "connection unavailable" in lowered:
            category = "connection_unavailable"
        elif "cannot be decrypted" in lowered:
            category = "credential_unavailable"
        elif "verified catalog" in lowered:
            category = "model_unavailable"
        elif "price is unavailable" in lowered:
            category = "pricing_unavailable"
        elif "group membership changed" in lowered:
            category = "checkpoint_conflict"
        else:
            category = "evaluation_execution_error"
        message = controlled_message or message
        retryable = category not in {
            "credential_unavailable",
            "model_unavailable",
            "pricing_unavailable",
        }
    elif isinstance(exc, (json.JSONDecodeError, ValueError)):
        category = "invalid_provider_response"
        message = "A provider returned data that failed the frozen response contract."

    return {
        "category": category,
        "message": message,
        "stage": stage,
        "retryable": retryable,
    }


def _segment_id(conversation_id: str, provider: str, index: int) -> str:
    """Create a globally traceable segment identity within one evaluation batch."""
    return f"{conversation_id}:{provider}:{index}"


def _asr_error(provider: str, exc: Exception) -> str:
    """Normalize one provider failure without persisting request or response data."""
    safe = _safe_error(exc)
    categories = {"authentication_failed", "rate_limited", "timeout"}
    category = safe if safe in categories else "provider_error"
    message = {
        "authentication_failed": "Provider authentication failed.",
        "rate_limited": "Provider rate limit was reached.",
        "timeout": "Provider request timed out.",
    }.get(category, "Provider job failed without a usable result.")
    retryable = category in {"rate_limited", "timeout", "provider_error"}
    controlled = str(exc).strip()
    lowered = controlled.casefold()
    if isinstance(exc, ValueError) and str(exc).startswith("Event Aligner"):
        category = "event_alignment_failed"
        message = str(exc)[:160]
    elif isinstance(exc, ValueError) and (
        "provider turns" in str(exc) or "provider union" in str(exc)
    ):
        category = "event_alignment_failed"
        message = str(exc)[:160]
    elif isinstance(exc, ValueError) and "user" in str(exc).casefold():
        category = "user_signal_validation_failed"
        message = str(exc)[:160]
    elif isinstance(exc, EvaluationExecutionError):
        if "no usable diarized full-call speaker timeline" in lowered:
            category = "invalid_result"
            message = "Provider returned no usable diarized speaker timeline."
            retryable = False
        elif "no transcript for the submitted audio" in lowered:
            category = "empty_transcript"
            message = "Provider returned no transcript for the submitted audio."
        elif "job rejected" in lowered:
            category = "provider_job_rejected"
            message = "Provider rejected the ASR job. Check the audio and provider settings."
            retryable = False
        elif "job error" in lowered or "job failed" in lowered:
            category = "provider_job_failed"
            message = "Provider ASR job failed before producing a usable result."
        elif "unsupported" in lowered or "configuration" in lowered:
            category = "configuration_error"
            message = "The ASR provider configuration is not supported."
            retryable = False
    if type(exc).__name__ == "ValidationError":
        category = "invalid_result"
        message = "Provider returned an invalid ASR result."
        retryable = False
    return ASRError(
        provider=provider,
        category=category,
        retryable=retryable,
        message=message,
    ).model_dump_json()


def _has_usable_diarized_timeline(result: object) -> bool:
    """Return whether a full-call result satisfies the current speaker contract."""
    if not isinstance(result, dict) or result.get("diarization_contract") != (
        "speaker_timestamps_v1"
    ):
        return False
    speakers: set[str] = set()
    for segment in result.get("segments") or []:
        if not isinstance(segment, dict):
            continue
        speaker = str(segment.get("speaker") or "").strip()
        text = str(segment.get("text") or "").strip()
        try:
            start_s = float(segment["start"])
            end_s = float(segment["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if speaker and text and start_s >= 0 and end_s > start_s:
            speakers.add(speaker)
    return len(speakers) >= 2


def _contains_key(value: object, forbidden_key: str) -> bool:
    """Detect a forbidden model-output field at any nesting level."""
    if isinstance(value, dict):
        return forbidden_key in value or any(
            _contains_key(item, forbidden_key) for item in value.values()
        )
    if isinstance(value, list):
        return any(_contains_key(item, forbidden_key) for item in value)
    return False


def _structured_retry_correction(exc: Exception) -> str:
    """Return content-free feedback that helps the next structured-output attempt."""
    if isinstance(exc, json.JSONDecodeError):
        failure = "The previous response was not one valid JSON object."
    elif isinstance(exc, ValueError):
        failure = str(exc).strip()[:240] or "The previous response violated the response schema."
    else:
        failure = "The previous response did not complete successfully."
    return (
        f"{failure} Retry the same complete input. Return every required item exactly once, "
        "preserve all required IDs, and output only the required JSON object."
    )


def _safe_structured_error(exc: Exception) -> str:
    """Persist an actionable schema category without provider content."""
    if isinstance(exc, EvaluationRequestTooLarge):
        return "preflight_input_limit"
    if isinstance(exc, EvaluationRequestOutputTooLarge):
        return "preflight_output_limit"
    if isinstance(exc, json.JSONDecodeError):
        return "schema_invalid_json"
    if isinstance(exc, ValueError):
        detail = str(exc).strip()[:160]
        return f"schema_contract: {detail}" if detail else "schema_contract"
    return _safe_error(exc)


def _pass_two_error_supports_split(error: str | None) -> bool:
    """Split only failures whose condition can improve with a smaller payload."""
    normalized = str(error or "").casefold()
    return normalized == "timeout" or normalized.startswith("schema_")


class EvaluationRunner:
    """Coordinate real LLM and ASR calls with SQLite checkpoints."""

    def __init__(self, store: EvaluationStore, cipher: BotKeyCipher | None) -> None:
        """Bind execution to persistent storage and the configured key cipher."""
        self.store = store
        self.cipher = cipher
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._worker_id = f"evaluation-worker-{uuid.uuid4().hex}"

    async def resume_pending(self) -> None:
        """Resume batches that were confirmed but interrupted by a process restart."""
        for batch in await self.store.list_batches():
            if batch["status"] == "running":
                self.start(str(batch["id"]))

    def start(self, batch_id: str) -> None:
        """Schedule one batch once in this process."""
        task = self._tasks.get(batch_id)
        if task is not None and not task.done():
            return
        self._tasks[batch_id] = asyncio.create_task(
            self._run_guarded(batch_id), name=f"evaluation-{batch_id}"
        )

    def handle_action(self, batch_id: str, action: str) -> None:
        """Apply process-local scheduling after the durable transition commits."""
        if action in {"pause", "stop"}:
            task = self._tasks.get(batch_id)
            if task is not None and not task.done():
                task.cancel()
            return
        if action in {"start", "resume", "retry_failed"}:
            self.start(batch_id)

    async def close(self) -> None:
        """Cancel in-process tasks; persisted checkpoints remain resumable."""
        tasks = [task for task in self._tasks.values() if not task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def translate_for_display(
        self,
        batch_id: str,
        texts: list[str],
    ) -> dict[str, object]:
        """Translate visible transcript text with the batch's frozen Pass 1 model."""
        batch = await self.store.get_batch(batch_id)
        if batch is None:
            raise EvaluationExecutionError("Batch is unavailable")
        model_id = str(batch["snapshot"]["pass_1_model"])
        provider = await self._model_provider(model_id)
        system_prompt = (
            "Translate each source_texts item into clear Simplified Chinese for display. "
            "Preserve names, numbers, intent, and uncertainty. Do not correct or classify "
            "the transcript. Return exactly one JSON object with a translations array; "
            "each item must contain the original integer index and translation_zh string. "
            "Do not wrap the JSON in Markdown fences or add any explanatory text."
        )

        def validate(result: dict[str, object], expected_count: int) -> list[str]:
            """Validate one display-only response without accepting partial translations."""
            raw_translations = result.get("translations")
            if not isinstance(raw_translations, list):
                raise ValueError("Missing translations array")
            translations: list[str | None] = [None] * expected_count
            for item in raw_translations:
                if not isinstance(item, dict):
                    raise ValueError("Invalid translation item")
                index = item.get("index")
                translation = item.get("translation_zh")
                if (
                    not isinstance(index, int)
                    or not 0 <= index < expected_count
                    or not isinstance(translation, str)
                    or not translation.strip()
                    or translations[index] is not None
                ):
                    raise ValueError("Invalid translation index or text")
                translations[index] = translation.strip()
            if any(value is None for value in translations):
                raise ValueError("Translation response is incomplete")
            return [str(value) for value in translations]

        request_id = uuid.uuid4().hex
        attempt_count = 0

        async def translate_group(group: list[str], group_key: str) -> list[str]:
            """Retry one stable group twice while preserving budget semantics."""
            nonlocal attempt_count
            payload = {
                "source_texts": [{"index": index, "text": text} for index, text in enumerate(group)]
            }
            last_error: Exception | None = None
            for attempt in range(1, 3):
                attempt_count += 1
                try:
                    result = await self._llm_json(
                        model_id,
                        system_prompt,
                        payload,
                        thinking=False,
                        max_output_tokens=min(
                            8192,
                            max(512, estimate_tokens(payload) * 2),
                        ),
                        batch_id=batch_id,
                        stage="display_translation",
                        item_key=f"{request_id}:{group_key}",
                        attempt=attempt,
                        pause_batch_on_budget_rejection=False,
                        disable_thinking=True,
                    )
                    return validate(result, len(group))
                except EvaluationBudgetReached:
                    raise
                except Exception as exc:
                    last_error = exc
                    logger.warning(
                        "Display translation attempt failed batch=%s provider=%s "
                        "group=%s size=%s attempt=%s error=%s",
                        batch_id,
                        provider,
                        group_key,
                        len(group),
                        attempt,
                        _safe_error(exc),
                    )
            assert last_error is not None
            raise last_error

        split_used = False
        failed_count = 0
        translations: list[str | None]
        try:
            try:
                translations = cast(
                    list[str | None],
                    await translate_group(texts, "full"),
                )
            except EvaluationBudgetReached:
                raise
            except Exception:
                if len(texts) <= 4:
                    translations = [None] * len(texts)
                    failed_count = len(texts)
                else:
                    split_used = True
                    translations = []
                    for start in range(0, len(texts), 4):
                        group = texts[start : start + 4]
                        try:
                            translations.extend(
                                await translate_group(
                                    group,
                                    f"chunk-{start // 4}",
                                )
                            )
                        except EvaluationBudgetReached:
                            raise
                        except Exception:
                            translations.extend([None] * len(group))
                            failed_count += len(group)
        except EvaluationBudgetReached:
            raise
        except Exception as exc:
            logger.warning(
                "Display translation failed batch=%s provider=%s error=%s",
                batch_id,
                provider,
                _safe_error(exc),
            )
            raise EvaluationExecutionError(
                "Display translation is temporarily unavailable"
            ) from exc
        await self.store.audit_access(
            "display_translation.requested",
            batch_id,
            {
                "provider": provider,
                "model_id": model_id,
                "text_count": len(texts),
                "attempt_count": attempt_count,
                "split_used": split_used,
                "failed_count": failed_count,
            },
        )
        return {
            "translations": translations,
            "provider": provider,
            "model_id": model_id,
            "ephemeral": True,
            "evidence": False,
            "partial": failed_count > 0,
            "failed_count": failed_count,
        }

    async def _run_guarded(self, batch_id: str) -> None:
        """Run a batch and convert unexpected failures into an honest terminal state."""
        if not await self.store.acquire_batch_lease(batch_id, self._worker_id):
            return
        parent_task = asyncio.current_task()

        async def renew_lease() -> None:
            while True:
                await asyncio.sleep(30)
                if not await self.store.renew_batch_lease(batch_id, self._worker_id):
                    if parent_task is not None:
                        parent_task.cancel()
                    return

        lease_task = asyncio.create_task(renew_lease(), name=f"evaluation-lease-{batch_id}")
        try:
            await self._run(batch_id)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # The stage checkpoints retain the actionable detail.
            logger.exception("evaluation_batch_failed batch_id=%s", batch_id)
            current = await self.store.get_batch(batch_id)
            failure = _safe_execution_failure(
                exc,
                str(current["stage"]) if current is not None else "unknown",
            )
            await self.store.set_batch_state(
                batch_id,
                status="partially_failed",
                stage=str(current["stage"]) if current is not None else "failed",
                progress=int(current["progress"]) if current is not None else 0,
                snapshot_updates={
                    "execution_error": failure["category"],
                    "execution_failure": failure,
                },
            )
        finally:
            lease_task.cancel()
            await asyncio.gather(lease_task, return_exceptions=True)
            await self.store.release_batch_lease(batch_id, self._worker_id)

    async def _run(self, batch_id: str) -> None:
        """Execute Pass 1, candidate-only ASR, Pass 2, then manual review."""
        batch = await self.store.get_batch(batch_id)
        if batch is None or batch["status"] == "stopped":
            return
        if self.cipher is None:
            raise EvaluationExecutionError("Saved provider keys cannot be decrypted")
        await self._validate_connections(batch)
        await self.store.set_batch_state(
            batch_id,
            status="running",
            stage="pass_1",
            progress=21,
            snapshot_updates={"provider_execution": "running"},
        )
        conversations = await self.store.source_conversations()
        await self._run_pass_one(batch_id, conversations)
        current = await self.store.get_batch(batch_id)
        if current is None or current["status"] == "budget_paused":
            return
        pass_one_rows = await self.store.checkpoint_rows("evaluation_pass1_runs", batch_id)
        completed_conversation_ids = {
            str(row["conversation_id"]) for row in pass_one_rows if row.get("status") == "completed"
        }
        failed_pass_one = sum(1 for row in pass_one_rows if row.get("status") == "failed")
        valid_user_events = sum(
            sum(event.get("speaker") == "customer" for event in conversation.get("events", []))
            for conversation in conversations
            if str(conversation["conversation_id"]) in completed_conversation_ids
        )
        source_user_events = int(batch["snapshot"].get("source_user_event_count", 0))
        await self.store.set_batch_state(
            batch_id,
            status="running",
            stage="pass_1",
            progress=44,
            denominator=valid_user_events,
            excluded_count=max(0, source_user_events - valid_user_events),
        )
        batch = await self.store.get_batch(batch_id)
        assert batch is not None
        if not completed_conversation_ids:
            await self.store.set_batch_state(
                batch_id,
                status="partially_failed",
                stage="failed",
                progress=44,
                snapshot_updates={
                    "provider_execution": "failed",
                    "execution_error": "pass_1_failed",
                    "execution_failure": {
                        "category": "pass_1_failed",
                        "message": "All first-pass evaluations failed",
                        "stage": "pass_1",
                        "retryable": True,
                    },
                    "pass_1_failed": failed_pass_one,
                },
            )
            return
        candidates = self._candidates(pass_one_rows)
        candidate_conversation_ids = {str(item["conversation_id"]) for item in candidates}
        await self.store.set_batch_state(
            batch_id,
            status="running",
            stage="evaluation_asr",
            progress=45,
            suspected_numerator=len(candidates),
            snapshot_updates={
                "candidate_conversation_count": len(candidate_conversation_ids),
                "candidate_event_count": len(candidates),
            },
        )
        if not candidates:
            report = await self.store.freeze_preliminary_report(batch_id)
            await self.store.set_batch_state(
                batch_id,
                status="completed_partial" if failed_pass_one else "completed",
                stage="completed",
                progress=100,
                snapshot_updates={
                    "provider_execution": "completed",
                    "pass_1_failed": failed_pass_one,
                    "benchmark_count": 0,
                    "latest_report_id": report["report_id"],
                    "latest_report_type": report["report_type"],
                },
            )
            return
        await self._run_asr(batch_id, batch, candidates)
        current = await self.store.get_batch(batch_id)
        if current is None or current["status"] == "budget_paused":
            return
        asr_rows = await self.store.checkpoint_rows("evaluation_case_asr_runs", batch_id)
        evidence_case_keys = {
            (str(row["conversation_id"]), str(row["event_id"]))
            for row in asr_rows
            if row.get("status") == "completed"
        }
        evidence_conversation_ids = {key[0] for key in evidence_case_keys}
        candidate_keys = {
            (str(item["conversation_id"]), str(item["event_id"])) for item in candidates
        }
        unavailable_case_keys = sorted(candidate_keys - evidence_case_keys)
        unavailable_conversation_ids = sorted({key[0] for key in unavailable_case_keys})
        eligible_candidates = [
            candidate
            for candidate in candidates
            if (str(candidate["conversation_id"]), str(candidate["event_id"])) in evidence_case_keys
        ]
        await self.store.set_batch_state(
            batch_id,
            status="partially_failed" if unavailable_conversation_ids else "running",
            stage="evaluation_asr" if not eligible_candidates else "pass_2",
            progress=75,
            snapshot_updates={
                "asr_unavailable_conversations": unavailable_conversation_ids,
                "asr_eligible_candidate_count": len(eligible_candidates),
            },
        )
        if not eligible_candidates:
            return
        await self._run_pass_two(
            batch_id,
            batch,
            conversations,
            eligible_candidates,
            plan_key="suspects",
        )
        current = await self.store.get_batch(batch_id)
        if current is None or current["status"] == "budget_paused":
            return
        suspect_rows = {
            (str(row["conversation_id"]), str(row["event_id"])): row
            for row in await self.store.checkpoint_rows("evaluation_pass2_runs", batch_id)
        }
        incomplete_suspects = [
            key
            for key in candidate_keys & evidence_case_keys
            if suspect_rows.get(key, {}).get("status") != "completed"
        ]
        if incomplete_suspects:
            review_count, benchmark_count = await self.store.materialize_pass2_results(batch_id)
            await self.store.set_batch_state(
                batch_id,
                status="partially_failed",
                stage="pass_2",
                progress=int(current["progress"]),
                review_total=review_count,
                snapshot_updates={
                    "provider_execution": "partially_failed",
                    "pass_2_failed": len(incomplete_suspects),
                    "good_balance_deferred": True,
                    "benchmark_count": benchmark_count,
                },
            )
            return
        good_pool = self._good_pool(
            pass_one_rows,
            conversations,
            candidate_conversation_ids & evidence_conversation_ids,
        )
        balance_round = 1
        while good_pool:
            pass_two_rows = await self.store.checkpoint_rows("evaluation_pass2_runs", batch_id)
            decisions = [
                str((row.get("result") or {}).get("decision"))
                for row in pass_two_rows
                if row.get("status") == "completed"
            ]
            missing_good = max(0, decisions.count("Bad Case") - decisions.count("Good Case"))
            if missing_good == 0:
                break
            selected = good_pool[:missing_good]
            del good_pool[:missing_good]
            await self._run_asr(batch_id, batch, selected)
            completed_good_keys = {
                (str(row["conversation_id"]), str(row["event_id"]))
                for row in await self.store.checkpoint_rows("evaluation_case_asr_runs", batch_id)
                if row.get("status") == "completed"
            }
            selected = [
                item
                for item in selected
                if (str(item["conversation_id"]), str(item["event_id"])) in completed_good_keys
            ]
            if not selected:
                continue
            await self._run_pass_two(
                batch_id,
                batch,
                conversations,
                selected,
                plan_key=f"good-balance-{balance_round}",
            )
            balance_round += 1
        pass_two = await self.store.checkpoint_rows("evaluation_pass2_runs", batch_id)
        final_decisions = [
            str((row.get("result") or {}).get("decision"))
            for row in pass_two
            if row.get("status") == "completed"
        ]
        final_bad = final_decisions.count("Bad Case")
        final_good = final_decisions.count("Good Case")
        await self.store.set_batch_state(
            batch_id,
            status="running",
            stage="pass_2",
            progress=92,
            snapshot_updates={
                "good_balance": {
                    "algorithm": "conversation_round_robin_v1",
                    "target_ratio": "1:1",
                    "good_count": final_good,
                    "bad_count": final_bad,
                    "shortage": max(0, final_bad - final_good),
                }
            },
        )
        failed = sum(1 for row in pass_two if row["status"] == "failed")
        failed_groups = sum(
            1 for row in await self.store.pass2_group_rows(batch_id) if row["status"] == "failed"
        )
        if failed or failed_groups:
            review_count, benchmark_count = await self.store.materialize_pass2_results(batch_id)
            await self.store.set_batch_state(
                batch_id,
                status="partially_failed",
                stage="pass_2",
                progress=92,
                review_total=review_count,
                snapshot_updates={
                    "provider_execution": "partially_failed",
                    "pass_2_failed": failed,
                    "pass_2_failed_groups": failed_groups,
                    "benchmark_count": benchmark_count,
                },
            )
            return
        review_count, benchmark_count = await self.store.materialize_pass2_results(batch_id)
        report = await self.store.freeze_preliminary_report(batch_id)
        terminal_status = (
            "partially_failed"
            if unavailable_conversation_ids
            else "awaiting_review"
            if review_count
            else "completed"
        )
        await self.store.set_batch_state(
            batch_id,
            status=terminal_status,
            stage=(
                "partial_failure"
                if unavailable_conversation_ids
                else "manual_review"
                if review_count
                else "completed"
            ),
            progress=92 if review_count else 100,
            review_total=review_count,
            snapshot_updates={
                "provider_execution": "completed",
                "pass_2_failed": failed,
                "benchmark_count": benchmark_count,
                "latest_report_id": report["report_id"],
                "latest_report_type": report["report_type"],
            },
        )

    async def _validate_connections(self, batch: dict[str, Any]) -> None:
        """Fail before billing if a frozen provider or model connection is unavailable."""
        snapshot = batch["snapshot"]
        required = list(snapshot["providers"])
        for model_key in ("pass_1_model", "pass_2_model"):
            provider = await self._model_provider(str(snapshot[model_key]))
            required.append(provider)
        missing = []
        for provider in set(required):
            connection = await self.store.get_connection(provider)
            if connection is None or connection["status"] != "verified":
                missing.append(provider)
        if missing:
            raise EvaluationExecutionError(
                "Missing verified connections: " + ", ".join(sorted(missing))
            )

    async def _model_provider(self, model_id: str) -> str:
        """Resolve a frozen custom model ID to its verified connection key."""
        qualified_provider, actual_model = (
            model_id.split("::", 1) if "::" in model_id else ("", model_id)
        )
        provider_keys = {
            "Gemini": "gemini",
            "GPT": "gpt",
            "Qwen": "qwen",
            "DeepSeek": "deepseek",
            "Azure GPT": "azure_gpt",
            "OpenRouter": "openrouter",
        }
        if qualified_provider:
            if qualified_provider not in provider_keys:
                raise EvaluationExecutionError(f"Unsupported model provider: {qualified_provider}")
            return provider_keys[qualified_provider]
        matches = [
            row for row in await self.store.list_llm_models() if row["model_id"] == actual_model
        ]
        if not matches:
            if model_id.startswith("gemini-"):
                return "gemini"
            if model_id.startswith("gpt-"):
                return "gpt"
            if model_id.casefold().startswith("qwen"):
                return "qwen"
            if model_id.startswith("deepseek-"):
                return "deepseek"
            raise EvaluationExecutionError(f"Model is not in the verified catalog: {model_id}")
        return {
            "Gemini": "gemini",
            "GPT": "gpt",
            "Qwen": "qwen",
            "DeepSeek": "deepseek",
            "Azure GPT": "azure_gpt",
            "OpenRouter": "openrouter",
        }[matches[0]["provider"]]

    async def _key(self, provider: str) -> tuple[str, str]:
        """Decrypt one verified connection only for the lifetime of its request."""
        connection = await self.store.get_connection(provider)
        if connection is None or self.cipher is None:
            raise EvaluationExecutionError(f"Connection unavailable: {provider}")
        secret = self.cipher.decrypt(str(connection["encrypted_api_key"]))
        return str(connection["base_url"]), secret.get_secret_value()

    async def _llm_json(
        self,
        model_id: str,
        system_prompt: str,
        payload: dict[str, Any],
        *,
        thinking: bool = False,
        max_output_tokens: int | None = None,
        batch_id: str,
        stage: str,
        item_key: str,
        attempt: int,
        pause_batch_on_budget_rejection: bool = True,
        disable_thinking: bool = False,
        system_only_payload: bool = False,
        user_instruction: str | None = None,
        max_input_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Call a verified model and require one JSON object response."""
        provider = await self._model_provider(model_id)
        actual_model = model_id.split("::", 1)[1] if "::" in model_id else model_id
        base_url, key = await self._key(provider)
        if system_only_payload:
            user_message = user_instruction or FIXED_EVALUATION_USER_MESSAGE
            estimated_input = final_request_input_tokens(
                system_prompt,
                payload,
                user_message=user_message,
            )
            system_prompt = _render_prompt(system_prompt, payload)
        else:
            user_message = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            system_prompt = _render_prompt(system_prompt, payload)
            estimated_input = estimate_tokens(system_prompt) + estimate_tokens(payload)
        output_limit = max_output_tokens or 8_192
        if max_input_tokens is not None and estimated_input > max_input_tokens:
            raise EvaluationRequestTooLarge(
                "Final evaluation request exceeds the pre-dispatch input limit "
                f"({estimated_input} > {max_input_tokens})."
            )
        batch = await self.store.get_batch(batch_id)
        if batch is None:
            raise EvaluationExecutionError("Batch is unavailable")
        reserve_amount, reserve_currency = self._frozen_llm_cost(
            batch,
            provider,
            actual_model,
            input_tokens=estimated_input,
            cached_input_tokens=0,
            reasoning_tokens=0,
            output_tokens=output_limit,
        )
        if reserve_amount is None:
            raise EvaluationExecutionError("Frozen model price is unavailable")
        fx = batch["snapshot"].get("pricing_version", {}).get("fx_rates", {"USD": 1.0, "CNY": 0.14})
        reserve_key = f"reserve:{batch_id}:{stage}:{item_key}:{attempt}"
        if not await self.store.reserve_budget(
            idempotency_key=reserve_key,
            batch_id=batch_id,
            estimated_usd=float(reserve_amount) * float(fx.get(reserve_currency, 0)),
            pause_batch_on_rejection=pause_batch_on_budget_rejection,
        ):
            raise EvaluationBudgetReached("Batch budget reached before the next LLM call")
        settled = False
        if provider == "gemini":
            client = genai.Client(api_key=key)
            try:
                config: dict[str, Any] = {
                    "system_instruction": system_prompt,
                    "response_mime_type": "application/json",
                    "temperature": 0,
                }
                thinking_config = _gemini_thinking_config(
                    actual_model,
                    thinking=thinking,
                    disable_thinking=disable_thinking,
                )
                if thinking_config is not None:
                    config["thinking_config"] = thinking_config
                if thinking:
                    config.pop("temperature")
                config["max_output_tokens"] = output_limit
                async with asyncio.timeout(120):
                    response = await client.aio.models.generate_content(
                        model=actual_model,
                        contents=user_message,
                        config=types.GenerateContentConfig(**config),
                    )
                usage = response.usage_metadata
                input_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
                cached_input_tokens = int(getattr(usage, "cached_content_token_count", 0) or 0)
                reasoning_tokens = int(getattr(usage, "thoughts_token_count", 0) or 0)
                output_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
                estimated_cost, currency = self._frozen_llm_cost(
                    batch,
                    provider,
                    actual_model,
                    input_tokens=input_tokens,
                    cached_input_tokens=cached_input_tokens,
                    reasoning_tokens=reasoning_tokens,
                    output_tokens=output_tokens,
                )
                await self.store.record_cost_entry(
                    idempotency_key=f"{batch_id}:{stage}:{item_key}:{attempt}",
                    batch_id=batch_id,
                    category="llm",
                    provider=provider,
                    stage=stage,
                    input_tokens=input_tokens,
                    cached_input_tokens=cached_input_tokens,
                    reasoning_tokens=reasoning_tokens,
                    output_tokens=output_tokens,
                    estimated_cost=estimated_cost,
                    currency=currency,
                    reservation_key=reserve_key,
                )
                settled = True
                return _parse_json(response.text or "")
            finally:
                await client.aio.aclose()
                if not settled:
                    await self.store.release_budget(reserve_key)
        if provider == "azure_gpt":
            try:
                request_body: dict[str, Any] = {
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    "max_tokens": output_limit,
                    "temperature": 0,
                }
                response_format = _structured_response_format(provider, thinking, actual_model)
                if response_format is not None:
                    request_body["response_format"] = response_format
                async with httpx.AsyncClient(timeout=120) as azure_client:
                    response = await azure_client.post(
                        base_url,
                        headers={"api-key": key, "Content-Type": "application/json"},
                        json=request_body,
                    )
                    response.raise_for_status()
                    response_payload = response.json()
                usage = response_payload.get("usage") or {}
                completion_details = usage.get("completion_tokens_details") or {}
                input_tokens = int(usage.get("prompt_tokens") or 0)
                cached_input_tokens = int(
                    (usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
                )
                reasoning_tokens = int(completion_details.get("reasoning_tokens") or 0)
                completion_tokens = int(usage.get("completion_tokens") or 0)
                output_tokens = max(0, completion_tokens - reasoning_tokens)
                estimated_cost, currency = self._frozen_llm_cost(
                    batch,
                    provider,
                    actual_model,
                    input_tokens=input_tokens,
                    cached_input_tokens=cached_input_tokens,
                    reasoning_tokens=reasoning_tokens,
                    output_tokens=output_tokens,
                )
                await self.store.record_cost_entry(
                    idempotency_key=f"{batch_id}:{stage}:{item_key}:{attempt}",
                    batch_id=batch_id,
                    category="llm",
                    provider=provider,
                    stage=stage,
                    input_tokens=input_tokens,
                    cached_input_tokens=cached_input_tokens,
                    reasoning_tokens=reasoning_tokens,
                    output_tokens=output_tokens,
                    estimated_cost=estimated_cost,
                    currency=currency,
                    reservation_key=reserve_key,
                )
                settled = True
                message = (response_payload.get("choices") or [{}])[0].get("message") or {}
                content = message.get("content") or ""
                return _parse_json(content)
            finally:
                if not settled:
                    await self.store.release_budget(reserve_key)
        if provider == "qwen" and is_native_dashscope_url(base_url):
            try:
                request_body = native_dashscope_request(
                    model=actual_model,
                    system_prompt=system_prompt,
                    user_message=user_message,
                    max_output_tokens=output_limit,
                    enable_thinking=True if thinking else False if disable_thinking else None,
                    structured_json=True,
                )
                async with httpx.AsyncClient(timeout=120) as dashscope_client:
                    response = await dashscope_client.post(
                        native_dashscope_generation_url(base_url, actual_model),
                        headers={
                            "Authorization": f"Bearer {key}",
                            "Content-Type": "application/json",
                        },
                        json=request_body,
                    )
                    response.raise_for_status()
                    content, usage = parse_native_dashscope_response(response.json())
                reasoning_tokens = usage["reasoning_tokens"]
                output_tokens = max(0, usage["output_tokens"] - reasoning_tokens)
                estimated_cost, currency = self._frozen_llm_cost(
                    batch,
                    provider,
                    actual_model,
                    input_tokens=usage["input_tokens"],
                    cached_input_tokens=usage["cached_input_tokens"],
                    reasoning_tokens=reasoning_tokens,
                    output_tokens=output_tokens,
                )
                await self.store.record_cost_entry(
                    idempotency_key=f"{batch_id}:{stage}:{item_key}:{attempt}",
                    batch_id=batch_id,
                    category="llm",
                    provider=provider,
                    stage=stage,
                    input_tokens=usage["input_tokens"],
                    cached_input_tokens=usage["cached_input_tokens"],
                    reasoning_tokens=reasoning_tokens,
                    output_tokens=output_tokens,
                    estimated_cost=estimated_cost,
                    currency=currency,
                    reservation_key=reserve_key,
                )
                settled = True
                return _parse_json(content)
            finally:
                if not settled:
                    await self.store.release_budget(reserve_key)
        client = AsyncOpenAI(
            api_key=key,
            base_url=base_url.rstrip("/") + "/",
            timeout=120,
            max_retries=0,
        )
        try:
            request: dict[str, Any] = {
                "model": actual_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
            }
            response_format = _structured_response_format(provider, thinking, actual_model)
            if response_format is not None:
                request["response_format"] = response_format
            if thinking:
                if provider == "deepseek":
                    request["reasoning_effort"] = "high"
                    request["extra_body"] = {"thinking": {"type": "enabled"}}
                elif provider == "qwen":
                    request["extra_body"] = {"enable_thinking": True}
                else:
                    request["reasoning_effort"] = "high"
            else:
                request["temperature"] = 0
                if provider == "deepseek" and disable_thinking:
                    request["extra_body"] = {"thinking": {"type": "disabled"}}
                elif provider == "qwen" and disable_thinking:
                    request["extra_body"] = {"enable_thinking": False}
            request[_completion_limit_field(provider, actual_model)] = output_limit
            response = await client.chat.completions.create(
                **request,
            )
            usage = response.usage
            prompt_details = getattr(usage, "prompt_tokens_details", None)
            completion_details = getattr(usage, "completion_tokens_details", None)
            input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
            cached_input_tokens = int(getattr(prompt_details, "cached_tokens", 0) or 0)
            reasoning_tokens = int(getattr(completion_details, "reasoning_tokens", 0) or 0)
            completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
            output_tokens = max(0, completion_tokens - reasoning_tokens)
            estimated_cost, currency = self._frozen_llm_cost(
                batch,
                provider,
                actual_model,
                input_tokens=input_tokens,
                cached_input_tokens=cached_input_tokens,
                reasoning_tokens=reasoning_tokens,
                output_tokens=output_tokens,
            )
            await self.store.record_cost_entry(
                idempotency_key=f"{batch_id}:{stage}:{item_key}:{attempt}",
                batch_id=batch_id,
                category="llm",
                provider=provider,
                stage=stage,
                input_tokens=input_tokens,
                cached_input_tokens=cached_input_tokens,
                reasoning_tokens=reasoning_tokens,
                output_tokens=output_tokens,
                estimated_cost=estimated_cost,
                currency=currency,
                reservation_key=reserve_key,
            )
            settled = True
            return _parse_json(response.choices[0].message.content or "")
        finally:
            await client.close()
            if not settled:
                await self.store.release_budget(reserve_key)

    @staticmethod
    def _frozen_llm_cost(
        batch: dict[str, Any],
        provider: str,
        model_id: str,
        *,
        input_tokens: int,
        cached_input_tokens: int,
        reasoning_tokens: int,
        output_tokens: int,
    ) -> tuple[float | None, str]:
        """Price one request only from the immutable batch snapshot."""
        provider_names = {
            "gemini": "Gemini",
            "gpt": "GPT",
            "qwen": "Qwen",
            "deepseek": "DeepSeek",
            "azure_gpt": "Azure GPT",
            "openrouter": "OpenRouter",
        }
        canonical_provider = provider_names.get(provider.casefold(), provider)
        normalized_model = normalize_pricing_model_id(canonical_provider, model_id)
        rates = batch["snapshot"].get("pricing_version", {}).get("rates", {}).get("llm", [])
        rate = next(
            (
                item
                for item in rates
                if str(item.get("provider", "")).casefold() == canonical_provider.casefold()
                and normalize_pricing_model_id(
                    canonical_provider,
                    str(item.get("model", "")),
                )
                == normalized_model
            ),
            None,
        )
        if rate is None:
            return None, "USD"
        uncached_tokens = max(0, input_tokens - cached_input_tokens)
        amount = (
            uncached_tokens * float(rate.get("input_per_1m") or 0)
            + cached_input_tokens
            * float(rate.get("cached_input_per_1m") or rate.get("input_per_1m") or 0)
            + (output_tokens + reasoning_tokens) * float(rate.get("output_per_1m") or 0)
        ) / 1_000_000
        return amount, str(rate.get("currency") or "USD")

    async def _run_pass_one(self, batch_id: str, conversations: list[dict[str, Any]]) -> None:
        """Screen dynamically packed groups while keeping conversations atomic."""
        batch = await self.store.get_batch(batch_id)
        assert batch is not None
        snapshot = batch["snapshot"]
        prompt = str(snapshot.get("pass_1_prompt", {}).get("content", PASS_ONE_SYSTEM_PROMPT))
        if "{{request_group_id}}" not in prompt or "{{conversations}}" not in prompt:
            await self._run_pass_one_legacy(batch_id, conversations, batch)
            return
        model_id = str(snapshot["pass_1_model"])
        provider = await self._model_provider(model_id)
        policy = evaluation_token_policy(provider, model_id.split("::", 1)[-1])
        existing = {
            str(row["conversation_id"]): row
            for row in await self.store.checkpoint_rows("evaluation_pass1_runs", batch_id)
        }
        prior_group_rows = await self.store.pass1_group_rows(batch_id)
        prior_groups = {str(row["group_id"]): row for row in prior_group_rows}
        pending_conversations = (
            conversations
            if prior_groups
            else [
                conversation
                for conversation in conversations
                if existing.get(str(conversation["conversation_id"]), {}).get("status")
                != "completed"
            ]
        )
        if not pending_conversations:
            return
        shared_payload = {
            "evaluation_context": snapshot.get("evaluation_context", EVALUATION_CONTEXT),
            "reference_dictionaries": snapshot.get(
                "reference_dictionaries", REFERENCE_DICTIONARIES
            ),
            "screening_strategy": snapshot["screening_strategy"],
            "scenario_tags": snapshot.get("scenario_tags", SCENARIO_TAGS),
        }
        units = [
            build_pass_one_unit(
                str(conversation["conversation_id"]),
                {
                    "conversation_id": str(conversation["conversation_id"]),
                    "conversation_history": conversation["events"],
                },
                sum(event.get("speaker") == "customer" for event in conversation["events"]),
            )
            for conversation in pending_conversations
        ]
        try:
            groups = pack_pass_one_units(
                batch_id=batch_id,
                units=units,
                system_prompt=prompt,
                shared_payload=shared_payload,
                policy=policy,
            )
        except ValueError as exc:
            if "Pass 1 token limit" in str(exc):
                raise EvaluationRequestTooLarge(
                    "One Pass 1 conversation exceeds the pre-dispatch input limit."
                ) from exc
            raise
        for group in groups:
            prior = prior_groups.get(group.group_id)
            if prior is not None:
                if (
                    str(prior["idempotency_key"]) != group.idempotency_key
                    or tuple(str(item) for item in prior["conversation_ids"])
                    != group.conversation_ids
                ):
                    raise EvaluationExecutionError("Frozen Pass 1 group membership changed")
                continue
            await self.store.checkpoint_pass1_group(
                batch_id=batch_id,
                group_id=group.group_id,
                idempotency_key=group.idempotency_key,
                conversation_ids=list(group.conversation_ids),
                estimated_input_tokens=group.estimated_input_tokens,
                reserved_output_tokens=group.reserved_output_tokens,
                status="pending",
                attempts=0,
            )
        planned_group_total = len(await self.store.pass1_group_rows(batch_id))
        await self.store.set_batch_state(
            batch_id,
            status="running",
            stage="pass_1",
            progress=20,
            snapshot_updates={
                "pass_1_plan": {
                    "unique_conversation_count": len(conversations),
                    "request_group_count": planned_group_total,
                    "thinking": "disabled",
                    "packing": "dynamic_conversation_atomic",
                }
            },
        )
        await self.store.refresh_execution_progress(
            batch_id,
            table="evaluation_pass1_runs",
            stage="pass_1",
            total=len(conversations),
            progress_start=20,
            progress_end=45,
        )

        by_conversation = {
            str(conversation["conversation_id"]): conversation for conversation in conversations
        }
        semaphore = asyncio.Semaphore(3)

        async def analyze_group(group: Any) -> None:
            prior = prior_groups.get(group.group_id)
            if prior is not None and prior.get("status") == "completed":
                return
            payload = build_pass_one_payload(group.group_id, group.units, shared_payload)
            retry_correction: str | None = None
            if prior is not None and int(prior.get("attempts") or 0) > 0:
                retry_correction = (
                    "The previous saved request group failed its structured-response contract. "
                    "Retry the same complete group and output only one complete JSON object."
                )
            prior_attempts = int(prior.get("attempts") or 0) if prior is not None else 0
            async with semaphore:
                for local_attempt in range(1, 4):
                    attempt = prior_attempts + local_attempt
                    started_at = time.perf_counter()
                    try:
                        result = await self._llm_json(
                            model_id,
                            prompt,
                            payload,
                            max_output_tokens=(
                                policy.max_output_tokens
                                if retry_correction is not None
                                else group.reserved_output_tokens
                            ),
                            batch_id=batch_id,
                            stage="pass_1",
                            item_key=group.group_id,
                            attempt=attempt,
                            disable_thinking=True,
                            system_only_payload=True,
                            user_instruction=retry_correction,
                            max_input_tokens=input_limit(policy),
                        )
                        indexed = self._validate_pass_one_group(
                            result,
                            group.group_id,
                            group.conversation_ids,
                            by_conversation,
                            str(snapshot["screening_strategy"]),
                        )
                        await self.store.checkpoint_pass1_group(
                            batch_id=batch_id,
                            group_id=group.group_id,
                            idempotency_key=group.idempotency_key,
                            conversation_ids=list(group.conversation_ids),
                            estimated_input_tokens=group.estimated_input_tokens,
                            reserved_output_tokens=group.reserved_output_tokens,
                            status="completed",
                            attempts=attempt,
                            conversation_results=indexed,
                        )
                        await self.store.refresh_execution_progress(
                            batch_id,
                            table="evaluation_pass1_runs",
                            stage="pass_1",
                            total=len(conversations),
                            progress_start=20,
                            progress_end=45,
                        )
                        await self.store.record_telemetry(
                            batch_id=batch_id,
                            stage="pass_1",
                            event="llm_request",
                            provider=provider,
                            outcome="completed",
                            attempt=attempt,
                            latency_ms=(time.perf_counter() - started_at) * 1000,
                        )
                        return
                    except EvaluationBudgetReached:
                        return
                    except Exception as exc:
                        retry_correction = _structured_retry_correction(exc)
                        await self.store.checkpoint_pass1_group(
                            batch_id=batch_id,
                            group_id=group.group_id,
                            idempotency_key=group.idempotency_key,
                            conversation_ids=list(group.conversation_ids),
                            estimated_input_tokens=group.estimated_input_tokens,
                            reserved_output_tokens=group.reserved_output_tokens,
                            status="pending",
                            attempts=attempt,
                            error=_safe_structured_error(exc),
                        )
                        await self.store.record_telemetry(
                            batch_id=batch_id,
                            stage="pass_1",
                            event=(
                                "schema_failure" if isinstance(exc, ValueError) else "llm_request"
                            ),
                            provider=provider,
                            outcome="failed",
                            attempt=attempt,
                            latency_ms=(time.perf_counter() - started_at) * 1000,
                        )
                        if local_attempt == 3:
                            await self.store.checkpoint_pass1_group(
                                batch_id=batch_id,
                                group_id=group.group_id,
                                idempotency_key=group.idempotency_key,
                                conversation_ids=list(group.conversation_ids),
                                estimated_input_tokens=group.estimated_input_tokens,
                                reserved_output_tokens=group.reserved_output_tokens,
                                status="failed",
                                attempts=attempt,
                                error=_safe_structured_error(exc),
                            )
                            await self.store.refresh_execution_progress(
                                batch_id,
                                table="evaluation_pass1_runs",
                                stage="pass_1",
                                total=len(conversations),
                                progress_start=20,
                                progress_end=45,
                            )
                        else:
                            await asyncio.sleep(float(local_attempt))

        await self.store.record_telemetry(
            batch_id=batch_id,
            stage="pass_1",
            event="queue_depth",
            provider=provider,
            outcome="observed",
            queue_depth=len(groups),
        )
        await asyncio.gather(*(analyze_group(group) for group in groups))
        final_groups = await self.store.pass1_group_rows(batch_id)
        updated_batch = await self.store.get_batch(batch_id)
        assert updated_batch is not None
        await self.store.set_batch_state(
            batch_id,
            status="running",
            stage="pass_1",
            progress=int(updated_batch["progress"]),
            snapshot_updates={
                "pass_1_request_status": {
                    "completed": sum(row["status"] == "completed" for row in final_groups),
                    "failed": sum(row["status"] == "failed" for row in final_groups),
                    "total": len(final_groups),
                }
            },
        )

    async def _run_pass_one_legacy(
        self,
        batch_id: str,
        conversations: list[dict[str, Any]],
        batch: dict[str, Any],
    ) -> None:
        """Resume an old immutable single-conversation Pass 1 snapshot safely."""
        snapshot = batch["snapshot"]
        existing = {
            str(row["conversation_id"]): row
            for row in await self.store.checkpoint_rows("evaluation_pass1_runs", batch_id)
        }
        semaphore = asyncio.Semaphore(3)
        await self.store.refresh_execution_progress(
            batch_id,
            table="evaluation_pass1_runs",
            stage="pass_1",
            total=len(conversations),
            progress_start=20,
            progress_end=45,
        )

        async def analyze(conversation: dict[str, Any]) -> None:
            conversation_id = str(conversation["conversation_id"])
            if existing.get(conversation_id, {}).get("status") == "completed":
                return
            payload = {
                "conversation_history": conversation["events"],
                "evaluation_context": snapshot.get("evaluation_context", EVALUATION_CONTEXT),
                "reference_dictionaries": snapshot.get(
                    "reference_dictionaries", REFERENCE_DICTIONARIES
                ),
                "screening_strategy": snapshot["screening_strategy"],
                "scenario_tags": snapshot.get("scenario_tags", SCENARIO_TAGS),
            }
            retry_correction: str | None = None
            async with semaphore:
                for attempt in range(1, 4):
                    started_at = time.perf_counter()
                    try:
                        attempt_payload = dict(payload)
                        if retry_correction is not None:
                            attempt_payload["retry_correction"] = retry_correction
                        result = await self._llm_json(
                            str(snapshot["pass_1_model"]),
                            str(snapshot["pass_1_prompt"]["content"]),
                            attempt_payload,
                            batch_id=batch_id,
                            stage="pass_1",
                            item_key=conversation_id,
                            attempt=attempt,
                        )
                        self._validate_pass_one(
                            result,
                            conversation,
                            str(snapshot["screening_strategy"]),
                        )
                        await self.store.checkpoint_result(
                            "evaluation_pass1_runs",
                            (batch_id, conversation_id),
                            status="completed",
                            attempts=attempt,
                            result=result,
                        )
                        await self.store.refresh_execution_progress(
                            batch_id,
                            table="evaluation_pass1_runs",
                            stage="pass_1",
                            total=len(conversations),
                            progress_start=20,
                            progress_end=45,
                        )
                        await self.store.record_telemetry(
                            batch_id=batch_id,
                            stage="pass_1",
                            event="llm_request",
                            outcome="completed",
                            attempt=attempt,
                            latency_ms=(time.perf_counter() - started_at) * 1000,
                        )
                        return
                    except EvaluationBudgetReached:
                        return
                    except Exception as exc:
                        retry_correction = _structured_retry_correction(exc)
                        await self.store.record_telemetry(
                            batch_id=batch_id,
                            stage="pass_1",
                            event=(
                                "schema_failure" if isinstance(exc, ValueError) else "llm_request"
                            ),
                            outcome="failed",
                            attempt=attempt,
                            latency_ms=(time.perf_counter() - started_at) * 1000,
                        )
                        if attempt == 3:
                            await self.store.checkpoint_result(
                                "evaluation_pass1_runs",
                                (batch_id, conversation_id),
                                status="failed",
                                attempts=attempt,
                                error=_safe_structured_error(exc),
                            )
                            await self.store.refresh_execution_progress(
                                batch_id,
                                table="evaluation_pass1_runs",
                                stage="pass_1",
                                total=len(conversations),
                                progress_start=20,
                                progress_end=45,
                            )
                        else:
                            await asyncio.sleep(float(attempt))

        await self.store.record_telemetry(
            batch_id=batch_id,
            stage="pass_1",
            event="queue_depth",
            outcome="observed",
            queue_depth=len(conversations),
        )
        await asyncio.gather(*(analyze(conversation) for conversation in conversations))

    @classmethod
    def _validate_pass_one_group(
        cls,
        result: dict[str, Any],
        expected_group_id: str,
        conversation_ids: tuple[str, ...],
        conversations: dict[str, dict[str, Any]],
        screening_strategy: str,
    ) -> dict[str, dict[str, Any]]:
        """Require one complete, valid result for every conversation in a group."""
        if result.get("request_group_id") != expected_group_id:
            raise ValueError("Pass 1 returned the wrong request group")
        rows = result.get("results")
        if not isinstance(rows, list):
            raise ValueError("Pass 1 group omitted results")
        indexed: dict[str, dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("Pass 1 conversation result must be an object")
            conversation_id = str(row.get("conversation_id") or "")
            if conversation_id in indexed:
                raise ValueError("Pass 1 group duplicated a conversation")
            if conversation_id not in conversation_ids:
                raise ValueError("Pass 1 group returned an unknown conversation")
            cls._validate_pass_one(
                row,
                conversations[conversation_id],
                screening_strategy,
            )
            indexed[conversation_id] = row
        if set(indexed) != set(conversation_ids):
            raise ValueError("Pass 1 group omitted a conversation")
        return indexed

    @staticmethod
    def _validate_pass_one(
        result: dict[str, Any],
        conversation: dict[str, Any],
        screening_strategy: str,
    ) -> None:
        """Reject incomplete coverage, duplicates, and out-of-scope priorities."""
        expected = {
            str(event["event_id"])
            for event in conversation["events"]
            if event["speaker"] == "customer"
        }
        rows = result.get("event_results")
        if not isinstance(rows, list):
            raise ValueError("Pass 1 omitted event_results")
        actual_rows = [str(row.get("event_id")) for row in rows if isinstance(row, dict)]
        if len(actual_rows) != len(set(actual_rows)) or set(actual_rows) != expected:
            raise ValueError("Pass 1 did not cover every customer event exactly once")
        event_decisions: dict[str, str] = {}
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("Pass 1 event result must be an object")
            event_id = str(row.get("event_id"))
            decision = str(row.get("decision"))
            if decision not in {"candidate", "pass", "data_issue"}:
                raise ValueError("Pass 1 returned an invalid event decision")
            if not str(row.get("reason") or "").strip():
                raise ValueError("Pass 1 event result requires a reason")
            event_decisions[event_id] = decision
        allowed_priorities = {
            "focused": {"P1"},
            "standard": {"P1", "P2"},
            "comprehensive": {"P1", "P2", "P3"},
        }.get(screening_strategy)
        if allowed_priorities is None:
            raise ValueError("Unknown screening strategy")
        candidate_events: set[str] = set()
        for issue in result.get("issues", []):
            if not isinstance(issue, dict) or issue.get("priority") not in allowed_priorities:
                raise ValueError("Pass 1 returned a priority outside the screening strategy")
            for target in issue.get("target_events", []):
                if not isinstance(target, dict) or target.get("decision") != "candidate":
                    raise ValueError("Pass 1 issue contains an invalid target")
                event_id = str(target.get("event_id"))
                if event_id not in expected or event_id in candidate_events:
                    raise ValueError("Pass 1 returned an unknown or duplicate candidate event")
                candidate_events.add(event_id)
        declared_candidates = {
            event_id for event_id, decision in event_decisions.items() if decision == "candidate"
        }
        if candidate_events != declared_candidates:
            raise ValueError("Pass 1 candidate issues and event results disagree")

    @staticmethod
    def _candidates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Flatten valid first-pass issues into event-scoped candidate cases."""
        candidates: list[dict[str, Any]] = []
        for row in rows:
            result = row.get("result") or {}
            for issue in result.get("issues", []):
                for target in issue.get("target_events", []):
                    if target.get("decision") != "candidate":
                        continue
                    candidates.append(
                        {
                            "conversation_id": row["conversation_id"],
                            "issue_id": issue.get("issue_id"),
                            "title": issue.get("title"),
                            "priority": issue.get("priority"),
                            "symptom": issue.get("symptom"),
                            "scenario_tag_candidates": issue.get("scenario_tag_candidates", []),
                            "event_id": target.get("event_id"),
                            "verification_question": target.get("verification_question"),
                        }
                    )
        return candidates

    @staticmethod
    def _good_pool(
        rows: list[dict[str, Any]],
        conversations: list[dict[str, Any]],
        candidate_conversation_ids: set[str],
    ) -> list[dict[str, Any]]:
        """Build a deterministic conversation-round-robin pool of Pass 1 controls."""
        valid_events = {
            str(conversation["conversation_id"]): {
                str(event["event_id"])
                for event in conversation["events"]
                if event["speaker"] == "customer" and str(event.get("text") or "").strip()
            }
            for conversation in conversations
        }
        by_conversation: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            conversation_id = str(row["conversation_id"])
            if conversation_id not in candidate_conversation_ids:
                continue
            for event_result in (row.get("result") or {}).get("event_results", []):
                event_id = str(event_result.get("event_id"))
                if event_result.get("decision") != "pass" or event_id not in valid_events.get(
                    conversation_id, set()
                ):
                    continue
                by_conversation.setdefault(conversation_id, []).append(
                    {
                        "conversation_id": conversation_id,
                        "issue_id": f"GOOD-{event_id}",
                        "title": "Additional Good control",
                        "priority": "control",
                        "symptom": str(event_result.get("reason") or ""),
                        "scenario_tag_candidates": [],
                        "event_id": event_id,
                        "verification_question": (
                            "Does the audio evidence support the historical transcript?"
                        ),
                        "origin": "additional_good_pool",
                    }
                )
        for events in by_conversation.values():
            events.sort(key=lambda item: str(item["event_id"]))
        ordered: list[dict[str, Any]] = []
        conversation_ids = sorted(by_conversation)
        while any(by_conversation.values()):
            for conversation_id in conversation_ids:
                events = by_conversation[conversation_id]
                if events:
                    ordered.append(events.pop(0))
        return ordered

    @staticmethod
    def _validate_event_alignment_group(
        result: dict[str, Any],
        *,
        expected_group_id: str,
        units_by_conversation: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """Validate complete real-ID mappings, order and customer-speaker consistency."""
        if result.get("request_group_id") != expected_group_id:
            raise ValueError("Event Aligner returned the wrong request group")
        rows = result.get("results")
        if not isinstance(rows, list):
            raise ValueError("Event Aligner omitted results")
        indexed: dict[str, dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("Event Aligner conversation result must be an object")
            conversation_id = str(row.get("conversation_id") or "")
            if conversation_id not in units_by_conversation or conversation_id in indexed:
                raise ValueError("Event Aligner returned an unknown or duplicate conversation")
            expected = units_by_conversation[conversation_id]
            target_ids = [str(item["event_id"]) for item in expected["target_events"]]
            event_rows = row.get("events")
            if not isinstance(event_rows, list):
                raise ValueError("Event Aligner omitted event mappings")
            mapped_events: dict[str, dict[str, Any]] = {}
            turn_owners: set[str] = set()
            catalog = expected["turn_lookup"]
            providers = set(expected["providers"])
            available_speakers: dict[str, set[str]] = {provider: set() for provider in providers}
            for turn in catalog.values():
                available_speakers[str(turn["provider"])].add(str(turn["speaker"]))
            role_rows = row.get("speaker_roles")
            if not isinstance(role_rows, list):
                raise ValueError("Event Aligner omitted provider speaker roles")
            customer_speakers: dict[str, str] = {}
            for role_row in role_rows:
                if not isinstance(role_row, dict):
                    raise ValueError("Event Aligner speaker role must be an object")
                provider = str(role_row.get("provider") or "")
                customer_speaker = str(role_row.get("customer_speaker") or "")
                robot_speakers = role_row.get("robot_speakers")
                if provider not in providers or provider in customer_speakers:
                    raise ValueError("Event Aligner returned unknown or duplicate speaker roles")
                if not isinstance(robot_speakers, list) or not robot_speakers:
                    raise ValueError("Event Aligner omitted robot speaker evidence")
                normalized_robot = {str(speaker) for speaker in robot_speakers if str(speaker)}
                if (
                    customer_speaker not in available_speakers[provider]
                    or not normalized_robot
                    or not normalized_robot.issubset(available_speakers[provider])
                    or customer_speaker in normalized_robot
                ):
                    raise ValueError("Event Aligner returned invalid customer speaker ownership")
                customer_speakers[provider] = customer_speaker
            if set(customer_speakers) != providers:
                raise ValueError("Event Aligner omitted provider speaker roles")
            for event_row in event_rows:
                if not isinstance(event_row, dict):
                    raise ValueError("Event Aligner event mapping must be an object")
                event_id = str(event_row.get("event_id") or "")
                if event_id not in target_ids or event_id in mapped_events:
                    raise ValueError("Event Aligner returned an unknown or duplicate event")
                mappings = event_row.get("providers")
                if not isinstance(mappings, list):
                    raise ValueError("Event Aligner omitted provider mappings")
                seen_providers: set[str] = set()
                mapped_count = 0
                wrong_role = False
                for mapping in mappings:
                    if not isinstance(mapping, dict):
                        raise ValueError("Event Aligner provider mapping must be an object")
                    provider = str(mapping.get("provider") or "")
                    status = str(mapping.get("status") or "")
                    turn_id = mapping.get("turn_id")
                    if provider not in providers or provider in seen_providers:
                        raise ValueError("Event Aligner returned an unknown or duplicate provider")
                    seen_providers.add(provider)
                    if status not in {"mapped", "missing", "ambiguous"}:
                        raise ValueError("Event Aligner returned an invalid mapping status")
                    if status != "mapped":
                        if turn_id is not None:
                            raise ValueError(
                                "Unmapped Event Aligner result must not include turn_id"
                            )
                        continue
                    selected = catalog.get(str(turn_id or ""))
                    if selected is None or selected["provider"] != provider:
                        raise ValueError("Event Aligner selected an unknown provider turn_id")
                    if str(turn_id) in turn_owners:
                        raise ValueError("Event Aligner reused one turn_id for multiple events")
                    turn_owners.add(str(turn_id))
                    if str(selected["speaker"]) != customer_speakers[provider]:
                        wrong_role = True
                    mapped_count += 1
                if seen_providers != providers:
                    raise ValueError("Event Aligner omitted a provider")
                mapped_events[event_id] = {
                    **event_row,
                    "conversation_id": conversation_id,
                    "alignment_error": (
                        "selected_non_customer_speaker"
                        if wrong_role
                        else "fewer_than_two_providers"
                        if mapped_count < 2
                        else None
                    ),
                }
            if set(mapped_events) != set(target_ids):
                raise ValueError("Event Aligner omitted a target event")
            provider_positions: dict[str, list[int]] = {}
            for event_id in target_ids:
                if mapped_events[event_id]["alignment_error"] is not None:
                    continue
                for mapping in mapped_events[event_id]["providers"]:
                    if mapping["status"] != "mapped":
                        continue
                    selected = catalog[str(mapping["turn_id"])]
                    provider = str(mapping["provider"])
                    provider_positions.setdefault(provider, []).append(int(selected["turn_index"]))
            if any(positions != sorted(positions) for positions in provider_positions.values()):
                raise ValueError("Event Aligner mappings violate conversation order")
            indexed[conversation_id] = {
                "conversation_id": conversation_id,
                "speaker_roles": role_rows,
                "events": [mapped_events[event_id] for event_id in target_ids],
            }
        if set(indexed) != set(units_by_conversation):
            raise ValueError("Event Aligner omitted a conversation")
        return indexed

    async def _run_event_alignment(
        self,
        batch_id: str,
        batch: dict[str, Any],
        case_keys: list[tuple[str, str]],
        context_by_conversation: dict[str, list[dict[str, Any]]],
    ) -> dict[tuple[str, str], dict[str, Any]]:
        """Map all target events with batch-first, conversation-atomic LLM requests."""
        targets_by_conversation: dict[str, list[str]] = {}
        for conversation_id, event_id in case_keys:
            targets_by_conversation.setdefault(conversation_id, []).append(event_id)
        unit_payloads: dict[str, dict[str, Any]] = {}
        units = []
        for conversation_id, target_ids in sorted(targets_by_conversation.items()):
            conversation = await self.store.get_conversation(conversation_id)
            if conversation is None:
                raise EvaluationExecutionError("Event Aligner conversation is unavailable")
            providers, lookup = build_turn_catalog(
                conversation_id, context_by_conversation.get(conversation_id, [])
            )
            target_events = [
                {"event_id": str(event["event_id"]), "text": str(event.get("text") or "")}
                for event in conversation["events"]
                if str(event.get("event_id")) in set(target_ids)
                and event.get("speaker") == "customer"
            ]
            payload = {
                "conversation_id": conversation_id,
                "conversation_history": conversation["events"],
                "target_events": target_events,
                "full_call_asr": providers,
            }
            unit_payloads[conversation_id] = {
                **payload,
                "turn_lookup": lookup,
                "providers": [str(item["provider"]) for item in providers],
            }
            if len(providers) < 2 or len(target_events) != len(target_ids):
                await self.store.checkpoint_result(
                    "evaluation_event_alignment_runs",
                    (batch_id, conversation_id),
                    status="failed",
                    attempts=0,
                    error=_safe_structured_error(
                        ValueError(
                            "Event Aligner requires two usable providers and every target event"
                        )
                    ),
                )
                continue
            units.append(
                build_event_alignment_unit(
                    conversation_id,
                    payload,
                    len(target_events),
                    len(providers),
                )
            )
        model_id = str(batch["snapshot"]["pass_1_model"])
        provider = await self._model_provider(model_id)
        policy = model_token_policy(provider, model_id.split("::", 1)[-1])
        groups = pack_event_alignment_units(
            batch_id=batch_id,
            units=units,
            system_prompt=EVENT_ALIGNER_SYSTEM_PROMPT,
            policy=policy,
        )
        prior_rows = await self.store.event_alignment_group_rows(batch_id)
        prior_groups = {str(row["group_id"]): row for row in prior_rows}
        for group in groups:
            prior = prior_groups.get(group.group_id)
            if prior is not None:
                if (
                    str(prior["idempotency_key"]) != group.idempotency_key
                    or tuple(str(value) for value in prior["conversation_ids"])
                    != group.conversation_ids
                ):
                    raise EvaluationExecutionError("Frozen Event Aligner group membership changed")
                continue
            await self.store.checkpoint_event_alignment_group(
                batch_id=batch_id,
                group_id=group.group_id,
                idempotency_key=group.idempotency_key,
                conversation_ids=list(group.conversation_ids),
                estimated_input_tokens=group.estimated_input_tokens,
                reserved_output_tokens=group.reserved_output_tokens,
                status="pending",
                attempts=0,
            )

        semaphore = asyncio.Semaphore(3)

        async def align_group(group: Any) -> None:
            prior = prior_groups.get(group.group_id)
            if prior is not None and prior.get("status") == "completed":
                return
            prior_attempts = int(prior.get("attempts") or 0) if prior is not None else 0
            payload = {
                "request_group_id": group.group_id,
                "conversations": [unit.payload for unit in group.units],
            }
            async with semaphore:
                for local_attempt in range(1, 4):
                    attempt = prior_attempts + local_attempt
                    try:
                        result = await self._llm_json(
                            model_id,
                            EVENT_ALIGNER_SYSTEM_PROMPT,
                            payload,
                            max_output_tokens=group.reserved_output_tokens,
                            batch_id=batch_id,
                            stage="event_alignment",
                            item_key=group.group_id,
                            attempt=attempt,
                            disable_thinking=True,
                        )
                        expected = {
                            conversation_id: unit_payloads[conversation_id]
                            for conversation_id in group.conversation_ids
                        }
                        indexed = self._validate_event_alignment_group(
                            result,
                            expected_group_id=group.group_id,
                            units_by_conversation=expected,
                        )
                        await self.store.checkpoint_event_alignment_group(
                            batch_id=batch_id,
                            group_id=group.group_id,
                            idempotency_key=group.idempotency_key,
                            conversation_ids=list(group.conversation_ids),
                            estimated_input_tokens=group.estimated_input_tokens,
                            reserved_output_tokens=group.reserved_output_tokens,
                            status="completed",
                            attempts=attempt,
                            conversation_results=indexed,
                        )
                        return
                    except EvaluationBudgetReached:
                        return
                    except Exception as exc:
                        terminal = local_attempt == 3
                        await self.store.checkpoint_event_alignment_group(
                            batch_id=batch_id,
                            group_id=group.group_id,
                            idempotency_key=group.idempotency_key,
                            conversation_ids=list(group.conversation_ids),
                            estimated_input_tokens=group.estimated_input_tokens,
                            reserved_output_tokens=group.reserved_output_tokens,
                            status="failed" if terminal else "pending",
                            attempts=attempt,
                            error=_safe_structured_error(exc),
                        )
                        if not terminal:
                            await asyncio.sleep(float(local_attempt))

        await asyncio.gather(*(align_group(group) for group in groups))
        rows = await self.store.checkpoint_rows("evaluation_event_alignment_runs", batch_id)
        mappings: dict[tuple[str, str], dict[str, Any]] = {}
        for row in rows:
            if row.get("status") != "completed" or not isinstance(row.get("result"), dict):
                continue
            for event in row["result"].get("events") or []:
                if isinstance(event, dict):
                    mappings[(str(row["conversation_id"]), str(event.get("event_id")))] = event
        return mappings

    async def _run_asr(
        self, batch_id: str, batch: dict[str, Any], candidates: list[dict[str, Any]]
    ) -> None:
        """Transcribe each full call once and project mapped turns into Case evidence."""
        case_keys = sorted(
            {(str(item["conversation_id"]), str(item["event_id"])) for item in candidates}
        )
        conversation_ids = sorted({conversation_id for conversation_id, _ in case_keys})
        existing_context = {
            (row["provider"], row["conversation_id"]): row
            for row in await self.store.checkpoint_rows("evaluation_asr_runs", batch_id)
        }
        existing = {
            (row["provider"], row["conversation_id"], row["event_id"]): row
            for row in await self.store.checkpoint_rows("evaluation_case_asr_runs", batch_id)
        }
        semaphore = asyncio.Semaphore(3)
        provider_semaphores = {
            provider: asyncio.Semaphore(_ASR_PROVIDER_CONCURRENCY[provider])
            for provider in batch["providers"]
        }
        context_jobs = len(batch["providers"]) * len(conversation_ids)
        await self.store.refresh_execution_progress(
            batch_id,
            table="evaluation_asr_runs",
            stage="evaluation_asr",
            total=context_jobs,
            progress_start=45,
            progress_end=55,
        )

        async def transcribe_context(provider: str, conversation_id: str) -> None:
            prior = existing_context.get((provider, conversation_id), {})
            if prior.get("status") == "completed" and _has_usable_diarized_timeline(
                prior.get("result")
            ):
                return
            conversation = await self.store.get_conversation(conversation_id)
            path = self.store.conversation_audio_path(conversation_id)
            if conversation is None or path is None:
                await self.store.checkpoint_result(
                    "evaluation_asr_runs",
                    (batch_id, provider, conversation_id),
                    status="failed",
                    attempts=0,
                    error=_asr_error(provider, FileNotFoundError("Full-call audio is unavailable")),
                )
                return
            duration = float((conversation.get("record_audio") or {}).get("duration_s") or 0)
            if duration <= 0:
                await self.store.checkpoint_result(
                    "evaluation_asr_runs",
                    (batch_id, provider, conversation_id),
                    status="failed",
                    attempts=0,
                    error=_asr_error(provider, ValueError("Full-call duration is unavailable")),
                )
                return
            rate = self._frozen_asr_rate(batch, provider)
            async with semaphore, provider_semaphores[provider]:
                previous_attempts = int(prior.get("attempts") or 0)
                for attempt in range(previous_attempts + 1, previous_attempts + 4):
                    reserve_key = (
                        f"reserve:{batch_id}:asr-context-speaker-v1:"
                        f"{provider}:{conversation_id}:{attempt}"
                    )
                    try:
                        if not await self.store.reserve_budget(
                            idempotency_key=reserve_key,
                            batch_id=batch_id,
                            estimated_usd=(duration / 3600) * rate,
                        ):
                            raise EvaluationBudgetReached(
                                "Batch budget reached before the next ASR context call"
                            )
                        result, remote_id = await self._transcribe(
                            batch_id,
                            provider,
                            path,
                            conversation_id,
                            attempt,
                        )
                        result["scope"] = "full_call_context"
                        result["diarization_contract"] = "speaker_timestamps_v1"
                        await self.store.record_cost_entry(
                            idempotency_key=(
                                f"{batch_id}:asr-context-speaker-v1:"
                                f"{provider}:{conversation_id}:{attempt}"
                            ),
                            batch_id=batch_id,
                            category="asr",
                            provider=provider,
                            stage="evaluation_asr_context",
                            audio_seconds=duration,
                            estimated_cost=(duration / 3600) * rate,
                            reservation_key=reserve_key,
                        )
                        if not _has_usable_diarized_timeline(result):
                            raise EvaluationExecutionError(
                                "Provider returned no usable diarized full-call speaker timeline"
                            )
                        await self.store.checkpoint_result(
                            "evaluation_asr_runs",
                            (batch_id, provider, conversation_id),
                            status="completed",
                            attempts=attempt,
                            result=result,
                            remote_job_id=remote_id,
                        )
                        await self.store.refresh_execution_progress(
                            batch_id,
                            table="evaluation_asr_runs",
                            stage="evaluation_asr",
                            total=context_jobs,
                            progress_start=45,
                            progress_end=55,
                        )
                        return
                    except EvaluationBudgetReached:
                        return
                    except Exception as exc:
                        await self.store.release_budget(reserve_key)
                        if attempt == previous_attempts + 3:
                            await self.store.checkpoint_result(
                                "evaluation_asr_runs",
                                (batch_id, provider, conversation_id),
                                status="failed",
                                attempts=attempt,
                                error=_asr_error(provider, exc),
                            )
                        else:
                            await asyncio.sleep(float(attempt * 2))

        await asyncio.gather(
            *(
                transcribe_context(provider, conversation_id)
                for provider in batch["providers"]
                for conversation_id in conversation_ids
            )
        )
        context_rows = await self.store.checkpoint_rows("evaluation_asr_runs", batch_id)
        context_by_conversation: dict[str, list[dict[str, Any]]] = {}
        for row in context_rows:
            result = row.get("result")
            if row.get("status") != "completed" or not _has_usable_diarized_timeline(result):
                continue
            assert isinstance(result, dict)
            context_by_conversation.setdefault(str(row["conversation_id"]), []).append(
                {"provider": str(row["provider"]), **result}
            )
        event_mappings = await self._run_event_alignment(
            batch_id,
            batch,
            case_keys,
            context_by_conversation,
        )
        prepared_clips: dict[tuple[str, str], tuple[Path, dict[str, Any]]] = {}
        clip_errors: dict[tuple[str, str], Exception] = {}
        for conversation_id, event_id in case_keys:
            try:
                event_mapping = event_mappings.get((conversation_id, event_id))
                if event_mapping is None:
                    raise ValueError("Event Aligner produced no validated mapping for this event")
                if event_mapping.get("alignment_error"):
                    raise ValueError(
                        "Event Aligner could not validate this event: "
                        f"{event_mapping['alignment_error']}"
                    )
                prepared_clips[
                    (conversation_id, event_id)
                ] = await self.store.prepare_case_asr_clip(
                    batch_id,
                    conversation_id,
                    event_id,
                    context_by_conversation.get(conversation_id, []),
                    event_mapping,
                )
            except (FileNotFoundError, LookupError, OSError, RuntimeError, ValueError) as exc:
                clip_errors[(conversation_id, event_id)] = exc

        turn_lookups = {
            conversation_id: build_turn_catalog(
                conversation_id,
                context_by_conversation.get(conversation_id, []),
            )[1]
            for conversation_id in conversation_ids
        }

        async def project(provider: str, conversation_id: str, event_id: str) -> None:
            """Persist one mapped full-call turn without another provider dispatch."""
            clip_error = clip_errors.get((conversation_id, event_id))
            if clip_error is not None:
                await self.store.checkpoint_result(
                    "evaluation_case_asr_runs",
                    (batch_id, provider, conversation_id, event_id),
                    status="failed",
                    attempts=0,
                    error=_asr_error(provider, clip_error),
                )
                return
            _path, clip_trace = prepared_clips[(conversation_id, event_id)]
            event_mapping = event_mappings[(conversation_id, event_id)]
            provider_mapping = next(
                (
                    row
                    for row in event_mapping.get("providers") or []
                    if isinstance(row, dict) and str(row.get("provider") or "") == provider
                ),
                None,
            )
            if not provider_mapping or provider_mapping.get("status") != "mapped":
                await self.store.checkpoint_result(
                    "evaluation_case_asr_runs",
                    (batch_id, provider, conversation_id, event_id),
                    status="failed",
                    attempts=0,
                    error=_asr_error(
                        provider,
                        ValueError("Event Aligner did not map this provider to the target event"),
                    ),
                )
                return
            turn_id = str(provider_mapping.get("turn_id") or "")
            turn = turn_lookups.get(conversation_id, {}).get(turn_id)
            if turn is None or str(turn.get("provider") or "") != provider:
                await self.store.checkpoint_result(
                    "evaluation_case_asr_runs",
                    (batch_id, provider, conversation_id, event_id),
                    status="failed",
                    attempts=0,
                    error=_asr_error(
                        provider,
                        ValueError("Mapped full-call provider turn is unavailable"),
                    ),
                )
                return
            prior = existing.get((provider, conversation_id, event_id), {})
            prior_result = prior.get("result") or {}
            if (
                prior.get("status") == "completed"
                and prior_result.get("scope") == "full_call_turn_projection"
                and str(prior_result.get("source_turn_id") or "") == turn_id
                and prior_result.get("source_clip") == clip_trace
            ):
                return
            result = {
                "event_id": event_id,
                "scope": "full_call_turn_projection",
                "source_turn_id": turn_id,
                "source_job_scope": "full_call_context",
                "text": str(turn.get("text") or ""),
                "segments": [
                    {
                        "segment_id": turn_id,
                        "start": float(turn["start_s"]),
                        "end": float(turn["end_s"]),
                        "speaker": str(turn.get("speaker") or ""),
                        "text": str(turn.get("text") or ""),
                    }
                ],
                "source_clip": clip_trace,
            }
            await self.store.checkpoint_result(
                "evaluation_case_asr_runs",
                (batch_id, provider, conversation_id, event_id),
                status="completed",
                attempts=0,
                result=result,
                remote_job_id=None,
            )

        await self.store.record_telemetry(
            batch_id=batch_id,
            stage="evaluation_asr",
            event="queue_depth",
            outcome="observed",
            queue_depth=context_jobs,
        )
        await asyncio.gather(
            *(
                project(provider, conversation_id, event_id)
                for provider in batch["providers"]
                for conversation_id, event_id in case_keys
            )
        )
        await self.store.refresh_execution_progress(
            batch_id,
            table="evaluation_asr_runs",
            stage="evaluation_asr",
            total=context_jobs,
            progress_start=55,
            progress_end=75,
        )

    @staticmethod
    def _frozen_asr_rate(batch: dict[str, Any], provider: str) -> float:
        """Resolve one provider rate from the immutable batch price snapshot."""
        rates = batch["snapshot"].get("pricing_version", {}).get("rates", {}).get("asr", [])
        for rate in rates:
            if str(rate.get("provider", "")).casefold() == provider.casefold():
                return float(rate.get("unit_price") or 0)
        return _ASR_HOURLY_USD[provider]

    async def _transcribe(
        self,
        batch_id: str,
        provider: str,
        path: Path,
        conversation_id: str,
        attempt: int,
        *,
        event_id: str | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        """Dispatch one audio file to the selected evaluation ASR."""
        if not path.is_file():
            raise FileNotFoundError(path.name)
        base_url, key = await self._key(provider)
        segment_scope = conversation_id if event_id is None else f"{conversation_id}:{event_id}"
        if provider == "elevenlabs":
            result, remote_id = await self._elevenlabs(
                base_url,
                key,
                path,
                segment_scope,
                correlation_id=(
                    f"evaluation:{batch_id}:{conversation_id}:{event_id or 'full'}:{attempt}"
                ),
            )
        elif provider == "speechmatics":
            result, remote_id = await self._speechmatics(base_url, key, path, segment_scope)
        elif provider == "soniox":
            result, remote_id = await self._soniox(base_url, key, path, segment_scope)
        else:
            raise EvaluationExecutionError(f"Unsupported ASR provider: {provider}")
        normalized = ASRResult(
            provider=provider,
            conversation_id=conversation_id,
            **result,
        )
        if not normalized.text.strip():
            raise EvaluationExecutionError(
                "Provider returned no transcript for the submitted audio"
            )
        return normalized.model_dump(exclude_none=True), remote_id

    async def _elevenlabs(
        self,
        base_url: str,
        key: str,
        path: Path,
        conversation_id: str,
        *,
        correlation_id: str,
    ) -> tuple[dict[str, Any], str | None]:
        """Use signed Scribe webhooks when configured, otherwise use synchronous fallback."""
        webhook_id = os.getenv("ELEVENLABS_STT_WEBHOOK_ID", "").strip()
        webhook_secret = os.getenv("ELEVENLABS_STT_WEBHOOK_SECRET", "")
        if webhook_id and webhook_secret:
            existing = await self.store.get_elevenlabs_job(correlation_id)
            request_id = str(existing["request_id"]) if existing else ""
            if existing is None:
                async with httpx.AsyncClient(timeout=300) as client:
                    with path.open("rb") as audio:
                        response = await client.post(
                            base_url.rstrip("/") + "/v1/speech-to-text",
                            headers={"xi-api-key": key},
                            files={"file": (path.name, audio, _audio_media_type(path))},
                            data={
                                "model_id": "scribe_v2",
                                "diarize": "true",
                                "webhook": "true",
                                "webhook_id": webhook_id,
                                "webhook_metadata": json.dumps(
                                    {"correlation_id": correlation_id},
                                    separators=(",", ":"),
                                ),
                            },
                        )
                    response.raise_for_status()
                    request_id = str(response.json()["request_id"])
                await self.store.register_elevenlabs_job(request_id, correlation_id)
            for _ in range(300):
                job = await self.store.get_elevenlabs_job(correlation_id)
                if job and job["status"] == "completed":
                    return self._elevenlabs_result(job["result"] or {}, conversation_id), request_id
                if job and job["status"] == "failed":
                    raise EvaluationExecutionError("ElevenLabs webhook job failed")
                await asyncio.sleep(1)
            raise TimeoutError("ElevenLabs webhook result did not arrive")

        async with httpx.AsyncClient(timeout=300) as client:
            with path.open("rb") as audio:
                response = await client.post(
                    base_url.rstrip("/") + "/v1/speech-to-text",
                    headers={"xi-api-key": key},
                    files={"file": (path.name, audio, _audio_media_type(path))},
                    data={"model_id": "scribe_v2", "diarize": "true"},
                )
            response.raise_for_status()
            payload = response.json()
        return self._elevenlabs_result(payload, conversation_id), None

    @staticmethod
    def _elevenlabs_result(payload: dict[str, Any], conversation_id: str) -> dict[str, Any]:
        """Normalize synchronous and webhook Scribe payloads identically."""
        segments = [
            {
                "segment_id": _segment_id(conversation_id, "elevenlabs", index),
                "start": word.get("start"),
                "end": word.get("end"),
                "speaker": word.get("speaker_id"),
                "text": word.get("text"),
            }
            for index, word in enumerate(payload.get("words", []))
            if word.get("type") == "word"
        ]
        return {"text": payload.get("text", ""), "segments": segments}

    async def _speechmatics(
        self,
        base_url: str,
        key: str,
        path: Path,
        conversation_id: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> tuple[dict[str, Any], str]:
        """Submit, poll, retrieve, and clean up one Speechmatics batch job."""
        headers = {"Authorization": f"Bearer {key}"}
        config = {
            "type": "transcription",
            "transcription_config": {
                "language": "ar",
                "operating_point": "enhanced",
                "diarization": "speaker",
            },
        }
        job_id: str | None = None
        cleanup_status = "not_required"
        async with httpx.AsyncClient(timeout=300, transport=transport) as client:
            try:
                with path.open("rb") as audio:
                    response = await client.post(
                        base_url.rstrip("/") + "/v2/jobs/",
                        headers=headers,
                        files={
                            "data_file": (path.name, audio, _audio_media_type(path)),
                            "config": (None, json.dumps(config), "application/json"),
                        },
                    )
                response.raise_for_status()
                job_id = str(response.json()["id"])
                for attempt in range(200):
                    status_response = await client.get(
                        base_url.rstrip("/") + f"/v2/jobs/{job_id}", headers=headers
                    )
                    status_response.raise_for_status()
                    status = status_response.json().get("job", {}).get("status")
                    if status == "done":
                        break
                    if status in {"rejected", "error"}:
                        raise EvaluationExecutionError(f"Speechmatics job {status}")
                    if attempt < 199:
                        await asyncio.sleep(3)
                else:
                    raise TimeoutError("Speechmatics job did not finish")
                transcript = await client.get(
                    base_url.rstrip("/") + f"/v2/jobs/{job_id}/transcript?format=json-v2",
                    headers=headers,
                )
                transcript.raise_for_status()
                payload = transcript.json()
            finally:
                if job_id is not None:
                    cleanup_status = "failed"
                    for cleanup_attempt in range(3):
                        try:
                            deleted = await client.delete(
                                base_url.rstrip("/") + f"/v2/jobs/{job_id}",
                                headers=headers,
                                timeout=30,
                            )
                            deleted.raise_for_status()
                            cleanup_status = "completed"
                            break
                        except (httpx.HTTPError, TimeoutError):
                            if cleanup_attempt < 2:
                                await asyncio.sleep(float(cleanup_attempt + 1))
                    if cleanup_status != "completed":
                        logger.error("speechmatics_remote_cleanup_failed job_id=%s", job_id)
        segments = []
        text_parts = []
        for index, item in enumerate(payload.get("results", [])):
            alternative = (item.get("alternatives") or [{}])[0]
            text = alternative.get("content", "")
            if text:
                text_parts.append(text)
            segments.append(
                {
                    "segment_id": _segment_id(conversation_id, "speechmatics", index),
                    "start": item.get("start_time"),
                    "end": item.get("end_time"),
                    "speaker": alternative.get("speaker"),
                    "text": text,
                }
            )
        assert job_id is not None
        return {
            "text": " ".join(text_parts),
            "segments": segments,
            "remote_cleanup": cleanup_status,
        }, job_id

    async def _soniox(
        self,
        base_url: str,
        key: str,
        path: Path,
        conversation_id: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> tuple[dict[str, Any], str]:
        """Upload, transcribe, retrieve, and clean up one Soniox batch job."""
        headers = {"Authorization": f"Bearer {key}"}
        file_id: str | None = None
        transcription_id: str | None = None
        async with httpx.AsyncClient(timeout=300, transport=transport) as client:
            try:
                with path.open("rb") as audio:
                    uploaded = await client.post(
                        base_url.rstrip("/") + "/v1/files",
                        headers=headers,
                        files={"file": (path.name, audio, _audio_media_type(path))},
                    )
                uploaded.raise_for_status()
                file_id = str(uploaded.json()["id"])
                created = await client.post(
                    base_url.rstrip("/") + "/v1/transcriptions",
                    headers=headers,
                    json={
                        "model": "stt-async-v5",
                        "file_id": file_id,
                        "client_reference_id": conversation_id,
                        "language_hints": ["ar", "en"],
                        "enable_language_identification": True,
                        "enable_speaker_diarization": True,
                    },
                )
                created.raise_for_status()
                transcription_id = str(created.json()["id"])
                for _ in range(200):
                    await asyncio.sleep(3)
                    status_response = await client.get(
                        base_url.rstrip("/") + f"/v1/transcriptions/{transcription_id}",
                        headers=headers,
                    )
                    status_response.raise_for_status()
                    status = status_response.json().get("status")
                    if status == "completed":
                        break
                    if status in {"error", "failed"}:
                        raise EvaluationExecutionError(f"Soniox job {status}")
                else:
                    raise TimeoutError("Soniox job did not finish")
                transcript = await client.get(
                    base_url.rstrip("/") + f"/v1/transcriptions/{transcription_id}/transcript",
                    headers=headers,
                )
                transcript.raise_for_status()
                tokens = transcript.json().get("tokens", [])
                segments = [
                    {
                        "segment_id": _segment_id(conversation_id, "soniox", index),
                        "start": token.get("start_ms", 0) / 1000,
                        "end": token.get("end_ms", 0) / 1000,
                        "speaker": token.get("speaker"),
                        "text": token.get("text", ""),
                    }
                    for index, token in enumerate(tokens)
                ]
                result = {
                    "text": "".join(token.get("text", "") for token in tokens),
                    "segments": segments,
                }
                return result, transcription_id
            finally:
                if transcription_id:
                    await client.delete(
                        base_url.rstrip("/") + f"/v1/transcriptions/{transcription_id}",
                        headers=headers,
                    )
                if file_id:
                    await client.delete(
                        base_url.rstrip("/") + f"/v1/files/{file_id}", headers=headers
                    )

    @staticmethod
    def _bounded_full_call_evidence(
        conversation_id: str,
        provider_results: list[dict[str, Any]],
        event_mapping: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """Keep direct neighbors while the mapped target is the formal candidate."""
        if not event_mapping:
            return []
        providers, _lookup = build_turn_catalog(conversation_id, provider_results)
        mapped_turns = {
            str(row.get("provider") or ""): str(row.get("turn_id") or "")
            for row in event_mapping.get("providers") or []
            if isinstance(row, dict) and row.get("status") == "mapped"
        }
        bounded: list[dict[str, Any]] = []
        for provider_row in providers:
            provider = str(provider_row.get("provider") or "")
            target_turn_id = mapped_turns.get(provider)
            turns = list(provider_row.get("turns") or [])
            target_index = next(
                (
                    index
                    for index, turn in enumerate(turns)
                    if str(turn.get("turn_id") or "") == target_turn_id
                ),
                None,
            )
            if target_index is None:
                continue
            neighbors = [
                turns[index]
                for index in (target_index - 1, target_index + 1)
                if 0 <= index < len(turns)
            ]
            bounded.append(
                {
                    "provider": provider,
                    "target_turn_id": target_turn_id,
                    "turns": neighbors,
                }
            )
        return bounded

    async def _run_pass_two(
        self,
        batch_id: str,
        batch: dict[str, Any],
        conversations: list[dict[str, Any]],
        candidates: list[dict[str, Any]],
        *,
        plan_key: str,
    ) -> None:
        """Evaluate preflight-safe request groups with bounded per-Case evidence."""
        if not candidates:
            return
        candidate_by_key = {
            (str(candidate["conversation_id"]), str(candidate["event_id"])): candidate
            for candidate in candidates
        }
        by_conversation = {str(item["conversation_id"]): item for item in conversations}
        context_rows = await self.store.checkpoint_rows("evaluation_asr_runs", batch_id)
        context_by_conversation: dict[str, list[dict[str, Any]]] = {}
        for row in context_rows:
            if row["status"] == "completed":
                context_by_conversation.setdefault(str(row["conversation_id"]), []).append(
                    {"provider": row["provider"], **(row["result"] or {})}
                )
        alignment_by_case: dict[tuple[str, str], dict[str, Any]] = {}
        alignment_rows = await self.store.checkpoint_rows(
            "evaluation_event_alignment_runs", batch_id
        )
        for row in alignment_rows:
            if row.get("status") != "completed" or not isinstance(row.get("result"), dict):
                continue
            for event in row["result"].get("events") or []:
                if isinstance(event, dict):
                    alignment_by_case[
                        (str(row["conversation_id"]), str(event.get("event_id") or ""))
                    ] = event
        asr_rows = await self.store.checkpoint_rows("evaluation_case_asr_runs", batch_id)
        asr_by_case: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for row in asr_rows:
            if row["status"] == "completed":
                key = (str(row["conversation_id"]), str(row["event_id"]))
                asr_by_case.setdefault(key, []).append(
                    {"provider": row["provider"], **(row["result"] or {})}
                )
        snapshot = batch["snapshot"]
        prompt = str(snapshot.get("pass_2_prompt", {}).get("content", PASS_TWO_SYSTEM_PROMPT))
        model_id = str(snapshot["pass_2_model"])
        provider = await self._model_provider(model_id)
        policy = evaluation_token_policy(provider, model_id.split("::", 1)[-1])
        candidates_by_conversation: dict[str, list[dict[str, Any]]] = {}
        for candidate in candidates:
            candidates_by_conversation.setdefault(str(candidate["conversation_id"]), []).append(
                candidate
            )
        shared_payload = {
            "evaluation_context": snapshot.get("evaluation_context", EVALUATION_CONTEXT),
            "reference_dictionaries": snapshot.get(
                "reference_dictionaries", REFERENCE_DICTIONARIES
            ),
            "screening_strategy": snapshot["screening_strategy"],
            "scenario_tags": snapshot.get("scenario_tags", SCENARIO_TAGS),
        }
        units = []
        for conversation_id, conversation_candidates in sorted(candidates_by_conversation.items()):
            conversation = by_conversation[conversation_id]
            production_by_event = {
                str(event["event_id"]): str(event["text"]) for event in conversation["events"]
            }
            ordered_candidates = sorted(
                conversation_candidates,
                key=lambda candidate: str(candidate["event_id"]),
            )

            def build_case_unit(
                subset: list[dict[str, Any]],
                *,
                current_conversation_id: str = conversation_id,
                current_conversation: dict[str, Any] = conversation,
                current_production_by_event: dict[str, str] = production_by_event,
            ) -> Any:
                unit_payload = {
                    "conversation_id": current_conversation_id,
                    "conversation_history": current_conversation["events"],
                    "candidate_cases": subset,
                    "full_audio_context_asr": [
                        {
                            "event_id": str(candidate["event_id"]),
                            "providers": self._bounded_full_call_evidence(
                                current_conversation_id,
                                context_by_conversation.get(current_conversation_id, []),
                                alignment_by_case.get(
                                    (current_conversation_id, str(candidate["event_id"]))
                                ),
                            ),
                        }
                        for candidate in subset
                    ],
                    "production_transcripts": {
                        str(candidate["event_id"]): current_production_by_event.get(
                            str(candidate["event_id"]), ""
                        )
                        for candidate in subset
                    },
                    "asr_results": [
                        {
                            "event_id": str(candidate["event_id"]),
                            "providers": asr_by_case.get(
                                (current_conversation_id, str(candidate["event_id"])), []
                            ),
                        }
                        for candidate in subset
                    ],
                }
                return build_unit(
                    current_conversation_id,
                    unit_payload,
                    [(current_conversation_id, str(candidate["event_id"])) for candidate in subset],
                    policy,
                )

            pending_subsets = [ordered_candidates]
            while pending_subsets:
                subset = pending_subsets.pop(0)
                try:
                    unit = build_case_unit(subset)
                    pack_units(
                        batch_id=f"{batch_id}:{plan_key}:preflight",
                        units=[unit],
                        system_prompt=prompt,
                        policy=policy,
                        shared_payload=shared_payload,
                    )
                except ValueError as exc:
                    if len(subset) == 1:
                        message = str(exc).casefold()
                        if "output limit" in message:
                            raise EvaluationRequestOutputTooLarge(
                                "One Pass 2 Case exceeds the pre-dispatch generation limit."
                            ) from exc
                        raise EvaluationRequestTooLarge(
                            "One Pass 2 Case exceeds the pre-dispatch input limit."
                        ) from exc
                    midpoint = len(subset) // 2
                    pending_subsets[0:0] = [subset[:midpoint], subset[midpoint:]]
                    continue
                units.append(unit)
        groups = pack_units(
            batch_id=f"{batch_id}:{plan_key}",
            units=units,
            system_prompt=prompt,
            policy=policy,
            shared_payload=shared_payload,
        )
        all_prior_groups = {
            str(row["group_id"]): row for row in await self.store.pass2_group_rows(batch_id)
        }
        prior_groups = {
            group.group_id: all_prior_groups[group.group_id]
            for group in groups
            if group.group_id in all_prior_groups
        }
        for group in groups:
            prior = prior_groups.get(group.group_id)
            if prior is not None and str(prior["idempotency_key"]) != group.idempotency_key:
                raise EvaluationExecutionError("Frozen Pass 2 group membership changed")
            if prior is None:
                await self.store.checkpoint_pass2_group(
                    batch_id=batch_id,
                    group_id=group.group_id,
                    idempotency_key=group.idempotency_key,
                    conversation_ids=[unit.conversation_id for unit in group.units],
                    case_keys=list(group.case_keys),
                    estimated_input_tokens=group.estimated_input_tokens,
                    reserved_output_tokens=group.reserved_output_tokens,
                    status="pending",
                    attempts=0,
                )
        planned_group_total = len(
            [
                row
                for row in await self.store.pass2_group_rows(batch_id)
                if row["status"] != "superseded"
            ]
        )
        planned_case_total = len(candidate_by_key)
        await self.store.set_batch_state(
            batch_id,
            status="running",
            stage="pass_2",
            progress=75,
            snapshot_updates={
                "pass_2_plan": {
                    "unique_case_count": planned_case_total,
                    "request_group_count": planned_group_total,
                    "thinking": "enabled",
                    "packing": "dynamic_case_preflight",
                }
            },
        )
        await self.store.refresh_pass2_progress(
            batch_id,
            suspect_case_keys=set(candidate_by_key) if plan_key == "suspects" else None,
            progress_start=75,
            progress_end=92,
        )

        request_semaphore = asyncio.Semaphore(2)

        async def request_group(
            group: Any,
            payload: dict[str, Any],
            attempt: int,
            retry_correction: str | None,
        ) -> dict[str, Any]:
            """Dispatch only a preflight-safe canonical request."""
            async with request_semaphore:
                return await self._llm_json(
                    model_id,
                    prompt,
                    payload,
                    thinking=True,
                    max_output_tokens=group.reserved_output_tokens,
                    batch_id=batch_id,
                    stage="pass_2",
                    item_key=group.group_id,
                    attempt=attempt,
                    system_only_payload=True,
                    user_instruction=retry_correction,
                    max_input_tokens=input_limit(policy),
                )

        async def decide_group(group: Any) -> None:
            latest_groups = {
                str(row["group_id"]): row for row in await self.store.pass2_group_rows(batch_id)
            }
            prior = latest_groups.get(group.group_id)
            if prior is not None and prior.get("status") == "completed":
                return
            if prior is not None and prior.get("status") == "superseded":
                raise EvaluationExecutionError(
                    "A legacy superseded Pass 2 group requires an explicit fresh retry plan."
                )
            payload = build_pass_two_payload(group.group_id, group.units, shared_payload)
            retry_correction: str | None = None
            if prior is not None and int(prior.get("attempts") or 0) > 0:
                retry_correction = (
                    "The previous saved request group failed its structured-response contract. "
                    "Retry the same complete group and output only one complete JSON object."
                )
            prior_attempts = int(prior.get("attempts") or 0) if prior is not None else 0
            for local_attempt in range(1, 4):
                attempt = prior_attempts + local_attempt
                started_at = time.perf_counter()
                try:
                    result = await request_group(group, payload, attempt, retry_correction)
                    indexed = self._validate_pass_two_group(
                        result,
                        group.case_keys,
                        {
                            (unit.conversation_id, str(event_result["event_id"])): bool(
                                event_result.get("providers")
                            )
                            for unit in group.units
                            for event_result in unit.payload.get("asr_results", [])
                        },
                        {
                            (unit.conversation_id, str(event_result["event_id"])): {
                                str(segment.get("segment_id"))
                                for asr_result in event_result.get("providers", [])
                                for segment in asr_result.get("segments", [])
                                if segment.get("segment_id")
                            }
                            for unit in group.units
                            for event_result in unit.payload.get("asr_results", [])
                        },
                        expected_group_id=group.group_id,
                    )
                    for key in group.case_keys:
                        stored_result = dict(indexed[key])
                        stored_result["origin"] = str(
                            candidate_by_key[key].get("origin") or "suspect_candidate"
                        )
                        await self.store.checkpoint_result(
                            "evaluation_pass2_runs",
                            (batch_id, key[0], key[1]),
                            status="completed",
                            attempts=attempt,
                            result=stored_result,
                        )
                    await self.store.checkpoint_pass2_group(
                        batch_id=batch_id,
                        group_id=group.group_id,
                        idempotency_key=group.idempotency_key,
                        conversation_ids=[unit.conversation_id for unit in group.units],
                        case_keys=list(group.case_keys),
                        estimated_input_tokens=group.estimated_input_tokens,
                        reserved_output_tokens=group.reserved_output_tokens,
                        status="completed",
                        attempts=attempt,
                        result={"result_count": len(indexed)},
                    )
                    await self._refresh_pass_two_group_status(batch_id)
                    await self.store.refresh_pass2_progress(
                        batch_id,
                        suspect_case_keys=(
                            set(candidate_by_key) if plan_key == "suspects" else None
                        ),
                        progress_start=75,
                        progress_end=92,
                    )
                    await self.store.record_telemetry(
                        batch_id=batch_id,
                        stage="pass_2",
                        event="llm_request",
                        provider=provider,
                        outcome="completed",
                        attempt=attempt,
                        latency_ms=(time.perf_counter() - started_at) * 1000,
                    )
                    return
                except EvaluationBudgetReached:
                    return
                except Exception as exc:
                    retry_correction = _structured_retry_correction(exc)
                    await self.store.checkpoint_pass2_group(
                        batch_id=batch_id,
                        group_id=group.group_id,
                        idempotency_key=group.idempotency_key,
                        conversation_ids=[unit.conversation_id for unit in group.units],
                        case_keys=list(group.case_keys),
                        estimated_input_tokens=group.estimated_input_tokens,
                        reserved_output_tokens=group.reserved_output_tokens,
                        status="pending",
                        attempts=attempt,
                        error=_safe_structured_error(exc),
                    )
                    await self.store.record_telemetry(
                        batch_id=batch_id,
                        stage="pass_2",
                        event=("schema_failure" if isinstance(exc, ValueError) else "llm_request"),
                        provider=provider,
                        outcome="failed",
                        attempt=attempt,
                        latency_ms=(time.perf_counter() - started_at) * 1000,
                    )
                    if local_attempt == 3:
                        error = _safe_structured_error(exc)
                        for key in group.case_keys:
                            await self.store.checkpoint_result(
                                "evaluation_pass2_runs",
                                (batch_id, key[0], key[1]),
                                status="failed",
                                attempts=attempt,
                                error=error,
                            )
                        await self.store.checkpoint_pass2_group(
                            batch_id=batch_id,
                            group_id=group.group_id,
                            idempotency_key=group.idempotency_key,
                            conversation_ids=[unit.conversation_id for unit in group.units],
                            case_keys=list(group.case_keys),
                            estimated_input_tokens=group.estimated_input_tokens,
                            reserved_output_tokens=group.reserved_output_tokens,
                            status="failed",
                            attempts=attempt,
                            error=error,
                        )
                        await self._refresh_pass_two_group_status(batch_id)
                        await self.store.refresh_pass2_progress(
                            batch_id,
                            suspect_case_keys=(
                                set(candidate_by_key) if plan_key == "suspects" else None
                            ),
                            progress_start=75,
                            progress_end=92,
                        )
                    else:
                        await asyncio.sleep(float(local_attempt))

        await self.store.record_telemetry(
            batch_id=batch_id,
            stage="pass_2",
            event="queue_depth",
            provider=provider,
            outcome="observed",
            queue_depth=len(groups),
        )
        await asyncio.gather(*(decide_group(group) for group in groups))
        await self._refresh_pass_two_group_status(batch_id)

    async def _refresh_pass_two_group_status(self, batch_id: str) -> None:
        """Expose external request progress separately from unique Case progress."""
        rows = await self.store.pass2_group_rows(batch_id)
        active_rows = [row for row in rows if row["status"] != "superseded"]
        batch = await self.store.get_batch(batch_id)
        if batch is None:
            raise LookupError("Batch not found")
        suspect_keys = {
            (str(item[0]), str(item[1]))
            for item in batch["snapshot"].get("pass_2_suspect_case_keys", [])
            if isinstance(item, list) and len(item) == 2
        }
        suspect_rows = [
            row
            for row in active_rows
            if not suspect_keys
            or {
                (str(item[0]), str(item[1]))
                for item in row.get("case_keys", [])
                if isinstance(item, list) and len(item) == 2
            }.issubset(suspect_keys)
        ]

        def group_status(group_rows: list[dict[str, Any]]) -> dict[str, int]:
            return {
                "completed": sum(row["status"] == "completed" for row in group_rows),
                "failed": sum(row["status"] == "failed" for row in group_rows),
                "pending": sum(row["status"] == "pending" for row in group_rows),
                "attempts": sum(int(row.get("attempts") or 0) for row in group_rows),
                "total": len(group_rows),
            }

        await self.store.set_batch_state(
            batch_id,
            status="running",
            stage="pass_2",
            progress=int(batch["progress"]),
            snapshot_updates={
                "pass_2_request_status": {
                    **group_status(suspect_rows),
                    "superseded": len(rows) - len(active_rows),
                },
                "pass_2_good_request_status": group_status(
                    [row for row in active_rows if row not in suspect_rows]
                ),
            },
        )

    @classmethod
    def _validate_pass_two_group(
        cls,
        result: dict[str, Any],
        expected_keys: tuple[tuple[str, str], ...],
        has_asr: dict[Any, bool],
        segment_ids: dict[Any, set[str]] | None = None,
        *,
        expected_group_id: str | None = None,
    ) -> dict[tuple[str, str], dict[str, Any]]:
        """Require exactly one valid result for every Case in a request group."""
        if expected_group_id is not None and result.get("request_group_id") != expected_group_id:
            raise ValueError("Pass 2 returned the wrong request group")
        rows = result.get("results")
        if not isinstance(rows, list):
            raise ValueError("Pass 2 group returned no results array")
        indexed: dict[tuple[str, str], dict[str, Any]] = {}
        expected = set(expected_keys)
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("Pass 2 result must be an object")
            key = (str(row.get("conversation_id")), str(row.get("event_id")))
            if key not in expected or key in indexed:
                raise ValueError("Pass 2 returned an unexpected or duplicate Case")
            cls._validate_pass_two(
                row,
                {"event_id": key[1]},
                has_asr.get(key, has_asr.get(key[0], False)),
                (segment_ids or {}).get(key, (segment_ids or {}).get(key[0])),
            )
            indexed[key] = row
        if set(indexed) != expected:
            raise ValueError("Pass 2 omitted one or more Cases")
        return indexed

    @staticmethod
    def _validate_pass_two(
        result: dict[str, Any],
        candidate: dict[str, Any],
        has_asr: bool,
        valid_segment_ids: set[str] | None = None,
    ) -> None:
        """Enforce the automatic-decision gates defined by the product spec."""
        if str(result.get("event_id")) != str(candidate["event_id"]):
            raise ValueError("Pass 2 returned the wrong event")
        decision = result.get("decision")
        allowed = {"Good Case", "Bad Case", "Needs manual audio review"}
        if decision not in allowed:
            raise ValueError("Pass 2 returned an invalid decision")
        if decision in {"Good Case", "Bad Case"} and (
            not has_asr or not str(result.get("reference_text") or "").strip()
        ):
            raise ValueError("Automatic decision lacks reference evidence")
        if _contains_key(result, "confidence"):
            raise ValueError("Pass 2 must not return confidence")
        if not str(result.get("reason") or "").strip():
            raise ValueError("Pass 2 result lacks a reason")
        if not str(result.get("scenario_tag") or "").strip():
            raise ValueError("Pass 2 result lacks a scenario tag")
        if result.get("evidence_completeness") not in {"complete", "partial"}:
            raise ValueError("Pass 2 evidence completeness is invalid")
        positioning_quality = result.get("positioning_quality")
        if positioning_quality not in {
            "exact",
            "expanded",
            "full_recording",
            "unavailable",
        }:
            raise ValueError("Pass 2 positioning quality is invalid")
        if decision in {"Good Case", "Bad Case"} and positioning_quality not in {
            "exact",
            "expanded",
        }:
            raise ValueError("Automatic decision lacks bounded evidence")
        proposal = result.get("proposed_tag")
        if proposal is not None:
            if not isinstance(proposal, dict):
                raise ValueError("Proposed tag must be an object")
            if proposal.get("type") not in {"acoustic", "semantic"} or any(
                not str(proposal.get(field) or "").strip()
                for field in ("name_en", "name_zh", "description_en", "description_zh")
            ):
                raise ValueError("Proposed tag lacks its bilingual schema")
        if decision == "Needs manual audio review":
            if result.get("reference_text") is not None:
                raise ValueError("Manual-review result must not provide reference text")
            if not str(result.get("manual_review_question") or "").strip():
                raise ValueError("Manual-review result lacks a listening question")
        elif result.get("manual_review_question") is not None:
            raise ValueError("Automatic decision must not include a listening question")
        if valid_segment_ids is None:
            return
        evidence = result.get("vendor_evidence")
        listening_ids = result.get("recommended_listening_segment_ids")
        if not isinstance(evidence, list) or not evidence:
            raise ValueError("Pass 2 result lacks vendor evidence")
        if not isinstance(listening_ids, list):
            raise ValueError("Pass 2 listening evidence is malformed")
        referenced_ids: set[str] = set()
        for item in evidence:
            if not isinstance(item, dict) or not str(item.get("provider") or "").strip():
                raise ValueError("Pass 2 vendor evidence is malformed")
            if item.get("relationship_to_history") not in {
                "agrees",
                "differs",
                "missing",
                "ambiguous",
            }:
                raise ValueError("Pass 2 vendor evidence relationship is invalid")
            item_ids = item.get("segment_ids")
            if not isinstance(item_ids, list):
                raise ValueError("Pass 2 vendor evidence segment IDs are malformed")
            referenced_ids.update(str(segment_id) for segment_id in item_ids)
        referenced_ids.update(str(segment_id) for segment_id in listening_ids)
        if referenced_ids and not referenced_ids.issubset(valid_segment_ids):
            raise ValueError("Pass 2 references unknown ASR segments")
        # PD-035 fixes the listening boundary before provider dispatch. Segment IDs remain
        # useful technical evidence, but providers may omit word timing for a valid short clip.
