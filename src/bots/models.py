"""Pydantic models for the bot configuration entity."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator


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
    asr_provider: str = Field(min_length=1, max_length=50)
    tts_provider: str = Field(min_length=1, max_length=50)
    tts_voice: str = Field(min_length=1, max_length=100)
    llm_provider: str = Field(min_length=1, max_length=50)
    llm_base_url: str = Field(min_length=8, max_length=500)
    llm_model: str = Field(min_length=1, max_length=200)
    system_prompt: str = Field(min_length=1, max_length=30000)
    opening_script: str = Field(max_length=2000)


class BotCreateRequest(BotConfigFields):
    """Create payload; keys are accepted only when save_keys is enabled."""

    save_keys: bool = False
    deepgram_api_key: SecretStr | None = Field(default=None, min_length=8, max_length=500)
    llm_api_key: SecretStr | None = Field(default=None, min_length=8, max_length=500)

    @field_validator("deepgram_api_key", "llm_api_key")
    @classmethod
    def reject_placeholder_key(cls, value: SecretStr | None) -> SecretStr | None:
        """Apply the same placeholder policy as session-level BYOK."""
        return _validate_optional_key(value)

    @model_validator(mode="after")
    def keys_match_save_intent(self) -> BotCreateRequest:
        """Require exactly both keys when saving and none when not."""
        provided = [key is not None for key in (self.deepgram_api_key, self.llm_api_key)]
        if self.save_keys and not all(provided):
            raise ValueError("Both API keys are required when save_keys is enabled")
        if not self.save_keys and any(provided):
            raise ValueError("API keys must not be submitted when save_keys is disabled")
        return self


class BotUpdateRequest(BotConfigFields):
    """Full-replace update payload with a keep/replace/clear tri-state for keys.

    save_keys=false clears stored keys; save_keys=true with no key fields keeps
    the existing ciphertext; save_keys=true with both keys replaces it.
    """

    save_keys: bool = False
    deepgram_api_key: SecretStr | None = Field(default=None, min_length=8, max_length=500)
    llm_api_key: SecretStr | None = Field(default=None, min_length=8, max_length=500)

    @field_validator("deepgram_api_key", "llm_api_key")
    @classmethod
    def reject_placeholder_key(cls, value: SecretStr | None) -> SecretStr | None:
        """Apply the same placeholder policy as session-level BYOK."""
        return _validate_optional_key(value)

    @model_validator(mode="after")
    def keys_all_or_nothing(self) -> BotUpdateRequest:
        """Accept keys only as a pair and only while save_keys is enabled."""
        provided = [key is not None for key in (self.deepgram_api_key, self.llm_api_key)]
        if any(provided) and not all(provided):
            raise ValueError("Both API keys must be provided together")
        if any(provided) and not self.save_keys:
            raise ValueError("save_keys must be enabled when replacing stored keys")
        return self


class BotRecord(BotConfigFields):
    """Full internal row including encrypted secrets and timestamps."""

    id: str
    encrypted_deepgram_key: str | None
    encrypted_llm_key: str | None
    created_at: str
    updated_at: str

    @property
    def has_saved_keys(self) -> bool:
        """Both columns move together; ASR and TTS share the Deepgram key."""
        return self.encrypted_deepgram_key is not None and self.encrypted_llm_key is not None


class BotResponse(BotConfigFields):
    """Public representation; never carries plaintext or ciphertext keys."""

    id: str
    has_saved_keys: bool
    created_at: str
    updated_at: str

    @classmethod
    def from_record(cls, record: BotRecord) -> BotResponse:
        """Strip secret columns while exposing only the saved-keys marker."""
        return cls(
            **record.model_dump(exclude={"encrypted_deepgram_key", "encrypted_llm_key"}),
            has_saved_keys=record.has_saved_keys,
        )
