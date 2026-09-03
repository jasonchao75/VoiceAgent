"""Async SQLite persistence for bot configurations."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite

from src.bots.models import BotConfigFields, BotRecord

_COLUMNS = (
    "id, name, asr_provider, tts_provider, tts_voice, llm_provider, llm_base_url, llm_model, "
    "system_prompt, opening_script, encrypted_deepgram_key, encrypted_llm_key, "
    "created_at, updated_at"
)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS bots (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    asr_provider TEXT NOT NULL,
    tts_provider TEXT NOT NULL,
    tts_voice TEXT NOT NULL,
    llm_provider TEXT NOT NULL,
    llm_base_url TEXT NOT NULL,
    llm_model TEXT NOT NULL,
    system_prompt TEXT NOT NULL,
    opening_script TEXT NOT NULL,
    encrypted_deepgram_key TEXT,
    encrypted_llm_key TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""


def _utcnow() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _row_to_record(row: Sequence[object]) -> BotRecord:
    keys = [column.strip() for column in _COLUMNS.split(",")]
    return BotRecord.model_validate(dict(zip(keys, row, strict=True)))


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
    ) -> BotRecord:
        """Insert one bot and return the stored record."""
        now = _utcnow()
        record = BotRecord(
            id=str(uuid.uuid4()),
            **config.model_dump(),
            encrypted_deepgram_key=encrypted_deepgram_key,
            encrypted_llm_key=encrypted_llm_key,
            created_at=now,
            updated_at=now,
        )
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                f"INSERT INTO bots ({_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                tuple(record.model_dump()[column.strip()] for column in _COLUMNS.split(",")),
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
    ) -> BotRecord | None:
        """Replace one bot's mutable fields; None when the ID does not exist."""
        existing = await self.get(bot_id)
        if existing is None:
            return None
        record = BotRecord(
            id=bot_id,
            **config.model_dump(),
            encrypted_deepgram_key=encrypted_deepgram_key,
            encrypted_llm_key=encrypted_llm_key,
            created_at=existing.created_at,
            updated_at=_utcnow(),
        )
        values = record.model_dump()
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

    async def delete(self, bot_id: str) -> bool:
        """Delete one bot; return whether a row was removed."""
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute("DELETE FROM bots WHERE id = ?", (bot_id,))
            await db.commit()
            return cursor.rowcount > 0
