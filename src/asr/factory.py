"""Provider registry and thin adapters for streaming speech recognition."""

from __future__ import annotations

import asyncio
import copy
import os
from collections.abc import Callable
from dataclasses import dataclass
from importlib.resources import files
from typing import Any, Protocol, cast

from pipecat.frames.frames import TranscriptionFrame
from pipecat.services.stt_service import STTService
from pipecat.transcriptions.language import Language

from src.asr.config import (
    AssemblyAIOptions,
    DeepgramFluxOptions,
    DeepgramNova3Options,
    SonioxOptions,
    SpeechmaticsOptions,
    StrictASRModel,
    normalize_provider,
    validate_asr_options,
)
from src.asr.source_frames import SourceOwnedASRMixin
from src.asr.transcript import SourceSegment
from src.asr.turn_events import SourceNormalizer
from src.config import AudioConfig

ASRBuilder = Callable[[str, str, str, StrictASRModel, AudioConfig, str], STTService]
ASSEMBLYAI_CONTEXT_TIMEOUT_SECONDS = 3.0


def _configure_provider_tls() -> None:
    """Use the locked certifi trust roots for every provider WebSocket."""
    import certifi

    os.environ.setdefault("SSL_CERT_FILE", certifi.where())


def _configure_speechmatics_runtime() -> None:
    """Pin local turn models before importing the Voice SDK.

    Speechmatics Voice otherwise downloads its VAD and Smart Turn models during
    the first live session. Pipecat already ships compatible copies, so reusing
    those assets keeps session startup deterministic and network-scoped.
    """
    silero_model = files("pipecat.audio.vad.data").joinpath("silero_vad.onnx")
    smart_turn_model = files("pipecat.audio.turn.smart_turn.data").joinpath(
        "smart-turn-v3.2-cpu.onnx"
    )
    os.environ.setdefault("SILERO_MODEL_PATH", str(silero_model))
    os.environ.setdefault("SMART_TURN_MODEL_PATH", str(smart_turn_model))


class AgentContextUpdater(Protocol):
    """Provider capability used by the public ASR control boundary."""

    async def update_agent_context(self, text: str) -> None:
        """Update context for the next user Turn."""


@dataclass(slots=True)
class ASRService:
    """Pipeline-facing ASR processor plus provider-neutral control capabilities."""

    processor: STTService
    context_updates_enabled: bool = False
    _context_updater: AgentContextUpdater | None = None
    source_normalizer: SourceNormalizer | None = None
    _soniox_snapshot_scope: int = 0
    _soniox_snapshot_epoch: int = -1

    def normalize_source_frame(self, frame: Any) -> tuple[SourceSegment, ...]:
        """Normalize preserved provider data at the public ASR boundary."""
        if self.source_normalizer is None:
            return ()
        metadata = getattr(frame, "metadata", {})
        if "asr_stream_epoch" in metadata and (
            type(metadata["asr_stream_epoch"]) is not int or metadata["asr_stream_epoch"] < 0
        ):
            self.source_normalizer.missing_reason = "source_connection_unavailable"
            if getattr(frame, "text", ""):
                self.source_normalizer.retain_unknown_source()
            return ()
        payload = getattr(frame, "result", None)
        if payload is not None and hasattr(payload, "model_dump"):
            payload = payload.model_dump()
        if isinstance(payload, list) and self.source_normalizer.provider == "soniox":
            if self._soniox_snapshot_epoch != self.source_normalizer.epoch:
                self._soniox_snapshot_scope = 0
                self._soniox_snapshot_epoch = self.source_normalizer.epoch
            payload = {
                "tokens": payload,
                "td_full_snapshot": True,
                "td_snapshot_scope": self._soniox_snapshot_scope,
            }
            # The SDK clears its stable-prefix buffer after this endpoint frame.
            if isinstance(frame, TranscriptionFrame) and frame.finalized:
                self._soniox_snapshot_scope += 1
        if not isinstance(payload, dict):
            self.source_normalizer.missing_reason = (
                "source_payload_unavailable" if getattr(frame, "text", "") else None
            )
            if getattr(frame, "text", ""):
                self.source_normalizer.retain_unknown_source()
            return ()
        return self.source_normalizer.normalize(payload)

    async def update_agent_context(self, text: str) -> None:
        """Send one bounded context update through the selected adapter."""
        if not self.context_updates_enabled or self._context_updater is None:
            raise RuntimeError("ASR service does not support agent context updates")
        await self._context_updater.update_agent_context(text)


