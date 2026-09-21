"""SQLite storage for source-backed ASR evaluation imports."""

from __future__ import annotations

import asyncio
import importlib
import io
import json
import os
import re
import shutil
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import aiosqlite
import soundfile as sf  # type: ignore[import-untyped]

from src.evaluation.dataset import ConversationAudit, DatasetAudit, audit_dataset
from src.evaluation.imports import (
    PackageUploadError,
    extract_package_archive,
    install_single_repair,
)
from src.evaluation.models import (
    EvaluationBatchAction,
    EvaluationBatchCreate,
    EvaluationReviewSubmit,
)
from src.evaluation.pricing import normalize_pricing_model_id
from src.evaluation.prompts import (
    EVALUATION_CONTEXT,
    PASS_ONE_SYSTEM_PROMPT,
    PASS_TWO_SYSTEM_PROMPT,
    REFERENCE_DICTIONARIES,
    SCENARIO_TAGS,
)

_REAL_SOURCE_MIGRATION = "real_source_migration_v1"
_ACTIVE_DATASET_META = "evaluation.active_dataset"
_PENDING_DATASET_META = "evaluation.pending_dataset"
_SAFE_CONVERSATION_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_CJK_TEXT = re.compile(r"[\u3400-\u9fff]")

_ASR_CAPABILITY_PROFILES: dict[str, dict[str, Any]] = {
    "soniox": {
        "display_name": "Soniox",
        "endpoint": "https://api.soniox.com",
        "model_id": "stt-async-v5",
        "parameters": {
            "language_hints": ["ar", "en"],
            "enable_language_identification": True,
            "enable_speaker_diarization": True,
        },
        "input_constraints": {
            "accepted_formats": ["mp3", "wav", "m4a", "mp4", "flac", "ogg", "webm"],
            "max_duration_hours": 5,
        },
    },
    "speechmatics": {
        "display_name": "Speechmatics",
        "endpoint": "https://asr.api.speechmatics.com",
        "model_id": "melia-1",
        "parameters": {
            "language": "ar",
            "operating_point": "enhanced",
            "diarization": "speaker",
        },
        "input_constraints": {
            "accepted_formats": ["mp3", "wav"],
            "mode": "batch",
        },
    },
    "elevenlabs": {
        "display_name": "ElevenLabs",
        "endpoint": "https://api.elevenlabs.io",
        "model_id": "scribe_v2",
        "parameters": {
            "language_code": None,
            "diarize": True,
            "timestamps_granularity": "word",
            "webhook": True,
        },
        "input_constraints": {
            "accepted_formats": ["mp3", "wav"],
            "max_source_bytes": 2_000_000_000,
        },
    },
}


def _utcnow() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _ten_year_retention_expiry(created_at: str) -> str:
    """Return the fixed evaluation-retention boundary, including leap-day safety."""
    created = datetime.fromisoformat(created_at)
    try:
        expiry = created.replace(year=created.year + 10)
    except ValueError:
        expiry = created.replace(year=created.year + 10, day=28)
    return expiry.isoformat(timespec="seconds")


