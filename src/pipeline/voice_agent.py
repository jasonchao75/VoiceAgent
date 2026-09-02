"""Pipecat orchestration for one browser Voice Agent session."""

from __future__ import annotations

import asyncio
import logging

from fastapi import WebSocket
from pipecat.frames.frames import TTSSpeakFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker, ProcessorUnusablePolicy
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.serializers.protobuf import ProtobufFrameSerializer
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)
from pipecat.workers.runner import WorkerRunner

from src.asr import create_flux_stt
from src.config import RuntimeConfig
from src.llm import create_openai_compatible_llm
from src.observability import SessionEventBuffer, SessionTimingObserver
from src.session import SessionLease
from src.tts import TTSProviderRegistry

logger = logging.getLogger(__name__)


async def run_voice_agent_session(
    *,
    websocket: WebSocket,
    lease: SessionLease,
    runtime: RuntimeConfig,
    tts_registry: TTSProviderRegistry,
    allowed_origins: list[str],
    event_buffer: SessionEventBuffer,
) -> None:
    """Run a complete Browser → Flux STT → LLM → Flux TTS session.

    Args:
        websocket: Accepted browser WebSocket.
        lease: Single-use session lease containing BYOK credentials.
        runtime: Validated server runtime configuration.
        tts_registry: Provider registry used outside orchestration logic.
        allowed_origins: Origins accepted by the transport.
        event_buffer: Non-secret timing buffer for UI telemetry.
    """
    deepgram_key = lease.credentials.deepgram_api_key.get_secret_value()
    llm_key = lease.credentials.llm_api_key.get_secret_value()

    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            audio_in_sample_rate=runtime.audio.input_sample_rate,
            audio_out_sample_rate=runtime.audio.output_sample_rate,
            audio_in_channels=runtime.audio.channels,
            audio_out_channels=runtime.audio.channels,
            add_wav_header=False,
            serializer=ProtobufFrameSerializer(),
            session_timeout=runtime.session.max_duration_seconds,
            allowed_origins=allowed_origins,
            audio_out_write_timeout_secs=10.0,
            ws_close_timeout=1.0,
        ),
    )
    stt = create_flux_stt(
        api_key=deepgram_key,
        config=runtime.asr,
        audio=runtime.audio,
    )
    llm = create_openai_compatible_llm(
        api_key=llm_key,
        config=lease.config.llm,
        system_prompt=lease.config.system_prompt,
    )
    tts = tts_registry.create(
        provider=lease.config.tts.provider,
        api_key=deepgram_key,
        config=lease.config.tts,
        audio=runtime.audio,
    )

    context = LLMContext()
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(context)
    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            user_aggregator,
            llm,
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )
    observer = SessionTimingObserver(session_id=lease.session_id, event_sink=event_buffer.add)
    worker = PipelineWorker(
        pipeline,
        name=f"voice-session-{lease.session_id}",
        conversation_id=lease.session_id,
        idle_timeout_secs=runtime.session.idle_timeout_seconds,
        cancel_on_idle_timeout=True,
        cancel_runner_on_idle_timeout=True,
        processor_unusable_policy=ProcessorUnusablePolicy.CANCEL,
        observers=[observer],
        params=PipelineParams(
            audio_in_sample_rate=runtime.audio.input_sample_rate,
            audio_out_sample_rate=runtime.audio.output_sample_rate,
            enable_metrics=True,
            enable_usage_metrics=True,
            report_only_initial_ttfb=False,
            start_metadata={"session_id": lease.session_id},
        ),
    )

    @worker.rtvi.event_handler("on_client_ready")
    async def on_client_ready(_rtvi: object) -> None:
        """Speak the fixed opening without asking the LLM to rewrite it."""
        if not lease.config.opening_script:
            return
        context.add_message({"role": "assistant", "content": lease.config.opening_script})
        await worker.queue_frames([TTSSpeakFrame(lease.config.opening_script)])

    @transport.event_handler("on_client_connected")
    async def on_client_connected(_transport: object, _client: object) -> None:
        """Record only a non-secret connection event."""
        logger.info("session_connected session_id=%s", lease.session_id)

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(_transport: object, _client: object) -> None:
        """Cancel in-flight LLM/TTS work when the browser leaves."""
        logger.info("session_disconnected session_id=%s", lease.session_id)
        await worker.cancel()

    runner = WorkerRunner(handle_sigint=False, handle_sigterm=False)
    await runner.add_workers(worker)
    try:
        async with asyncio.timeout(runtime.session.max_duration_seconds + 5):
            await runner.run()
    except TimeoutError:
        logger.info("session_timeout session_id=%s", lease.session_id)
        await worker.cancel()
