"""Whitelist validation of bot configuration against server catalogs."""

from __future__ import annotations

from src.bots.models import BotConfigFields
from src.config import LLMConfig, LLMProviderCatalog, VoiceCatalog

SUPPORTED_ASR_PROVIDERS: tuple[str, ...] = ("deepgram_flux",)


def validate_bot_config(
    *,
    config: BotConfigFields,
    voice_catalog: VoiceCatalog,
    llm_catalog: LLMProviderCatalog,
    tts_providers: tuple[str, ...],
) -> None:
    """Reject bot settings outside the controlled catalogs.

    Uses the same whitelist sources as session-level validation so a bot can
    never store a configuration that session creation would reject.

    Args:
        config: Non-secret bot fields to validate.
        voice_catalog: Allowed Flux voices for the deepgram_flux TTS provider.
        llm_catalog: Allowed LLM provider presets.
        tts_providers: Provider IDs registered in the TTS registry.

    Raises:
        ValueError: With a user-readable message when a field is not allowed.
    """
    if config.asr_provider not in SUPPORTED_ASR_PROVIDERS:
        raise ValueError("Unsupported ASR provider")
    if config.tts_provider not in tts_providers:
        raise ValueError("Unsupported TTS provider")
    if config.tts_provider == "deepgram_flux":
        voices = {voice.model_id for voice in voice_catalog.voices}
        if config.tts_voice not in voices:
            raise ValueError("Select a TTS voice from the server catalog")
        if config.tts_model != "flux-general-en":
            raise ValueError("Unsupported Deepgram Flux TTS model")
    elif config.tts_provider == "elevenlabs":
        if config.tts_model not in {"eleven_flash_v2_5", "eleven_multilingual_v2"}:
            raise ValueError("Unsupported ElevenLabs TTS model")
        if not config.tts_voice.strip() or len(config.tts_voice) > 100:
            raise ValueError("Enter a valid ElevenLabs voice ID")

    providers = {provider.id: provider for provider in llm_catalog.providers}
    provider = providers.get(config.llm_provider)
    if provider is None:
        raise ValueError("Unknown LLM provider")
    base_url = config.llm_base_url.rstrip("/")
    if provider.id != "custom" and base_url != provider.base_url:
        raise ValueError("The selected provider base URL does not match the server catalog")
    if not provider.supports_custom_model and config.llm_model not in provider.recommended_models:
        raise ValueError("Select an LLM model from the server catalog")
    # Reuse the canonical HTTPS endpoint validation instead of duplicating it.
    LLMConfig(provider=provider.id, base_url=base_url, model=config.llm_model.strip())
