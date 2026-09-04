"""Small TTS registry that keeps provider construction out of the pipeline."""

from __future__ import annotations

from collections.abc import Callable

from pipecat.services.tts_service import TTSService

from src.config import AudioConfig, TTSConfig

TTSBuilder = Callable[[str, TTSConfig, AudioConfig], TTSService]


class TTSProviderRegistry:
    """Registry boundary for current and future TTS providers."""

    def __init__(self) -> None:
        """Create an empty provider registry."""
        self._builders: dict[str, TTSBuilder] = {}

    def register(self, provider: str, builder: TTSBuilder) -> None:
        """Register one concrete provider builder.

        Args:
            provider: Stable provider identifier used by runtime configuration.
            builder: Function that creates a usable Pipecat TTS service.

        Raises:
            ValueError: If the provider is already registered.
        """
        if provider in self._builders:
            raise ValueError(f"TTS provider already registered: {provider}")
        self._builders[provider] = builder

    def create(
        self, *, provider: str, api_key: str, config: TTSConfig, audio: AudioConfig
    ) -> TTSService:
        """Create a configured TTS service from the selected provider."""
        builder = self._builders.get(provider)
        if builder is None:
            raise ValueError(f"Unsupported TTS provider: {provider}")
        return builder(api_key, config, audio)

    @property
    def providers(self) -> tuple[str, ...]:
        """Return registered provider IDs for health and tests."""
        return tuple(sorted(self._builders))


def _build_deepgram_flux(api_key: str, config: TTSConfig, audio: AudioConfig) -> TTSService:
    """Build the only production TTS provider included in the MVP."""
    from pipecat.services.deepgram.flux.tts import DeepgramFluxTTSService

    return DeepgramFluxTTSService(
        api_key=api_key,
        sample_rate=audio.output_sample_rate,
        settings=DeepgramFluxTTSService.Settings(
            voice=config.voice,
            speed=config.speed,
            expressivity=config.expressivity,
        ),
    )


def _build_elevenlabs(api_key: str, config: TTSConfig, audio: AudioConfig) -> TTSService:
    """Build low-latency ElevenLabs WebSocket synthesis."""
    from pipecat.services.elevenlabs.tts import ElevenLabsTTSService

    return ElevenLabsTTSService(
        api_key=api_key,
        sample_rate=audio.output_sample_rate,
        auto_mode=True,
        settings=ElevenLabsTTSService.Settings(
            voice=config.voice,
            model=config.model,
            speed=config.speed,
            stability=0.5,
            similarity_boost=0.8,
            style=0.0,
            use_speaker_boost=True,
            apply_text_normalization="auto",
        ),
    )


def create_default_tts_registry() -> TTSProviderRegistry:
    """Create the production registry for supported streaming TTS providers."""
    registry = TTSProviderRegistry()
    registry.register("deepgram_flux", _build_deepgram_flux)
    registry.register("elevenlabs", _build_elevenlabs)
    return registry
