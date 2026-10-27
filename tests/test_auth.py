"""Website session expiry and return-path security tests."""

import pytest

from src.auth import AuthSessionStore, safe_return_path


def test_auth_session_uses_idle_and_absolute_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Activity extends idle expiry but never crosses the absolute lifetime."""
    now = 1_000.0
    monkeypatch.setattr("src.auth.time.time", lambda: now)
    store = AuthSessionStore(idle_seconds=100, absolute_seconds=250)
    token, _, _ = store.create()

    now = 1_090.0
    assert store.validate(token) == (1_190.0, 1_250.0)
    now = 1_180.0
    assert store.validate(token) == (1_250.0, 1_250.0)
    now = 1_250.0
    assert store.validate(token) is None


@pytest.mark.parametrize("value", [None, "", "https://evil.example", "//evil.example"])
def test_return_path_rejects_external_destinations(value: str | None) -> None:
    """Login redirects must remain on VoiceAgent Demo."""
    assert safe_return_path(value) == "/"


def test_only_exact_task_telemetry_routes_use_call_bearer():
    """Bypassing the login Cookie must not expose management or arbitrary nested routes."""
    from src.auth import ProductAuthMiddleware

    allowed = [
        "/api/sessions/id/events",
        "/api/sessions/id/metrics",
        "/api/sessions/id/playback-events",
        "/api/sessions/id/playback-clock",
        "/api/sessions/id/playback-clock/sample",
        "/api/sessions/id/rtp-input",
    ]
    denied = [
        "/api/sessions",
        "/api/sessions/id",
        "/api/sessions//playback-events",
        "/api/sessions/id/playback-events/admin",
        "/api/sessions/id/rtp-input/admin",
        "/api/sessions/id/playback-clock/sample/admin",
        "/api/bots/id",
        "/api/history/id",
        "/api/sessions/id/unknown",
    ]
    assert all(ProductAuthMiddleware._uses_call_bearer(path) for path in allowed)
    assert not any(ProductAuthMiddleware._uses_call_bearer(path) for path in denied)
