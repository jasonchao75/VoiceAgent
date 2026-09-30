"""Integration tests for Bot publication, stable links, and public admission."""

from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from src.api import (
    BrowserEvent,
    ShortWindowRateLimiter,
    _ice_server_urls,
    _validate_webrtc_deployment,
    create_app,
)
from src.auth import ProductAuthMiddleware

ORIGIN = {"Origin": "http://localhost:8000"}
CONFIG = {
    "name": "Maya",
    "asr_provider": "deepgram",
    "asr_model": "flux-general-en",
    "tts_provider": "deepgram_flux",
    "tts_voice": "flux-alexis-en",
    "llm_provider": "openai",
    "llm_base_url": "https://api.openai.com/v1",
    "llm_model": "gpt-4.1-mini",
    "system_prompt": "Help the caller.",
    "opening_script": "Hello!",
}
KEYS = {
    "save_asr_key": True,
    "save_tts_key": True,
    "save_llm_key": True,
    "asr_api_key": "asr-test-key-00000001",
    "tts_api_key": "tts-test-key-00000001",
    "llm_api_key": "llm-test-key-00000001",
}


@pytest.fixture
def keyed_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Build the app after enabling encrypted Bot credential storage."""
    monkeypatch.setenv("VOICE_AGENT_STORAGE_KEY", Fernet.generate_key().decode())
    with TestClient(create_app()) as client:
        yield client


def _create_and_publish(client: TestClient) -> tuple[dict[str, object], dict[str, object]]:
    created = client.post("/api/bots", json={**CONFIG, **KEYS}, headers=ORIGIN)
    assert created.status_code == 201, created.text
    bot = created.json()
    published = client.post(
        f"/api/bots/{bot['id']}/publish",
        json={"public_title": "Maya · Voice guide", "public_description": "Call Maya."},
        headers=ORIGIN,
    )
    assert published.status_code == 200, published.text
    return bot, published.json()


def test_public_auth_allowlist_is_exact() -> None:
    """Keep public demo routes open without widening access to management APIs."""
    allowed = (
        "/demo/opaque-id",
        "/api/public/demos/opaque-id",
        "/api/public/demos/opaque-id/sessions",
        "/api/public/demos/opaque-id/events",
        "/api/public/webrtc/capability",
    )
    denied = (
        "/api/public/demos",
        "/api/public/demos/opaque-id/admin",
        "/api/public/demos/opaque-id/events/admin",
        "/api/public/webrtc",
        "/api/bots/bot-id/share",
    )
    assert all(ProductAuthMiddleware._is_public(path) for path in allowed)
    assert not any(ProductAuthMiddleware._is_public(path) for path in denied)


def test_mobile_network_event_schema_excludes_addresses_and_content() -> None:
    """Accept only coarse deployment telemetry without SDP, IP, or transcript fields."""
    event = BrowserEvent(
        event="mobile_webrtc_connected",
        elapsed_ms=842.5,
        candidate_type="srflx",
        network_type="4g",
    )
    assert event.candidate_type == "srflx"
    with pytest.raises(ValueError):
        BrowserEvent.model_validate(
            {
                "event": "mobile_webrtc_connected",
                "elapsed_ms": 1,
                "candidate_type": "198.51.100.8",
            }
        )
    with pytest.raises(ValueError):
        BrowserEvent.model_validate(
            {
                "event": "mobile_webrtc_connected",
                "elapsed_ms": 1,
                "sdp": "private signaling content",
            }
        )
    with pytest.raises(ValueError, match="cannot include text"):
        BrowserEvent.model_validate(
            {
                "event": "mobile_call_error",
                "elapsed_ms": 1,
                "text": "a transcript must never be accepted here",
            }
        )


def test_public_rate_limit_uses_opaque_short_lived_buckets() -> None:
    """Avoid retaining complete client IPs or stale process-lifetime keys."""
    now = [100.0]
    limiter = ShortWindowRateLimiter(
        limit=1,
        window_seconds=60,
        clock=lambda: now[0],
        salt=b"test-only-salt",
    )
    assert limiter.allow(scope="event", public_id="demo-a", client="198.51.100.8")
    assert not limiter.allow(scope="event", public_id="demo-a", client="198.51.100.8")
    assert limiter.active_bucket_count == 1
    assert all(isinstance(key, bytes) for key in limiter._buckets)
    assert b"198.51.100.8" not in b"".join(limiter._buckets)

    now[0] = 161.0
    assert limiter.allow(scope="event", public_id="demo-b", client="203.0.113.9")
    assert limiter.active_bucket_count == 1


def test_ice_configuration_accepts_stun_and_rejects_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep the first release's no-TURN decision enforced by configuration."""
    monkeypatch.setenv("VOICE_AGENT_STUN_URLS", "stun:one.example:3478,stuns:two.example:5349")
    assert _ice_server_urls() == ["stun:one.example:3478", "stuns:two.example:5349"]
    monkeypatch.setenv("VOICE_AGENT_STUN_URLS", "turn:relay.example:3478")
    with pytest.raises(RuntimeError, match="only stun"):
        _ice_server_urls()


