"""In-memory non-blocking capture of final text and turn timings."""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pipecat.frames.frames import (
    InputAudioRawFrame,
    LLMContextFrame,
    LLMFullResponseEndFrame,
    LLMTextFrame,
    MetricsFrame,
    TranscriptionFrame,
    TTSAudioRawFrame,
    TTSStartedFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.metrics.metrics import LLMUsageMetricsData

from src.history.models import HistoryTurn, LatencyInterval, TurnMetric
from src.history.recording import AudioRecorder
from src.history.render_clock import RenderClockLedger
from src.history.rtp_source import RTPCaptureLedger
from src.history.source_clock import CaptureSampleLedger, observe_input_source
from src.llm.capabilities import get_model_capability


@dataclass(slots=True)
class _TurnState:
    """Mutable timestamps for the current conversational turn."""

    index: int
    user_stop_ms: float | None = None
    asr_final_ms: float | None = None
    td_commit_ms: float | None = None
    td_turn_id: int | str | None = None
    renderer_observed: bool = False
    first_response_id: str | None = None
    playback_timing: LatencyInterval | None = None
    e2e_timing: LatencyInterval | None = None
    llm_request_ms: float | None = None
    llm_first_ms: float | None = None
    tts_start_ms: float | None = None
    tts_audio_ms: float | None = None
    browser_playback_ms: float | None = None
    asr_final_latency_ms: float | None = None
    asr_final_reason: str | None = None
    interrupted_by_user: bool = False
    reasoning_tokens: int | None = None
    context_applied: bool | None = None
    context_failure_reason: str | None = None


@dataclass(slots=True)
class CallCapture:
    """Collect bounded history data without database I/O in the frame path."""

    provider: str
    model: str
    recorder: AudioRecorder | None = None
    chat_mode: bool = False
    started: float = field(default_factory=time.monotonic)
    turns: list[HistoryTurn] = field(default_factory=list)
    td_events: list[dict[str, Any]] = field(default_factory=list)
    _current: _TurnState = field(default_factory=lambda: _TurnState(index=0))
    _states: list[_TurnState] = field(default_factory=list)
    _assistant_chunks: list[str] = field(default_factory=list)
    _assistant_response_id: str | None = None
    _assistant_turn_id: str | int | None = None
    _input_audio_ms: float = 0.0
    _playback_tasks: dict[str, dict[str, Any]] = field(default_factory=dict)
    playback_listener: Callable[[str, str], bool | None] | None = None
    render_clock: RenderClockLedger = field(init=False)
    capture_clock: RenderClockLedger = field(init=False)
    rtp_source: RTPCaptureLedger = field(init=False)
    input_samples: CaptureSampleLedger = field(default_factory=CaptureSampleLedger)
    _source_ends: dict[str, dict[str, Any]] = field(default_factory=dict)
    _timing_pending: dict[str, None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Keep challenge bounds on exactly the same monotonic clock as this capture."""
        self.render_clock = RenderClockLedger(now_ms=self.elapsed_ms)
        self.capture_clock = RenderClockLedger(now_ms=self.elapsed_ms)
        self.rtp_source = RTPCaptureLedger(now_ms=self.elapsed_ms)

    def elapsed_ms(self) -> float:
        """Return milliseconds since the voice session began."""
        return (time.monotonic() - self.started) * 1000

    def observe(self, frame: object) -> None:
        """Consume one Pipecat frame without blocking.

        Frames may arrive multiple times across the pipeline; each occurrence
        is tracked because timing events are first-occurrence per turn state.
        """
        elapsed = self.elapsed_ms()
        metadata = getattr(frame, "metadata", {})
        if metadata.get("td_source_only"):
            return
        if isinstance(frame, InputAudioRawFrame):
            if frame.audio and len(frame.audio) % 2 == 0:
                proof = metadata.get("td_rtp_input")
                if isinstance(proof, dict):
                    offset = self.input_samples.offset
                    self.input_samples.append(len(frame.audio) // 2)
                    if frame.sample_rate == 16000 and frame.num_channels == 1:
                        self.rtp_source.observe(offset, len(frame.audio) // 2, proof)
                else:
                    observe_input_source(
                        self.input_samples,
                        name=frame.name,
                        sample_count=len(frame.audio) // 2,
                        sample_rate=frame.sample_rate,
                        channels=frame.num_channels,
                    )
            bytes_per_second = frame.sample_rate * frame.num_channels * 2
            if bytes_per_second > 0:
                self._input_audio_ms += len(frame.audio) / bytes_per_second * 1000
            if self.recorder is not None:
                self.recorder.push(frame.audio)
        elif isinstance(frame, UserStartedSpeakingFrame):
            # A new user turn begins. Persist the previous turn if it captured
            # user speech, then reset state so assistant timings from the prior
            # turn (or the opening script) do not bleed into the new turn.
            self._flush_assistant(elapsed)
            if self._has_user_content(self._current):
                self._current.interrupted_by_user = self._current.browser_playback_ms is None
                self._states.append(self._current)
            self._current = _TurnState(index=len(self._states))
        elif isinstance(frame, UserStoppedSpeakingFrame):
            self._flush_assistant(elapsed)
            # Multiple VAD endpoint events can fire for one utterance (e.g.
            # Deepgram Flux eager EOT). Keep the latest stop timestamp on the
            # active turn instead of spawning an empty turn each time.
            self._current.user_stop_ms = elapsed
        elif isinstance(frame, TranscriptionFrame):
            if frame.metadata.get("td_commit"):
                self._current.td_commit_ms = elapsed
                self._current.td_turn_id = frame.metadata.get("td_turn_id")
                self._current.asr_final_reason = (
                    "source_final_timing_unavailable"
                    if frame.metadata.get("td_source_final")
                    else "partial_at_td_commit"
                )
            else:
                self._current.asr_final_ms = elapsed
                self._capture_asr_latency(frame)
            if frame.metadata.get("td_commit"):
                self.record_td_event(
                    {
                        "event": "conversation_utterance",
                        "role": "user",
                        "turn_id": frame.metadata.get("td_turn_id"),
                        "text": frame.text,
                        "history_sequence": len(self.turns),
                        "history_metric_index": self._current.index,
                        "source_final": frame.metadata.get("td_source_final"),
                    }
                )
            self.turns.append(
                HistoryTurn(
                    sequence=len(self.turns), role="user", text=frame.text, created_ms=elapsed
                )
            )
        elif isinstance(frame, LLMContextFrame) and (
            self._current.asr_final_ms is not None or self._current.td_commit_ms is not None
        ):
            # The user aggregator emits this frame immediately before the LLM
            # service starts inference, so it is the closest observable marker
            # for "LLM request sent".
            if self._current.llm_request_ms is None:
                self._current.llm_request_ms = elapsed
        elif isinstance(frame, LLMTextFrame) and self._current.llm_request_ms is not None:
            if self._current.llm_first_ms is None:
                self._current.llm_first_ms = elapsed
            response_id = frame.metadata.get("td_response_id")
            turn_id = frame.metadata.get("td_turn_id")
            if self._current.first_response_id is None and isinstance(response_id, str):
                self._current.first_response_id = response_id
            if (response_id, turn_id) != (self._assistant_response_id, self._assistant_turn_id):
                self._flush_assistant(elapsed)
                self._assistant_response_id = response_id
                self._assistant_turn_id = turn_id
            self._assistant_chunks.append(frame.text)
        elif isinstance(frame, LLMFullResponseEndFrame):
            self._flush_assistant(elapsed)
        elif (
            isinstance(frame, TTSStartedFrame)
            and self._current.llm_first_ms is not None
            and self._current.tts_start_ms is None
        ):
            self._current.tts_start_ms = elapsed
        elif (
            isinstance(frame, TTSAudioRawFrame)
            and self._current.tts_start_ms is not None
            and self._current.tts_audio_ms is None
        ):
            self._current.tts_audio_ms = elapsed
        elif isinstance(frame, MetricsFrame):
            for metric in frame.data:
                if isinstance(metric, LLMUsageMetricsData):
                    self._current.reasoning_tokens = metric.value.reasoning_tokens

    def record_td_event(self, event: dict[str, Any]) -> None:
        """Collect actual decision evidence without synchronous persistence on the audio path."""
        turn_key = str(event.get("turn_id"))
        if event.get("event") == "speech_resumed":
            if not self._source_ends.get(turn_key, {}).get("sealed"):
                self._source_ends.pop(turn_key, None)
        if event.get("event") == "candidate_created":
            end = event.get("speech_end_audio_ms")
            if isinstance(end, (int, float)) and math.isfinite(end) and end >= 0:
                self._source_ends[turn_key] = {
                    "sample": end * 16,
                    "created_ms": self.elapsed_ms(),
                    "sealed": False,
                }
                if len(self._source_ends) > 64:
                    self._source_ends.pop(next(iter(self._source_ends)))
                self._refresh_source_ends()
        if event.get("event") == "td_commit" and turn_key in self._source_ends:
            self._source_ends[turn_key]["sealed"] = True
        if event.get("event") == "playback_task_prepared" and event.get("playback_id"):
            self._playback_tasks.setdefault(
                event["playback_id"], {**event, "receipts": {}, "prepared_ms": self.elapsed_ms()}
            )
        if len(self.td_events) < 10000:
            self.td_events.append({**event, "created_ms": self.elapsed_ms()})
        elif len(self.td_events) == 10000:
            self.td_events.append(
                {
                    "event": "td_evidence_truncated",
                    "dropped_events": 1,
                    "retained_limit": 10000,
                    "created_ms": self.elapsed_ms(),
                }
            )
        else:
            self.td_events[-1]["dropped_events"] += 1

    def ack_capture_clock(
        self,
        sample_id: str,
        clock_id: str,
        sample_rate: int,
        frame: int,
    ) -> bool:
        """Retain capture-only causal evidence; never authorize output observations."""
        if not self.capture_clock.ack(sample_id, clock_id, sample_rate, frame):
            return False
        self._refresh_source_ends()
        self._refresh_render_timing()
        self._refresh_e2e_timing()
        return True

    def accept_rtp_packet_records(self, epoch: str, records: list[dict[str, Any]]) -> bool:
        """Join authenticated reports only to the current native connection's observed PCM."""
        if not self.rtp_source.add_records(epoch, records):
            return False
        self._refresh_source_ends()
        self._refresh_render_timing()
        self._refresh_e2e_timing()
        return True

    def _refresh_source_ends(self) -> None:
        """Freeze sample-proven source bounds before live anchors expire during TD waiting."""
        for source in self._source_ends.values():
            if "bounds" in source or self.elapsed_ms() - source["created_ms"] > 2000:
                continue
            first = self.input_samples.locate(math.floor(source["sample"]))
            last = self.input_samples.locate(math.ceil(source["sample"]))
            coordinates: dict[str, Any] = {}
            if first is None or last is None:
                lower_point = self.rtp_source.locate_sample(math.floor(source["sample"]))
                upper_point = self.rtp_source.locate_sample(math.ceil(source["sample"]))
                if (
                    lower_point is None
                    or upper_point is None
                    or lower_point.clock_id != upper_point.clock_id
                ):
                    continue
                first = (lower_point.clock_id, 16000, lower_point.lower_frame)
                last = (upper_point.clock_id, 16000, upper_point.upper_frame)
                coordinates = {
                    "coordinate_kind": "browser_reported_rtp_capture_time",
                    "mapping_spans": [*lower_point.proofs, *upper_point.proofs],
                }
            if first[:2] != last[:2]:
                continue
            lower = self.capture_clock.bounds(*first)
            upper = self.capture_clock.bounds(*last)
            if lower is None or upper is None or lower.lower_ms > upper.upper_ms:
                continue
            source["bounds"] = (lower.lower_ms, upper.upper_ms)
            source["anchors"] = [
                self.capture_clock.observation(key)
                for key in dict.fromkeys((*lower.anchor_ids, *upper.anchor_ids))
            ]
            source["coordinates"] = {
                "clock_id": first[0],
                "sample_rate": first[1],
                "first_frame": first[2],
                "last_frame": last[2],
                "input_sample_lower": math.floor(source["sample"]),
                "input_sample_upper": math.ceil(source["sample"]),
                "mapping_spans": self.input_samples.evidence(math.floor(source["sample"]))
                + self.input_samples.evidence(math.ceil(source["sample"])),
                **coordinates,
            }

    def ack_render_clock(
        self,
        sample_id: str,
        clock_id: str,
        sample_rate: int,
        frame: int,
    ) -> bool:
        """Persist one immutable anchor and refresh only pending identified tasks."""
        if not self.render_clock.ack(sample_id, clock_id, sample_rate, frame):
            return False
        self._refresh_render_timing()
        return True

    def _refresh_render_timing(self) -> None:
        """Derive only conservative playback bounds; absent speech clocks remain absent."""
        for playback_id in list(self._timing_pending):
            task = self._playback_tasks[playback_id]
            start = task["receipts"]["task_started"]
            frame, rate, clock_id = start[4:]
            bounds = self.render_clock.bounds(clock_id, rate, frame)
            if bounds is None:
                if self.elapsed_ms() - task["start_received_ms"] > 2000:
                    self._timing_pending.pop(playback_id)
                continue
            self._timing_pending.pop(playback_id)
            response_id = task.get("response_id")
            if not isinstance(response_id, str) or bounds.upper_ms < task["prepared_ms"]:
                continue
            timing = LatencyInterval(
                lower_ms=max(0, bounds.lower_ms - task["prepared_ms"]),
                upper_ms=bounds.upper_ms - task["prepared_ms"],
                playback_id=playback_id,
                response_id=response_id,
                anchor_ids=bounds.anchor_ids,
                source="authenticated_worklet_causal_bracket",
                origin="server_audio_task_prepared",
            )
            source_end = self._source_ends.get(str(task.get("turn_id")), {})
            source_ready = (
                source_end.get("sealed")
                and "bounds" in source_end
                and bounds.upper_ms >= source_end["bounds"][0]
            )
            self.record_td_event(
                {
                    "event": "playback_timing_bounds",
                    "turn_id": task.get("turn_id"),
                    "response_id": response_id,
                    "playback_id": playback_id,
                    "playback_range": timing.model_dump(mode="json"),
                    "anchors": [self.render_clock.observation(key) for key in bounds.anchor_ids],
                    "e2e_missing_reason": None if source_ready else "source_end_clock_unavailable",
                }
            )
            task["render_bounds"] = bounds
            task["render_anchors"] = [
                self.render_clock.observation(key) for key in bounds.anchor_ids
            ]
            self._refresh_e2e_timing()
            if task.get("kind") != "normal":
                continue
            for state in [*self._states, self._current]:
                if (
                    state.td_turn_id is not None
                    and str(state.td_turn_id) == str(task.get("turn_id"))
                    and state.first_response_id == response_id
                    and state.playback_timing is None
                ):
                    state.playback_timing = timing

    def _refresh_e2e_timing(self) -> None:
        """Join frozen source/render proofs even when their authenticated acks arrive late."""
        for playback_id, task in self._playback_tasks.items():
            bounds = task.get("render_bounds")
            response_id = task.get("response_id")
            if bounds is None or task.get("e2e_recorded") or not isinstance(response_id, str):
                continue
            source = self._source_ends.get(str(task.get("turn_id")), {})
            if source.get("sealed") and "bounds" in source:
                source_lower, source_upper = source["bounds"]
                if bounds.upper_ms >= source_lower:
                    e2e_timing = LatencyInterval(
                        lower_ms=max(0, bounds.lower_ms - source_upper),
                        upper_ms=bounds.upper_ms - source_lower,
                        playback_id=playback_id,
                        response_id=response_id,
                        anchor_ids=bounds.anchor_ids,
                        source="authenticated_worklet_causal_bracket",
                        origin="vad_speech_end_source_sample",
                    )
                    self.record_td_event(
                        {
                            "event": "e2e_timing_bounds",
                            "turn_id": task.get("turn_id"),
                            "response_id": response_id,
                            "playback_id": playback_id,
                            "e2e_range": e2e_timing.model_dump(mode="json"),
                            "source_anchors": source["anchors"],
                            "source_coordinates": source["coordinates"],
                            "render_anchors": [anchor for anchor in task["render_anchors"]],
                        }
                    )
                    task["e2e_recorded"] = True
                    if task.get("kind") == "normal":
                        for state in [*self._states, self._current]:
                            if (
                                str(state.td_turn_id) == str(task.get("turn_id"))
                                and state.first_response_id == response_id
                            ):
                                state.e2e_timing = e2e_timing

    def playback_receipt(
        self,
        playback_id: str,
        event: str,
        rendered_samples: int,
        elapsed_ms: float,
        request_id: str | None = None,
        *,
        failure_reason: str | None = None,
        render_frame: int | None = None,
        render_sample_rate: int | None = None,
        render_clock_id: str | None = None,
    ) -> bool:
        """Record render-thread facts against prepared identity, never the current user turn.

        Browser elapsed time remains in its own clock domain; server receipt time
        cannot substitute for the actual render timestamp in latency metrics.
        """
        task = self._playback_tasks.get(playback_id)
        if (
            task is None
            or event not in {"task_started", "task_finished", "task_stopped", "task_failed"}
            or rendered_samples < 0
            or (event == "task_started" and rendered_samples == 0)
            or not math.isfinite(elapsed_ms)
            or elapsed_ms < 0
            or (
                failure_reason is not None
                and (event != "task_failed" or failure_reason != "render_queue_limit")
            )
        ):
            return False
        coordinates = (render_frame, render_sample_rate, render_clock_id)
        if any(value is not None for value in coordinates):
            if (
                type(render_frame) is not int
                or not 0 <= render_frame <= 9_007_199_254_740_991
                or type(render_sample_rate) is not int
                or not 8000 <= render_sample_rate <= 384000
                or not isinstance(render_clock_id, str)
                or len(render_clock_id) != 32
                or any(char not in "0123456789abcdef" for char in render_clock_id)
            ):
                return False
            clock = (render_clock_id, render_sample_rate)
            if task.get("render_clock") not in (None, clock):
                return False
        previous = task["receipts"].get(event)
        if previous is not None:
            if rendered_samples < previous[0] or elapsed_ms < previous[1]:
                return False
            if previous[4:] != coordinates:
                return False
            if (rendered_samples, request_id, failure_reason) == (
                previous[0],
                previous[2],
                previous[3],
            ):
                return True
        start = task["receipts"].get("task_started")
        start_samples = rendered_samples if event == "task_started" else start[0] if start else None
        start_frame = render_frame if event == "task_started" else start[4] if start else None
        if start_frame is not None and start_samples is not None:
            for terminal_event in ("task_finished", "task_stopped", "task_failed"):
                terminal = task["receipts"].get(terminal_event)
                terminal_samples = (
                    rendered_samples
                    if event == terminal_event
                    else terminal[0]
                    if terminal
                    else None
                )
                terminal_frame = (
                    render_frame if event == terminal_event else terminal[4] if terminal else None
                )
                # HTTP messages can arrive in either order. Only coordinates on
                # the already-validated renderer clock establish this relation.
                if (
                    terminal_frame is not None
                    and terminal_samples is not None
                    and (
                        terminal_samples < start_samples
                        or terminal_frame - start_frame < terminal_samples
                    )
                ):
                    return False
        if self.playback_listener and self.playback_listener(playback_id, event) is False:
            return False
        if render_clock_id is not None:
            task["render_clock"] = (render_clock_id, render_sample_rate)
        task["receipts"][event] = (
            rendered_samples,
            elapsed_ms,
            request_id,
            failure_reason,
            *coordinates,
        )
        if event == "task_started" and render_frame is not None:
            task["start_received_ms"] = self.elapsed_ms()
            self._timing_pending[playback_id] = None
            if len(self._timing_pending) > 64:
                self._timing_pending.pop(next(iter(self._timing_pending)))
            self._refresh_render_timing()
        if (
            event in {"task_started", "task_finished", "task_stopped"}
            and rendered_samples > 0
            and task.get("turn_id") is not None
        ):
            for state in [*self._states, self._current]:
                if state.td_turn_id is not None and str(state.td_turn_id) == str(task["turn_id"]):
                    state.renderer_observed = True
        self.record_td_event(
            {
                "event": "playback_renderer_receipt",
                "playback_id": playback_id,
                "response_id": task.get("response_id"),
                "turn_id": task.get("turn_id"),
                "output_kind": task.get("kind"),
                "renderer_event": event,
                "rendered_samples": rendered_samples,
                "client_elapsed_ms": elapsed_ms,
                "request_id": request_id,
                "evidence_source": "audio_worklet_render",
                "failure_reason": failure_reason,
                "render_frame": render_frame,
                "render_sample_rate": render_sample_rate,
                "render_clock_id": render_clock_id,
            }
        )
        return True

    def browser_event(self, event: str, elapsed_ms: float) -> None:
        """Retain legacy telemetry without assigning receipt time to identified TD turns."""
        if (
            event == "first_playback"
            and self._current.td_commit_ms is None
            and self._current.tts_audio_ms is not None
            and self._current.browser_playback_ms is None
        ):
            # Keep derived durations on one server monotonic clock. The browser
            # timestamp is still logged separately for client-side telemetry.
            self._current.browser_playback_ms = self.elapsed_ms()

    def chat_text(self, text: str) -> None:
        """Start a text-input turn so Chat test reuses LLM and TTS capture."""
        elapsed = self.elapsed_ms()
        self._flush_assistant(elapsed)
        if self._has_user_content(self._current):
            self._states.append(self._current)
        self._current = _TurnState(index=len(self._states))
        self._current.user_stop_ms = elapsed
        self._current.asr_final_ms = elapsed
        self.turns.append(
            HistoryTurn(sequence=len(self.turns), role="user", text=text, created_ms=elapsed)
        )

    def record_context_update(self, turn_index: int, applied: bool, reason: str | None) -> None:
        """Attach one safe AssemblyAI context result to its originating Turn."""
        state = next(
            (
                candidate
                for candidate in [*self._states, self._current]
                if candidate.index == turn_index
            ),
            None,
        )
        if state is None:
            return
        state.context_applied = applied
        state.context_failure_reason = None if applied else reason

    def finalize(self) -> tuple[list[HistoryTurn], list[TurnMetric]]:
        """Flush final assistant text and return immutable snapshots."""
        self._flush_assistant(self.elapsed_ms())
        return list(self.turns), self.metrics_snapshot()

    def metrics_snapshot(self) -> list[TurnMetric]:
        """Return current Turn metrics without closing or mutating the capture."""
        states = [s for s in [*self._states, self._current] if self._has_user_content(s)]
        capability = get_model_capability(self.provider, self.model)
        control = None
        if capability and capability.control_name:
            control = f"{capability.control_name}={capability.control_value}"
        metrics = []
        for state in states:
            reasoning_status = capability.expected_status if capability else "unverified"
            if state.reasoning_tokens is not None and state.reasoning_tokens > 0:
                reasoning_status = "detected"
            asr_final_latency = state.asr_final_latency_ms
            llm_request_splicing = _difference(state.llm_request_ms, state.asr_final_ms)
            llm_first_token = _difference(state.llm_first_ms, state.llm_request_ms)
            tts_initial = _difference(state.tts_start_ms, state.llm_first_ms)
            tts_first_audio = _difference(state.tts_audio_ms, state.tts_start_ms)
            playback = _difference(state.browser_playback_ms, state.tts_audio_ms)
            # The breakdown is a telescoping chain; summing the parts guarantees it
            # equals the end-to-end latency even after per-step rounding.
            breakdown = [
                *([] if self.chat_mode else [asr_final_latency]),
                llm_request_splicing,
                llm_first_token,
                tts_initial,
                tts_first_audio,
                playback,
            ]
            complete_breakdown = [value for value in breakdown if value is not None]
            e2e: float | None
            if len(complete_breakdown) == len(breakdown):
                e2e = round(sum(complete_breakdown), 1)
            else:
                e2e = None
            metrics.append(
                TurnMetric(
                    turn_index=state.index,
                    asr_final_latency_ms=asr_final_latency,
                    llm_request_splicing_ms=llm_request_splicing,
                    llm_first_token_ms=llm_first_token,
                    tts_initial_ms=tts_initial,
                    tts_first_audio_ms=tts_first_audio,
                    playback_ms=playback,
                    server_to_playback_ms=playback,
                    turn_to_playback_ms=e2e,
                    timing_ranges=(
                        {
                            **(
                                {"playback": state.playback_timing} if state.playback_timing else {}
                            ),
                            **({"e2e": state.e2e_timing} if state.e2e_timing else {}),
                        }
                    ),
                    asr_final_reason=state.asr_final_reason,
                    incomplete_reason=self._incomplete_reason(state),
                    reasoning_tokens=state.reasoning_tokens,
                    reasoning_status=reasoning_status,
                    reasoning_control=control,
                    context_applied=state.context_applied,
                    context_failure_reason=state.context_failure_reason,
                )
            )
        return metrics

    def _capture_asr_latency(self, frame: TranscriptionFrame) -> None:
        """Measure Flux EOT latency from its final word timing and audio clock."""
        result = frame.result
        words = result.get("words") if isinstance(result, dict) else None
        last_word = words[-1] if isinstance(words, list) and words else None
        word_end = last_word.get("end") if isinstance(last_word, dict) else None
        if not isinstance(word_end, (int, float)):
            self._current.asr_final_reason = "word_timing_unavailable"
            return
        latency = self._input_audio_ms - float(word_end) * 1000
        if latency < 0:
            self._current.asr_final_reason = "audio_clock_mismatch"
            return
        self._current.asr_final_latency_ms = round(latency, 1)

    @staticmethod
    def _incomplete_reason(state: _TurnState) -> str | None:
        """Explain the first missing causal stage for an incomplete turn."""
        if state.llm_first_ms is None:
            return (
                "interrupted_before_llm_first_token"
                if state.interrupted_by_user
                else "session_ended_before_llm_first_token"
            )
        if state.tts_audio_ms is None:
            return (
                "interrupted_before_tts_audio"
                if state.interrupted_by_user
                else "session_ended_before_tts_audio"
            )
        if state.browser_playback_ms is None:
            if state.e2e_timing is not None:
                return "bounded_timing_only"
            if state.playback_timing is not None:
                return "source_end_clock_unavailable"
            return (
                "render_clock_uncorrelated"
                if state.renderer_observed
                else "client_playback_unconfirmed"
            )
        return None

    def _flush_assistant(self, elapsed_ms: float) -> None:
        text = "".join(self._assistant_chunks).strip()
        if text:
            if self._assistant_response_id is not None:
                self.record_td_event(
                    {
                        "event": "conversation_utterance",
                        "role": "assistant",
                        "turn_id": self._assistant_turn_id,
                        "response_id": self._assistant_response_id,
                        "text": text,
                        "history_sequence": len(self.turns),
                    }
                )
            self.turns.append(
                HistoryTurn(
                    sequence=len(self.turns), role="assistant", text=text, created_ms=elapsed_ms
                )
            )
        self._assistant_chunks.clear()
        self._assistant_response_id = None
        self._assistant_turn_id = None

    @staticmethod
    def _has_user_content(state: _TurnState) -> bool:
        """Return True if a state represents an actual user utterance.

        Empty VAD endpoint events (e.g. ambient noise or Flux eager EOT)
        must not be surfaced as turn metrics.
        """
        return state.asr_final_ms is not None or state.td_commit_ms is not None


def _difference(later: float | None, earlier: float | None) -> float | None:
    """Return a rounded positive duration when both events exist."""
    if later is None or earlier is None:
        return None
    return round(max(0.0, later - earlier), 1)
