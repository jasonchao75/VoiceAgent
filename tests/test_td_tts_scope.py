"""D-049 provider context IDs must keep the original response identity."""

from importlib import import_module, util

from pipecat.frames.frames import LLMFullResponseStartFrame, TTSAudioRawFrame
from pipecat.processors.frame_processor import FrameDirection

from src.pipeline.response_revision import ResponseRevisions


def service(owner):
    """Use a deterministic provider base; no socket or credentials."""
    assert util.find_spec("src.tts.response_scope") is not None, "TTS response scope absent"

    class Provider:
        def __init__(self, **kwargs):
            self.sent = []
            self.queued = []
            self._turn_context_id = None
            self._tts_contexts = {}
            self.counter = 0

        async def process_frame(self, frame, direction):
            if isinstance(frame, LLMFullResponseStartFrame):
                self._turn_context_id = self.create_context_id()

        def create_context_id(self):
            self.counter += 1
            return str(self.counter)

        async def push_frame(self, frame, direction):
            self.sent.append(frame)

        async def append_to_audio_context(self, context_id, frame):
            self.queued.append((context_id, frame))

    mixin = import_module("src.tts.response_scope").ResponseScopedTTSMixin
    return type("ScopedFixture", (mixin, Provider), {})(response_owner=owner)


async def test_old_audio_keeps_old_identity_after_final_replaces_partial():
    owner = ResponseRevisions()
    old = owner.submit(turn_id="t", source_ids=((0, "a"),), text="one", final=False)
    tts = service(owner)
    start = LLMFullResponseStartFrame()
    start.metadata["td_response_id"] = old.response_id
    await tts.process_frame(start, FrameDirection.DOWNSTREAM)
    old_context = tts._turn_context_id
    owner.finalize(turn_id="t", source_ids=((0, "a"),), revision=2, text="two")
    fresh = LLMFullResponseStartFrame()
    fresh.metadata["td_response_id"] = owner.current.response_id
    await tts.process_frame(fresh, FrameDirection.DOWNSTREAM)
    new_context = tts._turn_context_id
    assert old_context != new_context
    late = TTSAudioRawFrame(b"\x01\x00", 24000, 1, context_id=old_context)
    current = TTSAudioRawFrame(b"\x02\x00", 24000, 1, context_id=new_context)
    await tts.append_to_audio_context(old_context, late)
    await tts.push_frame(late)
    await tts.push_frame(current)
    assert tts.queued == []
    assert tts.sent == [current]
    assert current.metadata["td_response_id"] == owner.current.response_id


async def test_new_speech_fences_queued_audio_and_unknown_context_fails_closed():
    owner = ResponseRevisions()
    version = owner.submit(turn_id="t", source_ids=((0, "a"),), text="one", final=False)
    tts = service(owner)
    start = LLMFullResponseStartFrame()
    start.metadata["td_response_id"] = version.response_id
    await tts.process_frame(start, FrameDirection.DOWNSTREAM)
    owner.begin_speech()
    await tts.push_frame(TTSAudioRawFrame(b"\x01\x00", 24000, 1, context_id=tts._turn_context_id))
    await tts.push_frame(TTSAudioRawFrame(b"\x01\x00", 24000, 1, context_id="unknown"))
    assert tts.sent == []


async def test_unbound_background_context_is_never_treated_as_opening_audio():
    owner = ResponseRevisions()
    tts = service(owner)
    unknown = tts.create_context_id()
    await tts.push_frame(TTSAudioRawFrame(b"\x01\x00", 24000, 1, context_id=unknown))
    assert tts.sent == []


