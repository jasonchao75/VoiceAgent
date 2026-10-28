"""Source-positioned incremental echo planning independent of ASR formatting."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any, cast

from src.asr.transcript import TranscriptView
from src.pipeline.identifier_output import IdentifierOutput, _EchoJob
from src.pipeline.identifier_rules import IdentifierEvaluation


@dataclass
class _Plan:
    """One source's canonical positions; duplicate values retain separate positions."""

    units: tuple[str, ...]
    version: int = 0
    jobs: dict[int, _EchoJob] = field(default_factory=dict)
    correction: bool = False


class IncrementalIdentifierOutput(IdentifierOutput):
    """Preserve appended suffixes and merge only unsent source revisions."""

    def __init__(self, **kwargs: Any) -> None:
        """Reuse generation cleanup and audio resources from the existing controller."""
        super().__init__(**kwargs)
        self._plans: dict[tuple[int, str], _Plan] = {}

    def consider(
        self,
        snapshot: TranscriptView,
        evaluation: IdentifierEvaluation,
        turn_id: int | None = None,
        *,
        ready: bool = True,
    ) -> None:
        """Plan by canonical unit positions, keeping already-sent facts immutable."""
        if self._closed:
            return
        source = evaluation.source
        origins = (
            self.collection.generation,
            tuple((s.epoch, s.source_id, s.start_ms) for s in snapshot.segments),
        )
        key = (source.generation, source.source_id) if source else self._origins.get(origins)
        if key is None:
            return
        self._origins[origins] = key
        self._latest[key] = evaluation
        self._orders.setdefault(key, self.output.source_order(key[1], key[0]))
        units = self.collection.vocabulary.audio_units(snapshot.text) or ()
        eligible = source is not None and evaluation.echo_eligible and evaluation.path != "ordinary"
        plan = self._plans.get(key)
        if plan is None:
            plan = _Plan(units)
            self._plans[key] = plan
        elif units != plan.units:
            extension = len(units) >= len(plan.units) and units[: len(plan.units)] == plan.units
            if not extension:
                sent = any(
                    self.output._sent_bytes.get(job.playback_id, 0) for job in plan.jobs.values()
                )
                plan.version += 1
                plan.jobs = {}
                plan.correction = plan.correction or sent
            plan.units = units
        self.output.revalidate()
        if not ready or not eligible or source is None:
            return
        assert plan is not None
        stable_plan = cast(_Plan, plan)
        version = plan.version
        for position, unit in enumerate(units):
            previous = plan.jobs.get(position)
            if previous is not None:
                task = self.output.arbiter.tasks.get(previous.playback_id)
                retry = (
                    not self.output._sent_bytes.get(previous.playback_id, 0)
                    and self.output.source_failure(previous.playback_id) is None
                    and (
                        (
                            task is not None
                            and task.status in {"cancelled_unplayed", "send_cancelled"}
                        )
                        or (task is None and previous.task is not None and previous.task.done())
                    )
                )
                if not retry:
                    continue
            job = _EchoJob(uuid.uuid4().hex, source.generation, source.source_id, unit)
            plan.jobs[position] = job
            self._jobs[job.playback_id] = job

            def valid(
                position: int = position,
                unit: str = unit,
                version: int = version,
                plan: _Plan = stable_plan,
                playback_id: str = job.playback_id,
            ) -> bool:
                """Appending a source preserves earlier positions, unlike true corrections."""
                latest = self._latest.get(key)
                return bool(
                    not self._closed
                    and latest
                    and latest.source
                    and (latest.echo_eligible or bool(self.output._sent_bytes.get(playback_id, 0)))
                    and latest.path != "ordinary"
                    and plan.version == version
                    and position < len(plan.units)
                    and plan.units[position] == unit
                    and source.generation == self.collection.generation
                    and self.collection._valid(latest.source)
                )

            async def prepare(
                job: _EchoJob = job,
                position: int = position,
                unit: str = unit,
                valid: Callable[[], bool] = valid,
            ) -> None:
                """Use existing cached unit audio, preserving the configured inter-unit gap."""

                async def samples() -> AsyncIterator[bytes]:
                    """Emit only this position, with a gap before subsequent positions."""
                    if position:
                        yield b"\0" * (self.audio.gap_samples * 2)
                    async for pcm in self.audio.chunks(
                        "", generation=source.generation, units=(unit,)
                    ):
                        yield pcm

                await self.output.stream_audio(
                    playback_id=job.playback_id,
                    kind="correction" if plan.correction else "echo",
                    generation=source.generation,
                    source_id=f"{source.source_id}:v{version}:unit{position}:{job.playback_id}",
                    revision=source.revision,
                    source_order=self._orders[key],
                    valid=valid,
                    samples=samples(),
                    sample_rate=self.audio.sample_rate,
                    turn_id=turn_id,
                    final_segment=evaluation.path == "complete",
                    reserve_order=True,
                )

            job.task = asyncio.create_task(prepare())
            self._record(
                "identifier_echo_scheduled",
                playback_id=job.playback_id,
                source_id=source.source_id,
                source_revision=source.revision,
                collection_generation=source.generation,
                unit_position=position,
                text=unit,
                kind="correction" if plan.correction else "echo",
                turn_id=turn_id,
            )