class ASRProviderRegistry:
    """Create provider services behind one pipeline-facing boundary."""

    def __init__(self) -> None:
        """Create an empty registry."""
        self._builders: dict[tuple[str, str], ASRBuilder] = {}

    def register(self, provider: str, model: str, builder: ASRBuilder) -> None:
        """Register a provider/model builder exactly once."""
        key = (normalize_provider(provider), model)
        if key in self._builders:
            raise ValueError(f"ASR provider/model already registered: {key[0]}/{key[1]}")
        self._builders[key] = builder

    def create(
        self,
        *,
        provider: str,
        model: str,
        turn_detection_source: str,
        options: dict[str, Any],
        api_key: str,
        audio: AudioConfig,
        opening_script: str = "",
    ) -> ASRService:
        """Validate a selection and construct its Pipecat STT service."""
        _configure_provider_tls()
        canonical_provider = normalize_provider(provider)
        builder = self._builders.get((canonical_provider, model))
        if builder is None:
            raise ValueError(f"Unsupported ASR provider/model: {canonical_provider}/{model}")
        normalized = validate_asr_options(
            provider=canonical_provider,
            model=model,
            turn_detection_source=turn_detection_source,
            options=options,
        )
        option_type: type[StrictASRModel]
        if model.startswith("flux-"):
            option_type = DeepgramFluxOptions
        elif model == "nova-3":
            option_type = DeepgramNova3Options
        elif canonical_provider == "speechmatics":
            option_type = SpeechmaticsOptions
        elif canonical_provider == "soniox":
            option_type = SonioxOptions
        else:
            option_type = AssemblyAIOptions
        parsed = option_type.model_validate(normalized)
        processor = builder(api_key, model, turn_detection_source, parsed, audio, opening_script)
        if isinstance(processor, SourceOwnedASRMixin):
            processor._td_source_mode = turn_detection_source == "self_developed"
        context_enabled = isinstance(parsed, AssemblyAIOptions) and parsed.agent_context_enabled
        return ASRService(
            processor=processor,
            source_normalizer=SourceNormalizer(
                canonical_provider,
                model,
                sample_rate=audio.input_sample_rate,
            ),
            context_updates_enabled=context_enabled,
            _context_updater=(cast(AgentContextUpdater, processor) if context_enabled else None),
        )

    @property
    def models(self) -> tuple[tuple[str, str], ...]:
        """Return registered provider/model pairs for health checks and tests."""
        return tuple(sorted(self._builders))


def _build_deepgram_flux(
    api_key: str,
    model: str,
    _turn_source: str,
    options: StrictASRModel,
    audio: AudioConfig,
    _opening_script: str,
) -> STTService:
    """Map validated Flux options onto the V2 streaming service."""
    from pipecat.frames.frames import InterimTranscriptionFrame
    from pipecat.services.deepgram.flux.stt import DeepgramFluxSTTService
    from pipecat.utils.time import time_now_iso8601

    class _SourceAwareFluxSTTService(SourceOwnedASRMixin, DeepgramFluxSTTService):
        """Preserve raw Update snapshots before the provider decides EndOfTurn."""

        async def _handle_turn_info(self, data: dict[str, Any]) -> None:
            """Bridge interim text and original word timing through the public frame path."""
            if data.get("event") == "Update" and data.get("transcript"):
                await self.push_frame(
                    InterimTranscriptionFrame(
                        text=data["transcript"],
                        user_id=self._user_id,
                        timestamp=time_now_iso8601(),
                        result=copy.deepcopy(data),
                    )
                )
            await super()._handle_turn_info(data)

    assert isinstance(options, DeepgramFluxOptions)
    return _SourceAwareFluxSTTService(
        api_key=api_key,
        sample_rate=audio.input_sample_rate,
        flux_encoding=audio.encoding,
        should_interrupt=_turn_source != "self_developed",
        settings=DeepgramFluxSTTService.Settings(
            model=model,
            eager_eot_threshold=None,
            eot_threshold=options.eot_threshold,
            eot_timeout_ms=options.eot_timeout_ms,
            language_hints=[Language(code) for code in options.language_hints] or None,
            keyterm=options.keyterms,
            numerals=options.numerals,
            extra={
                "profanity_filter": options.profanity_filter,
                **({"redact": options.redact} if options.redact else {}),
            },
        ),
    )


