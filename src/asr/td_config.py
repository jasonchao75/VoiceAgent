"""Explicit, immutable custom TD settings kept separate from provider ASR options."""

from __future__ import annotations

import ipaddress
import unicodedata
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TDModel(BaseModel):
    """Reject unknown fields and non-finite numbers in session snapshots."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class LocalVADSettings(TDModel):
    """Four exposed Silero controls, explicitly supplied rather than silently calibrated."""

    confidence: float = Field(ge=0, le=1)
    start_secs: float = Field(gt=0, le=5)
    stop_secs: float = Field(gt=0, le=10)
    min_volume: float = Field(ge=0, le=1)


class JevOption(TDModel):
    """One stable Choice identifier with a local target silence mapping."""

    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$", max_length=64)
    meaning: str = Field(min_length=1, max_length=2000)
    wait_ms: int = Field(ge=0, le=120000)


class JevSettings(TDModel):
    """Non-secret backend connection and question settings."""

    endpoint: str
    model: str = Field(min_length=1, max_length=100)
    timeout_seconds: float = Field(gt=0, le=60)
    max_calls: int = Field(default=100, ge=1, le=10000)
    noul_instructions: str = Field(min_length=1, max_length=10000)
    choice_instructions: str = Field(min_length=1, max_length=10000)
    options: tuple[JevOption, ...] = Field(min_length=2, max_length=255)

    @field_validator("max_calls")
    @classmethod
    def uniform_session_budget(cls, value: int) -> int:
        """D-050 normalizes legacy drafts; hidden API fields cannot change the fixed budget."""
        return 100

    @field_validator("endpoint")
    @classmethod
    def public_endpoint(cls, value: str) -> str:
        """Avoid obvious private targets and credential-bearing URLs for the backend call."""
        parts = urlsplit(value)
        host = (parts.hostname or "").lower()
        if (
            parts.scheme != "https"
            or not host
            or parts.username
            or parts.password
            or parts.query
            or parts.fragment
            or host == "localhost"
            or host.endswith((".localhost", ".local", ".internal"))
        ):
            raise ValueError("Jev requires a public HTTPS endpoint")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            return value
        if not address.is_global:
            raise ValueError("Jev endpoint cannot target a private address")
        return value

    @model_validator(mode="after")
    def distinct_options(self) -> JevSettings:
        """Prevent two options from silently sharing a probability key."""
        if len({option.id for option in self.options}) != len(self.options):
            raise ValueError("Jev option IDs must be unique")
        return self

    def questions(self) -> dict[str, object]:
        """Build the official request questions without sending local wait mappings."""
        return {
            "yield": {"type": "noul", "instructions": self.noul_instructions},
            "speech_state": {
                "type": "choice",
                "instructions": self.choice_instructions,
                "criteria": {option.id: option.meaning for option in self.options},
            },
        }


class IdentifierUnit(TDModel):
    """One permanent spoken unit and its explicit recognized variants."""

    value: str = Field(min_length=1, max_length=100)
    aliases: tuple[str, ...] = Field(min_length=1, max_length=100)


class CollectionSettings(TDModel):
    """Optional completeness protection, separate from echo eligibility."""

    target_length: int = Field(ge=1, le=10000)
    timeout_ms: int = Field(gt=0, le=120000)
    overflow_pause_ms: int = Field(ge=0, le=120000)
    incomplete_text: str = Field(min_length=1, max_length=2000)
    overflow_text: str = Field(min_length=1, max_length=2000)


class EchoResource(TDModel):
    """One content-addressed audio version frozen by publication, never a browser cache."""

    unit: str = Field(min_length=1, max_length=100)
    version: str = Field(pattern=r"^[a-f0-9]{64}$")


class IdentifierRuleSettings(TDModel):
    """Preserve a hidden/disabled draft without inventing numeric runtime defaults."""

    enabled: bool
    keywords: tuple[str, ...] = ()
    vocabulary: tuple[IdentifierUnit, ...] = ()
    wpm_threshold: float | None = Field(default=None, gt=0, le=10000)
    pause_ms: int | None = Field(default=None, ge=0, le=120000)
    unit_gap_ms: int | None = Field(default=None, ge=0, le=10000)
    collection: CollectionSettings | None = None
    assets: tuple[EchoResource, ...] = ()

    @model_validator(mode="after")
    def explicit_valid_rule(self) -> IdentifierRuleSettings:
        """Reject ambiguous aliases and require the frozen keyword gate when enabled."""
        if any(not item.strip() for item in self.keywords):
            raise ValueError("Keywords must be nonempty")
        aliases: set[str] = set()
        targets: set[str] = set()
        for row in self.vocabulary:
            if not row.value.strip() or row.value in targets:
                raise ValueError("Vocabulary values must be unique and nonempty")
            targets.add(row.value)
            for alias in row.aliases:
                key = unicodedata.normalize("NFKC", alias).strip().casefold()
                if not key or key in aliases:
                    raise ValueError("Vocabulary aliases must be unique and nonempty")
                aliases.add(key)
        if self.enabled and (
            not self.keywords
            or not self.vocabulary
            or self.wpm_threshold is None
            or self.pause_ms is None
            or self.unit_gap_ms is None
        ):
            raise ValueError("Enabled identifier rules require explicit complete settings")
        return self


class CustomTDSettings(TDModel):
    """A Bot's saved draft and a session's immutable custom TD timing contract."""

    minimum_ms: int = Field(ge=0, le=120000)
    maximum_ms: int = Field(gt=0, le=120000)
    final_wait_ms: int = Field(ge=0, le=120000)
    alpha: float = Field(ge=0, le=1)
    conflict_threshold: float = Field(ge=0, le=1)
    vad: LocalVADSettings
    jev: JevSettings
    priority_rule: IdentifierRuleSettings | None = None

    @model_validator(mode="after")
    def ordered_bounds(self) -> CustomTDSettings:
        """Keep the maximum watchdog independent of VAD and bounded Final waiting."""
        if self.maximum_ms < self.minimum_ms:
            raise ValueError("Maximum silence must be at least minimum silence")
        return self
