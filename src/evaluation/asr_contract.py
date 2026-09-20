"""Common normalized contract for offline evaluation ASR providers."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ASRSegment(BaseModel):
    """One traceable provider segment on the source-audio timeline."""

    model_config = ConfigDict(extra="forbid")
    segment_id: str = Field(min_length=1, max_length=300)
    start: float | None = Field(default=None, ge=0)
    end: float | None = Field(default=None, ge=0)
    speaker: str | int | None = None
    text: str = ""

    @model_validator(mode="after")
    def validate_timeline(self) -> ASRSegment:
        """Reject inverted provider timestamps before they become evidence."""
        if self.start is not None and self.end is not None and self.end < self.start:
            raise ValueError("ASR segment end precedes start")
        return self


class ASRResult(BaseModel):
    """Provider-independent full-call transcription result."""

    model_config = ConfigDict(extra="forbid")
    provider: Literal["soniox", "speechmatics", "elevenlabs"]
    conversation_id: str = Field(min_length=1, max_length=128)
    text: str
    segments: list[ASRSegment]
    remote_cleanup: Literal["not_required", "completed", "failed"] | None = None


class ASRError(BaseModel):
    """Safe provider failure persisted without upstream bodies or credentials."""

    model_config = ConfigDict(extra="forbid")
    provider: Literal["soniox", "speechmatics", "elevenlabs"]
    category: Literal[
        "authentication_failed",
        "rate_limited",
        "timeout",
        "provider_error",
        "invalid_result",
    ]
    retryable: bool
    message: str = Field(max_length=160)
