"""ASR registry and provider mapping tests without external calls."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest
from deepgram.listen.v1.types import (
    ListenV1Results,
    ListenV1ResultsChannel,
    ListenV1ResultsChannelAlternativesItem,
)
from pipecat.frames.frames import ProposedUserStoppedSpeakingFrame
from pipecat.services.assemblyai.stt import AssemblyAISTTService
from pipecat.services.deepgram.flux.stt import DeepgramFluxSTTService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.soniox.stt import SonioxSTTService
from websockets.protocol import State

from src.asr import ASRProviderRegistry, create_default_asr_registry
from src.asr import factory as asr_factory
from src.config import RuntimeConfig


def test_default_registry_contains_every_frozen_model() -> None:
    """The registry exposes all six provider/model selections."""
    assert create_default_asr_registry().models == (
        ("assemblyai", "universal-3-5-pro"),
        ("deepgram", "flux-general-en"),
        ("deepgram", "flux-general-multi"),
        ("deepgram", "nova-3"),
        ("soniox", "stt-rt-v5"),
        ("speechmatics", "enhanced"),
    )


def test_flux_and_nova3_map_distinct_protocols(runtime_config: RuntimeConfig) -> None:
    """Flux uses V2 model EOT while Nova-3 uses V1 fixed-silence endpointing."""
    registry = create_default_asr_registry()
    flux = registry.create(
        provider="deepgram",
        model="flux-general-en",
        turn_detection_source="provider_native",
        options={},
        api_key="inert-test-key",
        audio=runtime_config.audio,
    )
    nova = registry.create(
        provider="deepgram",
        model="nova-3",
        turn_detection_source="off",
        options={"language": "ar-AE", "endpointing_ms": 420},
        api_key="inert-test-key",
        audio=runtime_config.audio,
    )
    assert isinstance(flux.processor, DeepgramFluxSTTService)
    assert flux.processor._settings.eot_threshold == 0.7
    assert isinstance(nova.processor, DeepgramSTTService)
    assert nova.processor._settings.language == "ar-AE"
    assert nova.processor._settings.endpointing == 420


@pytest.mark.asyncio
async def test_nova3_only_closes_on_speech_final(runtime_config: RuntimeConfig) -> None:
    """Chunk finals remain text-only; one speech_final closes exactly one Turn."""
    service = create_default_asr_registry().create(
        provider="deepgram",
        model="nova-3",
        turn_detection_source="off",
        options={"language": "ar-SA", "endpointing_ms": 300},
        api_key="inert-test-key",
        audio=runtime_config.audio,
    )
    proposals: list[type[ProposedUserStoppedSpeakingFrame]] = []

    async def capture_proposal(frame_type: type[ProposedUserStoppedSpeakingFrame]) -> None:
        proposals.append(frame_type)

    service.processor.broadcast_frame = capture_proposal
    channel = ListenV1ResultsChannel(
        alternatives=[
            ListenV1ResultsChannelAlternativesItem(
                transcript="",
                confidence=1.0,
                languages=["ar-SA"],
                words=[],
            )
        ]
    )

    def result(*, speech_final: bool) -> ListenV1Results:
        return ListenV1Results.model_construct(
            type="Results",
            channel_index=[0, 1],
            duration=0.3,
            start=1.0,
            is_final=True,
            speech_final=speech_final,
            channel=channel.model_dump(),
            metadata=None,
            from_finalize=False,
            entities=None,
        )

    await service.processor._on_message(result(speech_final=False))
    assert proposals == []
    final_message = result(speech_final=True)
    await service.processor._on_message(final_message)
    await service.processor._on_message(final_message)
    assert proposals == [ProposedUserStoppedSpeakingFrame]


def test_soniox_uses_provider_native_endpointing(runtime_config: RuntimeConfig) -> None:
    """Soniox native endpointing is enabled without Pipecat forcing endpoints."""
    service = create_default_asr_registry().create(
        provider="soniox",
        model="stt-rt-v5",
        turn_detection_source="provider_native",
        options={"language_hints": ["ar", "en"]},
        api_key="inert-test-key",
        audio=runtime_config.audio,
    )
    assert isinstance(service.processor, SonioxSTTService)
    assert service.processor._vad_force_turn_endpoint is False
    assert service.processor._settings.model == "stt-rt-v5"
    assert service.processor._settings.endpoint_sensitivity == 0.3
    assert service.processor._settings.context.general is None


def test_registry_pins_ca_bundle_for_every_provider(
    runtime_config: RuntimeConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every provider receives the same locked CA roots before creating sockets."""
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    create_default_asr_registry().create(
        provider="soniox",
        model="stt-rt-v5",
        turn_detection_source="provider_native",
        options={},
        api_key="inert-test-key",
        audio=runtime_config.audio,
    )
    assert Path(os.environ["SSL_CERT_FILE"]).is_file()


