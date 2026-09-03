"""In-memory non-blocking capture of final text and turn timings."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from pipecat.frames.frames import (
    InputAudioRawFrame,
    LLMFullResponseEndFrame,
    LLMTextFrame,
    MetricsFrame,
    TranscriptionFrame,
    TTSAudioRawFrame,
    TTSStartedFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.metrics.metrics import LLMUsageMetricsData

from src.history.models import HistoryTurn, TurnMetric
from src.history.recording import AudioRecorder
from src.llm.capabilities import get_model_capability


@dataclass(slots=True)
class _TurnState:
    """Mutable timestamps for the current conversational turn."""

    index: int
    user_stop_ms: float | None = None
    asr_final_ms: float | None = None
    llm_first_ms: float | None = None
    tts_start_ms: float | None = None
    tts_audio_ms: float | None = None
    browser_playback_ms: float | None = None
    reasoning_tokens: int | None = None


@dataclass(slots=True)
class CallCapture:
    """Collect bounded history data without database I/O in the frame path."""

    provider: str
    model: str
    recorder: AudioRecorder | None = None
    started: float = field(default_factory=time.monotonic)
    turns: list[HistoryTurn] = field(default_factory=list)
    _current: _TurnState = field(default_factory=lambda: _TurnState(index=0))
    _states: list[_TurnState] = field(default_factory=list)
    _assistant_chunks: list[str] = field(default_factory=list)

    def elapsed_ms(self) -> float:
        """Return milliseconds since the voice session began."""
        return (time.monotonic() - self.started) * 1000

    def observe(self, frame: object) -> None:
        """Consume one deduplicated Pipecat frame without blocking."""
        elapsed = self.elapsed_ms()
        if isinstance(frame, InputAudioRawFrame) and self.recorder is not None:
            self.recorder.push(frame.audio)
        elif isinstance(frame, UserStoppedSpeakingFrame):
            self._flush_assistant(elapsed)
            if self._current.user_stop_ms is not None:
                self._states.append(self._current)
            self._current = _TurnState(index=len(self._states), user_stop_ms=elapsed)
        elif isinstance(frame, TranscriptionFrame):
            self._current.asr_final_ms = elapsed
            self.turns.append(
                HistoryTurn(
                    sequence=len(self.turns), role="user", text=frame.text, created_ms=elapsed
                )
            )
        elif isinstance(frame, LLMTextFrame):
            if self._current.llm_first_ms is None:
                self._current.llm_first_ms = elapsed
            self._assistant_chunks.append(frame.text)
        elif isinstance(frame, LLMFullResponseEndFrame):
            self._flush_assistant(elapsed)
        elif isinstance(frame, TTSStartedFrame) and self._current.tts_start_ms is None:
            self._current.tts_start_ms = elapsed
        elif isinstance(frame, TTSAudioRawFrame) and self._current.tts_audio_ms is None:
            self._current.tts_audio_ms = elapsed
        elif isinstance(frame, MetricsFrame):
            for metric in frame.data:
                if isinstance(metric, LLMUsageMetricsData):
                    self._current.reasoning_tokens = metric.value.reasoning_tokens

    def browser_event(self, event: str, elapsed_ms: float) -> None:
        """Attach browser playback timing to the current turn."""
        if event == "first_playback" and self._current.browser_playback_ms is None:
            # Keep derived durations on one server monotonic clock. The browser
            # timestamp is still logged separately for client-side telemetry.
            self._current.browser_playback_ms = self.elapsed_ms()

    def finalize(self) -> tuple[list[HistoryTurn], list[TurnMetric]]:
        """Flush final assistant text and return immutable snapshots."""
        self._flush_assistant(self.elapsed_ms())
        states = [*self._states, self._current]
        capability = get_model_capability(self.provider, self.model)
        control = None
        if capability and capability.control_name:
            control = f"{capability.control_name}={capability.control_value}"
        metrics = []
        for state in states:
            reasoning_status = capability.expected_status if capability else "unverified"
            if state.reasoning_tokens is not None and state.reasoning_tokens > 0:
                reasoning_status = "detected"
            metrics.append(
                TurnMetric(
                    turn_index=state.index,
                    llm_first_token_ms=_difference(state.llm_first_ms, state.asr_final_ms),
                    tts_first_audio_ms=_difference(state.tts_audio_ms, state.tts_start_ms),
                    server_to_playback_ms=_difference(
                        state.browser_playback_ms, state.tts_audio_ms
                    ),
                    turn_to_playback_ms=_difference(state.browser_playback_ms, state.user_stop_ms),
                    reasoning_tokens=state.reasoning_tokens,
                    reasoning_status=reasoning_status,
                    reasoning_control=control,
                )
            )
        return list(self.turns), metrics

    def _flush_assistant(self, elapsed_ms: float) -> None:
        text = "".join(self._assistant_chunks).strip()
        if text:
            self.turns.append(
                HistoryTurn(
                    sequence=len(self.turns), role="assistant", text=text, created_ms=elapsed_ms
                )
            )
        self._assistant_chunks.clear()


def _difference(later: float | None, earlier: float | None) -> float | None:
    """Return a rounded positive duration when both events exist."""
    if later is None or earlier is None:
        return None
    return round(max(0.0, later - earlier), 1)
