"""Carry immutable task identity through native audio rechunking without changing PCM."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Mapping
from contextvars import ContextVar
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, ClassVar, Literal

from pipecat.frames.frames import (
    Frame,
    InterruptionFrame,
    OutputAudioRawFrame,
    OutputTransportMessageFrame,
    OutputTransportMessageUrgentFrame,
    TTSAudioRawFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.serializers.protobuf import ProtobufFrameSerializer

_PREFIX = "voice-agent-audio-v1:"
AudioKind = Literal["normal", "echo", "correction", "overflow", "incomplete"]


@dataclass
class TaskAudioFrame(TTSAudioRawFrame):
    """A per-task immutable class binding survives the SDK's type(frame)(pcm, ...) copy."""

    task_identity: ClassVar[Mapping[str, str | None]] = MappingProxyType({})

    def __post_init__(self) -> None:
        """Use the existing protobuf name field, never PCM samples or a parallel audio stream."""
        super().__post_init__()
        self.name = _PREFIX + json.dumps(dict(self.task_identity), separators=(",", ":"))


def audio_frame_type(
    *,
    playback_id: str,
    kind: AudioKind,
    response_id: str | None,
) -> type[TaskAudioFrame]:
    """Create one session task's frame type; no later task can mutate its identity.

    Raises:
        ValueError: If bounded non-secret identifiers or output kind are invalid.
    """
    if (
        not isinstance(playback_id, str)
        or not playback_id
        or len(playback_id) > 128
        or kind not in {"normal", "echo", "correction", "overflow", "incomplete"}
        or (
            response_id is not None and (not isinstance(response_id, str) or len(response_id) > 256)
        )
    ):
        raise ValueError("Invalid audio task identity")
    identity = MappingProxyType(
        {"playback_id": playback_id, "kind": kind, "response_id": response_id}
    )
    return type("TaskBoundAudioFrame", (TaskAudioFrame,), {"task_identity": identity})


def decode_audio_identity(name: str) -> dict[str, str | None] | None:
    """Read only the versioned bounded identity schema; ordinary SDK names stay unmodified."""
    if not name.startswith(_PREFIX) or len(name) > 1024:
        return None
    try:
        data = json.loads(name[len(_PREFIX) :])
        if not isinstance(data, dict) or set(data) != {"playback_id", "kind", "response_id"}:
            return None
        audio_frame_type(**data)
        return data
    except (ValueError, TypeError):
        return None


class TaskProtobufSerializer(ProtobufFrameSerializer):
    """Reuse the locked wire format/codec and serialize the explicit task name field."""

    def __init__(self) -> None:
        """Keep immutable sender identity local to the actual write coroutine."""
        super().__init__()
        self._write_identity: ContextVar[str | None] = ContextVar("ws_audio_identity", default=None)

    def bind_output(self, output: Any) -> None:
        """Preserve identity across the locked SDK writer's fresh OutputAudioRawFrame copy.

        The existing writer still owns connection checks, rate conversion, pacing
        and serialization. Context-local provenance cannot leak to another task.
        """
        original = output.write_audio_frame

        async def write(frame: OutputAudioRawFrame) -> bool:
            """Carry only the original task identity through this one native write."""
            token = self._write_identity.set(
                frame.name if isinstance(frame, TaskAudioFrame) else None
            )
            try:
                return await original(frame)
            finally:
                self._write_identity.reset(token)

        output.write_audio_frame = write

    async def serialize(self, frame: Frame) -> str | bytes | None:
        """Normalize only task audio subclasses because the base serializer uses exact types."""
        if isinstance(frame, TaskAudioFrame):
            ordinary = OutputAudioRawFrame(frame.audio, frame.sample_rate, frame.num_channels)
            ordinary.name = frame.name
            ordinary.pts = frame.pts
            frame = ordinary
        if isinstance(frame, OutputAudioRawFrame) and self._write_identity.get():
            frame.name = self._write_identity.get() or frame.name
        return await super().serialize(frame)


class AudioTaskTagger(FrameProcessor):
    """Tag original provider contexts before the existing sender chunks their PCM."""

    def __init__(self, evidence_sink: Callable[[dict[str, Any]], None] | None = None) -> None:
        """Keep task identities session-local and distinguish sending from client rendering."""
        super().__init__()
        self._sink = evidence_sink
        self._contexts: dict[str, type[TaskAudioFrame]] = {}
        self._issued: dict[str, type[TaskAudioFrame]] = {}
        self._ended: set[str] = set()

    def acknowledge(self, playback_id: str, event: str) -> None:
        """Retire stop targets only after validated client completion, never on server send."""
        if event in {"task_finished", "task_stopped", "task_failed"}:
            self._issued.pop(playback_id, None)

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        """Preserve PCM/clock metadata and send task boundaries in the same output queue."""
        await super().process_frame(frame, direction)
        if direction != FrameDirection.DOWNSTREAM:
            await self.push_frame(frame, direction)
            return
        if isinstance(frame, TTSStartedFrame) and frame.context_id in self._ended:
            self._ended.remove(frame.context_id)
            self._contexts.pop(frame.context_id, None)
        if isinstance(frame, TaskAudioFrame):
            await self.push_frame(frame, direction)
            return
        if isinstance(frame, TTSAudioRawFrame):
            context_id = frame.context_id
            if not context_id:
                if self._sink:
                    self._sink(
                        {"event": "playback_audio_unbound", "reason": "missing_provider_context"}
                    )
                return
            if context_id in self._ended:
                return
            cls = self._contexts.get(context_id)
            if cls is None:
                response_id = frame.metadata.get("td_response_id")
                kind = frame.metadata.get("td_output_kind", "normal")
                if kind not in {"normal", "echo", "correction", "overflow", "incomplete"}:
                    kind = "normal"
                cls = audio_frame_type(
                    playback_id=uuid.uuid4().hex,
                    kind=kind,
                    response_id=response_id if isinstance(response_id, str) else None,
                )
                self._contexts[context_id] = cls
                self._issued[str(cls.task_identity["playback_id"])] = cls
                if self._sink:
                    self._sink(
                        {
                            "event": "playback_task_prepared",
                            **dict(cls.task_identity),
                            "turn_id": frame.metadata.get("td_turn_id"),
                        }
                    )
            tagged = cls(frame.audio, frame.sample_rate, frame.num_channels, context_id=context_id)
            tagged.metadata.update(frame.metadata)
            tagged.pts = frame.pts
            tagged.transport_destination = frame.transport_destination
            await self.push_frame(tagged, direction)
            return
        if isinstance(frame, TTSStoppedFrame):
            await self.push_frame(frame, direction)
            context_id = frame.context_id
            if context_id in self._contexts and context_id not in self._ended:
                self._ended.add(context_id)
                await self.push_frame(
                    OutputTransportMessageFrame(
                        message={
                            "label": "voice-agent-playback",
                            "event": "task_end",
                            "playback_id": self._contexts[context_id].task_identity["playback_id"],
                        }
                    )
                )
            return
        if isinstance(frame, InterruptionFrame):
            for cls in list(self._issued.values()):
                await self.push_frame(
                    OutputTransportMessageUrgentFrame(
                        message={
                            "label": "voice-agent-playback",
                            "event": "stop_task",
                            "playback_id": cls.task_identity["playback_id"],
                            "request_id": uuid.uuid4().hex,
                        }
                    )
                )
        await self.push_frame(frame, direction)