def _build_deepgram_nova3(
    api_key: str,
    _model: str,
    _turn_source: str,
    options: StrictASRModel,
    audio: AudioConfig,
    _opening_script: str,
) -> STTService:
    """Map Nova-3 V1 silence endpointing without semantic Turn Detection."""
    from deepgram.listen.v1.types import ListenV1Results
    from pipecat.frames.frames import ProposedUserStoppedSpeakingFrame
    from pipecat.services.deepgram.stt import DeepgramSTTService

    assert isinstance(options, DeepgramNova3Options)

    class _Nova3STTService(SourceOwnedASRMixin, DeepgramSTTService):
        """End a Turn only on Deepgram's silence-confirmed speech_final event."""

        def __init__(self, **kwargs: Any) -> None:
            """Initialize Nova-3 and remember the last closed provider Turn."""
            super().__init__(**kwargs)
            self._last_speech_final_key: tuple[float, float] | None = None
            self._diagnostic_audio_bytes = 0
            self._diagnostic_next_bytes = 32000
            # Nova retries within one SDK task, outside _connect/_websocket_connect.
            connector = self._client.listen.v1
            connector.connect = self._source_context_connector(connector.connect)

        async def run_stt(self, audio):  # type: ignore[no-untyped-def]
            """Observe SDK ingress; socket presence is not a remote receipt."""
            self._diagnostic_audio_bytes += len(audio)
            connected_before = self._connection is not None
            async for frame in super().run_stt(audio):
                yield frame
            if self._diagnostic_audio_bytes >= self._diagnostic_next_bytes:
                self._diagnostic_next_bytes = self._diagnostic_audio_bytes + 32000
                self.record_source_diagnostic(
                    "asr_audio_ingress",
                    total_bytes=self._diagnostic_audio_bytes,
                    connected_before=connected_before,
                    connected_after=self._connection is not None,
                    remote_receipt_verified=False,
                )

        async def _on_message(self, message):  # type: ignore[no-untyped-def]
            if isinstance(message, ListenV1Results):
                alternatives = message.channel.alternatives if message.channel else []
                first = alternatives[0] if alternatives else None
                self.record_source_diagnostic(
                    "asr_native_result",
                    provider="deepgram",
                    start_seconds=message.start,
                    duration_seconds=message.duration,
                    is_final=message.is_final,
                    speech_final=message.speech_final,
                    text_chars=len(first.transcript or "") if first else 0,
                    word_count=len(first.words or []) if first else 0,
                    confidence=first.confidence if first else None,
                )
            await super()._on_message(message)
            if not isinstance(message, ListenV1Results) or not message.speech_final:
                return
            event_key = (message.start, message.duration)
            if event_key == self._last_speech_final_key:
                return
            self._last_speech_final_key = event_key
            await self.broadcast_frame(ProposedUserStoppedSpeakingFrame)

    extra: dict[str, Any] = {"vad_events": options.vad_events}
    if options.diarize_model:
        extra["diarize_model"] = options.diarize_model
    return _Nova3STTService(
        api_key=api_key,
        sample_rate=audio.input_sample_rate,
        encoding=audio.encoding,
        channels=audio.channels,
        settings=DeepgramSTTService.Settings(
            model="nova-3",
            language=options.language,
            endpointing=options.endpointing_ms,
            interim_results=options.interim_results,
            keyterm=options.keyterms,
            smart_format=options.smart_format,
            numerals=options.numerals,
            profanity_filter=options.profanity_filter,
            redact=options.redact,
            extra=extra,
        ),
    )


