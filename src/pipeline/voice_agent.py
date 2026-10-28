"""Pipecat orchestration for one browser Voice Agent session."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Literal

from fastapi import WebSocket
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.frames.frames import InterruptionFrame, TTSSpeakFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker, ProcessorUnusablePolicy
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.processors.frame_processor import FrameDirection
from pipecat.serializers.protobuf import ProtobufFrameSerializer
from pipecat.services.llm_service import FunctionCallParams
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)
from pipecat.workers.runner import WorkerRunner

from src.asr import ASRProviderRegistry
from src.config import RuntimeConfig, TTSConfig
from src.history.capture import CallCapture
from src.llm import create_llm_service
from src.observability import SessionEventBuffer, SessionTimingObserver
from src.pipeline.assistant_context import AssistantContextBridge
from src.pipeline.audio_identity import AudioTaskTagger, TaskProtobufSerializer
from src.pipeline.custom_td import prepare_custom_td
from src.pipeline.echo_audio import EchoAudio
from src.pipeline.identifier import IdentifierCollection, IdentifierVocabulary
from src.pipeline.identifier_rules import IdentifierRules
from src.pipeline.identifier_tools import IdentifierTools
from src.pipeline.incremental_identifier_output import IncrementalIdentifierOutput
from src.pipeline.native_output import NativeSerialAudioOutput
from src.pipeline.response_revision import ResponseRevisions
from src.pipeline.response_scope import ResponseScope
from src.pipeline.serial_output import SerialAudioOutput
from src.pipeline.speed_control import SessionSpeedController
from src.pipeline.td_rtvi import TDRTVIProcessor
from src.pipeline.td_strategies import create_custom_aggregators
from src.session import SessionLease
from src.tts import TTSProviderRegistry
from src.tts.echo_cache import EchoAudioCache
from src.tts.unit_synthesis import synthesize_unit

logger = logging.getLogger(__name__)


async def run_voice_agent_session(
    *,
    websocket: WebSocket,
    lease: SessionLease,
    runtime: RuntimeConfig,
    asr_registry: ASRProviderRegistry,
    tts_registry: TTSProviderRegistry,
    allowed_origins: list[str],
    event_buffer: SessionEventBuffer,
    call_capture: CallCapture | None = None,
    echo_cache: EchoAudioCache | None = None,
) -> None:
    """Run one WebSocket-backed browser voice-agent session.

    Args:
        websocket: Accepted browser WebSocket.
        lease: Single-use session lease containing BYOK credentials.
        runtime: Validated server runtime configuration.
        asr_registry: Speech recognition registry used outside orchestration logic.
        tts_registry: Provider registry used outside orchestration logic.
        allowed_origins: Origins accepted by the transport.
        event_buffer: Non-secret timing buffer for UI telemetry.
        call_capture: Optional non-blocking history and recording sink.
    """
    is_chat = lease.session_type == "chat_test"
    serializer = (
        TaskProtobufSerializer()
        if not is_chat and lease.config.asr.turn_detection_source == "self_developed"
        else ProtobufFrameSerializer()
    )
    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=not is_chat,
            audio_out_enabled=True,
            audio_in_sample_rate=runtime.audio.input_sample_rate,
            audio_out_sample_rate=runtime.audio.output_sample_rate,
            audio_in_channels=runtime.audio.channels,
            audio_out_channels=runtime.audio.channels,
            add_wav_header=False,
            serializer=serializer,
            session_timeout=runtime.session.max_duration_seconds,
            allowed_origins=allowed_origins,
            audio_out_write_timeout_secs=10.0,
            ws_close_timeout=1.0,
        ),
    )
    if isinstance(serializer, TaskProtobufSerializer) and hasattr(
        transport.output(), "write_audio_frame"
    ):
        serializer.bind_output(transport.output())
    await run_voice_agent_pipeline(
        transport=transport,
        lease=lease,
        runtime=runtime,
        asr_registry=asr_registry,
        tts_registry=tts_registry,
        event_buffer=event_buffer,
        call_capture=call_capture,
        echo_cache=echo_cache,
        playback_protocol="websocket",
    )


def create_small_webrtc_transport(
    *,
    connection: SmallWebRTCConnection,
    runtime: RuntimeConfig,
    custom_td: bool = False,
    candidate_playback: bool = False,
) -> SmallWebRTCTransport:
    """Create a Small WebRTC transport using the pipeline audio contract.

    Args:
        connection: Negotiated Pipecat peer connection.
        runtime: Validated runtime audio configuration.
        custom_td: Extend native RTP queue cancellation for self-developed TD only.

    Returns:
        A transport that uses the same raw audio contract as WebSocket.
    """
    from src.pipeline.webrtc_cancel import CancellableRTPTransport

    transport_type = CancellableRTPTransport if custom_td else SmallWebRTCTransport
    transport = transport_type(
        webrtc_connection=connection,
        params=TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            audio_in_sample_rate=runtime.audio.input_sample_rate,
            audio_out_sample_rate=runtime.audio.output_sample_rate,
            audio_in_channels=runtime.audio.channels,
            audio_out_channels=runtime.audio.channels,
            audio_out_write_timeout_secs=10.0,
        ),
    )
    if candidate_playback:
        if not custom_td:
            raise ValueError("Candidate playback requires custom TD")
        from src.pipeline.rtp_input import install_candidate_input
        from src.pipeline.rtp_output import install_candidate_transport

        install_candidate_transport(transport, connection)
        install_candidate_input(transport, connection)
    return transport


async def run_voice_agent_pipeline(
    *,
    transport: BaseTransport,
    lease: SessionLease,
    runtime: RuntimeConfig,
    asr_registry: ASRProviderRegistry,
    tts_registry: TTSProviderRegistry,
    event_buffer: SessionEventBuffer,
    call_capture: CallCapture | None = None,
    echo_cache: EchoAudioCache | None = None,
    playback_protocol: Literal["websocket", "webrtc", "webrtc_candidate"] | None = None,
) -> None:
    """Run the shared ASR → LLM → TTS pipeline over an injected transport.

    Args:
        transport: Connected WebSocket or Small WebRTC transport.
        lease: Single-use session lease containing credentials and configuration.
        runtime: Validated server runtime configuration.
        asr_registry: Speech-recognition provider registry.
        tts_registry: Speech-synthesis provider registry.
        event_buffer: Non-secret timing buffer for UI telemetry.
        call_capture: Optional non-blocking history and recording sink.
    """
    asr_key = lease.credentials.asr_api_key.get_secret_value()
    llm_key = lease.credentials.llm_api_key.get_secret_value()
    tts_key = lease.credentials.tts_api_key.get_secret_value()

    is_chat = lease.session_type == "chat_test"
    stt = (
        None
        if is_chat
        else asr_registry.create(
            provider=lease.config.asr.provider,
            model=lease.config.asr.model,
            turn_detection_source=lease.config.asr.turn_detection_source,
            options=lease.config.asr.options,
            api_key=asr_key,
            audio=runtime.audio,
            opening_script=lease.config.opening_script,
        )
    )
    responses = (
        ResponseRevisions()
        if stt is not None and lease.config.asr.turn_detection_source == "self_developed"
        else None
    )
    response_scope = (
        ResponseScope(responses, call_capture.record_td_event if call_capture else None)
        if responses is not None
        else None
    )
    identifier_tools: IdentifierTools | None = None
    identifier_rules: IdentifierRules | None = None
    rule = lease.config.td_config.priority_rule if lease.config.td_config else None
    if response_scope is not None and rule is not None and rule.enabled:
        collection = IdentifierCollection(
            IdentifierVocabulary({row.value: list(row.aliases) for row in rule.vocabulary}),
            target_length=rule.collection.target_length if rule.collection else None,
        )
        identifier_rules = IdentifierRules(rule, collection)
        identifier_tools = IdentifierTools(
            response_scope,
            collection,
            keywords=rule.keywords,
            new_collection_allowed=identifier_rules.can_begin_collection,
        )
        response_scope.enrich_context = identifier_tools.enrich_context
    llm = create_llm_service(
        api_key=llm_key,
        config=lease.config.llm,
        system_prompt=lease.config.system_prompt,
        **({"response_scope": response_scope} if response_scope is not None else {}),
    )
    tts = tts_registry.create(
        provider=lease.config.tts.provider,
        api_key=tts_key,
        config=lease.config.tts,
        audio=runtime.audio,
        **({"response_owner": responses} if responses is not None else {}),
    )

    event_sink = call_capture.record_td_event if call_capture else None
    serial_output = (
        SerialAudioOutput(responses=responses, evidence_sink=event_sink)
        if responses is not None and playback_protocol in {"websocket", "webrtc_candidate"}
        else None
    )
    if responses is not None and playback_protocol == "webrtc":
        native_output = transport.output()

        async def cancel_native_audio() -> None:
            """Finish native transport cancellation before the next direct PCM write."""
            await native_output.process_frame(InterruptionFrame(), FrameDirection.DOWNSTREAM)

        serial_output = NativeSerialAudioOutput(
            responses=responses,
            evidence_sink=event_sink,
            write=native_output.write_audio_frame,
            cancel_audio=cancel_native_audio,
        )
    identifier_output: IncrementalIdentifierOutput | None = None
    if serial_output is not None and identifier_rules is not None:
        if echo_cache is None:
            raise ValueError("Custom identifier output requires the application audio cache")
        assert rule is not None and rule.unit_gap_ms is not None

        async def synthesize_echo(
            unit: str, config: TTSConfig, sample_rate: int, *, timeout: float
        ) -> bytes:
            """Recover only vocabulary units with the session's frozen provider credential."""
            return await synthesize_unit(
                tts_registry, tts_key, unit, config, sample_rate, timeout=timeout
            )

        def record_echo(event: str, **fields: object) -> None:
            """Keep original input/task attribution rather than borrowing the current turn."""
            if event_sink:
                event_sink({"event": event, **fields})

        identifier_output = IncrementalIdentifierOutput(
            collection=identifier_rules.collection,
            audio=EchoAudio(
                cache=echo_cache,
                bot_id=lease.bot_id or "session:" + lease.session_id,
                collection=identifier_rules.collection,
                config=lease.config.tts,
                sample_rate=runtime.audio.output_sample_rate,
                gap_ms=rule.unit_gap_ms,
                manifest={asset.unit: asset.version for asset in rule.assets},
                synthesize=synthesize_echo,
                record=record_echo,
            ),
            output=serial_output,
            evidence_sink=event_sink,
        )

    tools: list[FunctionSchema] = []
    if identifier_tools is not None:
        tools.extend(identifier_tools.schemas())
    if lease.config.tts.dynamic_speed_enabled and lease.config.tts.model != "eleven_v3":
        limits = (0.5, 1.5) if lease.config.tts.provider == "deepgram_flux" else (0.7, 1.2)

        async def apply_speed(target: float) -> None:
            settings_type = type(tts._settings)
            settings = settings_type.from_mapping({"speed": target})
            await asyncio.wait_for(tts._update_settings(settings), timeout=3.0)

        speed_controller = SessionSpeedController(
            configured_speed=lease.config.tts.speed,
            step=lease.config.tts.speed_step,
            minimum=limits[0],
            maximum=limits[1],
            apply_speed=apply_speed,
        )

        async def set_speech_speed(params: FunctionCallParams) -> None:
            async def perform_update() -> dict[str, object]:
                """Return provider truth; the response scope owns replay and stale checks."""
                started = time.monotonic()
                action = params.arguments.get("action")
                if action not in {"faster", "slower", "normal", "configured"}:
                    return {"status": "failed", "reason": "invalid_action"}
                result = await speed_controller.update(action)
                logger.info(
                    "speech_speed_update session_id=%s provider=%s action=%s old=%s "
                    "target=%s status=%s duration_ms=%.1f",
                    lease.session_id,
                    lease.config.tts.provider,
                    action,
                    result.old_speed,
                    result.target_speed,
                    result.status,
                    (time.monotonic() - started) * 1000,
                )
                return {
                    "status": result.status,
                    "old_speed": result.old_speed,
                    "effective_speed": result.effective_speed,
                }

            if response_scope is not None:
                await response_scope.execute(params, perform_update)
            else:
                await params.result_callback(await perform_update())

        tools.append(
            FunctionSchema(
                name="set_speech_speed",
                description=(
                    "Change this agent's speaking speed for the current call when the caller "
                    "explicitly asks. Only confirm a change when status is applied."
                ),
                properties={
                    "action": {
                        "type": "string",
                        "enum": ["faster", "slower", "normal", "configured"],
                    }
                },
                required=["action"],
                handler=set_speech_speed,
            )
        )

    context = LLMContext(tools=[tool for tool in tools]) if tools else LLMContext()
    custom_td = None
    td_input = None
    td_http = None
    if stt is not None and lease.config.asr.turn_detection_source == "self_developed":
        if lease.config.td_config is None or lease.credentials.jev_api_key is None:
            raise ValueError("Custom TD requires explicit settings and a Jev credential")
        td_input, custom_td, td_http = await prepare_custom_td(
            asr=stt,
            settings=lease.config.td_config,
            api_key=lease.credentials.jev_api_key.get_secret_value(),
            evidence_sink=call_capture.record_td_event if call_capture else None,
            responses=responses,
            bind_input=identifier_tools.bind_snapshot if identifier_tools else None,
            identifier_rules=identifier_rules,
            identifier_output=identifier_output.consider if identifier_output else None,
            identifier_observe=identifier_output.observe if identifier_output else None,
        )
        user_aggregator, assistant_aggregator = create_custom_aggregators(
            context, custom_td.authority
        )
    else:
        user_aggregator, assistant_aggregator = LLMContextAggregatorPair(context)
    processors = [transport.input()]
    if td_input is not None:
        processors.append(td_input)
    if stt is not None:
        processors.append(stt.processor)
    if custom_td is not None:
        processors.append(custom_td)
    processors.extend([user_aggregator, llm])
    if stt is not None and (stt.context_updates_enabled or custom_td is not None):

        async def update_assistant_context(text: str) -> None:
            """Keep the semantic snapshot distinct from provider context update transport."""
            if custom_td is not None:
                custom_td.assistant_context(text)
            if stt is not None and stt.context_updates_enabled:
                await stt.update_agent_context(text)

        processors.append(
            AssistantContextBridge(
                update_assistant_context,
                call_capture.record_context_update if call_capture is not None else None,
            )
        )
    processors.append(tts)
    if custom_td is not None:
        audio_tagger = AudioTaskTagger(call_capture.record_td_event if call_capture else None)
        if call_capture is not None:

            def receive_playback(playback_id: str, event: str) -> bool:
                """Validate active serial identity before accepting/retiring a renderer fact."""
                if serial_output is not None and not serial_output.receipt(playback_id, event):
                    return False
                audio_tagger.acknowledge(playback_id, event)
                return True

            call_capture.playback_listener = receive_playback
        processors.append(audio_tagger)
        if serial_output is not None:
            processors.append(serial_output)
    processors.extend([transport.output(), assistant_aggregator])
    pipeline = Pipeline(processors)
    observer = SessionTimingObserver(
        session_id=lease.session_id,
        event_sink=event_buffer.add,
        frame_sink=call_capture.observe if call_capture is not None else None,
    )
    worker = PipelineWorker(
        pipeline,
        rtvi_processor=TDRTVIProcessor() if custom_td is not None else None,
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

    async def on_llm_completion_timeout(_service: object) -> None:
        """Speak the Bot fallback without issuing another LLM request."""
        logger.warning("llm_completion_timeout session_id=%s", lease.session_id)
        if lease.config.fallback_script:
            await worker.queue_frames([TTSSpeakFrame(lease.config.fallback_script)])

    add_llm_handler = getattr(llm, "add_event_handler", None)
    if callable(add_llm_handler):
        add_llm_handler("on_completion_timeout", on_llm_completion_timeout)

    @worker.rtvi.event_handler("on_client_ready")
    async def on_client_ready(_rtvi: object) -> None:
        """Speak the fixed opening without asking the LLM to rewrite it."""
        if not lease.config.opening_script:
            return
        context.add_message({"role": "assistant", "content": lease.config.opening_script})
        if custom_td is not None:
            custom_td.assistant_context(lease.config.opening_script)
            if event_sink:
                event_sink({"event": "assistant_opening", "text": lease.config.opening_script})
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
            if custom_td is not None and custom_td.source_evidence_error is not None:
                raise custom_td.source_evidence_error
    except TimeoutError:
        logger.info("session_timeout session_id=%s", lease.session_id)
        await worker.cancel()
    finally:
        if identifier_output is not None:
            await identifier_output.close()
        if call_capture is not None:
            call_capture.playback_listener = None
        if response_scope is not None:
            await response_scope.close()
        if identifier_tools is not None:
            identifier_tools.close()
        if td_http is not None:
            await td_http.aclose()
