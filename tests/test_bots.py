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


# --- management API ----------------------------------------------------------


def test_bot_crud_without_saved_keys(client: TestClient) -> None:
    created = _create_bot(client)
    assert created["has_saved_keys"] is False
    assert created["name"] == "Support bot"
    assert "deepgram_api_key" not in created
    assert "llm_api_key" not in created

    listing = client.get("/api/bots", headers=ORIGIN)
    assert listing.status_code == 200
    assert [bot["id"] for bot in listing.json()] == [created["id"]]

    fetched = client.get(f"/api/bots/{created['id']}", headers=ORIGIN)
    assert fetched.status_code == 200
    assert fetched.json()["tts_voice"] == "flux-alexis-en"

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
        "tts_model": "eleven_flash_v2_5",
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
    assert created.json()["tts_model"] == "eleven_flash_v2_5"
    session = client_with_keys.post(
        "/api/sessions", json={"bot_id": created.json()["id"]}, headers=ORIGIN
    )
    assert session.status_code == 201, session.text


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