async def test_actual_sdk_pipeline_fences_late_provider_audio_and_keeps_opening():
    """Run the locked SDK queues/aggregation and replace only the external synth generator."""
    import asyncio

    from pipecat.frames.frames import (
        InterruptionFrame,
        LLMFullResponseEndFrame,
        LLMTextFrame,
        StartFrame,
        TTSSpeakFrame,
        TTSStoppedFrame,
    )
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.worker import PipelineParams, PipelineWorker
    from pipecat.processors.frame_processor import FrameProcessor
    from pipecat.services.tts_service import TextAggregationMode, TTSService
    from pipecat.workers.runner import WorkerRunner

    from src.tts.response_scope import ResponseScopedTTSMixin

    owner = ResponseRevisions()
    ready, opening, first_sent, released, fresh_audio = (asyncio.Event() for _ in range(5))
    audio = []
    jobs = []

    class Synth(ResponseScopedTTSMixin, TTSService):
        async def run_tts(self, text, context_id):
            if "old" in text:

                async def late():
                    first_sent.set()
                    await released.wait()
                    await self.append_to_audio_context(
                        context_id,
                        TTSAudioRawFrame(b"\x09\x00" * 240, 24000, 1, context_id=context_id),
                    )

                jobs.append(asyncio.create_task(late()))
                yield None
            else:
                yield TTSAudioRawFrame(b"\x02\x00" * 240, 24000, 1, context_id=context_id)
                yield TTSStoppedFrame(context_id=context_id)

    class Sink(FrameProcessor):
        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)
            if isinstance(frame, StartFrame):
                ready.set()
            if isinstance(frame, TTSAudioRawFrame):
                audio.append(frame)
                if frame.metadata.get("td_response_id"):
                    fresh_audio.set()
                else:
                    opening.set()
            await self.push_frame(frame, direction)

    synth = Synth(
        response_owner=owner, sample_rate=24000, text_aggregation_mode=TextAggregationMode.SENTENCE
    )
    worker = PipelineWorker(
        Pipeline([synth, Sink()]), params=PipelineParams(audio_out_sample_rate=24000)
    )
    worker_runner = WorkerRunner(handle_sigint=False)
    await worker_runner.add_workers(worker)
    runner = asyncio.create_task(worker_runner.run())
    try:
        await asyncio.wait_for(ready.wait(), 2)
        await worker.queue_frame(TTSSpeakFrame("welcome"))
        await asyncio.wait_for(opening.wait(), 2)
        original = owner.submit(turn_id="t", source_ids=((0, "a"),), text="old", final=False)
        frames = [LLMFullResponseStartFrame(), LLMTextFrame("old."), LLMFullResponseEndFrame()]
        for frame in frames:
            frame.metadata["td_response_id"] = original.response_id
            await worker.queue_frame(frame)
        await asyncio.wait_for(first_sent.wait(), 2)
        owner.finalize(turn_id="t", source_ids=((0, "a"),), revision=2, text="new")
        await worker.queue_frame(InterruptionFrame())
        frames = [LLMFullResponseStartFrame(), LLMTextFrame("new."), LLMFullResponseEndFrame()]
        for frame in frames:
            frame.metadata["td_response_id"] = owner.current.response_id
            await worker.queue_frame(frame)
        released.set()
        await asyncio.wait_for(fresh_audio.wait(), 4)
        await asyncio.gather(*jobs)
        assert not any(frame.audio.startswith(b"\x09") for frame in audio)
        assert audio[-1].metadata["td_response_id"] == owner.current.response_id
    finally:
        released.set()
        await asyncio.gather(*jobs)
        await worker.cancel()
        await asyncio.wait_for(runner, 3)


async def test_unbound_late_job_cannot_borrow_new_active_turn_context():
    owner = ResponseRevisions()
    version = owner.submit(turn_id="t", source_ids=((0, "a"),), text="new", final=True)
    tts = service(owner)
    start = LLMFullResponseStartFrame()
    start.metadata["td_response_id"] = version.response_id
    await tts.process_frame(start, FrameDirection.DOWNSTREAM)
    unbound = tts.create_context_id()
    await tts.push_frame(TTSAudioRawFrame(b"\x09\x00", 24000, 1, context_id=unbound))
    assert tts.sent == []


async def test_opening_and_reminders_are_bound_to_speech_generation_even_without_llm_response():
    owner = ResponseRevisions()
    tts = service(owner)
    token = tts._tts_response.set(None)
    try:
        context = tts.create_context_id()
    finally:
        tts._tts_response.reset(token)
    owner.begin_speech()
    await tts.push_frame(TTSAudioRawFrame(b"\x01\x00", 24000, 1, context_id=context))
    assert tts.sent == []
