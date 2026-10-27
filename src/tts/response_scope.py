"""Bind provider audio context IDs to original response provenance before synthesis."""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from typing import Any

from pipecat.frames.frames import (
    Frame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    TTSAudioRawFrame,
    TTSSpeakFrame,
    TTSStoppedFrame,
)
from pipecat.processors.frame_processor import FrameDirection

from src.pipeline.response_revision import ResponseRevisions

_UNBOUND = "__unbound_tts_response__"


class ResponseScopedTTSMixin:
    """Reject cancelled provider audio at enqueue and emission without relabeling late data."""

    _tts_contexts: dict[str, Any]

    def __init__(self, *, response_owner: ResponseRevisions | None = None, **kwargs: Any) -> None:
        """Keep immutable context provenance for this bounded session only."""
        self.response_owner = response_owner
        self._response_ids: dict[str, str | None] = {}
        self._context_generations: dict[str, int] = {}
        self._context_kinds: dict[str, str] = {}
        self._context_turns: dict[str, str | int | None] = {}
        self._tts_kind: ContextVar[str] = ContextVar("tts_kind", default="normal")
        self._tts_turn: ContextVar[str | int | None] = ContextVar("tts_turn", default=None)
        self._tts_response: ContextVar[str | None] = ContextVar("tts_response", default=_UNBOUND)
        super().__init__(**kwargs)

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        """Capture tagged text provenance before provider aggregation or background jobs."""
        owner = self.response_owner
        if owner is None:
            await super().process_frame(frame, direction)  # type: ignore[misc]
            return
        if isinstance(frame, (LLMFullResponseStartFrame, LLMFullResponseEndFrame, LLMTextFrame)):
            response_id = frame.metadata.get("td_response_id")
            if not isinstance(response_id, str) or not owner.accepts_output(response_id):
                return
            token = self._tts_response.set(response_id)
        elif isinstance(frame, TTSSpeakFrame):
            token = self._tts_response.set(None)
        else:
            await super().process_frame(frame, direction)  # type: ignore[misc]
            return
        kind = frame.metadata.get("td_output_kind", "normal")
        if kind not in {"normal", "overflow", "incomplete"}:
            kind = "normal"
        turn = frame.metadata.get("td_turn_id")
        if turn is None and isinstance(
            frame, (LLMFullResponseStartFrame, LLMFullResponseEndFrame, LLMTextFrame)
        ):
            turn = owner.current.turn_id if owner.current else None
        kind_token = self._tts_kind.set(kind)
        turn_token = self._tts_turn.set(turn)
        try:
            await super().process_frame(frame, direction)  # type: ignore[misc]
        finally:
            self._tts_response.reset(token)
            self._tts_kind.reset(kind_token)
            self._tts_turn.reset(turn_token)

    def create_context_id(self) -> str:
        """Bind before sending so a late audio callback never borrows the current answer ID."""
        context_id = super().create_context_id()  # type: ignore[misc]
        if self.response_owner is not None:
            response_id = self._tts_response.get()
            generation = self.response_owner.speech_generation
            kind = self._tts_kind.get()
            turn = self._tts_turn.get()
            if context_id in self._response_ids and (
                self._response_ids[context_id] != response_id
                or self._context_generations[context_id] != generation
                or self._context_kinds[context_id] != kind
                or self._context_turns[context_id] != turn
            ):
                context_id = str(uuid.uuid4())
            self._response_ids[context_id] = response_id
            self._context_generations[context_id] = generation
            self._context_kinds[context_id] = kind
            self._context_turns[context_id] = turn
        return context_id

    def _accept_audio_context(self, context_id: str | None, frame: Frame | None) -> bool:
        """Fail closed for unknown audio; unscoped opening/reminder contexts remain permitted."""
        owner = self.response_owner
        if owner is None or frame is None:
            return True
        if context_id not in self._response_ids:
            return False
        response_id = self._response_ids[context_id]
        if response_id is None:
            if self._context_generations[context_id] != owner.speech_generation:
                return False
        elif not owner.accepts_output(response_id):
            return False
        else:
            frame.metadata["td_response_id"] = response_id
        frame.metadata["td_output_kind"] = self._context_kinds[context_id]
        frame.metadata["td_turn_id"] = self._context_turns[context_id]
        return True

    async def append_to_audio_context(self, context_id: str | None, frame: Any) -> None:
        """Fence before queue insertion as well as later emission after cancellation races."""
        if isinstance(frame, Frame) and not self._accept_audio_context(context_id, frame):
            return
        await super().append_to_audio_context(context_id, frame)  # type: ignore[misc]

    async def push_frame(
        self,
        frame: Frame,
        direction: FrameDirection = FrameDirection.DOWNSTREAM,
    ) -> None:
        """Preserve the provider context identity instead of stamping current global state."""
        context_id = getattr(frame, "context_id", None)
        if context_id or isinstance(frame, TTSAudioRawFrame):
            if not self._accept_audio_context(context_id, frame):
                if isinstance(frame, TTSStoppedFrame):
                    self._tts_contexts.pop(str(context_id), None)
                return
        await super().push_frame(frame, direction)  # type: ignore[misc]
