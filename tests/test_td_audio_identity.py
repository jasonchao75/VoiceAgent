"""P11: provider audio identity must survive locked transport rechunking/protobuf."""

from importlib import import_module, util

from pipecat.frames.protobufs import frames_pb2


def protocol():
    assert util.find_spec("src.pipeline.audio_identity") is not None, "Audio task identity absent"
    return import_module("src.pipeline.audio_identity")


async def test_task_identity_survives_transport_style_reconstruction_and_protobuf():
    module = protocol()
    cls = module.audio_frame_type(playback_id="task-a", kind="normal", response_id="turn:1")
    original = cls(b"\x01\x00" * 24, 24000, 1)
    # Locked BaseOutputTransport recreates type(frame), discarding instance metadata/context_id.
    reconstructed = type(original)(original.audio, 24000, 1)
    data = await module.TaskProtobufSerializer().serialize(reconstructed)
    parsed = frames_pb2.Frame.FromString(data)
    assert parsed.audio.audio == original.audio
    identity = module.decode_audio_identity(parsed.audio.name)
    assert identity == {"playback_id": "task-a", "kind": "normal", "response_id": "turn:1"}
    assert reconstructed.metadata == {}


def test_distinct_audio_types_do_not_share_mutable_task_identity():
    module = protocol()
    first = module.audio_frame_type(playback_id="first", kind="echo", response_id=None)
    second = module.audio_frame_type(playback_id="second", kind="normal", response_id="turn:2")
    assert module.decode_audio_identity(first(b"\x00\x00", 24000, 1).name)["playback_id"] == "first"
    assert (
        module.decode_audio_identity(second(b"\x00\x00", 24000, 1).name)["playback_id"] == "second"
    )
    assert module.decode_audio_identity("ordinary SDK frame") is None


async def test_actual_native_output_rechunks_and_flushes_each_task_without_relabeling():
    """Use the actual transport sender/resampler queues, not a handcrafted metadata copy."""
    import asyncio

    from pipecat.frames.frames import StartFrame, TTSStoppedFrame
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.worker import PipelineParams, PipelineWorker
    from pipecat.processors.frame_processor import FrameProcessor
    from pipecat.transports.base_output import BaseOutputTransport
    from pipecat.transports.base_transport import TransportParams
    from pipecat.workers.runner import WorkerRunner

    module = protocol()
    ready, complete = asyncio.Event(), asyncio.Event()
    packets = []

    class Output(BaseOutputTransport):
        async def start(self, frame):
            await super().start(frame)
            await self.set_transport_ready(frame)

        async def write_audio_frame(self, frame):
            if isinstance(frame, module.TaskAudioFrame):
                packets.append(await module.TaskProtobufSerializer().serialize(frame))
                if len(packets) == 2:
                    complete.set()
            return True

    class Sink(FrameProcessor):
        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)
            if isinstance(frame, StartFrame):
                ready.set()
            await self.push_frame(frame, direction)

    output = Output(TransportParams(audio_out_enabled=True, audio_out_sample_rate=24000))
    worker = PipelineWorker(
        Pipeline([output, Sink()]), params=PipelineParams(audio_out_sample_rate=24000)
    )
    runner = WorkerRunner(handle_sigint=False)
    await runner.add_workers(worker)
    running = asyncio.create_task(runner.run())
    try:
        await asyncio.wait_for(ready.wait(), 2)
        for index, task in enumerate(["first", "second"], 1):
            cls = module.audio_frame_type(
                playback_id=task, kind="normal", response_id=f"turn:{index}"
            )
            await worker.queue_frame(cls(bytes([index, 0]) * 24, 24000, 1))
            await worker.queue_frame(TTSStoppedFrame())
        await asyncio.wait_for(complete.wait(), 3)
        frames = [frames_pb2.Frame.FromString(data).audio for data in packets]
        assert [module.decode_audio_identity(frame.name)["playback_id"] for frame in frames] == [
            "first",
            "second",
        ]
        for index, frame in enumerate(frames, 1):
            assert frame.audio[:48] == bytes([index, 0]) * 24
            assert all(value == 0 for value in frame.audio[48:])
    finally:
        await worker.cancel()
        await asyncio.wait_for(running, 3)


