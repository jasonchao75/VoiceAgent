"""Bind source-owned identifier echo jobs to the shared collection and serial output."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from src.asr.transcript import TranscriptView
from src.pipeline.echo_audio import EchoAudio
from src.pipeline.identifier import IdentifierCollection
from src.pipeline.identifier_rules import IdentifierEvaluation
from src.pipeline.playback import PlaybackKind
from src.pipeline.serial_output import SerialAudioOutput


@dataclass
class _EchoJob:
    """One revision's bounded preparation, independent of the client's actual play state."""

    playback_id: str
    generation: int
    source_id: str
    text: str
    task: asyncio.Task[None] | None = None
    status: str = "preparing"


class IdentifierOutput:
    """Coalesce unplayed revisions while protecting sent/played facts and fixed voice settings."""

    def __init__(
        self,
        *,
        collection: IdentifierCollection,
        audio: EchoAudio,
        output: SerialAudioOutput,
        evidence_sink: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """Attach a single session collection without changing local/tool collection authority."""
        self.collection = collection
        self.audio = audio
        self.output = output
        self._sink = evidence_sink
        self._latest: dict[tuple[int, str], IdentifierEvaluation] = {}
        self._last: dict[tuple[int, str], _EchoJob] = {}
        self._origins: dict[tuple, tuple[int, str]] = {}
        self._orders: dict[tuple[int, str], int] = {}
        self._turns: dict[tuple[int, str], int | None] = {}
        self._jobs: dict[str, _EchoJob] = {}
        self._closed = False
        self._generation_listener = self._generation_changed
        if collection.on_generation_change is not None:
            raise ValueError("Collection already has an output generation listener")
        collection.on_generation_change = self._generation_listener
        if collection.generation > output.arbiter.generation:
            output.clear(collection.generation)

    def _record(self, event: str, **fields: Any) -> None:
        """Record scheduling and cancellation, never a synthetic client playback fact."""
        if self._sink:
            self._sink({"event": event, **fields})

    def _generation_changed(self, generation: int) -> None:
        """A successful clear/new collection invalidates even not-yet-started preparation."""
        if generation > self.output.arbiter.generation:
            self.output.clear(generation)
        for job in self._jobs.values():
            if job.generation != generation and job.task and not job.task.done():
                job.status = "cancelled"
                job.task.cancel()

    def consider(
        self,
        snapshot: TranscriptView,
        evaluation: IdentifierEvaluation,
        turn_id: int | None = None,
        *,
        ready: bool = True,
    ) -> None:
        """Schedule only eligible pure sources; metadata-only Final never repeats the echo."""
        if self._closed:
            return
        source = evaluation.source
        origins = (
            self.collection.generation,
            tuple((s.epoch, s.source_id, s.start_ms) for s in snapshot.segments),
        )
        key = (source.generation, source.source_id) if source else self._origins.get(origins)
        if key is None:
            self.output.revalidate()
            return
        self._origins[origins] = key
        self._latest[key] = evaluation
        self._turns.setdefault(key, turn_id)
        self._orders.setdefault(key, self.output.source_order(key[1], key[0]))
        previous = self._last.get(key)
        previous_task = self.output.arbiter.tasks.get(previous.playback_id) if previous else None
        eligible = source is not None and evaluation.echo_eligible and evaluation.path != "ordinary"
        if previous and previous.task and not previous.task.done():
            unplayed = previous_task is None or previous_task.status == "queued"
            if unplayed and (not eligible or previous.text != snapshot.text):
                previous.status = "cancelled"
                previous.task.cancel()
        self.output.revalidate()
        if not ready or not eligible or source is None:
            return
        if previous and previous.text == snapshot.text:
            if self.output.source_failure(previous.playback_id) is not None:
                return
            cancelled = previous.status == "cancelled" or (
                previous_task is not None and previous_task.status == "cancelled_unplayed"
            )
            if not cancelled:
                return
        prior_sent = any(
            task.generation == source.generation
            and task.source_id == source.source_id
            and task.status not in {"queued", "cancelled_unplayed"}
            for task in self.output.arbiter.tasks.values()
        )
        kind: PlaybackKind = "correction" if prior_sent else "echo"
        job = _EchoJob(uuid.uuid4().hex, source.generation, source.source_id, snapshot.text)
        self._jobs[job.playback_id] = job
        self._last[key] = job

        def valid() -> bool:
            """Equivalent metadata revisions may refresh provenance without replaying audio."""
            latest = self._latest.get(key)
            return bool(
                latest
                and latest.source
                and latest.echo_eligible
                and latest.path != "ordinary"
                and latest.source.text == job.text
                and self.collection._valid(latest.source)
            )

        async def prepare() -> None:
            """All cache reads and any recovery happen outside the coordinator's audio lock."""
            await self.output.stream_audio(
                playback_id=job.playback_id,
                kind=kind,
                generation=source.generation,
                source_id=source.source_id,
                revision=source.revision,
                source_order=self._orders[key],
                valid=valid,
                samples=self.audio.chunks(
                    snapshot.text,
                    generation=source.generation,
                    trace={
                        "playback_id": job.playback_id,
                        "source_id": source.source_id,
                        "source_revision": source.revision,
                        "turn_id": self._turns[key],
                    },
                ),
                turn_id=self._turns[key],
                final_segment=evaluation.path == "complete",
            )

        job.task = asyncio.create_task(prepare())

        def settled(task: asyncio.Task[None]) -> None:
            """Consume cancellation/errors without leaving unobserved asynchronous failures."""
            if task.cancelled():
                job.status = "cancelled"
            elif task.exception() is not None:
                job.status = "failed"
                self._record(
                    "identifier_echo_job_failed",
                    playback_id=job.playback_id,
                    error_type=type(task.exception()).__name__,
                )
            elif self.output.source_failure(job.playback_id) is not None:
                job.status = "failed"
                self._record(
                    "identifier_echo_job_failed",
                    playback_id=job.playback_id,
                    error_type=self.output.source_failure(job.playback_id),
                    source_id=job.source_id,
                    collection_generation=job.generation,
                    turn_id=self._turns[key],
                )
            else:
                state = self.output.arbiter.tasks.get(job.playback_id)
                job.status = (
                    "ready"
                    if state
                    and state.status
                    not in {
                        "cancelled_unplayed",
                        "failed",
                        "stopped",
                    }
                    else "failed"
                )

        job.task.add_done_callback(settled)
        self._record(
            "identifier_echo_scheduled",
            playback_id=job.playback_id,
            source_id=source.source_id,
            source_revision=source.revision,
            collection_generation=source.generation,
            text=snapshot.text,
            kind=kind,
            prior_output_sent=prior_sent,
            turn_id=self._turns[key],
        )

    def observe(
        self, snapshot: TranscriptView, evaluation: IdentifierEvaluation, turn_id: int | None = None
    ) -> None:
        """Reserve source order and invalidate stale queued data without bypassing the pause."""
        self.consider(snapshot, evaluation, turn_id, ready=False)

    async def wait_pending(self) -> None:
        """Wait only for current bounded preparation jobs, without asserting playback."""
        await asyncio.gather(
            *(job.task for job in self._jobs.values() if job.task), return_exceptions=True
        )

    async def close(self) -> None:
        """Detach and cancel session jobs; app-owned in-flight cache recovery remains bounded."""
        self._closed = True
        if self.collection.on_generation_change is self._generation_listener:
            self.collection.on_generation_change = None
        for job in self._jobs.values():
            if job.task and not job.task.done():
                job.task.cancel()
        await self.wait_pending()