def test_production_webrtc_requires_stun_and_host_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prevent production from publishing a known-unreachable WebRTC path."""
    monkeypatch.setenv("VOICE_AGENT_DEPLOYMENT_ENVIRONMENT", "production")
    monkeypatch.delenv("VOICE_AGENT_WEBRTC_HOST_NETWORK", raising=False)
    with pytest.raises(RuntimeError, match="STUN"):
        _validate_webrtc_deployment([])
    with pytest.raises(RuntimeError, match="host networking"):
        _validate_webrtc_deployment(["stun:stun.example:3478"])
    monkeypatch.setenv("VOICE_AGENT_WEBRTC_HOST_NETWORK", "true")
    _validate_webrtc_deployment(["stun:stun.example:3478"])


def test_publication_is_stable_private_and_uses_shared_capacity(
    keyed_client: TestClient,
) -> None:
    """Publish one safe locator and admit only zero-config mobile sessions."""
    _bot, share = _create_and_publish(keyed_client)
    assert share["published"] is True
    assert share["active"] is True
    assert share["available"] is True
    assert len(str(share["public_id"])) >= 24

    metadata = keyed_client.get(f"/api/public/demos/{share['public_id']}")
    assert metadata.status_code == 200
    assert metadata.json() == {
        "public_id": share["public_id"],
        "title": "Maya · Voice guide",
        "description": "Call Maya.",
        "active": True,
        "available": True,
    }
    assert "prompt" not in metadata.text.lower()
    assert "key" not in metadata.text.lower()

    rejected = keyed_client.post(
        f"/api/public/demos/{share['public_id']}/sessions",
        json={"bot_id": "override"},
        headers=ORIGIN,
    )
    assert rejected.status_code == 422

    sessions = [
        keyed_client.post(
            f"/api/public/demos/{share['public_id']}/sessions",
            json={},
            headers=ORIGIN,
        )
        for _ in range(4)
    ]
    assert [response.status_code for response in sessions] == [201, 201, 201, 429]
    assert sessions[0].json()["connection_url"].startswith("/api/public/webrtc/")
    assert sessions[0].json()["ice_servers"] == []
    assert sessions[0].headers["cache-control"] == "no-store"


def test_public_funnel_events_are_bounded_and_do_not_log_raw_link(
    keyed_client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Capture safe pre-session outcomes without persisting the bearer-like locator."""
    _bot, share = _create_and_publish(keyed_client)
    public_id = str(share["public_id"])
    with caplog.at_level("INFO", logger="src.api"):
        viewed = keyed_client.post(
            f"/api/public/demos/{public_id}/events",
            json={"event": "mobile_demo_view", "elapsed_ms": 12.3},
            headers=ORIGIN,
        )
        permission = keyed_client.post(
            f"/api/public/demos/{public_id}/events",
            json={
                "event": "mobile_mic_permission",
                "elapsed_ms": 50.0,
                "result": "denied",
            },
            headers=ORIGIN,
        )
    assert viewed.status_code == 204
    assert permission.status_code == 204
    assert viewed.headers["cache-control"] == "no-store"
    assert "mobile_mic_permission" in caplog.text
    assert public_id not in caplog.text
    invalid = keyed_client.post(
        f"/api/public/demos/{public_id}/events",
        json={
            "event": "mobile_mic_permission",
            "elapsed_ms": 50.0,
            "result": "denied",
            "transcript": "must be rejected",
        },
        headers=ORIGIN,
    )
    assert invalid.status_code == 422


def test_failed_publish_keeps_bot_unpublished(keyed_client: TestClient) -> None:
    """Reject incomplete credentials before any link or snapshot becomes visible."""
    created = keyed_client.post(
        "/api/bots",
        json={
            **CONFIG,
            "save_asr_key": True,
            "save_tts_key": True,
            "save_llm_key": False,
            "asr_api_key": KEYS["asr_api_key"],
            "tts_api_key": KEYS["tts_api_key"],
        },
        headers=ORIGIN,
    )
    assert created.status_code == 201
    bot_id = created.json()["id"]
    failed = keyed_client.post(
        f"/api/bots/{bot_id}/publish",
        json={"public_title": "Maya", "public_description": ""},
        headers=ORIGIN,
    )
    assert failed.status_code == 400
    share = keyed_client.get(f"/api/bots/{bot_id}/share", headers=ORIGIN).json()
    assert share["published"] is False
    assert share["public_id"] is None

    blank_title = keyed_client.post(
        f"/api/bots/{bot_id}/publish",
        json={"public_title": "   ", "public_description": ""},
        headers=ORIGIN,
    )
    assert blank_title.status_code == 422


