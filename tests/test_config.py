"""Runtime and public catalog schema tests."""

from urllib.parse import urlparse

import httpx
import pytest
from pydantic import ValidationError

from src.asr.catalog import discover_asr_model_catalog
from src.asr.config import (
    ASSEMBLYAI_LANGUAGES,
    NOVA3_LANGUAGES,
    SONIOX_LANGUAGES,
    SPEECHMATICS_DOMAINS,
    SPEECHMATICS_LANGUAGE_PACKS,
    asr_provider_catalog,
    validate_asr_options,
)
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


def test_asr_catalog_exposes_confirmed_provider_and_turn_capabilities() -> None:
    """The browser catalog must not invent unsupported provider/model states."""
    catalog = asr_provider_catalog()
    providers = {provider["id"]: provider for provider in catalog["providers"]}
    assert set(providers) == {"deepgram", "speechmatics", "soniox", "assemblyai"}

    deepgram_models = {model["id"]: model for model in providers["deepgram"]["models"]}
    assert deepgram_models["nova-3"]["turn_sources"] == ["off"]
    assert deepgram_models["flux-general-en"]["turn_sources"] == ["provider_native"]
    assert providers["soniox"]["models"][0]["turn_sources"] == ["provider_native"]
    assert providers["assemblyai"]["models"][0]["turn_sources"] == ["provider_native"]
    assert len(SPEECHMATICS_LANGUAGE_PACKS) == 62
    assert len(SONIOX_LANGUAGES) == 60
    assert len(ASSEMBLYAI_LANGUAGES) == 18
    assert len(set(ASSEMBLYAI_LANGUAGES)) == 18
    assert len(NOVA3_LANGUAGES) == 105
    speechmatics = providers["speechmatics"]["models"][0]
    assert speechmatics["domains_by_language"]["en"] == ["finance", "medical"]
    assert speechmatics["domains_by_language"]["ar_en"] == ["medical"]
    assert SPEECHMATICS_DOMAINS["es"] == ("bilingual-en", "medical")
    assert speechmatics["language_control"]["account_filtered"] is False
    assert speechmatics["advanced_fields"]
    soniox_language = providers["soniox"]["models"][0]["language_control"]
    assembly_language = providers["assemblyai"]["models"][0]["language_control"]
    assert soniox_language["labels"]["ar"] == "Arabic"
    assert assembly_language["labels"]["ar"] == "Arabic"


@pytest.mark.asyncio
async def test_authenticated_asr_catalogs_are_normalized_without_exposing_keys() -> None:
    """Provider discovery responses become the same safe browser catalog shape."""

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer secret-test-key"
        if "speechmatics" in request.url.host:
            return httpx.Response(
                200,
                json={
                    "language_packs": [
                        {"language": "auto", "domains": []},
                        {"language": "en", "domains": ["finance", "medical"]},
                        {"language": "ar_en", "domains": ["medical"]},
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "models": [
                    {
                        "id": "stt-rt-v5",
                        "languages": [
                            {"code": "ar", "name": "Arabic account label"},
                            {"code": "en"},
                        ],
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        speechmatics = await discover_asr_model_catalog(
            "speechmatics", "secret-test-key", client=client
        )
        soniox = await discover_asr_model_catalog("soniox", "secret-test-key", client=client)

    assert speechmatics["language_control"]["values"] == ["en", "ar_en"]
    assert speechmatics["language_control"]["account_filtered"] is True
    assert speechmatics["domains_by_language"]["en"] == ["finance", "medical"]
    assert soniox["language_control"]["values"] == ["ar", "en"]
    assert soniox["language_control"]["labels"] == {
        "ar": "Arabic account label",
        "en": "English",
    }
    assert "secret-test-key" not in repr((speechmatics, soniox))


def test_asr_options_are_strictly_isolated_by_provider_model() -> None:
    """Flux fields cannot leak into Nova-3 or another provider branch."""
    nova = validate_asr_options(
        provider="deepgram",
        model="nova-3",
        turn_detection_source="off",
        options={"language": "ar-SA", "endpointing_ms": 300, "keyterms": ["Riyad Bank"]},
    )
    assert nova["language"] == "ar-SA"
    assert nova["endpointing_ms"] == 300

    with pytest.raises(ValidationError, match="eot_threshold"):
        validate_asr_options(
            provider="deepgram",
            model="nova-3",
            turn_detection_source="off",
            options={"language": "ar-SA", "eot_threshold": 0.7},
        )
    with pytest.raises(ValueError, match="Turn Detection source"):
        validate_asr_options(
            provider="assemblyai",
            model="universal-3-5-pro",
            turn_detection_source="off",
            options={},
        )


def test_speechmatics_off_requires_positive_fixed_silence() -> None:
    """Off means fixed-silence turns and never disables automatic boundaries."""
    validated = validate_asr_options(
        provider="speechmatics",
        model="enhanced",
        turn_detection_source="off",
        options={
            "language": "ar_en",
            "turn_detection_mode": "fixed",
            "end_of_utterance_silence_trigger": 0.5,
            "end_of_utterance_max_delay": 10.0,
        },
    )
    assert validated["turn_detection_mode"] == "fixed"
    with pytest.raises(ValidationError, match="greater than 0"):
        validate_asr_options(
            provider="speechmatics",
            model="enhanced",
            turn_detection_source="off",
            options={
                "language": "ar_en",
                "turn_detection_mode": "fixed",
                "end_of_utterance_silence_trigger": 0,
            },
        )


def test_speechmatics_domain_must_match_language_pack() -> None:
    """A stale domain cannot leak across Speechmatics Language Packs."""
    validated = validate_asr_options(
        provider="speechmatics",
        model="enhanced",
        turn_detection_source="provider_native",
        options={"language": "en", "domain": "finance"},
    )
    assert validated["domain"] == "finance"
    with pytest.raises(ValueError, match="domain is unavailable"):
        validate_asr_options(
            provider="speechmatics",
            model="enhanced",
            turn_detection_source="provider_native",
            options={"language": "ar", "domain": "finance"},
        )
