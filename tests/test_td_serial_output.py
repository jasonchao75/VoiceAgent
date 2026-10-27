"""Serial output holds a single sent task until matching real client acknowledgement."""

import asyncio
from importlib import import_module, util

from pipecat.frames.frames import OutputTransportMessageFrame, StartFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineWorker
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.workers.runner import WorkerRunner

from src.pipeline.audio_identity import TaskAudioFrame, audio_frame_type
from src.pipeline.response_revision import ResponseRevisions


async def test_serial_frames_wait_for_client_finish_and_ignore_foreign_receipt():
    assert util.find_spec("src.pipeline.serial_output") is not None, "Serial output adapter absent"
    module = import_module("src.pipeline.serial_output")
    owner = ResponseRevisions()
    output = module.SerialAudioOutput(responses=owner)
    ready, first, second = asyncio.Event(), asyncio.Event(), asyncio.Event()
    ids = []

    class Sink(FrameProcessor):
        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)
            if isinstance(frame, StartFrame):
                ready.set()
            if isinstance(frame, TaskAudioFrame):
                ids.append(frame.task_identity["playback_id"])
                (first if ids[-1] == "first" else second).set()
            await self.push_frame(frame, direction)

    worker = PipelineWorker(Pipeline([output, Sink()]))
    runner = WorkerRunner(handle_sigint=False)
    await runner.add_workers(worker)
    running = asyncio.create_task(runner.run())
    try:
        await asyncio.wait_for(ready.wait(), 2)
        for identity in ["first", "second"]:
            cls = audio_frame_type(playback_id=identity, kind="normal", response_id=None)
            await worker.queue_frame(cls(b"\x01\x00" * 240, 24000, 1))
            await worker.queue_frame(
                OutputTransportMessageFrame(
                    message={
                        "label": "voice-agent-playback",
                        "event": "task_end",
                        "playback_id": identity,
                    }
                )
            )
        await asyncio.wait_for(first.wait(), 2)
        assert ids == ["first"]
        assert output.arbiter.tasks["first"].status == "sent_unknown"
        output.receipt("foreign", "task_finished")
        assert not second.is_set()
        output.receipt("first", "task_started")
        assert not second.is_set()
        output.receipt("first", "task_finished")
        await asyncio.wait_for(second.wait(), 2)
        assert ids == ["first", "second"]
        assert output.arbiter.tasks["first"].started
    finally:
        await worker.cancel()
        await asyncio.wait_for(running, 3)


async def test_cached_echo_clear_waits_for_actual_stop_before_ordinary_response(tmp_path):
    """Exercise real SDK queues, cache PCM and receipt validation without a provider/network."""
    from pipecat.frames.frames import InterruptionFrame

    from src.config import TTSConfig
    from src.history.capture import CallCapture
    from src.pipeline.echo_audio import EchoAudio
    from src.pipeline.identifier_output import IdentifierOutput
    from src.pipeline.serial_output import SerialAudioOutput
    from src.tts.echo_cache import EchoAudioCache
    from tests.test_td_identifier_output import view
    from tests.test_td_identifier_rules import policy

    rules = policy()
    capture = CallCapture(provider="fixture", model="fixture")
    output = SerialAudioOutput(responses=ResponseRevisions(), evidence_sink=capture.record_td_event)
    cache = EchoAudioCache(tmp_path / "cache")
    config = TTSConfig(voice="fixture")
    calls = []

    async def synthesize(unit, config, rate, *, timeout):
        calls.append(unit)
        return b"\x01\x00" * 240

    await cache.prepare("bot", ["1", "2"], config, 24000, synthesize, timeout=2)
    calls.clear()
    echo = IdentifierOutput(
        collection=rules.collection,
        audio=EchoAudio(
            cache=cache,
            bot_id="bot",
            collection=rules.collection,
            config=config,
            sample_rate=24000,
            gap_ms=0,
            manifest={},
            synthesize=synthesize,
            record=lambda event, **fields: capture.record_td_event({"event": event, **fields}),
        ),
        output=output,
        evidence_sink=capture.record_td_event,
    )
    capture.playback_listener = output.receipt
    ready = asyncio.Event()
    frames = asyncio.Queue()
    controls = asyncio.Queue()

    class Sink(FrameProcessor):
        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)
            if isinstance(frame, StartFrame):
                ready.set()
            if isinstance(frame, TaskAudioFrame):
                frames.put_nowait(frame)
            if getattr(frame, "message", {}).get("label") == "voice-agent-playback":
                controls.put_nowait(frame.message)
            await self.push_frame(frame, direction)

    worker = PipelineWorker(Pipeline([output, Sink()]), enable_rtvi=False)
    runner = WorkerRunner(handle_sigint=False)
    await runner.add_workers(worker)
    running = asyncio.create_task(runner.run())
    try:
        await asyncio.wait_for(ready.wait(), 2)
        initial = view("12")
        echo.consider(initial, rules.evaluate(initial, "编号"), 7)
        await echo.wait_pending()
        first = await asyncio.wait_for(frames.get(), 2)
        identity = first.task_identity["playback_id"]
        assert first.task_identity["kind"] == "echo"
        assert (await asyncio.wait_for(frames.get(), 2)).task_identity["playback_id"] == identity
        end = await asyncio.wait_for(controls.get(), 2)
        assert end["event"] == "task_end"
        assert capture.playback_receipt(identity, "task_started", 240, 10)
        # Continuation preserves active identifier audio.
        await worker.queue_frame(InterruptionFrame())
        assert output.arbiter.tasks[identity].status == "playing"
        rules.collection.clear_tool(rules.collection.bind_source(0, "clear", 1, "clear"))
        stop = await asyncio.wait_for(controls.get(), 2)
        assert stop["event"] == "stop_task" and stop["playback_id"] == identity
        cls = audio_frame_type(playback_id="reply", kind="normal", response_id=None)
        await worker.queue_frame(cls(b"\x02\x00" * 240, 24000, 1))
        await worker.queue_frame(
            OutputTransportMessageFrame(
                message={
                    "label": "voice-agent-playback",
                    "event": "task_end",
                    "playback_id": "reply",
                }
            )
        )
        assert not capture.playback_receipt("reply", "task_finished", 240, 20)
        assert frames.empty()
        assert capture.playback_receipt(identity, "task_stopped", 480, 30)
        fresh = await asyncio.wait_for(frames.get(), 2)
        assert fresh.task_identity["playback_id"] == "reply"
        assert output.arbiter.tasks[identity].status == "stopped"
        receipt = [e for e in capture.td_events if e["event"] == "playback_renderer_receipt"][-1]
        assert receipt["turn_id"] == 7
        assert calls == []
    finally:
        await echo.close()
        await worker.cancel()
        await asyncio.wait_for(running, 3)
        await cache.close()


