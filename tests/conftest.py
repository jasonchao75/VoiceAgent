"""Shared fixtures for the English Flux Voice Agent tests."""

from __future__ import annotations

import pytest

from src.config import (
    LLMProviderCatalog,
    RuntimeConfig,
    VoiceCatalog,
    load_llm_provider_catalog,
    load_runtime_config,
    load_voice_catalog,
)
from src.session import SessionRequest


@pytest.fixture
def runtime_config() -> RuntimeConfig:
    """Return validated runtime defaults."""
    return load_runtime_config()


@pytest.fixture
def voice_catalog() -> VoiceCatalog:
    """Return the controlled voice catalog."""
    return load_voice_catalog()


@pytest.fixture
def llm_catalog() -> LLMProviderCatalog:
    """Return controlled LLM provider presets."""
    return load_llm_provider_catalog()


@pytest.fixture
def session_request(runtime_config: RuntimeConfig) -> SessionRequest:
    """Return a valid request using inert test-only credential strings."""
    return SessionRequest(
        deepgram_api_key="test-deepgram-secret-123",
        llm_api_key="test-llm-secret-456",
        llm_provider=runtime_config.llm.provider,
        llm_base_url=runtime_config.llm.base_url,
        llm_model=runtime_config.llm.model,
        system_prompt=runtime_config.system_prompt,
        opening_script=runtime_config.opening_script,
        flux_voice=runtime_config.tts.voice,
    )
