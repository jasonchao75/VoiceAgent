"""FastAPI routes for source-backed ASR evaluation data."""

from __future__ import annotations

import asyncio
import csv
import hashlib
import hmac
import io
import json
import os
import re
import time
import uuid
import zipfile
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response

from src.evaluation.imports import PackageUploadError
from src.evaluation.models import (
    BenchmarkExportRequest,
    BenchmarkUpdate,
    EvaluationBatchAction,
    EvaluationBatchCreate,
    EvaluationBatchDelete,
    EvaluationContextStatusUpdate,
    EvaluationContextWrite,
    EvaluationDisplayTranslationRequest,
    EvaluationPricingVersionWrite,
    EvaluationReviewComplete,
    EvaluationReviewSubmit,
    PromptTemplateRestore,
    PromptTemplateWrite,
    ReferenceDictionaryWrite,
    ScenarioTagStatusUpdate,
    ScenarioTagWrite,
)
from src.evaluation.pricing import (
    OfficialPricingService,
    PricingSyncError,
    PricingSyncRequest,
)
from src.evaluation.storage import EvaluationStore


def _safe_slug(value: str) -> str:
    """Convert controlled grouping values to filesystem-safe ZIP paths."""
    return re.sub(r"[^a-z0-9_-]+", "-", value.lower()).strip("-") or "unclassified"