async def test_formal_tagger_emits_one_stable_identity_and_ordered_end_marker():
    import asyncio

    from pipecat.frames.frames import (
        OutputTransportMessageFrame,
        StartFrame,
        TTSAudioRawFrame,
        TTSStartedFrame,
        TTSStoppedFrame,
    )
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.worker import PipelineWorker
    from pipecat.processors.frame_processor import FrameProcessor
    from pipecat.workers.runner import WorkerRunner

    module = protocol()
    assert hasattr(module, "AudioTaskTagger"), "Formal output task tagger absent"
    ready, ended = asyncio.Event(), asyncio.Event()
    emitted, evidence = [], []

    class Sink(FrameProcessor):
        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)
            if isinstance(frame, StartFrame):
                ready.set()
            if isinstance(frame, module.TaskAudioFrame):
                emitted.append(frame)
            if isinstance(frame, OutputTransportMessageFrame):
                emitted.append(frame)
                ended.set()
            await self.push_frame(frame, direction)

    tagger = module.AudioTaskTagger(evidence.append)
    worker = PipelineWorker(Pipeline([tagger, Sink()]))
    runner = WorkerRunner(handle_sigint=False)
    await runner.add_workers(worker)
    running = asyncio.create_task(runner.run())
    try:
        await asyncio.wait_for(ready.wait(), 2)
        for _ in range(2):
            frame = TTSAudioRawFrame(b"\x01\x00" * 24, 24000, 1, context_id="provider-context")
            frame.metadata["td_response_id"] = "1:2"
            await worker.queue_frame(frame)
        await worker.queue_frame(TTSStoppedFrame(context_id="provider-context"))
        await asyncio.wait_for(ended.wait(), 2)
        assert len(emitted) == 3
        identities = [module.decode_audio_identity(frame.name) for frame in emitted[:2]]
        assert identities[0] == identities[1] and identities[0]["response_id"] == "1:2"
        assert emitted[2].message["playback_id"] == identities[0]["playback_id"]
        assert emitted[2].message["event"] == "task_end"
        assert len(evidence) == 1 and evidence[0]["event"] == "playback_task_prepared"
        ended.clear()
        await worker.queue_frame(TTSStartedFrame(context_id="provider-context"))
        following = TTSAudioRawFrame(b"\x02\x00" * 24, 24000, 1, context_id="provider-context")
        following.metadata["td_response_id"] = "1:2"
        await worker.queue_frame(following)
        await worker.queue_frame(TTSStoppedFrame(context_id="provider-context"))
        await asyncio.wait_for(ended.wait(), 2)
        assert len(emitted) == 5
        assert (
            module.decode_audio_identity(emitted[3].name)["playback_id"]
            != identities[0]["playback_id"]
        )
        assert len(evidence) == 2
        assert len(tagger._issued) == 2
        tagger.acknowledge(identities[0]["playback_id"], "task_finished")
        assert len(tagger._issued) == 1
    finally:
        await worker.cancel()
        await asyncio.wait_for(running, 3)


async def test_native_writer_repack_keeps_concurrent_task_identity_and_resets_plain_audio():
    """The final native writer rebuilds OutputAudioRawFrame after its sender has rechunked."""
    import asyncio

    from pipecat.frames.frames import OutputAudioRawFrame
    from pipecat.frames.protobufs import frames_pb2

    from src.pipeline.audio_identity import (
        TaskProtobufSerializer,
        audio_frame_type,
        decode_audio_identity,
    )

    serializer = TaskProtobufSerializer()
    arrived, release = asyncio.Event(), asyncio.Event()
    payloads = []

    class NativeWriter:
        async def write_audio_frame(self, frame):
            arrived.set()
            await release.wait()
            # Match the locked final writer's fresh-frame boundary, not a type(frame) copy.
            copy = OutputAudioRawFrame(frame.audio, frame.sample_rate, frame.num_channels)
            payloads.append(await serializer.serialize(copy))
            return True

    writer = NativeWriter()
    serializer.bind_output(writer)
    a = audio_frame_type(playback_id="a", kind="echo", response_id=None)
    b = audio_frame_type(playback_id="b", kind="normal", response_id="turn:1")
    first = asyncio.create_task(writer.write_audio_frame(a(b"\x01\x00", 24000, 1)))
    await arrived.wait()
    second = asyncio.create_task(writer.write_audio_frame(b(b"\x02\x00", 24000, 1)))
    release.set()
    await asyncio.gather(first, second)
    await writer.write_audio_frame(OutputAudioRawFrame(b"\x03\x00", 24000, 1))
    decoded = [frames_pb2.Frame.FromString(payload).audio for payload in payloads]
    identities = {frame.audio[0]: decode_audio_identity(frame.name) for frame in decoded}
    assert identities[1]["playback_id"] == "a"
    assert identities[2]["playback_id"] == "b"
    assert identities[3] is None
