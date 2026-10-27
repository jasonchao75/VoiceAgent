"""Version-bound runtime PCM preparation; transport delivery remains a separate fact."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Callable, Mapping
from typing import Any

from src.config import TTSConfig
from src.pipeline.identifier import IdentifierCollection
from src.tts.echo_cache import EchoAudioCache, Synthesize, fingerprint


class EchoAudio:
    """Prepare bounded audio chunks without changing ordinary reply speed or claiming playback."""

    def __init__(
        self,
        *,
        cache: EchoAudioCache,
        bot_id: str,
        collection: IdentifierCollection,
        config: TTSConfig,
        sample_rate: int,
        gap_ms: int,
        manifest: Mapping[str, str],
        synthesize: Synthesize,
        record: Callable[..., Any],
        timeout: float = 20.0,
    ) -> None:
        """Capture immutable session voice settings and publication resource bindings."""
        self.cache = cache
        self.bot_id = bot_id
        self.collection = collection
        self.config = config.model_copy(deep=True)
        self.sample_rate = sample_rate
        self.gap_samples = round(sample_rate * gap_ms / 1000)
        self.manifest = dict(manifest)
        self.synthesize = synthesize
        self.record = record
        self.timeout = timeout
        if sample_rate <= 0 or gap_ms < 0 or timeout <= 0:
            raise ValueError("Invalid echo audio limits")

    async def chunks(
        self, text: str, *, generation: int, trace: Mapping[str, Any] | None = None
    ) -> AsyncIterator[bytes]:
        """Read/recover fixed audio and yield at most 20ms PCM chunks while identity is current.

        Raises:
            ValueError: For out-of-vocabulary input or unreadable/unrecoverable PCM.
        """

        def record(event: str, **fields: Any) -> None:
            """Keep recovery ownership and each reader's original task attribution."""
            self.record(event, **{**(trace or {}), "collection_generation": generation, **fields})

        units = self.collection.vocabulary.audio_units(text)
        if units is None:
            raise ValueError("Input outside echo vocabulary")
        chunk_bytes = max(2, round(self.sample_rate * 0.02) * 2)
        fp = fingerprint(self.config, self.sample_rate)
        for index, unit in enumerate(units):
            if generation != self.collection.generation:
                record("identifier_echo_stale", collection_generation=generation)
                return
            started = time.monotonic()

            async def synthesize(
                value: str, config: TTSConfig, rate: int, *, timeout: float
            ) -> bytes:
                """Count actual synthesis ownership, including a shared cache repair's origin."""
                record("identifier_echo_synthesis_started", unit=value, fingerprint=fp)
                return await self.synthesize(value, config, rate, timeout=timeout)

            try:
                pcm, recovered = await self.cache.resolve(
                    self.bot_id,
                    unit,
                    self.config,
                    self.sample_rate,
                    synthesize,
                    timeout=self.timeout,
                    version=self.manifest.get(unit),
                )
            except Exception as error:
                record(
                    "identifier_echo_resource_failed",
                    unit=unit,
                    fingerprint=fp,
                    resource_version=self.manifest.get(unit),
                    error_type=type(error).__name__,
                    elapsed_ms=(time.monotonic() - started) * 1000,
                )
                raise
            record(
                "identifier_echo_resource_ready",
                unit=unit,
                fingerprint=fp,
                resource_version=self.manifest.get(unit),
                recovery_path=recovered,
                elapsed_ms=(time.monotonic() - started) * 1000,
            )
            # Recheck after every await and yielded frame: clear cannot resurrect old audio.
            if generation != self.collection.generation:
                record("identifier_echo_stale", collection_generation=generation)
                return
            if index:
                remaining = self.gap_samples * 2
                while remaining:
                    if generation != self.collection.generation:
                        record("identifier_echo_stale", collection_generation=generation)
                        return
                    size = min(chunk_bytes, remaining)
                    yield b"\x00" * size
                    remaining -= size
            for offset in range(0, len(pcm), chunk_bytes):
                if generation != self.collection.generation:
                    record("identifier_echo_stale", collection_generation=generation)
                    return
                yield pcm[offset : offset + chunk_bytes]
