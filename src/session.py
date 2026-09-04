"""In-memory BYOK session lifecycle with single-use opaque tokens."""

from __future__ import annotations

import asyncio
import secrets
import time
import uuid
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from src.config import (
    LLMConfig,
    LLMProviderCatalog,
    RuntimeConfig,
    TTSConfig,
    VoiceCatalog,
)


class SessionRequest(BaseModel):
    """Initial session request; secret values are masked in repr and serialization."""

    model_config = ConfigDict(extra="forbid")

    deepgram_api_key: SecretStr = Field(min_length=8, max_length=500)
    llm_api_key: SecretStr = Field(min_length=8, max_length=500)
    elevenlabs_api_key: SecretStr | None = Field(default=None, min_length=8, max_length=500)
    llm_provider: str = Field(min_length=1, max_length=50)
    llm_base_url: str = Field(min_length=8, max_length=500)
    llm_model: str = Field(min_length=1, max_length=200)
    reasoning_mode: Literal["lowest_latency"] = "lowest_latency"
    system_prompt: str = Field(min_length=1, max_length=30000)
    opening_script: str = Field(max_length=2000)
    flux_voice: str = Field(min_length=8, max_length=100)
    tts_provider: Literal["deepgram_flux", "elevenlabs"] = "deepgram_flux"
    tts_model: str = Field(default="flux-general-en", min_length=1, max_length=100)
    tts_text_aggregation: Literal["token", "sentence"] = "token"
    tts_speed: float = Field(default=1.0, ge=0.7, le=1.2, multiple_of=0.05)
    tts_expressivity: Literal[-2, -1, 0, 1, 2] = 0
    tts_stability: float = Field(default=0.5, ge=0, le=1)
    tts_similarity_boost: float = Field(default=0.8, ge=0, le=1)
    tts_style: float = Field(default=0.0, ge=0, le=1)
    tts_use_speaker_boost: bool = False
    tts_text_normalization: Literal["auto", "on", "off"] = "auto"

    @field_validator("deepgram_api_key", "llm_api_key", "elevenlabs_api_key")
    @classmethod
    def reject_placeholder_key(cls, value: SecretStr | None) -> SecretStr | None:
        """Reject obvious placeholders without assuming a provider-specific key format."""
        if value is None:
            return None
        secret = value.get_secret_value().strip()
        lowered = secret.lower()
        if not secret or "your_" in lowered or "api_key_here" in lowered:
            raise ValueError("Enter a real API key for this session")
        return SecretStr(secret)


class BotSessionRequest(BaseModel):
    """Session request that sources configuration and optionally keys from a bot.

    Mutually exclusive with the inline SessionRequest shape: the API union
    rejects payloads carrying both bot_id and inline configuration fields.
    """

    model_config = ConfigDict(extra="forbid")

    bot_id: str = Field(min_length=1, max_length=100)
    deepgram_api_key: SecretStr | None = Field(default=None, min_length=8, max_length=500)
    llm_api_key: SecretStr | None = Field(default=None, min_length=8, max_length=500)
    elevenlabs_api_key: SecretStr | None = Field(default=None, min_length=8, max_length=500)

    @field_validator("deepgram_api_key", "llm_api_key", "elevenlabs_api_key")
    @classmethod
    def reject_placeholder_key(cls, value: SecretStr | None) -> SecretStr | None:
        """Apply the same placeholder policy as inline BYOK."""
        if value is None:
            return None
        secret = value.get_secret_value().strip()
        lowered = secret.lower()
        if not secret or "your_" in lowered or "api_key_here" in lowered:
            raise ValueError("Enter a real API key for this session")
        return SecretStr(secret)

    @model_validator(mode="after")
    def keys_all_or_nothing(self) -> BotSessionRequest:
        """Per-session BYOK keys are only valid as a pair."""
        provided = [key is not None for key in (self.deepgram_api_key, self.llm_api_key)]
        if any(provided) and not all(provided):
            raise ValueError("Deepgram and LLM API keys must be provided together")
        return self