class EvaluationStore:
    """Persist source imports, real batch state, reviews, and Benchmark rows."""

    def __init__(self, database_path: Path, dataset_root: Path) -> None:
        """Configure storage and the initial read-only evaluation dataset root."""
        self.database_path = database_path
        self.seed_dataset_root = dataset_root
        self.dataset_root = dataset_root
        self.upload_root = database_path.parent / "evaluation-datasets"
        self.export_root = database_path.parent / "evaluation-exports"
        self.benchmark_clip_root = database_path.parent / "evaluation-benchmark-clips"
        self.asr_clip_root = database_path.parent / "evaluation-asr-clips"
        self._source_audit: DatasetAudit | None = None
        self._active_dataset: dict[str, Any] | None = None
        self._pending_dataset: dict[str, Any] | None = None
        self._pending_audit: DatasetAudit | None = None
        self._import_lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Create storage, remove legacy simulations once, and import real source data."""
        database_preexisted = self.database_path.exists()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.upload_root.mkdir(parents=True, exist_ok=True)
        self.export_root.mkdir(parents=True, exist_ok=True)
        self.benchmark_clip_root.mkdir(parents=True, exist_ok=True)
        self.asr_clip_root.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.database_path) as database:
            await database.executescript(
                """
                PRAGMA foreign_keys = ON;
                CREATE TABLE IF NOT EXISTS evaluation_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evaluation_batches (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    context_name TEXT NOT NULL,
                    input_count INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    progress INTEGER NOT NULL,
                    suspected_numerator INTEGER,
                    denominator INTEGER,
                    excluded_count INTEGER NOT NULL DEFAULT 0,
                    cost REAL NOT NULL,
                    budget REAL NOT NULL,
                    review_total INTEGER NOT NULL DEFAULT 0,
                    review_completed INTEGER NOT NULL DEFAULT 0,
                    report_type TEXT,
                    simulation_started_at TEXT,
                    providers_json TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS evaluation_reviews (
                    id TEXT PRIMARY KEY,
                    fixture_key TEXT NOT NULL,
                    batch_id TEXT NOT NULL REFERENCES evaluation_batches(id),
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    decision TEXT,
                    label TEXT,
                    language TEXT NOT NULL,
                    scenario_tag TEXT NOT NULL,
                    reviewed_at TEXT,
                    version INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS evaluation_benchmarks (
                    id TEXT PRIMARY KEY,
                    batch_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    case_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    language TEXT NOT NULL,
                    scenario_tag TEXT NOT NULL,
                    label TEXT NOT NULL,
                    audio_start_s REAL NOT NULL,
                    audio_end_s REAL NOT NULL,
                    origin TEXT NOT NULL DEFAULT 'suspect_candidate',
                    positioning_quality TEXT NOT NULL DEFAULT 'unavailable',
                    clip_status TEXT NOT NULL DEFAULT 'pending',
                    clip_path TEXT,
                    clip_error TEXT,
                    trace_json TEXT NOT NULL DEFAULT '{}',
                    revision INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    UNIQUE(batch_id, conversation_id, event_id)
                );
                CREATE TABLE IF NOT EXISTS evaluation_commands (
                    idempotency_key TEXT PRIMARY KEY,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evaluation_benchmark_revisions (
                    id TEXT PRIMARY KEY,
                    benchmark_id TEXT NOT NULL REFERENCES evaluation_benchmarks(id),
                    revision INTEGER NOT NULL,
                    label TEXT NOT NULL,
                    language TEXT NOT NULL,
                    scenario_tag TEXT NOT NULL,
                    source TEXT NOT NULL,
                    changed_at TEXT NOT NULL,
                    UNIQUE(benchmark_id, revision)
                );
                CREATE TABLE IF NOT EXISTS evaluation_batch_leases (
                    batch_id TEXT PRIMARY KEY REFERENCES evaluation_batches(id) ON DELETE CASCADE,
                    owner_id TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evaluation_audit (
                    id TEXT PRIMARY KEY,
                    action TEXT NOT NULL,
                    object_id TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evaluation_source_conversations (
                    conversation_id TEXT PRIMARY KEY,
                    history_path TEXT,
                    record_path TEXT,
                    user_record_path TEXT,
                    detected_language TEXT NOT NULL,
                    event_count INTEGER NOT NULL,
                    user_event_count INTEGER NOT NULL,
                    robot_event_count INTEGER NOT NULL,
                    record_audio_json TEXT,
                    user_audio_json TEXT,
                    issues_json TEXT NOT NULL,
                    valid INTEGER NOT NULL,
                    imported_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evaluation_source_events (
                    conversation_id TEXT NOT NULL
                        REFERENCES evaluation_source_conversations(conversation_id)
                        ON DELETE CASCADE,
                    event_id TEXT NOT NULL,
                    source_row INTEGER NOT NULL,
                    time_s REAL NOT NULL,
                    speaker TEXT NOT NULL,
                    text TEXT NOT NULL,
                    PRIMARY KEY (conversation_id, event_id)
                );
                CREATE TABLE IF NOT EXISTS evaluation_llm_models (
                    provider TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    base_url_host TEXT NOT NULL,
                    source TEXT NOT NULL,
                    diagnostic_id TEXT NOT NULL,
                    verified_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (provider, model_id)
                );
                CREATE TABLE IF NOT EXISTS evaluation_connections (
                    provider TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    base_url TEXT NOT NULL,
                    encrypted_api_key TEXT NOT NULL,
                    status TEXT NOT NULL,
                    diagnostic_id TEXT NOT NULL,
                    last_model_id TEXT,
                    verified_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evaluation_asr_capabilities (
                    provider TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    parameters_json TEXT NOT NULL,
                    input_constraints_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    diagnostic_id TEXT,
                    validation_json TEXT NOT NULL DEFAULT '{}',
                    verified_at TEXT,
                    updated_at TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS evaluation_scenario_tags (
                    id TEXT PRIMARY KEY,
                    tag_key TEXT NOT NULL UNIQUE,
                    current_version INTEGER NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    deleted_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evaluation_scenario_tag_versions (
                    tag_id TEXT NOT NULL
                        REFERENCES evaluation_scenario_tags(id) ON DELETE RESTRICT,
                    version INTEGER NOT NULL,
                    name_en TEXT NOT NULL,
                    name_zh TEXT NOT NULL,
                    description_en TEXT NOT NULL,
                    description_zh TEXT NOT NULL,
                    tag_type TEXT NOT NULL,
                    examples_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (tag_id, version)
                );
                CREATE TABLE IF NOT EXISTS evaluation_reference_dictionaries (
                    id TEXT PRIMARY KEY,
                    dictionary_key TEXT NOT NULL UNIQUE,
                    current_version INTEGER NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evaluation_reference_dictionary_versions (
                    dictionary_id TEXT NOT NULL
                        REFERENCES evaluation_reference_dictionaries(id) ON DELETE RESTRICT,
                    version INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (dictionary_id, version)
                );
                CREATE TABLE IF NOT EXISTS evaluation_contexts (
                    id TEXT PRIMARY KEY,
                    context_key TEXT NOT NULL UNIQUE,
                    current_version INTEGER NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    is_default INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evaluation_context_versions (
                    context_id TEXT NOT NULL REFERENCES evaluation_contexts(id) ON DELETE RESTRICT,
                    version INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (context_id, version)
                );
                CREATE TABLE IF NOT EXISTS evaluation_prompt_templates (
                    template_key TEXT PRIMARY KEY,
                    current_version INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evaluation_prompt_template_versions (
                    template_key TEXT NOT NULL REFERENCES evaluation_prompt_templates(template_key)
                        ON DELETE RESTRICT,
                    version INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (template_key, version)
                );
                CREATE TABLE IF NOT EXISTS evaluation_pass1_runs (
                    batch_id TEXT NOT NULL REFERENCES evaluation_batches(id) ON DELETE CASCADE,
                    conversation_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    result_json TEXT,
                    error TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (batch_id, conversation_id)
                );
                CREATE TABLE IF NOT EXISTS evaluation_pass1_groups (
                    batch_id TEXT NOT NULL REFERENCES evaluation_batches(id) ON DELETE CASCADE,
                    group_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    conversation_ids_json TEXT NOT NULL,
                    estimated_input_tokens INTEGER NOT NULL,
                    reserved_output_tokens INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    result_json TEXT,
                    error TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (batch_id, group_id),
                    UNIQUE (batch_id, idempotency_key)
                );
                CREATE TABLE IF NOT EXISTS evaluation_asr_runs (
                    batch_id TEXT NOT NULL REFERENCES evaluation_batches(id) ON DELETE CASCADE,
                    provider TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    remote_job_id TEXT,
                    result_json TEXT,
                    error TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (batch_id, provider, conversation_id)
                );
                CREATE TABLE IF NOT EXISTS evaluation_case_asr_runs (
                    batch_id TEXT NOT NULL REFERENCES evaluation_batches(id) ON DELETE CASCADE,
                    provider TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    remote_job_id TEXT,
                    clip_path TEXT,
                    clip_start_s REAL,
                    clip_end_s REAL,
                    result_json TEXT,
                    error TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (batch_id, provider, conversation_id, event_id)
                );
                CREATE TABLE IF NOT EXISTS evaluation_pass2_runs (
                    batch_id TEXT NOT NULL REFERENCES evaluation_batches(id) ON DELETE CASCADE,
                    conversation_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    result_json TEXT,
                    error TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (batch_id, conversation_id, event_id)
                );
                CREATE TABLE IF NOT EXISTS evaluation_pass2_groups (
                    batch_id TEXT NOT NULL REFERENCES evaluation_batches(id) ON DELETE CASCADE,
                    group_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    conversation_ids_json TEXT NOT NULL,
                    case_keys_json TEXT NOT NULL,
                    estimated_input_tokens INTEGER NOT NULL,
                    reserved_output_tokens INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    result_json TEXT,
                    error TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (batch_id, group_id),
                    UNIQUE (batch_id, idempotency_key)
                );
                CREATE TABLE IF NOT EXISTS evaluation_reports (
                    report_id TEXT PRIMARY KEY,
                    batch_id TEXT NOT NULL REFERENCES evaluation_batches(id) ON DELETE CASCADE,
                    version INTEGER NOT NULL,
                    report_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE (batch_id, version)
                );
                CREATE TABLE IF NOT EXISTS evaluation_cost_ledger (
                    idempotency_key TEXT PRIMARY KEY,
                    batch_id TEXT NOT NULL REFERENCES evaluation_batches(id) ON DELETE CASCADE,
                    category TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL DEFAULT 0,
                    cached_input_tokens INTEGER NOT NULL DEFAULT 0,
                    reasoning_tokens INTEGER NOT NULL DEFAULT 0,
                    output_tokens INTEGER NOT NULL DEFAULT 0,
                    audio_seconds REAL NOT NULL DEFAULT 0,
                    estimated_cost REAL,
                    currency TEXT NOT NULL DEFAULT 'USD',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evaluation_cost_reservations (
                    idempotency_key TEXT PRIMARY KEY,
                    batch_id TEXT NOT NULL REFERENCES evaluation_batches(id) ON DELETE CASCADE,
                    estimated_usd REAL NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evaluation_telemetry (
                    id TEXT PRIMARY KEY,
                    batch_id TEXT NOT NULL REFERENCES evaluation_batches(id) ON DELETE CASCADE,
                    trace_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    event TEXT NOT NULL,
                    provider TEXT,
                    outcome TEXT NOT NULL,
                    attempt INTEGER NOT NULL DEFAULT 1,
                    latency_ms REAL,
                    queue_depth INTEGER,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evaluation_pricing_versions (
                    version INTEGER PRIMARY KEY AUTOINCREMENT,
                    base_currency TEXT NOT NULL,
                    cny_to_usd REAL NOT NULL,
                    rates_json TEXT NOT NULL DEFAULT '{}',
                    default_batch_budget REAL NOT NULL DEFAULT 10,
                    source_note TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evaluation_proposed_tag_actions (
                    report_id TEXT NOT NULL REFERENCES evaluation_reports(report_id),
                    proposal_key TEXT NOT NULL,
                    tag_id TEXT NOT NULL REFERENCES evaluation_scenario_tags(id),
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (report_id, proposal_key)
                );
                CREATE TABLE IF NOT EXISTS evaluation_benchmark_exports (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    artifact_path TEXT,
                    manifest_json TEXT NOT NULL DEFAULT '[]',
                    error TEXT,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evaluation_elevenlabs_jobs (
                    request_id TEXT PRIMARY KEY,
                    correlation_id TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    result_json TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            if os.getenv("VOICE_AGENT_DEPLOYMENT_ENVIRONMENT") == "production":
                provenance = await (
                    await database.execute(
                        "SELECT value FROM evaluation_meta WHERE key=?",
                        ("deployment.provenance",),
                    )
                ).fetchone()
                if database_preexisted and (
                    provenance is None or str(provenance[0]) != "production"
                ):
                    raise RuntimeError(
                        "Refusing an Evaluation database without production provenance"
                    )
                if not database_preexisted:
                    await database.execute(
                        """INSERT INTO evaluation_meta (key,value,updated_at)
                           VALUES (?,?,?)""",
                        ("deployment.provenance", "production", _utcnow()),
                    )
            benchmark_columns = {
                str(row[1])
                for row in await (
                    await database.execute("PRAGMA table_info(evaluation_benchmarks)")
                ).fetchall()
            }
            if "origin" not in benchmark_columns:
                await database.execute(
                    """ALTER TABLE evaluation_benchmarks ADD COLUMN origin TEXT
                       NOT NULL DEFAULT 'suspect_candidate'"""
                )
            if "positioning_quality" not in benchmark_columns:
                await database.execute(
                    """ALTER TABLE evaluation_benchmarks ADD COLUMN positioning_quality TEXT
                       NOT NULL DEFAULT 'unavailable'"""
                )
            for column, definition in (
                ("clip_status", "TEXT NOT NULL DEFAULT 'pending'"),
                ("clip_path", "TEXT"),
                ("clip_error", "TEXT"),
                ("trace_json", "TEXT NOT NULL DEFAULT '{}'"),
                ("revision", "INTEGER NOT NULL DEFAULT 1"),
            ):
                if column not in benchmark_columns:
                    await database.execute(
                        f"ALTER TABLE evaluation_benchmarks ADD COLUMN {column} {definition}"
                    )
            pricing_columns = {
                str(row[1])
                for row in await (
                    await database.execute("PRAGMA table_info(evaluation_pricing_versions)")
                ).fetchall()
            }
            if "rates_json" not in pricing_columns:
                await database.execute(
                    "ALTER TABLE evaluation_pricing_versions ADD COLUMN rates_json "
                    "TEXT NOT NULL DEFAULT '{}'"
                )
            if "default_batch_budget" not in pricing_columns:
                await database.execute(
                    """ALTER TABLE evaluation_pricing_versions ADD COLUMN default_batch_budget REAL
                       NOT NULL DEFAULT 10"""
                )
            self._active_dataset = await self._load_dataset_meta(database, _ACTIVE_DATASET_META)
            self._pending_dataset = await self._load_dataset_meta(database, _PENDING_DATASET_META)
            active_root = self._managed_dataset_path(self._active_dataset)
            if active_root is not None:
                self.dataset_root = active_root
                self._source_audit = audit_dataset(active_root, expected_conversations=None)
            else:
                self.dataset_root = self.seed_dataset_root
                self._active_dataset = None
                self._source_audit = audit_dataset(self.seed_dataset_root)
            pending_root = self._managed_dataset_path(self._pending_dataset)
            if pending_root is not None:
                self._pending_audit = audit_dataset(
                    pending_root,
                    expected_conversations=None,
                )
            else:
                self._pending_dataset = None
                self._pending_audit = None
            await self._remove_legacy_simulations(database)
            await self._seed_scenario_tags(database)
            await self._seed_evaluation_configuration(database)
            await self._seed_asr_capabilities(database)
            await database.execute(
                """INSERT INTO evaluation_pricing_versions
                   (base_currency,cny_to_usd,rates_json,default_batch_budget,source_note,created_at)
                   SELECT 'USD',0.14,'{}',10,'Initial administrator-review draft',?
                   WHERE NOT EXISTS (SELECT 1 FROM evaluation_pricing_versions)""",
                (_utcnow(),),
            )
            await self._migrate_seed_prompt_contracts(database)
            await self._sync_source_data(database, self._source_audit)
            await database.commit()
        await self.recover_pending_benchmark_clips()
        await self.recover_missing_preliminary_reports()

    async def _seed_asr_capabilities(self, database: aiosqlite.Connection) -> None:
        """Seed truthful offline-ASR capability contracts without inventing validation."""
        now = _utcnow()
        for provider, profile in _ASR_CAPABILITY_PROFILES.items():
            await database.execute(
                """INSERT OR IGNORE INTO evaluation_asr_capabilities (
                       provider,display_name,endpoint,model_id,parameters_json,
                       input_constraints_json,status,enabled,diagnostic_id,
                       validation_json,verified_at,updated_at,version
                   ) VALUES (?,?,?,?,?,?,'pending',1,NULL,'{}',NULL,?,1)""",
                (
                    provider,
                    profile["display_name"],
                    profile["endpoint"],
                    profile["model_id"],
                    _json(profile["parameters"]),
                    _json(profile["input_constraints"]),
                    now,
                ),
            )
            row = await (
                await database.execute(
                    """SELECT endpoint,model_id,parameters_json,input_constraints_json
                       FROM evaluation_asr_capabilities WHERE provider=?""",
                    (provider,),
                )
            ).fetchone()
            expected = (
                profile["endpoint"],
                profile["model_id"],
                _json(profile["parameters"]),
                _json(profile["input_constraints"]),
            )
            if row is not None and tuple(row) != expected:
                await database.execute(
                    """UPDATE evaluation_asr_capabilities
                       SET display_name=?,endpoint=?,model_id=?,parameters_json=?,
                           input_constraints_json=?,status='pending',diagnostic_id=NULL,
                           validation_json='{}',verified_at=NULL,updated_at=?,version=version+1
                       WHERE provider=?""",
                    (
                        profile["display_name"],
                        *expected,
                        now,
                        provider,
                    ),
                )
            connection = await (
                await database.execute(
                    """SELECT status,diagnostic_id,verified_at,base_url
                       FROM evaluation_connections WHERE provider=? AND kind='asr'""",
                    (provider,),
                )
            ).fetchone()
            if connection is not None and connection[0] == "verified":
                await database.execute(
                    """UPDATE evaluation_asr_capabilities
                       SET status='verified',diagnostic_id=?,verified_at=?,updated_at=?,
                           validation_json=? WHERE provider=? AND status='pending'""",
                    (
                        connection[1],
                        connection[2],
                        now,
                        _json({"endpoint_authenticated": True, "contract_validated": True}),
                        provider,
                    ),
                )

    async def _seed_evaluation_configuration(self, database: aiosqlite.Connection) -> None:
        """Seed reviewed fixtures once without overwriting administrator versions."""
        now = _utcnow()
        dictionary_id = "dict-riyadbank-branches"
        dictionary_payload = {
            "name": "RiyadBank branch entities",
            "purpose": "Branch names, aliases, codes, locales, and metadata.",
            "schema_fields": REFERENCE_DICTIONARIES[0]["schema"],
            "entries": REFERENCE_DICTIONARIES[0]["entries"],
        }
        await database.execute(
            """INSERT OR IGNORE INTO evaluation_reference_dictionaries
               VALUES(?,?,1,1,?,?)""",
            (dictionary_id, "riyadbank_branches", now, now),
        )
        await database.execute(
            """INSERT OR IGNORE INTO evaluation_reference_dictionary_versions
               VALUES(?,1,?,?)""",
            (dictionary_id, _json(dictionary_payload), now),
        )
        context_payload = {
            **EVALUATION_CONTEXT,
            "dictionary_version_ids": [f"{dictionary_id}:1"],
        }
        await database.execute(
            """INSERT OR IGNORE INTO evaluation_contexts
               VALUES('context-riyadbank','riyadbank',3,1,1,?,?)""",
            (now, now),
        )
        await database.execute(
            """INSERT OR IGNORE INTO evaluation_context_versions
               VALUES('context-riyadbank',3,?,?)""",
            (_json(context_payload), now),
        )
        for template_key, content in (
            ("pass_1", PASS_ONE_SYSTEM_PROMPT),
            ("pass_2", PASS_TWO_SYSTEM_PROMPT),
        ):
            await database.execute(
                """INSERT OR IGNORE INTO evaluation_prompt_templates
                   VALUES(?,1,?,?)""",
                (template_key, _json({"content": content}), now),
            )
            await database.execute(
                """INSERT OR IGNORE INTO evaluation_prompt_template_versions
                   SELECT template_key,current_version,payload_json,updated_at
                   FROM evaluation_prompt_templates WHERE template_key=?""",
                (template_key,),
            )

    async def _migrate_seed_prompt_contracts(self, database: aiosqlite.Connection) -> None:
        """Append a reviewed contract revision when mandatory behavior is absent."""
        required_slots = {
            "pass_1": (
                "request_group_id",
                "conversations",
                "evaluation_context",
                "reference_dictionaries",
            ),
            "pass_2": (
                "request_group_id",
                "candidate_case",
                "conversation_history",
                "asr_results",
            ),
        }
        approved = {"pass_1": PASS_ONE_SYSTEM_PROMPT, "pass_2": PASS_TWO_SYSTEM_PROMPT}
        policy_markers = {
            "pass_1": "唯一质检目标是检测线上 ASR",
            "pass_2": "纯用户事件切片重转录结果",
        }
        for template_key, slots in required_slots.items():
            row = await (
                await database.execute(
                    """SELECT current_version,payload_json FROM evaluation_prompt_templates
                       WHERE template_key=?""",
                    (template_key,),
                )
            ).fetchone()
            if row is None:
                continue
            current = json.loads(str(row[1])).get("content", "")
            if (
                all(f"{{{{{slot}}}}}" in current for slot in slots)
                and policy_markers[template_key] in current
            ):
                continue
            now = _utcnow()
            version = int(row[0]) + 1
            payload = _json({"content": approved[template_key]})
            await database.execute(
                """INSERT INTO evaluation_prompt_template_versions
                   (template_key,version,payload_json,created_at) VALUES(?,?,?,?)""",
                (template_key, version, payload, now),
            )
            await database.execute(
                """UPDATE evaluation_prompt_templates
                   SET current_version=?,payload_json=?,updated_at=? WHERE template_key=?""",
                (version, payload, now, template_key),
            )

    async def _seed_scenario_tags(self, database: aiosqlite.Connection) -> None:
        """Insert accepted defaults once without overwriting administrator versions."""
        now = _utcnow()
        for tag in SCENARIO_TAGS:
            tag_key = str(tag["key"])
            tag_id = f"tag-{tag_key}"
            await database.execute(
                """INSERT OR IGNORE INTO evaluation_scenario_tags (
                    id,tag_key,current_version,enabled,deleted_at,created_at,updated_at
                ) VALUES (?,?,1,?,NULL,?,?)""",
                (tag_id, tag_key, int(bool(tag.get("enabled", True))), now, now),
            )
            await database.execute(
                """INSERT OR IGNORE INTO evaluation_scenario_tag_versions (
                    tag_id,version,name_en,name_zh,description_en,description_zh,
                    tag_type,examples_json,created_at
                ) VALUES (?,1,?,?,?,?,?,?,?)""",
                (
                    tag_id,
                    tag["name_en"],
                    tag["name_zh"],
                    tag["description_en"],
                    tag["description_zh"],
                    tag["tag_type"],
                    _json(tag.get("examples", [])),
                    now,
                ),
            )

    async def list_scenario_tags(self) -> list[dict[str, Any]]:
        """Return only tags available in the current taxonomy."""
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            rows = await (
                await database.execute(
                    """SELECT t.id,t.tag_key,t.current_version,t.enabled,t.updated_at,
                              v.name_en,v.name_zh,v.description_en,v.description_zh,
                              v.tag_type,v.examples_json,
                              (SELECT COUNT(*) FROM evaluation_benchmarks b
                               LEFT JOIN evaluation_batches batch ON batch.id=b.batch_id
                               WHERE COALESCE(
                                   json_extract(batch.snapshot_json,'$.result_disposition'),
                                   'formal'
                               ) != 'audit_only'
                                 AND EXISTS (
                                   SELECT 1 FROM evaluation_scenario_tag_versions history
                                   WHERE history.tag_id=t.id
                                     AND b.scenario_tag IN (history.name_en,history.name_zh)
                               )) AS reference_count
                       FROM evaluation_scenario_tags t
                       JOIN evaluation_scenario_tag_versions v
                         ON v.tag_id=t.id AND v.version=t.current_version
                       WHERE t.deleted_at IS NULL
                       ORDER BY t.created_at,t.id"""
                )
            ).fetchall()
        return [
            {
                **dict(row),
                "enabled": bool(row["enabled"]),
                "examples": json.loads(row["examples_json"]),
            }
            for row in rows
        ]

    async def create_scenario_tag(self, payload: Any) -> dict[str, Any]:
        """Create a stable tag and its first immutable version."""
        now = _utcnow()
        tag_id = f"tag-{uuid.uuid4().hex}"
        tag_key = f"custom-{uuid.uuid4().hex[:12]}"
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute("PRAGMA foreign_keys = ON")
            duplicate = await (
                await database.execute(
                    """SELECT 1 FROM evaluation_scenario_tag_versions v
                       JOIN evaluation_scenario_tags t ON t.id=v.tag_id
                       WHERE t.deleted_at IS NULL AND v.version=t.current_version
                         AND (lower(v.name_en)=lower(?) OR v.name_zh=?)""",
                    (payload.name_en.strip(), payload.name_zh.strip()),
                )
            ).fetchone()
            if duplicate:
                raise ValueError("A current scenario tag already uses this name")
            await database.execute(
                "INSERT INTO evaluation_scenario_tags VALUES(?,?,1,1,NULL,?,?)",
                (tag_id, tag_key, now, now),
            )
            await database.execute(
                """INSERT INTO evaluation_scenario_tag_versions VALUES(?,1,?,?,?,?,?,?,?)""",
                (
                    tag_id,
                    payload.name_en.strip(),
                    payload.name_zh.strip(),
                    payload.description_en.strip(),
                    payload.description_zh.strip(),
                    payload.tag_type,
                    _json(payload.examples),
                    now,
                ),
            )
            await self._audit(database, "scenario_tag.created", tag_id, {"version": 1})
            await database.commit()
        return await self.get_scenario_tag(tag_id)

    async def get_scenario_tag(self, tag_id: str) -> dict[str, Any]:
        """Return one current non-deleted scenario-tag version."""
        rows = await self.list_scenario_tags()
        for row in rows:
            if row["id"] == tag_id:
                return row
        raise LookupError("Scenario tag not found")

    async def update_scenario_tag(self, tag_id: str, payload: Any) -> dict[str, Any]:
        """Append a version and preserve every historical snapshot."""
        now = _utcnow()
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute("PRAGMA foreign_keys = ON")
            row = await (
                await database.execute(
                    """SELECT current_version FROM evaluation_scenario_tags
                       WHERE id=? AND deleted_at IS NULL""",
                    (tag_id,),
                )
            ).fetchone()
            if row is None:
                raise LookupError("Scenario tag not found")
            current = int(row[0])
            if payload.expected_version != current:
                raise RuntimeError("Scenario tag changed; reload before saving")
            next_version = current + 1
            await database.execute(
                """INSERT INTO evaluation_scenario_tag_versions VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    tag_id,
                    next_version,
                    payload.name_en.strip(),
                    payload.name_zh.strip(),
                    payload.description_en.strip(),
                    payload.description_zh.strip(),
                    payload.tag_type,
                    _json(payload.examples),
                    now,
                ),
            )
            await database.execute(
                "UPDATE evaluation_scenario_tags SET current_version=?,updated_at=? WHERE id=?",
                (next_version, now, tag_id),
            )
            await self._audit(
                database,
                "scenario_tag.version_created",
                tag_id,
                {"previous_version": current, "version": next_version},
            )
            await database.commit()
        return await self.get_scenario_tag(tag_id)

    async def set_scenario_tag_status(
        self, tag_id: str, *, enabled: bool, expected_version: int
    ) -> dict[str, Any]:
        """Change only current availability without mutating version content."""
        now = _utcnow()
        async with aiosqlite.connect(self.database_path) as database:
            row = await (
                await database.execute(
                    """SELECT current_version FROM evaluation_scenario_tags
                       WHERE id=? AND deleted_at IS NULL""",
                    (tag_id,),
                )
            ).fetchone()
            if row is None:
                raise LookupError("Scenario tag not found")
            if int(row[0]) != expected_version:
                raise RuntimeError("Scenario tag changed; reload before updating status")
            await database.execute(
                "UPDATE evaluation_scenario_tags SET enabled=?,updated_at=? WHERE id=?",
                (int(enabled), now, tag_id),
            )
            await self._audit(
                database,
                "scenario_tag.enabled" if enabled else "scenario_tag.disabled",
                tag_id,
                {"version": expected_version},
            )
            await database.commit()
        return await self.get_scenario_tag(tag_id)

    async def delete_scenario_tag(self, tag_id: str, expected_version: int) -> None:
        """Tombstone one tag so historical version rows remain readable."""
        now = _utcnow()
        async with aiosqlite.connect(self.database_path) as database:
            row = await (
                await database.execute(
                    """SELECT current_version FROM evaluation_scenario_tags
                       WHERE id=? AND deleted_at IS NULL""",
                    (tag_id,),
                )
            ).fetchone()
            if row is None:
                raise LookupError("Scenario tag not found")
            if int(row[0]) != expected_version:
                raise RuntimeError("Scenario tag changed; reload before deleting")
            await database.execute(
                """UPDATE evaluation_scenario_tags
                   SET enabled=0,deleted_at=?,updated_at=? WHERE id=?""",
                (now, now, tag_id),
            )
            await self._audit(
                database,
                "scenario_tag.deleted",
                tag_id,
                {"version": expected_version},
            )
            await database.commit()

    async def list_reference_dictionaries(self) -> list[dict[str, Any]]:
        """Return current generic dictionary versions with complete entries."""
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            rows = await (
                await database.execute(
                    """SELECT d.id,d.dictionary_key,d.current_version,d.enabled,d.updated_at,
                              v.payload_json
                       FROM evaluation_reference_dictionaries d
                       JOIN evaluation_reference_dictionary_versions v
                         ON v.dictionary_id=d.id AND v.version=d.current_version
                       ORDER BY d.created_at,d.id"""
                )
            ).fetchall()
        return [
            {
                **{key: row[key] for key in row.keys() if key != "payload_json"},
                **json.loads(row["payload_json"]),
                "version_id": f"{row['id']}:{row['current_version']}",
                "enabled": bool(row["enabled"]),
            }
            for row in rows
        ]

    async def write_reference_dictionary(
        self,
        payload: Any,
        dictionary_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a dictionary or append a new immutable version."""
        now = _utcnow()
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            await database.execute("BEGIN IMMEDIATE")
            if dictionary_id is None:
                dictionary_id = f"dict-{uuid.uuid4().hex}"
                key = payload.dictionary_key or f"custom_{uuid.uuid4().hex[:12]}"
                duplicate = await (
                    await database.execute(
                        "SELECT 1 FROM evaluation_reference_dictionaries WHERE dictionary_key=?",
                        (key,),
                    )
                ).fetchone()
                if duplicate:
                    raise ValueError("Reference dictionary key already exists")
                version = 1
                await database.execute(
                    """INSERT INTO evaluation_reference_dictionaries
                       VALUES(?,?,1,1,?,?)""",
                    (dictionary_id, key, now, now),
                )
            else:
                row = await (
                    await database.execute(
                        """SELECT current_version FROM evaluation_reference_dictionaries
                           WHERE id=?""",
                        (dictionary_id,),
                    )
                ).fetchone()
                if row is None:
                    raise LookupError("Reference dictionary not found")
                if row["current_version"] != payload.expected_version:
                    raise RuntimeError("The dictionary changed; refresh before saving")
                version = int(row["current_version"]) + 1
                await database.execute(
                    """UPDATE evaluation_reference_dictionaries
                       SET current_version=?,updated_at=? WHERE id=?""",
                    (version, now, dictionary_id),
                )
            content = {
                "name": payload.name,
                "purpose": payload.purpose,
                "schema_fields": payload.schema_fields,
                "entries": payload.entries,
            }
            await database.execute(
                """INSERT INTO evaluation_reference_dictionary_versions
                   VALUES(?,?,?,?)""",
                (dictionary_id, version, _json(content), now),
            )
            await self._audit(
                database,
                "reference_dictionary.version_created",
                dictionary_id,
                {"version": version, "entry_count": len(payload.entries)},
            )
            await database.commit()
        return next(
            row for row in await self.list_reference_dictionaries() if row["id"] == dictionary_id
        )

    async def list_contexts(self) -> list[dict[str, Any]]:
        """Return current versioned evaluation contexts."""
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            rows = await (
                await database.execute(
                    """SELECT c.id,c.context_key,c.current_version,c.enabled,c.is_default,
                              c.updated_at,v.payload_json
                       FROM evaluation_contexts c JOIN evaluation_context_versions v
                         ON v.context_id=c.id AND v.version=c.current_version
                       ORDER BY c.is_default DESC,c.created_at,c.id"""
                )
            ).fetchall()
        return [
            {
                **{key: row[key] for key in row.keys() if key != "payload_json"},
                **json.loads(row["payload_json"]),
                "enabled": bool(row["enabled"]),
                "is_default": bool(row["is_default"]),
            }
            for row in rows
        ]

    async def write_context(
        self,
        payload: Any,
        context_id: str | None = None,
    ) -> dict[str, Any]:
        """Create an evaluation context or append one immutable version."""
        dictionaries = {row["version_id"] for row in await self.list_reference_dictionaries()}
        if not set(payload.dictionary_version_ids).issubset(dictionaries):
            raise ValueError("Context references an unavailable dictionary version")
        now = _utcnow()
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            await database.execute("BEGIN IMMEDIATE")
            if context_id is None:
                context_id = f"context-{uuid.uuid4().hex}"
                key = payload.context_key or f"custom_{uuid.uuid4().hex[:12]}"
                duplicate = await (
                    await database.execute(
                        "SELECT 1 FROM evaluation_contexts WHERE context_key=?",
                        (key,),
                    )
                ).fetchone()
                if duplicate:
                    raise ValueError("Evaluation context key already exists")
                version = 1
                await database.execute(
                    "INSERT INTO evaluation_contexts VALUES(?,?,1,1,0,?,?)",
                    (context_id, key, now, now),
                )
            else:
                row = await (
                    await database.execute(
                        "SELECT current_version FROM evaluation_contexts WHERE id=?",
                        (context_id,),
                    )
                ).fetchone()
                if row is None:
                    raise LookupError("Evaluation context not found")
                if row["current_version"] != payload.expected_version:
                    raise RuntimeError("The context changed; refresh before saving")
                version = int(row["current_version"]) + 1
                await database.execute(
                    """UPDATE evaluation_contexts SET current_version=?,updated_at=?
                       WHERE id=?""",
                    (version, now, context_id),
                )
            content = payload.model_dump(exclude={"context_key", "expected_version"})
            content["version"] = f"v{version}"
            await database.execute(
                "INSERT INTO evaluation_context_versions VALUES(?,?,?,?)",
                (context_id, version, _json(content), now),
            )
            await self._audit(
                database,
                "evaluation_context.version_created",
                context_id,
                {"version": version},
            )
            await database.commit()
        return next(row for row in await self.list_contexts() if row["id"] == context_id)

    async def set_context_status(
        self,
        context_id: str,
        *,
        enabled: bool | None,
        is_default: bool | None,
        expected_version: int,
    ) -> dict[str, Any]:
        """Update future-batch context selection without rewriting a content version."""
        now = _utcnow()
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            await database.execute("BEGIN IMMEDIATE")
            row = await (
                await database.execute(
                    """SELECT current_version,enabled,is_default
                       FROM evaluation_contexts WHERE id=?""",
                    (context_id,),
                )
            ).fetchone()
            if row is None:
                raise LookupError("Evaluation context not found")
            if int(row["current_version"]) != expected_version:
                raise RuntimeError("The context changed; refresh before updating its status")
            next_enabled = bool(row["enabled"]) if enabled is None else enabled
            next_default = bool(row["is_default"]) if is_default is None else is_default
            if is_default is True:
                next_enabled = True
                next_default = True
                await database.execute(
                    "UPDATE evaluation_contexts SET is_default=0 WHERE id<>?",
                    (context_id,),
                )
            if bool(row["is_default"]) and (not next_enabled or not next_default):
                raise ValueError("Choose another default context before disabling this one")
            await database.execute(
                """UPDATE evaluation_contexts
                   SET enabled=?,is_default=?,updated_at=? WHERE id=?""",
                (int(next_enabled), int(next_default), now, context_id),
            )
            await self._audit(
                database,
                "evaluation_context.status_updated",
                context_id,
                {"enabled": next_enabled, "is_default": next_default},
            )
            await database.commit()
        return next(row for row in await self.list_contexts() if row["id"] == context_id)

    async def prompt_templates(self) -> list[dict[str, Any]]:
        """Return complete current Prompt templates, never truncated summaries."""
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            rows = await (
                await database.execute(
                    """SELECT t.template_key,t.current_version,t.updated_at,v.payload_json
                       FROM evaluation_prompt_templates t
                       JOIN evaluation_prompt_template_versions v
                         ON v.template_key=t.template_key AND v.version=t.current_version
                       ORDER BY t.template_key"""
                )
            ).fetchall()
        return [
            {
                "template_key": row["template_key"],
                "current_version": row["current_version"],
                "updated_at": row["updated_at"],
                **json.loads(row["payload_json"]),
            }
            for row in rows
        ]

    @staticmethod
    def _validate_prompt_template(template_key: str, content: str) -> None:
        """Enforce the frozen input and output contract before persistence."""
        required = {
            "pass_1": {
                "{{request_group_id}}",
                "{{conversations}}",
                "{{evaluation_context}}",
                "{{reference_dictionaries}}",
                "{{screening_strategy}}",
                "{{scenario_tags}}",
                '"issues"',
                '"results"',
                '"conversation_id"',
                '"event_results"',
                '"target_events"',
                "candidate|pass|data_issue",
                "唯一质检目标是检测线上 ASR",
                "用户没有回答当前问题",
            },
            "pass_2": {
                "{{request_group_id}}",
                "{{candidate_case}}",
                "{{conversation_history}}",
                "{{production_transcript}}",
                "{{asr_results}}",
                "{{evaluation_context}}",
                "{{reference_dictionaries}}",
                "{{screening_strategy}}",
                "{{scenario_tags}}",
                '"conversation_id"',
                '"issue_id"',
                '"event_id"',
                '"decision"',
                "Good Case|Bad Case|Needs manual audio review",
                '"reference_text"',
                '"segment_ids"',
                '"name_en"',
                '"name_zh"',
                '"description_en"',
                '"description_zh"',
                '"results"',
                '"positioning_quality"',
                "中性 ASR 质检维度",
                "不得描述用户没有回答",
            },
        }
        if template_key not in required:
            raise LookupError("Prompt template not found")
        missing = [term for term in required[template_key] if term not in content]
        if missing:
            raise ValueError(
                "Prompt is missing required contract terms: " + ", ".join(sorted(missing))
            )
        if re.search(r'["\'`]confidence["\'`]\s*:', content, re.IGNORECASE):
            raise ValueError("Prompt output must not contain a confidence field")

    async def prompt_template_versions(self, template_key: str) -> list[dict[str, Any]]:
        """Return every immutable version without changing the active template."""
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            current = await (
                await database.execute(
                    "SELECT current_version FROM evaluation_prompt_templates WHERE template_key=?",
                    (template_key,),
                )
            ).fetchone()
            if current is None:
                raise LookupError("Prompt template not found")
            rows = await (
                await database.execute(
                    """SELECT version,payload_json,created_at
                       FROM evaluation_prompt_template_versions
                       WHERE template_key=? ORDER BY version DESC""",
                    (template_key,),
                )
            ).fetchall()
        return [
            {
                "template_key": template_key,
                "version": int(row["version"]),
                "content": json.loads(row["payload_json"])["content"],
                "created_at": row["created_at"],
                "is_current": int(row["version"]) == int(current["current_version"]),
            }
            for row in rows
        ]

    async def update_prompt_template(self, template_key: str, payload: Any) -> dict[str, Any]:
        """Validate required variable slots and replace the active version atomically."""
        self._validate_prompt_template(template_key, payload.content)
        now = _utcnow()
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            await database.execute("BEGIN IMMEDIATE")
            row = await (
                await database.execute(
                    "SELECT current_version FROM evaluation_prompt_templates WHERE template_key=?",
                    (template_key,),
                )
            ).fetchone()
            if row is None:
                raise LookupError("Prompt template not found")
            if row["current_version"] != payload.expected_version:
                raise RuntimeError("The Prompt changed; refresh before saving")
            version = int(row["current_version"]) + 1
            await database.execute(
                """UPDATE evaluation_prompt_templates
                   SET current_version=?,payload_json=?,updated_at=? WHERE template_key=?""",
                (version, _json({"content": payload.content}), now, template_key),
            )
            await database.execute(
                """INSERT INTO evaluation_prompt_template_versions
                   VALUES(?,?,?,?)""",
                (template_key, version, _json({"content": payload.content}), now),
            )
            await self._audit(
                database,
                "prompt_template.version_created",
                template_key,
                {"version": version},
            )
            await database.commit()
        return next(
            row for row in await self.prompt_templates() if row["template_key"] == template_key
        )

    async def restore_prompt_template(self, template_key: str, payload: Any) -> dict[str, Any]:
        """Copy one historical Prompt into a newly appended active version."""
        now = _utcnow()
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            await database.execute("BEGIN IMMEDIATE")
            current = await (
                await database.execute(
                    "SELECT current_version FROM evaluation_prompt_templates WHERE template_key=?",
                    (template_key,),
                )
            ).fetchone()
            if current is None:
                raise LookupError("Prompt template not found")
            if int(current["current_version"]) != payload.expected_version:
                raise RuntimeError("The Prompt changed; refresh before restoring")
            source = await (
                await database.execute(
                    """SELECT payload_json FROM evaluation_prompt_template_versions
                       WHERE template_key=? AND version=?""",
                    (template_key, payload.source_version),
                )
            ).fetchone()
            if source is None:
                raise LookupError("Prompt version not found")
            source_payload = json.loads(source["payload_json"])
            self._validate_prompt_template(template_key, source_payload["content"])
            version = int(current["current_version"]) + 1
            await database.execute(
                """UPDATE evaluation_prompt_templates
                   SET current_version=?,payload_json=?,updated_at=? WHERE template_key=?""",
                (version, source["payload_json"], now, template_key),
            )
            await database.execute(
                """INSERT INTO evaluation_prompt_template_versions
                   VALUES(?,?,?,?)""",
                (template_key, version, source["payload_json"], now),
            )
            await self._audit(
                database,
                "prompt_template.version_restored",
                template_key,
                {"source_version": payload.source_version, "version": version},
            )
            await database.commit()
        return next(
            row for row in await self.prompt_templates() if row["template_key"] == template_key
        )

    async def context_snapshot(self, context_key: str) -> dict[str, Any]:
        """Resolve one current context and its exact linked dictionary versions."""
        contexts = await self.list_contexts()
        context = next(
            (row for row in contexts if row["context_key"] == context_key and row["enabled"]),
            None,
        )
        if context is None:
            raise ValueError("Evaluation context is unavailable")
        dictionaries: list[dict[str, Any]] = []
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            for version_id in context.get("dictionary_version_ids", []):
                dictionary_id, separator, raw_version = str(version_id).rpartition(":")
                if not separator or not raw_version.isdigit():
                    raise ValueError("Evaluation context has an invalid dictionary reference")
                row = await (
                    await database.execute(
                        """SELECT d.dictionary_key,v.version,v.payload_json
                           FROM evaluation_reference_dictionaries d
                           JOIN evaluation_reference_dictionary_versions v
                             ON v.dictionary_id=d.id
                           WHERE d.id=? AND v.version=?""",
                        (dictionary_id, int(raw_version)),
                    )
                ).fetchone()
                if row is None:
                    raise ValueError("Evaluation context dictionary version is unavailable")
                dictionaries.append(
                    {
                        "dictionary_key": row["dictionary_key"],
                        "version": f"v{row['version']}",
                        **json.loads(row["payload_json"]),
                    }
                )
        prompts = {row["template_key"]: row for row in await self.prompt_templates()}
        return {
            "context": context,
            "reference_dictionaries": dictionaries,
            "pass_1_prompt": prompts["pass_1"],
            "pass_2_prompt": prompts["pass_2"],
        }

    async def _load_dataset_meta(
        self,
        database: aiosqlite.Connection,
        key: str,
    ) -> dict[str, Any] | None:
        """Load one managed-dataset descriptor from SQLite."""
        row = await (
            await database.execute("SELECT value FROM evaluation_meta WHERE key=?", (key,))
        ).fetchone()
        if row is None:
            return None
        try:
            value = json.loads(row[0])
        except (TypeError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    def _managed_dataset_path(self, descriptor: dict[str, Any] | None) -> Path | None:
        """Resolve a stored dataset ID only inside the managed upload directory."""
        dataset_id = str((descriptor or {}).get("dataset_id", ""))
        if not dataset_id.startswith("dataset-") or any(
            character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in dataset_id
        ):
            return None
        candidate = self.upload_root / dataset_id
        return candidate if candidate.is_dir() else None

    async def _remove_legacy_simulations(self, database: aiosqlite.Connection) -> None:
        """Remove the prior fixed results once without touching source files."""
        migrated = await (
            await database.execute(
                "SELECT 1 FROM evaluation_meta WHERE key=?", (_REAL_SOURCE_MIGRATION,)
            )
        ).fetchone()
        if migrated:
            return
        counts: dict[str, int] = {}
        for table in (
            "evaluation_benchmarks",
            "evaluation_reviews",
            "evaluation_batches",
            "evaluation_commands",
            "evaluation_audit",
        ):
            row = await (await database.execute(f"SELECT COUNT(*) FROM {table}")).fetchone()
            counts[table] = int(row[0] if row else 0)
        await database.execute("DELETE FROM evaluation_benchmarks")
        await database.execute("DELETE FROM evaluation_reviews")
        await database.execute("DELETE FROM evaluation_batches")
        await database.execute("DELETE FROM evaluation_commands")
        await database.execute("DELETE FROM evaluation_audit")
        now = _utcnow()
        await database.execute(
            "INSERT INTO evaluation_meta(key,value,updated_at) VALUES(?,?,?)",
            (_REAL_SOURCE_MIGRATION, _json({"removed_rows": counts}), now),
        )
        await database.execute(
            "INSERT INTO evaluation_audit VALUES(?,?,?,?,?)",
            (
                str(uuid.uuid4()),
                "migration.remove_simulated_results",
                "evaluation",
                _json({"removed_rows": counts, "source_files_deleted": 0}),
                now,
            ),
        )

    async def _sync_source_data(
        self,
        database: aiosqlite.Connection,
        audit: DatasetAudit,
    ) -> None:
        """Replace the imported source index with the latest read-only package audit."""
        await database.execute("DELETE FROM evaluation_source_events")
        await database.execute("DELETE FROM evaluation_source_conversations")
        now = _utcnow()
        for conversation in audit.conversations:
            await self._insert_source_conversation(database, conversation, now)

    async def _insert_source_conversation(
        self,
        database: aiosqlite.Connection,
        conversation: ConversationAudit,
        imported_at: str,
    ) -> None:
        """Persist one audited conversation and its source events."""
        data = conversation.to_dict()
        await database.execute(
            """INSERT INTO evaluation_source_conversations (
                conversation_id,history_path,record_path,user_record_path,detected_language,
                event_count,user_event_count,robot_event_count,record_audio_json,user_audio_json,
                issues_json,valid,imported_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                conversation.conversation_id,
                conversation.history_path,
                conversation.record_path,
                conversation.user_record_path,
                conversation.detected_language,
                len(conversation.events),
                conversation.user_event_count,
                conversation.robot_event_count,
                _json(data["record_audio"]) if data["record_audio"] else None,
                _json(data["user_audio"]) if data["user_audio"] else None,
                _json(conversation.issues),
                int(conversation.valid),
                imported_at,
            ),
        )
        await database.executemany(
            """INSERT INTO evaluation_source_events (
                conversation_id,event_id,source_row,time_s,speaker,text
            ) VALUES (?,?,?,?,?,?)""",
            [
                (
                    conversation.conversation_id,
                    event.event_id,
                    event.source_row,
                    event.time_s,
                    event.speaker,
                    event.text,
                )
                for event in conversation.events
            ],
        )

    async def _set_meta(
        self,
        database: aiosqlite.Connection,
        key: str,
        value: dict[str, Any],
    ) -> None:
        """Upsert one JSON metadata value."""
        await database.execute(
            """INSERT INTO evaluation_meta(key,value,updated_at) VALUES(?,?,?)
               ON CONFLICT(key) DO UPDATE SET
                   value=excluded.value,updated_at=excluded.updated_at""",
            (key, _json(value), _utcnow()),
        )

    def _dataset_descriptor(
        self,
        dataset_id: str,
        filename: str,
        *,
        valid: bool,
    ) -> dict[str, Any]:
        """Build a non-secret descriptor for one immutable uploaded package."""
        return {
            "dataset_id": dataset_id,
            "filename": Path(filename).name[:240],
            "uploaded_at": _utcnow(),
            "valid": valid,
        }

    def _repair_base(self, candidate_id: str | None) -> Path:
        """Resolve the explicit or latest candidate used by a repair upload."""
        if candidate_id:
            for descriptor in (self._pending_dataset, self._active_dataset):
                if descriptor and descriptor.get("dataset_id") == candidate_id:
                    resolved = self._managed_dataset_path(descriptor)
                    if resolved is not None:
                        return resolved
            raise PackageUploadError("The selected upload candidate is no longer available")
        pending = self._managed_dataset_path(self._pending_dataset)
        return pending or self.dataset_root

    def _stage_dataset_upload(
        self,
        uploaded_path: Path,
        original_filename: str,
        *,
        repair: bool,
        base_root: Path | None,
    ) -> tuple[str, Path, DatasetAudit]:
        """Create and audit an immutable managed dataset directory."""
        dataset_id = f"dataset-{uuid.uuid4().hex}"
        staging = self.upload_root / f".staging-{uuid.uuid4().hex}"
        final = self.upload_root / dataset_id
        try:
            if repair:
                assert base_root is not None
                shutil.copytree(base_root, staging)
            else:
                staging.mkdir(parents=True)
            if Path(original_filename).suffix.lower() == ".zip":
                extract_package_archive(uploaded_path, staging)
            elif repair:
                install_single_repair(uploaded_path, Path(original_filename).name, staging)
            else:
                raise PackageUploadError("A complete dataset upload must be a ZIP archive")
            audit_dataset(staging, expected_conversations=None)
            staging.rename(final)
            return dataset_id, final, audit_dataset(final, expected_conversations=None)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise

    async def import_dataset_upload(
        self,
        uploaded_path: Path,
        original_filename: str,
        *,
        repair: bool = False,
        candidate_id: str | None = None,
    ) -> dict[str, Any]:
        """Stage, validate, and conditionally activate an uploaded dataset."""
        async with self._import_lock:
            base_root = self._repair_base(candidate_id) if repair else None
            dataset_id, final, audit = await asyncio.to_thread(
                self._stage_dataset_upload,
                uploaded_path,
                original_filename,
                repair=repair,
                base_root=base_root,
            )
            descriptor = self._dataset_descriptor(
                dataset_id,
                original_filename,
                valid=audit.valid,
            )
            async with aiosqlite.connect(self.database_path) as database:
                if audit.valid:
                    await self._set_meta(database, _ACTIVE_DATASET_META, descriptor)
                    await database.execute(
                        "DELETE FROM evaluation_meta WHERE key=?",
                        (_PENDING_DATASET_META,),
                    )
                    await self._sync_source_data(database, audit)
                    await self._audit(
                        database,
                        "dataset.upload_activated",
                        dataset_id,
                        {
                            "filename": descriptor["filename"],
                            "conversation_count": len(audit.conversations),
                            "repair": repair,
                        },
                    )
                else:
                    await self._set_meta(database, _PENDING_DATASET_META, descriptor)
                    await self._audit(
                        database,
                        "dataset.upload_blocked",
                        dataset_id,
                        {
                            "filename": descriptor["filename"],
                            "issue_count": audit.to_dict()["blocking_issue_count"],
                            "warning_count": audit.to_dict()["warning_count"],
                            "repair": repair,
                        },
                    )
                await database.commit()
            if audit.valid:
                self.dataset_root = final
                self._source_audit = audit
                self._active_dataset = descriptor
                self._pending_dataset = None
                self._pending_audit = None
            else:
                self._pending_dataset = descriptor
                self._pending_audit = audit
            result = audit.to_dict(include_conversations=True)
            result.update(
                {
                    "dataset_id": dataset_id,
                    "filename": descriptor["filename"],
                    "active": audit.valid,
                    "repair": repair,
                }
            )
            return result

    def pending_dataset_status(self) -> dict[str, Any] | None:
        """Return the latest blocked upload during the current repair flow."""
        if self._pending_dataset is None or self._pending_audit is None:
            return None
        result = self._pending_audit.to_dict(include_conversations=True)
        result.update(self._pending_dataset)
        result["active"] = False
        return result

    async def discard_pending_dataset(self) -> dict[str, Any]:
        """Discard only the exact unstarted upload candidate and return active data."""
        async with self._import_lock:
            descriptor = self._pending_dataset
            pending_root = self._managed_dataset_path(descriptor)
            dataset_id = str((descriptor or {}).get("dataset_id", ""))
            async with aiosqlite.connect(self.database_path) as database:
                await database.execute(
                    "DELETE FROM evaluation_meta WHERE key=?",
                    (_PENDING_DATASET_META,),
                )
                if dataset_id:
                    await self._audit(
                        database,
                        "dataset.pending_discarded",
                        dataset_id,
                        {"filename": str((descriptor or {}).get("filename", ""))},
                    )
                await database.commit()
            self._pending_dataset = None
            self._pending_audit = None
            if pending_root is not None:
                await asyncio.to_thread(shutil.rmtree, pending_root)
        return self.fixture_status()

    def candidate_dataset_audit(self, candidate_id: str | None) -> dict[str, Any] | None:
        """Return the active or pending audit selected by the UI."""
        if candidate_id is None:
            return self.dataset_audit(include_conversations=True)
        if self._pending_dataset and self._pending_dataset.get("dataset_id") == candidate_id:
            return self.pending_dataset_status()
        if self._active_dataset and self._active_dataset.get("dataset_id") == candidate_id:
            return self.dataset_audit(include_conversations=True)
        return None

    def fixture_status(self) -> dict[str, Any]:
        """Return a real content audit summary for the active source package."""
        if self._source_audit is None:
            self._source_audit = audit_dataset(
                self.dataset_root,
                expected_conversations=None if self._active_dataset else 56,
            )
        result = self._source_audit.to_dict()
        result["source"] = (
            self._active_dataset["filename"]
            if self._active_dataset
            else "benchmarks/RiyadBankConversation"
        )
        result["dataset_id"] = (
            self._active_dataset["dataset_id"] if self._active_dataset else "mounted-source"
        )
        result["active"] = True
        return result

    def dataset_audit(self, *, include_conversations: bool = True) -> dict[str, Any]:
        """Return the current source audit, including per-conversation details when requested."""
        if self._source_audit is None:
            self._source_audit = audit_dataset(
                self.dataset_root,
                expected_conversations=None if self._active_dataset else 56,
            )
        result = self._source_audit.to_dict(include_conversations=include_conversations)
        result["source"] = (
            self._active_dataset["filename"]
            if self._active_dataset
            else "benchmarks/RiyadBankConversation"
        )
        result["dataset_id"] = (
            self._active_dataset["dataset_id"] if self._active_dataset else "mounted-source"
        )
        result["active"] = True
        return result

    async def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        """Return the actual parsed source transcript for one conversation."""
        if _SAFE_CONVERSATION_ID.fullmatch(conversation_id) is None:
            return None
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            conversation = await (
                await database.execute(
                    "SELECT * FROM evaluation_source_conversations WHERE conversation_id=?",
                    (conversation_id,),
                )
            ).fetchone()
            if conversation is None:
                return None
            events = await (
                await database.execute(
                    """SELECT event_id,source_row,time_s,speaker,text
                       FROM evaluation_source_events WHERE conversation_id=?
                       ORDER BY source_row""",
                    (conversation_id,),
                )
            ).fetchall()
        return {
            "conversation_id": conversation_id,
            "history_path": conversation["history_path"],
            "record_path": conversation["record_path"],
            "user_record_path": conversation["user_record_path"],
            "detected_language": conversation["detected_language"],
            "event_count": conversation["event_count"],
            "user_event_count": conversation["user_event_count"],
            "robot_event_count": conversation["robot_event_count"],
            "record_audio": json.loads(conversation["record_audio_json"] or "null"),
            "user_audio": json.loads(conversation["user_audio_json"] or "null"),
            "issues": json.loads(conversation["issues_json"]),
            "valid": bool(conversation["valid"]),
            "audio_url": f"/api/evaluation/conversations/{conversation_id}/audio",
            "user_audio_url": f"/api/evaluation/conversations/{conversation_id}/user-audio",
            "events": [dict(event) for event in events],
        }

    async def _command_result(self, key: str) -> dict[str, Any] | None:
        async with aiosqlite.connect(self.database_path) as database:
            row = await (
                await database.execute(
                    "SELECT response_json FROM evaluation_commands WHERE idempotency_key=?",
                    (key,),
                )
            ).fetchone()
        return json.loads(row[0]) if row else None

    async def command_result(self, key: str) -> dict[str, Any] | None:
        """Return a previously committed idempotent command response."""
        return await self._command_result(key)

    async def _save_command(
        self,
        database: aiosqlite.Connection,
        key: str,
        response: dict[str, Any],
    ) -> None:
        await database.execute(
            "INSERT INTO evaluation_commands VALUES (?,?,?)",
            (key, _json(response), _utcnow()),
        )

    async def _audit(
        self,
        database: aiosqlite.Connection,
        action: str,
        object_id: str,
        metadata: dict[str, Any],
    ) -> None:
        await database.execute(
            "INSERT INTO evaluation_audit VALUES (?,?,?,?,?)",
            (str(uuid.uuid4()), action, object_id, _json(metadata), _utcnow()),
        )

    async def audit_access(
        self,
        action: str,
        object_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Persist one authorized read/play action without customer content."""
        async with aiosqlite.connect(self.database_path) as database:
            await self._audit(
                database,
                action,
                object_id,
                {"actor": "authenticated_product_session", **(metadata or {})},
            )
            await database.commit()

    @staticmethod
    def _batch(row: aiosqlite.Row) -> dict[str, Any]:
        snapshot = json.loads(row["snapshot_json"])
        audit_only = snapshot.get("result_disposition") == "audit_only"
        return {
            "id": row["id"],
            "name": row["name"],
            "context_name": row["context_name"],
            "input_count": row["input_count"],
            "status": row["status"],
            "stage": row["stage"],
            "progress": row["progress"],
            "suspected_numerator": row["suspected_numerator"],
            "denominator": row["denominator"],
            "excluded_count": row["excluded_count"],
            "cost": row["cost"],
            "budget": row["budget"],
            "review_total": row["review_total"],
            "review_completed": row["review_completed"],
            "report_type": None if audit_only else row["report_type"],
            "audit_report_type": row["report_type"] if audit_only else None,
            "result_disposition": "audit_only" if audit_only else "formal",
            "providers": json.loads(row["providers_json"]),
            "snapshot": snapshot,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "version": row["version"],
        }

    async def list_batches(self) -> list[dict[str, Any]]:
        """Return only source-backed batches; no progress is synthesized."""
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            rows = await (
                await database.execute(
                    "SELECT * FROM evaluation_batches ORDER BY created_at DESC, id DESC"
                )
            ).fetchall()
        return [self._batch(row) for row in rows]

    async def get_batch(self, batch_id: str) -> dict[str, Any] | None:
        """Return one persisted batch without synthesizing execution state."""
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            row = await (
                await database.execute("SELECT * FROM evaluation_batches WHERE id=?", (batch_id,))
            ).fetchone()
        return self._batch(row) if row is not None else None

    async def mark_batch_audit_only(self, batch_id: str, *, reason: str) -> dict[str, Any]:
        """Retain a batch as evidence while excluding it from formal product outputs."""
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            row = await (
                await database.execute("SELECT * FROM evaluation_batches WHERE id=?", (batch_id,))
            ).fetchone()
            if row is None:
                raise LookupError("Batch not found")
            snapshot = json.loads(row["snapshot_json"])
            if snapshot.get("result_disposition") != "audit_only":
                snapshot["result_disposition"] = "audit_only"
                snapshot["disposition_reason"] = reason
                now = _utcnow()
                await database.execute(
                    """UPDATE evaluation_batches
                       SET snapshot_json=?,updated_at=?,version=version+1 WHERE id=?""",
                    (_json(snapshot), now, batch_id),
                )
                await self._audit(
                    database,
                    "batch.marked_audit_only",
                    batch_id,
                    {"reason": reason},
                )
                await database.commit()
                row = await (
                    await database.execute(
                        "SELECT * FROM evaluation_batches WHERE id=?", (batch_id,)
                    )
                ).fetchone()
                assert row is not None
        return self._batch(row)

    async def source_conversations(self) -> list[dict[str, Any]]:
        """Return all valid source conversations in deterministic order."""
        async with aiosqlite.connect(self.database_path) as database:
            rows = await (
                await database.execute(
                    """SELECT conversation_id FROM evaluation_source_conversations
                       WHERE valid=1 ORDER BY conversation_id"""
                )
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            conversation = await self.get_conversation(str(row[0]))
            if conversation is not None:
                result.append(conversation)
        return result

    async def set_batch_state(
        self,
        batch_id: str,
        *,
        status: str,
        stage: str,
        progress: int,
        cost: float | None = None,
        suspected_numerator: int | None = None,
        review_total: int | None = None,
        denominator: int | None = None,
        excluded_count: int | None = None,
        snapshot_updates: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Persist one monotonic execution checkpoint for restart-safe polling."""
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            row = await (
                await database.execute("SELECT * FROM evaluation_batches WHERE id=?", (batch_id,))
            ).fetchone()
            if row is None:
                raise LookupError("Batch not found")
            snapshot = json.loads(row["snapshot_json"])
            snapshot.update(snapshot_updates or {})
            values: list[object] = [status, stage, max(0, min(100, progress)), _json(snapshot)]
            assignments = [
                "status=?",
                "stage=?",
                "progress=?",
                "snapshot_json=?",
                "updated_at=?",
                "version=version+1",
            ]
            values.append(_utcnow())
            for column, value in (
                ("cost", cost),
                ("suspected_numerator", suspected_numerator),
                ("review_total", review_total),
                ("denominator", denominator),
                ("excluded_count", excluded_count),
            ):
                if value is not None:
                    assignments.append(f"{column}=?")
                    values.append(value)
            values.append(batch_id)
            await database.execute(
                f"UPDATE evaluation_batches SET {','.join(assignments)} WHERE id=?", values
            )
            updated = await (
                await database.execute("SELECT * FROM evaluation_batches WHERE id=?", (batch_id,))
            ).fetchone()
            await database.commit()
        assert updated is not None
        return self._batch(updated)

    async def checkpoint_result(
        self,
        table: str,
        keys: tuple[str, ...],
        *,
        status: str,
        attempts: int,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        remote_job_id: str | None = None,
    ) -> None:
        """Upsert one pass or provider result using a bounded table allow-list."""
        definitions = {
            "evaluation_pass1_runs": ("batch_id,conversation_id", 2),
            "evaluation_asr_runs": ("batch_id,provider,conversation_id", 3),
            "evaluation_case_asr_runs": (
                "batch_id,provider,conversation_id,event_id",
                4,
            ),
            "evaluation_pass2_runs": ("batch_id,conversation_id,event_id", 3),
        }
        definition = definitions.get(table)
        if definition is None or len(keys) != definition[1]:
            raise ValueError("Invalid evaluation checkpoint target")
        columns = definition[0]
        provider_table = table in {"evaluation_asr_runs", "evaluation_case_asr_runs"}
        extra_column = ",remote_job_id" if provider_table else ""
        extra_value = ",?" if provider_table else ""
        extra_update = ",remote_job_id=excluded.remote_job_id" if provider_table else ""
        conflict = columns
        params: tuple[object, ...] = (
            *keys,
            status,
            attempts,
            _json(result) if result is not None else None,
            error,
            *([remote_job_id] if provider_table else []),
            _utcnow(),
        )
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute(
                f"""INSERT INTO {table} ({columns},status,attempts,result_json,error
                       {extra_column},updated_at)
                    VALUES ({",".join("?" for _ in keys)},?,?,?,?{extra_value},?)
                    ON CONFLICT({conflict}) DO UPDATE SET
                       status=excluded.status,attempts=excluded.attempts,
                       result_json=excluded.result_json,error=excluded.error,
                       updated_at=excluded.updated_at{extra_update}""",
                params,
            )
            await database.commit()

    async def checkpoint_rows(self, table: str, batch_id: str) -> list[dict[str, Any]]:
        """Read persisted execution checkpoints for one batch."""
        if table not in {
            "evaluation_pass1_runs",
            "evaluation_asr_runs",
            "evaluation_case_asr_runs",
            "evaluation_pass2_runs",
        }:
            raise ValueError("Invalid evaluation checkpoint target")
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            rows = await (
                await database.execute(f"SELECT * FROM {table} WHERE batch_id=?", (batch_id,))
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["result"] = json.loads(item.pop("result_json") or "null")
            result.append(item)
        return result

    async def checkpoint_pass2_group(
        self,
        *,
        batch_id: str,
        group_id: str,
        idempotency_key: str,
        conversation_ids: list[str],
        case_keys: list[tuple[str, str]],
        estimated_input_tokens: int,
        reserved_output_tokens: int,
        status: str,
        attempts: int,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """Persist frozen Pass 2 group membership and its request outcome."""
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute(
                """INSERT INTO evaluation_pass2_groups (
                       batch_id,group_id,idempotency_key,conversation_ids_json,
                       case_keys_json,estimated_input_tokens,reserved_output_tokens,
                       status,attempts,result_json,error,updated_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(batch_id,group_id) DO UPDATE SET
                       status=excluded.status,attempts=excluded.attempts,
                       result_json=excluded.result_json,error=excluded.error,
                       updated_at=excluded.updated_at""",
                (
                    batch_id,
                    group_id,
                    idempotency_key,
                    _json(conversation_ids),
                    _json(case_keys),
                    estimated_input_tokens,
                    reserved_output_tokens,
                    status,
                    attempts,
                    _json(result) if result is not None else None,
                    error,
                    _utcnow(),
                ),
            )
            await database.commit()

    async def checkpoint_pass1_group(
        self,
        *,
        batch_id: str,
        group_id: str,
        idempotency_key: str,
        conversation_ids: list[str],
        estimated_input_tokens: int,
        reserved_output_tokens: int,
        status: str,
        attempts: int,
        conversation_results: dict[str, dict[str, Any]] | None = None,
        error: str | None = None,
    ) -> None:
        """Persist one frozen Pass 1 group and its conversation results atomically."""
        if status == "completed" and set(conversation_results or {}) != set(conversation_ids):
            raise ValueError("Completed Pass 1 group requires every conversation result")
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute("BEGIN IMMEDIATE")
            await database.execute(
                """INSERT INTO evaluation_pass1_groups (
                       batch_id,group_id,idempotency_key,conversation_ids_json,
                       estimated_input_tokens,reserved_output_tokens,status,attempts,
                       result_json,error,updated_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(batch_id,group_id) DO UPDATE SET
                       status=excluded.status,attempts=excluded.attempts,
                       result_json=excluded.result_json,error=excluded.error,
                       updated_at=excluded.updated_at""",
                (
                    batch_id,
                    group_id,
                    idempotency_key,
                    _json(conversation_ids),
                    estimated_input_tokens,
                    reserved_output_tokens,
                    status,
                    attempts,
                    _json({"result_count": len(conversation_results or {})})
                    if conversation_results is not None
                    else None,
                    error,
                    _utcnow(),
                ),
            )
            if status in {"completed", "failed"}:
                for conversation_id in conversation_ids:
                    result = (conversation_results or {}).get(conversation_id)
                    await database.execute(
                        """INSERT INTO evaluation_pass1_runs
                               (batch_id,conversation_id,status,attempts,result_json,error,updated_at)
                           VALUES(?,?,?,?,?,?,?)
                           ON CONFLICT(batch_id,conversation_id) DO UPDATE SET
                               status=excluded.status,attempts=excluded.attempts,
                               result_json=excluded.result_json,error=excluded.error,
                               updated_at=excluded.updated_at""",
                        (
                            batch_id,
                            conversation_id,
                            status,
                            attempts,
                            _json(result) if result is not None else None,
                            error,
                            _utcnow(),
                        ),
                    )
            await database.commit()

    async def pass1_group_rows(self, batch_id: str) -> list[dict[str, Any]]:
        """Return first-pass group checkpoints with decoded frozen membership."""
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            rows = await (
                await database.execute(
                    """SELECT * FROM evaluation_pass1_groups
                       WHERE batch_id=? ORDER BY group_id""",
                    (batch_id,),
                )
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["conversation_ids"] = json.loads(item.pop("conversation_ids_json"))
            item["result"] = json.loads(item.pop("result_json") or "null")
            result.append(item)
        return result

    async def pass2_group_rows(self, batch_id: str) -> list[dict[str, Any]]:
        """Return group checkpoints with decoded immutable membership."""
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            rows = await (
                await database.execute(
                    """SELECT * FROM evaluation_pass2_groups
                       WHERE batch_id=? ORDER BY group_id""",
                    (batch_id,),
                )
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["conversation_ids"] = json.loads(item.pop("conversation_ids_json"))
            item["case_keys"] = json.loads(item.pop("case_keys_json"))
            item["result"] = json.loads(item.pop("result_json") or "null")
            result.append(item)
        return result

    async def acquire_batch_lease(
        self, batch_id: str, owner_id: str, *, ttl_seconds: int = 90
    ) -> bool:
        """Acquire or recover an expired durable batch-worker lease."""
        now = datetime.now(UTC)
        expires_at = (now + timedelta(seconds=ttl_seconds)).isoformat(timespec="seconds")
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            await database.execute("PRAGMA busy_timeout = 5000")
            await database.execute("BEGIN IMMEDIATE")
            row = await (
                await database.execute(
                    "SELECT owner_id,expires_at FROM evaluation_batch_leases WHERE batch_id=?",
                    (batch_id,),
                )
            ).fetchone()
            if row is not None:
                current_expiry = datetime.fromisoformat(str(row["expires_at"]))
                if current_expiry > now and str(row["owner_id"]) != owner_id:
                    await database.rollback()
                    return False
            await database.execute(
                """INSERT INTO evaluation_batch_leases(batch_id,owner_id,expires_at,updated_at)
                   VALUES(?,?,?,?)
                   ON CONFLICT(batch_id) DO UPDATE SET owner_id=excluded.owner_id,
                   expires_at=excluded.expires_at,updated_at=excluded.updated_at""",
                (batch_id, owner_id, expires_at, now.isoformat(timespec="seconds")),
            )
            await database.commit()
        return True

    async def renew_batch_lease(
        self, batch_id: str, owner_id: str, *, ttl_seconds: int = 90
    ) -> bool:
        """Extend a lease only while the same worker still owns it."""
        now = datetime.now(UTC)
        expires_at = (now + timedelta(seconds=ttl_seconds)).isoformat(timespec="seconds")
        async with aiosqlite.connect(self.database_path) as database:
            cursor = await database.execute(
                """UPDATE evaluation_batch_leases SET expires_at=?,updated_at=?
                   WHERE batch_id=? AND owner_id=?""",
                (expires_at, now.isoformat(timespec="seconds"), batch_id, owner_id),
            )
            await database.commit()
        return cursor.rowcount == 1

    async def release_batch_lease(self, batch_id: str, owner_id: str) -> None:
        """Release a durable lease without disturbing another worker owner."""
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute(
                "DELETE FROM evaluation_batch_leases WHERE batch_id=? AND owner_id=?",
                (batch_id, owner_id),
            )
            await database.commit()

    async def refresh_execution_progress(
        self,
        batch_id: str,
        *,
        table: str,
        stage: str,
        total: int,
        progress_start: int,
        progress_end: int,
    ) -> dict[str, Any]:
        """Expose real checkpoint counts and map them into one stage progress band."""
        allowed = {
            "evaluation_pass1_runs": "pass_1",
            "evaluation_asr_runs": "evaluation_asr",
            "evaluation_case_asr_runs": "evaluation_asr",
            "evaluation_pass2_runs": "pass_2",
        }
        if allowed.get(table) != stage:
            raise ValueError("Invalid execution progress target")
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            await database.execute("PRAGMA busy_timeout = 5000")
            await database.execute("BEGIN IMMEDIATE")
            rows = await (
                await database.execute(
                    f"SELECT status, COUNT(*) AS count FROM {table} "
                    "WHERE batch_id=? GROUP BY status",
                    (batch_id,),
                )
            ).fetchall()
            counts = {str(row["status"]): int(row["count"]) for row in rows}
            completed = counts.get("completed", 0)
            failed = counts.get("failed", 0)
            finished = min(max(total, 0), completed + failed)
            span = max(0, progress_end - progress_start)
            progress = progress_start
            if total > 0:
                progress += round(span * finished / total)
            batch = await (
                await database.execute(
                    "SELECT snapshot_json FROM evaluation_batches WHERE id=?", (batch_id,)
                )
            ).fetchone()
            if batch is None:
                raise LookupError("Batch not found")
            snapshot = json.loads(batch["snapshot_json"])
            execution_status = snapshot.setdefault("execution_status", {})
            execution_status[stage] = {
                "completed": completed,
                "failed": failed,
                "finished": finished,
                "total": max(total, 0),
            }
            await database.execute(
                """UPDATE evaluation_batches
                   SET progress=?,snapshot_json=?,updated_at=?,version=version+1
                   WHERE id=?""",
                (progress, _json(snapshot), _utcnow(), batch_id),
            )
            updated = await (
                await database.execute("SELECT * FROM evaluation_batches WHERE id=?", (batch_id,))
            ).fetchone()
            await database.commit()
        assert updated is not None
        return self._batch(updated)

    async def materialize_pass2_results(self, batch_id: str) -> tuple[int, int]:
        """Project completed Pass 2 decisions into review and Benchmark records."""
        pass_one_rows = await self.checkpoint_rows("evaluation_pass1_runs", batch_id)
        asr_rows = await self.checkpoint_rows("evaluation_case_asr_runs", batch_id)
        pass_two_rows = await self.checkpoint_rows("evaluation_pass2_runs", batch_id)
        priorities: dict[tuple[str, str], str] = {}
        for row in pass_one_rows:
            for issue in (row.get("result") or {}).get("issues", []):
                for target in issue.get("target_events", []):
                    key = (str(row["conversation_id"]), str(target.get("event_id")))
                    priorities[key] = str(issue.get("priority") or "P2")
        evidence: dict[str, list[dict[str, Any]]] = {}
        for row in asr_rows:
            if row["status"] == "completed":
                evidence.setdefault(str(row["conversation_id"]), []).append(row)
        review_count = 0
        benchmark_count = 0
        pending_clips: list[str] = []
        async with aiosqlite.connect(self.database_path) as database:
            for row in pass_two_rows:
                if row["status"] != "completed" or not row.get("result"):
                    continue
                result = row["result"]
                conversation_id = str(row["conversation_id"])
                event_id = str(row["event_id"])
                conversation = await self.get_conversation(conversation_id)
                if conversation is None:
                    continue
                event = next(
                    (item for item in conversation["events"] if item["event_id"] == event_id),
                    None,
                )
                if event is None:
                    continue
                start_s, end_s, positioning_quality, _ = self._playback_range(
                    conversation, result, evidence.get(conversation_id, [])
                )
                decision = str(result.get("decision"))
                scenario = str(result.get("scenario_tag") or "Unclassified (AI suggested)")
                language = {"ar": "ar", "en": "en", "mixed": "mixed"}.get(
                    str(conversation.get("detected_language", "")).lower(), "mixed"
                )
                if decision == "Needs manual audio review":
                    providers: list[dict[str, Any]] = []
                    for asr in evidence.get(conversation_id, []):
                        if str(asr.get("event_id")) != event_id:
                            continue
                        segments = (asr.get("result") or {}).get("segments", [])
                        chosen = segments
                        result_text = str((asr.get("result") or {}).get("text") or "")
                        providers.append(
                            {
                                "provider": str(asr["provider"]),
                                "text": result_text,
                                "segment_id": ", ".join(
                                    str(item.get("segment_id")) for item in chosen[:8]
                                ),
                                "start_s": start_s,
                                "end_s": end_s,
                            }
                        )
                    context = [
                        {
                            "event": item["event_id"],
                            "speaker": item["speaker"],
                            "text": item["text"],
                        }
                        for item in conversation["events"]
                        if abs(float(item["time_s"]) - float(event["time_s"])) <= 15
                    ]
                    review_id = f"RV-{batch_id}-{conversation_id}-{event_id}"
                    issue_en, issue_zh, question_en, question_zh = self._review_copy(scenario)
                    payload = {
                        "conversation_id": conversation_id,
                        "event_id": event_id,
                        "issue_en": issue_en,
                        "issue_zh": issue_zh,
                        "priority": priorities.get((conversation_id, event_id), "P2"),
                        "start_s": start_s,
                        "end_s": end_s,
                        "production_transcript": event["text"],
                        "question_en": question_en,
                        "question_zh": question_zh,
                        "context": context,
                        "providers": providers,
                        "positioning_quality": positioning_quality,
                    }
                    await database.execute(
                        """INSERT OR IGNORE INTO evaluation_reviews (
                           id,fixture_key,batch_id,payload_json,status,decision,label,language,
                           scenario_tag,reviewed_at,version
                           ) VALUES (?,?,?,?,'pending',NULL,NULL,?,?,NULL,1)""",
                        (
                            review_id,
                            f"{conversation_id}:{event_id}",
                            batch_id,
                            _json(payload),
                            language,
                            self._scenario_key(scenario),
                        ),
                    )
                    review_count += 1
                elif decision in {"Good Case", "Bad Case"}:
                    label = str(result.get("reference_text") or "").strip()
                    if not label:
                        continue
                    benchmark_id = f"BM-{batch_id}-{conversation_id}-{event_id}"
                    cursor = await database.execute(
                        """INSERT OR IGNORE INTO evaluation_benchmarks (
                           id,batch_id,conversation_id,event_id,case_type,source,language,
                           scenario_tag,label,audio_start_s,audio_end_s,origin,
                           positioning_quality,clip_status,clip_path,clip_error,trace_json,
                           revision,created_at
                           ) VALUES (?,?,?,?,?,'ai',?,?,?,?,?,?,?,'pending',NULL,NULL,'{}',1,?)""",
                        (
                            benchmark_id,
                            batch_id,
                            conversation_id,
                            event_id,
                            "good" if decision == "Good Case" else "bad",
                            language,
                            self._scenario_key(scenario),
                            label,
                            start_s,
                            end_s,
                            str(result.get("origin") or "suspect_candidate"),
                            positioning_quality,
                            _utcnow(),
                        ),
                    )
                    if cursor.rowcount:
                        await self._append_benchmark_revision(database, benchmark_id)
                        pending_clips.append(benchmark_id)
                        benchmark_count += 1
            await database.commit()
        for benchmark_id in pending_clips:
            await self.finalize_benchmark_clip(benchmark_id)
        return review_count, benchmark_count

    async def _append_benchmark_revision(
        self,
        database: aiosqlite.Connection,
        benchmark_id: str,
    ) -> None:
        """Copy the current classification into immutable revision history."""
        row = await (
            await database.execute(
                """SELECT revision,label,language,scenario_tag,source
                   FROM evaluation_benchmarks WHERE id=?""",
                (benchmark_id,),
            )
        ).fetchone()
        if row is None:
            return
        await database.execute(
            """INSERT OR IGNORE INTO evaluation_benchmark_revisions (
               id,benchmark_id,revision,label,language,scenario_tag,source,changed_at
               ) VALUES (?,?,?,?,?,?,?,?)""",
            (
                f"{benchmark_id}:v{int(row[0])}",
                benchmark_id,
                int(row[0]),
                str(row[1]),
                str(row[2]),
                str(row[3]),
                str(row[4]),
                _utcnow(),
            ),
        )

    @staticmethod
    def _write_benchmark_clip(
        source: Path,
        destination: Path,
        start_s: float,
        end_s: float,
    ) -> dict[str, Any]:
        """Write one bounded pure-user WAV clip and return processing trace."""
        info = sf.info(source)
        data, sample_rate = sf.read(source, always_2d=True)
        if len(data) == 0:
            raise ValueError("Source WAV contains no audio frames")
        start = max(0, min(len(data) - 1, int(start_s * sample_rate)))
        end = max(start + 1, min(len(data), int(end_s * sample_rate)))
        buffer = io.BytesIO()
        subtype = str(info.subtype) if str(info.subtype).startswith("PCM_") else "PCM_16"
        sf.write(buffer, data[start:end], sample_rate, format="WAV", subtype=subtype)
        temporary = destination.with_name(f"{destination.name}.{uuid.uuid4().hex}.part")
        temporary.write_bytes(buffer.getvalue())
        temporary.replace(destination)
        return {
            "source": f"user_record/{source.name}",
            "start_s": start / sample_rate,
            "end_s": end / sample_rate,
            "sample_rate": sample_rate,
            "channels": int(info.channels),
            "source_subtype": str(info.subtype),
            "output_subtype": subtype,
            "frame_count": end - start,
        }

    @staticmethod
    def _locate_user_speech(
        source: Path,
        *,
        anchor_s: float,
        lower_bound_s: float,
        upper_bound_s: float,
    ) -> dict[str, float | str]:
        """Locate the nearest bounded speech island around an approximate event anchor."""
        np = importlib.import_module("numpy")
        data, sample_rate = sf.read(source, always_2d=True, dtype="float32")
        if len(data) == 0 or sample_rate <= 0:
            raise ValueError("Source WAV contains no audio frames")
        duration = len(data) / sample_rate
        lower = max(0.0, min(duration, lower_bound_s))
        upper = max(lower, min(duration, upper_bound_s))
        if upper - lower < 0.1:
            raise ValueError("Speech search interval is empty")

        mono = np.max(np.abs(data), axis=1)
        frame_size = max(1, round(sample_rate * 0.02))
        frame_count = len(mono) // frame_size
        if frame_count == 0:
            raise ValueError("Source WAV is too short for speech detection")
        framed = mono[: frame_count * frame_size].reshape(frame_count, frame_size)
        rms = np.sqrt(np.mean(np.square(framed), axis=1))
        search_start = max(0, int(lower / 0.02))
        search_end = min(frame_count, max(search_start + 1, int(np.ceil(upper / 0.02))))
        search_rms = rms[search_start:search_end]
        calibration_start = max(search_start, int(max(lower, anchor_s - 4.5) / 0.02))
        calibration_end = min(
            search_end,
            max(calibration_start + 1, int(min(upper, anchor_s + 1.0) / 0.02)),
        )
        calibration_rms = rms[calibration_start:calibration_end]
        peak = float(np.percentile(calibration_rms, 99))
        noise = float(np.percentile(calibration_rms, 35))
        threshold = max(0.0015, noise * 3.0, peak * 0.08)
        active = search_rms >= threshold

        max_gap_frames = max(1, round(0.35 / 0.02))
        active_indices = np.flatnonzero(active)
        if active_indices.size == 0:
            raise ValueError("No user speech found near the event anchor")
        for left, right in zip(active_indices[:-1], active_indices[1:], strict=False):
            if 1 < right - left <= max_gap_frames + 1:
                active[left : right + 1] = True

        minimum_frames = max(1, round(0.16 / 0.02))
        islands: list[tuple[float, float]] = []
        island_start: int | None = None
        for offset, is_active in enumerate(np.append(active, False)):
            if is_active and island_start is None:
                island_start = offset
            elif not is_active and island_start is not None:
                if offset - island_start >= minimum_frames:
                    start_s = (search_start + island_start) * 0.02
                    end_s = min(duration, (search_start + offset) * 0.02)
                    islands.append((start_s, end_s))
                island_start = None
        if not islands:
            raise ValueError("No stable user speech found near the event anchor")

        def distance(island: tuple[float, float]) -> tuple[float, float]:
            start_s, end_s = island
            if start_s <= anchor_s <= end_s:
                return (0.0, -end_s)
            if end_s <= anchor_s:
                return (anchor_s - end_s, -end_s)
            return ((start_s - anchor_s) + 0.5, start_s)

        ranked_islands = sorted(islands, key=distance)
        speech_start, speech_end = ranked_islands[0]
        anchor_distance = distance((speech_start, speech_end))[0]
        if anchor_distance > 4.0:
            raise ValueError("No unambiguous user speech found near the event anchor")
        if len(ranked_islands) > 1:
            runner_up_distance = distance(ranked_islands[1])[0]
            if runner_up_distance - anchor_distance < 0.5:
                raise ValueError(
                    "Multiple user speech intervals are equally close to the event anchor"
                )
        start_s = max(lower, speech_start - 0.18)
        end_s = min(upper, speech_end + 0.25)
        if end_s - start_s > 12.0:
            raise ValueError("Detected user speech interval is implausibly long")
        return {
            "start_s": start_s,
            "end_s": end_s,
            "speech_start_s": speech_start,
            "speech_end_s": speech_end,
            "anchor_s": anchor_s,
            "anchor_distance_s": anchor_distance,
            "detection_rule": "nearest_energy_island_to_excel_anchor_v2",
        }

    async def prepare_case_asr_clip(
        self,
        batch_id: str,
        conversation_id: str,
        event_id: str,
    ) -> tuple[Path, dict[str, Any]]:
        """Create one stable pure-user event clip for evaluation ASR providers."""
        conversation = await self.get_conversation(conversation_id)
        if conversation is None:
            raise LookupError("Conversation not found")
        issue_types = {str(issue.get("issue_type")) for issue in conversation.get("issues", [])}
        if "audio_timeline_mismatch" in issue_types:
            raise ValueError("Pure-user audio timeline is not aligned")
        events = list(conversation.get("events", []))
        index = next(
            (position for position, item in enumerate(events) if item["event_id"] == event_id),
            None,
        )
        if index is None or events[index].get("speaker") != "customer":
            raise ValueError("Target event is not a customer event")
        source = self.conversation_user_audio_path(conversation_id)
        if source is None:
            raise FileNotFoundError("Pure-user WAV is unavailable")
        duration = float((conversation.get("user_audio") or {}).get("duration_s") or 0)
        anchor_s = float(events[index]["time_s"])
        if duration <= 0 or anchor_s < 0:
            raise ValueError("Target event has no reliable audio anchor")
        customer_anchors = [
            float(item["time_s"])
            for item in events
            if item.get("speaker") == "customer" and float(item["time_s"]) >= 0
        ]
        prior = [value for value in customer_anchors if value < anchor_s]
        following = [value for value in customer_anchors if value > anchor_s]
        lower_bound = max(0.0, anchor_s - 15.0)
        upper_bound = min(duration, anchor_s + 3.0)
        if prior:
            lower_bound = max(lower_bound, (max(prior) + anchor_s) / 2)
        if following:
            upper_bound = min(upper_bound, (anchor_s + min(following)) / 2)
        speech_trace = await asyncio.to_thread(
            self._locate_user_speech,
            source,
            anchor_s=anchor_s,
            lower_bound_s=lower_bound,
            upper_bound_s=upper_bound,
        )
        start_s = float(speech_trace["start_s"])
        end_s = float(speech_trace["end_s"])
        clip_key = uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"{batch_id}:{conversation_id}:{event_id}:pure-user-v2",
        ).hex
        destination = self.asr_clip_root / f"{clip_key}.wav"
        trace = await asyncio.to_thread(
            self._write_benchmark_clip,
            source,
            destination,
            start_s,
            end_s,
        )
        trace.update(
            {
                **speech_trace,
                "batch_id": batch_id,
                "conversation_id": conversation_id,
                "event_id": event_id,
                "boundary_rule": "excel_anchor_to_detected_user_speech_v2",
                "start_s": trace["start_s"],
                "end_s": trace["end_s"],
            }
        )
        return destination, trace

    async def finalize_benchmark_clip(self, benchmark_id: str) -> None:
        """Recoverably move one pending Benchmark sample to ready or failed."""
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            row = await (
                await database.execute(
                    "SELECT * FROM evaluation_benchmarks WHERE id=?", (benchmark_id,)
                )
            ).fetchone()
        if row is None or row["clip_status"] == "ready":
            return
        source = self.conversation_user_audio_path(str(row["conversation_id"]))
        destination = self.benchmark_clip_root / f"{benchmark_id}.wav"
        error: str | None = None
        trace: dict[str, Any] = {}
        try:
            if source is None:
                raise FileNotFoundError("Pure-user WAV is unavailable")
            conversation = await self.get_conversation(str(row["conversation_id"]))
            issue_types = {
                str(issue.get("issue_type")) for issue in (conversation or {}).get("issues", [])
            }
            quality = str(row["positioning_quality"])
            if quality not in {"exact", "expanded", "full_recording"}:
                raise ValueError("Benchmark position is unavailable")
            if quality != "full_recording" and "audio_timeline_mismatch" in issue_types:
                raise ValueError("MP3 and user WAV timelines are not aligned")
            trace = await asyncio.to_thread(
                self._write_benchmark_clip,
                source,
                destination,
                float(row["audio_start_s"]),
                float(row["audio_end_s"]),
            )
        except (OSError, RuntimeError, ValueError) as exc:
            destination.unlink(missing_ok=True)
            error = f"{type(exc).__name__}: {exc}"
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute(
                """UPDATE evaluation_benchmarks
                   SET clip_status=?,clip_path=?,clip_error=?,trace_json=? WHERE id=?""",
                (
                    "failed" if error else "ready",
                    None if error else str(destination),
                    error,
                    _json(trace),
                    benchmark_id,
                ),
            )
            await database.commit()

    async def recover_pending_benchmark_clips(self) -> None:
        """Resume incomplete clip creation after process restart."""
        async with aiosqlite.connect(self.database_path) as database:
            rows = await (
                await database.execute(
                    "SELECT id FROM evaluation_benchmarks WHERE clip_status='pending'"
                )
            ).fetchall()
        for row in rows:
            await self.finalize_benchmark_clip(str(row[0]))

    async def recover_missing_preliminary_reports(self) -> None:
        """Backfill missing reports and repair batches with an unlinked report."""
        async with aiosqlite.connect(self.database_path) as database:
            rows = await (
                await database.execute(
                    """SELECT b.id FROM evaluation_batches b
                       WHERE b.status IN ('awaiting_review','completed','completed_partial')
                         AND COALESCE(
                             json_extract(b.snapshot_json,'$.result_disposition'),
                             'formal'
                         ) != 'audit_only'
                         AND EXISTS (
                           SELECT 1 FROM evaluation_pass2_runs p WHERE p.batch_id=b.id
                         )
                       ORDER BY b.created_at"""
                )
            ).fetchall()
        for row in rows:
            batch_id = str(row[0])
            await self.freeze_preliminary_report(batch_id)

    @staticmethod
    def _review_copy(scenario: str) -> tuple[str, str, str, str]:
        """Return controlled bilingual UI copy instead of model-authored mixed language."""
        mappings = {
            "branches": (
                "Branch name needs audio confirmation",
                "分行名称需要回听确认",
                "Which branch or city did the customer actually say?",
                "用户实际说的是哪个分行或城市？",
            ),
            "分行名称与城市": (
                "Branch name needs audio confirmation",
                "分行名称需要回听确认",
                "Which branch or city did the customer actually say?",
                "用户实际说的是哪个分行或城市？",
            ),
            "Branch names and cities": (
                "Branch name needs audio confirmation",
                "分行名称需要回听确认",
                "Which branch or city did the customer actually say?",
                "用户实际说的是哪个分行或城市？",
            ),
            "数字与分行代码": (
                "Branch code needs audio confirmation",
                "分行代码需要回听确认",
                "Which digits or code did the customer actually say?",
                "用户实际说的是哪些数字或代码？",
            ),
            "Numbers and branch codes": (
                "Branch code needs audio confirmation",
                "分行代码需要回听确认",
                "Which digits or code did the customer actually say?",
                "用户实际说的是哪些数字或代码？",
            ),
            "numbers": (
                "Branch code needs audio confirmation",
                "分行代码需要回听确认",
                "Which digits or code did the customer actually say?",
                "用户实际说的是哪些数字或代码？",
            ),
            "客户类别": (
                "Customer tier needs audio confirmation",
                "客户类别需要回听确认",
                "Which customer tier did the customer actually say?",
                "用户实际说的是哪个客户类别？",
            ),
            "Customer tier": (
                "Customer tier needs audio confirmation",
                "客户类别需要回听确认",
                "Which customer tier did the customer actually say?",
                "用户实际说的是哪个客户类别？",
            ),
            "customer_tier": (
                "Customer tier needs audio confirmation",
                "客户类别需要回听确认",
                "Which customer tier did the customer actually say?",
                "用户实际说的是哪个客户类别？",
            ),
            "confirmation": (
                "Confirmation or negation needs audio confirmation",
                "确认或否定需要回听确认",
                "What confirmation, negation, or correction did the customer actually say?",
                "用户实际表达了什么确认、否定或纠正？",
            ),
        }
        return mappings.get(
            scenario,
            (
                "Transcript needs audio confirmation",
                "转写需要回听确认",
                "What did the customer actually say in this event?",
                "用户在该事件中实际说了什么？",
            ),
        )

    @staticmethod
    def _playback_range(
        conversation: dict[str, Any],
        decision: dict[str, Any],
        evidence_rows: list[dict[str, Any]],
    ) -> tuple[float, float, str, bool]:
        """Resolve the exact source interval used for pure-user Case retranscription."""
        duration = float((conversation.get("user_audio") or {}).get("duration_s") or 0)
        event_id = str(decision.get("event_id") or "")
        if duration <= 0:
            return 0.0, 0.0, "unavailable", False
        intervals = {
            (
                round(float(source_clip["start_s"]), 6),
                round(float(source_clip["end_s"]), 6),
            )
            for row in evidence_rows
            if str(row.get("event_id")) == event_id
            for source_clip in [(row.get("result") or {}).get("source_clip")]
            if isinstance(source_clip, dict)
            and source_clip.get("start_s") is not None
            and source_clip.get("end_s") is not None
        }
        if len(intervals) != 1:
            return 0.0, 0.0, "unavailable", False
        start_s, end_s = next(iter(intervals))
        if start_s < 0 or start_s >= duration or end_s <= start_s or end_s > duration:
            return 0.0, 0.0, "unavailable", False
        if "audio_timeline_mismatch" in {
            str(issue.get("issue_type")) for issue in conversation.get("issues", [])
        }:
            return 0.0, 0.0, "unavailable", False
        return start_s, end_s, "exact", True

    async def freeze_preliminary_report(
        self, batch_id: str, *, persist: bool = True
    ) -> dict[str, Any]:
        """Create the immutable automated-stage report from persisted evidence."""
        existing = await self.latest_report(batch_id)
        if (
            persist
            and existing is not None
            and existing["report_type"] in {"final", "final_partial"}
        ):
            return existing
        batch = await self.get_batch(batch_id)
        if batch is None:
            raise LookupError("Batch not found")
        tag_aliases: dict[str, str] = {}
        for tag in batch["snapshot"].get("scenario_tags", []):
            tag_key = str(tag.get("tag_key") or tag.get("name_en") or "").strip()
            if not tag_key:
                continue
            for alias in (tag_key, tag.get("name_en"), tag.get("name_zh")):
                if str(alias or "").strip():
                    tag_aliases[str(alias).strip()] = tag_key
        pass_one = await self.checkpoint_rows("evaluation_pass1_runs", batch_id)
        pass_two = await self.checkpoint_rows("evaluation_pass2_runs", batch_id)
        asr_rows = await self.checkpoint_rows("evaluation_case_asr_runs", batch_id)
        candidates: dict[tuple[str, str], dict[str, Any]] = {}
        for row in pass_one:
            for issue in (row.get("result") or {}).get("issues", []):
                for target in issue.get("target_events", []):
                    key = (str(row["conversation_id"]), str(target.get("event_id")))
                    candidates[key] = {
                        "priority": str(issue.get("priority") or "P2"),
                        "issue_title": str(issue.get("title") or "Candidate"),
                    }
        decisions = {
            (str(row["conversation_id"]), str(row["event_id"])): row["result"]
            for row in pass_two
            if row["status"] == "completed" and row.get("result")
        }
        first_pass_candidate_count = len(candidates)
        for key in decisions:
            if key not in candidates:
                candidates[key] = {
                    "priority": "control",
                    "issue_title": "Additional Good control",
                }
        evidence_rows: dict[str, list[dict[str, Any]]] = {}
        asr_by_case: dict[tuple[str, str], dict[str, str]] = {}
        for row in asr_rows:
            if row["status"] != "completed":
                continue
            evidence_rows.setdefault(str(row["conversation_id"]), []).append(row)
            result = row.get("result") or {}
            text = str(result.get("text") or "").strip()
            if text:
                case_key = (str(row["conversation_id"]), str(row["event_id"]))
                asr_by_case.setdefault(case_key, {})[str(row["provider"])] = text
        tag_counts: dict[str, int] = {}
        language_counts: dict[str, int] = {}
        decision_counts = {"Good Case": 0, "Bad Case": 0, "Needs manual audio review": 0}
        proposed: dict[str, dict[str, Any]] = {}
        cases: list[dict[str, Any]] = []
        for key, candidate in sorted(candidates.items()):
            conversation = await self.get_conversation(key[0])
            if conversation is None:
                continue
            event = next(
                (item for item in conversation["events"] if str(item["event_id"]) == key[1]),
                None,
            )
            decision = decisions.get(key) or {}
            decision_name = str(decision.get("decision") or "Not completed")
            if decision_name in decision_counts:
                decision_counts[decision_name] += 1
            raw_tag = str(decision.get("scenario_tag") or "Unclassified (AI suggested)")
            tag = tag_aliases.get(raw_tag, raw_tag)
            language = str(conversation.get("detected_language") or "unknown")
            if decision_name in decision_counts:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
                language_counts[language] = language_counts.get(language, 0) + 1
            proposal = decision.get("proposed_tag")
            if isinstance(proposal, dict) and all(
                str(proposal.get(field) or "").strip()
                for field in ("type", "name_en", "name_zh", "description_en", "description_zh")
            ):
                proposal_key = str(proposal["name_en"]).strip().lower()
                item = proposed.setdefault(proposal_key, {**proposal, "case_keys": []})
                item["case_keys"].append([key[0], key[1]])
            decision_with_event = {"event_id": key[1], **decision}
            audio_start, audio_end, positioning_quality, audio_available = self._playback_range(
                conversation,
                decision_with_event,
                evidence_rows.get(key[0], []),
            )
            evaluation_asr = dict(asr_by_case.get(key, {}))
            for item in decision.get("vendor_evidence", []):
                if not isinstance(item, dict):
                    continue
                provider = str(item.get("provider") or "").strip().lower()
                quoted_text = str(item.get("quoted_text") or "").strip()
                if provider and quoted_text:
                    evaluation_asr[provider] = quoted_text
            cases.append(
                {
                    "conversation_id": key[0],
                    "event_id": key[1],
                    "language": conversation.get("detected_language"),
                    "priority": candidate["priority"],
                    "issue_title": candidate["issue_title"],
                    "production_transcript": str((event or {}).get("text") or ""),
                    "audio_start_s": audio_start,
                    "audio_end_s": audio_end,
                    "audio_available": audio_available and audio_end > audio_start,
                    "positioning_quality": positioning_quality,
                    # Store only the evidence quoted for this Case. Repeating a full-call
                    # transcript in every row obscures the event-level decision trail.
                    "evaluation_asr": evaluation_asr,
                    "decision": decision_name,
                    "reference_text": decision.get("reference_text"),
                    "scenario_tag": tag,
                    "reason": decision.get("reason"),
                    "origin": decision.get("origin", "suspect_candidate"),
                    "label_status": (
                        "Pending manual"
                        if decision_name == "Needs manual audio review"
                        else "AI labeled"
                        if decision_name in {"Good Case", "Bad Case"}
                        else "Incomplete"
                    ),
                }
            )
        valid_events = int(batch["denominator"])
        source_user_events = int(batch["snapshot"].get("source_user_event_count", valid_events))
        excluded_count = max(0, source_user_events - valid_events)
        completed_cases = [
            case
            for case in cases
            if case["decision"] in {"Good Case", "Bad Case", "Needs manual audio review"}
        ]
        observation_groups: dict[str, dict[str, Any]] = {}
        for case in completed_cases:
            group = observation_groups.setdefault(
                str(case["scenario_tag"]),
                {"case_keys": [], "findings": []},
            )
            group["case_keys"].append([case["conversation_id"], case["event_id"]])
            reason = str(case.get("reason") or "").strip()
            if reason and reason not in group["findings"]:
                group["findings"].append(reason)
        suspicious = decision_counts["Bad Case"] + decision_counts["Needs manual audio review"]
        payload = {
            "batch_id": batch_id,
            "batch_name": batch["name"],
            "context_name": batch["context_name"],
            "report_type": "preliminary",
            "input_conversations": int(batch["input_count"]),
            "valid_user_events": valid_events,
            "source_user_events": source_user_events,
            "excluded_count": excluded_count,
            "excluded_reasons": (
                [{"reason": "pass_1_failed_or_unavailable", "count": excluded_count}]
                if excluded_count
                else []
            ),
            "source_warning_counts": batch["snapshot"].get("source_warning_counts", {}),
            "candidate_count": first_pass_candidate_count,
            "evaluated_case_count": len(completed_cases),
            "incomplete_case_count": len(cases) - len(completed_cases),
            "decision_counts": decision_counts,
            "suspected_count": suspicious,
            "suspected_rate": round((suspicious / valid_events * 100) if valid_events else 0, 2),
            "review_total": decision_counts["Needs manual audio review"],
            "review_completed": 0,
            "benchmark_count": decision_counts["Good Case"] + decision_counts["Bad Case"],
            "good_balance": batch["snapshot"].get("good_balance", {}),
            "tag_distribution": [
                {"name": name, "count": count}
                for name, count in sorted(tag_counts.items(), key=lambda item: (-item[1], item[0]))
            ],
            "language_distribution": [
                {"name": name, "count": count}
                for name, count in sorted(
                    language_counts.items(), key=lambda item: (-item[1], item[0])
                )
            ],
            "proposed_tags": [{"proposal_key": key, **value} for key, value in proposed.items()],
            "production_asr_observations": [
                {
                    "scenario_tag": name,
                    "case_count": count,
                    "finding": " | ".join(observation_groups[name]["findings"][:3])
                    or "No meaning-changing difference was recorded for this group.",
                    "case_keys": observation_groups[name]["case_keys"],
                }
                for name, count in sorted(tag_counts.items(), key=lambda item: (-item[1], item[0]))
            ],
            "cases": cases,
            "frozen_snapshot": batch["snapshot"],
        }
        if not persist:
            failure = batch["snapshot"].get("execution_failure") or {}
            payload.update(
                {
                    "report_type": "partial_results",
                    "incomplete": True,
                    "non_final": True,
                    "batch_status": batch["status"],
                    "failed_stage": failure.get("stage") or batch["stage"],
                    "failure": failure,
                    "cost": batch["cost"],
                    "budget": batch["budget"],
                }
            )
            return {
                "report_id": f"{batch_id}-PARTIAL",
                "batch_id": batch_id,
                "version": 0,
                "report_type": "partial_results",
                "payload": payload,
                "created_at": batch["updated_at"],
                "ephemeral": True,
            }
        comparable_payload = {
            key: value for key, value in payload.items() if key != "frozen_snapshot"
        }
        if existing is not None and existing["report_type"] == "preliminary":
            existing_comparable = {
                key: value
                for key, value in existing.get("payload", {}).items()
                if key != "frozen_snapshot"
            }
            if existing_comparable == comparable_payload:
                await self._link_preliminary_report(batch_id, existing)
                return existing
        now = _utcnow()
        version = int(existing["version"]) + 1 if existing is not None else 1
        report_id = f"{batch_id}-R{version}"
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute(
                """INSERT INTO evaluation_reports
                   (report_id,batch_id,version,report_type,payload_json,created_at)
                   VALUES (?,?,?,'preliminary',?,?)""",
                (report_id, batch_id, version, _json(payload), now),
            )
            await database.commit()
        report = await self.latest_report(batch_id)
        assert report is not None
        await self._link_preliminary_report(batch_id, report)
        return report

    async def _link_preliminary_report(
        self,
        batch_id: str,
        report: dict[str, Any],
    ) -> None:
        """Expose a frozen preliminary report through the owning batch immediately."""
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            row = await (
                await database.execute(
                    """SELECT report_type,suspected_numerator,snapshot_json
                       FROM evaluation_batches WHERE id=?""",
                    (batch_id,),
                )
            ).fetchone()
            if row is None:
                return
            suspected_count = int(report.get("payload", {}).get("suspected_count") or 0)
            snapshot = json.loads(row["snapshot_json"])
            already_linked = (
                row["report_type"] == "preliminary"
                and int(row["suspected_numerator"] or 0) == suspected_count
                and snapshot.get("latest_report_id") == report["report_id"]
            )
            if already_linked:
                return
            snapshot["latest_report_id"] = report["report_id"]
            snapshot["latest_report_type"] = report["report_type"]
            cursor = await database.execute(
                """UPDATE evaluation_batches
                   SET report_type=COALESCE(report_type,'preliminary'),suspected_numerator=?,
                       snapshot_json=?,updated_at=?,version=version+1
                   WHERE id=?""",
                (suspected_count, _json(snapshot), _utcnow(), batch_id),
            )
            if cursor.rowcount:
                await self._audit(
                    database,
                    "report.preliminary_linked",
                    str(report["report_id"]),
                    {"batch_id": batch_id},
                )
            await database.commit()

    async def freeze_final_report(
        self,
        batch_id: str,
        *,
        allow_partial: bool = False,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Freeze a second immutable report version from submitted human reviews."""
        if idempotency_key:
            previous = await self._command_result(idempotency_key)
            if previous is not None:
                return previous
        preliminary = await self._latest_report_of_types(batch_id, {"preliminary"})
        if preliminary is None:
            raise LookupError("Preliminary report not found")
        existing = await self._latest_report_of_types(batch_id, {"final", "final_partial"})
        if existing is not None:
            return existing
        reviews = await self.list_reviews("all")
        batch_reviews = [row for row in reviews if row["batch_id"] == batch_id]
        pending = [row for row in batch_reviews if row["status"] == "pending"]
        if pending and not allow_partial:
            raise ValueError("Manual review is not complete")

        payload = json.loads(_json(preliminary["payload"]))
        review_by_key = {
            (str(row["conversation_id"]), str(row["event_id"])): row
            for row in batch_reviews
            if row["status"] == "completed"
        }
        manual_bad = 0
        manual_good = 0
        unclear = 0
        for case in payload["cases"]:
            review = review_by_key.get((str(case["conversation_id"]), str(case["event_id"])))
            if review is None:
                continue
            case["language"] = review["language"]
            case["scenario_tag"] = review["scenario_tag"]
            if review["decision"] == "good":
                manual_good += 1
                case["decision"] = "Good Case"
                case["reference_text"] = review["label"]
                case["label_status"] = "Manual labeled"
            elif review["decision"] == "bad":
                manual_bad += 1
                case["decision"] = "Bad Case"
                case["reference_text"] = review["label"]
                case["label_status"] = "Manual labeled"
            else:
                unclear += 1
                case["decision"] = "Unclear"
                case["reference_text"] = None
                case["label_status"] = "Excluded as unclear"

        tag_counts: dict[str, int] = {}
        language_counts: dict[str, int] = {}
        for case in payload["cases"]:
            tag = str(case["scenario_tag"])
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
            language = str(case.get("language") or "unknown")
            language_counts[language] = language_counts.get(language, 0) + 1
        payload.update(
            {
                "report_type": "final_partial" if pending else "final",
                "review_completed": len(batch_reviews) - len(pending),
                "review_pending": len(pending),
                "manual_decision_counts": {
                    "Good Case": manual_good,
                    "Bad Case": manual_bad,
                    "Unclear": unclear,
                },
                "manually_confirmed_bad_count": manual_bad,
                "manually_confirmed_bad_rate": round(
                    (manual_bad / int(payload["valid_user_events"]) * 100)
                    if payload["valid_user_events"]
                    else 0,
                    2,
                ),
                "tag_distribution": [
                    {"name": name, "count": count}
                    for name, count in sorted(
                        tag_counts.items(), key=lambda item: (-item[1], item[0])
                    )
                ],
                "language_distribution": [
                    {"name": name, "count": count}
                    for name, count in sorted(
                        language_counts.items(), key=lambda item: (-item[1], item[0])
                    )
                ],
            }
        )
        now = _utcnow()
        latest = await self.latest_report(batch_id)
        version = int(latest["version"]) + 1 if latest is not None else 1
        report_id = f"{batch_id}-R{version}"
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute("PRAGMA busy_timeout = 5000")
            await database.execute("BEGIN IMMEDIATE")
            await database.execute(
                """INSERT INTO evaluation_reports
                   (report_id,batch_id,version,report_type,payload_json,created_at)
                   VALUES (?,?,?,?,?,?)""",
                (report_id, batch_id, version, payload["report_type"], _json(payload), now),
            )
            await database.execute(
                """UPDATE evaluation_batches
                   SET status=?,stage='completed',progress=100,review_completed=?,
                       report_type=?,updated_at=?,version=version+1 WHERE id=?""",
                (
                    "completed_partial" if pending else "completed",
                    len(batch_reviews) - len(pending),
                    payload["report_type"],
                    now,
                    batch_id,
                ),
            )
            await self._audit(
                database,
                "report.final_frozen",
                report_id,
                {
                    "partial": bool(pending),
                    "review_completed": len(batch_reviews) - len(pending),
                    "review_pending": len(pending),
                },
            )
            if idempotency_key:
                command_response = {
                    "report_id": report_id,
                    "batch_id": batch_id,
                    "version": version,
                    "report_type": payload["report_type"],
                    "payload": payload,
                    "created_at": now,
                }
                await self._save_command(database, idempotency_key, command_response)
            await database.commit()
        final = await self._report_version(batch_id, version)
        assert final is not None
        return final

    async def _latest_report_of_types(
        self,
        batch_id: str,
        report_types: set[str],
    ) -> dict[str, Any] | None:
        """Return the newest immutable report matching one of the requested types."""
        placeholders = ",".join("?" for _ in report_types)
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            row = await (
                await database.execute(
                    f"""SELECT * FROM evaluation_reports WHERE batch_id=?
                        AND report_type IN ({placeholders}) ORDER BY version DESC LIMIT 1""",
                    (batch_id, *sorted(report_types)),
                )
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["payload"] = json.loads(result.pop("payload_json"))
        return result

    async def _report_version(self, batch_id: str, version: int) -> dict[str, Any] | None:
        """Return one immutable report version."""
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            row = await (
                await database.execute(
                    "SELECT * FROM evaluation_reports WHERE batch_id=? AND version=?",
                    (batch_id, version),
                )
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["payload"] = json.loads(result.pop("payload_json"))
        return result

    async def latest_report(self, batch_id: str) -> dict[str, Any] | None:
        """Return the latest immutable report version for one batch."""
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            row = await (
                await database.execute(
                    """SELECT * FROM evaluation_reports WHERE batch_id=?
                       ORDER BY version DESC LIMIT 1""",
                    (batch_id,),
                )
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["payload"] = json.loads(result.pop("payload_json"))
        return result

    async def active_pricing_version(self) -> dict[str, Any]:
        """Return the newest immutable currency-conversion version."""
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            row = await (
                await database.execute(
                    """SELECT version,base_currency,cny_to_usd,rates_json,
                              default_batch_budget,source_note,created_at
                       FROM evaluation_pricing_versions ORDER BY version DESC LIMIT 1"""
                )
            ).fetchone()
        if row is None:
            raise LookupError("Pricing version is unavailable")
        result = dict(row)
        result["fx_rates"] = {"USD": 1.0, "CNY": float(result["cny_to_usd"])}
        from src.evaluation.pricing import pricing_catalog

        stored_rates = json.loads(str(result.pop("rates_json")))
        result["rates"] = stored_rates or pricing_catalog()
        return result

    async def reserve_budget(
        self,
        *,
        idempotency_key: str,
        batch_id: str,
        estimated_usd: float,
        pause_batch_on_rejection: bool = True,
    ) -> bool:
        """Atomically reserve one next external request without overspending."""
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            await database.execute("BEGIN IMMEDIATE")
            batch = await (
                await database.execute(
                    "SELECT cost,budget,status FROM evaluation_batches WHERE id=?",
                    (batch_id,),
                )
            ).fetchone()
            if batch is None:
                raise LookupError("Batch not found")
            if str(batch["status"]) == "budget_paused":
                await database.commit()
                return False
            existing = await (
                await database.execute(
                    "SELECT 1 FROM evaluation_cost_reservations WHERE idempotency_key=?",
                    (idempotency_key,),
                )
            ).fetchone()
            if existing is not None:
                await database.commit()
                return True
            reserved_row = await (
                await database.execute(
                    """SELECT SUM(estimated_usd) FROM evaluation_cost_reservations
                       WHERE batch_id=?""",
                    (batch_id,),
                )
            ).fetchone()
            reserved = float(reserved_row[0] or 0)
            if float(batch["cost"]) + reserved + max(0, estimated_usd) > float(batch["budget"]):
                if pause_batch_on_rejection:
                    await database.execute(
                        """UPDATE evaluation_batches
                           SET status='budget_paused',stage='budget_blocked',updated_at=?,
                               version=version+1
                           WHERE id=?""",
                        (_utcnow(), batch_id),
                    )
                await database.commit()
                return False
            await database.execute(
                """INSERT INTO evaluation_cost_reservations
                   (idempotency_key,batch_id,estimated_usd,created_at) VALUES(?,?,?,?)""",
                (idempotency_key, batch_id, max(0, estimated_usd), _utcnow()),
            )
            await database.commit()
        return True

    async def release_budget(self, idempotency_key: str) -> None:
        """Release a request reservation that did not produce billable usage."""
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute(
                "DELETE FROM evaluation_cost_reservations WHERE idempotency_key=?",
                (idempotency_key,),
            )
            await database.commit()

    async def save_pricing_version(
        self,
        *,
        cny_to_usd: float,
        source_note: str,
        default_batch_budget: float | None = None,
        asr_rates: list[dict[str, Any]] | None = None,
        llm_rates: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Append reviewed rates, FX, and default hard budget for future batches."""
        now = _utcnow()
        current = await self.active_pricing_version()
        normalized_llm_rates = None
        llm_selections = current["rates"].get("llm_selections", [])
        if llm_rates is not None:
            merged_rates: dict[tuple[str, str], dict[str, Any]] = {}
            for rate in [*current["rates"]["llm"], *llm_rates]:
                normalized_rate = dict(rate)
                provider = str(normalized_rate.get("provider", "")).strip()
                model = str(normalized_rate.get("model", "")).strip()
                canonical_model = normalize_pricing_model_id(provider, model)
                normalized_rate["provider"] = provider
                normalized_rate["model"] = canonical_model
                merged_rates[(provider.casefold(), canonical_model)] = normalized_rate
            normalized_llm_rates = list(merged_rates.values())
            llm_selections = [
                {
                    "provider": str(rate.get("provider", "")).strip(),
                    "model": str(rate.get("model", "")).strip(),
                }
                for rate in llm_rates
            ]
        rates = {
            "asr": asr_rates if asr_rates is not None else current["rates"]["asr"],
            "llm": (
                normalized_llm_rates
                if normalized_llm_rates is not None
                else current["rates"]["llm"]
            ),
            "llm_selections": llm_selections,
        }
        budget = float(default_batch_budget or current["default_batch_budget"])
        async with aiosqlite.connect(self.database_path) as database:
            cursor = await database.execute(
                """INSERT INTO evaluation_pricing_versions
                   (base_currency,cny_to_usd,rates_json,default_batch_budget,source_note,created_at)
                   VALUES ('USD',?,?,?,?,?)""",
                (cny_to_usd, _json(rates), budget, source_note.strip(), now),
            )
            version = int(cursor.lastrowid or 0)
            await self._audit(
                database,
                "pricing.version_created",
                str(version),
                {
                    "base_currency": "USD",
                    "cny_to_usd": cny_to_usd,
                    "default_batch_budget": budget,
                    "asr_rate_count": len(rates["asr"]),
                    "llm_rate_count": len(rates["llm"]),
                },
            )
            await database.commit()
        return await self.active_pricing_version()

    async def record_cost_entry(
        self,
        *,
        idempotency_key: str,
        batch_id: str,
        category: str,
        provider: str,
        stage: str,
        input_tokens: int = 0,
        cached_input_tokens: int = 0,
        reasoning_tokens: int = 0,
        output_tokens: int = 0,
        audio_seconds: float = 0,
        estimated_cost: float | None = None,
        currency: str = "USD",
        reservation_key: str | None = None,
    ) -> None:
        """Append one idempotent ASR or LLM usage entry without request content."""
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute(
                """INSERT OR IGNORE INTO evaluation_cost_ledger (
                   idempotency_key,batch_id,category,provider,stage,input_tokens,
                   cached_input_tokens,reasoning_tokens,output_tokens,audio_seconds,
                   estimated_cost,currency,created_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    idempotency_key,
                    batch_id,
                    category,
                    provider,
                    stage,
                    input_tokens,
                    cached_input_tokens,
                    reasoning_tokens,
                    output_tokens,
                    audio_seconds,
                    estimated_cost,
                    currency,
                    _utcnow(),
                ),
            )
            if reservation_key is not None:
                await database.execute(
                    "DELETE FROM evaluation_cost_reservations WHERE idempotency_key=?",
                    (reservation_key,),
                )
            batch_row = await (
                await database.execute(
                    "SELECT snapshot_json FROM evaluation_batches WHERE id=?",
                    (batch_id,),
                )
            ).fetchone()
            snapshot = json.loads(batch_row[0]) if batch_row else {}
            fx_rates = snapshot.get("pricing_version", {}).get(
                "fx_rates", {"USD": 1.0, "CNY": 0.14}
            )
            totals = await (
                await database.execute(
                    """SELECT currency,SUM(COALESCE(estimated_cost,0))
                       FROM evaluation_cost_ledger WHERE batch_id=? GROUP BY currency""",
                    (batch_id,),
                )
            ).fetchall()
            converted_total = sum(
                float(amount or 0) * float(fx_rates.get(str(row_currency), 0))
                for row_currency, amount in totals
            )
            await database.execute(
                "UPDATE evaluation_batches SET cost=?,updated_at=? WHERE id=?",
                (converted_total, _utcnow(), batch_id),
            )
            await database.commit()

    async def cost_summary(self, batch_id: str) -> dict[str, Any]:
        """Return separate ASR and LLM ledgers with actual usage and estimated money."""
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            rows = await (
                await database.execute(
                    """SELECT category,provider,stage,COUNT(*) AS calls,
                              SUM(input_tokens) AS input_tokens,
                              SUM(cached_input_tokens) AS cached_input_tokens,
                              SUM(reasoning_tokens) AS reasoning_tokens,
                              SUM(output_tokens) AS output_tokens,
                              SUM(audio_seconds) AS audio_seconds,
                              SUM(estimated_cost) AS estimated_cost,currency
                       FROM evaluation_cost_ledger WHERE batch_id=?
                       GROUP BY category,provider,stage,currency
                       ORDER BY category,provider,stage,currency""",
                    (batch_id,),
                )
            ).fetchall()
            batch_row = await (
                await database.execute(
                    "SELECT snapshot_json FROM evaluation_batches WHERE id=?",
                    (batch_id,),
                )
            ).fetchone()
        items = [dict(row) for row in rows]
        snapshot = json.loads(batch_row[0]) if batch_row else {}
        pricing_version = snapshot.get("pricing_version", {})
        fx_rates = pricing_version.get("fx_rates", {"USD": 1.0, "CNY": 0.14})
        for item in items:
            amount = item.get("estimated_cost")
            rate = float(fx_rates.get(str(item["currency"]), 0))
            item["fx_to_usd"] = rate
            item["converted_usd"] = None if amount is None else float(amount) * rate
        return {
            "batch_id": batch_id,
            "asr": [row for row in items if row["category"] == "asr"],
            "llm": [row for row in items if row["category"] == "llm"],
            "pricing_version": pricing_version,
            "total_usd": sum(float(row.get("converted_usd") or 0) for row in items),
            "money_status": "estimated_from_frozen_supplier_rates",
        }

    async def record_telemetry(
        self,
        *,
        batch_id: str,
        stage: str,
        event: str,
        outcome: str,
        provider: str | None = None,
        attempt: int = 1,
        latency_ms: float | None = None,
        queue_depth: int | None = None,
        trace_id: str | None = None,
    ) -> str:
        """Persist one content-free execution trace event."""
        event_id = f"telemetry-{uuid.uuid4().hex}"
        safe_trace_id = trace_id or f"trace-{uuid.uuid4().hex}"
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute(
                """INSERT INTO evaluation_telemetry (
                   id,batch_id,trace_id,stage,event,provider,outcome,attempt,
                   latency_ms,queue_depth,created_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    event_id,
                    batch_id,
                    safe_trace_id,
                    stage,
                    event,
                    provider,
                    outcome,
                    max(1, attempt),
                    None if latency_ms is None else max(0.0, latency_ms),
                    None if queue_depth is None else max(0, queue_depth),
                    _utcnow(),
                ),
            )
            await database.commit()
        return safe_trace_id

    async def telemetry_summary(self, batch_id: str) -> dict[str, Any]:
        """Aggregate safe operational counters and traces for one batch."""
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            rows = await (
                await database.execute(
                    """SELECT stage,event,provider,outcome,COUNT(*) AS count,
                              SUM(CASE WHEN attempt > 1 THEN 1 ELSE 0 END) AS retries,
                              AVG(latency_ms) AS average_latency_ms,
                              MAX(latency_ms) AS max_latency_ms,
                              MAX(queue_depth) AS max_queue_depth
                       FROM evaluation_telemetry WHERE batch_id=?
                       GROUP BY stage,event,provider,outcome
                       ORDER BY stage,event,provider,outcome""",
                    (batch_id,),
                )
            ).fetchall()
            traces = await (
                await database.execute(
                    """SELECT trace_id,stage,event,provider,outcome,attempt,latency_ms,
                              queue_depth,created_at
                       FROM evaluation_telemetry WHERE batch_id=?
                       ORDER BY created_at DESC LIMIT 100""",
                    (batch_id,),
                )
            ).fetchall()
        costs = await self.cost_summary(batch_id)
        return {
            "batch_id": batch_id,
            "counters": [dict(row) for row in rows],
            "recent_traces": [dict(row) for row in traces],
            "schema_failures": sum(
                int(row["count"]) for row in rows if row["event"] == "schema_failure"
            ),
            "costs": {
                "asr": costs["asr"],
                "llm": costs["llm"],
                "total_usd": costs["total_usd"],
            },
        }

    async def create_proposed_tag(self, report_id: str, proposal_key: str) -> dict[str, Any]:
        """Create one global tag and move its grouped mutable Cases atomically."""
        now = _utcnow()
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            await database.execute("PRAGMA foreign_keys = ON")
            await database.execute("BEGIN IMMEDIATE")
            existing = await (
                await database.execute(
                    """SELECT tag_id FROM evaluation_proposed_tag_actions
                       WHERE report_id=? AND proposal_key=?""",
                    (report_id, proposal_key),
                )
            ).fetchone()
            if existing is not None:
                await database.rollback()
                return await self.get_scenario_tag(str(existing["tag_id"]))
            report = await (
                await database.execute(
                    "SELECT batch_id,payload_json FROM evaluation_reports WHERE report_id=?",
                    (report_id,),
                )
            ).fetchone()
            if report is None:
                raise LookupError("Report not found")
            report_payload = json.loads(report["payload_json"])
            proposal = next(
                (
                    item
                    for item in report_payload.get("proposed_tags", [])
                    if item.get("proposal_key") == proposal_key
                ),
                None,
            )
            if proposal is None:
                raise LookupError("Proposed tag not found")
            required = ("type", "name_en", "name_zh", "description_en", "description_zh")
            if not all(str(proposal.get(field) or "").strip() for field in required):
                raise ValueError("Proposed tag is incomplete")
            duplicate = await (
                await database.execute(
                    """SELECT 1 FROM evaluation_scenario_tag_versions v
                       JOIN evaluation_scenario_tags t ON t.id=v.tag_id
                       WHERE t.deleted_at IS NULL AND v.version=t.current_version
                         AND (lower(v.name_en)=lower(?) OR v.name_zh=?)""",
                    (proposal["name_en"], proposal["name_zh"]),
                )
            ).fetchone()
            if duplicate is not None:
                raise ValueError("A current scenario tag already uses this name")
            tag_id = f"tag-{uuid.uuid4().hex}"
            tag_key = f"custom-{uuid.uuid4().hex[:12]}"
            await database.execute(
                "INSERT INTO evaluation_scenario_tags VALUES(?,?,1,1,NULL,?,?)",
                (tag_id, tag_key, now, now),
            )
            await database.execute(
                """INSERT INTO evaluation_scenario_tag_versions
                   VALUES(?,1,?,?,?,?,?,?,?)""",
                (
                    tag_id,
                    proposal["name_en"],
                    proposal["name_zh"],
                    proposal["description_en"],
                    proposal["description_zh"],
                    proposal["type"],
                    "[]",
                    now,
                ),
            )
            case_keys = {(str(item[0]), str(item[1])) for item in proposal.get("case_keys", [])}
            review_rows = await (
                await database.execute(
                    "SELECT id,payload_json FROM evaluation_reviews WHERE batch_id=?",
                    (report["batch_id"],),
                )
            ).fetchall()
            for review in review_rows:
                payload = json.loads(review["payload_json"])
                key = (str(payload.get("conversation_id")), str(payload.get("event_id")))
                if key in case_keys:
                    await database.execute(
                        "UPDATE evaluation_reviews SET scenario_tag=? WHERE id=?",
                        (tag_key, review["id"]),
                    )
            for conversation_id, event_id in case_keys:
                await database.execute(
                    """UPDATE evaluation_benchmarks
                       SET scenario_tag=?,revision=revision+1
                       WHERE batch_id=? AND conversation_id=? AND event_id=?""",
                    (tag_key, report["batch_id"], conversation_id, event_id),
                )
                benchmark_rows = await (
                    await database.execute(
                        """SELECT id FROM evaluation_benchmarks
                           WHERE batch_id=? AND conversation_id=? AND event_id=?""",
                        (report["batch_id"], conversation_id, event_id),
                    )
                ).fetchall()
                for benchmark_row in benchmark_rows:
                    await self._append_benchmark_revision(database, str(benchmark_row[0]))
            await database.execute(
                "INSERT INTO evaluation_proposed_tag_actions VALUES(?,?,?,?)",
                (report_id, proposal_key, tag_id, now),
            )
            await self._audit(
                database,
                "report.proposed_tag_created",
                report_id,
                {"proposal_key": proposal_key, "tag_id": tag_id, "case_count": len(case_keys)},
            )
            await database.commit()
        return await self.get_scenario_tag(tag_id)

    @staticmethod
    def _scenario_key(value: str) -> str:
        """Map frozen display labels to the stable values used by the current UI."""
        mappings = {
            "分行名称与城市": "branches",
            "Branch names and cities": "branches",
            "数字与分行代码": "numbers",
            "Numbers and branch codes": "numbers",
            "客户类别": "customer_tier",
            "Customer tier": "customer_tier",
            "确认与否定": "confirmation",
            "Confirmation and negation": "confirmation",
            "Unclassified (AI suggested)": "unclassified",
        }
        stable_values = {
            "branches",
            "numbers",
            "customer_tier",
            "confirmation",
            "overlap",
            "code_switching",
            "unclassified",
        }
        return mappings.get(value, value if value in stable_values else "unclassified")

    async def list_llm_models(self) -> list[dict[str, str]]:
        """Return the persisted, live-verified evaluation model catalog."""
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            rows = await (
                await database.execute(
                    """SELECT provider, model_id, base_url_host, source,
                              diagnostic_id, verified_at, updated_at
                       FROM evaluation_llm_models
                       ORDER BY provider, model_id"""
                )
            ).fetchall()
        return [dict(row) for row in rows]

    async def register_llm_model(
        self,
        *,
        provider: str,
        model_id: str,
        base_url_host: str,
        diagnostic_id: str,
    ) -> dict[str, str]:
        """Upsert one model only after its caller completed a real diagnostic."""
        now = _utcnow()
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute(
                """INSERT INTO evaluation_llm_models (
                       provider, model_id, base_url_host, source, diagnostic_id,
                       verified_at, updated_at
                   ) VALUES (?, ?, ?, 'live_diagnostic', ?, ?, ?)
                   ON CONFLICT(provider, model_id) DO UPDATE SET
                       base_url_host=excluded.base_url_host,
                       diagnostic_id=excluded.diagnostic_id,
                       verified_at=excluded.verified_at,
                       updated_at=excluded.updated_at""",
                (provider, model_id, base_url_host, diagnostic_id, now, now),
            )
            await self._audit(
                database,
                "llm_model.verified",
                f"{provider}:{model_id}",
                {
                    "provider": provider,
                    "model_id": model_id,
                    "base_url_host": base_url_host,
                    "diagnostic_id": diagnostic_id,
                },
            )
            await database.commit()
        return {
            "provider": provider,
            "model_id": model_id,
            "base_url_host": base_url_host,
            "source": "live_diagnostic",
            "diagnostic_id": diagnostic_id,
            "verified_at": now,
            "updated_at": now,
        }

    async def list_connections(self) -> list[dict[str, Any]]:
        """Return safe connection metadata without encrypted credentials."""
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            rows = await (
                await database.execute(
                    """SELECT provider,kind,base_url,status,diagnostic_id,
                              last_model_id,verified_at,updated_at
                       FROM evaluation_connections ORDER BY provider"""
                )
            ).fetchall()
        return [
            {
                **dict(row),
                "has_saved_key": True,
            }
            for row in rows
        ]

    async def list_asr_capabilities(self) -> list[dict[str, Any]]:
        """Return safe, persisted offline-ASR capability state."""
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            rows = await (
                await database.execute(
                    """SELECT provider,display_name,endpoint,model_id,parameters_json,
                              input_constraints_json,status,enabled,diagnostic_id,
                              validation_json,verified_at,updated_at,version
                       FROM evaluation_asr_capabilities ORDER BY provider"""
                )
            ).fetchall()
        capabilities: list[dict[str, Any]] = []
        for row in rows:
            item = {
                key: value
                for key, value in dict(row).items()
                if key not in {"parameters_json", "input_constraints_json", "validation_json"}
            }
            item.update(
                {
                    "parameters": json.loads(str(row["parameters_json"])),
                    "input_constraints": json.loads(str(row["input_constraints_json"])),
                    "validation": json.loads(str(row["validation_json"])),
                    "enabled": bool(row["enabled"]),
                    "available": bool(row["enabled"]) and row["status"] == "verified",
                }
            )
            capabilities.append(item)
        return capabilities

    async def set_asr_capability_validation(
        self,
        provider: str,
        *,
        status: str,
        diagnostic_id: str,
        summary: str,
    ) -> dict[str, Any]:
        """Persist one endpoint/auth and local model/input-contract validation result."""
        if status not in {"verified", "unavailable"}:
            raise ValueError("ASR capability status must be verified or unavailable")
        now = _utcnow()
        async with aiosqlite.connect(self.database_path) as database:
            cursor = await database.execute(
                """UPDATE evaluation_asr_capabilities
                   SET status=?,diagnostic_id=?,validation_json=?,verified_at=?,
                       updated_at=?,version=version+1 WHERE provider=?""",
                (
                    status,
                    diagnostic_id,
                    _json(
                        {
                            "endpoint_authenticated": status == "verified",
                            "contract_validated": True,
                            "summary": summary,
                        }
                    ),
                    now if status == "verified" else None,
                    now,
                    provider,
                ),
            )
            if cursor.rowcount != 1:
                raise LookupError(f"Unknown ASR capability: {provider}")
            await self._audit(
                database,
                "asr_capability.validated",
                provider,
                {
                    "provider": provider,
                    "status": status,
                    "diagnostic_id": diagnostic_id,
                },
            )
            await database.commit()
        return next(
            item for item in await self.list_asr_capabilities() if item["provider"] == provider
        )

    async def unavailable_asr_providers(self, providers: Sequence[str]) -> list[str]:
        """Return requested providers that are not both enabled and verified."""
        available = {
            str(item["provider"])
            for item in await self.list_asr_capabilities()
            if item["available"]
        }
        return sorted(set(providers) - available)

    async def get_connection(self, provider: str) -> dict[str, Any] | None:
        """Return one internal connection record including its encrypted key."""
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            row = await (
                await database.execute(
                    "SELECT * FROM evaluation_connections WHERE provider=?",
                    (provider,),
                )
            ).fetchone()
        return dict(row) if row is not None else None

    async def save_connection(
        self,
        *,
        provider: str,
        kind: str,
        base_url: str,
        encrypted_api_key: str,
        diagnostic_id: str,
        model_id: str | None,
    ) -> dict[str, Any]:
        """Persist one successfully verified encrypted provider connection."""
        now = _utcnow()
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute(
                """INSERT INTO evaluation_connections (
                       provider,kind,base_url,encrypted_api_key,status,diagnostic_id,
                       last_model_id,verified_at,updated_at
                   ) VALUES (?,?,?,?,'verified',?,?,?,?)
                   ON CONFLICT(provider) DO UPDATE SET
                       kind=excluded.kind,
                       base_url=excluded.base_url,
                       encrypted_api_key=excluded.encrypted_api_key,
                       status='verified',
                       diagnostic_id=excluded.diagnostic_id,
                       last_model_id=excluded.last_model_id,
                       verified_at=excluded.verified_at,
                       updated_at=excluded.updated_at""",
                (
                    provider,
                    kind,
                    base_url,
                    encrypted_api_key,
                    diagnostic_id,
                    model_id,
                    now,
                    now,
                ),
            )
            await self._audit(
                database,
                "connection.verified_and_saved",
                provider,
                {
                    "provider": provider,
                    "kind": kind,
                    "base_url": base_url,
                    "diagnostic_id": diagnostic_id,
                    "model_id": model_id,
                },
            )
            await database.commit()
        saved = await self.get_connection(provider)
        assert saved is not None
        saved.pop("encrypted_api_key", None)
        saved["has_saved_key"] = True
        return saved

    async def create_batch(self, request: EvaluationBatchCreate) -> dict[str, Any]:
        """Freeze a validated real source import without fabricating provider results."""
        previous = await self._command_result(request.idempotency_key)
        if previous:
            return previous
        source = self.fixture_status()
        if not source["valid"]:
            raise ValueError(
                f"Source audit found {source['blocking_issue_count']} blocking issues; "
                "fix or replace "
                "the affected files before starting an evaluation"
            )
        now = _utcnow()
        batch_id = f"EV-{datetime.now(UTC):%Y%m%d}-{uuid.uuid4().hex[:4].upper()}"
        scenario_tags = [tag for tag in await self.list_scenario_tags() if tag["enabled"]]
        configuration = await self.context_snapshot(request.context_key)
        pricing_version = await self.active_pricing_version()
        missing_prices = await self._models_without_frozen_prices(
            pricing_version,
            [request.pass_1_model, request.pass_2_model],
        )
        if missing_prices:
            raise ValueError(
                "Pricing is unavailable for selected model(s): "
                + ", ".join(missing_prices)
                + ". Add model pricing in Cost settings before starting the evaluation."
            )
        context = configuration["context"]
        warning_counts: dict[str, int] = {}
        for issue in source.get("warnings", []):
            issue_type = str(issue.get("issue_type") or "source_warning")
            warning_counts[issue_type] = warning_counts.get(issue_type, 0) + 1
        snapshot = {
            "context_key": request.context_key,
            "screening_strategy": request.screening_strategy,
            "providers": request.asr_providers,
            "pass_1_model": request.pass_1_model,
            "pass_2_model": request.pass_2_model,
            "source": source["source"],
            "source_counts": source["counts"],
            "source_event_count": source["event_count"],
            "source_user_event_count": source["user_event_count"],
            "source_warning_counts": warning_counts,
            "mock_external_calls": False,
            "provider_execution": "queued",
            "retention": {
                "class": "evaluation_10y",
                "expires_at": _ten_year_retention_expiry(now),
                "automatic_cleanup_before_expiry": False,
            },
            "evaluation_context": context,
            "reference_dictionaries": configuration["reference_dictionaries"],
            "scenario_tags": scenario_tags,
            "pass_1_prompt": configuration["pass_1_prompt"],
            "pass_2_prompt": configuration["pass_2_prompt"],
            "pricing_version": pricing_version,
        }
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute(
                """INSERT INTO evaluation_batches (
                    id,name,context_name,input_count,status,stage,progress,denominator,
                    excluded_count,cost,budget,providers_json,snapshot_json,
                    simulation_started_at,created_at,updated_at,version
                ) VALUES (?,?,?,?,'running','pass_1',21,?,0,0,?,?,?,NULL,?,?,1)""",
                (
                    batch_id,
                    request.name.strip(),
                    f"{context['name']} {context['version']}",
                    source["conversation_count"],
                    source["user_event_count"],
                    request.budget_limit,
                    _json(request.asr_providers),
                    _json(snapshot),
                    now,
                    now,
                ),
            )
            database.row_factory = aiosqlite.Row
            row = await (
                await database.execute("SELECT * FROM evaluation_batches WHERE id=?", (batch_id,))
            ).fetchone()
            assert row is not None
            response = self._batch(row)
            await self._audit(
                database,
                "batch.started",
                batch_id,
                {"source": source["source"], "provider_execution": "queued"},
            )
            await database.commit()
        return response

    async def _models_without_frozen_prices(
        self,
        pricing_version: dict[str, Any],
        model_ids: list[str],
    ) -> list[str]:
        """Return selected models that cannot be priced by the immutable snapshot."""
        provider_names = {
            "gemini": "Gemini",
            "gpt": "GPT",
            "qwen": "Qwen",
            "deepseek": "DeepSeek",
            "azure_gpt": "Azure GPT",
            "openrouter": "OpenRouter",
        }
        catalog = await self.list_llm_models()
        rates = pricing_version.get("rates", {}).get("llm", [])
        missing: list[str] = []
        for raw_model_id in dict.fromkeys(model_ids):
            model_id = raw_model_id.strip()
            qualified_provider, catalog_model_id = (
                model_id.split("::", 1) if "::" in model_id else ("", model_id)
            )
            catalog_match = next(
                (
                    row
                    for row in catalog
                    if str(row["model_id"]) == catalog_model_id
                    and (not qualified_provider or str(row["provider"]) == qualified_provider)
                ),
                None,
            )
            if catalog_match is not None:
                provider = str(catalog_match["provider"])
                model_id = catalog_model_id
            else:
                provider_key = next(
                    (key for key in provider_names if model_id.casefold().startswith(f"{key}-")),
                    "",
                )
                provider = provider_names.get(provider_key, "")
            normalized_model = normalize_pricing_model_id(provider, model_id)
            matched = any(
                str(rate.get("provider", "")).casefold() == provider.casefold()
                and normalize_pricing_model_id(
                    provider,
                    str(rate.get("model", "")),
                )
                == normalized_model
                for rate in rates
            )
            if not matched:
                missing.append(model_id)
        return missing

    async def act_on_batch(
        self,
        batch_id: str,
        request: EvaluationBatchAction,
    ) -> dict[str, Any]:
        """Persist an optimistic execution transition before the runner acts on it."""
        previous = await self._command_result(request.idempotency_key)
        if previous:
            return previous
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            row = await (
                await database.execute("SELECT * FROM evaluation_batches WHERE id=?", (batch_id,))
            ).fetchone()
            if row is None:
                raise LookupError("Batch not found")
            if row["version"] != request.expected_version:
                raise RuntimeError("The batch changed; refresh before retrying")
            allowed: dict[str, set[str]] = {
                "start": {"data_ready"},
                "pause": {"running"},
                "resume": {"paused", "budget_paused"},
                "stop": {"data_ready", "running", "paused", "budget_paused", "partially_failed"},
                "retry_failed": {"partially_failed", "completed_partial"},
            }
            if row["status"] not in allowed[request.action]:
                raise ValueError(f"Batch status {row['status']} cannot {request.action}")
            target_status = {
                "start": "running",
                "pause": "paused",
                "resume": "running",
                "stop": "stopped",
                "retry_failed": "running",
            }[request.action]
            target_stage = (
                "stopped"
                if request.action == "stop"
                else "pass_1"
                if request.action == "start"
                else row["stage"]
            )
            await database.execute(
                """UPDATE evaluation_batches SET status=?,stage=?,updated_at=?,
                   version=version+1 WHERE id=?""",
                (target_status, target_stage, _utcnow(), batch_id),
            )
            updated = await (
                await database.execute("SELECT * FROM evaluation_batches WHERE id=?", (batch_id,))
            ).fetchone()
            assert updated is not None
            response = self._batch(updated)
            await self._save_command(database, request.idempotency_key, response)
            await self._audit(database, f"batch.{request.action}", batch_id, {})
            await database.commit()
        return response

    async def delete_batch(
        self,
        batch_id: str,
        *,
        expected_version: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Delete one safe terminal batch without touching shared source/configuration."""
        previous = await self._command_result(idempotency_key)
        if previous:
            return previous
        clip_paths: list[str] = []
        asr_clip_paths: list[Path] = []
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute("PRAGMA foreign_keys = ON")
            database.row_factory = aiosqlite.Row
            row = await (
                await database.execute("SELECT * FROM evaluation_batches WHERE id=?", (batch_id,))
            ).fetchone()
            if row is None:
                raise LookupError("Batch not found")
            if row["version"] != expected_version:
                raise RuntimeError("The batch changed; refresh before retrying")
            snapshot = json.loads(row["snapshot_json"])
            audit_only = snapshot.get("result_disposition") == "audit_only"
            deletable_statuses = {
                "failed",
                "partially_failed",
                "stopped",
                "awaiting_review",
                "completed",
                "completed_partial",
            }
            if not audit_only and row["status"] not in deletable_statuses:
                raise RuntimeError("Stop the evaluation before deleting it")

            benchmark_rows = await (
                await database.execute(
                    "SELECT id,clip_path FROM evaluation_benchmarks WHERE batch_id=?",
                    (batch_id,),
                )
            ).fetchall()
            benchmark_ids = [str(item["id"]) for item in benchmark_rows]
            clip_paths = [str(item["clip_path"]) for item in benchmark_rows if item["clip_path"]]
            case_rows = await (
                await database.execute(
                    """SELECT DISTINCT conversation_id,event_id
                       FROM evaluation_case_asr_runs WHERE batch_id=?""",
                    (batch_id,),
                )
            ).fetchall()
            asr_clip_paths = [
                self.asr_clip_root
                / (
                    uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"{batch_id}:{item['conversation_id']}:{item['event_id']}:{version}",
                    ).hex
                    + ".wav"
                )
                for item in case_rows
                for version in ("pure-user-v1", "pure-user-v2")
            ]
            report_rows = await (
                await database.execute(
                    "SELECT report_id FROM evaluation_reports WHERE batch_id=?",
                    (batch_id,),
                )
            ).fetchall()
            report_ids = [str(item["report_id"]) for item in report_rows]
            if benchmark_ids:
                await database.executemany(
                    "DELETE FROM evaluation_benchmark_revisions WHERE benchmark_id=?",
                    [(item,) for item in benchmark_ids],
                )
            if report_ids:
                await database.executemany(
                    "DELETE FROM evaluation_proposed_tag_actions WHERE report_id=?",
                    [(item,) for item in report_ids],
                )
            await database.execute("DELETE FROM evaluation_reviews WHERE batch_id=?", (batch_id,))
            await database.execute(
                "DELETE FROM evaluation_benchmarks WHERE batch_id=?",
                (batch_id,),
            )
            await database.execute("DELETE FROM evaluation_audit WHERE object_id=?", (batch_id,))
            await database.execute(
                "DELETE FROM evaluation_commands WHERE json_extract(response_json,'$.id')=?",
                (batch_id,),
            )
            await database.execute("DELETE FROM evaluation_batches WHERE id=?", (batch_id,))
            response = {"id": batch_id, "deleted": True}
            await self._save_command(database, idempotency_key, response)
            await self._audit(
                database,
                "batch.deleted",
                batch_id,
                {"prior_status": row["status"], "audit_only": audit_only},
            )
            await database.commit()

        clip_root = self.benchmark_clip_root.resolve()
        for raw_path in clip_paths:
            candidate = Path(raw_path)
            if not candidate.is_absolute():
                candidate = self.benchmark_clip_root / candidate
            resolved = candidate.resolve()
            if resolved == clip_root or clip_root not in resolved.parents:
                continue
            resolved.unlink(missing_ok=True)
        for candidate in asr_clip_paths:
            resolved = candidate.resolve()
            clip_root = self.asr_clip_root.resolve()
            if resolved != clip_root and clip_root in resolved.parents:
                resolved.unlink(missing_ok=True)
        return response

    async def list_reviews(self, status: str = "pending") -> list[dict[str, Any]]:
        """Return real review cases only; a clean store therefore returns none."""
        query = """SELECT r.* FROM evaluation_reviews r
                   JOIN evaluation_batches b ON b.id=r.batch_id
                   WHERE COALESCE(
                       json_extract(b.snapshot_json,'$.result_disposition'),
                       'formal'
                   ) != 'audit_only'"""
        params: tuple[object, ...] = ()
        if status != "all":
            query += " AND r.status=?"
            params = (status,)
        query += " ORDER BY r.id"
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            rows = await (await database.execute(query, params)).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            payload = json.loads(row["payload_json"])
            issue_en, issue_zh, question_en, question_zh = self._review_copy(
                str(row["scenario_tag"])
            )
            if not payload.get("issue_en") or _CJK_TEXT.search(str(payload["issue_en"])):
                payload["issue_en"] = issue_en
            if not payload.get("question_en") or _CJK_TEXT.search(str(payload["question_en"])):
                payload["question_en"] = question_en
            payload.setdefault("issue_zh", issue_zh)
            payload.setdefault("question_zh", question_zh)
            payload.update(
                {
                    "id": row["id"],
                    "batch_id": row["batch_id"],
                    "status": row["status"],
                    "decision": row["decision"],
                    "label": row["label"],
                    "language": row["language"],
                    "scenario_tag": row["scenario_tag"],
                    "version": row["version"],
                    "audio_url": f"/api/evaluation/reviews/{row['id']}/audio",
                }
            )
            result.append(payload)
        return result

    async def review_audio_path(self, review_id: str) -> Path | None:
        """Resolve a real review case to its pure-customer WAV source."""
        async with aiosqlite.connect(self.database_path) as database:
            row = await (
                await database.execute(
                    "SELECT payload_json FROM evaluation_reviews WHERE id=?", (review_id,)
                )
            ).fetchone()
        if row is None:
            return None
        conversation_id = json.loads(row[0])["conversation_id"]
        return self.conversation_user_audio_path(conversation_id)

    def conversation_audio_path(self, conversation_id: str) -> Path | None:
        """Resolve a source conversation to its real full-call MP3."""
        if _SAFE_CONVERSATION_ID.fullmatch(conversation_id) is None:
            return None
        path = self.dataset_root / "record" / f"{conversation_id}.mp3"
        return path if path.is_file() else None

    def conversation_user_audio_path(self, conversation_id: str) -> Path | None:
        """Resolve a source conversation to its real pure-customer WAV."""
        if _SAFE_CONVERSATION_ID.fullmatch(conversation_id) is None:
            return None
        path = self.dataset_root / "user_record" / f"{conversation_id}.wav"
        return path if path.is_file() else None

    async def submit_review(
        self,
        review_id: str,
        request: EvaluationReviewSubmit,
    ) -> dict[str, Any]:
        """Persist a decision only for an existing real review case."""
        previous = await self._command_result(request.idempotency_key)
        if previous:
            return previous
        benchmark_id: str | None = None
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            row = await (
                await database.execute("SELECT * FROM evaluation_reviews WHERE id=?", (review_id,))
            ).fetchone()
            if row is None:
                raise LookupError("Review case not found")
            if row["version"] != request.expected_version:
                raise RuntimeError("The review case changed; refresh before submitting")
            if row["status"] != "pending":
                raise ValueError("This review case is already complete")
            payload = json.loads(row["payload_json"])
            label = None
            if request.decision == "good":
                label = payload["production_transcript"]
            elif request.decision == "bad":
                label = request.label.strip() if request.label else None
            now = _utcnow()
            await database.execute(
                """UPDATE evaluation_reviews SET status='completed',decision=?,label=?,language=?,
                   scenario_tag=?,reviewed_at=?,version=version+1 WHERE id=?""",
                (
                    request.decision,
                    label,
                    request.language,
                    request.scenario_tag,
                    now,
                    review_id,
                ),
            )
            benchmark_created = request.decision in {"good", "bad"} and bool(label)
            if benchmark_created:
                benchmark_id = f"BM-M-{uuid.uuid4().hex[:8].upper()}"
                cursor = await database.execute(
                    """INSERT OR IGNORE INTO evaluation_benchmarks (
                       id,batch_id,conversation_id,event_id,case_type,source,language,scenario_tag,
                       label,audio_start_s,audio_end_s,origin,positioning_quality,clip_status,
                       clip_path,clip_error,trace_json,revision,created_at
                    ) VALUES (?,?,?,?,?,'manual',?,?,?,?,?,?,?,'pending',NULL,NULL,'{}',1,?)""",
                    (
                        benchmark_id,
                        row["batch_id"],
                        payload["conversation_id"],
                        payload["event_id"],
                        request.decision,
                        request.language,
                        request.scenario_tag,
                        label,
                        payload["start_s"],
                        payload["end_s"],
                        "manual_review",
                        str(payload.get("positioning_quality") or "unavailable"),
                        now,
                    ),
                )
                benchmark_created = bool(cursor.rowcount)
                if benchmark_created:
                    await self._append_benchmark_revision(database, benchmark_id)
            response = {
                "id": review_id,
                "decision": request.decision,
                "label": label,
                "benchmark_created": benchmark_created,
            }
            await self._audit(
                database,
                "review.submit",
                review_id,
                {"decision": request.decision, "benchmark_created": benchmark_created},
            )
            counts = await (
                await database.execute(
                    """SELECT COUNT(*) AS total,
                              SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS completed
                       FROM evaluation_reviews WHERE batch_id=?""",
                    (row["batch_id"],),
                )
            ).fetchone()
            review_total = int(counts["total"] if counts else 0)
            review_completed = int(counts["completed"] if counts else 0)
            response["remaining"] = review_total - review_completed
            await self._save_command(database, request.idempotency_key, response)
            await database.execute(
                """UPDATE evaluation_batches SET review_total=?,review_completed=?,
                   updated_at=?,version=version+1 WHERE id=?""",
                (review_total, review_completed, now, row["batch_id"]),
            )
            await database.commit()
        if benchmark_created and benchmark_id is not None:
            await self.finalize_benchmark_clip(benchmark_id)
        if review_total and review_completed == review_total:
            final_report = await self.freeze_final_report(str(row["batch_id"]))
            response["final_report_id"] = final_report["report_id"]
        return response

    async def list_benchmarks(
        self,
        *,
        language: str = "all",
        scenario_tag: str = "all",
        source: str = "all",
        case_type: str = "all",
        search: str = "",
        limit: int = 20,
        offset: int = 0,
        ids: list[str] | None = None,
        include_storage: bool = False,
    ) -> dict[str, Any]:
        """Query only real Benchmark rows using stable filters and pagination."""
        clauses: list[str] = [
            "COALESCE(json_extract(batch.snapshot_json,"
            "'$.result_disposition'),'formal') != 'audit_only'"
        ]
        params: list[object] = []
        if language != "all":
            clauses.append("benchmark.language=?")
            params.append(language)
        if scenario_tag != "all":
            clauses.append("benchmark.scenario_tag=?")
            params.append(scenario_tag)
        if source != "all":
            clauses.append("benchmark.source=?")
            params.append(source)
        if case_type != "all":
            clauses.append("benchmark.case_type=?")
            params.append(case_type)
        if search.strip():
            clauses.append(
                "(benchmark.conversation_id LIKE ? OR benchmark.label LIKE ? "
                "OR benchmark.id LIKE ?)"
            )
            pattern = f"%{search.strip()}%"
            params.extend((pattern, pattern, pattern))
        if ids:
            clauses.append(f"benchmark.id IN ({','.join('?' for _ in ids)})")
            params.extend(ids)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            source = (
                "evaluation_benchmarks benchmark LEFT JOIN evaluation_batches batch "
                "ON batch.id=benchmark.batch_id"
            )
            total = await (
                await database.execute(f"SELECT COUNT(*) FROM {source}{where}", params)
            ).fetchone()
            rows = await (
                await database.execute(
                    f"SELECT benchmark.* FROM {source}{where} "
                    "ORDER BY benchmark.created_at DESC,benchmark.id DESC LIMIT ? OFFSET ?",
                    (*params, limit, offset),
                )
            ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["trace"] = json.loads(str(item.pop("trace_json") or "{}"))
            item["audio_url"] = (
                f"/api/evaluation/benchmarks/{item['id']}/audio"
                if item["clip_status"] == "ready"
                else None
            )
            if not include_storage:
                item.pop("clip_path", None)
            items.append(item)
        return {
            "items": items,
            "total": int(total[0] if total else 0),
            "limit": limit,
            "offset": offset,
        }

    async def benchmark_audio_path(self, benchmark_id: str) -> Path | None:
        """Resolve only a ready managed Benchmark clip."""
        async with aiosqlite.connect(self.database_path) as database:
            row = await (
                await database.execute(
                    """SELECT clip_path FROM evaluation_benchmarks
                       WHERE id=? AND clip_status='ready'""",
                    (benchmark_id,),
                )
            ).fetchone()
        path = Path(str(row[0])) if row and row[0] else None
        return path if path and path.is_file() else None

    async def benchmark_revisions(self, benchmark_id: str) -> list[dict[str, Any]]:
        """Return immutable classification history for one Benchmark sample."""
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            rows = await (
                await database.execute(
                    """SELECT revision,label,language,scenario_tag,source,changed_at
                       FROM evaluation_benchmark_revisions WHERE benchmark_id=?
                       ORDER BY revision""",
                    (benchmark_id,),
                )
            ).fetchall()
        return [dict(row) for row in rows]

    async def update_benchmark(
        self,
        benchmark_id: str,
        *,
        label: str,
        language: str,
        scenario_tag: str,
        expected_revision: int,
    ) -> dict[str, Any]:
        """Append a correction revision with optimistic concurrency control."""
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            row = await (
                await database.execute(
                    "SELECT revision FROM evaluation_benchmarks WHERE id=?", (benchmark_id,)
                )
            ).fetchone()
            if row is None:
                raise LookupError("Benchmark sample not found")
            if int(row["revision"]) != expected_revision:
                raise RuntimeError("Benchmark sample changed; refresh before saving")
            revision = expected_revision + 1
            await database.execute(
                """UPDATE evaluation_benchmarks
                   SET label=?,language=?,scenario_tag=?,revision=? WHERE id=?""",
                (label.strip(), language, scenario_tag, revision, benchmark_id),
            )
            await self._append_benchmark_revision(database, benchmark_id)
            await self._audit(
                database,
                "benchmark.updated",
                benchmark_id,
                {"revision": revision},
            )
            await database.commit()
        result = await self.list_benchmarks(ids=[benchmark_id], limit=1)
        return result["items"][0]

    async def delete_benchmark(self, benchmark_id: str) -> dict[str, Any]:
        """Delete one Benchmark sample and only its managed derived clip."""
        clip_path: str | None = None
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            await database.execute("BEGIN IMMEDIATE")
            row = await (
                await database.execute(
                    "SELECT clip_path FROM evaluation_benchmarks WHERE id=?",
                    (benchmark_id,),
                )
            ).fetchone()
            if row is None:
                await database.rollback()
                raise LookupError("Benchmark sample not found")
            clip_path = str(row["clip_path"]) if row["clip_path"] else None
            await database.execute(
                "DELETE FROM evaluation_benchmark_revisions WHERE benchmark_id=?",
                (benchmark_id,),
            )
            await database.execute(
                "DELETE FROM evaluation_benchmarks WHERE id=?",
                (benchmark_id,),
            )
            await self._audit(
                database,
                "benchmark.deleted",
                benchmark_id,
                {"derived_clip_deleted": bool(clip_path)},
            )
            await database.commit()

        if clip_path:
            candidate = Path(clip_path)
            if not candidate.is_absolute():
                candidate = self.benchmark_clip_root / candidate
            clip_root = self.benchmark_clip_root.resolve()
            resolved = candidate.resolve()
            if resolved != clip_root and clip_root in resolved.parents:
                resolved.unlink(missing_ok=True)
        return {"id": benchmark_id, "deleted": True}

    async def create_benchmark_export(self, request: dict[str, Any]) -> dict[str, Any]:
        """Freeze one Benchmark export request as a durable expiring job."""
        export_id = f"EXP-{uuid.uuid4().hex.upper()}"
        now = datetime.now(UTC)
        expires_at = (now + timedelta(hours=24)).isoformat(timespec="seconds")
        created_at = now.isoformat(timespec="seconds")
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute(
                """INSERT INTO evaluation_benchmark_exports (
                   id,status,request_json,artifact_path,manifest_json,error,
                   created_at,expires_at,updated_at
                   ) VALUES (?,'pending',?,NULL,'[]',NULL,?,?,?)""",
                (export_id, _json(request), created_at, expires_at, created_at),
            )
            await database.commit()
        return await self.get_benchmark_export(export_id)  # type: ignore[return-value]

    async def get_benchmark_export(self, export_id: str) -> dict[str, Any] | None:
        """Return safe state for one export and expire stale artifacts."""
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            row = await (
                await database.execute(
                    "SELECT * FROM evaluation_benchmark_exports WHERE id=?", (export_id,)
                )
            ).fetchone()
            if row is None:
                return None
            result = dict(row)
            if result["status"] == "ready" and datetime.fromisoformat(
                str(result["expires_at"])
            ) <= datetime.now(UTC):
                await database.execute(
                    """UPDATE evaluation_benchmark_exports
                       SET status='expired',updated_at=? WHERE id=?""",
                    (_utcnow(), export_id),
                )
                await database.commit()
                artifact = result.get("artifact_path")
                if artifact:
                    Path(str(artifact)).unlink(missing_ok=True)
                result["status"] = "expired"
        result["request"] = json.loads(result.pop("request_json"))
        result["manifest"] = json.loads(result.pop("manifest_json"))
        result.pop("artifact_path", None)
        return result

    async def benchmark_export_request(self, export_id: str) -> dict[str, Any] | None:
        """Load the frozen request used by an export worker."""
        async with aiosqlite.connect(self.database_path) as database:
            row = await (
                await database.execute(
                    "SELECT request_json FROM evaluation_benchmark_exports WHERE id=?",
                    (export_id,),
                )
            ).fetchone()
        return json.loads(row[0]) if row else None

    async def finish_benchmark_export(
        self,
        export_id: str,
        *,
        artifact_path: Path | None = None,
        manifest: list[dict[str, str]] | None = None,
        error: str | None = None,
    ) -> None:
        """Commit the terminal state of one export without exposing filesystem paths."""
        status = "failed" if error else "ready"
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute(
                """UPDATE evaluation_benchmark_exports
                   SET status=?,artifact_path=?,manifest_json=?,error=?,updated_at=?
                   WHERE id=?""",
                (
                    status,
                    str(artifact_path) if artifact_path else None,
                    _json(manifest or []),
                    error,
                    _utcnow(),
                    export_id,
                ),
            )
            await database.commit()

    async def benchmark_export_artifact(self, export_id: str) -> Path | None:
        """Resolve a ready, unexpired export artifact for authenticated download."""
        state = await self.get_benchmark_export(export_id)
        if state is None or state["status"] != "ready":
            return None
        async with aiosqlite.connect(self.database_path) as database:
            row = await (
                await database.execute(
                    "SELECT artifact_path FROM evaluation_benchmark_exports WHERE id=?",
                    (export_id,),
                )
            ).fetchone()
        path = Path(str(row[0])) if row and row[0] else None
        return path if path and path.is_file() else None

    async def audit_benchmark_export_download(self, export_id: str) -> None:
        """Record an authorized export download without storing customer content."""
        request = await self.benchmark_export_request(export_id)
        async with aiosqlite.connect(self.database_path) as database:
            await self._audit(
                database,
                "benchmark_export.downloaded",
                export_id,
                {"sample_count": len((request or {}).get("sample_ids", []))},
            )
            await database.commit()

    async def register_elevenlabs_job(self, request_id: str, correlation_id: str) -> None:
        """Persist one webhook correlation without overwriting an early callback."""
        now = _utcnow()
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute(
                """INSERT INTO evaluation_elevenlabs_jobs (
                   request_id,correlation_id,status,result_json,error,created_at,updated_at
                   ) VALUES (?,?,'pending',NULL,NULL,?,?)
                   ON CONFLICT(correlation_id) DO UPDATE SET
                     request_id=excluded.request_id,
                     updated_at=excluded.updated_at""",
                (request_id, correlation_id, now, now),
            )
            await database.commit()

    async def complete_elevenlabs_job(
        self,
        *,
        request_id: str,
        correlation_id: str,
        result: dict[str, Any] | None,
        error: str | None,
    ) -> None:
        """Idempotently store one verified ElevenLabs webhook result."""
        now = _utcnow()
        status = "failed" if error else "completed"
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute(
                """INSERT INTO evaluation_elevenlabs_jobs (
                   request_id,correlation_id,status,result_json,error,created_at,updated_at
                   ) VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(correlation_id) DO UPDATE SET
                     request_id=excluded.request_id,
                     status=excluded.status,
                     result_json=excluded.result_json,
                     error=excluded.error,
                     updated_at=excluded.updated_at""",
                (
                    request_id,
                    correlation_id,
                    status,
                    _json(result) if result is not None else None,
                    error,
                    now,
                    now,
                ),
            )
            await database.commit()

    async def get_elevenlabs_job(self, correlation_id: str) -> dict[str, Any] | None:
        """Return safe state for a locally correlated Scribe webhook job."""
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            row = await (
                await database.execute(
                    """SELECT request_id,correlation_id,status,result_json,error,updated_at
                       FROM evaluation_elevenlabs_jobs WHERE correlation_id=?""",
                    (correlation_id,),
                )
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        raw_result = result.pop("result_json")
        result["result"] = json.loads(raw_result) if raw_result else None
        return result

    async def summary(self) -> dict[str, Any]:
        """Return counters without manufacturing evaluation conclusions."""
        batches = await self.list_batches()
        latest_evaluated = next(
            (
                batch
                for batch in batches
                if batch["result_disposition"] == "formal"
                and batch["report_type"] is not None
                and batch["denominator"]
                and batch["suspected_numerator"] is not None
            ),
            None,
        )
        reviews = await self.list_reviews("pending")
        benchmarks = await self.list_benchmarks(limit=5000)
        benchmark_items = benchmarks["items"]
        source = self.fixture_status()
        return {
            "batch_count": len(batches),
            "conversation_count": source["conversation_count"],
            "source_valid_conversations": source["valid_conversations"],
            "source_issue_count": len(source["issues"]),
            "source_blocking_issue_count": source["blocking_issue_count"],
            "source_warning_count": source["warning_count"],
            "source_user_events": source["user_event_count"],
            "pending_reviews": len(reviews),
            "pending_conversations": len({review["conversation_id"] for review in reviews}),
            "benchmark_count": benchmarks["total"],
            "benchmark_ai_count": sum(item["source"] == "ai" for item in benchmark_items),
            "benchmark_manual_count": sum(item["source"] == "manual" for item in benchmark_items),
            "suspected_numerator": (
                latest_evaluated["suspected_numerator"] if latest_evaluated else None
            ),
            "valid_user_events": latest_evaluated["denominator"] if latest_evaluated else None,
            "suspected_rate": (
                round(
                    latest_evaluated["suspected_numerator"] / latest_evaluated["denominator"] * 100,
                    1,
                )
                if latest_evaluated
                else None
            ),
        }
