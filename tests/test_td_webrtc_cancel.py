"""Exercise the locked SDK RTP queue without changing media transport."""

import asyncio
from types import SimpleNamespace

import numpy as np
import pytest
from pipecat.transports.smallwebrtc.transport import RawAudioTrack


def adapter():
    """Load the production adapter only after the missing-behavior red test runs."""
    from src.pipeline.webrtc_cancel import clear_pending_rtp_audio

    return clear_pending_rtp_audio


@pytest.mark.asyncio
async def test_cancelled_writer_does_not_leave_old_pcm_in_rtp_track():
    track = RawAudioTrack(sample_rate=24000)
    old = track.add_audio_bytes(np.full(2400, 1234, dtype=np.int16).tobytes())
    old.cancel()
    adapter()(track)
    frame = await track.recv()
    assert not np.any(frame.to_ndarray())
    assert track.readyState == "live"
    track.stop()


@pytest.mark.asyncio
async def test_purge_settles_waiters_and_preserves_new_audio_on_the_same_track():
    track = RawAudioTrack(sample_rate=24000)
    old = track.add_audio_bytes(np.full(480, 1111, dtype=np.int16).tobytes())
    adapter()(track)
    assert old.done() and old.result() is False
    fresh = track.add_audio_bytes(np.full(240, 2222, dtype=np.int16).tobytes())
    frame = await track.recv()
    assert np.all(frame.to_ndarray() == 2222)
    assert await asyncio.wait_for(fresh, 0.1) is True
    track.stop()


def test_unknown_sdk_queue_shape_is_rejected_instead_of_claiming_a_purge():
    with pytest.raises(RuntimeError, match="queue"):
        adapter()(SimpleNamespace(_chunk_queue=[]))


@pytest.mark.asyncio
async def test_native_output_interruption_purges_track_before_next_answer():
    """Use native SDK output queues and clock, replacing only the network client."""
    from pipecat.frames.frames import InterruptionFrame, OutputAudioRawFrame, StartFrame
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.worker import PipelineWorker
    from pipecat.processors.frame_processor import FrameProcessor
    from pipecat.transports.base_transport import TransportParams
    from pipecat.workers.runner import WorkerRunner

    from src.pipeline.webrtc_cancel import CancellableRTPOutput

    ready, old_queued, fresh_rendered = asyncio.Event(), asyncio.Event(), asyncio.Event()
    cleared = asyncio.Event()
    track = RawAudioTrack(sample_rate=24000)
    observed = []

    class Client:
        _audio_output_track = track

        async def setup(self, *args):
            pass

        async def connect(self):
            pass

        async def disconnect(self):
            pass

        async def send_message(self, frame):
            pass

        async def write_audio_frame(self, frame):
            waiter = track.add_audio_bytes(frame.audio)
            old_queued.set()
            await waiter
            return True

    class Sink(FrameProcessor):
        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)
            if isinstance(frame, StartFrame):
                ready.set()
            await self.push_frame(frame, direction)

    class Output(CancellableRTPOutput):
        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)
            if isinstance(frame, InterruptionFrame):
                cleared.set()

    async def receive():
        while True:
            frame = await track.recv()
            value = int(frame.to_ndarray()[0, 0])
            observed.append(value)
            if value == 2222:
                fresh_rendered.set()

    output = Output(Client(), TransportParams(audio_out_enabled=True, audio_out_sample_rate=24000))
    worker = PipelineWorker(Pipeline([output, Sink()]))
    runner = WorkerRunner(handle_sigint=False)
    await runner.add_workers(worker)
    running = asyncio.create_task(runner.run())
    consuming = asyncio.create_task(receive())
    try:
        await asyncio.wait_for(ready.wait(), 2)
        await worker.queue_frame(
            OutputAudioRawFrame(np.full(24000, 1111, dtype=np.int16).tobytes(), 24000, 1)
        )
        await asyncio.wait_for(old_queued.wait(), 2)
        await worker.queue_frame(InterruptionFrame())
        await asyncio.wait_for(cleared.wait(), 0.3)
        assert not track._chunk_queue
        boundary = len(observed)
        await worker.queue_frame(
            OutputAudioRawFrame(np.full(2400, 2222, dtype=np.int16).tobytes(), 24000, 1)
        )
        await asyncio.wait_for(fresh_rendered.wait(), 2)
        assert 1111 not in observed[boundary:]
        assert track.readyState == "live"
    finally:
        consuming.cancel()
        await asyncio.gather(consuming, return_exceptions=True)
        await worker.cancel()
        await asyncio.wait_for(running, 3)
        track.stop()
