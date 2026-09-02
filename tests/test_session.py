"""BYOK request validation, token, TTL, and cleanup tests."""

from __future__ import annotations

import pytest

from src.config import LLMProviderCatalog, RuntimeConfig, VoiceCatalog
from src.session import SessionLease, SessionRequest, SessionStore, SessionTokenError


async def _create_lease(
    *,
    request: SessionRequest,
    runtime: RuntimeConfig,
    voices: VoiceCatalog,
    providers: LLMProviderCatalog,
) -> tuple[SessionStore, SessionLease]:
    store = SessionStore(token_ttl_seconds=120, max_sessions=3)
    lease = await store.create(
        request=request,
        runtime=runtime,
        voice_catalog=voices,
        llm_catalog=providers,
    )
    return store, lease


@pytest.mark.asyncio
async def test_token_is_single_use_and_credentials_clear_on_close(
    session_request: SessionRequest,
    runtime_config: RuntimeConfig,
    voice_catalog: VoiceCatalog,
    llm_catalog: LLMProviderCatalog,
) -> None:
    """A WebSocket token must bind to one session and die with its credentials."""
    store, pending = await _create_lease(
        request=session_request,
        runtime=runtime_config,
        voices=voice_catalog,
        providers=llm_catalog,
    )
    lease = await store.claim(pending.token)
    with pytest.raises(SessionTokenError):
        await store.claim(pending.token)

    await store.close(lease.session_id)
    assert lease.closed is True
    assert lease.credentials.deepgram_api_key.get_secret_value() == ""
    assert lease.credentials.llm_api_key.get_secret_value() == ""
    with pytest.raises(SessionTokenError):
        await store.get_active(session_id=lease.session_id, token=lease.token)


@pytest.mark.asyncio
async def test_expired_pending_token_clears_credentials(
    session_request: SessionRequest,
    runtime_config: RuntimeConfig,
    voice_catalog: VoiceCatalog,
    llm_catalog: LLMProviderCatalog,
) -> None:
    """An unclaimed BYOK session must release secrets after its short TTL."""
    store, lease = await _create_lease(
        request=session_request,
        runtime=runtime_config,
        voices=voice_catalog,
        providers=llm_catalog,
    )
    lease.expires_at = 0
    assert await store.purge_expired() == 1
    assert lease.closed is True
    with pytest.raises(SessionTokenError):
        await store.claim(lease.token)


@pytest.mark.asyncio
async def test_new_session_can_be_created_after_previous_session_closes(
    session_request: SessionRequest,
    runtime_config: RuntimeConfig,
    voice_catalog: VoiceCatalog,
    llm_catalog: LLMProviderCatalog,
) -> None:
    """A recoverable failure or user end must release capacity for reconnection."""
    store = SessionStore(token_ttl_seconds=120, max_sessions=1)
    first = await store.create(
        request=session_request,
        runtime=runtime_config,
        voice_catalog=voice_catalog,
        llm_catalog=llm_catalog,
    )
    active = await store.claim(first.token)
    await store.close(active.session_id)
    second = await store.create(
        request=session_request,
        runtime=runtime_config,
        voice_catalog=voice_catalog,
        llm_catalog=llm_catalog,
    )
    assert second.session_id != first.session_id
    assert second.token != first.token
    await store.close_all()


def test_request_repr_masks_both_provider_keys(session_request: SessionRequest) -> None:
    """Accidental request logging must not reveal either API key."""
    rendered = repr(session_request)
    assert "test-deepgram-secret-123" not in rendered
    assert "test-llm-secret-456" not in rendered


def test_unknown_flux_voice_is_rejected(
    session_request: SessionRequest,
    runtime_config: RuntimeConfig,
    voice_catalog: VoiceCatalog,
    llm_catalog: LLMProviderCatalog,
) -> None:
    """Session overrides may only select a verified catalog voice."""
    from src.session import build_session_config

    invalid = session_request.model_copy(update={"flux_voice": "flux-invented-en"})
    with pytest.raises(ValueError, match="server catalog"):
        build_session_config(
            request=invalid,
            runtime=runtime_config,
            voice_catalog=voice_catalog,
            llm_catalog=llm_catalog,
        )
