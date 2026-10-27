"""A Flux cancel acknowledgement fences untagged late bytes and the next Speak."""

import asyncio

from src.config import AudioConfig, TTSConfig
from src.pipeline.response_revision import ResponseRevisions
from src.tts.factory import create_default_tts_registry


def setup_service():
    """Use the actual scoped Flux SDK service, replacing only its wire sender."""
    owner = ResponseRevisions()
    old = owner.submit(turn_id="t", source_ids=((0, "s"),), text="old", final=False)
    service = create_default_tts_registry().create(
        provider="deepgram_flux",
        api_key="inert-no-socket",
        config=TTSConfig(voice="flux-alexis-en", provider="deepgram_flux"),
        audio=AudioConfig(output_sample_rate=24000),
        response_owner=owner,
    )
    service._transport_is_active = lambda: True
    sent = []

    async def send(message):
        sent.append(message)

    service._fixture_interrupt_sent = asyncio.Event()
    original_send = send

    async def observed_send(message):
        await original_send(message)
        if message.get("type") == "Interrupt":
            service._fixture_interrupt_sent.set()

    service._transport_send_json = observed_send
    service._tts_response.set(old.response_id)
    old_context = service.create_context_id()
    return service, owner, old_context, sent


async def replace_context(service, owner):
    """Install the new provenance exactly as text aggregation does before run_tts."""
    owner.finalize(turn_id="t", source_ids=((0, "s"),), revision=2, text="new")
    service._tts_response.set(owner.current.response_id)
    context = service.create_context_id()
    service._playing_context_id = None
    service._turn_context_id = context
    await service.create_audio_context(context)
    return context


async def test_actual_flux_drops_old_wire_audio_until_interrupt_ack():
    service, owner, old, sent = setup_service()
    await service.on_audio_context_interrupted(old)
    await asyncio.wait_for(service._fixture_interrupt_sent.wait(), 1)
    new = await replace_context(service, owner)
    await service._handle_audio(b"\x09\x00" * 240)
    assert sent == [{"type": "Interrupt"}]
    assert service._audio_contexts[new].empty(), "Old wire bytes acquired the new response identity"


async def test_actual_flux_does_not_send_new_speak_before_interrupt_ack():
    service, owner, old, sent = setup_service()
    await service.on_audio_context_interrupted(old)
    await asyncio.wait_for(service._fixture_interrupt_sent.wait(), 1)
    new = await replace_context(service, owner)
    pending = asyncio.create_task(anext(service.run_tts("new", new)))
    try:
        await asyncio.sleep(0)
        assert sent == [{"type": "Interrupt"}], "New Speak escaped before the old wire boundary"
        await service._handle_message({"type": "SpeechInterrupted"})
        await asyncio.wait_for(pending, 1)
        assert sent[-1] == {"type": "Speak", "text": "new"}
    finally:
        pending.cancel()
        await asyncio.gather(pending, return_exceptions=True)


async def test_old_metadata_cannot_close_fresh_context_and_new_audio_survives_ack():
    service, owner, old, _ = setup_service()
    await service.on_audio_context_interrupted(old)
    await asyncio.wait_for(service._fixture_interrupt_sent.wait(), 1)
    new = await replace_context(service, owner)
    await service._handle_message({"type": "SpeechMetadata", "speech_id": "old-wire-turn"})
    assert service._audio_contexts[new].empty()
    await service._handle_message({"type": "SpeechInterrupted"})
    await service._handle_audio(b"\x02\x00" * 240)
    frame = service._audio_contexts[new].get_nowait()
    assert frame.audio == b"\x02\x00" * 240
    assert frame.metadata["td_response_id"] == owner.current.response_id


async def test_missing_ack_fails_permanently_without_sending_new_text():
    service, owner, old, sent = setup_service()
    service._interrupt_timeout = 0.01
    errors = []

    async def error(message, **kwargs):
        errors.append(kwargs)

    service.push_error = error
    await service.on_audio_context_interrupted(old)
    await asyncio.wait_for(service._fixture_interrupt_sent.wait(), 1)
    new = await replace_context(service, owner)
    assert [frame async for frame in service.run_tts("new", new)] == []
    assert sent == [{"type": "Interrupt"}]
    assert errors == [{"force_treat_as_permanent": True}]
    await service._handle_message({"type": "SpeechInterrupted"})
    await service._handle_audio(b"\x09\x00" * 240)
    assert service._audio_contexts[new].empty()


async def test_multiple_local_contexts_send_only_one_pending_interrupt():
    service, _, old, sent = setup_service()
    await service.on_audio_context_interrupted(old)
    await asyncio.wait_for(service._fixture_interrupt_sent.wait(), 1)
    await service.on_audio_context_interrupted("second-abandoned-local-context")
    assert sent == [{"type": "Interrupt"}]


async def test_no_active_speech_warning_releases_boundary_without_fake_audio():
    service, owner, old, sent = setup_service()
    await service.on_audio_context_interrupted(old)
    await asyncio.wait_for(service._fixture_interrupt_sent.wait(), 1)
    new = await replace_context(service, owner)
    await service._handle_message({"type": "Warning", "code": "NO_ACTIVE_SPEECH"})
    await anext(service.run_tts("new", new))
    assert sent[-1] == {"type": "Speak", "text": "new"}
    assert service._audio_contexts[new].empty()


