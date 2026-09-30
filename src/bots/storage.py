"""Async SQLite persistence for bot configurations."""

from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite

from src.bots.models import BotConfigFields, BotRecord

_COLUMNS = (
    "id, name, asr_provider, asr_model, turn_detection_source, asr_options, "
    "asr_language_hints, asr_eot_threshold, "
    "asr_eot_timeout_ms, asr_keyterms, asr_profanity_filter, asr_numerals, asr_redact, "
    "tts_provider, tts_voice, tts_model, tts_text_aggregation, tts_speed, "
    "tts_dynamic_speed_enabled, tts_speed_step, tts_expressivity, tts_stability, "
    "tts_similarity_boost, tts_model_improvement_opt_out, "
    "tts_style, tts_use_speaker_boost, tts_text_normalization, "
    "llm_provider, llm_base_url, llm_model, llm_temperature, "
    "reasoning_mode, llm_max_response_tokens, llm_request_timeout_seconds, "
    "system_prompt, opening_script, fallback_script, encrypted_deepgram_key, "
    "llm_key_provider, encrypted_llm_key, "
    "encrypted_elevenlabs_key, asr_key_provider, encrypted_asr_key, "
    "tts_key_provider, encrypted_tts_key, "
    "asr_account_catalog, "
    "created_at, updated_at"
)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS bots (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    asr_provider TEXT NOT NULL,
    asr_model TEXT NOT NULL DEFAULT 'flux-general-en',
    turn_detection_source TEXT NOT NULL DEFAULT 'provider_native',
    asr_options TEXT NOT NULL DEFAULT '{}',
    asr_language_hints TEXT NOT NULL DEFAULT '[]',
    asr_eot_threshold REAL NOT NULL DEFAULT 0.7,
    asr_eot_timeout_ms INTEGER NOT NULL DEFAULT 5000,
    asr_keyterms TEXT NOT NULL DEFAULT '[]',
    asr_profanity_filter INTEGER NOT NULL DEFAULT 0,
    asr_numerals INTEGER NOT NULL DEFAULT 0,
    asr_redact TEXT,
    tts_provider TEXT NOT NULL,
    tts_voice TEXT NOT NULL,
    tts_model TEXT NOT NULL DEFAULT 'flux-general-en',
    tts_text_aggregation TEXT,
    tts_speed REAL NOT NULL DEFAULT 1.0,
    tts_dynamic_speed_enabled INTEGER NOT NULL DEFAULT 0,
    tts_speed_step REAL NOT NULL DEFAULT 0.10,
    tts_expressivity INTEGER NOT NULL DEFAULT 0,
    tts_stability REAL NOT NULL DEFAULT 0.5,
    tts_similarity_boost REAL NOT NULL DEFAULT 0.8,
    tts_model_improvement_opt_out INTEGER NOT NULL DEFAULT 0,
    tts_style REAL NOT NULL DEFAULT 0.0,
    tts_use_speaker_boost INTEGER NOT NULL DEFAULT 0,
    tts_text_normalization TEXT NOT NULL DEFAULT 'auto',
    llm_provider TEXT NOT NULL,
    llm_base_url TEXT NOT NULL,
    llm_model TEXT NOT NULL,
    llm_temperature REAL NOT NULL DEFAULT 0.7,
    reasoning_mode TEXT NOT NULL DEFAULT 'provider_default',
    llm_max_response_tokens INTEGER NOT NULL DEFAULT 250,
    llm_request_timeout_seconds REAL NOT NULL DEFAULT 15.0,
    system_prompt TEXT NOT NULL,
    opening_script TEXT NOT NULL,
    fallback_script TEXT NOT NULL DEFAULT '',
    encrypted_deepgram_key TEXT,
    llm_key_provider TEXT,
    encrypted_llm_key TEXT,
    encrypted_elevenlabs_key TEXT,
    asr_key_provider TEXT,
    encrypted_asr_key TEXT,
    tts_key_provider TEXT,
    encrypted_tts_key TEXT,
    asr_account_catalog TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""


def _utcnow() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _row_to_record(row: Sequence[object]) -> BotRecord:
    keys = [column.strip() for column in _COLUMNS.split(",")]
    values = dict(zip(keys, row, strict=True))
    for key in ("asr_options", "asr_language_hints", "asr_keyterms"):
        values[key] = json.loads(str(values[key]))
    values["asr_account_catalog"] = (
        json.loads(str(values["asr_account_catalog"]))
        if values["asr_account_catalog"] is not None
        else None
    )
    return BotRecord.model_validate(values)


class BotStore:
    """Small async CRUD boundary around the bots table."""

    def __init__(self, db_path: Path) -> None:
        """Point the store at one SQLite file; initialize() creates it."""
        self._db_path = db_path

    async def initialize(self) -> None:
        """Create the database directory and table when missing."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(_CREATE_TABLE)
            columns = {
                row[1] for row in await (await db.execute("PRAGMA table_info(bots)")).fetchall()
            }
            if "reasoning_mode" not in columns:
                await db.execute(
                    "ALTER TABLE bots ADD COLUMN reasoning_mode TEXT NOT NULL "
                    "DEFAULT 'lowest_latency'"
                )
            if "asr_account_catalog" not in columns:
                await db.execute("ALTER TABLE bots ADD COLUMN asr_account_catalog TEXT")
            if "tts_model" not in columns:
                await db.execute(
                    "ALTER TABLE bots ADD COLUMN tts_model TEXT NOT NULL DEFAULT 'flux-general-en'"
                )
            if "encrypted_elevenlabs_key" not in columns:
                await db.execute("ALTER TABLE bots ADD COLUMN encrypted_elevenlabs_key TEXT")
            migrations = (
                "asr_model TEXT NOT NULL DEFAULT 'flux-general-en'",
                "turn_detection_source TEXT NOT NULL DEFAULT 'provider_native'",
                "asr_options TEXT NOT NULL DEFAULT '{}'",
                "asr_language_hints TEXT NOT NULL DEFAULT '[]'",
                "asr_eot_threshold REAL NOT NULL DEFAULT 0.7",
                "asr_eot_timeout_ms INTEGER NOT NULL DEFAULT 5000",
                "asr_keyterms TEXT NOT NULL DEFAULT '[]'",
                "asr_profanity_filter INTEGER NOT NULL DEFAULT 0",
                "asr_numerals INTEGER NOT NULL DEFAULT 0",
                "asr_redact TEXT",
                "tts_text_aggregation TEXT",
                "tts_speed REAL NOT NULL DEFAULT 1.0",
                "tts_dynamic_speed_enabled INTEGER NOT NULL DEFAULT 0",
                "tts_speed_step REAL NOT NULL DEFAULT 0.10",
                "tts_expressivity INTEGER NOT NULL DEFAULT 0",
                "tts_stability REAL NOT NULL DEFAULT 0.5",
                "tts_similarity_boost REAL NOT NULL DEFAULT 0.8",
                "tts_model_improvement_opt_out INTEGER NOT NULL DEFAULT 0",
                "tts_style REAL NOT NULL DEFAULT 0.0",
                "tts_use_speaker_boost INTEGER NOT NULL DEFAULT 0",
                "tts_text_normalization TEXT NOT NULL DEFAULT 'auto'",
                "llm_max_response_tokens INTEGER NOT NULL DEFAULT 250",
                "llm_temperature REAL NOT NULL DEFAULT 0.7",
                "llm_request_timeout_seconds REAL NOT NULL DEFAULT 15.0",
                "fallback_script TEXT NOT NULL DEFAULT ''",
                "llm_key_provider TEXT",
                "asr_key_provider TEXT",
                "encrypted_asr_key TEXT",
                "tts_key_provider TEXT",
                "encrypted_tts_key TEXT",
            )
            for column_def in migrations:
                if column_def.split()[0] not in columns:
                    await db.execute(f"ALTER TABLE bots ADD COLUMN {column_def}")
            await db.execute(
                """UPDATE bots
                   SET tts_text_aggregation = CASE
                       WHEN tts_provider = 'elevenlabs' THEN 'sentence'
                       ELSE 'token'
                   END
                   WHERE tts_text_aggregation IS NULL"""
            )
            await db.execute(
                "UPDATE bots SET reasoning_mode = 'minimal' WHERE reasoning_mode = 'lowest_latency'"
            )
            await db.execute(
                "UPDATE bots SET asr_provider = 'deepgram' WHERE asr_provider = 'deepgram_flux'"
            )
            await db.execute(
                """UPDATE bots
                   SET llm_key_provider = llm_provider
                   WHERE llm_key_provider IS NULL AND encrypted_llm_key IS NOT NULL"""
            )
            await db.execute(
                """UPDATE bots
                   SET asr_key_provider = 'deepgram',
                       encrypted_asr_key = encrypted_deepgram_key
                   WHERE encrypted_asr_key IS NULL AND encrypted_deepgram_key IS NOT NULL"""
            )
            await db.execute(
                """UPDATE bots
                   SET tts_key_provider = tts_provider,
                       encrypted_tts_key = CASE
                           WHEN tts_provider = 'elevenlabs' THEN encrypted_elevenlabs_key
                           ELSE encrypted_deepgram_key
                       END
                   WHERE encrypted_tts_key IS NULL"""
            )
            await db.commit()

    async def list(self) -> list[BotRecord]:
        """Return every bot, most recently updated first."""
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(f"SELECT {_COLUMNS} FROM bots ORDER BY updated_at DESC")
            rows = await cursor.fetchall()
        return [_row_to_record(row) for row in rows]

    async def get(self, bot_id: str) -> BotRecord | None:
        """Return one bot by ID, or None when it does not exist."""
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(f"SELECT {_COLUMNS} FROM bots WHERE id = ?", (bot_id,))
            row = await cursor.fetchone()
        return _row_to_record(row) if row is not None else None

    async def create(
        self,
        *,
        config: BotConfigFields,
        encrypted_deepgram_key: str | None,
        encrypted_llm_key: str | None,
        encrypted_elevenlabs_key: str | None,
        llm_key_provider: str | None = None,
        asr_key_provider: str | None = None,
        encrypted_asr_key: str | None = None,
        tts_key_provider: str | None = None,
        encrypted_tts_key: str | None = None,
        asr_account_catalog: dict[str, object] | None = None,
    ) -> BotRecord:
        """Insert one bot and return the stored record."""
        now = _utcnow()
        record = BotRecord(
            id=str(uuid.uuid4()),
            **config.model_dump(),
            encrypted_deepgram_key=encrypted_deepgram_key,
            llm_key_provider=llm_key_provider,
            encrypted_llm_key=encrypted_llm_key,
            encrypted_elevenlabs_key=encrypted_elevenlabs_key,
            asr_key_provider=asr_key_provider,
            encrypted_asr_key=encrypted_asr_key,
            tts_key_provider=tts_key_provider,
            encrypted_tts_key=encrypted_tts_key,
            asr_account_catalog=asr_account_catalog,
            created_at=now,
            updated_at=now,
        )
        async with aiosqlite.connect(self._db_path) as db:
            values = record.model_dump()
            values["asr_options"] = json.dumps(values["asr_options"])
            values["asr_language_hints"] = json.dumps(values["asr_language_hints"])
            values["asr_keyterms"] = json.dumps(values["asr_keyterms"])
            values["asr_account_catalog"] = (
                json.dumps(values["asr_account_catalog"])
                if values["asr_account_catalog"] is not None
                else None
            )
            await db.execute(
                f"INSERT INTO bots ({_COLUMNS}) VALUES "
                f"({', '.join('?' for _ in _COLUMNS.split(','))})",
                tuple(values[column.strip()] for column in _COLUMNS.split(",")),
            )
            await db.commit()
        return record

    async def update(
        self,
        bot_id: str,
        *,
        config: BotConfigFields,
        encrypted_deepgram_key: str | None,
        encrypted_llm_key: str | None,
        encrypted_elevenlabs_key: str | None,
        llm_key_provider: str | None = None,
        asr_key_provider: str | None = None,
        encrypted_asr_key: str | None = None,
        tts_key_provider: str | None = None,
        encrypted_tts_key: str | None = None,
        asr_account_catalog: dict[str, object] | None = None,
    ) -> BotRecord | None:
        """Replace one bot's mutable fields; None when the ID does not exist."""
        existing = await self.get(bot_id)
        if existing is None:
            return None
        record = BotRecord(
            id=bot_id,
            **config.model_dump(),
            encrypted_deepgram_key=encrypted_deepgram_key,
            llm_key_provider=llm_key_provider,
            encrypted_llm_key=encrypted_llm_key,
            encrypted_elevenlabs_key=encrypted_elevenlabs_key,
            asr_key_provider=asr_key_provider,
            encrypted_asr_key=encrypted_asr_key,
            tts_key_provider=tts_key_provider,
            encrypted_tts_key=encrypted_tts_key,
            asr_account_catalog=asr_account_catalog,
            created_at=existing.created_at,
            updated_at=_utcnow(),
        )
        values = record.model_dump()
        values["asr_options"] = json.dumps(values["asr_options"])
        values["asr_language_hints"] = json.dumps(values["asr_language_hints"])
        values["asr_keyterms"] = json.dumps(values["asr_keyterms"])
        values["asr_account_catalog"] = (
            json.dumps(values["asr_account_catalog"])
            if values["asr_account_catalog"] is not None
            else None
        )
        mutable_columns = [
            column.strip() for column in _COLUMNS.split(",") if column.strip() != "id"
        ]
        assignments = ", ".join(f"{column} = ?" for column in mutable_columns)
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                f"UPDATE bots SET {assignments} WHERE id = ?",
                tuple(values[column] for column in mutable_columns) + (bot_id,),
            )
            await db.commit()
        return record

    async def set_asr_account_catalog(
        self, bot_id: str, catalog: dict[str, object]
    ) -> BotRecord | None:
        """Persist one normalized account catalog for restart-safe validation."""
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "UPDATE bots SET asr_account_catalog=?, updated_at=? WHERE id=?",
                (json.dumps(catalog), _utcnow(), bot_id),
            )
            await db.commit()
        return await self.get(bot_id) if cursor.rowcount else None

    async def delete(self, bot_id: str) -> bool:
        """Delete one bot; return whether a row was removed."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("PRAGMA foreign_keys = ON")
            cursor = await db.execute("DELETE FROM bots WHERE id = ?", (bot_id,))
            await db.commit()
            return cursor.rowcount > 0