class SessionConfig(BaseModel):
    """Validated non-secret configuration locked for one conversation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    llm: LLMConfig
    tts: TTSConfig
    system_prompt: str
    opening_script: str


@dataclass(slots=True, repr=False)
class SessionCredentials:
    """Mutable secret holder whose references are cleared deterministically."""

    deepgram_api_key: SecretStr
    llm_api_key: SecretStr
    elevenlabs_api_key: SecretStr | None = None

    def clear(self) -> None:
        """Drop references to provider keys after the session ends."""
        self.deepgram_api_key = SecretStr("")
        self.llm_api_key = SecretStr("")
        self.elevenlabs_api_key = None


@dataclass(slots=True, repr=False)
class SessionLease:
    """Credential and configuration lease owned by exactly one WebSocket."""

    session_id: str
    token: str
    credentials: SessionCredentials
    config: SessionConfig
    created_at: float
    expires_at: float
    claimed: bool = False
    closed: bool = False

    def close(self) -> None:
        """Invalidate the lease and release its credential references."""
        if self.closed:
            return
        self.closed = True
        self.credentials.clear()


class SessionCapacityError(RuntimeError):
    """Raised when the configured in-process session limit is reached."""


class SessionTokenError(RuntimeError):
    """Raised for missing, expired, or already-used session tokens."""


class SessionStore:
    """Async-safe in-memory store for pending and active BYOK sessions."""

    def __init__(self, *, token_ttl_seconds: int, max_sessions: int) -> None:
        """Initialize the store.

        Args:
            token_ttl_seconds: Lifetime of an unclaimed WebSocket token.
            max_sessions: Combined pending and active session limit.
        """
        self._token_ttl_seconds = token_ttl_seconds
        self._max_sessions = max_sessions
        self._pending: dict[str, SessionLease] = {}
        self._active: dict[str, SessionLease] = {}
        self._lock = asyncio.Lock()

    async def create(
        self,
        *,
        request: SessionRequest,
        runtime: RuntimeConfig,
        voice_catalog: VoiceCatalog,
        llm_catalog: LLMProviderCatalog,
    ) -> SessionLease:
        """Validate a request and create a short-lived, unclaimed session lease.

        Args:
            request: BYOK credentials and requested per-session settings.
            runtime: Server runtime defaults and limits.
            voice_catalog: Allowed Flux voices.
            llm_catalog: Allowed provider presets.

        Returns:
            A pending lease containing a single-use opaque token.

        Raises:
            SessionCapacityError: If the local concurrency limit is reached.
            ValueError: If a requested provider setting is not allowed.
        """
        session_config = build_session_config(
            request=request,
            runtime=runtime,
            voice_catalog=voice_catalog,
            llm_catalog=llm_catalog,
        )
        now = time.monotonic()
        async with self._lock:
            self._purge_expired_locked(now)
            if len(self._pending) + len(self._active) >= self._max_sessions:
                raise SessionCapacityError("The demo has reached its session limit")
            token = secrets.token_urlsafe(32)
            lease = SessionLease(
                session_id=str(uuid.uuid4()),
                token=token,
                credentials=SessionCredentials(
                    deepgram_api_key=request.deepgram_api_key,
                    llm_api_key=request.llm_api_key,
                    elevenlabs_api_key=request.elevenlabs_api_key,
                ),
                config=session_config,
                created_at=now,
                expires_at=now + self._token_ttl_seconds,
            )
            self._pending[token] = lease
        return lease

    async def build_config(
        self,
        *,
        request: SessionRequest,
        runtime: RuntimeConfig,
        voice_catalog: VoiceCatalog,
        llm_catalog: LLMProviderCatalog,
    ) -> SessionConfig:
        """Validate public configuration without creating a credential lease."""
        return build_session_config(
            request=request,
            runtime=runtime,
            voice_catalog=voice_catalog,
            llm_catalog=llm_catalog,
        )

    async def claim(self, token: str) -> SessionLease:
        """Consume a token and bind its lease to one active WebSocket."""
        now = time.monotonic()
        async with self._lock:
            self._purge_expired_locked(now)
            lease = self._pending.pop(token, None)
            if lease is None or lease.closed:
                raise SessionTokenError("Session token is invalid or expired")
            lease.claimed = True
            self._active[lease.session_id] = lease
            return lease

    async def close(self, session_id: str) -> None:
        """Remove an active session and clear its credential holder."""
        async with self._lock:
            lease = self._active.pop(session_id, None)
            if lease is not None:
                lease.close()

    async def get_active(self, *, session_id: str, token: str) -> SessionLease:
        """Authorize a non-secret browser event against the active session."""
        async with self._lock:
            lease = self._active.get(session_id)
            if lease is None or lease.closed or not secrets.compare_digest(lease.token, token):
                raise SessionTokenError("Session authorization is invalid")
            return lease

    async def purge_expired(self) -> int:
        """Clear expired pending sessions and return the number removed."""
        async with self._lock:
            return self._purge_expired_locked(time.monotonic())

    async def close_all(self) -> None:
        """Clear every credential reference during application shutdown."""
        async with self._lock:
            leases = [*self._pending.values(), *self._active.values()]
            self._pending.clear()
            self._active.clear()
            for lease in leases:
                lease.close()

    async def counts(self) -> tuple[int, int]:
        """Return pending and active counts for non-secret health reporting."""
        async with self._lock:
            self._purge_expired_locked(time.monotonic())
            return len(self._pending), len(self._active)

    def _purge_expired_locked(self, now: float) -> int:
        expired_tokens = [
            token for token, lease in self._pending.items() if lease.expires_at <= now
        ]
        for token in expired_tokens:
            self._pending.pop(token).close()
        return len(expired_tokens)


def build_session_config(
    *,
    request: SessionRequest,
    runtime: RuntimeConfig,
    voice_catalog: VoiceCatalog,
    llm_catalog: LLMProviderCatalog,
) -> SessionConfig:
    """Whitelist all public session overrides against controlled catalogs."""
    if request.tts_provider == "deepgram_flux":
        voices = {voice.model_id for voice in voice_catalog.voices}
        if request.flux_voice not in voices:
            raise ValueError("Select a Flux voice from the server catalog")
        if request.tts_model != "flux-general-en":
            raise ValueError("Unsupported Deepgram Flux TTS model")
    else:
        if request.elevenlabs_api_key is None:
            raise ValueError("ElevenLabs API key is required for ElevenLabs TTS")
        if request.tts_model not in {
            "eleven_flash_v2_5",
            "eleven_turbo_v2_5",
            "eleven_multilingual_v2",
            "eleven_v3",
        }:
            raise ValueError("Unsupported ElevenLabs TTS model")
        if request.tts_model == "eleven_v3" and request.tts_stability not in {0.0, 0.5, 1.0}:
            raise ValueError("Eleven v3 stability must be Creative, Natural, or Robust")

    providers = {provider.id: provider for provider in llm_catalog.providers}
    provider = providers.get(request.llm_provider)
    if provider is None:
        raise ValueError("Unknown LLM provider")
    base_url = request.llm_base_url.rstrip("/")
    if provider.id != "custom" and base_url != provider.base_url:
        raise ValueError("The selected provider base URL does not match the server catalog")
    if not provider.supports_custom_model and request.llm_model not in provider.recommended_models:
        raise ValueError("Select an LLM model from the server catalog")

    llm = LLMConfig(
        provider=provider.id,
        base_url=base_url,
        model=request.llm_model.strip(),
        reasoning_mode=request.reasoning_mode,
        timeout_seconds=runtime.llm.timeout_seconds,
    )
    tts = TTSConfig(
        provider=request.tts_provider,
        voice=request.flux_voice,
        model=request.tts_model,
        text_aggregation=request.tts_text_aggregation,
        speed=request.tts_speed,
        expressivity=request.tts_expressivity,
        stability=request.tts_stability,
        similarity_boost=request.tts_similarity_boost,
        style=request.tts_style,
        use_speaker_boost=request.tts_use_speaker_boost,
        text_normalization=request.tts_text_normalization,
    )
    return SessionConfig(
        llm=llm,
        tts=tts,
        system_prompt=request.system_prompt.strip(),
        opening_script=request.opening_script.strip(),
    )
