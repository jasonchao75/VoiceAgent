"""Formal cache APIs and publication contract without any provider call."""

import io
import json
import wave

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from src.api import create_app
from tests.test_publication import CONFIG, KEYS, ORIGIN
from tests.test_td_config import td_settings
from tests.test_td_rule_settings import priority_settings


def payload():
    """Saved inert keys and explicit rule settings exercise the same production routes."""
    settings = td_settings()
    settings["priority_rule"] = priority_settings()
    return {
        **CONFIG,
        **KEYS,
        "turn_detection_source": "self_developed",
        "td_config": settings,
        "jev_api_key": "inert-jev-fixture-key",
        "save_jev_key": True,
    }


def test_cache_generate_preview_restart_and_publish_only_check(monkeypatch):
    """Published resources are immutable and a missing/changed asset never causes implicit fees."""
    monkeypatch.setenv("VOICE_AGENT_STORAGE_KEY", Fernet.generate_key().decode())
    calls = []

    async def synthesize(unit, config, rate, *, timeout, api_key):
        calls.append((unit, config.speed))
        return b"\x01\x00" * 100

    with TestClient(create_app()) as client:
        client.app.state.echo_synthesize = synthesize
        created = client.post("/api/bots", json=payload(), headers=ORIGIN)
        assert created.status_code == 201, created.text
        bot_id = created.json()["id"]
        url = f"/api/bots/{bot_id}/echo-audio"
        before = client.get(url)
        assert before.status_code == 200, before.text
        assert all(row["status"] == "missing" for row in before.json()["assets"])
        blocked = client.post(
            f"/api/bots/{bot_id}/publish",
            headers=ORIGIN,
            json={"public_title": "Fixture", "public_description": ""},
        )
        assert blocked.status_code == 400 and "audio missing" in blocked.text
        assert calls == []
        rejected = client.post(
            url + "/generate", json={"units": ["outside-vocabulary"]}, headers=ORIGIN
        )
        assert rejected.status_code == 400 and calls == []
        generated = client.post(url + "/generate", json={}, headers=ORIGIN)
        assert generated.status_code == 200, generated.text
        assert len(calls) == 3 and all(
            row["status"] == "ready" for row in generated.json()["assets"]
        )
        asset_url = generated.json()["assets"][0]["url"]
        audio = client.get(asset_url)
        assert audio.status_code == 200
        with wave.open(io.BytesIO(audio.content), "rb") as wav:
            assert (
                wav.getframerate() == 24000 and wav.getnchannels() == 1 and wav.getsampwidth() == 2
            )
            assert wav.readframes(1000) == b"\x01\x00" * 100
        published = client.post(
            f"/api/bots/{bot_id}/publish",
            headers=ORIGIN,
            json={"public_title": "Fixture", "public_description": ""},
        )
        assert published.status_code == 200, published.text
        assert not published.json()["unpublished_changes"]
        public_id = published.json()["public_id"]
        changed = payload()
        changed["tts_speed"] = 1.2
        updated = client.put(f"/api/bots/{bot_id}", json=changed, headers=ORIGIN)
        assert updated.status_code == 200
        blocked = client.post(
            f"/api/bots/{bot_id}/publish",
            headers=ORIGIN,
            json={"public_title": "Fixture", "public_description": ""},
        )
        assert blocked.status_code == 400 and len(calls) == 3
        frozen = client.portal.call(client.app.state.publication_store.get_public, public_id)
        assert len(json.loads(frozen.config_json)["td_config"]["priority_rule"]["assets"]) == 3
        assert client.get(asset_url).content == audio.content
        assert "tts-test-key" not in generated.text
    with TestClient(create_app()) as restarted:
        status = restarted.get(url)
        assert status.status_code == 200
        assert all(row["status"] == "missing" for row in status.json()["assets"])
        assert restarted.get(asset_url).content == audio.content


def test_publish_refuses_configuration_changed_during_audio_validation(monkeypatch):
    """A successful resource check cannot authorize a different/currently edited draft."""
    from src.bots.models import BotConfigFields

    monkeypatch.setenv("VOICE_AGENT_STORAGE_KEY", Fernet.generate_key().decode())
    with TestClient(create_app()) as client:

        async def synthesize(*args, **kwargs):
            return b"\x01\x00" * 100

        client.app.state.echo_synthesize = synthesize
        created = client.post("/api/bots", json=payload(), headers=ORIGIN).json()
        bot_id = created["id"]
        assert (
            client.post(
                f"/api/bots/{bot_id}/echo-audio/generate", json={}, headers=ORIGIN
            ).status_code
            == 200
        )
        original = client.app.state.echo_cache.manifest

        async def check_then_edit(*args, **kwargs):
            resources = await original(*args, **kwargs)
            current = await client.app.state.bot_store.get(bot_id)
            config = BotConfigFields.model_validate(
                {field: getattr(current, field) for field in BotConfigFields.model_fields}
            )
            config = config.model_copy(update={"tts_speed": 1.2})
            keys = {
                name: getattr(current, name)
                for name in (
                    "encrypted_deepgram_key",
                    "encrypted_llm_key",
                    "encrypted_elevenlabs_key",
                    "llm_key_provider",
                    "asr_key_provider",
                    "encrypted_asr_key",
                    "tts_key_provider",
                    "encrypted_tts_key",
                    "encrypted_jev_key",
                    "jev_key_endpoint",
                    "asr_account_catalog",
                )
            }
            await client.app.state.bot_store.update(bot_id, config=config, **keys)
            return resources

        monkeypatch.setattr(client.app.state.echo_cache, "manifest", check_then_edit)
        result = client.post(
            f"/api/bots/{bot_id}/publish",
            headers=ORIGIN,
            json={"public_title": "Fixture", "public_description": ""},
        )
        assert result.status_code == 400 and "configuration changed" in result.text
        assert client.get(f"/api/bots/{bot_id}/share").json()["published"] is False
