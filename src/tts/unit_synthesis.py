"""Bounded fixed-setting unit synthesis through the existing TTS registry and SDK."""

from __future__ import annotations

import asyncio

from pipecat.frames.frames import (
    ErrorFrame,
    Frame,
    StartFrame,
    TTSAudioRawFrame,
    TTSSpeakFrame,
    TTSStoppedFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.services.tts_service import TTSService
from pipecat.workers.runner import WorkerRunner

from src.config import AudioConfig, TTSConfig
from src.tts.factory import TTSProviderRegistry


async def synthesize_unit(
    registry: TTSProviderRegistry,
    api_key: str,
    unit: str,
    config: TTSConfig,
    sample_rate: int,
    *,
    timeout: float,
) -> bytes:
    """Render one configured unit, validating actual PCM before it becomes a persistent asset.

    Args:
        registry: Existing provider registry, injectable without network in tests.
        api_key: Backend-only credential, never returned or placed in metadata.
        unit: One allowed vocabulary output, not arbitrary user speech.
        config: Frozen batch/publication synthesis settings.
        sample_rate: Required output PCM rate.
        timeout: Setup and synthesis deadline; bounded cancellation/cleanup may follow.

    Raises:
        ValueError: If the provider returns empty, oversized or mismatched PCM.
        TimeoutError: If the unit does not complete within the explicit deadline.
    """
    audio = AudioConfig.model_validate({"output_sample_rate": sample_rate})
    fixed = config.model_copy(
        deep=True,
        update={
            "dynamic_speed_enabled": False,
            "text_aggregation": "sentence",
        },
    )
    processor = registry.create(provider=fixed.provider, api_key=api_key, config=fixed, audio=audio)
    if isinstance(processor, TTSService):
        # A standalone unit has no following sentence to separate. Preserve its exact text
        # instead of the pinned SDK's continuous-sentence trailing space and extra billing.
        processor._append_trailing_space = False
    loop = asyncio.get_running_loop()
    result: asyncio.Future[bytes] = loop.create_future()
    ready = asyncio.Event()
    chunks: list[bytes] = []
    length = 0

    class Sink(FrameProcessor):
        """Read actual SDK output; server start signals alone never prove usable audio."""

        async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
            nonlocal length
            await super().process_frame(frame, direction)
            if isinstance(frame, StartFrame):
                ready.set()
            if not result.done():
                if isinstance(frame, TTSAudioRawFrame):
                    if (
                        frame.sample_rate != sample_rate
                        or frame.num_channels != 1
                        or len(frame.audio) % 2
                    ):
                        result.set_exception(ValueError("TTS PCM format mismatch"))
                    else:
                        length += len(frame.audio)
                        if length > sample_rate * 2 * 120:
                            result.set_exception(ValueError("TTS PCM exceeds unit bound"))
                        else:
                            chunks.append(frame.audio)
                elif isinstance(frame, TTSStoppedFrame):
                    if chunks:
                        result.set_result(b"".join(chunks))
                    else:
                        result.set_exception(ValueError("TTS returned empty audio"))
                elif isinstance(frame, ErrorFrame):
                    result.set_exception(ValueError("TTS synthesis failed"))
            await self.push_frame(frame, direction)

    worker = PipelineWorker(
        Pipeline([processor, Sink()]),
        enable_rtvi=False,
        setup_timeout_secs=timeout,
        cancel_timeout_secs=min(timeout, 1),
        params=PipelineParams(audio_out_sample_rate=sample_rate),
    )

    @worker.event_handler("on_pipeline_error")
    async def on_pipeline_error(worker: PipelineWorker, frame: ErrorFrame) -> None:
        """Observe SDK upstream errors without exposing provider details or credentials."""
        if not result.done():
            result.set_exception(ValueError("TTS synthesis failed"))
        # Setup can fail before a downstream StartFrame reaches the sink.
        ready.set()

    runner = WorkerRunner(handle_sigint=False, handle_sigterm=False)
    await runner.add_workers(worker)
    running = asyncio.create_task(runner.run())
    try:
        async with asyncio.timeout(timeout):
            await ready.wait()
            if result.done():
                return await result
            await worker.queue_frames([TTSSpeakFrame(unit, append_to_context=False)])
            return await result
    finally:
        try:
            await asyncio.wait_for(worker.cancel(), timeout=min(timeout, 5))
        except TimeoutError:
            pass
        try:
            await asyncio.wait_for(running, timeout=min(timeout, 5))
        except TimeoutError:
            running.cancel()
            await asyncio.gather(running, return_exceptions=True)
