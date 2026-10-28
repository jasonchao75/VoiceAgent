"""Explicit aggregator strategies that accept only the custom TD commit signal."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pipecat.frames.frames import (
    DataFrame,
    Frame,
    LLMContextFrame,
    TranscriptionFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMAssistantAggregator,
    LLMAssistantAggregatorParams,
    LLMUserAggregator,
    LLMUserAggregatorParams,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.turns.types import ProcessFrameResult
from pipecat.turns.user_start import ExternalUserTurnStartStrategy
from pipecat.turns.user_stop.base_user_turn_stop_strategy import BaseUserTurnStopStrategy
from pipecat.turns.user_turn_strategies import UserTurnStrategies


@dataclass
class TDCommitFrame(UserStoppedSpeakingFrame):
    """A private in-process signal created only after custom TD atomically commits."""

    authority: object | None = None


class TDStopStrategy(BaseUserTurnStopStrategy):
    """No provider proposals, transcript heuristics, fallback timers or local Smart Turn."""

    def __init__(self, authority: object) -> None:
        """Bind this stop strategy to exactly one coordinator instance."""
        super().__init__()
        self._authority = authority

    async def process_frame(self, frame: Frame) -> ProcessFrameResult:
        """Resolve only a signal carrying this session's private authority identity."""
        if isinstance(frame, TDCommitFrame) and frame.authority is self._authority:
            await self.trigger_user_turn_stopped(enable_user_speaking_frames=False)
            return ProcessFrameResult.STOP
        return ProcessFrameResult.CONTINUE


def custom_aggregator_params(authority: object) -> LLMUserAggregatorParams:
    """Disable framework endpoint/idle fallbacks and explicitly choose both strategies."""
    return LLMUserAggregatorParams(
        audio_idle_timeout=0,
        user_turn_stop_timeout=float("inf"),
        user_turn_strategies=UserTurnStrategies(
            start=[ExternalUserTurnStartStrategy()],
            stop=[TDStopStrategy(authority)],
        ),
    )


@dataclass
class TDSubmissionFrame(TranscriptionFrame):
    """One ordered data frame carries both transcript and private commit authority."""

    authority: object | None = None


@dataclass
class TDResponseRestartFrame(DataFrame):
    """Replace context within the same original user turn without aggregating a new turn."""

    authority: object | None = None
    turn_id: int = 0
    text: str = ""
    response_id: str = ""


@dataclass
class TDTranscriptUpdateFrame(DataFrame):
    """Update finalized user text without rerunning inference or removing assistant output."""

    authority: object | None = None
    turn_id: int = 0
    text: str = ""


class TDUserAggregator(LLMUserAggregator):
    """Reuse Pipecat aggregation while atomically ordering custom transcript and stop."""

    def __init__(self, context: LLMContext, authority: object) -> None:
        """Bind the normal aggregator to one coordinator's immutable commit identity."""
        super().__init__(
            context, params=custom_aggregator_params(authority), _realtime_service_mode=False
        )
        self._td_authority = authority
        self._td_seen: set[int] = set()
        self._td_indices: dict[int, int] = {}
        self._td_response_id: str | None = None

    async def push_context_frame(
        self,
        direction: FrameDirection = FrameDirection.DOWNSTREAM,
    ) -> None:
        """Tag the original request before another Final revision can supersede it."""
        frame = LLMContextFrame(self._context)
        if self._td_response_id is not None:
            frame.metadata["td_response_id"] = self._td_response_id
        await self.push_frame(frame, direction)

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        """Process the transcript before the stop signal inside the same ordered task."""
        if isinstance(frame, TDTranscriptUpdateFrame):
            if frame.authority is self._td_authority and frame.text.strip():
                index = self._td_indices.get(frame.turn_id)
                messages = self._context.get_messages()
                if index is not None and index < len(messages):
                    messages[index] = {"role": "user", "content": frame.text}
            return
        if isinstance(frame, TDResponseRestartFrame):
            if frame.authority is not self._td_authority or not frame.text.strip():
                return
            index = self._td_indices.get(frame.turn_id, len(self._context.get_messages()))
            self._context.set_messages(
                [
                    *self._context.get_messages()[:index],
                    {"role": "user", "content": frame.text},
                ]
            )
            self._td_seen.add(frame.turn_id)
            self._td_indices[frame.turn_id] = index
            self._td_response_id = frame.response_id
            context_frame = LLMContextFrame(self._context)
            context_frame.metadata["td_response_id"] = frame.response_id
            await self.push_frame(context_frame)
            return
        if isinstance(frame, TDSubmissionFrame):
            turn = frame.metadata.get("td_turn_id")
            if (
                frame.authority is not self._td_authority
                or not isinstance(turn, int)
                or turn in self._td_seen
            ):
                return
            self._td_seen.add(turn)
            self._td_response_id = frame.metadata.get("td_response_id")
            self._td_indices[turn] = len(self._context.get_messages())
            await super().process_frame(frame, direction)
            await super().process_frame(TDCommitFrame(authority=self._td_authority), direction)
            return
        await super().process_frame(frame, direction)


def create_custom_aggregators(context: LLMContext, authority: object) -> tuple[Any, Any]:
    """Build the existing user/assistant pair with only the custom user specialization."""
    user = TDUserAggregator(context, authority)
    assistant = LLMAssistantAggregator(
        context,
        params=LLMAssistantAggregatorParams(),
        _realtime_service_mode=False,
        _paired_user_aggregator=user,
    )
    return user, assistant