def test_concurrent_publications_serialize_revisions(keyed_client: TestClient) -> None:
    """Serialize simultaneous publish attempts without duplicating the stable link."""
    created = keyed_client.post("/api/bots", json={**CONFIG, **KEYS}, headers=ORIGIN)
    assert created.status_code == 201
    bot_id = created.json()["id"]

    def publish(title: str) -> int:
        response = keyed_client.post(
            f"/api/bots/{bot_id}/publish",
            json={"public_title": title, "public_description": ""},
            headers=ORIGIN,
        )
        assert response.status_code == 200, response.text
        return int(response.json()["revision"])

    with ThreadPoolExecutor(max_workers=2) as executor:
        revisions = list(executor.map(publish, ("Maya one", "Maya two")))
    assert sorted(revisions) == [1, 2]
    state = keyed_client.get(f"/api/bots/{bot_id}/share", headers=ORIGIN).json()
    assert state["revision"] == 2
    assert state["public_id"]


def test_link_disable_enable_delete_and_restart_persist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keep one public ID through restart/enable while deletion invalidates it."""
    monkeypatch.setenv("VOICE_AGENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VOICE_AGENT_STORAGE_KEY", Fernet.generate_key().decode())
    with TestClient(create_app()) as client:
        bot, share = _create_and_publish(client)
        public_id = share["public_id"]
        disabled = client.post(f"/api/bots/{bot['id']}/share/disable", headers=ORIGIN)
        assert disabled.status_code == 200
        assert disabled.json()["active"] is False
        denied = client.post(f"/api/public/demos/{public_id}/sessions", json={}, headers=ORIGIN)
        assert denied.status_code == 404

    with TestClient(create_app()) as restarted:
        loaded = restarted.get(f"/api/bots/{bot['id']}/share", headers=ORIGIN)
        assert loaded.status_code == 200
        assert loaded.json()["public_id"] == public_id
        enabled = restarted.post(f"/api/bots/{bot['id']}/share/enable", headers=ORIGIN)
        assert enabled.status_code == 200
        assert enabled.json()["public_id"] == public_id
        assert restarted.delete(f"/api/bots/{bot['id']}", headers=ORIGIN).status_code == 204
        assert restarted.get(f"/api/public/demos/{public_id}").status_code == 404


def test_referenced_key_rotation_clear_and_restore_follow_bot(
    keyed_client: TestClient,
) -> None:
    """Rotate in place, suspend on clear, then restore without republishing."""
    bot, share = _create_and_publish(keyed_client)
    bot_id = bot["id"]
    rotated = keyed_client.put(
        f"/api/bots/{bot_id}",
        json={
            **CONFIG,
            **KEYS,
            "asr_api_key": "asr-rotated-key-000001",
            "tts_api_key": "tts-rotated-key-000001",
            "llm_api_key": "llm-rotated-key-000001",
        },
        headers=ORIGIN,
    )
    assert rotated.status_code == 200, rotated.text
    after_rotation = keyed_client.get(f"/api/bots/{bot_id}/share", headers=ORIGIN).json()
    assert after_rotation["public_id"] == share["public_id"]
    assert after_rotation["available"] is True
    assert after_rotation["unpublished_changes"] is False

    cleared = keyed_client.put(
        f"/api/bots/{bot_id}",
        json={**CONFIG, "save_asr_key": True, "save_tts_key": True, "save_llm_key": False},
        headers=ORIGIN,
    )
    assert cleared.status_code == 200, cleared.text
    assert (
        keyed_client.get(f"/api/bots/{bot_id}/share", headers=ORIGIN).json()["available"] is False
    )
    unavailable = keyed_client.post(
        f"/api/public/demos/{share['public_id']}/sessions", json={}, headers=ORIGIN
    )
    assert unavailable.status_code == 409

    restored = keyed_client.put(
        f"/api/bots/{bot_id}",
        json={
            **CONFIG,
            "save_asr_key": True,
            "save_tts_key": True,
            "save_llm_key": True,
            "llm_api_key": "llm-restored-key-000001",
        },
        headers=ORIGIN,
    )
    assert restored.status_code == 200, restored.text
    assert keyed_client.get(f"/api/bots/{bot_id}/share", headers=ORIGIN).json()["available"] is True

    switched = keyed_client.put(
        f"/api/bots/{bot_id}",
        json={
            **CONFIG,
            "llm_provider": "custom",
            "llm_base_url": "https://example.com/v1",
            "llm_model": "draft-model",
            "save_asr_key": True,
            "save_tts_key": True,
            "save_llm_key": False,
        },
        headers=ORIGIN,
    )
    assert switched.status_code == 200, switched.text
    draft_state = keyed_client.get(f"/api/bots/{bot_id}/share", headers=ORIGIN).json()
    assert draft_state["unpublished_changes"] is True
    assert draft_state["available"] is True
    old_snapshot_session = keyed_client.post(
        f"/api/public/demos/{share['public_id']}/sessions", json={}, headers=ORIGIN
    )
    assert old_snapshot_session.status_code == 201
