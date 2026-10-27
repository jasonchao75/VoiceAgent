"""M1-1: catalog/source compatibility and durable custom TD configuration."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.asr.config import asr_provider_catalog, validate_asr_options
from src.bots.models import BotConfigFields
from src.bots.storage import BotStore
from src.session import SessionRequest, build_session_config


def td_settings():
    """Explicit fixture values are test inputs, never calibrated runtime defaults."""
    return {
        "minimum_ms": 600,
        "maximum_ms": 2500,
        "final_wait_ms": 200,
        "alpha": 0.5,
        "conflict_threshold": 0.8,
        "vad": {"confidence": 0.7, "start_secs": 0.2, "stop_secs": 0.2, "min_volume": 0.6},
        "jev": {
            "endpoint": "https://api.typesafe.ai/v1/systemone",
            "model": "jev-latest",
            "timeout_seconds": 2,
            "max_calls": 100,
            "noul_instructions": "Has the user yielded the floor?",
            "choice_instructions": "Classify the utterance.",
            "options": [
                {"id": "complete", "meaning": "Complete", "wait_ms": 700},
                {"id": "incomplete", "meaning": "Incomplete", "wait_ms": 1500},
            ],
        },
    }


@pytest.mark.parametrize(
    "provider,model",
    [
        ("deepgram", "flux-general-en"),
        ("deepgram", "flux-general-multi"),
        ("deepgram", "nova-3"),
        ("speechmatics", "enhanced"),
        ("soniox", "stt-rt-v5"),
        ("assemblyai", "universal-3-5-pro"),
    ],
)
def test_every_model_allows_custom_source_without_expanding_off(provider, model):
    """The new source must be available in both validation and server catalog."""
    options = validate_asr_options(
        provider=provider, model=model, turn_detection_source="self_developed", options={}
    )
    assert options["schema_version"] == 1
    entry = next(p for p in asr_provider_catalog()["providers"] if p["id"] == provider)
    assert "self_developed" in next(m for m in entry["models"] if m["id"] == model)["turn_sources"]
    if provider in {"soniox", "assemblyai"} or model.startswith("flux-"):
        with pytest.raises(ValueError):
            validate_asr_options(
                provider=provider, model=model, turn_detection_source="off", options={}
            )


async def test_td_draft_persists_when_source_hidden_and_restart(tmp_path: Path, session_request):
    """A native-source Bot can keep a custom draft without accidentally enabling it."""
    request = {
        name: getattr(session_request, name)
        for name in BotConfigFields.model_fields
        if hasattr(session_request, name)
    }
    from tests.test_td_rule_settings import priority_settings

    settings = td_settings()
    settings["priority_rule"] = priority_settings()
    config = BotConfigFields.model_validate(
        {
            **request,
            "name": "TD config",
            "tts_provider": "deepgram_flux",
            "tts_voice": session_request.flux_voice,
            "td_config": settings,
        }
    )
    store = BotStore(tmp_path / "bots.db")
    await store.initialize()
    row = await store.create(
        config=config,
        encrypted_deepgram_key=None,
        encrypted_llm_key=None,
        encrypted_elevenlabs_key=None,
    )
    restored = await BotStore(tmp_path / "bots.db").get(row.id)
    assert restored.td_config.model_dump(mode="json") == config.td_config.model_dump(mode="json")
    assert restored.turn_detection_source == "provider_native"
    assert restored.td_config.priority_rule.wpm_threshold == 90


@pytest.mark.parametrize(
    "provider,model",
    [
        ("deepgram", "flux-general-en"),
        ("deepgram", "flux-general-multi"),
        ("deepgram", "nova-3"),
        ("speechmatics", "enhanced"),
        ("soniox", "stt-rt-v5"),
        ("assemblyai", "universal-3-5-pro"),
    ],
)
def test_explicit_td_settings_are_deep_copied_into_session(
    provider,
    model,
    session_request,
    runtime_config,
    voice_catalog,
    llm_catalog,
):
    """Later edits of a Bot draft cannot mutate an already created session snapshot."""
    from tests.test_td_rule_settings import priority_settings

    settings = td_settings()
    settings["priority_rule"] = priority_settings()
    request = SessionRequest.model_validate(
        {
            **session_request.model_dump(),
            "asr_provider": provider,
            "asr_model": model,
            "asr_api_key": "fixture-asr-inert-key",
            "turn_detection_source": "self_developed",
            "td_config": settings,
            "jev_api_key": "fixture-jev-inert-key",
        }
    )
    config = build_session_config(
        request=request,
        runtime=runtime_config,
        voice_catalog=voice_catalog,
        llm_catalog=llm_catalog,
    )
    assert config.asr.provider == provider and config.asr.model == model
    assert config.asr.turn_detection_source == "self_developed"
    assert config.td_config.maximum_ms == 2500
    assert config.td_config.priority_rule == request.td_config.priority_rule
    assert config.td_config.priority_rule is not request.td_config.priority_rule
    with pytest.raises(ValidationError):
        config.td_config.maximum_ms = 1
    assert "fixture-jev" not in config.model_dump_json()


def test_custom_source_without_explicit_settings_is_rejected(session_request):
    """Illustrative prototype values must not silently become production defaults."""
    with pytest.raises(ValidationError, match="td_config"):
        SessionRequest.model_validate(
            {**session_request.model_dump(), "turn_detection_source": "self_developed"}
        )


def test_text_chat_with_custom_source_does_not_require_unused_jev_key(session_request):
    """Chat test bypasses the audio detector and must not require an unused cloud key."""
    request = SessionRequest.model_validate(
        {
            **session_request.model_dump(),
            "session_type": "chat_test",
            "turn_detection_source": "self_developed",
            "td_config": td_settings(),
        }
    )
    assert request.jev_api_key is None


def test_jev_budget_is_uniform_without_hidden_ui_field():
    """D-050 permits new configurations and normalizes legacy/requested budgets to 100."""
    from src.asr.td_config import CustomTDSettings

    data = td_settings()
    data["jev"].pop("max_calls")
    assert CustomTDSettings.model_validate(data).jev.max_calls == 100
    data["jev"]["max_calls"] = 7
    assert CustomTDSettings.model_validate(data).jev.max_calls == 100
    data["jev"]["max_calls"] = 10000
    assert CustomTDSettings.model_validate(data).jev.max_calls == 100
