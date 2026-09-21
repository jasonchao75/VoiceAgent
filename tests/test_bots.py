"""Tests for bot persistence, encryption, the management API, and bot sessions."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlparse

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import SecretStr

from src.api import create_app
from src.bots.crypto import BotKeyCipher, StorageKeyError
from src.bots.storage import BotStore
from src.llm.diagnostics import DiagnosticConfig, LLMDiagnosticResult

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


def test_bot_persists_llm_limits_and_fallback_script(client: TestClient) -> None:
    """Per-Bot LLM limits and fallback behavior must round-trip through the API."""
    bot = _create_bot(
        client,
        llm_max_response_tokens=512,
        llm_temperature=0.3,
        llm_request_timeout_seconds=12,
        fallback_script="Please try again in a moment.",
    )
    assert bot["llm_max_response_tokens"] == 512
    assert bot["llm_temperature"] == 0.3
    assert bot["llm_request_timeout_seconds"] == 12
    assert bot["fallback_script"] == "Please try again in a moment."


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


def test_evaluation_connection_survives_restart_without_exposing_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A verified evaluation connection must persist in the shared encrypted volume."""
    storage_key = Fernet.generate_key().decode()
    plain_key = "soniox-test-key-never-returned"
    monkeypatch.setenv("VOICE_AGENT_STORAGE_KEY", storage_key)
    monkeypatch.setenv("VOICE_AGENT_DATA_DIR", str(tmp_path))

    async def fake_probe(provider: str, api_key: str, *, timeout: float) -> dict[str, object]:
        assert provider == "soniox"
        assert api_key == plain_key
        assert timeout == 10.0
        return {
            "success": True,
            "category": "ok",
            "diagnostic_id": "diag-soniox-persisted",
            "summary": "Authenticated provider probe passed.",
            "suggestion": "Ready.",
        }

    monkeypatch.setattr("src.api.test_asr_connection", fake_probe)
    with TestClient(create_app()) as first_client:
        saved = first_client.post(
            "/api/evaluation/connections/soniox/test-and-save",
            json={"api_key": plain_key},
            headers=ORIGIN,
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["connection"]["has_saved_key"] is True
        assert plain_key not in saved.text

    with sqlite3.connect(tmp_path / "evaluation.db") as database:
        encrypted = database.execute(
            "SELECT encrypted_api_key FROM evaluation_connections WHERE provider='soniox'"
        ).fetchone()
    assert encrypted is not None and encrypted[0] != plain_key

    with TestClient(create_app()) as restarted_client:
        listed = restarted_client.get("/api/evaluation/connections")
        assert listed.status_code == 200
        assert listed.json() == [
            {
                "provider": "soniox",
                "kind": "asr",
                "base_url": "https://api.soniox.com",
                "status": "verified",
                "diagnostic_id": "diag-soniox-persisted",
                "last_model_id": None,
                "verified_at": listed.json()[0]["verified_at"],
                "updated_at": listed.json()[0]["updated_at"],
                "has_saved_key": True,
            }
        ]
        assert plain_key not in listed.text


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

    response = client.post("/api/bots", json={**VALID_CONFIG, "tts_speed": 1.5}, headers=ORIGIN)
    assert response.status_code == 201

    response = client.post("/api/bots", json={**VALID_CONFIG, "tts_speed": 1.55}, headers=ORIGIN)
    assert response.status_code == 422

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


def test_diagnostic_reuses_saved_bot_key_for_another_catalog_model(
    client_with_keys: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A saved provider key may test another catalog model without changing the Bot."""
    bot = _create_bot(
        client_with_keys,
        llm_provider="google_gemini",
        llm_base_url="https://generativelanguage.googleapis.com",
        llm_model="gemini-2.5-flash-lite",
        save_keys=True,
        deepgram_api_key=DEEPGRAM_KEY,
        llm_api_key=LLM_KEY,
    )
    captured: dict[str, DiagnosticConfig] = {}

    async def fake_diagnostic(config: DiagnosticConfig) -> LLMDiagnosticResult:
        captured["config"] = config
        return LLMDiagnosticResult(
            diagnostic_id="diag-test",
            success=True,
            category="ok",
            summary="Connected.",
            suggestion="",
            provider=config.provider,
            base_url_host="generativelanguage.googleapis.com",
            model=config.model,
            first_token_ms=12.0,
            total_ms=24.0,
            reasoning_status="minimized",
        )

    monkeypatch.setattr("src.api.run_llm_diagnostic", fake_diagnostic)
    response = client_with_keys.post(
        "/api/llm/diagnostics",
        json={
            "bot_id": bot["id"],
            "llm_model": "gemini-3.8-flash",
            "reasoning_mode": "provider_default",
        },
        headers=ORIGIN,
    )

    assert response.status_code == 200, response.text
    assert response.json()["model"] == "gemini-3.8-flash"
    assert captured["config"].api_key == LLM_KEY
    assert captured["config"].base_url == "https://generativelanguage.googleapis.com"
    assert bot["llm_model"] == "gemini-2.5-flash-lite"


def test_diagnostic_rejects_uncatalogued_model_with_saved_bot_key(
    client_with_keys: TestClient,
) -> None:
    """Saved credentials cannot bypass the controlled provider model catalog."""
    bot = _create_bot(
        client_with_keys,
        llm_provider="google_gemini",
        llm_base_url="https://generativelanguage.googleapis.com",
        llm_model="gemini-2.5-flash-lite",
        save_keys=True,
        deepgram_api_key=DEEPGRAM_KEY,
        llm_api_key=LLM_KEY,
    )
    response = client_with_keys.post(
        "/api/llm/diagnostics",
        json={"bot_id": bot["id"], "llm_model": "gemini-does-not-exist"},
        headers=ORIGIN,
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Select an LLM model from the server catalog"


def test_successful_custom_diagnostic_registers_evaluation_model(
    client_with_keys: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real successful custom-model test should persist an idempotent catalog row."""
    bot = _create_bot(
        client_with_keys,
        llm_provider="custom",
        llm_base_url="https://api.deepseek.com",
        llm_model="deepseek-chat",
        save_keys=True,
        deepgram_api_key=DEEPGRAM_KEY,
        llm_api_key=LLM_KEY,
    )

    async def fake_diagnostic(config: DiagnosticConfig) -> LLMDiagnosticResult:
        return LLMDiagnosticResult(
            diagnostic_id="diag-custom-catalog",
            success=True,
            category="ok",
            summary="Connected.",
            suggestion="",
            provider=config.provider,
            base_url_host="api.deepseek.com",
            model=config.model,
            first_token_ms=10.0,
            total_ms=20.0,
            reasoning_status="unverified",
        )

    monkeypatch.setattr("src.api.run_llm_diagnostic", fake_diagnostic)
    payload = {
        "bot_id": bot["id"],
        "llm_model": "deepseek-custom-2026",
        "register_for_evaluation_catalog": True,
    }
    first = client_with_keys.post("/api/llm/diagnostics", json=payload, headers=ORIGIN)
    second = client_with_keys.post("/api/llm/diagnostics", json=payload, headers=ORIGIN)

    assert first.status_code == 200, first.text
    assert first.json()["evaluation_catalog_registered"] is True
    assert first.json()["evaluation_provider"] == "DeepSeek"
    assert second.status_code == 200, second.text
    catalog = client_with_keys.get("/api/evaluation/llm-models")
    assert catalog.status_code == 200
    assert len(catalog.json()) == 1
    assert catalog.json()[0]["provider"] == "DeepSeek"
    assert catalog.json()[0]["model_id"] == "deepseek-custom-2026"
    assert catalog.json()[0]["base_url_host"] == "api.deepseek.com"


def test_azure_and_openrouter_connections_are_isolated_and_provider_qualified(
    client_with_keys: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Azure and OpenRouter may register the same model ID without sharing secrets."""
    seen: list[DiagnosticConfig] = []

    async def fake_diagnostic(config: DiagnosticConfig) -> LLMDiagnosticResult:
        seen.append(config)
        return LLMDiagnosticResult(
            diagnostic_id=f"diag-{config.provider}",
            success=True,
            category="ok",
            summary="Connected.",
            suggestion="",
            provider=config.provider,
            base_url_host=urlparse(config.base_url).hostname or "",
            model=config.model,
            first_token_ms=10.0,
            total_ms=20.0,
            reasoning_status="unverified",
        )

    monkeypatch.setattr("src.api.run_llm_diagnostic", fake_diagnostic)
    azure_key = "azure-secret-never-returned"
    openrouter_key = "openrouter-secret-never-returned"
    azure_url = (
        "https://example-resource.openai.azure.com/openai/deployments/gpt-4o/"
        "chat/completions?api-version=2025-01-01-preview"
    )
    azure = client_with_keys.post(
        "/api/evaluation/connections/azure_gpt/test-and-save",
        json={
            "api_key": azure_key,
            "base_url": azure_url,
            "model_id": "gpt-4o",
            "register_for_evaluation_catalog": True,
        },
        headers=ORIGIN,
    )
    openrouter = client_with_keys.post(
        "/api/evaluation/connections/openrouter/test-and-save",
        json={
            "api_key": openrouter_key,
            "model_id": "gpt-4o",
            "register_for_evaluation_catalog": True,
        },
        headers=ORIGIN,
    )

    assert azure.status_code == openrouter.status_code == 200
    assert seen[0].provider == "azure_openai"
    assert seen[0].base_url == azure_url
    assert seen[1].provider == "custom"
    assert seen[1].base_url == "https://openrouter.ai/api/v1"
    connections = client_with_keys.get("/api/evaluation/connections")
    assert connections.status_code == 200
    assert {item["provider"] for item in connections.json()} >= {
        "azure_gpt",
        "openrouter",
    }
    assert azure_key not in connections.text
    assert openrouter_key not in connections.text
    catalog = client_with_keys.get("/api/evaluation/llm-models").json()
    duplicates = [item for item in catalog if item["model_id"] == "gpt-4o"]
    assert {item["provider"] for item in duplicates} == {"Azure GPT", "OpenRouter"}


@pytest.mark.parametrize(
    "base_url",
    [
        "https://dashscope.aliyuncs.com/api/v1",
        "https://prem.dashscope.aliyuncs.com/api/v1",
        "https://ws-demo.cn-beijing.maas.aliyuncs.com/api/v1",
    ],
)
def test_qwen_native_endpoints_register_as_qwen(
    client_with_keys: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    base_url: str,
) -> None:
    """Both premium and workspace-native URLs must retain the Qwen provider identity."""

    async def fake_diagnostic(config: DiagnosticConfig) -> LLMDiagnosticResult:
        return LLMDiagnosticResult(
            diagnostic_id="diag-qwen-native",
            success=True,
            category="ok",
            summary="Connected.",
            suggestion="",
            provider=config.provider,
            base_url_host=urlparse(config.base_url).hostname or "",
            model=config.model,
            first_token_ms=10.0,
            total_ms=20.0,
            reasoning_status="unverified",
        )

    monkeypatch.setattr("src.api.run_llm_diagnostic", fake_diagnostic)
    response = client_with_keys.post(
        "/api/evaluation/connections/qwen/test-and-save",
        json={
            "api_key": "qwen-secret-never-returned",
            "base_url": base_url,
            "model_id": "qwen3.8-max",
            "register_for_evaluation_catalog": True,
        },
        headers=ORIGIN,
    )

    assert response.status_code == 200, response.text
    assert response.json()["evaluation_provider"] == "Qwen"


def test_unknown_custom_endpoint_cannot_register_evaluation_model(
    client_with_keys: TestClient,
) -> None:
    """An arbitrary OpenAI-compatible endpoint must not enter the product catalog."""
    bot = _create_bot(
        client_with_keys,
        llm_provider="custom",
        llm_base_url="https://models.example.com/v1",
        llm_model="private-model",
        save_keys=True,
        deepgram_api_key=DEEPGRAM_KEY,
        llm_api_key=LLM_KEY,
    )
    response = client_with_keys.post(
        "/api/llm/diagnostics",
        json={
            "bot_id": bot["id"],
            "llm_model": "private-model-v2",
            "register_for_evaluation_catalog": True,
        },
        headers=ORIGIN,
    )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "This endpoint is not a supported evaluation model provider"
    )
    assert client_with_keys.get("/api/evaluation/llm-models").json() == []


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