async def test_locked_sdk_pipeline_replacement_waits_for_wire_boundary():
    """Exercise SDK interruption/aggregation queues, replacing only network transport."""
    from pipecat.frames.frames import (
        InterruptionFrame,
        LLMFullResponseEndFrame,
        LLMFullResponseStartFrame,
        LLMTextFrame,
        StartFrame,
        TTSAudioRawFrame,
    )
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.worker import PipelineWorker
    from pipecat.processors.frame_processor import FrameProcessor
    from pipecat.workers.runner import WorkerRunner

    service, owner, _, sent = setup_service()
    old = owner.current
    ready, first_speak, interrupted, second_speak, fresh_audio = (asyncio.Event() for _ in range(5))
    received = []

    async def connect():
        pass

    async def send(message):
        sent.append(message)
        if message["type"] == "Interrupt":
            interrupted.set()
        elif message["type"] == "Speak":
            (first_speak if "old" in message["text"] else second_speak).set()

    service._connect = connect
    service._disconnect = connect
    service._transport_send_json = send

    class Sink(FrameProcessor):
        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)
            if isinstance(frame, StartFrame):
                ready.set()
            if isinstance(frame, TTSAudioRawFrame):
                received.append(frame)
                if frame.audio == b"\x02\x00" * 240:
                    fresh_audio.set()
            await self.push_frame(frame, direction)

    worker = PipelineWorker(Pipeline([service, Sink()]), enable_rtvi=False)
    running = asyncio.create_task(WorkerRunner(handle_sigint=False).run(worker))

    async def enqueue(version, text):
        frames = [LLMFullResponseStartFrame(), LLMTextFrame(text), LLMFullResponseEndFrame()]
        for frame in frames:
            frame.metadata["td_response_id"] = version.response_id
        await worker.queue_frames(frames)

    try:
        await asyncio.wait_for(ready.wait(), 2)
        await enqueue(old, "old.")
        await asyncio.wait_for(first_speak.wait(), 2)
        owner.finalize(turn_id="t", source_ids=((0, "s"),), revision=2, text="new")
        await worker.queue_frame(InterruptionFrame())
        await asyncio.wait_for(interrupted.wait(), 2)
        await enqueue(owner.current, "new.")
        for _ in range(100):
            if service._turn_context_id:
                break
            await asyncio.sleep(0.001)
        assert service._turn_context_id
        assert not second_speak.is_set()
        await service._handle_audio(b"\x09\x00" * 240)
        await service._handle_message({"type": "SpeechMetadata", "speech_id": "old"})
        await service._handle_message({"type": "SpeechInterrupted"})
        await asyncio.wait_for(second_speak.wait(), 2)
        await service._handle_audio(b"\x02\x00" * 240)
        await service._handle_message({"type": "SpeechMetadata", "speech_id": "new"})
        await asyncio.wait_for(fresh_audio.wait(), 2)
        assert all(frame.audio != b"\x09\x00" * 240 for frame in received)
        assert received[-1].metadata["td_response_id"] == owner.current.response_id
    finally:
        await worker.cancel()
        await asyncio.wait_for(running, 2)


async def test_interrupt_hook_does_not_block_local_stop_on_wire_backpressure():
    """The SDK forwards local interruption only after this provider hook returns."""
    service, _, old, _ = setup_service()
    blocked = asyncio.Event()

    async def send(message):
        await blocked.wait()

    service._transport_send_json = send
    try:
        await asyncio.wait_for(service.on_audio_context_interrupted(old), 0.02)
        assert not service._interrupt_ready.is_set()
    finally:
        blocked.set()
        task = getattr(service, "_interrupt_sender", None)
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


async def test_cleanup_joins_previous_sender_even_if_ack_arrives_before_drain():
    service, _, old, _ = setup_service()
    started = asyncio.Event()
    blocked = asyncio.Event()

    async def send(message):
        started.set()
        await blocked.wait()

    service._transport_send_json = send
    await service.on_audio_context_interrupted(old)
    first = service._interrupt_sender
    try:
        await asyncio.wait_for(started.wait(), 1)
        await service._handle_message({"type": "SpeechInterrupted"})
        await service.on_audio_context_interrupted("next-context")
        second = service._interrupt_sender
        assert first is not second
        await service._cancel_interrupt_sender()
        assert first.done() and second.done()
    finally:
        first.cancel()
        await asyncio.gather(first, return_exceptions=True)
        await service._cancel_interrupt_sender()


async def test_old_send_failure_cannot_poison_new_interrupt_generation():
    service, _, old, _ = setup_service()
    started, release, second_sent = (asyncio.Event() for _ in range(3))
    count = 0

    async def send(message):
        nonlocal count
        count += 1
        if count == 1:
            started.set()
            await release.wait()
            raise OSError("inert old send failure")
        second_sent.set()

    service._transport_send_json = send
    await service.on_audio_context_interrupted(old)
    first = service._interrupt_sender
    try:
        await asyncio.wait_for(started.wait(), 1)
        await service._handle_message({"type": "SpeechInterrupted"})
        await service.on_audio_context_interrupted("next-context")
        await asyncio.wait_for(second_sent.wait(), 1)
        release.set()
        await asyncio.wait_for(first, 1)
        assert service._interrupt_error is None
        assert not service._interrupt_ready.is_set()
    finally:
        release.set()
        await service._cancel_interrupt_sender()
