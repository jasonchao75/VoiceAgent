"""Tests for bot persistence, encryption, the management API, and bot sessions."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import SecretStr

from src.api import create_app
from src.bots.crypto import BotKeyCipher, StorageKeyError
from src.bots.storage import BotStore

VALID_CONFIG = {
    "name": "Support bot",
    "asr_provider": "deepgram_flux",
    "tts_provider": "deepgram_flux",
    "tts_voice": "flux-alexis-en",
    "llm_provider": "openai",
    "llm_base_url": "https://api.openai.com/v1",
    "llm_model": "gpt-4.1-mini",
    "system_prompt": "You are a helpful assistant.",
    "opening_script": "Hi there!",
}

DEEPGRAM_KEY = "dg-test-key-0000000001"
LLM_KEY = "llm-test-key-0000000001"
ELEVENLABS_KEY = "elevenlabs-test-key-0000000001"
ORIGIN = {"Origin": "http://localhost:8000"}


@pytest.fixture
def storage_key(monkeypatch: pytest.MonkeyPatch) -> str:
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("VOICE_AGENT_STORAGE_KEY", key)
    return key


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def client_with_keys(storage_key: str) -> Iterator[TestClient]:
    """App built after the master key is configured; fixture order matters."""
    with TestClient(create_app()) as test_client:
        yield test_client


def _create_bot(client: TestClient, **overrides: object) -> dict:
    payload = {**VALID_CONFIG, **overrides}
    response = client.post("/api/bots", json=payload, headers=ORIGIN)
    assert response.status_code == 201, response.text
    return response.json()


# --- crypto -----------------------------------------------------------------


def test_cipher_roundtrip_and_wrong_key() -> None:
    cipher = BotKeyCipher(Fernet.generate_key().decode())
    token = cipher.encrypt(SecretStr("super-secret"))
    assert "super-secret" not in token
    assert cipher.decrypt(token).get_secret_value() == "super-secret"

    other = BotKeyCipher(Fernet.generate_key().decode())
    with pytest.raises(StorageKeyError, match="cannot be decrypted"):
        other.decrypt(token)


def test_cipher_rejects_malformed_master_key() -> None:
    with pytest.raises(StorageKeyError, match="not a valid Fernet key"):
        BotKeyCipher("not-a-fernet-key")


@pytest.mark.asyncio
async def test_legacy_bots_receive_provider_compatible_aggregation(tmp_path: Path) -> None:
    """Migration preserves the pre-setting provider behavior for existing bots."""
    database_path = tmp_path / "bots.db"
    columns = """id, name, asr_provider, tts_provider, tts_voice, tts_model,
        llm_provider, llm_base_url, llm_model, reasoning_mode, system_prompt,
        opening_script, encrypted_deepgram_key, encrypted_llm_key,
        encrypted_elevenlabs_key, created_at, updated_at"""
    with sqlite3.connect(database_path) as database:
        database.execute(
            """CREATE TABLE bots (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, asr_provider TEXT NOT NULL,
                tts_provider TEXT NOT NULL, tts_voice TEXT NOT NULL,
                tts_model TEXT NOT NULL, llm_provider TEXT NOT NULL,
                llm_base_url TEXT NOT NULL, llm_model TEXT NOT NULL,
                reasoning_mode TEXT NOT NULL, system_prompt TEXT NOT NULL,
                opening_script TEXT NOT NULL, encrypted_deepgram_key TEXT,
                encrypted_llm_key TEXT, encrypted_elevenlabs_key TEXT,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )"""
        )
        values = (
            "legacy-eleven",
            "Legacy Eleven",
            "deepgram_flux",
            "elevenlabs",
            "voice-1",
            "eleven_flash_v2_5",
            "openai",
            "https://api.openai.com/v1",
            "gpt-4.1-mini",
            "lowest_latency",
            "Prompt",
            "Hello",
            None,
            None,
            None,
            "now",
            "now",
        )
        database.execute(
            f"INSERT INTO bots ({columns}) VALUES ({', '.join('?' for _ in values)})",
            values,
        )

    store = BotStore(database_path)
    await store.initialize()
    record = await store.get("legacy-eleven")
    assert record is not None
    assert record.tts_text_aggregation == "sentence"
    assert record.tts_expressivity == 0


# --- management API ----------------------------------------------------------


def test_bot_crud_without_saved_keys(client: TestClient) -> None:
    created = _create_bot(client, tts_speed=1.05, tts_expressivity=1)
    assert created["has_saved_keys"] is False
    assert created["name"] == "Support bot"
    assert created["tts_speed"] == 1.05
    assert created["tts_expressivity"] == 1
    assert "deepgram_api_key" not in created
    assert "llm_api_key" not in created

    listing = client.get("/api/bots", headers=ORIGIN)
    assert listing.status_code == 200
    assert [bot["id"] for bot in listing.json()] == [created["id"]]

    fetched = client.get(f"/api/bots/{created['id']}", headers=ORIGIN)
    assert fetched.status_code == 200
    assert fetched.json()["tts_voice"] == "flux-alexis-en"
    assert fetched.json()["tts_expressivity"] == 1

    updated = client.put(
        f"/api/bots/{created['id']}",
        json={**VALID_CONFIG, "name": "Renamed bot"},
        headers=ORIGIN,
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Renamed bot"
    assert updated.json()["created_at"] == created["created_at"]

    deleted = client.delete(f"/api/bots/{created['id']}", headers=ORIGIN)
    assert deleted.status_code == 204
    assert client.get(f"/api/bots/{created['id']}", headers=ORIGIN).status_code == 404


def test_bot_validation_uses_catalogs(client: TestClient) -> None:
    response = client.post(
        "/api/bots", json={**VALID_CONFIG, "tts_voice": "not-a-voice"}, headers=ORIGIN
    )
    assert response.status_code == 400

    response = client.post(
        "/api/bots", json={**VALID_CONFIG, "llm_provider": "unknown"}, headers=ORIGIN
    )
    assert response.status_code == 400

    response = client.post(
        "/api/bots",
        json={**VALID_CONFIG, "llm_base_url": "https://evil.example.com/v1"},
        headers=ORIGIN,
    )
    assert response.status_code == 400

    response = client.post(
        "/api/bots", json={**VALID_CONFIG, "asr_provider": "other-asr"}, headers=ORIGIN
    )
    assert response.status_code == 400

    response = client.post("/api/bots", json={**VALID_CONFIG, "tts_speed": 1.2}, headers=ORIGIN)
    assert response.status_code == 400

    response = client.post(
        "/api/bots", json={**VALID_CONFIG, "tts_expressivity": 1.5}, headers=ORIGIN
    )
    assert response.status_code == 422


def test_saving_keys_requires_storage_key(client: TestClient) -> None:
    response = client.post(
        "/api/bots",
        json={
            **VALID_CONFIG,
            "save_keys": True,
            "deepgram_api_key": DEEPGRAM_KEY,
            "llm_api_key": LLM_KEY,
        },
        headers=ORIGIN,
    )
    assert response.status_code == 400
    assert "VOICE_AGENT_STORAGE_KEY" in response.json()["detail"]


def test_saved_keys_are_encrypted_and_never_returned(
    client_with_keys: TestClient, tmp_path: Path
) -> None:
    created = _create_bot(
        client_with_keys,
        save_keys=True,
        deepgram_api_key=DEEPGRAM_KEY,
        llm_api_key=LLM_KEY,
    )
    assert created["has_saved_keys"] is True

    for response in (
        client_with_keys.get("/api/bots", headers=ORIGIN),
        client_with_keys.get(f"/api/bots/{created['id']}", headers=ORIGIN),
    ):
        assert response.status_code == 200
        assert DEEPGRAM_KEY not in response.text
        assert LLM_KEY not in response.text

    # The database file itself must only hold ciphertext.
    db = sqlite3.connect(tmp_path / "bots.db")
    row = db.execute(
        "SELECT encrypted_deepgram_key, encrypted_llm_key FROM bots WHERE id = ?",
        (created["id"],),
    ).fetchone()
    db.close()
    assert row is not None and row[0] and row[1]
    assert DEEPGRAM_KEY not in row[0] and LLM_KEY not in row[1]
    assert "encrypted_deepgram_key" not in created


def test_update_key_tristate(client_with_keys: TestClient) -> None:
    created = _create_bot(
        client_with_keys,
        save_keys=True,
        deepgram_api_key=DEEPGRAM_KEY,
        llm_api_key=LLM_KEY,
    )

    # Keep: update config only, keys stay stored.
    kept = client_with_keys.put(
        f"/api/bots/{created['id']}",
        json={**VALID_CONFIG, "save_keys": True, "system_prompt": "New prompt."},
        headers=ORIGIN,
    )
    assert kept.status_code == 200
    assert kept.json()["has_saved_keys"] is True

    # Replace: new pair accepted.
    replaced = client_with_keys.put(
        f"/api/bots/{created['id']}",
        json={
            **VALID_CONFIG,
            "save_keys": True,
            "deepgram_api_key": "dg-test-key-0000000002",
            "llm_api_key": "llm-test-key-0000000002",
        },
        headers=ORIGIN,
    )
    assert replaced.status_code == 200
    assert replaced.json()["has_saved_keys"] is True

    # Clear: save_keys=false drops the stored pair.
    cleared = client_with_keys.put(
        f"/api/bots/{created['id']}",
        json={**VALID_CONFIG, "save_keys": False},
        headers=ORIGIN,
    )
    assert cleared.status_code == 200
    assert cleared.json()["has_saved_keys"] is False

    # Keep semantics on a bot without keys is an error.
    response = client_with_keys.put(
        f"/api/bots/{created['id']}",
        json={**VALID_CONFIG, "save_keys": True},
        headers=ORIGIN,
    )
    assert response.status_code == 400


# --- sessions from bots ------------------------------------------------------


def test_session_from_saved_key_bot_needs_no_keys(client_with_keys: TestClient) -> None:
    bot = _create_bot(
        client_with_keys,
        save_keys=True,
        deepgram_api_key=DEEPGRAM_KEY,
        llm_api_key=LLM_KEY,
    )
    response = client_with_keys.post("/api/sessions", json={"bot_id": bot["id"]}, headers=ORIGIN)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["session_token"] and body["websocket_path"]

    # Keys must not be submitted for a bot that already stores them.
    rejected = client_with_keys.post(
        "/api/sessions",
        json={"bot_id": bot["id"], "deepgram_api_key": DEEPGRAM_KEY, "llm_api_key": LLM_KEY},
        headers=ORIGIN,
    )
    assert rejected.status_code == 422


def test_session_from_byok_bot_requires_session_keys(client: TestClient) -> None:
    bot = _create_bot(client)
    missing = client.post("/api/sessions", json={"bot_id": bot["id"]}, headers=ORIGIN)
    assert missing.status_code == 422

    provided = client.post(
        "/api/sessions",
        json={"bot_id": bot["id"], "deepgram_api_key": DEEPGRAM_KEY, "llm_api_key": LLM_KEY},
        headers=ORIGIN,
    )
    assert provided.status_code == 201, provided.text


def test_session_request_rejects_mixed_bot_and_inline_config(client: TestClient) -> None:
    bot = _create_bot(client)
    response = client.post(
        "/api/sessions",
        json={"bot_id": bot["id"], "system_prompt": "inline override"},
        headers=ORIGIN,
    )
    assert response.status_code == 422


def test_session_from_unknown_bot_is_404(client: TestClient) -> None:
    response = client.post("/api/sessions", json={"bot_id": "missing"}, headers=ORIGIN)
    assert response.status_code == 404


def test_elevenlabs_bot_requires_and_uses_provider_key(client_with_keys: TestClient) -> None:
    """ElevenLabs bots persist and resolve all three required provider keys."""
    config = {
        **VALID_CONFIG,
        "tts_provider": "elevenlabs",
        "tts_voice": "test-elevenlabs-voice-id",
        "tts_model": "eleven_turbo_v2_5",
        "tts_text_aggregation": "sentence",
        "tts_speed": 1.1,
        "tts_stability": 0.7,
        "tts_similarity_boost": 0.65,
        "tts_style": 0.2,
        "tts_use_speaker_boost": True,
        "tts_text_normalization": "on",
        "save_keys": True,
        "deepgram_api_key": DEEPGRAM_KEY,
        "llm_api_key": LLM_KEY,
    }
    missing = client_with_keys.post("/api/bots", json=config, headers=ORIGIN)
    assert missing.status_code == 422

    created = client_with_keys.post(
        "/api/bots",
        json={**config, "elevenlabs_api_key": ELEVENLABS_KEY},
        headers=ORIGIN,
    )
    assert created.status_code == 201, created.text
    assert created.json()["has_saved_keys"] is True
    assert created.json()["tts_model"] == "eleven_turbo_v2_5"
    assert created.json()["tts_text_aggregation"] == "sentence"
    assert created.json()["tts_speed"] == 1.1
    assert created.json()["tts_stability"] == 0.7
    assert created.json()["tts_similarity_boost"] == 0.65
    assert created.json()["tts_style"] == 0.2
    assert created.json()["tts_use_speaker_boost"] is True
    assert created.json()["tts_text_normalization"] == "on"
    session = client_with_keys.post(
        "/api/sessions", json={"bot_id": created.json()["id"]}, headers=ORIGIN
    )
    assert session.status_code == 201, session.text


def test_eleven_v3_accepts_only_supported_stability_presets(client: TestClient) -> None:
    """Eleven v3 accepts its discrete stability contract and all four models are valid."""
    for model in (
        "eleven_flash_v2_5",
        "eleven_turbo_v2_5",
        "eleven_multilingual_v2",
        "eleven_v3",
    ):
        created = _create_bot(
            client,
            name=model,
            tts_provider="elevenlabs",
            tts_voice="test-elevenlabs-voice-id",
            tts_model=model,
            tts_stability=1.0,
        )
        assert created["tts_model"] == model

    rejected = client.post(
        "/api/bots",
        json={
            **VALID_CONFIG,
            "tts_provider": "elevenlabs",
            "tts_voice": "test-elevenlabs-voice-id",
            "tts_model": "eleven_v3",
            "tts_stability": 0.7,
        },
        headers=ORIGIN,
    )
    assert rejected.status_code == 400
    assert "stability" in rejected.json()["detail"]


def test_saved_key_bot_degrades_without_storage_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("VOICE_AGENT_STORAGE_KEY", key)
    with TestClient(create_app()) as first_client:
        bot = _create_bot(
            first_client,
            save_keys=True,
            deepgram_api_key=DEEPGRAM_KEY,
            llm_api_key=LLM_KEY,
        )

    # Restart without the master key: the app boots but cannot use stored keys.
    monkeypatch.delenv("VOICE_AGENT_STORAGE_KEY")
    with TestClient(create_app()) as second_client:
        assert second_client.get("/api/bots", headers=ORIGIN).status_code == 200
        response = second_client.post("/api/sessions", json={"bot_id": bot["id"]}, headers=ORIGIN)
        assert response.status_code == 400
        assert "VOICE_AGENT_STORAGE_KEY" in response.json()["detail"]

    # A different master key cannot decrypt the stored pair either.
    monkeypatch.setenv("VOICE_AGENT_STORAGE_KEY", Fernet.generate_key().decode())
    with TestClient(create_app()) as third_client:
        response = third_client.post("/api/sessions", json={"bot_id": bot["id"]}, headers=ORIGIN)
        assert response.status_code == 400
