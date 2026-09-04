"""Async persistence and retention for call history."""

from __future__ import annotations

import asyncio
import os
import shutil
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import aiosqlite

from src.history.models import (
    CallDetail,
    CallListResponse,
    CallSummary,
    HistoryTurn,
    TurnMetric,
)


class HistoryStore:
    """Persist safe call metadata, transcripts, metrics, and recording references."""

    def __init__(self, data_dir: Path) -> None:
        """Initialize paths and configurable retention limits."""
        self.data_dir = data_dir
        self.database_path = data_dir / "history.db"
        self.recordings_dir = data_dir / "recordings"
        self.history_days = _positive_int("VOICE_AGENT_HISTORY_RETENTION_DAYS", 30)
        self.recording_days = _positive_int("VOICE_AGENT_RECORDING_RETENTION_DAYS", 7)
        self.recording_max_bytes = _positive_int("VOICE_AGENT_RECORDING_MAX_BYTES", 5 * 1024**3)
        self.min_free_bytes = _positive_int("VOICE_AGENT_STORAGE_MIN_FREE_BYTES", 1024**3)

    async def initialize(self) -> None:
        """Create storage directories and idempotent schema."""
        await asyncio.to_thread(self.recordings_dir.mkdir, parents=True, exist_ok=True)
        async with aiosqlite.connect(self.database_path) as database:
            await database.executescript(
                """
                PRAGMA foreign_keys = ON;
                CREATE TABLE IF NOT EXISTS calls (
                    id TEXT PRIMARY KEY,
                    bot_id TEXT,
                    bot_name TEXT,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    status TEXT NOT NULL,
                    duration_ms REAL,
                    llm_provider TEXT NOT NULL,
                    llm_model TEXT NOT NULL,
                    tts_provider TEXT NOT NULL DEFAULT 'deepgram_flux',
                    tts_model TEXT NOT NULL DEFAULT 'flux-general-en',
                    tts_voice TEXT NOT NULL DEFAULT '',
                    tts_text_aggregation TEXT NOT NULL DEFAULT 'token',
                    asr_provider TEXT NOT NULL,
                    asr_model TEXT NOT NULL,
                    language TEXT NOT NULL,
                    audio_format TEXT NOT NULL,
                    sample_rate INTEGER NOT NULL,
                    channels INTEGER NOT NULL,
                    recording_path TEXT,
                    recording_status TEXT NOT NULL DEFAULT 'pending',
                    recording_bytes INTEGER NOT NULL DEFAULT 0,
                    error_category TEXT,
                    diagnostic_id TEXT
                );
                CREATE TABLE IF NOT EXISTS turns (
                    call_id TEXT NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
                    sequence INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    text TEXT NOT NULL,
                    created_ms REAL NOT NULL,
                    PRIMARY KEY (call_id, sequence)
                );
                CREATE TABLE IF NOT EXISTS turn_metrics (
                    call_id TEXT NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
                    turn_index INTEGER NOT NULL,
                    asr_final_latency_ms REAL,
                    llm_request_splicing_ms REAL,
                    llm_first_token_ms REAL,
                    tts_initial_ms REAL,
                    tts_first_audio_ms REAL,
                    playback_ms REAL,
                    server_to_playback_ms REAL,
                    turn_to_playback_ms REAL,
                    asr_final_reason TEXT,
                    incomplete_reason TEXT,
                    reasoning_tokens INTEGER,
                    reasoning_status TEXT NOT NULL,
                    reasoning_control TEXT,
                    PRIMARY KEY (call_id, turn_index)
                );
                CREATE INDEX IF NOT EXISTS idx_calls_started_at ON calls(started_at DESC);
                """
            )
            await self._migrate_turn_metrics(database)
            await self._migrate_calls(database)
            await database.execute(
                """UPDATE calls
                   SET ended_at = COALESCE(ended_at, ?), status = 'failed',
                       error_category = COALESCE(error_category, 'session_interrupted')
                   WHERE status = 'pending'""",
                (datetime.now(UTC).isoformat(),),
            )
            await database.commit()

    async def _migrate_calls(self, database: aiosqlite.Connection) -> None:
        """Add provider-neutral TTS snapshot columns idempotently."""
        for column_def in (
            "tts_provider TEXT NOT NULL DEFAULT 'deepgram_flux'",
            "tts_model TEXT NOT NULL DEFAULT 'flux-general-en'",
            "tts_voice TEXT NOT NULL DEFAULT ''",
            "tts_text_aggregation TEXT NOT NULL DEFAULT 'token'",
        ):
            try:
                await database.execute(f"ALTER TABLE calls ADD COLUMN {column_def}")
            except sqlite3.OperationalError as exc:
                if "duplicate column name" not in str(exc).lower():
                    raise

    async def _migrate_turn_metrics(self, database: aiosqlite.Connection) -> None:
        """Add latency-chain columns to existing turn_metrics tables idempotently."""
        new_columns = [
            "asr_final_latency_ms REAL",
            "llm_request_splicing_ms REAL",
            "tts_initial_ms REAL",
            "playback_ms REAL",
            "asr_final_reason TEXT",
            "incomplete_reason TEXT",
        ]
        for column_def in new_columns:
            try:
                await database.execute(f"ALTER TABLE turn_metrics ADD COLUMN {column_def}")
            except sqlite3.OperationalError as exc:
                if "duplicate column name" not in str(exc).lower():
                    raise

    async def start_call(
        self,
        *,
        call_id: str,
        bot_id: str | None,
        bot_name: str | None,
        llm_provider: str,
        llm_model: str,
        tts_provider: str = "deepgram_flux",
        tts_model: str = "flux-general-en",
        tts_voice: str = "",
        tts_text_aggregation: str = "token",
        asr_provider: str,
        asr_model: str,
        language: str,
        sample_rate: int,
        channels: int,
    ) -> None:
        """Insert a non-secret call snapshot before its WebSocket is claimed."""
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute(
                """INSERT INTO calls (
                    id, bot_id, bot_name, started_at, status, llm_provider, llm_model,
                    tts_provider, tts_model, tts_voice, tts_text_aggregation,
                    asr_provider, asr_model, language, audio_format, sample_rate, channels
                ) VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?, ?, 'flac', ?, ?)""",
                (
                    call_id,
                    bot_id,
                    bot_name,
                    datetime.now(UTC).isoformat(),
                    llm_provider,
                    llm_model,
                    tts_provider,
                    tts_model,
                    tts_voice,
                    tts_text_aggregation,
                    asr_provider,
                    asr_model,
                    language,
                    sample_rate,
                    channels,
                ),
            )
            await database.commit()

    async def finish_call(
        self,
        *,
        call_id: str,
        status: str,
        duration_ms: float,
        turns: list[HistoryTurn],
        metrics: list[TurnMetric],
        recording_path: Path | None,
        recording_status: str,
        error_category: str | None = None,
        diagnostic_id: str | None = None,
    ) -> None:
        """Atomically store the final transcript, metrics, and recording state."""
        relative_path = None
        recording_bytes = 0
        if recording_path is not None and recording_path.exists():
            relative_path = str(recording_path.relative_to(self.data_dir))
            recording_bytes = recording_path.stat().st_size
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute("PRAGMA foreign_keys = ON")
            await database.execute(
                """UPDATE calls SET ended_at=?, status=?, duration_ms=?, recording_path=?,
                   recording_status=?, recording_bytes=?, error_category=?, diagnostic_id=?
                   WHERE id=?""",
                (
                    datetime.now(UTC).isoformat(),
                    status,
                    round(duration_ms, 1),
                    relative_path,
                    recording_status,
                    recording_bytes,
                    error_category,
                    diagnostic_id,
                    call_id,
                ),
            )
            await database.executemany(
                "INSERT OR REPLACE INTO turns VALUES (?, ?, ?, ?, ?)",
                [(call_id, item.sequence, item.role, item.text, item.created_ms) for item in turns],
            )
            await database.executemany(
                """INSERT OR REPLACE INTO turn_metrics (
                       call_id, turn_index, asr_final_latency_ms,
                       llm_request_splicing_ms, llm_first_token_ms, tts_initial_ms,
                       tts_first_audio_ms, playback_ms, server_to_playback_ms,
                       turn_to_playback_ms, asr_final_reason, incomplete_reason,
                       reasoning_tokens, reasoning_status, reasoning_control
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        call_id,
                        item.turn_index,
                        item.asr_final_latency_ms,
                        item.llm_request_splicing_ms,
                        item.llm_first_token_ms,
                        item.tts_initial_ms,
                        item.tts_first_audio_ms,
                        item.playback_ms,
                        item.server_to_playback_ms,
                        item.turn_to_playback_ms,
                        item.asr_final_reason,
                        item.incomplete_reason,
                        item.reasoning_tokens,
                        item.reasoning_status,
                        item.reasoning_control,
                    )
                    for item in metrics
                ],
            )
            await database.commit()
        await self.cleanup()

    async def list_calls(self, *, limit: int, offset: int) -> CallListResponse:
        """Return a newest-first page of call summaries."""
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            total_row = await (
                await database.execute("SELECT COUNT(*) AS count FROM calls")
            ).fetchone()
            rows = await (
                await database.execute(
                    "SELECT * FROM calls ORDER BY started_at DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                )
            ).fetchall()
        return CallListResponse(
            items=[_summary(row) for row in rows],
            total=int(total_row["count"] if total_row else 0),
            limit=limit,
            offset=offset,
        )

    async def get_call(self, call_id: str) -> CallDetail | None:
        """Return one call with ordered transcripts and metrics."""
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            row = await (
                await database.execute("SELECT * FROM calls WHERE id=?", (call_id,))
            ).fetchone()
            if row is None:
                return None
            turns = await (
                await database.execute(
                    "SELECT * FROM turns WHERE call_id=? ORDER BY sequence", (call_id,)
                )
            ).fetchall()
            metrics = await (
                await database.execute(
                    "SELECT * FROM turn_metrics WHERE call_id=? ORDER BY turn_index", (call_id,)
                )
            ).fetchall()
        return CallDetail(
            **_summary(row).model_dump(),
            asr_provider=row["asr_provider"],
            asr_model=row["asr_model"],
            language=row["language"],
            audio_format=row["audio_format"],
            sample_rate=row["sample_rate"],
            channels=row["channels"],
            recording_bytes=row["recording_bytes"],
            turns=[
                HistoryTurn(**{key: item[key] for key in item.keys() if key != "call_id"})
                for item in turns
            ],
            metrics=[
                TurnMetric(**{k: item[k] for k in item.keys() if k != "call_id"})
                for item in metrics
            ],
        )

    async def recording_path(self, call_id: str) -> Path | None:
        """Resolve a recording path while preventing traversal outside data storage."""
        async with aiosqlite.connect(self.database_path) as database:
            row = await (
                await database.execute("SELECT recording_path FROM calls WHERE id=?", (call_id,))
            ).fetchone()
        if row is None or row[0] is None:
            return None
        candidate = (self.data_dir / row[0]).resolve()
        if self.recordings_dir.resolve() not in candidate.parents or not candidate.is_file():
            return None
        return candidate

    async def delete_call(self, call_id: str) -> bool:
        """Delete one call and its recording, if present."""
        path = await self.recording_path(call_id)
        async with aiosqlite.connect(self.database_path) as database:
            await database.execute("PRAGMA foreign_keys = ON")
            cursor = await database.execute("DELETE FROM calls WHERE id=?", (call_id,))
            await database.commit()
        if path is not None:
            await asyncio.to_thread(path.unlink, missing_ok=True)
        return cursor.rowcount > 0

    async def cleanup(self) -> None:
        """Apply age, quota, and minimum-free-space retention policies."""
        history_cutoff = (datetime.now(UTC) - timedelta(days=self.history_days)).isoformat()
        recording_cutoff = (datetime.now(UTC) - timedelta(days=self.recording_days)).isoformat()
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            expired = await (
                await database.execute(
                    """SELECT id, recording_path FROM calls
                       WHERE recording_path IS NOT NULL AND started_at < ?""",
                    (recording_cutoff,),
                )
            ).fetchall()
            await self._expire_recordings(database, expired)
            old_calls = await (
                await database.execute(
                    "SELECT id, recording_path FROM calls WHERE started_at < ?", (history_cutoff,)
                )
            ).fetchall()
            for row in old_calls:
                await self._unlink_relative(row["recording_path"])
            await database.execute("PRAGMA foreign_keys = ON")
            await database.execute("DELETE FROM calls WHERE started_at < ?", (history_cutoff,))
            await database.commit()
        await self._enforce_capacity()

    async def _expire_recordings(
        self, database: aiosqlite.Connection, rows: list[aiosqlite.Row]
    ) -> None:
        for row in rows:
            await self._unlink_relative(row["recording_path"])
            await database.execute(
                """UPDATE calls SET recording_path=NULL, recording_status='expired',
                   recording_bytes=0 WHERE id=?""",
                (row["id"],),
            )
        await database.commit()

    async def _enforce_capacity(self) -> None:
        usage = await asyncio.to_thread(shutil.disk_usage, self.data_dir)
        quota = min(self.recording_max_bytes, int(usage.total * 0.2))
        async with aiosqlite.connect(self.database_path) as database:
            database.row_factory = aiosqlite.Row
            rows = await (
                await database.execute(
                    """SELECT id, recording_path, recording_bytes FROM calls
                   WHERE recording_path IS NOT NULL ORDER BY started_at ASC"""
                )
            ).fetchall()
            total = sum(int(row["recording_bytes"]) for row in rows)
            for row in rows:
                usage = await asyncio.to_thread(shutil.disk_usage, self.data_dir)
                if total <= quota and usage.free >= self.min_free_bytes:
                    break
                await self._unlink_relative(row["recording_path"])
                await database.execute(
                    """UPDATE calls SET recording_path=NULL, recording_status='quota_deleted',
                       recording_bytes=0 WHERE id=?""",
                    (row["id"],),
                )
                total -= int(row["recording_bytes"])
            await database.commit()

    async def _unlink_relative(self, value: str | None) -> None:
        if not value:
            return
        candidate = (self.data_dir / value).resolve()
        if self.recordings_dir.resolve() in candidate.parents:
            await asyncio.to_thread(candidate.unlink, missing_ok=True)


def _summary(row: aiosqlite.Row) -> CallSummary:
    return CallSummary(
        id=row["id"],
        bot_id=row["bot_id"],
        bot_name=row["bot_name"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        status=row["status"],
        duration_ms=row["duration_ms"],
        llm_provider=row["llm_provider"],
        llm_model=row["llm_model"],
        tts_provider=row["tts_provider"],
        tts_model=row["tts_model"],
        tts_voice=row["tts_voice"],
        tts_text_aggregation=row["tts_text_aggregation"],
        has_recording=row["recording_path"] is not None,
        recording_status=row["recording_status"],
        error_category=row["error_category"],
        diagnostic_id=row["diagnostic_id"],
    )


def _positive_int(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value <= 0:
        raise RuntimeError(f"{name} must be positive")
    return value
