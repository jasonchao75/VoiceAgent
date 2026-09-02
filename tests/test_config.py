"""Runtime and public catalog schema tests."""

from urllib.parse import urlparse

import pytest

from src.config import LLMConfig, LLMProviderCatalog, RuntimeConfig, VoiceCatalog


def test_audio_contract_is_explicit(runtime_config: RuntimeConfig) -> None:
    """Keep browser, Pipecat, Flux STT, and Flux TTS on one asserted contract."""
    assert runtime_config.audio.encoding == "linear16"
    assert runtime_config.audio.input_sample_rate == 16_000
    assert runtime_config.audio.output_sample_rate == 24_000
    assert runtime_config.audio.sample_width_bytes == 2
    assert runtime_config.audio.channels == 1


def test_voice_catalog_has_unique_english_flux_models(voice_catalog: VoiceCatalog) -> None:
    """Prevent a free-form or invalid voice from reaching a paid session."""
    ids = [voice.model_id for voice in voice_catalog.voices]
    assert len(ids) == len(set(ids))
    assert all(model.startswith("flux-") and model.endswith("-en") for model in ids)
    assert urlparse(voice_catalog.source_url).scheme == "https"
    assert urlparse(voice_catalog.listen_url).scheme == "https"


def test_llm_catalog_has_safe_help_links_and_custom_option(
    llm_catalog: LLMProviderCatalog,
) -> None:
    """Only controlled HTTPS links are rendered beside credential inputs."""
    assert "custom" in {provider.id for provider in llm_catalog.providers}
    for provider in llm_catalog.providers:
        assert urlparse(provider.api_key_url).scheme == "https"
        assert urlparse(provider.models_url).scheme == "https"
        if provider.id != "custom":
            assert provider.default_model in provider.recommended_models


@pytest.mark.parametrize(
    "base_url",
    ["https://localhost/v1", "https://127.0.0.1/v1", "https://10.0.0.5/v1"],
)
def test_custom_llm_endpoint_rejects_obvious_local_targets(base_url: str) -> None:
    """Reduce SSRF exposure when a public demo enables the custom provider option."""
    with pytest.raises(ValueError, match="local|private"):
        LLMConfig(provider="custom", base_url=base_url, model="test-model")
