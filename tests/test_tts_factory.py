"""TTS registry extension boundary tests."""

import pytest
from pipecat.services.deepgram.flux.tts import DeepgramFluxTTSService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService

from src.config import RuntimeConfig
from src.tts import TTSProviderRegistry, create_default_tts_registry


def test_default_registry_contains_supported_providers(runtime_config: RuntimeConfig) -> None:
    """Both production streaming TTS providers are registered."""
    registry = create_default_tts_registry()
    assert registry.providers == ("deepgram_flux", "elevenlabs")
    service = registry.create(
        provider="deepgram_flux",
        api_key="inert-test-key",
        config=runtime_config.tts,
        audio=runtime_config.audio,
    )
    assert isinstance(service, DeepgramFluxTTSService)
    assert service._settings.voice == runtime_config.tts.voice
    assert service._settings.speed == runtime_config.tts.speed
    assert service._settings.expressivity == runtime_config.tts.expressivity
    assert service._init_sample_rate == runtime_config.audio.output_sample_rate
    assert service._text_aggregation_mode.value == "token"

    elevenlabs_config = runtime_config.tts.model_copy(
        update={
            "provider": "elevenlabs",
            "voice": "test-voice-id",
            "model": "eleven_flash_v2_5",
        }
    )
    elevenlabs = registry.create(
        provider="elevenlabs",
        api_key="inert-test-key",
        config=elevenlabs_config,
        audio=runtime_config.audio,
    )
    assert isinstance(elevenlabs, ElevenLabsTTSService)
    assert elevenlabs._init_sample_rate == runtime_config.audio.output_sample_rate
    assert elevenlabs._text_aggregation_mode.value == "token"
    assert elevenlabs._auto_mode is False


def test_elevenlabs_settings_and_derived_auto_mode(runtime_config: RuntimeConfig) -> None:
    """Provider settings survive construction and sentence input derives Auto mode."""
    registry = create_default_tts_registry()
    config = runtime_config.tts.model_copy(
        update={
            "provider": "elevenlabs",
            "voice": "test-voice-id",
            "model": "eleven_turbo_v2_5",
            "text_aggregation": "sentence",
            "speed": 1.1,
            "stability": 0.7,
            "similarity_boost": 0.65,
            "style": 0.2,
            "use_speaker_boost": True,
            "text_normalization": "on",
        }
    )
    service = registry.create(
        provider="elevenlabs",
        api_key="inert-test-key",
        config=config,
        audio=runtime_config.audio,
    )
    assert service._text_aggregation_mode.value == "sentence"
    assert service._auto_mode is True
    assert service._settings.stability == 0.7
    assert service._settings.similarity_boost == 0.65
    assert service._settings.style == 0.2
    assert service._settings.use_speaker_boost is True
    assert service._settings.speed == 1.1
    assert service._settings.apply_text_normalization == "on"


def test_flux_voice_controls_are_passed_to_service(runtime_config: RuntimeConfig) -> None:
    """Flux receives the persisted conversational voice controls."""
    config = runtime_config.tts.model_copy(update={"speed": 1.05, "expressivity": 1})
    service = create_default_tts_registry().create(
        provider="deepgram_flux",
        api_key="inert-test-key",
        config=config,
        audio=runtime_config.audio,
    )
    assert service._settings.speed == 1.05
    assert service._settings.expressivity == 1


def test_eleven_v3_omits_unsupported_settings(runtime_config: RuntimeConfig) -> None:
    """Eleven v3 must not receive similarity or speaker boost parameters."""
    config = runtime_config.tts.model_copy(
        update={
            "provider": "elevenlabs",
            "voice": "test-voice-id",
            "model": "eleven_v3",
            "stability": 1.0,
            "similarity_boost": 0.2,
            "use_speaker_boost": True,
        }
    )
    service = create_default_tts_registry().create(
        provider="elevenlabs",
        api_key="inert-test-key",
        config=config,
        audio=runtime_config.audio,
    )
    assert service._settings.stability == 1.0
    assert service._settings.similarity_boost is None
    assert service._settings.use_speaker_boost is None


def test_registry_rejects_unimplemented_provider() -> None:
    """Unknown providers fail before pipeline startup or paid API access."""
    registry = TTSProviderRegistry()
    with pytest.raises(ValueError, match="Unsupported TTS provider"):
        registry.create(provider="elevenlabs", api_key="x", config=None, audio=None)  # type: ignore[arg-type]
