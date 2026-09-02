"""Validated runtime configuration and public provider catalogs."""

from __future__ import annotations

import json
from ipaddress import ip_address
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_CONFIG_DIR = PROJECT_ROOT / "configs" / "runtime"


class StrictModel(BaseModel):
    """Reject unknown configuration fields to catch deployment mistakes early."""

    model_config = ConfigDict(extra="forbid")


class AudioConfig(StrictModel):
    """Audio format shared by browser transport and provider services."""

    encoding: Literal["linear16"] = "linear16"
    input_sample_rate: Literal[16000] = 16000
    output_sample_rate: Literal[24000] = 24000
    sample_width_bytes: Literal[2] = 2
    channels: Literal[1] = 1


class ASRConfig(StrictModel):
    """Deepgram Flux speech recognition settings."""

    provider: Literal["deepgram_flux"] = "deepgram_flux"
    model: Literal["flux-general-en"] = "flux-general-en"
    eager_eot_threshold: float | None = Field(default=None, ge=0.3, le=0.9)
    eot_threshold: float | None = Field(default=None, ge=0.5, le=0.9)
    eot_timeout_ms: int | None = Field(default=None, ge=500, le=5000)


class LLMConfig(StrictModel):
    """Default OpenAI-compatible language model settings."""

    provider: str = Field(min_length=1, max_length=50)
    base_url: str
    model: str = Field(min_length=1, max_length=200)
    timeout_seconds: float = Field(default=15.0, ge=3.0, le=60.0)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        """Require a public HTTPS endpoint and remove a trailing slash."""
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("LLM base_url must be an HTTPS URL without embedded credentials")
        host = (parsed.hostname or "").lower().rstrip(".")
        if host == "localhost" or host.endswith((".local", ".internal")):
            raise ValueError("LLM base_url must not target a local network host")
        try:
            address = ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError("LLM base_url must not target a private or reserved IP address")
        return value.rstrip("/")


class TTSConfig(StrictModel):
    """Deepgram Flux synthesis settings."""

    provider: Literal["deepgram_flux"] = "deepgram_flux"
    voice: str
    speed: float = Field(default=1.0, ge=0.85, le=1.15, multiple_of=0.05)
    expressivity: Literal[-2, -1, 0, 1, 2] = 0


class SessionLimits(StrictModel):
    """In-process limits for a local or protected demo instance."""

    pending_token_ttl_seconds: int = Field(default=120, ge=30, le=600)
    idle_timeout_seconds: int = Field(default=300, ge=30, le=1800)
    max_duration_seconds: int = Field(default=1800, ge=60, le=7200)
    max_concurrent_sessions: int = Field(default=3, ge=1, le=20)


class RuntimeConfig(StrictModel):
    """Complete non-secret runtime configuration."""

    language: Literal["en"] = "en"
    audio: AudioConfig
    asr: ASRConfig
    llm: LLMConfig
    tts: TTSConfig
    system_prompt: str = Field(min_length=1, max_length=12000)
    opening_script: str = Field(max_length=2000)
    session: SessionLimits


class VoiceEntry(StrictModel):
    """Public metadata for one selectable Flux voice."""

    name: str
    model_id: str
    accent: str
    gender: str
    age: str
    traits: list[str]
    use_cases: list[str]

    @field_validator("model_id")
    @classmethod
    def validate_flux_model(cls, value: str) -> str:
        """Limit the MVP catalog to English Flux voices."""
        if not value.startswith("flux-") or not value.endswith("-en"):
            raise ValueError("Flux voice model must match flux-*-en")
        return value


class VoiceCatalog(StrictModel):
    """Controlled Flux voice catalog served to the frontend."""

    source_url: str
    listen_url: str
    verified_at: str
    voices: list[VoiceEntry] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_catalog(self) -> VoiceCatalog:
        """Validate HTTPS links and unique model IDs."""
        _require_https(self.source_url)
        _require_https(self.listen_url)
        ids = [voice.model_id for voice in self.voices]
        if len(ids) != len(set(ids)):
            raise ValueError("Flux voice model IDs must be unique")
        return self


class LLMProviderEntry(StrictModel):
    """Public metadata and documentation links for an LLM provider."""

    id: str
    name: str
    base_url: str
    recommended_models: list[str]
    default_model: str
    api_key_url: str
    models_url: str
    supports_custom_model: bool

    @model_validator(mode="after")
    def validate_provider(self) -> LLMProviderEntry:
        """Keep help links controlled and require HTTPS provider endpoints."""
        _require_https(self.api_key_url)
        _require_https(self.models_url)
        if self.id == "custom":
            if self.base_url or self.default_model or self.recommended_models:
                raise ValueError("Custom provider must not inject endpoint or model defaults")
        else:
            _require_https(self.base_url)
            if self.default_model not in self.recommended_models:
                raise ValueError("Default model must be in recommended_models")
        return self


class LLMProviderCatalog(StrictModel):
    """Controlled provider presets served to the frontend."""

    verified_at: str
    providers: list[LLMProviderEntry] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_catalog(self) -> LLMProviderCatalog:
        """Require unique IDs and the advanced custom option."""
        ids = [provider.id for provider in self.providers]
        if len(ids) != len(set(ids)) or "custom" not in ids:
            raise ValueError("LLM provider IDs must be unique and include custom")
        return self


def _require_https(value: str) -> None:
    """Raise when a controlled URL is not a plain HTTPS URL."""
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError(f"Controlled URL must use HTTPS: {value}")


def _load_json(path: Path) -> dict:
    """Load a UTF-8 JSON object from disk."""
    with path.open("r", encoding="utf-8") as file:
        value = json.load(file)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def load_runtime_config() -> RuntimeConfig:
    """Load and validate the default Agent configuration."""
    return RuntimeConfig.model_validate(_load_json(RUNTIME_CONFIG_DIR / "agent.json"))


def load_voice_catalog() -> VoiceCatalog:
    """Load and validate the selectable Flux voices."""
    return VoiceCatalog.model_validate(_load_json(RUNTIME_CONFIG_DIR / "flux_voices.json"))


def load_llm_provider_catalog() -> LLMProviderCatalog:
    """Load and validate LLM provider presets and help links."""
    return LLMProviderCatalog.model_validate(_load_json(RUNTIME_CONFIG_DIR / "llm_providers.json"))
