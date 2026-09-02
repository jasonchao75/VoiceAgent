"""Deepgram Flux STT provider mapping."""

from pipecat.services.deepgram.flux.stt import DeepgramFluxSTTService

from src.config import ASRConfig, AudioConfig


def create_flux_stt(
    *, api_key: str, config: ASRConfig, audio: AudioConfig
) -> DeepgramFluxSTTService:
    """Create a Flux STT service using server-side turn detection.

    Args:
        api_key: Session-scoped Deepgram API key.
        config: Validated Flux ASR settings.
        audio: Explicit input audio contract.

    Returns:
        Configured Pipecat Deepgram Flux STT service.
    """
    return DeepgramFluxSTTService(
        api_key=api_key,
        sample_rate=audio.input_sample_rate,
        flux_encoding=audio.encoding,
        should_interrupt=True,
        settings=DeepgramFluxSTTService.Settings(
            model=config.model,
            eager_eot_threshold=config.eager_eot_threshold,
            eot_threshold=config.eot_threshold,
            eot_timeout_ms=config.eot_timeout_ms,
        ),
    )