def test_assemblyai_maps_context_and_voice_focus(runtime_config: RuntimeConfig) -> None:
    """U3.5 Pro receives native Turn, opening context, and enum Voice Focus."""
    service = create_default_asr_registry().create(
        provider="assemblyai",
        model="universal-3-5-pro",
        turn_detection_source="provider_native",
        options={
            "language_codes": ["ar", "en"],
            "voice_focus": "near-field",
            "voice_focus_threshold": 0.65,
        },
        api_key="inert-test-key",
        audio=runtime_config.audio,
        opening_script="Welcome to the banking assistant.",
    )
    assert isinstance(service.processor, AssemblyAISTTService)
    assert service.processor._vad_force_turn_endpoint is False
    assert service.processor._settings.agent_context == "Welcome to the banking assistant."
    assert service.processor._settings.voice_focus == "near-field"
    assert service.processor._settings.voice_focus_threshold == 0.65
    assert service.processor._settings.previous_context_n_turns == 5


@pytest.mark.asyncio
async def test_assemblyai_context_update_reports_socket_outcome(
    runtime_config: RuntimeConfig,
) -> None:
    """Context success requires an open socket; disconnected updates fail visibly."""
    service = create_default_asr_registry().create(
        provider="assemblyai",
        model="universal-3-5-pro",
        turn_detection_source="provider_native",
        options={"agent_context_enabled": True},
        api_key="inert-test-key",
        audio=runtime_config.audio,
    )
    with pytest.raises(ConnectionError, match="socket is not open"):
        await service.update_agent_context("Assistant reply")

    sent: list[str] = []

    class OpenSocket:
        state = State.OPEN

        async def send(self, payload: str) -> None:
            sent.append(payload)

    service.processor._websocket = OpenSocket()  # type: ignore[attr-defined,assignment]
    await service.update_agent_context("Assistant reply")
    assert sent == ['{"type": "UpdateConfiguration", "agent_context": "Assistant reply"}']