async def test_source_failure_after_pcm_requests_actual_stop_instead_of_success_end():
    """D-074 skips the remaining failed echo but preserves unknown render facts."""
    from src.pipeline.serial_output import SerialAudioOutput

    output = SerialAudioOutput(responses=ResponseRevisions())
    ready, first, terminal, second = (asyncio.Event() for _ in range(4))
    controls = []

    class Sink(FrameProcessor):
        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)
            if isinstance(frame, StartFrame):
                ready.set()
            if isinstance(frame, TaskAudioFrame):
                (first if frame.task_identity["playback_id"] == "failed" else second).set()
            message = getattr(frame, "message", {})
            if message.get("playback_id") == "failed":
                controls.append(message)
                terminal.set()
            await self.push_frame(frame, direction)

    async def source():
        yield b"\x01\x00" * 240
        await first.wait()
        raise ValueError("inert source unavailable")

    worker = PipelineWorker(Pipeline([output, Sink()]))
    runner = WorkerRunner(handle_sigint=False)
    await runner.add_workers(worker)
    running = asyncio.create_task(runner.run())
    try:
        await asyncio.wait_for(ready.wait(), 2)
        await output.stream_audio(
            playback_id="failed",
            kind="echo",
            generation=0,
            source_id="range",
            revision=1,
            source_order=1,
            samples=source(),
            valid=lambda: True,
        )
        await asyncio.wait_for(terminal.wait(), 2)
        assert controls[0]["event"] == "stop_task"
        assert not any(item["event"] == "task_end" for item in controls)
        assert output.arbiter.tasks["failed"].status == "stop_requested"
        cls = audio_frame_type(playback_id="next", kind="normal", response_id=None)
        await worker.queue_frame(cls(b"\x02\x00" * 240, 24000, 1))
        await asyncio.sleep(0)
        assert not second.is_set()
        assert output.receipt("failed", "task_stopped")
        await asyncio.wait_for(second.wait(), 2)
        assert not output.arbiter.tasks["failed"].started
    finally:
        await worker.cancel()
        await asyncio.wait_for(running, 3)


async def test_unconfirmed_stop_fails_boundedly_without_releasing_the_next_response():
    """A missing renderer receipt must not hold the call silently or authorize overlap."""
    from src.pipeline.serial_output import SerialAudioOutput

    events, errors, ids = [], [], []
    output = SerialAudioOutput(
        responses=ResponseRevisions(), evidence_sink=events.append, stop_confirmation_timeout=0.03
    )
    ready, first, failed = (asyncio.Event() for _ in range(3))

    async def fail(**kwargs):
        errors.append(kwargs)
        failed.set()

    output.push_error = fail

    class Sink(FrameProcessor):
        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)
            if isinstance(frame, StartFrame):
                ready.set()
            if isinstance(frame, TaskAudioFrame):
                ids.append(frame.task_identity["playback_id"])
                first.set()
            await self.push_frame(frame, direction)

    worker = PipelineWorker(Pipeline([output, Sink()]))
    runner = WorkerRunner(handle_sigint=False)
    await runner.add_workers(worker)
    running = asyncio.create_task(runner.run())
    try:
        await asyncio.wait_for(ready.wait(), 2)
        cls = audio_frame_type(playback_id="old", kind="normal", response_id=None)
        await worker.queue_frame(cls(b"\x01\x00" * 240, 24000, 1))
        await asyncio.wait_for(first.wait(), 2)
        await worker.queue_frame(
            OutputTransportMessageFrame(
                message={
                    "label": "voice-agent-playback",
                    "event": "stop_task",
                    "playback_id": "old",
                }
            )
        )
        cls = audio_frame_type(playback_id="new-final", kind="normal", response_id=None)
        await worker.queue_frame(cls(b"\x01\x00" * 240, 24000, 1))
        await asyncio.wait_for(failed.wait(), 0.5)
        assert ids == ["old"]
        assert errors[0]["force_treat_as_permanent"] is True
        assert any(e["event"] == "playback_stop_unconfirmed" for e in events)
        assert output.arbiter.tasks["old"].status == "stop_requested"
        assert not output.arbiter.tasks["old"].started
    finally:
        await worker.cancel()
        await asyncio.wait_for(running, 3)
    assert not output._stop_guards
