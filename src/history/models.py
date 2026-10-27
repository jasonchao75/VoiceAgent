"""Public and internal call history models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class HistoryTurn(BaseModel):
    """One final user or assistant utterance."""

    model_config = ConfigDict(extra="forbid")
    sequence: int
    role: str
    text: str
    created_ms: float


class LatencyInterval(BaseModel):
    """An evidence-bounded interval, never an implied exact midpoint."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    lower_ms: float = Field(ge=0)
    upper_ms: float = Field(ge=0)
    playback_id: str
    response_id: str
    anchor_ids: tuple[str, str]
    source: Literal["authenticated_worklet_causal_bracket"]
    origin: Literal["server_audio_task_prepared", "vad_speech_end_source_sample"]

    @model_validator(mode="after")
    def ordered_interval(self) -> LatencyInterval:
        """Reject inverted evidence rather than repairing it into a believable number."""
        if self.lower_ms > self.upper_ms:
            raise ValueError("Latency interval is inverted")
        return self


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
    timing_ranges: dict[Literal["playback", "e2e"], LatencyInterval] = Field(default_factory=dict)
    playback_evidence: (
        Literal["missing", "unverified_client_report", "client_render_confirmed"] | None
    ) = None
    asr_final_reason: str | None = None
    incomplete_reason: str | None = None
    reasoning_tokens: int | None = None
    reasoning_status: str = "unverified"
    reasoning_control: str | None = None
    context_applied: bool | None = None
    context_failure_reason: str | None = None

    @model_validator(mode="after")
    def playback_provenance(self) -> TurnMetric:
        """Keep legacy measurements without upgrading their unknown event provenance."""
        measured = any(
            value is not None
            for value in (
                self.playback_ms,
                self.server_to_playback_ms,
                self.turn_to_playback_ms,
            )
        )
        if self.timing_ranges:
            self.playback_evidence = "client_render_confirmed"
        elif not measured:
            self.playback_evidence = "missing"
        elif self.playback_evidence in {None, "missing"}:
            self.playback_evidence = "unverified_client_report"
        return self


class CallSummary(BaseModel):
    """Compact history row for the paginated list."""

    id: str
    bot_id: str | None
    bot_name: str | None
    session_type: str = "web_call"
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
    context_mode: Literal["off", "agent", "full"] = "off"
    audio_format: str
    sample_rate: int
    channels: int
    recording_bytes: int
    td_events: list[dict[str, Any]] = Field(default_factory=list)
    turns: list[HistoryTurn]
    metrics: list[TurnMetric]


class CallListResponse(BaseModel):
    """Paginated call list response."""

    items: list[CallSummary]
    total: int
    limit: int
    offset: int