def _build_soniox(
    api_key: str,
    _model: str,
    _turn_source: str,
    options: StrictASRModel,
    audio: AudioConfig,
    _opening_script: str,
) -> STTService:
    """Use Soniox semantic endpointing as the session's single Turn authority."""
    from pipecat.services.soniox.stt import (
        SonioxContextGeneralItem,
        SonioxContextObject,
        SonioxSTTService,
    )

    assert isinstance(options, SonioxOptions)
    context = SonioxContextObject(
        general=[
            SonioxContextGeneralItem(key=item.key, value=item.value)
            for item in options.context_general
        ]
        or None,
        text=options.context_text or None,
        terms=options.context_terms or None,
    )

    class _SourceAwareSonioxSTTService(SourceOwnedASRMixin, SonioxSTTService):
        """Keep SDK token transport while custom TD owns session turn boundaries."""

    return _SourceAwareSonioxSTTService(
        api_key=api_key,
        sample_rate=audio.input_sample_rate,
        audio_format="pcm_s16le",
        num_channels=audio.channels,
        vad_force_turn_endpoint=False,
        should_interrupt=_turn_source != "self_developed",
        settings=SonioxSTTService.Settings(
            model="stt-rt-v5",
            language_hints=[Language(code) for code in options.language_hints] or None,
            language_hints_strict=options.language_hints_strict,
            enable_language_identification=options.enable_language_identification,
            endpoint_sensitivity=options.endpoint_sensitivity,
            endpoint_latency_adjustment_level=options.endpoint_latency_adjustment_level,
            max_endpoint_delay_ms=options.max_endpoint_delay_ms,
            context=context,
        ),
    )


def _build_assemblyai(
    api_key: str,
    _model: str,
    _turn_source: str,
    options: StrictASRModel,
    audio: AudioConfig,
    opening_script: str,
) -> STTService:
    """Use U3.5 Pro native Turn Detection and initialize conversation context."""
    import json

    from pipecat.services.assemblyai.stt import AssemblyAISTTService, AssemblyAISTTSettings
    from websockets.protocol import State

    assert isinstance(options, AssemblyAIOptions)

    class _ObservableAssemblyAISTTService(SourceOwnedASRMixin, AssemblyAISTTService):
        """Expose whether a live agent-context update actually reached the socket."""

        async def update_agent_context(self, text: str) -> None:
            """Send one bounded context update or raise a safe local failure."""
            if not text:
                return
            bounded = self._clip_agent_context(text)
            cast(AssemblyAISTTSettings, self._settings).agent_context = bounded
            websocket = self._websocket
            if websocket is None or websocket.state is not State.OPEN:
                raise ConnectionError("AssemblyAI context socket is not open")
            await asyncio.wait_for(
                websocket.send(
                    json.dumps({"type": "UpdateConfiguration", "agent_context": bounded})
                ),
                timeout=ASSEMBLYAI_CONTEXT_TIMEOUT_SECONDS,
            )

    return _ObservableAssemblyAISTTService(
        api_key=api_key,
        sample_rate=audio.input_sample_rate,
        encoding="pcm_s16le",
        vad_force_turn_endpoint=False,
        should_interrupt=_turn_source != "self_developed",
        settings=AssemblyAISTTService.Settings(
            model="universal-3-5-pro",
            language_codes=[Language(code) for code in options.language_codes] or None,
            mode=options.mode,
            prompt=options.prompt or None,
            keyterms_prompt=options.keyterms_prompt or None,
            continuous_partials=options.continuous_partials,
            min_turn_silence=options.min_turn_silence,
            max_turn_silence=options.max_turn_silence,
            vad_threshold=options.vad_threshold,
            interruption_delay=options.interruption_delay,
            agent_context=(opening_script or None) if options.agent_context_enabled else None,
            previous_context_n_turns=(
                options.previous_context_n_turns if options.user_context_carryover_enabled else 0
            ),
            voice_focus=options.voice_focus,
            voice_focus_threshold=options.voice_focus_threshold,
            speaker_labels=options.speaker_labels,
        ),
    )


