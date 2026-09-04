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
    assert service._init_sample_rate == runtime_config.audio.output_sample_rate

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


def test_registry_rejects_unimplemented_provider() -> None:
    """Unknown providers fail before pipeline startup or paid API access."""
    registry = TTSProviderRegistry()
    with pytest.raises(ValueError, match="Unsupported TTS provider"):
        registry.create(provider="elevenlabs", api_key="x", config=None, audio=None)  # type: ignore[arg-type]
