"""In-process source ownership fences around locked Pipecat provider services."""

from __future__ import annotations

from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from pipecat.frames.frames import (
    Frame,
    InterimTranscriptionFrame,
    ProposedUserStartedSpeakingFrame,
    ProposedUserStoppedSpeakingFrame,
    SystemFrame,
    TranscriptionFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection

_BOUNDARIES = (
    ProposedUserStartedSpeakingFrame,
    ProposedUserStoppedSpeakingFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)


@dataclass
class ASRStreamEpochFrame(SystemFrame):
    """A source connection attempt starts a new audio/identifier namespace."""

    epoch: int = 0


class SourceOwnedASRMixin:
    """Preserve native behavior unless the session explicitly chose custom TD."""

    _td_source_mode: bool = False
    _td_stream_epoch: int = -1

    def __init__(self, **kwargs: Any) -> None:
        """Keep immutable receive-task provenance separate from the current connection."""
        self._td_stream_epoch = -1
        self._td_claimed_epoch: int | None = None
        self._td_source_epoch: ContextVar[int | None] = ContextVar(
            f"asr_source_epoch_{id(self)}", default=None
        )
        super().__init__(**kwargs)

    async def _begin_source_epoch(self) -> None:
        """Announce a namespace before the SDK creates receiver/callback tasks."""
        self._td_stream_epoch += 1
        self._td_source_epoch.set(self._td_stream_epoch)
        await self.push_frame(ASRStreamEpochFrame(epoch=self._td_stream_epoch))

    async def _claim_source_connection(self) -> None:
        """Fence actual opens, including retries which bypass the SDK's _connect method."""
        epoch = self._td_source_epoch.get()
        if epoch is None or epoch != self._td_stream_epoch or epoch == self._td_claimed_epoch:
            await self._begin_source_epoch()
        self._td_claimed_epoch = self._td_stream_epoch

    def _source_context_connector(self, connect: Any) -> Any:
        """Bind lazy SDK connections on entry, before receive callbacks are registered."""

        @asynccontextmanager
        async def scoped(*args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
            if self._td_source_mode:
                await self._claim_source_connection()
            async with connect(*args, **kwargs) as connection:
                yield connection

        return scoped

    async def _websocket_connect(self, *args: Any, **kwargs: Any) -> Any:
        """Keep a retry's new namespace in its receiver loop and inherited child tasks."""
        if self._td_source_mode:
            await self._claim_source_connection()
        return await super()._websocket_connect(*args, **kwargs)  # type: ignore[misc]

    async def _connect(self) -> None:
        """Fence stream identifiers before the provider begins accepting new audio."""
        if not self._td_source_mode:
            await super()._connect()  # type: ignore[misc]
            return
        token = self._td_source_epoch.set(None)
        try:
            await self._begin_source_epoch()
            await super()._connect()  # type: ignore[misc]
        finally:
            self._td_source_epoch.reset(token)

    async def push_frame(
        self,
        frame: Frame,
        direction: FrameDirection = FrameDirection.DOWNSTREAM,
    ) -> None:
        """Tag source-only text before observers and consume provider-owned boundaries."""
        if self._td_source_mode:
            if isinstance(frame, _BOUNDARIES):
                return
            if isinstance(frame, (TranscriptionFrame, InterimTranscriptionFrame)):
                frame.metadata["td_source_only"] = True
                epoch = self._td_source_epoch.get()
                # A missing receive context is not evidence for the current socket.
                frame.metadata["asr_stream_epoch"] = epoch
        await super().push_frame(frame, direction)  # type: ignore[misc]

    async def broadcast_frame(self, frame_cls: type[Frame], **kwargs: Any) -> None:
        """Keep upstream/downstream SDK endpoint proposals away from the user aggregator."""
        if self._td_source_mode and issubclass(frame_cls, _BOUNDARIES):
            return
        await super().broadcast_frame(frame_cls, **kwargs)  # type: ignore[misc]
