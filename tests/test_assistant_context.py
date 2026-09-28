"""AssemblyAI assistant context aggregation tests."""

import asyncio

import pytest
from pipecat.frames.frames import (
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
)
from pipecat.processors.frame_processor import FrameDirection

from src.pipeline.assistant_context import (
    AssistantContextBridge,
    AssistantTurnAccumulator,
)


def test_assistant_turn_emits_one_complete_snapshot() -> None:
    """Streaming text is accumulated without per-token context updates."""
    accumulator = AssistantTurnAccumulator()
    assert accumulator.consume(LLMFullResponseStartFrame()) is None
    assert accumulator.consume(LLMTextFrame("Hello ")) is None
    assert accumulator.consume(LLMTextFrame("there.")) is None
    assert accumulator.consume(LLMFullResponseEndFrame()) == "Hello there."
    assert accumulator.consume(LLMFullResponseEndFrame()) is None


def test_new_response_discards_incomplete_previous_buffer() -> None:
    """A restarted response cannot leak partial text into the next context snapshot."""
    accumulator = AssistantTurnAccumulator()
    accumulator.consume(LLMFullResponseStartFrame())
    accumulator.consume(LLMTextFrame("discard me"))
    accumulator.consume(LLMFullResponseStartFrame())
    accumulator.consume(LLMTextFrame("keep me"))
    assert accumulator.consume(LLMFullResponseEndFrame()) == "keep me"


@pytest.mark.asyncio
async def test_context_update_runs_after_frames_continue_downstream() -> None:
    """A slow context update never serializes the LLM-to-TTS frame path."""
    release = asyncio.Event()
    started = asyncio.Event()
    forwarded: list[object] = []
    results: list[tuple[int, bool, str | None]] = []
    tasks: list[asyncio.Task[None]] = []

    async def update_context(_text: str) -> None:
        started.set()
        await release.wait()

    bridge = AssistantContextBridge(
        update_context,
        lambda turn, ok, reason: results.append((turn, ok, reason)),
    )

    async def push(frame, _direction):  # type: ignore[no-untyped-def]
        forwarded.append(frame)

    def create_task(coro, **_kwargs):  # type: ignore[no-untyped-def]
        task = asyncio.create_task(coro)
        tasks.append(task)
        return task

    bridge.push_frame = push  # type: ignore[method-assign]
    bridge.create_task = create_task  # type: ignore[method-assign]
    frames = [LLMFullResponseStartFrame(), LLMTextFrame("Hello"), LLMFullResponseEndFrame()]
    for frame in frames:
        await bridge.process_frame(frame, FrameDirection.DOWNSTREAM)

    await started.wait()
    assert forwarded == frames
    assert len(tasks) == 1 and not tasks[0].done()
    release.set()
    await tasks[0]
    assert results == [(0, True, None)]


@pytest.mark.asyncio
async def test_context_failure_is_contained_and_reported_safely() -> None:
    """Provider context failures are recorded without blocking or exposing messages."""
    results: list[tuple[int, bool, str | None]] = []

    async def fail(_text: str) -> None:
        raise RuntimeError("secret provider payload")

    bridge = AssistantContextBridge(
        fail,
        lambda turn, ok, reason: results.append((turn, ok, reason)),
    )
    await bridge._deliver(3, "completed assistant turn")
    assert results == [(3, False, "provider_update_failed:RuntimeError")]