def _build_speechmatics(
    api_key: str,
    _model: str,
    _turn_source: str,
    options: StrictASRModel,
    audio: AudioConfig,
    _opening_script: str,
) -> STTService:
    """Construct Speechmatics while bypassing the upstream split-sentences bug."""
    _configure_speechmatics_runtime()
    from pipecat.services.speechmatics.stt import SpeechmaticsSTTService
    from speechmatics.voice import SpeechSegmentConfig  # type: ignore[import-untyped]

    assert isinstance(options, SpeechmaticsOptions)

    punctuation_overrides = options.punctuation_overrides.model_dump(mode="json")
    if punctuation_overrides["permitted_marks"] == "all":
        # "all" is a product sentinel; Speechmatics means all marks by omission.
        punctuation_overrides.pop("permitted_marks")

    class _SafeSpeechmaticsSTTService(SourceOwnedASRMixin, SpeechmaticsSTTService):
        """Avoid assigning split_sentences to VoiceAgentConfig in Pipecat 1.8.1."""

        async def _send_frames(
            self,
            segments: list[dict[str, Any]],
            finalized: bool = False,
        ) -> None:
            """Retain Voice SDK metadata/fragments without changing frame text or Final state."""
            enriched = []
            for segment in segments:
                row = copy.deepcopy(segment)
                row["results"] = {
                    "message": "AddSegment" if finalized else "AddPartialSegment",
                    "segments": [copy.deepcopy(segment)],
                }
                enriched.append(row)
            await super()._send_frames(enriched, finalized=finalized)

        def _build_config(self, settings):  # type: ignore[no-untyped-def]
            emit_sentences = settings.split_sentences
            safe_settings = copy.copy(settings)
            safe_settings.split_sentences = None
            config = super()._build_config(safe_settings)
            config.speech_segment_config = SpeechSegmentConfig(emit_sentences=bool(emit_sentences))
            config.include_results = True
            return config

    additional_vocab = [
        _SafeSpeechmaticsSTTService.AdditionalVocabEntry(
            content=item.content,
            sounds_like=item.sounds_like,
        )
        for item in options.additional_vocab
    ]
    return _SafeSpeechmaticsSTTService(
        api_key=api_key,
        sample_rate=audio.input_sample_rate,
        encoding=_SafeSpeechmaticsSTTService.AudioEncoding.PCM_S16LE,
        should_interrupt=_turn_source != "self_developed",
        settings=_SafeSpeechmaticsSTTService.Settings(
            language=options.language,
            domain=options.domain,
            turn_detection_mode=_SafeSpeechmaticsSTTService.TurnDetectionMode(
                "fixed" if _turn_source == "self_developed" else options.turn_detection_mode
            ),
            operating_point=_SafeSpeechmaticsSTTService.OperatingPoint.ENHANCED,
            max_delay=options.max_delay,
            end_of_utterance_silence_trigger=options.end_of_utterance_silence_trigger,
            end_of_utterance_max_delay=options.end_of_utterance_max_delay,
            additional_vocab=additional_vocab,
            punctuation_overrides=punctuation_overrides,
            include_partials=options.include_partials,
            split_sentences=options.emit_sentences,
        ),
    )


def create_default_asr_registry() -> ASRProviderRegistry:
    """Create the production registry for all frozen-baseline ASR models."""
    registry = ASRProviderRegistry()
    registry.register("deepgram", "flux-general-en", _build_deepgram_flux)
    registry.register("deepgram", "flux-general-multi", _build_deepgram_flux)
    registry.register("deepgram", "nova-3", _build_deepgram_nova3)
    registry.register("speechmatics", "enhanced", _build_speechmatics)
    registry.register("soniox", "stt-rt-v5", _build_soniox)
    registry.register("assemblyai", "universal-3-5-pro", _build_assemblyai)
    return registry
