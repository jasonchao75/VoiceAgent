"""Non-network tests for multi-provider Bot ASR configuration persistence."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.bots.models import BotConfigFields
from src.bots.storage import BotStore
from src.bots.validation import validate_asr_account_catalog


def _base_config(**overrides: object) -> BotConfigFields:
    """Build one valid Bot while allowing ASR-specific overrides."""
    values: dict[str, object] = {
        "name": "ASR test bot",
        "asr_provider": "deepgram",
        "asr_model": "flux-general-en",
        "tts_provider": "deepgram_flux",
        "tts_voice": "flux-alexis-en",
        "llm_provider": "openai",
        "llm_base_url": "https://api.openai.com/v1",
        "llm_model": "gpt-4.1-mini",
        "system_prompt": "Be helpful.",
        "opening_script": "Hello.",
    }
    values.update(overrides)
    return BotConfigFields.model_validate(values)


@pytest.mark.parametrize(
    ("provider", "model", "turn_source", "options"),
    [
        ("deepgram", "nova-3", "off", {"language": "ar-SA", "endpointing_ms": 300}),
        (
            "speechmatics",
            "enhanced",
            "off",
            {
                "language": "ar_en",
                "turn_detection_mode": "fixed",
                "end_of_utterance_silence_trigger": 0.5,
                "end_of_utterance_max_delay": 10.0,
            },
        ),
        ("soniox", "stt-rt-v5", "provider_native", {"language_hints": ["ar", "en"]}),
        (
            "assemblyai",
            "universal-3-5-pro",
            "provider_native",
            {"language_codes": ["ar", "en"], "mode": "balanced"},
        ),
    ],
)
def test_bot_accepts_strict_provider_options(
    provider: str, model: str, turn_source: str, options: dict[str, object]
) -> None:
    """Every confirmed provider branch normalizes into versioned JSON."""
    config = _base_config(
        asr_provider=provider,
        asr_model=model,
        turn_detection_source=turn_source,
        asr_options=options,
    )
    assert config.asr_options["schema_version"] == 1


def test_bot_rejects_cross_provider_fields() -> None:
    """A stale UI branch cannot submit Flux fields to AssemblyAI."""
    with pytest.raises(ValidationError, match="eot_threshold"):
        _base_config(
            asr_provider="assemblyai",
            asr_model="universal-3-5-pro",
            asr_options={"eot_threshold": 0.7},
        )


def test_speechmatics_rejects_marks_outside_language_pack_catalog() -> None:
    """Arbitrary Unicode symbols cannot be sent as Speechmatics punctuation."""
    with pytest.raises(ValidationError, match="Language Pack catalog"):
        _base_config(
            asr_provider="speechmatics",
            asr_model="enhanced",
            asr_options={
                "language": "ar_en",
                "punctuation_overrides": {
                    "sensitivity": 0.5,
                    "permitted_marks": ["😀"],
                },
            },
        )


@pytest.mark.asyncio
async def test_provider_options_round_trip_and_legacy_flux_migration(tmp_path: Path) -> None:
    """SQLite stores strict JSON and maps the legacy provider ID without behavior loss."""
    database_path = tmp_path / "bots.db"
    with sqlite3.connect(database_path) as database:
        database.execute(
            """CREATE TABLE bots (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, asr_provider TEXT NOT NULL,
                tts_provider TEXT NOT NULL, tts_voice TEXT NOT NULL,
                llm_provider TEXT NOT NULL, llm_base_url TEXT NOT NULL,
                llm_model TEXT NOT NULL, system_prompt TEXT NOT NULL,
                opening_script TEXT NOT NULL, encrypted_deepgram_key TEXT,
                encrypted_llm_key TEXT, encrypted_elevenlabs_key TEXT,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )"""
        )
        database.execute(
            """INSERT INTO bots (
                id, name, asr_provider, tts_provider, tts_voice, llm_provider,
                llm_base_url, llm_model, system_prompt, opening_script, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "legacy-flux",
                "Legacy Flux",
                "deepgram_flux",
                "deepgram_flux",
                "flux-alexis-en",
                "openai",
                "https://api.openai.com/v1",
                "gpt-4.1-mini",
                "Be helpful.",
                "Hello.",
                "now",
                "now",
            ),
        )

    store = BotStore(database_path)
    await store.initialize()
    legacy = await store.get("legacy-flux")
    assert legacy is not None
    assert legacy.asr_provider == "deepgram"
    assert legacy.asr_model == "flux-general-en"
    assert legacy.asr_options["eot_threshold"] == 0.7

    created = await store.create(
        config=_base_config(
            asr_provider="assemblyai",
            asr_model="universal-3-5-pro",
            asr_options={"language_codes": ["ar", "en"]},
        ),
        encrypted_deepgram_key=None,
        encrypted_llm_key=None,
        encrypted_elevenlabs_key=None,
    )
    reloaded = await store.get(created.id)
    assert reloaded is not None
    assert reloaded.asr_options["language_codes"] == ["ar", "en"]


@pytest.mark.asyncio
async def test_account_catalog_persists_and_blocks_unavailable_language(tmp_path: Path) -> None:
    """Restart-safe account discovery must govern later saves and sessions."""
    store = BotStore(tmp_path / "bots.db")
    await store.initialize()
    created = await store.create(
        config=_base_config(
            asr_provider="speechmatics",
            asr_model="enhanced",
            asr_options={"language": "en", "domain": "finance"},
        ),
        encrypted_deepgram_key=None,
        encrypted_llm_key=None,
        encrypted_elevenlabs_key=None,
    )
    catalog = {
        "id": "enhanced",
        "language_control": {"kind": "single", "values": ["en"]},
        "domains_by_language": {"en": ["finance"]},
    }
    await store.set_asr_account_catalog(created.id, catalog)

    restarted = BotStore(tmp_path / "bots.db")
    await restarted.initialize()
    loaded = await restarted.get(created.id)
    assert loaded is not None
    assert loaded.asr_account_catalog == catalog
    validate_asr_account_catalog(loaded, loaded.asr_account_catalog)

    unsupported = _base_config(
        asr_provider="speechmatics",
        asr_model="enhanced",
        asr_options={"language": "ar_en", "domain": "medical"},
    )
    with pytest.raises(ValueError, match="unavailable for this Bot account"):
        validate_asr_account_catalog(unsupported, loaded.asr_account_catalog)
