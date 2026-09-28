"""Pydantic models for the bot configuration entity."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from src.asr.config import normalize_provider, validate_asr_options


def _validate_optional_key(value: SecretStr | None) -> SecretStr | None:
    """Reject placeholders without assuming a provider-specific key format."""
    if value is None:
        return None
    secret = value.get_secret_value().strip()
    lowered = secret.lower()
    if not secret or "your_" in lowered or "api_key_here" in lowered:
        raise ValueError("Enter a real API key")
    return SecretStr(secret)


class BotConfigFields(BaseModel):
    """Non-secret bot configuration; secrets travel only in dedicated fields."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    asr_provider: str = Field(default="deepgram", min_length=1, max_length=50)
    asr_model: str = Field(default="flux-general-en", min_length=1, max_length=100)
    turn_detection_source: Literal["provider_native", "off"] = "provider_native"
    asr_options: dict[str, Any] = Field(default_factory=dict)
    asr_language_hints: list[
        Literal["en", "es", "fr", "de", "hi", "ru", "pt", "ja", "it", "nl"]
    ] = Field(default_factory=list, max_length=10)
    asr_eot_threshold: float = Field(default=0.7, ge=0.5, le=1.0)
    asr_eot_timeout_ms: int = Field(default=5000, ge=500, le=60000)
    asr_keyterms: list[str] = Field(default_factory=list, max_length=100)
    asr_profanity_filter: bool = False
    asr_numerals: bool = False
    asr_redact: Literal["numbers", "aggressive_numbers"] | None = None
    tts_provider: str = Field(min_length=1, max_length=50)
    tts_voice: str = Field(min_length=1, max_length=100)
    tts_model: str = Field(default="flux-general-en", min_length=1, max_length=100)
    tts_text_aggregation: Literal["token", "sentence"] = "token"
    tts_speed: float = Field(default=1.0, ge=0.5, le=1.5, multiple_of=0.05)
    tts_dynamic_speed_enabled: bool = False
    tts_speed_step: float = Field(default=0.10, ge=0.05, le=0.25, multiple_of=0.05)
    tts_expressivity: Literal[-2, -1, 0, 1, 2] = 0
    tts_model_improvement_opt_out: bool = False
    tts_stability: float = Field(default=0.5, ge=0, le=1)
    tts_similarity_boost: float = Field(default=0.8, ge=0, le=1)
    tts_style: float = Field(default=0.0, ge=0, le=1)
    tts_use_speaker_boost: bool = False
    tts_text_normalization: Literal["auto", "on", "off"] = "auto"
    llm_provider: str = Field(min_length=1, max_length=50)
    llm_base_url: str = Field(min_length=8, max_length=500)
    llm_model: str = Field(min_length=1, max_length=200)
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    reasoning_mode: Literal["provider_default", "off", "minimal"] = "provider_default"
    llm_max_response_tokens: int = Field(default=250, ge=1, le=32768)
    llm_request_timeout_seconds: float = Field(default=15.0, ge=3.0, le=60.0)
    system_prompt: str = Field(min_length=1, max_length=30000)
    opening_script: str = Field(max_length=2000)
    fallback_script: str = Field(default="", max_length=2000)

    @field_validator("asr_provider", mode="before")
    @classmethod
    def normalize_legacy_asr_provider(cls, value: object) -> object:
        """Keep existing Deepgram Bots valid while adopting provider-level IDs."""
        return normalize_provider(value) if isinstance(value, str) else value

    @field_validator("asr_keyterms")
    @classmethod
    def validate_keyterms(cls, value: list[str]) -> list[str]:
        """Keep user-entered phrases plain while rejecting empty or oversized entries."""
        normalized = [term.strip() for term in value]
        if any(not term or len(term) > 200 for term in normalized):
            raise ValueError("ASR keyterms must be non-empty and at most 200 characters")
        if len(normalized) != len(set(normalized)):
            raise ValueError("ASR keyterms must be unique")
        return normalized

    @model_validator(mode="after")
    def validate_provider_dependencies(self) -> BotConfigFields:
        """Reject combinations unsupported by the selected ASR and TTS models."""
        if self.asr_provider not in {"deepgram", "speechmatics", "soniox", "assemblyai"}:
            return self
        options = self.asr_options
        if not options and self.asr_provider == "deepgram" and self.asr_model.startswith("flux-"):
            options = {
                "language_hints": self.asr_language_hints,
                "eot_threshold": self.asr_eot_threshold,
                "eot_timeout_ms": self.asr_eot_timeout_ms,
                "keyterms": self.asr_keyterms,
                "profanity_filter": self.asr_profanity_filter,
                "numerals": self.asr_numerals,
                "redact": self.asr_redact,
            }
        self.asr_options = validate_asr_options(
            provider=self.asr_provider,
            model=self.asr_model,
            turn_detection_source=self.turn_detection_source,
            options=options,
        )
        if self.tts_provider == "elevenlabs" and not 0.7 <= self.tts_speed <= 1.2:
            raise ValueError("ElevenLabs speed must be between 0.7 and 1.2")
        if self.tts_model == "eleven_v3" and self.tts_dynamic_speed_enabled:
            raise ValueError("Eleven v3 does not support conversational speed control")
        return self


