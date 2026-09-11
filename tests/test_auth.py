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