@pytest.mark.asyncio
async def test_assemblyai_context_update_has_a_bounded_send_timeout(
    runtime_config: RuntimeConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stalled provider socket cannot leave the side-channel task pending forever."""
    service = create_default_asr_registry().create(
        provider="assemblyai",
        model="universal-3-5-pro",
        turn_detection_source="provider_native",
        options={"agent_context_enabled": True},
        api_key="inert-test-key",
        audio=runtime_config.audio,
    )

    class StalledSocket:
        state = State.OPEN

        async def send(self, _payload: str) -> None:
            await asyncio.Event().wait()

    monkeypatch.setattr(asr_factory, "ASSEMBLYAI_CONTEXT_TIMEOUT_SECONDS", 0.01)
    service.processor._websocket = StalledSocket()  # type: ignore[attr-defined,assignment]
    with pytest.raises(TimeoutError):
        await service.update_agent_context("Assistant reply")


def test_speechmatics_constructs_without_network_and_maps_sentences(
    runtime_config: RuntimeConfig,
) -> None:
    """The thin adapter bypasses the Pipecat split_sentences config defect."""
    service = create_default_asr_registry().create(
        provider="speechmatics",
        model="enhanced",
        turn_detection_source="provider_native",
        options={"emit_sentences": True},
        api_key="inert-test-key",
        audio=runtime_config.audio,
    )
    assert service.processor._config.operating_point.value == "enhanced"
    assert service.processor._config.speech_segment_config.emit_sentences is True
    assert service.processor._config.punctuation_overrides == {"sensitivity": 0.5}
    assert not hasattr(service.processor._config, "split_sentences")


def test_speechmatics_custom_punctuation_marks_reach_wire_config(
    runtime_config: RuntimeConfig,
) -> None:
    """A custom punctuation subset remains an array in the SDK wire config."""
    service = create_default_asr_registry().create(
        provider="speechmatics",
        model="enhanced",
        turn_detection_source="provider_native",
        options={
            "punctuation_overrides": {
                "sensitivity": 0.7,
                "permitted_marks": [".", "?"],
            }
        },
        api_key="inert-test-key",
        audio=runtime_config.audio,
    )
    assert service.processor._config.punctuation_overrides == {
        "sensitivity": 0.7,
        "permitted_marks": [".", "?"],
    }


def test_speechmatics_uses_bundled_turn_models_and_certifi(
    runtime_config: RuntimeConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Speechmatics startup reuses local models and pinned CA roots without downloads."""
    from speechmatics.voice import VoiceAgentClient

    for name in ("SSL_CERT_FILE", "SILERO_MODEL_PATH", "SMART_TURN_MODEL_PATH"):
        monkeypatch.delenv(name, raising=False)

    service = create_default_asr_registry().create(
        provider="speechmatics",
        model="enhanced",
        turn_detection_source="provider_native",
        options={"turn_detection_mode": "smart_turn"},
        api_key="inert-test-key",
        audio=runtime_config.audio,
    )

    assert Path(os.environ["SSL_CERT_FILE"]).is_file()
    assert Path(os.environ["SILERO_MODEL_PATH"]).is_file()
    assert Path(os.environ["SMART_TURN_MODEL_PATH"]).is_file()

    def reject_download(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Speechmatics runtime attempted an unapproved model download")

    monkeypatch.setattr("urllib.request.urlretrieve", reject_download)
    client = VoiceAgentClient(api_key="inert-test-key", config=service.processor._config)
    assert client._uses_silero_vad is True
    assert client._uses_smart_turn is True


@pytest.mark.asyncio
async def test_speechmatics_segments_do_not_end_turn_before_end_of_turn(
    runtime_config: RuntimeConfig,
) -> None:
    """Sentence segments remain transcript input until one real EndOfTurn proposal."""
    service = create_default_asr_registry().create(
        provider="speechmatics",
        model="enhanced",
        turn_detection_source="provider_native",
        options={"emit_sentences": True},
        api_key="inert-test-key",
        audio=runtime_config.audio,
    )
    segments: list[tuple[list[dict[str, object]], bool]] = []
    proposals: list[type[ProposedUserStoppedSpeakingFrame]] = []

    async def capture_segments(values: list[dict[str, object]], *, finalized: bool = False) -> None:
        segments.append((values, finalized))

    async def capture_proposal(frame_type: type[ProposedUserStoppedSpeakingFrame]) -> None:
        proposals.append(frame_type)

    service.processor._send_frames = capture_segments
    service.processor.broadcast_frame = capture_proposal
    await service.processor._handle_segment({"segments": [{"content": "First sentence."}]})
    await service.processor._handle_segment({"segments": [{"content": "Second sentence."}]})
    assert len(segments) == 2
    assert all(finalized for _values, finalized in segments)
    assert proposals == []

    await service.processor._handle_end_of_turn({"message": "EndOfTurn"})
    assert proposals == [ProposedUserStoppedSpeakingFrame]


def test_registry_rejects_unknown_or_cross_provider_fields(
    runtime_config: RuntimeConfig,
) -> None:
    """Invalid selections fail before a provider connection is attempted."""
    registry = create_default_asr_registry()
    with pytest.raises(ValueError, match="Unsupported ASR provider/model"):
        registry.create(
            provider="assemblyai",
            model="nova-3",
            turn_detection_source="off",
            options={},
            api_key="x",
            audio=runtime_config.audio,
        )
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        registry.create(
            provider="soniox",
            model="stt-rt-v5",
            turn_detection_source="provider_native",
            options={"eot_threshold": 0.7},
            api_key="x",
            audio=runtime_config.audio,
        )


def test_registry_rejects_duplicate_registration() -> None:
    """A stable provider/model identifier cannot be silently replaced."""
    registry = ASRProviderRegistry()

    def inert(*_args):  # type: ignore[no-untyped-def]
        return object()

    registry.register("deepgram", "nova-3", inert)
    with pytest.raises(ValueError, match="already registered"):
        registry.register("deepgram", "nova-3", inert)
