"""Custom TD runtime: local audio/VAD and one source-aware submission authority."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import replace
from typing import Any

from pipecat.audio.vad.vad_analyzer import VADState
from pipecat.frames.frames import (
    CancelFrame,
    EndFrame,
    Frame,
    InputAudioRawFrame,
    InterimTranscriptionFrame,
    ProposedUserStartedSpeakingFrame,
    ProposedUserStoppedSpeakingFrame,
    StartFrame,
    TranscriptionFrame,
    TTSSpeakFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameCallback, FrameDirection, FrameProcessor
from pipecat.utils.time import time_now_iso8601

from src.asr.factory import ASRService
from src.asr.source_frames import ASRStreamEpochFrame, SourceOwnedASRMixin
from src.asr.td_config import CustomTDSettings
from src.asr.transcript import (
    ASRSourceEvidenceError,
    TranscriptLedger,
    TranscriptView,
    join_source_segments,
)
from src.pipeline.identifier_rules import IdentifierEvaluation, IdentifierRules
from src.pipeline.jev import JevResult
from src.pipeline.response_revision import ResponseRevisions, ResponseVersion
from src.pipeline.td_strategies import TDResponseRestartFrame, TDSubmissionFrame
from src.pipeline.turn_detection import CandidateToken, TurnClock, WaitPolicy

Decision = Callable[..., Awaitable[JevResult]]
EvidenceSink = Callable[[dict[str, Any]], None]
InputBinding = Callable[[ResponseVersion, TranscriptView, str], None]
IdentifierNotify = Callable[[TranscriptView, IdentifierEvaluation, int], None]


class CustomTDCoordinator(FrameProcessor):
    """Own transcript consumption and all ordinary user-turn submissions in one session."""

    def __init__(
        self,
        *,
        asr: ASRService,
        settings: CustomTDSettings,
        decide: Decision | None,
        evidence_sink: EvidenceSink | None = None,
        responses: ResponseRevisions | None = None,
        bind_input: InputBinding | None = None,
        identifier_rules: IdentifierRules | None = None,
        identifier_output: IdentifierNotify | None = None,
        identifier_observe: IdentifierNotify | None = None,
    ) -> None:
        """Build a coordinator without opening any provider connection.

        Args:
            asr: Selected adapter's public normalization boundary.
            settings: Explicit immutable session settings.
            decide: Backend Jev request, injectable for no-network tests.
            evidence_sink: Nonblocking collector for actual decision evidence.
        """
        super().__init__()
        self.asr = asr
        self.settings = settings
        self.authority = object()
        self.ledger = TranscriptLedger()
        self.responses = responses if responses is not None else ResponseRevisions()
        self._submitted_snapshot: TranscriptView | None = None
        self.clock = TurnClock(
            WaitPolicy(
                settings.minimum_ms,
                settings.maximum_ms,
                settings.final_wait_ms,
                settings.alpha,
                settings.conflict_threshold,
            )
        )
        self._decide = decide
        self._sink = evidence_sink
        self._diagnostic_count = 0
        self._lock = asyncio.Lock()
        self._candidate: CandidateToken | None = None
        self._speaking = False
        self._suspected = False
        self._audio_ms = 0.0
        self._last_audio_wall: float | None = None
        self._audio_processing = 0
        self._audio_pending = 0
        self._watchdog: asyncio.Task[None] | None = None
        self._decision: asyncio.Task[None] | None = None
        self._closed = False
        self._assistant = ""
        self._turn_index = 0
        self._active_turn_id = 1
        self._last_requested: tuple[int, int] | None = None
        self.unranged_text: str | None = None
        self.source_evidence_error: ASRSourceEvidenceError | None = None
        self._bind_input = bind_input
        self.identifier_rules = identifier_rules
        self._identifier_output = identifier_output
        self._identifier_observe = identifier_observe
        self._input_collection_generation = (
            identifier_rules.collection.generation if identifier_rules else None
        )
        self._rule_evaluation: IdentifierEvaluation | None = None
        self._local_snapshot: TranscriptView | None = None
        self._revised_local_snapshot: TranscriptView | None = None
        self._local_assistant = ""
        self._pending_mixed: dict[tuple[tuple[int, str, float, float], ...], TranscriptView] = {}
        self._retained_local: dict[
            tuple[tuple[int, str, float, float], ...], tuple[TranscriptView, str, int, int]
        ] = {}

    @staticmethod
    def _range_key(snapshot: TranscriptView) -> tuple[tuple[int, str, float, float], ...]:
        """Identify consumed extents independently of text, Final status or later input."""
        return tuple((s.epoch, s.source_id, s.start_ms, s.end_ms) for s in snapshot.segments)

    def _retain_local(self, snapshot: TranscriptView) -> None:
        """Keep the original keyword snapshot and collection generation across new speech."""
        if self.identifier_rules and snapshot.segments:
            key = self._range_key(snapshot)
            previous = self._retained_local.get(key)
            original_assistant = self._assistant
            original_turn = self._active_turn_id
            if previous is not None and previous[2] == self.identifier_rules.collection.generation:
                original_assistant = previous[1]
                original_turn = previous[3]
            self._retained_local[key] = (
                snapshot,
                original_assistant,
                self.identifier_rules.collection.generation,
                original_turn,
            )

    def _revise_retained_local(self) -> None:
        """Update only the original contribution; old ASR cannot start a new collection/turn."""
        rules = self.identifier_rules
        if rules is None:
            return
        live = self._local_snapshot or self._revised_local_snapshot
        live_key = self._range_key(live) if live is not None and self._candidate else None
        for key, (snapshot, assistant, generation, turn_id) in list(self._retained_local.items()):
            if generation != rules.collection.generation:
                del self._retained_local[key]
                continue
            if key == live_key:
                continue
            revised = self.ledger.resolve_snapshot(
                snapshot, require_final=False, expand_local=turn_id > self._turn_index
            )
            if revised is None or revised == snapshot:
                continue
            evaluation = rules.evaluate(revised, assistant, allow_new_collection=False)
            self._retained_local[key] = (revised, assistant, generation, turn_id)
            self.record(
                "identifier_retained_revision",
                turn_id=turn_id,
                text=revised.text,
                previous_text=snapshot.text,
                path=evaluation.path,
                collection_generation=generation,
                collected=rules.collection.value,
                source_final=revised.final,
                echo_eligible=evaluation.echo_eligible,
            )
            if (
                revised.text
                and turn_id == self._active_turn_id
                and turn_id > self._turn_index
                and (
                    self._speaking or self._candidate or evaluation.path in {"ordinary", "complete"}
                )
            ):
                self._pending_mixed[key] = revised
            else:
                self._pending_mixed.pop(key, None)
            rules.confirm_committed()
            if turn_id > self._turn_index and (self._speaking or self._candidate):
                if self._identifier_observe:
                    self._identifier_observe(revised, evaluation, turn_id)
            else:
                self._notify_identifier_output(revised, evaluation, turn_id=turn_id)

    def _notify_identifier_output(
        self,
        snapshot: TranscriptView,
        evaluation: IdentifierEvaluation,
        *,
        turn_id: int | None = None,
    ) -> None:
        """Offer preparation outside the audio lock; eligibility never claims playback."""
        if self._identifier_output:
            self._identifier_output(
                snapshot, evaluation, turn_id if turn_id is not None else self._active_turn_id
            )
        elif evaluation.echo_eligible:
            self.record("identifier_echo_not_dispatched", reason="audio_adapter_pending")

    def record(self, kind: str, **fields: Any) -> None:
        """Emit actual bounded event fields without provider payloads or credentials."""
        if self._sink:
            self._sink(
                {
                    "event": kind,
                    "turn_id": self._active_turn_id,
                    "audio_ms": self._audio_ms,
                    **fields,
                }
            )

    def assistant_context(self, text: str) -> None:
        """Set only the latest ordinary assistant reply, never a rule echo."""
        self._assistant = text

    def record_diagnostic(self, kind: str, **fields: Any) -> None:
        """Bound additional evidence and isolate storage failures from live audio."""
        if self._diagnostic_count >= 2400:
            return
        self._diagnostic_count += 1
        try:
            self.record(kind, **fields)
            if self._diagnostic_count == 2400:
                self.record("td_diagnostic_limit", limit=2400)
        except Exception:
            # Optional diagnostics must not become a new interruption cause.
            return

    def _invalidate_cleared_input(self) -> None:
        """Consume pre-clear candidates before late ASR can collect or submit them again."""
        rules = self.identifier_rules
        if rules is None or self._input_collection_generation == rules.collection.generation:
            return
        self.ledger.consume()
        self._candidate = None
        self._rule_evaluation = None
        self._local_snapshot = None
        self._revised_local_snapshot = None
        self._pending_mixed.clear()
        self.clock.resume()
        self._input_collection_generation = rules.collection.generation
        if self._decision:
            self._decision.cancel()
        self.record(
            "identifier_old_candidate_invalidated",
            collection_generation=rules.collection.generation,
        )

    async def speech_started(self) -> None:
        """Invalidate old candidates before propagating the normal interruption signal."""
        async with self._lock:
            if self._speaking:
                return
            self._invalidate_cleared_input()
            self._speaking = True
            self._active_turn_id = self._turn_index + 1
            self.responses.begin_speech()
            if self.identifier_rules:
                self.identifier_rules.begin_input()
            self.clock.resume()
            self._candidate = None
            self._rule_evaluation = None
            self._local_snapshot = None
            self._revised_local_snapshot = None
            if self._decision:
                self._decision.cancel()
            self.record("speech_resumed", trigger="local_vad")
            self.record_diagnostic("interruption_proposed", trigger="local_vad")
            await self.push_frame(ProposedUserStartedSpeakingFrame())

    async def speech_stopped(self, speech_end_ms: float) -> None:
        """Create one candidate at the actual audio speech boundary."""
        async with self._lock:
            self._speaking = False
            self._candidate = self.clock.pause(speech_end_ms)
            self.record(
                "candidate_created",
                candidate=self._candidate.generation,
                speech_end_audio_ms=speech_end_ms,
            )
            self._sync_transcript()
            self._schedule_decision()

    def _sync_transcript(self) -> None:
        """Update candidate text without allowing ASR Final to submit independently."""
        if self._candidate:
            view = self._current_view()
            if not view.text and self._rule_evaluation is not None:
                return
            self.clock.transcript(self._candidate, view.text, final=view.final)
            if self.identifier_rules is not None and view.text:
                self._rule_evaluation = self.identifier_rules.evaluate(view, self._assistant)
                self._input_collection_generation = self.identifier_rules.collection.generation
                evaluation = self._rule_evaluation
                if self._identifier_observe:
                    self._identifier_observe(view, evaluation, self._active_turn_id)
                self.record(
                    "identifier_evaluated",
                    candidate=self._candidate.generation,
                    input_id=evaluation.source.source_id if evaluation.source else None,
                    collection_generation=self.identifier_rules.collection.generation,
                    source_ranges=[
                        {
                            "epoch": s.epoch,
                            "source_id": s.source_id,
                            "source_revision": s.revision,
                            "start_ms": s.start_ms,
                            "end_ms": s.end_ms,
                        }
                        for s in view.segments
                    ],
                    path=evaluation.path,
                    matched_keyword=evaluation.matched_keyword,
                    assistant=self._assistant,
                    units=evaluation.units,
                    start_ms=evaluation.start_ms,
                    end_ms=evaluation.end_ms,
                    wpm=evaluation.wpm,
                    wpm_threshold=self.identifier_rules.settings.wpm_threshold,
                    timing_reason=evaluation.timing_reason,
                    echo_eligible=evaluation.echo_eligible,
                    collected=self.identifier_rules.collection.value,
                )
            if view.missing_reason:
                self.record("range_evidence_missing", reason=view.missing_reason)

    def _current_view(self) -> TranscriptView:
        """Include a revised local range that has never been submitted to the LLM."""
        view = self.ledger.view()
        if self.asr.source_normalizer and self.asr.source_normalizer.unresolved_sources:
            view = replace(view, final=False, missing_reason="unresolved_source_audio_range")
        pending = list(self._pending_mixed.values())
        if self._revised_local_snapshot is not None:
            pending.append(self._revised_local_snapshot)
        if not pending:
            return view
        pieces = {self._range_key(item): item for item in pending if item.segments}
        if view.segments:
            pieces[self._range_key(view)] = view
        ordered = sorted(
            pieces.values(), key=lambda item: (item.segments[0].epoch, item.segments[0].start_ms)
        )
        return TranscriptView(
            join_source_segments(tuple(segment for item in ordered for segment in item.segments)),
            bool(ordered) and all(item.final for item in ordered),
            tuple(segment for item in ordered for segment in item.segments),
            next((item.missing_reason for item in [*ordered, view] if item.missing_reason), None),
        )

    async def receive_transcript(self, frame: Any) -> None:
        """Accept the adapter's source ranges, retaining unknown text as explicit evidence."""
        async with self._lock:
            self._invalidate_cleared_input()
            normalizer = self.asr.source_normalizer
            previous_gaps = set(normalizer.unresolved_sources) if normalizer else set()
            segments = self.asr.normalize_source_frame(frame)
            changed = bool(normalizer and previous_gaps != normalizer.unresolved_sources)
            if changed:
                self._last_requested = None
                if self._decision:
                    self._decision.cancel()
            for segment in segments:
                changed = self.ledger.apply(segment) or changed
            if (
                self.asr.source_normalizer
                and self.asr.source_normalizer.missing_reason
                and frame.text
            ):
                self.unranged_text = frame.text
                self.record(
                    "unranged_transcript",
                    turn_id=None,
                    text=frame.text,
                    reason=self.asr.source_normalizer.missing_reason,
                    stream_epoch=frame.metadata.get(
                        "asr_stream_epoch", self.asr.source_normalizer.epoch
                    ),
                    normalized_segment_count=len(segments),
                    raw_frame_kind=type(frame).__name__,
                )
            if changed:
                local = self._local_snapshot or self._revised_local_snapshot
                if local is not None and self._candidate and self.identifier_rules:
                    revised = self.ledger.resolve_snapshot(
                        local, require_final=False, expand_local=True
                    )
                    if revised is not None and revised != local:
                        evaluation = self.identifier_rules.evaluate(revised, self._local_assistant)
                        self._rule_evaluation = evaluation
                        if (
                            self._revised_local_snapshot is not None
                            or evaluation.path in {"ordinary", "complete"}
                            or any(
                                new.end_ms > old.end_ms
                                for old, new in zip(local.segments, revised.segments, strict=True)
                            )
                        ):
                            self._revised_local_snapshot = revised
                            self._local_snapshot = None
                        else:
                            self._local_snapshot = revised
                            self._revised_local_snapshot = None
                        self.record(
                            "identifier_local_revision",
                            text=revised.text,
                            path=evaluation.path,
                            collected=self.identifier_rules.collection.value,
                        )
                        key = self._range_key(local)
                        if key in self._retained_local:
                            _, assistant, generation, turn_id = self._retained_local[key]
                            self._retained_local[key] = (revised, assistant, generation, turn_id)
                        if self._revised_local_snapshot is not None:
                            if self._identifier_observe:
                                self._identifier_observe(revised, evaluation, self._active_turn_id)
                        else:
                            self._notify_identifier_output(revised, evaluation)
                self._revise_retained_local()
                for segment in segments:
                    related_turns = {
                        turn
                        for retained, _, _, turn in self._retained_local.values()
                        if any(
                            s.epoch == segment.epoch
                            and s.source_id == segment.source_id
                            and max(s.start_ms, segment.start_ms) < min(s.end_ms, segment.end_ms)
                            for s in retained.segments
                        )
                    }
                    if self._submitted_snapshot and any(
                        s.epoch == segment.epoch
                        and s.source_id == segment.source_id
                        and max(s.start_ms, segment.start_ms) < min(s.end_ms, segment.end_ms)
                        for s in self._submitted_snapshot.segments
                    ):
                        related_turns.add(self._turn_index)
                    if not related_turns:
                        related_turns.add(self._active_turn_id)
                    source_turn = next(iter(related_turns)) if len(related_turns) == 1 else None
                    self.record(
                        "source_transcript",
                        turn_id=source_turn,
                        related_turn_ids=sorted(related_turns),
                        source_id=segment.source_id,
                        stream_epoch=segment.epoch,
                        source_revision=segment.revision,
                        text=segment.text,
                        source_final=segment.final,
                        source_withdrawn=not bool(segment.text),
                    )
                if self._submitted_snapshot is not None:
                    resolved = self.ledger.resolve_snapshot(self._submitted_snapshot)
                    if resolved is not None:
                        restart = self.responses.finalize(
                            turn_id=str(self._turn_index),
                            source_ids=tuple(
                                (s.epoch, s.source_id) for s in self._submitted_snapshot.segments
                            ),
                            revision=max(s.revision for s in resolved.segments),
                            text=resolved.text,
                        )
                        if restart:
                            if self._bind_input:
                                self._bind_input(restart.new_response, resolved, self._assistant)
                            if self.identifier_rules:
                                self.identifier_rules.confirm_committed()
                            self.record(
                                "response_restart",
                                text=resolved.text,
                                old_response_id=restart.cancel_response_id,
                                response_id=restart.new_response.response_id,
                                reason=restart.reason,
                            )
                            await self.broadcast_interruption()
                            await self.push_frame(
                                TDResponseRestartFrame(
                                    authority=self.authority,
                                    turn_id=self._turn_index,
                                    text=resolved.text,
                                    response_id=restart.new_response.response_id,
                                )
                            )
                self._sync_transcript()
                self._schedule_decision()

    def _schedule_decision(self) -> None:
        """Keep at most one request per current text revision; never delay the watchdog."""
        token = self._candidate
        view = self._current_view()
        if not token or self._speaking or not view.text or not self._decide or view.missing_reason:
            return
        if self._rule_evaluation and self._rule_evaluation.path not in {"ordinary", "complete"}:
            if self._decision:
                self._decision.cancel()
            return
        identity = (token.generation, self.clock.text_revision)
        if self._last_requested == identity:
            return
        self._last_requested = identity
        if self._decision:
            self._decision.cancel()
        self._decision = asyncio.create_task(
            self._ask(
                token,
                self.clock.text_revision,
                view.text,
                view.final,
                self._active_turn_id,
                self._assistant,
            )
        )

    async def _ask(
        self,
        token: CandidateToken,
        revision: int,
        text: str,
        final: bool,
        turn_id: int,
        assistant: str,
    ) -> None:
        """Version-check a bounded Jev result after the asynchronous network boundary."""
        assert self._decide is not None
        started = time.monotonic()
        self.record(
            "jev_decision_attempt",
            turn_id=turn_id,
            candidate=token.generation,
            source_revision=revision,
            text=text,
            assistant=assistant,
            transcript_status="Final" if final else "Partial",
        )
        try:
            result = await self._decide(
                model=self.settings.jev.model,
                state={
                    "assistant": assistant,
                    "user": text,
                    "transcript_status": "Final" if final else "Partial",
                },
                questions=self.settings.jev.questions(),
                noul_id="yield",
                choice_id="speech_state",
                timeout=self.settings.jev.timeout_seconds,
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            result = JevResult("request_failed:" + type(error).__name__)
        duration_ms = (time.monotonic() - started) * 1000
        async with self._lock:
            if token != self._candidate or revision != self.clock.text_revision or self._closed:
                self.record(
                    "jev_discarded",
                    turn_id=turn_id,
                    candidate=token.generation,
                    source_revision=revision,
                    duration_ms=duration_ms,
                    reason="stale",
                )
                return
            self.record(
                "jev_result",
                turn_id=turn_id,
                source_revision=revision,
                duration_ms=duration_ms,
                candidate=token.generation,
                status=result.status,
                noul=result.noul,
                probabilities=result.probabilities,
            )
            if (
                result.status == "ok"
                and result.noul is not None
                and result.probabilities is not None
            ):
                try:
                    wait = self.clock.policy.fuse(
                        result.noul,
                        result.probabilities,
                        {option.id: option.wait_ms for option in self.settings.jev.options},
                        elapsed_ms=max(0, self._audio_ms - self.clock._silence_at),
                    )
                except ValueError:
                    self.record("jev_invalid_distribution", candidate=token.generation)
                    return
                self.record(
                    "jev_wait_calculated",
                    turn_id=turn_id,
                    candidate=token.generation,
                    source_revision=revision,
                    noul_ms=wait.noul_ms,
                    choice_ms=wait.choice_ms,
                    target_ms=wait.target_ms,
                    remaining_ms=wait.remaining_ms,
                    conflict=wait.conflict,
                    alpha=self.settings.alpha,
                )
                self.clock.semantic(token, wait.target_ms, text_revision=revision)

    async def advance(self, audio_ms: float) -> None:
        """Release at most one user turn after the last validity check and range consumption."""
        async with self._lock:
            self._invalidate_cleared_input()
            self._audio_ms = max(self._audio_ms, audio_ms)
            if (
                self._speaking
                or self._suspected
                or self._closed
                or self._audio_processing
                or self._audio_pending
            ):
                return
            view = self._current_view()
            if view.missing_reason:
                if self._candidate and (
                    self._audio_ms - self.clock._silence_at >= self.settings.maximum_ms
                ):
                    self.source_evidence_error = ASRSourceEvidenceError()
                    self.record(
                        "asr_source_evidence_failed",
                        reason=view.missing_reason,
                        turn_id=None,
                        candidate=self._candidate.generation,
                        maximum_ms=self.settings.maximum_ms,
                        silence_start_ms=self.clock._silence_at,
                        deadline_ms=self.clock._silence_at + self.settings.maximum_ms,
                    )
                    self._closed = True
                    self._candidate = None
                    self.clock.resume()
                    self.responses.begin_speech()
                    if self._decision:
                        self._decision.cancel()
                    await self.push_error(
                        ASRSourceEvidenceError.code, force_treat_as_permanent=True
                    )
                return
            if (
                self.identifier_rules
                and self._rule_evaluation
                and self._rule_evaluation.path == "complete"
                and self._candidate
                and view.text
                and self.identifier_rules.settings.pause_ms is not None
                and self._audio_ms - self.clock._silence_at
                >= self.identifier_rules.settings.pause_ms
            ):
                self._notify_identifier_output(view, self._rule_evaluation)
            if self._rule_evaluation and self._rule_evaluation.path not in {"ordinary", "complete"}:
                await self._advance_identifier(view)
                return
            commit = self.clock.poll(self._audio_ms)
            if not commit:
                return
            snapshot = view
            if self._rule_evaluation and self._rule_evaluation.path == "complete":
                self._retain_local(snapshot)
            self.ledger.consume()
            self.ledger.freeze_submission(snapshot)
            self._local_snapshot = None
            self._revised_local_snapshot = None
            self._pending_mixed.clear()
            self._candidate = None
            self._turn_index += 1
            self._submitted_snapshot = snapshot
            response = self.responses.submit(
                turn_id=str(self._turn_index),
                source_ids=tuple((s.epoch, s.source_id) for s in snapshot.segments),
                text=snapshot.text,
                final=snapshot.final,
            )
            if (
                self.identifier_rules
                and self._rule_evaluation
                and self._rule_evaluation.path == "complete"
            ):
                self.identifier_rules.committed()
            if self._bind_input:
                self._bind_input(response, snapshot, self._assistant)
            self.record(
                "td_commit",
                text=snapshot.text,
                source_final=snapshot.final,
                reason=commit.reason,
                candidate=commit.candidate.generation,
                sources=[
                    {"epoch": s.epoch, "source_id": s.source_id, "revision": s.revision}
                    for s in snapshot.segments
                ],
            )
            transcription = TDSubmissionFrame(
                snapshot.text, "", time_now_iso8601(), finalized=False, authority=self.authority
            )
            transcription.metadata.update(
                td_commit=True,
                td_source_final=snapshot.final,
                td_turn_id=self._turn_index,
                td_response_id=response.response_id,
            )
            await self.push_frame(transcription)

    async def _advance_identifier(self, view: TranscriptView) -> None:
        """Protect local collection independently from ordinary semantic deadlines."""
        if not self._candidate or not self.clock.media_healthy or not self.identifier_rules:
            return
        evaluation = self._rule_evaluation
        assert evaluation is not None
        settings = self.identifier_rules.settings
        elapsed = self._audio_ms - self.clock._silence_at
        completeness = settings.collection
        reminder = None
        if completeness:
            if evaluation.path == "incomplete" and elapsed >= completeness.timeout_ms:
                reminder = completeness.incomplete_text
            elif evaluation.path == "overlength" and elapsed >= completeness.overflow_pause_ms:
                reminder = completeness.overflow_text
        if reminder is not None:
            self._retain_local(self.ledger.consume_local(view))
            self._pending_mixed.clear()
            self._candidate = None
            self._rule_evaluation = None
            self._local_snapshot = None
            self._revised_local_snapshot = None
            self.clock.resume()
            self.assistant_context(reminder)
            self.record(
                "identifier_reminder",
                text=reminder,
                elapsed_ms=elapsed,
                collected=self.identifier_rules.collection.value,
            )
            frame = TTSSpeakFrame(reminder)
            frame.metadata.update(
                td_rule_reminder=True,
                td_turn_id=self._active_turn_id,
                td_output_kind="overflow" if evaluation.path == "overlength" else "incomplete",
            )
            await self.push_frame(frame)
            return
        assert settings.pause_ms is not None
        if view.text and elapsed >= settings.pause_ms:
            snapshot = self.ledger.consume_local(view)
            self._pending_mixed.clear()
            self._revised_local_snapshot = None
            self._retain_local(snapshot)
            self._local_snapshot = snapshot
            self._local_assistant = self._assistant
            self.record(
                "identifier_local_processed",
                candidate=self._candidate.generation,
                collection_generation=self.identifier_rules.collection.generation,
                text=snapshot.text,
                collected=self.identifier_rules.collection.value,
                source_final=snapshot.final,
                elapsed_ms=elapsed,
            )
            self._notify_identifier_output(snapshot, evaluation)
            if evaluation.path == "local":
                self._candidate = None
                self._rule_evaluation = None
                self.clock.resume()

    async def filter_provider_frame(self, frame: Frame) -> bool:
        """Consume provider text and endpoint signals; allow ordinary control/media frames."""
        if isinstance(frame, ASRStreamEpochFrame):
            async with self._lock:
                while self.ledger.epoch < frame.epoch:
                    self.ledger.reconnect()
                if self.asr.source_normalizer:
                    while self.asr.source_normalizer.epoch < frame.epoch:
                        self.asr.source_normalizer.reconnect()
                self.record("asr_stream_epoch", epoch=frame.epoch)
            return True
        if isinstance(frame, (InterimTranscriptionFrame, TranscriptionFrame)):
            epoch = frame.metadata.get("asr_stream_epoch", self.ledger.epoch)
            if type(epoch) is int and epoch >= 0 and epoch != self.ledger.epoch:
                self.record("stale_source_frame", epoch=epoch)
                return True
            await self.receive_transcript(frame)
            return True
        return isinstance(
            frame,
            (
                ProposedUserStartedSpeakingFrame,
                ProposedUserStoppedSpeakingFrame,
                UserStartedSpeakingFrame,
                UserStoppedSpeakingFrame,
            ),
        )

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        """Filter both directions so provider broadcasts cannot reach the aggregator."""
        await super().process_frame(frame, direction)
        if isinstance(frame, StartFrame) and self._watchdog is None:
            self.record(
                "td_settings_snapshot",
                turn_id=None,
                minimum_ms=self.settings.minimum_ms,
                maximum_ms=self.settings.maximum_ms,
                final_wait_ms=self.settings.final_wait_ms,
                alpha=self.settings.alpha,
                conflict_threshold=self.settings.conflict_threshold,
                vad=self.settings.vad.model_dump(),
                jev_model=self.settings.jev.model,
                noul_instructions=self.settings.jev.noul_instructions,
                choice_instructions=self.settings.jev.choice_instructions,
                options=[option.model_dump() for option in self.settings.jev.options],
            )
            self._watchdog = self.create_task(self._watch(), name="custom-td-watchdog")
        if isinstance(frame, (EndFrame, CancelFrame)):
            await self._close_tasks()
        if not await self.filter_provider_frame(frame):
            await self.push_frame(frame, direction)

    async def _watch(self) -> None:
        """Poll independently of cloud requests, using only received audio progress."""
        while not self._closed:
            await asyncio.sleep(0.01)
            if self._last_audio_wall is not None and time.monotonic() - self._last_audio_wall > 0.1:
                if self.clock.media_healthy:
                    self.record("media_gap")
                self.clock.media_healthy = False
            await self.advance(self._audio_ms)

    async def _close_tasks(self) -> None:
        """Fence the session before cancelling its asynchronous work."""
        self._closed = True
        for task in (self._decision, self._watchdog):
            if task:
                task.cancel()
        await asyncio.gather(
            *(t for t in (self._decision, self._watchdog) if t), return_exceptions=True
        )

    async def cleanup(self) -> None:
        """Release all per-session work when the pipeline exits."""
        await self._close_tasks()
        await super().cleanup()


class CustomTDAudioInput(FrameProcessor):
    """Analyze original PCM before ASR can consume it or block on its transport."""

    def __init__(self, coordinator: CustomTDCoordinator, vad: Any) -> None:
        """Bind one prewarmed local Silero analyzer to the session coordinator."""
        super().__init__()
        self.coordinator = coordinator
        self.vad = vad
        self._state = VADState.QUIET
        self._audio_ms = 0.0
        self._queued_audio: dict[int, int] = {}

    async def queue_frame(
        self,
        frame: Frame,
        direction: FrameDirection = FrameDirection.DOWNSTREAM,
        callback: FrameCallback | None = None,
    ) -> None:
        """Fence arrived PCM before the SDK can delay it in its input queue.

        Args:
            frame: Existing SDK frame, without changing media format or routing.
            direction: Existing pipeline direction.
            callback: Native callback retained for successful processing.
        """
        if not isinstance(frame, InputAudioRawFrame) or self._cancelling:
            await super().queue_frame(frame, direction, callback)
            return
        self._queued_audio[frame.id] = self._queued_audio.get(frame.id, 0) + 1
        self.coordinator._audio_pending += 1
        try:
            await super().queue_frame(frame, direction, callback)
        except (Exception, asyncio.CancelledError):
            self._finish_queued_audio(frame.id)
            raise

    def _finish_queued_audio(self, frame_id: int) -> None:
        """Retire one queued occurrence; direct calls do not consume another frame's slot."""
        count = self._queued_audio.get(frame_id, 0)
        if count:
            self.coordinator._audio_pending -= 1
            if count == 1:
                del self._queued_audio[frame_id]
            else:
                self._queued_audio[frame_id] = count - 1

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        """Check PCM, update audio time, and release the queue fence only after VAD."""
        is_audio = isinstance(frame, InputAudioRawFrame)
        try:
            await super().process_frame(frame, direction)
            if isinstance(frame, InputAudioRawFrame):
                if frame.sample_rate != 16000 or frame.num_channels != 1 or len(frame.audio) % 2:
                    raise ValueError("Custom TD requires 16 kHz mono signed 16-bit PCM")
                self._audio_ms += len(frame.audio) / 32
                self.coordinator._last_audio_wall = time.monotonic()
                self.coordinator.clock.media_healthy = True
                self.coordinator._audio_processing += 1
                try:
                    state = await self.vad.analyze_audio(frame.audio)
                    if state != self._state:
                        self.coordinator.record_diagnostic(
                            "vad_state_changed",
                            previous=self._state.name,
                            state=state.name,
                            input_audio_ms=self._audio_ms,
                            trigger="local_vad",
                        )
                    self.coordinator._suspected = state == VADState.STARTING
                    if state == VADState.SPEAKING and self._state != VADState.SPEAKING:
                        await self.coordinator.speech_started()
                    if state == VADState.QUIET and self._state in {
                        VADState.SPEAKING,
                        VADState.STOPPING,
                    }:
                        stop_ms = self.coordinator.settings.vad.stop_secs * 1000
                        end = max(0, self._audio_ms - stop_ms)
                        await self.coordinator.speech_stopped(end)
                    self._state = state
                finally:
                    self.coordinator._audio_processing -= 1
        except (Exception, asyncio.CancelledError):
            if is_audio:
                self.coordinator.clock.media_healthy = False
            raise
        finally:
            if is_audio:
                self._finish_queued_audio(frame.id)
        if is_audio:
            await self.coordinator.advance(self._audio_ms)
        await self.push_frame(frame, direction)

    async def cleanup(self) -> None:
        """Cancel SDK queues before releasing pending media and Silero's executor."""
        await super().cleanup()
        self.coordinator.clock.media_healthy = False
        self.coordinator._audio_pending -= sum(self._queued_audio.values())
        self._queued_audio.clear()
        await self.vad.cleanup()


async def prepare_custom_td(
    *,
    asr: ASRService,
    settings: CustomTDSettings,
    api_key: str,
    evidence_sink: EvidenceSink | None = None,
    responses: ResponseRevisions | None = None,
    bind_input: InputBinding | None = None,
    identifier_rules: IdentifierRules | None = None,
    identifier_output: IdentifierNotify | None = None,
    identifier_observe: IdentifierNotify | None = None,
) -> tuple[CustomTDAudioInput, CustomTDCoordinator, Any]:
    """Prewarm bundled Silero off the event loop and build a session-only HTTP client."""
    import httpx
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    from pipecat.audio.vad.vad_analyzer import VADParams

    from src.pipeline.jev import JevClient

    def build_vad() -> Any:
        """Load only Pipecat's bundled ONNX asset, with no network model download."""
        analyzer = SileroVADAnalyzer(
            sample_rate=16000, params=VADParams(**settings.vad.model_dump())
        )
        analyzer.set_sample_rate(16000)
        return analyzer

    vad = await asyncio.to_thread(build_vad)
    client = httpx.AsyncClient(timeout=settings.jev.timeout_seconds, follow_redirects=False)
    jev = JevClient(
        endpoint=settings.jev.endpoint,
        api_key=api_key,
        client=client,
        max_calls=settings.jev.max_calls,
    )
    coordinator = CustomTDCoordinator(
        asr=asr,
        settings=settings,
        decide=jev.decide,
        evidence_sink=evidence_sink,
        responses=responses,
        bind_input=bind_input,
        identifier_rules=identifier_rules,
        identifier_output=identifier_output,
        identifier_observe=identifier_observe,
    )
    if isinstance(asr.processor, SourceOwnedASRMixin):
        asr.processor._td_diagnostic_sink = coordinator.record_diagnostic
    return CustomTDAudioInput(coordinator, vad), coordinator, client
