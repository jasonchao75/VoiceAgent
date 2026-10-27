"""Backend-only Jev credentials follow independent explicit save intent."""

import sqlite3

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from src.api import create_app
from tests.test_bots import ORIGIN, VALID_CONFIG
from tests.test_td_config import td_settings


def test_jev_key_is_encrypted_redacted_and_bound_to_endpoint(monkeypatch, tmp_path):
    """A changed endpoint cannot silently inherit a credential meant for another receiver."""
    monkeypatch.setenv("VOICE_AGENT_STORAGE_KEY", Fernet.generate_key().decode())
    secret = "test-fixture-jev-secret-12345"
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/bots",
            headers=ORIGIN,
            json={
                **VALID_CONFIG,
                "td_config": td_settings(),
                "jev_api_key": secret,
                "save_jev_key": True,
            },
        )
        assert response.status_code == 201, response.text
        assert secret not in response.text and "encrypted_jev_key" not in response.text
        bot = response.json()
        assert bot["has_jev_key"]
        response = client.put(
            f"/api/bots/{bot['id']}",
            headers=ORIGIN,
            json={
                **VALID_CONFIG,
                "td_config": td_settings(),
            },
        )
        assert response.status_code == 200 and response.json()["has_jev_key"]
        settings = td_settings()
        settings["jev"]["endpoint"] = "https://other.example/v1/systemone"
        response = client.put(
            f"/api/bots/{bot['id']}",
            headers=ORIGIN,
            json={
                **VALID_CONFIG,
                "td_config": settings,
            },
        )
        assert response.status_code == 200 and not response.json()["has_jev_key"]
    with sqlite3.connect(tmp_path / "bots.db") as database:
        columns = [row[1] for row in database.execute("PRAGMA table_info(bots)")]
        assert "encrypted_jev_key" in columns
        assert secret.encode() not in (tmp_path / "bots.db").read_bytes()
