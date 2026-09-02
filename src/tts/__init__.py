"""Text-to-speech provider registry."""

from src.tts.factory import TTSProviderRegistry, create_default_tts_registry

__all__ = ["TTSProviderRegistry", "create_default_tts_registry"]