class BotCreateRequest(BotConfigFields):
    """Create payload; keys are accepted only when save_keys is enabled."""

    save_keys: bool = False
    save_asr_key: bool | None = None
    save_tts_key: bool | None = None
    save_llm_key: bool | None = None
    asr_api_key: SecretStr | None = Field(default=None, min_length=8, max_length=500)
    tts_api_key: SecretStr | None = Field(default=None, min_length=8, max_length=500)
    deepgram_api_key: SecretStr | None = Field(default=None, min_length=8, max_length=500)
    llm_api_key: SecretStr | None = Field(default=None, min_length=8, max_length=500)
    elevenlabs_api_key: SecretStr | None = Field(default=None, min_length=8, max_length=500)

    @field_validator(
        "asr_api_key",
        "tts_api_key",
        "deepgram_api_key",
        "llm_api_key",
        "elevenlabs_api_key",
    )
    @classmethod
    def reject_placeholder_key(cls, value: SecretStr | None) -> SecretStr | None:
        """Apply the same placeholder policy as session-level BYOK."""
        return _validate_optional_key(value)

    @model_validator(mode="after")
    def keys_match_save_intent(self) -> BotCreateRequest:
        """Validate each component's independent save intent."""
        components = (
            ("ASR", self.save_asr, self.effective_asr_key),
            ("TTS", self.save_tts, self.effective_tts_key),
            ("LLM", self.save_llm, self.llm_api_key),
        )
        for label, should_save, key in components:
            if should_save and key is None:
                raise ValueError(f"{label} API key is required when saving that component")
            if not should_save and key is not None:
                raise ValueError(f"{label} API key must not be submitted when saving is disabled")
        return self

    @property
    def save_asr(self) -> bool:
        """Resolve explicit component intent with legacy global compatibility."""
        return self.save_keys if self.save_asr_key is None else self.save_asr_key

    @property
    def save_tts(self) -> bool:
        """Resolve explicit component intent with legacy global compatibility."""
        return self.save_keys if self.save_tts_key is None else self.save_tts_key

    @property
    def save_llm(self) -> bool:
        """Resolve explicit component intent with legacy global compatibility."""
        return self.save_keys if self.save_llm_key is None else self.save_llm_key

    @property
    def effective_asr_key(self) -> SecretStr | None:
        """Resolve the new component field with legacy Deepgram compatibility."""
        return self.asr_api_key or (
            self.deepgram_api_key if self.asr_provider == "deepgram" else None
        )

    @property
    def effective_tts_key(self) -> SecretStr | None:
        """Resolve the selected TTS provider key without crossing components."""
        if self.tts_api_key is not None:
            return self.tts_api_key
        if self.tts_provider == "elevenlabs":
            return self.elevenlabs_api_key
        return self.deepgram_api_key


