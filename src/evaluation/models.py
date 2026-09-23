"""Validated request models for the ASR evaluation domain."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator


class EvaluationConnectionTestRequest(BaseModel):
    """Test and atomically save one evaluation provider connection."""

    model_config = ConfigDict(extra="forbid")
    api_key: SecretStr | None = Field(default=None, min_length=8, max_length=500)
    base_url: str | None = Field(default=None, min_length=8, max_length=500)
    model_id: str | None = Field(default=None, min_length=1, max_length=200)
    register_for_evaluation_catalog: bool = False


class EvaluationBatchCreate(BaseModel):
    """Create one local evaluation run from the mounted acceptance fixture."""

    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=160)
    context_key: str = Field(default="riyadbank", min_length=1, max_length=80)
    screening_strategy: Literal["focused", "standard", "comprehensive"] = "focused"
    asr_providers: list[Literal["soniox", "speechmatics", "elevenlabs"]] = Field(
        min_length=1,
        max_length=3,
    )
    pass_1_model: str = Field(min_length=1, max_length=160)
    pass_2_model: str = Field(min_length=1, max_length=160)
    budget_limit: float = Field(gt=0, le=10000)
    idempotency_key: str = Field(min_length=8, max_length=160)


class EvaluationBatchAction(BaseModel):
    """Apply an optimistic state transition to a batch."""

    model_config = ConfigDict(extra="forbid")
    action: Literal["start", "pause", "resume", "stop", "retry_failed"]
    expected_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=8, max_length=160)


class EvaluationBatchDelete(BaseModel):
    """Delete one non-running batch after explicit confirmation."""

    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=8, max_length=160)


class EvaluationDisplayTranslationRequest(BaseModel):
    """Translate visible source transcript text without persisting the result."""

    model_config = ConfigDict(extra="forbid")
    texts: list[str] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_texts(self) -> EvaluationDisplayTranslationRequest:
        """Bound paid display requests and reject empty transcript entries."""
        if any(not text.strip() or len(text) > 5000 for text in self.texts):
            raise ValueError("Each source text must contain 1 to 5000 characters")
        if sum(len(text) for text in self.texts) > 50_000:
            raise ValueError("Visible source text exceeds the 50000 character limit")
        return self


class EvaluationPricingVersionWrite(BaseModel):
    """Create one immutable pricing conversion version for future batches."""

    model_config = ConfigDict(extra="forbid")
    cny_to_usd: float = Field(gt=0, le=1)
    source_note: str = Field(min_length=1, max_length=500)
    default_batch_budget: float | None = Field(default=None, gt=0, le=10000)
    asr_rates: list[dict[str, Any]] | None = Field(default=None, max_length=20)
    llm_rates: list[dict[str, Any]] | None = Field(default=None, max_length=100)


class EvaluationReviewSubmit(BaseModel):
    """Submit an explicit human decision for one review case."""

    model_config = ConfigDict(extra="forbid")
    decision: Literal["good", "bad", "unclear"]
    label: str | None = Field(default=None, max_length=5000)
    language: Literal["en", "ar", "mixed"]
    scenario_tag: str = Field(min_length=1, max_length=120)
    expected_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=8, max_length=160)

    @model_validator(mode="after")
    def validate_label(self) -> EvaluationReviewSubmit:
        """Require a corrected label only for a Bad decision."""
        if self.decision == "bad" and not (self.label or "").strip():
            raise ValueError("Bad decisions require a corrected label")
        if self.decision == "unclear" and self.label:
            raise ValueError("Unclear decisions cannot include a label")
        return self


class HistoricalTurnReviewSubmit(BaseModel):
    """Submit a group-level decision for one suspected historical Turn issue."""

    model_config = ConfigDict(extra="forbid")
    decision: Literal["confirm", "reject", "defer"]
    expected_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=8, max_length=160)


class EvaluationReviewComplete(BaseModel):
    """End manual review early and freeze a partial final report."""

    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=8, max_length=160)


class ScenarioTagWrite(BaseModel):
    """Create or version one global scenario tag."""

    model_config = ConfigDict(extra="forbid")
    name_en: str = Field(min_length=1, max_length=120)
    name_zh: str = Field(min_length=1, max_length=120)
    description_en: str = Field(min_length=1, max_length=2000)
    description_zh: str = Field(min_length=1, max_length=2000)
    tag_type: Literal["acoustic", "semantic"]
    examples: list[str] = Field(default_factory=list, max_length=20)
    expected_version: int | None = Field(default=None, ge=1)


class ScenarioTagStatusUpdate(BaseModel):
    """Enable or disable one scenario tag with optimistic locking."""

    model_config = ConfigDict(extra="forbid")
    enabled: bool
    expected_version: int = Field(ge=1)


class BenchmarkExportRequest(BaseModel):
    """Select Benchmark samples by explicit IDs or a frozen filter snapshot."""

    model_config = ConfigDict(extra="forbid")
    sample_ids: list[str] = Field(default_factory=list, max_length=5000)
    language: Literal["all", "en", "ar", "mixed"] = "all"
    scenario_tag: str = Field(default="all", max_length=120)
    source: Literal["all", "ai", "manual"] = "all"
    case_type: Literal["all", "good", "bad"] = "all"
    search: str = Field(default="", max_length=5000)


class BenchmarkUpdate(BaseModel):
    """Append a classified Benchmark correction without erasing prior values."""

    model_config = ConfigDict(extra="forbid")
    label: str = Field(min_length=1, max_length=5000)
    language: Literal["en", "ar", "mixed"]
    scenario_tag: str = Field(min_length=1, max_length=120)
    expected_revision: int = Field(ge=1)


class ReferenceDictionaryWrite(BaseModel):
    """Create or version one generic reference dictionary."""

    model_config = ConfigDict(extra="forbid")
    dictionary_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=80,
        pattern=r"^[a-z][a-z0-9_]*$",
    )
    name: str = Field(min_length=1, max_length=160)
    purpose: str = Field(min_length=1, max_length=2000)
    schema_fields: list[str] = Field(min_length=1, max_length=50)
    entries: list[dict[str, Any]] = Field(default_factory=list, max_length=10000)
    expected_version: int | None = Field(default=None, ge=1)


class EvaluationContextWrite(BaseModel):
    """Create or version one evaluation context and frozen dictionary links."""

    model_config = ConfigDict(extra="forbid")
    context_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=80,
        pattern=r"^[a-z][a-z0-9_]*$",
    )
    name: str = Field(min_length=1, max_length=160)
    business_scope: str = Field(min_length=1, max_length=2000)
    business_background_and_objective: str = Field(min_length=1, max_length=10000)
    standard_business_flow: str = Field(min_length=1, max_length=10000)
    terms_and_key_entities: str = Field(min_length=1, max_length=10000)
    dialogue_and_decision_rules: str = Field(min_length=1, max_length=10000)
    known_asr_risks: str = Field(min_length=1, max_length=10000)
    dictionary_version_ids: list[str] = Field(default_factory=list, max_length=100)
    expected_version: int | None = Field(default=None, ge=1)


class EvaluationContextStatusUpdate(BaseModel):
    """Change context availability or make one context the default."""

    model_config = ConfigDict(extra="forbid")
    enabled: bool | None = None
    is_default: bool | None = None
    expected_version: int = Field(ge=1)

    @model_validator(mode="after")
    def require_change(self) -> EvaluationContextStatusUpdate:
        """Reject empty status writes that cannot change observable state."""
        if self.enabled is None and self.is_default is None:
            raise ValueError("Choose an availability or default-state change")
        return self


class PromptTemplateWrite(BaseModel):
    """Append one validated complete Prompt template version."""

    model_config = ConfigDict(extra="forbid")
    content: str = Field(min_length=100, max_length=100000)
    expected_version: int = Field(ge=1)


class PromptTemplateRestore(BaseModel):
    """Restore historical Prompt content as a new immutable version."""

    model_config = ConfigDict(extra="forbid")
    source_version: int = Field(ge=1)
    expected_version: int = Field(ge=1)
