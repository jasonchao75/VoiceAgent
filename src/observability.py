"""Non-secret timing events for Voice Agent acceptance testing."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from pipecat.frames.frames import (
    InterruptionFrame,
    LLMTextFrame,
    TranscriptionFrame,
    TTSAudioRawFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.observers.base_observer import BaseObserver, FramePushed

logger = logging.getLogger(__name__)

EventSink = Callable[[str, float], None]
FrameSink = Callable[[object], None]


class SessionTimingObserver(BaseObserver):
    """Record first-occurrence pipeline timings without storing transcripts."""

    def __init__(
        self,
        *,
        session_id: str,
        event_sink: EventSink | None = None,
        frame_sink: FrameSink | None = None,
    ) -> None:
        """Initialize the observer.

        Args:
            session_id: Non-secret correlation ID.
            event_sink: Optional in-memory callback for frontend metrics.
        """
        super().__init__()
        self._session_id = session_id
        self._event_sink = event_sink
        self._frame_sink = frame_sink
        self._started_at = time.monotonic()
        self._seen_frames: set[int] = set()
        self._turn_events: set[str] = set()

    async def on_push_frame(self, data: FramePushed) -> None:
        """Map significant Pipecat frames to safe timing events."""
        # A frame is observed at every processor boundary. Capture it once by
        # frame ID so transcripts, text chunks, and turn transitions are not
        # duplicated as the same frame traverses the pipeline.
        if data.frame.id in self._seen_frames:
            return
        self._seen_frames.add(data.frame.id)
        if self._frame_sink is not None:
            self._frame_sink(data.frame)

        event: str | None = None
        if isinstance(data.frame, UserStartedSpeakingFrame):
            self._turn_events.clear()
            event = "user_turn_start"
        elif isinstance(data.frame, UserStoppedSpeakingFrame):
            event = "user_turn_end"
        elif isinstance(data.frame, TranscriptionFrame):
            event = "asr_final"
        elif isinstance(data.frame, LLMTextFrame):
            event = "llm_first_token"
        elif isinstance(data.frame, TTSAudioRawFrame):
            event = "tts_first_audio"
        elif isinstance(data.frame, InterruptionFrame):
            event = "interruption"

        if event is None or event in self._turn_events:
            return
        self._turn_events.add(event)
        elapsed_ms = (time.monotonic() - self._started_at) * 1000
        logger.info(
            "session_event session_id=%s event=%s elapsed_ms=%.1f",
            self._session_id,
            event,
            elapsed_ms,
        )
        if self._event_sink is not None:
            self._event_sink(event, elapsed_ms)


class SessionEventBuffer:
    """Small bounded event buffer for browser-visible latency calculations."""

    def __init__(self, *, max_events: int = 100) -> None:
        """Initialize an empty bounded buffer."""
        self._max_events = max_events
        self._events: list[dict[str, float | str]] = []

    def add(self, event: str, elapsed_ms: float) -> None:
        """Append one safe timing event."""
        self._events.append({"event": event, "elapsed_ms": round(elapsed_ms, 1)})
        if len(self._events) > self._max_events:
            del self._events[: len(self._events) - self._max_events]

    def snapshot(self) -> list[dict[str, float | str]]:
        """Return a copy suitable for a JSON API response."""
        return list(self._events)
