"""Non-blocking assistant-turn context delivery for ASR providers."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from pipecat.frames.frames import (
    Frame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

logger = logging.getLogger(__name__)


class AssistantTurnAccumulator:
    """Collect one assistant response and emit exactly one completed snapshot."""

    def __init__(self) -> None:
        """Initialize an empty turn buffer."""
        self._parts: list[str] = []
        self._active = False

    def consume(self, frame: Frame) -> str | None:
        """Consume an LLM frame and return text only when its turn completes."""
        if isinstance(frame, LLMFullResponseStartFrame):
            self._parts.clear()
            self._active = True
        elif self._active and isinstance(frame, LLMTextFrame):
            self._parts.append(frame.text)
        elif self._active and isinstance(frame, LLMFullResponseEndFrame):
            text = "".join(self._parts).strip()
            self._parts.clear()
            self._active = False
            return text or None
        return None


class AssistantContextBridge(FrameProcessor):
    """Forward LLM frames immediately and update ASR context in a side task."""

    def __init__(
        self,
        update_context: Callable[[str], Awaitable[None]],
        on_result: Callable[[int, bool, str | None], None] | None = None,
    ) -> None:
        """Bind one session-local ASR context updater."""
        super().__init__()
        self._update_context = update_context
        self._on_result = on_result
        self._accumulator = AssistantTurnAccumulator()
        self._turn_index = 0

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        """Pass through frames and schedule one update after each completed turn."""
        await super().process_frame(frame, direction)
        text = self._accumulator.consume(frame) if direction is FrameDirection.DOWNSTREAM else None
        await self.push_frame(frame, direction)
        if text:
            turn_index = self._turn_index
            self._turn_index += 1
            self.create_task(self._deliver(turn_index, text), name=f"{self.name}-update")

    async def _deliver(self, turn_index: int, text: str) -> None:
        """Contain provider failures so TTS and playback remain independent."""
        try:
            await self._update_context(text)
        except Exception as exc:
            logger.warning("assistant_context_update_failed error_type=%s", type(exc).__name__)
            if self._on_result is not None:
                self._on_result(turn_index, False, f"provider_update_failed:{type(exc).__name__}")
        else:
            if self._on_result is not None:
                self._on_result(turn_index, True, None)