class BotUpdateRequest(BotConfigFields):
    """Full-replace update payload with a keep/replace/clear tri-state for keys.

    save_keys=false clears stored keys; save_keys=true with no key fields keeps
    the existing ciphertext; save_keys=true with both keys replaces it.
    """

    save_keys: bool = False
    save_asr_key: bool | None = None
    save_tts_key: bool | None = None
    save_llm_key: bool | None = None
    asr_api_key: SecretStr | None = Field(default=None, min_length=8, max_length=500)
    tts_api_key: SecretStr | None = Field(default=None, min_length=8, max_length=500)
    deepgram_api_key: SecretStr | None = Field(default=None, min_length=8, max_length=500)
    llm_api_key: SecretStr | None = Field(default=None, min_length=8, max_length=500)
    elevenlabs_api_key: SecretStr | None = Field(default=None, min_length=8, max_length=500)

    @field_validator(
        "asr_api_key",
        "tts_api_key",
        "deepgram_api_key",
        "llm_api_key",
        "elevenlabs_api_key",
    )
    @classmethod
    def reject_placeholder_key(cls, value: SecretStr | None) -> SecretStr | None:
        """Apply the same placeholder policy as session-level BYOK."""
        return _validate_optional_key(value)

    @model_validator(mode="after")
    def keys_follow_component_intent(self) -> BotUpdateRequest:
        """Allow one component key to change without replacing the others."""
        components = (
            ("ASR", self.save_asr, self.effective_asr_key),
            ("TTS", self.save_tts, self.effective_tts_key),
            ("LLM", self.save_llm, self.llm_api_key),
        )
        for label, should_save, key in components:
            if key is not None and not should_save:
                raise ValueError(
                    f"{label} key saving must be enabled when replacing that component key"
                )
        return self

    @property
    def save_asr(self) -> bool:
        """Resolve explicit component intent with legacy global compatibility."""
        return self.save_keys if self.save_asr_key is None else self.save_asr_key

    @property
    def save_tts(self) -> bool:
        """Resolve explicit component intent with legacy global compatibility."""
        return self.save_keys if self.save_tts_key is None else self.save_tts_key

    @property
    def save_llm(self) -> bool:
        """Resolve explicit component intent with legacy global compatibility."""
        return self.save_keys if self.save_llm_key is None else self.save_llm_key

    @property
    def effective_asr_key(self) -> SecretStr | None:
        """Resolve the new component field with legacy Deepgram compatibility."""
        return self.asr_api_key or (
            self.deepgram_api_key if self.asr_provider == "deepgram" else None
        )

    @property
    def effective_tts_key(self) -> SecretStr | None:
        """Resolve the selected TTS provider key without crossing components."""
        if self.tts_api_key is not None:
            return self.tts_api_key
        if self.tts_provider == "elevenlabs":
            return self.elevenlabs_api_key
        return self.deepgram_api_key


class BotRecord(BotConfigFields):
    """Full internal row including encrypted secrets and timestamps."""

    id: str
    encrypted_deepgram_key: str | None
    encrypted_llm_key: str | None
    llm_key_provider: str | None = None
    encrypted_elevenlabs_key: str | None
    asr_key_provider: str | None = None
    encrypted_asr_key: str | None = None
    tts_key_provider: str | None = None
    encrypted_tts_key: str | None = None
    asr_account_catalog: dict[str, object] | None = None
    created_at: str
    updated_at: str

    @property
    def has_saved_keys(self) -> bool:
        """All selected Bot component credentials are present and provider-matched."""
        return self.has_asr_key and self.has_tts_key and self.has_llm_key

    @property
    def has_asr_key(self) -> bool:
        """Return whether the selected ASR provider has a Bot-scoped key."""
        return self.encrypted_asr_key is not None and self.asr_key_provider == self.asr_provider

    @property
    def has_tts_key(self) -> bool:
        """Return whether the selected TTS provider has a Bot-scoped key."""
        return self.encrypted_tts_key is not None and self.tts_key_provider == self.tts_provider

    @property
    def has_llm_key(self) -> bool:
        """Return whether the selected LLM provider has a Bot-scoped key."""
        return self.encrypted_llm_key is not None and self.llm_key_provider == self.llm_provider


class BotResponse(BotConfigFields):
    """Public representation; never carries plaintext or ciphertext keys."""

    id: str
    has_saved_keys: bool
    has_asr_key: bool
    has_tts_key: bool
    has_llm_key: bool
    asr_account_catalog: dict[str, object] | None = None
    created_at: str
    updated_at: str

    @classmethod
    def from_record(cls, record: BotRecord) -> BotResponse:
        """Strip secret columns while exposing only the saved-keys marker."""
        return cls(
            **record.model_dump(
                exclude={
                    "encrypted_deepgram_key",
                    "encrypted_llm_key",
                    "llm_key_provider",
                    "encrypted_elevenlabs_key",
                    "asr_key_provider",
                    "encrypted_asr_key",
                    "tts_key_provider",
                    "encrypted_tts_key",
                }
            ),
            has_saved_keys=record.has_saved_keys,
            has_asr_key=record.has_asr_key,
            has_tts_key=record.has_tts_key,
            has_llm_key=record.has_llm_key,
        )