def _build_benchmark_archive(
    artifact_path: Path,
    rows: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Build an export from managed ready clips and report every unavailable item."""
    manifest: list[dict[str, str]] = []
    csv_buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        csv_buffer,
        fieldnames=["audio_path", "benchmark_id", "annotated_text"],
    )
    writer.writeheader()
    temporary_path = artifact_path.with_suffix(".part")
    try:
        with zipfile.ZipFile(temporary_path, "w", zipfile.ZIP_DEFLATED) as bundle:
            for row in rows:
                folder = (
                    f"wav/{_safe_slug(str(row['language']))}/{_safe_slug(str(row['scenario_tag']))}"
                )
                relative = f"{folder}/{row['id']}.wav"
                source_value = row.get("clip_path")
                source = Path(str(source_value)) if source_value else None
                try:
                    if row.get("clip_status") != "ready" or source is None:
                        raise ValueError(str(row.get("clip_error") or "Clip is unavailable"))
                    bundle.write(source, relative)
                    writer.writerow(
                        {
                            "audio_path": relative,
                            "benchmark_id": row["id"],
                            "annotated_text": row["label"],
                        }
                    )
                except (OSError, RuntimeError, ValueError) as exc:
                    manifest.append({"benchmark_id": str(row["id"]), "error": type(exc).__name__})
            bundle.writestr("benchmark.csv", csv_buffer.getvalue().encode("utf-8-sig"))
            if manifest:
                manifest_buffer = io.StringIO(newline="")
                manifest_writer = csv.DictWriter(
                    manifest_buffer,
                    fieldnames=["benchmark_id", "error"],
                )
                manifest_writer.writeheader()
                manifest_writer.writerows(manifest)
                bundle.writestr("manifest.csv", manifest_buffer.getvalue().encode("utf-8-sig"))
        temporary_path.replace(artifact_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return manifest


def _issue_csv(audit: dict[str, object]) -> bytes:
    """Serialize a stable repair-oriented issue list."""
    output = io.StringIO(newline="")
    fields = [
        "severity",
        "issue_type",
        "conversation_id",
        "expected_path",
        "source_file",
        "source_row",
        "message",
    ]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(audit.get("issues", []))  # type: ignore[arg-type]
    return output.getvalue().encode("utf-8-sig")


def _verify_elevenlabs_signature(raw_body: bytes, signature: str, secret: str) -> None:
    """Verify the documented timestamped ElevenLabs HMAC signature."""
    try:
        fields = dict(part.split("=", 1) for part in signature.split(","))
        timestamp = fields["t"]
        supplied = fields["v0"]
        if abs(time.time() - int(timestamp)) > 30 * 60:
            raise ValueError("stale")
    except (KeyError, ValueError) as exc:
        raise ValueError("Invalid ElevenLabs webhook signature") from exc
    expected = hmac.new(
        secret.encode(),
        timestamp.encode() + b"." + raw_body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, supplied):
        raise ValueError("Invalid ElevenLabs webhook signature")


def _upload_template() -> bytes:
    """Build a small package-contract template without customer data."""
    instructions = """ASR evaluation upload package

Required paths (one complete set per conversation ID):
  conversation_history/{full_conversation_id}.xlsx
  record/{full_conversation_id}.mp3
  user_record/{full_conversation_id}.wav

Workbook contract:
  Worksheet: Dialogue Details
  Columns A:C: time (s), robot, customer
  Each event row must contain text for exactly one speaker.

Repair upload:
  Upload one corrected XLSX/MP3/WAV file, or a ZIP containing only corrected files.
  ZIP repairs must preserve the required relative paths above.
"""
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("UPLOAD_INSTRUCTIONS.txt", instructions)
        for folder in ("conversation_history/", "record/", "user_record/"):
            bundle.writestr(folder, b"")
    return archive.getvalue()


def create_evaluation_router(
    store: EvaluationStore,
    pricing_service: OfficialPricingService | None = None,
    start_batch: Callable[[str], None] | None = None,
    handle_batch_action: Callable[[str, str], None] | None = None,
    translate_for_display: Callable[[str, list[str]], Awaitable[dict[str, object]]] | None = None,
) -> APIRouter:
    """Build evaluation routes around one initialized store."""
    router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])
    official_pricing = pricing_service or OfficialPricingService()
    export_tasks: dict[str, asyncio.Task[None]] = {}

    async def run_benchmark_export(export_id: str) -> None:
        """Build one frozen export and persist its terminal state."""
        request = await store.benchmark_export_request(export_id)
        if request is None:
            return
        try:
            result = await store.list_benchmarks(
                limit=5000,
                ids=[str(value) for value in request.get("sample_ids", [])],
                include_storage=True,
            )
            rows = result["items"]
            if not rows:
                raise ValueError("No Benchmark samples remain available for this export")
            artifact_path = store.export_root / f"{export_id}.zip"
            manifest = await asyncio.to_thread(
                _build_benchmark_archive,
                artifact_path,
                rows,
            )
            await store.finish_benchmark_export(
                export_id,
                artifact_path=artifact_path,
                manifest=manifest,
            )
        except Exception as exc:  # noqa: BLE001 - the durable job must expose failure state
            await store.finish_benchmark_export(
                export_id,
                error=f"{type(exc).__name__}: {exc}",
            )

    def schedule_benchmark_export(export_id: str) -> None:
        """Keep a strong task reference and deduplicate worker scheduling."""
        existing = export_tasks.get(export_id)
        if existing is not None and not existing.done():
            return
        task = asyncio.create_task(run_benchmark_export(export_id))
        export_tasks[export_id] = task
        task.add_done_callback(lambda _task: export_tasks.pop(export_id, None))

    @router.get("/bootstrap")
    async def bootstrap() -> dict[str, object]:
        return {
            "mode": "real_provider_execution",
            "fixture": store.fixture_status(),
            "summary": await store.summary(),
            "batches": await store.list_batches(),
            "reviews": await store.list_reviews("pending"),
            "benchmarks": await store.list_benchmarks(limit=20),
            "scenario_tags": await store.list_scenario_tags(),
            "reference_dictionaries": await store.list_reference_dictionaries(),
            "evaluation_contexts": await store.list_contexts(),
            "prompt_templates": await store.prompt_templates(),
            "asr_capabilities": await store.list_asr_capabilities(),
            "pending_dataset": store.pending_dataset_status(),
        }

    @router.post("/webhooks/elevenlabs", include_in_schema=False)
    async def elevenlabs_webhook(request: Request) -> dict[str, str]:
        """Accept only signed Scribe completion events and correlate them durably."""
        secret = os.getenv("ELEVENLABS_STT_WEBHOOK_SECRET", "")
        if not secret:
            raise HTTPException(status_code=503, detail="ElevenLabs webhook is not configured")
        raw_body = await request.body()
        try:
            _verify_elevenlabs_signature(
                raw_body,
                request.headers.get("elevenlabs-signature", ""),
                secret,
            )
            event = json.loads(raw_body)
        except (ValueError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=401, detail="Invalid webhook signature") from exc
        if event.get("type") not in {
            "speech_to_text_transcription",
            "speech_to_text.completed",
        }:
            return {"status": "ignored"}
        data = event.get("data") or {}
        metadata = data.get("webhook_metadata") or {}
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError as exc:
                raise HTTPException(
                    status_code=422,
                    detail="Webhook correlation is invalid",
                ) from exc
        if not isinstance(metadata, dict):
            raise HTTPException(status_code=422, detail="Webhook correlation is invalid")
        correlation_id = str(metadata.get("correlation_id") or "")
        request_id = str(data.get("request_id") or data.get("requestId") or "")
        if not correlation_id.startswith("evaluation:") or not request_id:
            raise HTTPException(status_code=422, detail="Webhook correlation is invalid")
        transcription = data.get("transcription")
        failure = data.get("error") or data.get("failure_reason")
        if not isinstance(transcription, dict) and not failure:
            raise HTTPException(status_code=422, detail="Webhook result is incomplete")
        await store.complete_elevenlabs_job(
            request_id=request_id,
            correlation_id=correlation_id,
            result=transcription if isinstance(transcription, dict) else None,
            error=str(failure) if failure else None,
        )
        return {"status": "received"}

    @router.get("/reference-dictionaries")
    async def reference_dictionaries() -> list[dict[str, object]]:
        """Return current generic dictionary versions and complete content."""
        return await store.list_reference_dictionaries()

    @router.post("/reference-dictionaries", status_code=201)
    async def create_reference_dictionary(
        payload: ReferenceDictionaryWrite,
    ) -> dict[str, object]:
        """Create one reusable reference dictionary."""
        try:
            return await store.write_reference_dictionary(payload)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.put("/reference-dictionaries/{dictionary_id}")
    async def update_reference_dictionary(
        dictionary_id: str,
        payload: ReferenceDictionaryWrite,
    ) -> dict[str, object]:
        """Append an immutable dictionary version."""
        try:
            return await store.write_reference_dictionary(payload, dictionary_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.get("/contexts")
    async def evaluation_contexts() -> list[dict[str, object]]:
        """Return current versioned evaluation contexts."""
        return await store.list_contexts()

    @router.post("/contexts", status_code=201)
    async def create_evaluation_context(
        payload: EvaluationContextWrite,
    ) -> dict[str, object]:
        """Create one evaluation context and freeze its dictionary links."""
        try:
            return await store.write_context(payload)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.put("/contexts/{context_id}")
    async def update_evaluation_context(
        context_id: str,
        payload: EvaluationContextWrite,
    ) -> dict[str, object]:
        """Append an immutable evaluation-context version."""
        try:
            return await store.write_context(payload, context_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.patch("/contexts/{context_id}/status")
    async def update_evaluation_context_status(
        context_id: str,
        payload: EvaluationContextStatusUpdate,
    ) -> dict[str, object]:
        """Change future-batch availability or select the default context."""
        try:
            return await store.set_context_status(
                context_id,
                enabled=payload.enabled,
                is_default=payload.is_default,
                expected_version=payload.expected_version,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.get("/prompt-templates")
    async def prompt_templates() -> list[dict[str, object]]:
        """Return the complete active two-pass Prompt templates."""
        return await store.prompt_templates()

    @router.put("/prompt-templates/{template_key}")
    async def update_prompt_template(
        template_key: str,
        payload: PromptTemplateWrite,
    ) -> dict[str, object]:
        """Append a Prompt version after required-slot validation."""
        try:
            return await store.update_prompt_template(template_key, payload)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.get("/prompt-templates/{template_key}/versions")
    async def prompt_template_versions(template_key: str) -> list[dict[str, object]]:
        """Return immutable Prompt history newest first for comparison."""
        try:
            return await store.prompt_template_versions(template_key)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/prompt-templates/{template_key}/restore")
    async def restore_prompt_template(
        template_key: str,
        payload: PromptTemplateRestore,
    ) -> dict[str, object]:
        """Copy historical Prompt content into a new active version."""
        try:
            return await store.restore_prompt_template(template_key, payload)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.get("/scenario-tags")
    async def scenario_tags() -> list[dict[str, object]]:
        """Return the current data-backed global taxonomy."""
        return await store.list_scenario_tags()

    @router.post("/scenario-tags", status_code=201)
    async def create_scenario_tag(payload: ScenarioTagWrite) -> dict[str, object]:
        """Create one tag with an immutable first version."""
        try:
            return await store.create_scenario_tag(payload)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.put("/scenario-tags/{tag_id}")
    async def update_scenario_tag(tag_id: str, payload: ScenarioTagWrite) -> dict[str, object]:
        """Append a new content version for one tag."""
        try:
            return await store.update_scenario_tag(tag_id, payload)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.patch("/scenario-tags/{tag_id}/status")
    async def update_scenario_tag_status(
        tag_id: str, payload: ScenarioTagStatusUpdate
    ) -> dict[str, object]:
        """Enable or disable a current tag without rewriting history."""
        try:
            return await store.set_scenario_tag_status(
                tag_id,
                enabled=payload.enabled,
                expected_version=payload.expected_version,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.delete("/scenario-tags/{tag_id}", status_code=204)
    async def delete_scenario_tag(tag_id: str, expected_version: int) -> Response:
        """Tombstone a tag while retaining all referenced versions."""
        try:
            await store.delete_scenario_tag(tag_id, expected_version)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return Response(status_code=204)

    @router.get("/fixture")
    async def fixture_status() -> dict[str, object]:
        return store.fixture_status()

    @router.get("/llm-models")
    async def llm_models() -> list[dict[str, str]]:
        """Return custom evaluation models admitted by a successful live test."""
        return await store.list_llm_models()

    @router.get("/connections")
    async def connections() -> list[dict[str, object]]:
        """Return restart-safe connection metadata without credentials."""
        return await store.list_connections()

    @router.get("/batches/{batch_id}/report")
    async def batch_report(batch_id: str) -> dict[str, object]:
        """Return the latest immutable report for a completed automated stage."""
        batch = await store.get_batch(batch_id)
        if batch is None:
            raise HTTPException(status_code=404, detail="Batch not found")
        if batch["result_disposition"] == "audit_only":
            raise HTTPException(
                status_code=409,
                detail="This batch is retained as audit-only evidence and has no formal report",
            )
        report = await store.latest_report(batch_id)
        if report is None:
            raise HTTPException(status_code=404, detail="No frozen report exists for this batch")
        await store.audit_access("report.viewed", str(report["report_id"]), {"batch_id": batch_id})
        return report

    @router.get("/batches/{batch_id}/partial-results")
    async def batch_partial_results(batch_id: str) -> dict[str, object]:
        """Project persisted successful checkpoints without freezing a formal report."""
        batch = await store.get_batch(batch_id)
        if batch is None:
            raise HTTPException(status_code=404, detail="Batch not found")
        if batch["status"] not in {"partially_failed", "stopped", "budget_paused"}:
            raise HTTPException(
                status_code=409,
                detail="Partial results are only available for incomplete batches",
            )
        report = await store.freeze_preliminary_report(batch_id, persist=False)
        await store.audit_access("partial_results.viewed", batch_id, {"status": batch["status"]})
        return report

    @router.post("/batches/{batch_id}/display-translation")
    async def display_translation(
        batch_id: str,
        payload: EvaluationDisplayTranslationRequest,
    ) -> dict[str, object]:
        """Translate only visible source text and return a non-durable display result."""
        if translate_for_display is None:
            raise HTTPException(status_code=503, detail="Display translation is unavailable")
        if await store.get_batch(batch_id) is None:
            raise HTTPException(status_code=404, detail="Batch not found")
        try:
            return await translate_for_display(batch_id, payload.texts)
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.get("/batches/{batch_id}/audit-evidence")
    async def batch_audit_evidence(batch_id: str) -> dict[str, object]:
        """Return retained evidence only for a batch explicitly excluded from formal outputs."""
        batch = await store.get_batch(batch_id)
        if batch is None:
            raise HTTPException(status_code=404, detail="Batch not found")
        if batch["result_disposition"] != "audit_only":
            raise HTTPException(status_code=409, detail="Batch is not audit-only")
        report = await store.latest_report(batch_id)
        if report is None:
            raise HTTPException(status_code=404, detail="No retained audit evidence exists")
        await store.audit_access(
            "batch.audit_evidence_viewed",
            batch_id,
            {"retained_report_id": str(report["report_id"])},
        )
        return {**report, "audit_only": True, "formal_report": False}

    @router.get("/batches/{batch_id}/costs")
    async def batch_costs(batch_id: str) -> dict[str, object]:
        """Return separately reconciled ASR and LLM usage ledgers."""
        if await store.get_batch(batch_id) is None:
            raise HTTPException(status_code=404, detail="Batch not found")
        return await store.cost_summary(batch_id)

    @router.get("/batches/{batch_id}/telemetry")
    async def batch_telemetry(batch_id: str) -> dict[str, object]:
        """Return content-free execution counters, traces, and reconciled cost totals."""
        if await store.get_batch(batch_id) is None:
            raise HTTPException(status_code=404, detail="Batch not found")
        return await store.telemetry_summary(batch_id)

    @router.get("/batches/{batch_id}/reports/{version}")
    async def batch_report_version(batch_id: str, version: int) -> dict[str, object]:
        """Return one immutable report version."""
        if version < 1:
            raise HTTPException(status_code=422, detail="Report version must be positive")
        batch = await store.get_batch(batch_id)
        if batch is None:
            raise HTTPException(status_code=404, detail="Batch not found")
        if batch["result_disposition"] == "audit_only":
            raise HTTPException(
                status_code=409,
                detail="This batch is retained as audit-only evidence and has no formal report",
            )
        report = await store._report_version(batch_id, version)
        if report is None:
            raise HTTPException(status_code=404, detail="Report version not found")
        await store.audit_access("report.viewed", str(report["report_id"]), {"batch_id": batch_id})
        return report

    @router.post("/reports/{report_id}/proposed-tags/{proposal_key}")
    async def create_report_proposed_tag(
        report_id: str,
        proposal_key: str,
    ) -> dict[str, object]:
        """Create a complete bilingual proposal and move its grouped Cases."""
        try:
            return await store.create_proposed_tag(report_id, proposal_key)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post("/batches/{batch_id}/complete-review")
    async def complete_review_early(
        batch_id: str,
        payload: EvaluationReviewComplete,
    ) -> dict[str, object]:
        """Explicitly freeze a partial final report with pending reviews excluded."""
        previous = await store.command_result(payload.idempotency_key)
        if previous is not None:
            return previous
        batch = await store.get_batch(batch_id)
        if batch is None:
            raise HTTPException(status_code=404, detail="Batch not found")
        if batch["version"] != payload.expected_version:
            raise HTTPException(
                status_code=409,
                detail="The batch changed; refresh before retrying",
            )
        if batch["status"] != "awaiting_review":
            raise HTTPException(status_code=422, detail="Batch is not awaiting manual review")
        try:
            return await store.freeze_final_report(
                batch_id,
                allow_partial=True,
                idempotency_key=payload.idempotency_key,
            )
        except (LookupError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/batches/{batch_id}/complete-with-current-results")
    async def complete_with_current_results(
        batch_id: str,
        payload: EvaluationReviewComplete,
    ) -> dict[str, object]:
        """Freeze durable successes without resuming execution or calling providers."""
        previous = await store.command_result(payload.idempotency_key)
        if previous is not None:
            return previous
        batch = await store.get_batch(batch_id)
        if batch is None:
            raise HTTPException(status_code=404, detail="Batch not found")
        if batch["version"] != payload.expected_version:
            raise HTTPException(
                status_code=409,
                detail="The batch changed; refresh before retrying",
            )
        if batch["status"] not in {"paused", "partially_failed"}:
            raise HTTPException(
                status_code=422,
                detail="Only paused or partially failed batches can use current results",
            )
        try:
            return await store.freeze_final_report(
                batch_id,
                allow_partial=True,
                force_partial=True,
                completion_mode="current_results",
                idempotency_key=payload.idempotency_key,
            )
        except (LookupError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/pricing/official")
    async def sync_official_pricing(payload: PricingSyncRequest) -> dict[str, object]:
        """Verify official public list prices without silently keeping stale values."""
        try:
            return await official_pricing.sync(payload)
        except PricingSyncError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.get("/pricing/settings")
    async def pricing_settings() -> dict[str, object]:
        """Return the currency conversion version used by future batches."""
        return await store.active_pricing_version()

    @router.post("/pricing/settings", status_code=201)
    async def save_pricing_settings(
        payload: EvaluationPricingVersionWrite,
    ) -> dict[str, object]:
        """Append an administrator-reviewed currency conversion version."""
        return await store.save_pricing_version(
            cny_to_usd=payload.cny_to_usd,
            source_note=payload.source_note,
            default_batch_budget=payload.default_batch_budget,
            asr_rates=payload.asr_rates,
            llm_rates=payload.llm_rates,
        )

    @router.get("/dataset/audit")
    async def dataset_audit(candidate_id: str | None = None) -> dict[str, object]:
        """Return the complete 56-conversation source audit."""
        result = store.candidate_dataset_audit(candidate_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Dataset candidate is unavailable")
        return result

    async def receive_upload(file: UploadFile) -> tuple[Path, str]:
        """Stream one browser upload into the writable data volume with a hard limit."""
        original_name = Path(file.filename or "").name
        if not original_name:
            raise HTTPException(status_code=422, detail="Choose a file to upload")
        incoming = store.upload_root / f".incoming-{uuid.uuid4().hex}"
        size = 0
        try:
            with incoming.open("xb") as output:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > 512 * 1024 * 1024:
                        raise HTTPException(
                            status_code=413,
                            detail="Upload exceeds the 512 MB compressed-file limit",
                        )
                    output.write(chunk)
        except Exception:
            incoming.unlink(missing_ok=True)
            raise
        finally:
            await file.close()
        if size == 0:
            incoming.unlink(missing_ok=True)
            raise HTTPException(status_code=422, detail="The uploaded file is empty")
        return incoming, original_name

    async def import_upload(
        file: UploadFile,
        *,
        repair: bool,
        candidate_id: str | None = None,
    ) -> dict[str, object]:
        """Persist one incoming file only for the duration of safe staging."""
        incoming, original_name = await receive_upload(file)
        try:
            return await store.import_dataset_upload(
                incoming,
                original_name,
                repair=repair,
                candidate_id=candidate_id,
            )
        except PackageUploadError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        finally:
            incoming.unlink(missing_ok=True)

    @router.post("/dataset/upload")
    async def upload_dataset(
        file: Annotated[UploadFile, File()],
    ) -> dict[str, object]:
        """Validate a complete ZIP and activate it only when every check passes."""
        return await import_upload(file, repair=False)

    @router.post("/dataset/repair")
    async def repair_dataset(
        file: Annotated[UploadFile, File()],
        candidate_id: Annotated[str | None, Form()] = None,
    ) -> dict[str, object]:
        """Overlay corrected files on a candidate and re-run the complete audit."""
        return await import_upload(file, repair=True, candidate_id=candidate_id)

    @router.delete("/dataset/pending")
    async def discard_pending_dataset() -> dict[str, object]:
        """Start a clean dialog draft by removing only the unstarted candidate."""
        return await store.discard_pending_dataset()

    @router.get("/dataset/issues.csv")
    async def download_dataset_issues(candidate_id: str | None = None) -> Response:
        """Download all current validation problems as a repair checklist."""
        audit = store.candidate_dataset_audit(candidate_id)
        if audit is None:
            raise HTTPException(status_code=404, detail="Dataset candidate is unavailable")
        headers = {"Content-Disposition": 'attachment; filename="evaluation-issues.csv"'}
        return Response(_issue_csv(audit), media_type="text/csv; charset=utf-8", headers=headers)

    @router.get("/dataset/template")
    async def download_dataset_template() -> Response:
        """Download a customer-data-free package structure guide."""
        headers = {"Content-Disposition": 'attachment; filename="evaluation-upload-template.zip"'}
        return Response(_upload_template(), media_type="application/zip", headers=headers)

    @router.get("/batches")
    async def batches() -> list[dict[str, object]]:
        return await store.list_batches()

    @router.post("/batches", status_code=201)
    async def create_batch(payload: EvaluationBatchCreate) -> dict[str, object]:
        try:
            unavailable = await store.unavailable_asr_providers(payload.asr_providers)
            if unavailable:
                raise ValueError(
                    "Verify and enable these evaluation ASR resources before starting: "
                    + ", ".join(unavailable)
                )
            batch = await store.create_batch(payload)
            if start_batch is not None:
                start_batch(str(batch["id"]))
            return batch
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post("/batches/{batch_id}/actions")
    async def batch_action(
        batch_id: str,
        payload: EvaluationBatchAction,
    ) -> dict[str, object]:
        try:
            batch = await store.act_on_batch(batch_id, payload)
            if handle_batch_action is not None:
                handle_batch_action(batch_id, payload.action)
            return batch
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.delete("/batches/{batch_id}")
    async def delete_batch(
        batch_id: str,
        payload: EvaluationBatchDelete,
    ) -> dict[str, object]:
        """Delete a non-running batch after explicit confirmation."""
        try:
            return await store.delete_batch(
                batch_id,
                expected_version=payload.expected_version,
                idempotency_key=payload.idempotency_key,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.get("/reviews")
    async def reviews(
        status: str = Query(default="pending", pattern="^(pending|completed|all)$"),
    ) -> list[dict[str, object]]:
        return await store.list_reviews(status)

    @router.post("/reviews/{review_id}/decision")
    async def submit_review(
        review_id: str,
        payload: EvaluationReviewSubmit,
    ) -> dict[str, object]:
        try:
            return await store.submit_review(review_id, payload)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.get("/reviews/{review_id}/audio")
    async def review_audio(review_id: str) -> FileResponse:
        path = await store.review_audio_path(review_id)
        if path is None:
            raise HTTPException(status_code=404, detail="Review audio is unavailable")
        await store.audit_access("review_audio.played", review_id)
        return FileResponse(path, media_type="audio/wav", filename=path.name)

    @router.get("/conversations/{conversation_id}/audio")
    async def conversation_audio(conversation_id: str) -> FileResponse:
        path = store.conversation_audio_path(conversation_id)
        if path is None:
            raise HTTPException(status_code=404, detail="Conversation audio is unavailable")
        await store.audit_access("source_audio.played", conversation_id, {"kind": "full_call"})
        return FileResponse(path, media_type="audio/mpeg")

    @router.get("/conversations/{conversation_id}")
    async def conversation(conversation_id: str) -> dict[str, object]:
        """Return the parsed source workbook and actual audio metadata."""
        result = await store.get_conversation(conversation_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Conversation source is unavailable")
        await store.audit_access("source_conversation.viewed", conversation_id)
        return result

    @router.get("/conversations/{conversation_id}/user-audio")
    async def conversation_user_audio(conversation_id: str) -> FileResponse:
        path = store.conversation_user_audio_path(conversation_id)
        if path is None:
            raise HTTPException(status_code=404, detail="Customer audio is unavailable")
        await store.audit_access("source_audio.played", conversation_id, {"kind": "customer"})
        return FileResponse(path, media_type="audio/wav")

    @router.get("/benchmarks")
    async def benchmarks(
        language: str = "all",
        scenario_tag: str = "all",
        source: str = "all",
        case_type: str = Query(default="all", pattern="^(all|good|bad)$"),
        search: str = Query(default="", max_length=5000),
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ) -> dict[str, object]:
        return await store.list_benchmarks(
            language=language,
            scenario_tag=scenario_tag,
            source=source,
            case_type=case_type,
            search=search,
            limit=limit,
            offset=offset,
        )

    @router.post("/benchmarks/export")
    async def export_benchmarks(payload: BenchmarkExportRequest) -> JSONResponse:
        result = await store.list_benchmarks(
            language=payload.language,
            scenario_tag=payload.scenario_tag,
            source=payload.source,
            case_type=payload.case_type,
            search=payload.search,
            limit=5000,
            ids=payload.sample_ids or None,
        )
        rows = result["items"]
        if not rows:
            raise HTTPException(status_code=422, detail="No Benchmark samples match this export")
        frozen_request = {
            "sample_ids": [str(row["id"]) for row in rows],
            "language": payload.language,
            "scenario_tag": payload.scenario_tag,
            "source": payload.source,
            "case_type": payload.case_type,
            "search": payload.search,
        }
        export = await store.create_benchmark_export(frozen_request)
        schedule_benchmark_export(str(export["id"]))
        return JSONResponse(
            status_code=202,
            content={
                **export,
                "status_url": f"/api/evaluation/benchmarks/exports/{export['id']}",
            },
        )

    @router.get("/benchmarks/{benchmark_id}/audio")
    async def benchmark_audio(benchmark_id: str) -> FileResponse:
        path = await store.benchmark_audio_path(benchmark_id)
        if path is None:
            raise HTTPException(status_code=404, detail="Benchmark clip is unavailable")
        await store.audit_access("benchmark_audio.played", benchmark_id)
        return FileResponse(path, media_type="audio/wav")

    @router.get("/benchmarks/{benchmark_id}/revisions")
    async def benchmark_revisions(benchmark_id: str) -> list[dict[str, object]]:
        revisions = await store.benchmark_revisions(benchmark_id)
        if not revisions:
            raise HTTPException(status_code=404, detail="Benchmark sample was not found")
        await store.audit_access("benchmark.viewed", benchmark_id)
        return revisions

    @router.patch("/benchmarks/{benchmark_id}")
    async def update_benchmark(
        benchmark_id: str,
        payload: BenchmarkUpdate,
    ) -> dict[str, object]:
        try:
            return await store.update_benchmark(
                benchmark_id,
                label=payload.label,
                language=payload.language,
                scenario_tag=payload.scenario_tag,
                expected_revision=payload.expected_revision,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.delete("/benchmarks/{benchmark_id}")
    async def delete_benchmark(benchmark_id: str) -> dict[str, object]:
        try:
            return await store.delete_benchmark(benchmark_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/benchmarks/exports/{export_id}")
    async def benchmark_export_status(export_id: str) -> dict[str, object]:
        export = await store.get_benchmark_export(export_id)
        if export is None:
            raise HTTPException(status_code=404, detail="Benchmark export was not found")
        if export["status"] == "pending":
            schedule_benchmark_export(export_id)
        result: dict[str, object] = dict(export)
        result["status_url"] = f"/api/evaluation/benchmarks/exports/{export_id}"
        if export["status"] == "ready":
            result["download_url"] = f"/api/evaluation/benchmarks/exports/{export_id}/download"
        return result

    @router.get("/benchmarks/exports/{export_id}/download")
    async def download_benchmark_export(export_id: str) -> FileResponse:
        export = await store.get_benchmark_export(export_id)
        if export is None:
            raise HTTPException(status_code=404, detail="Benchmark export was not found")
        if export["status"] == "expired":
            raise HTTPException(status_code=410, detail="Benchmark export has expired")
        if export["status"] != "ready":
            raise HTTPException(
                status_code=409,
                detail=f"Benchmark export is {export['status']}",
            )
        artifact = await store.benchmark_export_artifact(export_id)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Benchmark export artifact is unavailable")
        await store.audit_benchmark_export_download(export_id)
        return FileResponse(
            artifact,
            media_type="application/zip",
            filename="asr-benchmark.zip",
        )

    return router
