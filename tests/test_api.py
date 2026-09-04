"""Non-paid FastAPI contract and secret-safe error tests."""

import base64

import pytest
from fastapi.testclient import TestClient

from src.api import create_app


def test_health_and_catalogs_do_not_call_providers() -> None:
    """Local readiness endpoints should work without any provider key."""
    with TestClient(create_app()) as client:
        health = client.get("/health")
        catalogs = client.get("/api/catalogs")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["tts_providers"] == ["deepgram_flux", "elevenlabs"]
    assert catalogs.status_code == 200
    assert "deepgram_api_key" not in catalogs.text
    assert "llm_api_key" not in catalogs.text


def test_elevenlabs_voice_discovery_sanitizes_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The proxy returns only approved voice metadata and pagination state."""

    class FakeResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "voices": [
                    {
                        "voice_id": "voice-1",
                        "name": "Support",
                        "category": "cloned",
                        "labels": {"language": "en", "gender": "female"},
                        "preview_url": "https://example.com/preview.mp3",
                        "secret_internal_field": "must-not-leak",
                    }
                ],
                "has_more": True,
                "next_page_token": "next",
            }

    class FakeClient:
        def __init__(self, *, timeout: float) -> None:
            assert timeout == 10.0

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def get(self, *args: object, **kwargs: object) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr("src.api.httpx.AsyncClient", FakeClient)
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/tts/elevenlabs/voices",
            json={"api_key": "elevenlabs-test-key"},
            headers={"Origin": "http://localhost:8000"},
        )
    assert response.status_code == 200, response.text
    assert response.json()["voices"][0]["labels"]["accent"] == "Unspecified"
    assert "secret_internal_field" not in response.text


def test_validation_error_never_echoes_rejected_key() -> None:
    """Override FastAPI's default input echo for BYOK request failures."""
    secret = "secret-that-must-never-appear"
    payload = {
        "deepgram_api_key": secret,
        "llm_api_key": "bad",
        "llm_provider": "openai",
        "llm_base_url": "https://api.openai.com/v1",
        "llm_model": "gpt-4.1-mini",
        "system_prompt": "Be helpful.",
        "opening_script": "Hello.",
        "flux_voice": "flux-alexis-en",
    }
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/sessions", json=payload, headers={"Origin": "http://localhost:8000"}
        )
    assert response.status_code == 422
    assert secret not in response.text
    assert '"bad"' not in response.text


def test_byok_rejects_unapproved_page_origin() -> None:
    """Keys cannot be submitted from an arbitrary or insecure public page."""
    payload = {
        "deepgram_api_key": "test-deepgram-key",
        "llm_api_key": "test-openai-key",
        "llm_provider": "openai",
        "llm_base_url": "https://api.openai.com/v1",
        "llm_model": "gpt-4.1-mini",
        "system_prompt": "Be helpful.",
        "opening_script": "Hello.",
        "flux_voice": "flux-alexis-en",
    }
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/sessions", json=payload, headers={"Origin": "http://unsafe.example"}
        )
    assert response.status_code == 403


def test_basic_auth_protects_public_routes_but_not_health(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Public demos should challenge page/API requests without hiding health checks."""
    username = "demo-user"
    password = "test-password-long-enough"
    monkeypatch.setenv("VOICE_AGENT_BASIC_AUTH_USERNAME", username)
    monkeypatch.setenv("VOICE_AGENT_BASIC_AUTH_PASSWORD", password)
    token = base64.b64encode(f"{username}:{password}".encode()).decode()

    with TestClient(create_app()) as client:
        health = client.get("/health")
        unauthorized = client.get("/api/catalogs")
        authorized = client.get("/api/catalogs", headers={"Authorization": f"Basic {token}"})

    assert health.status_code == 200
    assert unauthorized.status_code == 401
    assert unauthorized.headers["www-authenticate"].startswith("Basic ")
    assert authorized.status_code == 200


def test_session_bearer_failure_does_not_trigger_basic_auth_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Telemetry bearer failures must not make the browser reopen its login dialog."""
    monkeypatch.setenv("VOICE_AGENT_BASIC_AUTH_USERNAME", "demo-user")
    monkeypatch.setenv("VOICE_AGENT_BASIC_AUTH_PASSWORD", "test-password-long-enough")

    with TestClient(create_app()) as client:
        response = client.get(
            "/api/sessions/not-active/events",
            headers={"Authorization": "Bearer invalid-session-token"},
        )

    assert response.status_code == 401
    assert "www-authenticate" not in response.headers
    assert response.json()["detail"] == "Session authorization is invalid"


def test_basic_auth_rejects_incomplete_or_placeholder_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A public deployment must fail closed when its access password is unsafe."""
    monkeypatch.setenv("VOICE_AGENT_BASIC_AUTH_USERNAME", "demo-user")
    monkeypatch.delenv("VOICE_AGENT_BASIC_AUTH_PASSWORD", raising=False)
    with pytest.raises(RuntimeError, match="Both VoiceAgent Basic Auth"):
        create_app()

    monkeypatch.setenv("VOICE_AGENT_BASIC_AUTH_PASSWORD", "SET_A_STRONG_PASSWORD_BEFORE_DEPLOY")
    with pytest.raises(RuntimeError, match="at least 8 characters"):
        create_app()

    monkeypatch.setenv("VOICE_AGENT_BASIC_AUTH_PASSWORD", "only7ch")
    with pytest.raises(RuntimeError, match="at least 8 characters"):
        create_app()
