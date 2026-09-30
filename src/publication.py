"""Persistent Bot publication, public links, and provider-scoped credentials."""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import aiosqlite

from src.bots.models import BotConfigFields, BotRecord

Component = Literal["asr", "tts", "llm"]


def _utcnow() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _config_json(record: BotRecord) -> str:
    config = BotConfigFields.model_validate(
        {field: getattr(record, field) for field in BotConfigFields.model_fields}
    )
    return json.dumps(config.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class ShareState:
    """Safe management view of one Bot's current publication state."""

    bot_id: str
    bot_name: str
    public_id: str | None
    title: str
    description: str
    active: bool
    published: bool
    available: bool
    revision: int | None
    published_at: str | None
    unpublished_changes: bool


@dataclass(frozen=True, slots=True)
class PublishedDemo:
    """Published snapshot plus credential references used to start a call."""

    bot_id: str
    bot_name: str
    public_id: str
    title: str
    description: str
    active: bool
    revision: int
    config_json: str
    asr_provider: str
    tts_provider: str
    llm_provider: str
    encrypted_asr_key: str | None
    encrypted_tts_key: str | None
    encrypted_llm_key: str | None

    @property
    def available(self) -> bool:
        """Return whether all credentials referenced by the snapshot exist."""
        return all((self.encrypted_asr_key, self.encrypted_tts_key, self.encrypted_llm_key))


class DemoPublicationStore:
    """SQLite boundary for immutable publications and stable public links."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    async def initialize(self) -> None:
        """Create publication tables and migrate current Bot credentials."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("PRAGMA foreign_keys = ON")
            await db.executescript(
                """
                CREATE TABLE IF NOT EXISTS bot_provider_credentials (
                    bot_id TEXT NOT NULL,
                    component TEXT NOT NULL CHECK(component IN ('asr', 'tts', 'llm')),
                    provider TEXT NOT NULL,
                    encrypted_key TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (bot_id, component, provider),
                    FOREIGN KEY (bot_id) REFERENCES bots(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS bot_publications (
                    bot_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    public_title TEXT NOT NULL,
                    public_description TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    asr_provider TEXT NOT NULL,
                    tts_provider TEXT NOT NULL,
                    llm_provider TEXT NOT NULL,
                    published_at TEXT NOT NULL,
                    PRIMARY KEY (bot_id, revision),
                    FOREIGN KEY (bot_id) REFERENCES bots(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS demo_links (
                    bot_id TEXT PRIMARY KEY,
                    public_id TEXT NOT NULL UNIQUE,
                    active INTEGER NOT NULL DEFAULT 1,
                    current_revision INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (bot_id) REFERENCES bots(id) ON DELETE CASCADE,
                    FOREIGN KEY (bot_id, current_revision)
                        REFERENCES bot_publications(bot_id, revision)
                );
                """
            )
            now = _utcnow()
            migrations = (
                ("asr", "asr_key_provider", "encrypted_asr_key"),
                ("tts", "tts_key_provider", "encrypted_tts_key"),
                ("llm", "llm_key_provider", "encrypted_llm_key"),
            )
            for component, provider_column, key_column in migrations:
                await db.execute(
                    f"""INSERT OR IGNORE INTO bot_provider_credentials
                        (bot_id, component, provider, encrypted_key, created_at, updated_at)
                        SELECT id, ?, {provider_column}, {key_column}, ?, ? FROM bots
                        WHERE {provider_column} IS NOT NULL AND {key_column} IS NOT NULL""",
                    (component, now, now),
                )
            await db.commit()

    async def get_credential(self, bot_id: str, component: Component, provider: str) -> str | None:
        """Return one ciphertext for server-side resolution only."""
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                """SELECT encrypted_key FROM bot_provider_credentials
                   WHERE bot_id=? AND component=? AND provider=?""",
                (bot_id, component, provider),
            )
            row = await cursor.fetchone()
        return str(row[0]) if row else None

    async def sync_credential(
        self,
        *,
        bot_id: str,
        component: Component,
        provider: str,
        should_save: bool,
        encrypted_key: str | None,
    ) -> None:
        """Apply the selected provider's keep, replace, or clear intent."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("PRAGMA foreign_keys = ON")
            if not should_save:
                await db.execute(
                    """DELETE FROM bot_provider_credentials
                       WHERE bot_id=? AND component=? AND provider=?""",
                    (bot_id, component, provider),
                )
            elif encrypted_key is not None:
                now = _utcnow()
                await db.execute(
                    """INSERT INTO bot_provider_credentials
                       (bot_id, component, provider, encrypted_key, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?)
                       ON CONFLICT(bot_id, component, provider) DO UPDATE SET
                           encrypted_key=excluded.encrypted_key,
                           updated_at=excluded.updated_at""",
                    (bot_id, component, provider, encrypted_key, now, now),
                )
            await db.commit()

    async def share_state(self, record: BotRecord) -> ShareState:
        """Build the protected Share page response for one Bot."""
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                """SELECT l.public_id, l.active, l.current_revision,
                          p.public_title, p.public_description, p.config_json, p.published_at,
                          (SELECT COUNT(*) FROM bot_provider_credentials c
                           WHERE c.bot_id=l.bot_id AND (
                               (c.component='asr' AND c.provider=p.asr_provider) OR
                               (c.component='tts' AND c.provider=p.tts_provider) OR
                               (c.component='llm' AND c.provider=p.llm_provider)
                           )) AS credential_count
                   FROM demo_links l
                   JOIN bot_publications p
                     ON p.bot_id=l.bot_id AND p.revision=l.current_revision
                   WHERE l.bot_id=?""",
                (record.id,),
            )
            row = await cursor.fetchone()
        if row is None:
            return ShareState(
                bot_id=record.id,
                bot_name=record.name,
                public_id=None,
                title=record.name,
                description="",
                active=False,
                published=False,
                available=False,
                revision=None,
                published_at=None,
                unpublished_changes=False,
            )
        return ShareState(
            bot_id=record.id,
            bot_name=record.name,
            public_id=str(row[0]),
            active=bool(row[1]),
            revision=int(row[2]),
            title=str(row[3]),
            description=str(row[4]),
            published=True,
            available=int(row[7]) == 3,
            published_at=str(row[6]),
            unpublished_changes=str(row[5]) != _config_json(record),
        )

    async def publish(self, record: BotRecord, *, title: str, description: str) -> ShareState:
        """Atomically validate credentials, append a snapshot, and move the link."""
        config_json = _config_json(record)
        now = _utcnow()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("PRAGMA foreign_keys = ON")
            await db.execute("BEGIN IMMEDIATE")
            providers = {
                "asr": record.asr_provider,
                "tts": record.tts_provider,
                "llm": record.llm_provider,
            }
            for component, provider in providers.items():
                cursor = await db.execute(
                    """SELECT 1 FROM bot_provider_credentials
                       WHERE bot_id=? AND component=? AND provider=?""",
                    (record.id, component, provider),
                )
                if await cursor.fetchone() is None:
                    await db.rollback()
                    raise ValueError(
                        f"Save the {component.upper()} key for {provider} before publishing"
                    )
            cursor = await db.execute(
                "SELECT COALESCE(MAX(revision), 0) + 1 FROM bot_publications WHERE bot_id=?",
                (record.id,),
            )
            revision = int((await cursor.fetchone())[0])
            await db.execute(
                """INSERT INTO bot_publications
                   (bot_id, revision, public_title, public_description, config_json,
                    asr_provider, tts_provider, llm_provider, published_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.id,
                    revision,
                    title,
                    description,
                    config_json,
                    record.asr_provider,
                    record.tts_provider,
                    record.llm_provider,
                    now,
                ),
            )
            cursor = await db.execute(
                "SELECT public_id, active FROM demo_links WHERE bot_id=?", (record.id,)
            )
            link = await cursor.fetchone()
            if link is None:
                public_id = secrets.token_urlsafe(18)
                await db.execute(
                    """INSERT INTO demo_links
                       (bot_id, public_id, active, current_revision, created_at, updated_at)
                       VALUES (?, ?, 1, ?, ?, ?)""",
                    (record.id, public_id, revision, now, now),
                )
            else:
                await db.execute(
                    """UPDATE demo_links SET current_revision=?, updated_at=?
                       WHERE bot_id=?""",
                    (revision, now, record.id),
                )
            await db.commit()
        return await self.share_state(record)

    async def set_active(self, bot_id: str, active: bool) -> bool:
        """Idempotently enable or disable one stable public link."""
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "UPDATE demo_links SET active=?, updated_at=? WHERE bot_id=?",
                (int(active), _utcnow(), bot_id),
            )
            await db.commit()
        return cursor.rowcount > 0

    async def get_public(self, public_id: str) -> PublishedDemo | None:
        """Resolve one public locator without exposing private Bot configuration."""
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                """SELECT l.bot_id, b.name, l.public_id, p.public_title,
                          p.public_description, l.active, p.revision, p.config_json,
                          p.asr_provider, p.tts_provider, p.llm_provider,
                          ca.encrypted_key, ct.encrypted_key, cl.encrypted_key
                   FROM demo_links l
                   JOIN bots b ON b.id=l.bot_id
                   JOIN bot_publications p
                     ON p.bot_id=l.bot_id AND p.revision=l.current_revision
                   LEFT JOIN bot_provider_credentials ca
                     ON ca.bot_id=l.bot_id AND ca.component='asr'
                    AND ca.provider=p.asr_provider
                   LEFT JOIN bot_provider_credentials ct
                     ON ct.bot_id=l.bot_id AND ct.component='tts'
                    AND ct.provider=p.tts_provider
                   LEFT JOIN bot_provider_credentials cl
                     ON cl.bot_id=l.bot_id AND cl.component='llm'
                    AND cl.provider=p.llm_provider
                   WHERE l.public_id=?""",
                (public_id,),
            )
            row = await cursor.fetchone()
        return PublishedDemo(*row) if row else None
