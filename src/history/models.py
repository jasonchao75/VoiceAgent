"""Public and internal call history models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class HistoryTurn(BaseModel):
    """One final user or assistant utterance."""

    model_config = ConfigDict(extra="forbid")
    sequence: int
    role: str
    text: str
    created_ms: float


class TurnMetric(BaseModel):
    """One turn's full latency chain decomposition.

    The breakdown fields telescope to ``turn_to_playback_ms``:
    asr_final_latency + llm_request_splicing + llm_first_token +
    tts_initial + tts_first_audio + playback == e2e latency.
    """

    model_config = ConfigDict(extra="forbid")
    turn_index: int
    asr_final_latency_ms: float | None = None
    llm_request_splicing_ms: float | None = None
    llm_first_token_ms: float | None = None
    tts_initial_ms: float | None = None
    tts_first_audio_ms: float | None = None
    playback_ms: float | None = None
    server_to_playback_ms: float | None = None
    turn_to_playback_ms: float | None = None
    asr_final_reason: str | None = None
    incomplete_reason: str | None = None
    reasoning_tokens: int | None = None
    reasoning_status: str = "unverified"
    reasoning_control: str | None = None


class CallSummary(BaseModel):
    """Compact history row for the paginated list."""

    id: str
    bot_id: str | None
    bot_name: str | None
    started_at: str
    ended_at: str | None
    status: str
    duration_ms: float | None
    llm_provider: str
    llm_model: str
    tts_provider: str = "deepgram_flux"
    tts_model: str = "flux-general-en"
    tts_voice: str = ""
    tts_text_aggregation: str = "token"
    has_recording: bool
    recording_status: str
    error_category: str | None
    diagnostic_id: str | None


class CallDetail(CallSummary):
    """Full history record with turns and metrics."""

    asr_provider: str
    asr_model: str
    language: str
    audio_format: str
    sample_rate: int
    channels: int
    recording_bytes: int
    turns: list[HistoryTurn]
    metrics: list[TurnMetric]


class CallListResponse(BaseModel):
    """Paginated call list response."""

    items: list[CallSummary]
    total: int
    limit: int
    offset: int
