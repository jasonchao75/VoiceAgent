"""Permanent content-addressed echo PCM with immutable publication manifests."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
import uuid
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import aiosqlite

from src.config import TTSConfig

if TYPE_CHECKING:
    from src.bots.models import BotConfigFields

Synthesize = Callable[..., Awaitable[bytes]]


def tts_for_bot(bot: BotConfigFields) -> TTSConfig:
    """Use the same complete TTS settings as the formal Bot/session fields."""
    return TTSConfig(**{field: getattr(bot, "tts_" + field) for field in TTSConfig.model_fields})


def units_for_values(values: Iterable[str]) -> tuple[str, ...]:
    """Split digit sequences into spoken digits while keeping other configured units intact."""
    return tuple(
        unit for value in values for unit in (tuple(value) if value.isdigit() else (value,))
    )


def fingerprint(config: TTSConfig, sample_rate: int) -> str:
    """Hash effective fixed synthesis settings, excluding ordinary-response speed controls."""
    payload = config.model_dump(exclude={"dynamic_speed_enabled", "speed_step", "text_aggregation"})
    payload.update(sample_rate=sample_rate, channels=1, encoding="pcm_s16le")
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class EchoAsset:
    """Safe resource metadata; no credential is retained in the fingerprint or database."""

    version: str
    bot_id: str
    fingerprint: str
    unit: str
    status: str
    digest: str
    path: Path
    sample_rate: int
    error: str | None = None

    def public(self) -> dict[str, object]:
        """Expose status/version without leaking an internal filesystem path."""
        return {
            "version": self.version,
            "unit": self.unit,
            "status": self.status,
            "fingerprint": self.fingerprint,
            "sample_rate": self.sample_rate,
            "error": self.error,
            "url": "/api/echo-assets/" + self.version if self.status == "ready" else None,
        }


class EchoAudioCache:
    """One app-owned cache; concurrent requests share each bounded synthesis attempt."""

    def __init__(self, root: Path) -> None:
        """Use a dedicated permanent directory, never browser/session temporary storage."""
        self.root = root
        self._initialized = False
        self._init_lock = asyncio.Lock()
        self._lock = asyncio.Lock()
        self._inflight: dict[tuple[str, str, str], asyncio.Task[EchoAsset]] = {}

    async def initialize(self) -> None:
        """Create schema idempotently without synchronous I/O on the audio event loop."""
        async with self._init_lock:
            if self._initialized:
                return
            await asyncio.to_thread(self.root.mkdir, parents=True, exist_ok=True)
            async with aiosqlite.connect(self.root / "assets.sqlite3") as db:
                await db.executescript("""
                    CREATE TABLE IF NOT EXISTS echo_assets (
                        version TEXT PRIMARY KEY, bot_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
                        unit TEXT NOT NULL, status TEXT NOT NULL, digest TEXT NOT NULL,
                        filename TEXT NOT NULL, sample_rate INTEGER NOT NULL, error TEXT,
                        created_ns INTEGER NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS echo_assets_lookup
                        ON echo_assets(bot_id, fingerprint, unit, created_ns DESC);
                """)
                await db.commit()
            self._initialized = True

    async def _find(self, bot_id: str, unit: str, config: TTSConfig, rate: int) -> EchoAsset | None:
        """Resolve latest attempt matching this exact Bot and effective configuration."""
        await self.initialize()
        async with aiosqlite.connect(self.root / "assets.sqlite3") as db:
            cursor = await db.execute(
                """SELECT version, bot_id, fingerprint, unit, status,
                digest, filename, sample_rate, error FROM echo_assets
                WHERE bot_id=? AND fingerprint=? AND unit=? ORDER BY created_ns DESC LIMIT 1""",
                (bot_id, fingerprint(config, rate), unit),
            )
            row = await cursor.fetchone()
        return self._asset(row) if row else None

    def _asset(self, row: aiosqlite.Row) -> EchoAsset:
        """Restrict persisted resource paths even if metadata has been tampered with."""
        filename = str(row[6])
        if filename != Path(filename).name or not filename.endswith(".pcm"):
            raise ValueError("Invalid audio resource path")
        return EchoAsset(
            str(row[0]),
            str(row[1]),
            str(row[2]),
            str(row[3]),
            str(row[4]),
            str(row[5]),
            self.root / filename,
            int(row[7]),
            row[8],
        )

    async def asset(self, version: str) -> EchoAsset:
        """Read a fixed resource version; a publication never resolves to a newer voice."""
        await self.initialize()
        async with aiosqlite.connect(self.root / "assets.sqlite3") as db:
            cursor = await db.execute(
                """SELECT version, bot_id, fingerprint, unit, status,
                digest, filename, sample_rate, error FROM echo_assets WHERE version=?""",
                (version,),
            )
            row = await cursor.fetchone()
        if row is None:
            raise ValueError("Audio resource missing")
        return self._asset(row)

    async def read(self, asset: EchoAsset) -> bytes:
        """Verify PCM length and checksum rather than treating file existence as integrity."""
        if asset.status != "ready":
            raise ValueError("Audio resource missing")
        try:
            pcm = await asyncio.to_thread(asset.path.read_bytes)
        except OSError as error:
            raise ValueError("Audio resource missing") from error
        if not pcm or len(pcm) % 2 or hashlib.sha256(pcm).hexdigest() != asset.digest:
            raise ValueError("Audio resource missing or corrupt")
        return pcm

    async def status(
        self, bot_id: str, units: Iterable[str], config: TTSConfig, sample_rate: int
    ) -> list[EchoAsset | None]:
        """Return actual current statuses in unique-unit order, including corrupt/missing files."""
        config = config.model_copy(deep=True)
        rows = []
        for unit in dict.fromkeys(units):
            asset = await self._find(bot_id, unit, config, sample_rate)
            if asset and asset.status == "ready":
                try:
                    await self.read(asset)
                except ValueError:
                    asset = EchoAsset(
                        asset.version,
                        asset.bot_id,
                        asset.fingerprint,
                        asset.unit,
                        "missing",
                        asset.digest,
                        asset.path,
                        asset.sample_rate,
                        "unreadable_or_corrupt",
                    )
            rows.append(asset)
        return rows

    async def manifest(
        self, bot_id: str, units: Iterable[str], config: TTSConfig, sample_rate: int
    ) -> dict[str, str]:
        """Validate only; publishing must never trigger synthesis or borrow mismatched assets."""
        config = config.model_copy(deep=True)
        required = tuple(dict.fromkeys(units))
        rows = await self.status(bot_id, required, config, sample_rate)
        missing = [
            unit
            for unit, row in zip(required, rows, strict=True)
            if row is None or row.status != "ready"
        ]
        if missing:
            raise ValueError("Echo audio missing: " + ", ".join(missing))
        return {unit: row.version for unit, row in zip(required, rows, strict=True) if row}

    async def prepare(
        self,
        bot_id: str,
        units: Iterable[str],
        config: TTSConfig,
        sample_rate: int,
        synthesize: Synthesize,
        *,
        timeout: float,
    ) -> list[EchoAsset]:
        """Generate only missing units, retaining successes and explicit per-unit failures."""
        config = config.model_copy(deep=True)
        rows = []
        for unit in dict.fromkeys(units):
            asset = await self._find(bot_id, unit, config, sample_rate)
            try:
                if asset:
                    await self.read(asset)
                else:
                    raise ValueError("missing")
            except ValueError:
                asset = await self._repair(bot_id, unit, config, sample_rate, synthesize, timeout)
            assert asset is not None
            rows.append(asset)
        return rows

    async def resolve(
        self,
        bot_id: str,
        unit: str,
        config: TTSConfig,
        sample_rate: int,
        synthesize: Synthesize,
        *,
        timeout: float,
        version: str | None = None,
    ) -> tuple[bytes, bool]:
        """Resolve a frozen version or repair a runtime read failure with fixed session settings."""
        config = config.model_copy(deep=True)
        asset = None
        try:
            asset = (
                await self.asset(version)
                if version
                else await self._find(bot_id, unit, config, sample_rate)
            )
            if asset is None:
                raise ValueError("missing")
            if (
                asset.bot_id != bot_id
                or asset.unit != unit
                or asset.fingerprint != fingerprint(config, sample_rate)
            ):
                raise ValueError("Audio resource mismatch")
            return await self.read(asset), False
        except ValueError:
            repaired = await self._repair(bot_id, unit, config, sample_rate, synthesize, timeout)
            return await self.read(repaired), True

    async def _repair(
        self,
        bot_id: str,
        unit: str,
        config: TTSConfig,
        rate: int,
        synthesize: Synthesize,
        timeout: float,
    ) -> EchoAsset:
        """Share already-sent work, while timeout/cancellation never starts duplicate requests."""
        key = (bot_id, fingerprint(config, rate), unit)
        async with self._lock:
            task = self._inflight.get(key)
            if task is None:
                task = asyncio.create_task(
                    self._generate(bot_id, unit, config, rate, synthesize, timeout)
                )
                self._inflight[key] = task

                def settled(future: asyncio.Task[EchoAsset]) -> None:
                    """Release bounded jobs even when every requesting session was cancelled."""
                    if self._inflight.get(key) is future:
                        self._inflight.pop(key)
                    if not future.cancelled():
                        future.exception()

                task.add_done_callback(settled)
        try:
            return await asyncio.shield(task)
        finally:
            if task.done():
                async with self._lock:
                    if self._inflight.get(key) is task:
                        self._inflight.pop(key)

    async def _generate(
        self,
        bot_id: str,
        unit: str,
        config: TTSConfig,
        rate: int,
        synthesize: Synthesize,
        timeout: float,
    ) -> EchoAsset:
        """Atomically store an actual PCM resource or an honest sanitized failure attempt."""
        await self.initialize()
        fp = fingerprint(config, rate)
        existing = await self._find(bot_id, unit, config, rate)
        if existing is not None:
            try:
                await self.read(existing)
                return existing
            except ValueError:
                pass
        status, error, pcm = "ready", None, b""
        try:
            async with asyncio.timeout(timeout):
                pcm = await synthesize(unit, config.model_copy(deep=True), rate, timeout=timeout)
            if not isinstance(pcm, bytes) or not pcm or len(pcm) % 2 or len(pcm) > rate * 2 * 120:
                raise ValueError("Invalid PCM synthesis")
        except Exception as failure:
            status, error = "failed", type(failure).__name__
        digest = hashlib.sha256(pcm).hexdigest() if status == "ready" else ""
        version = (
            hashlib.sha256(json.dumps([bot_id, fp, unit, digest]).encode()).hexdigest()
            if status == "ready"
            else uuid.uuid4().hex
        )
        filename = version + ".pcm"
        if status == "ready":

            def write() -> None:
                """Use a unique staging path; readers never see a partially written PCM asset."""
                temporary = self.root / (version + "." + uuid.uuid4().hex + ".tmp")
                temporary.write_bytes(pcm)
                os.replace(temporary, self.root / filename)

            try:
                await asyncio.to_thread(write)
            except OSError as failure:
                status, error, digest = "failed", type(failure).__name__, ""
                version = uuid.uuid4().hex
                filename = version + ".pcm"
        async with aiosqlite.connect(self.root / "assets.sqlite3") as db:
            await db.execute(
                """INSERT INTO echo_assets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(version) DO UPDATE SET created_ns=excluded.created_ns,
                    status=excluded.status, error=excluded.error""",
                (version, bot_id, fp, unit, status, digest, filename, rate, error, time.time_ns()),
            )
            await db.commit()
        return EchoAsset(
            version, bot_id, fp, unit, status, digest, self.root / filename, rate, error
        )

    async def compose(
        self, manifest: Mapping[str, str], units: Iterable[str], *, sample_rate: int, gap_ms: int
    ) -> bytes:
        """Compose s16 mono samples with gaps only between units, preserving every repetition."""
        if gap_ms < 0:
            raise ValueError("Audio gap must be non-negative")
        gap = b"\x00\x00" * round(sample_rate * gap_ms / 1000)
        parts = []
        for unit in units:
            asset = await self.asset(manifest[unit])
            if asset.unit != unit or asset.sample_rate != sample_rate:
                raise ValueError("Audio resource format mismatch")
            parts.append(await self.read(asset))
        return gap.join(parts)

    async def close(self) -> None:
        """Wait for bounded already-started operations before application shutdown."""
        await asyncio.gather(*self._inflight.values(), return_exceptions=True)
        self._inflight.clear()
