"""Strict provider-specific ASR configuration and capability catalog."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ASRProvider = Literal["deepgram", "speechmatics", "soniox", "assemblyai"]
TurnDetectionSource = Literal["provider_native", "off"]

FLUX_LANGUAGE_HINTS = ("en", "es", "fr", "de", "hi", "ru", "pt", "ja", "it", "nl")
NOVA3_LANGUAGES = (
    "multi",
    "af",
    "af-ZA",
    "ar",
    "ar-AE",
    "ar-SA",
    "ar-QA",
    "ar-KW",
    "ar-SY",
    "ar-LB",
    "ar-PS",
    "ar-JO",
    "ar-EG",
    "ar-SD",
    "ar-TD",
    "ar-MA",
    "ar-DZ",
    "ar-TN",
    "ar-IQ",
    "ar-IR",
    "hy",
    "as",
    "as-IN",
    "be",
    "bn",
    "bs",
    "bg",
    "ca",
    "zh-HK",
    "zh",
    "zh-CN",
    "zh-Hans",
    "zh-TW",
    "zh-Hant",
    "hr",
    "cs",
    "cs-CZ",
    "da",
    "da-DK",
    "nl",
    "en",
    "en-US",
    "en-AU",
    "en-GB",
    "en-IN",
    "en-NZ",
    "et",
    "fi",
    "nl-BE",
    "fr",
    "fr-CA",
    "ka",
    "ka-GE",
    "de",
    "de-CH",
    "el",
    "gu",
    "gu-IN",
    "he",
    "hi",
    "hu",
    "id",
    "it",
    "ja",
    "kn",
    "kk",
    "kk-KZ",
    "ko",
    "ko-KR",
    "lv",
    "lt",
    "mk",
    "ms",
    "mr",
    "mn",
    "ne",
    "no",
    "ps",
    "ps-AF",
    "fa",
    "pl",
    "pt",
    "pt-BR",
    "pt-PT",
    "pa",
    "pa-IN",
    "ro",
    "ru",
    "sr",
    "sk",
    "sl",
    "es",
    "es-419",
    "sv",
    "sv-SE",
    "tl",
    "ta",
    "te",
    "th",
    "th-TH",
    "tr",
    "tr-TR",
    "uk",
    "ur",
    "vi",
)
ASSEMBLYAI_LANGUAGES = (
    "en",
    "ar",
    "es",
    "fr",
    "de",
    "it",
    "pt",
    "da",
    "nl",
    "fi",
    "he",
    "hi",
    "ja",
    "zh",
    "no",
    "sv",
    "tr",
    "vi",
)
SPEECHMATICS_LANGUAGE_PACKS = (
    "ar",
    "ar_en",
    "ba",
    "eu",
    "be",
    "bg",
    "bn",
    "yue",
    "ca",
    "hr",
    "cs",
    "da",
    "nl",
    "en",
    "en_ms",
    "en_ta",
    "eo",
    "et",
    "fa",
    "fi",
    "fr",
    "gl",
    "de",
    "el",
    "he",
    "hi",
    "hu",
    "ia",
    "it",
    "id",
    "ga",
    "ja",
    "ko",
    "lv",
    "lt",
    "ms",
    "mt",
    "cmn",
    "cmn_en",
    "cmn_en_ms_ta",
    "mr",
    "mn",
    "nn",
    "no",
    "pl",
    "pt",
    "ro",
    "ru",
    "sk",
    "sl",
    "es",
    "sv",
    "sw",
    "tl",
    "ta",
    "th",
    "tr",
    "ug",
    "uk",
    "ur",
    "vi",
    "cy",
)
SPEECHMATICS_DOMAINS: dict[str, tuple[str, ...]] = {
    "ar_en": ("medical",),
    "da": ("medical",),
    "de": ("medical",),
    "en": ("finance", "medical"),
    "es": ("bilingual-en", "medical"),
    "fi": ("medical",),
    "fr": ("medical",),
    "nl": ("medical",),
    "no": ("medical",),
    "sv": ("medical",),
}
# Feature-discovery fixtures currently expose this conservative punctuation subset
# for every Realtime language pack used by the product. Keeping it catalog data
# prevents arbitrary Unicode symbols from reaching the provider configuration.
SPEECHMATICS_PUNCTUATION_MARKS: dict[str, tuple[str, ...]] = {
    language: (".", ",", "?", "!") for language in SPEECHMATICS_LANGUAGE_PACKS
}
SONIOX_LANGUAGES = (
    "af",
    "sq",
    "ar",
    "az",
    "eu",
    "be",
    "bn",
    "bs",
    "bg",
    "ca",
    "zh",
    "hr",
    "cs",
    "da",
    "nl",
    "en",
    "et",
    "fi",
    "fr",
    "gl",
    "de",
    "el",
    "gu",
    "he",
    "hi",
    "hu",
    "id",
    "it",
    "ja",
    "kn",
    "kk",
    "ko",
    "lv",
    "lt",
    "mk",
    "ms",
    "ml",
    "mr",
    "no",
    "fa",
    "pl",
    "pt",
    "pa",
    "ro",
    "ru",
    "sr",
    "sk",
    "sl",
    "es",
    "sw",
    "sv",
    "tl",
    "ta",
    "te",
    "th",
    "tr",
    "uk",
    "ur",
    "vi",
    "cy",
)

LANGUAGE_DISPLAY_NAMES: dict[str, str] = {
    "af": "Afrikaans",
    "sq": "Albanian",
    "ar": "Arabic",
    "az": "Azerbaijani",
    "eu": "Basque",
    "be": "Belarusian",
    "bn": "Bengali",
    "bs": "Bosnian",
    "bg": "Bulgarian",
    "ca": "Catalan",
    "zh": "Chinese",
    "hr": "Croatian",
    "cs": "Czech",
    "da": "Danish",
    "nl": "Dutch",
    "en": "English",
    "et": "Estonian",
    "fi": "Finnish",
    "fr": "French",
    "gl": "Galician",
    "de": "German",
    "el": "Greek",
    "gu": "Gujarati",
    "he": "Hebrew",
    "hi": "Hindi",
    "hu": "Hungarian",
    "id": "Indonesian",
    "it": "Italian",
    "ja": "Japanese",
    "kn": "Kannada",
    "kk": "Kazakh",
    "ko": "Korean",
    "lv": "Latvian",
    "lt": "Lithuanian",
    "mk": "Macedonian",
    "ms": "Malay",
    "ml": "Malayalam",
    "mr": "Marathi",
    "no": "Norwegian",
    "fa": "Persian",
    "pl": "Polish",
    "pt": "Portuguese",
    "pa": "Punjabi",
    "ro": "Romanian",
    "ru": "Russian",
    "sr": "Serbian",
    "sk": "Slovak",
    "sl": "Slovenian",
    "es": "Spanish",
    "sw": "Swahili",
    "sv": "Swedish",
    "tl": "Tagalog",
    "ta": "Tamil",
    "te": "Telugu",
    "th": "Thai",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "ur": "Urdu",
    "vi": "Vietnamese",
    "cy": "Welsh",
}


class StrictASRModel(BaseModel):
    """Reject provider fields that do not belong to the selected model."""

    model_config = ConfigDict(extra="forbid")


def _normalize_phrases(values: list[str], *, field_name: str) -> list[str]:
    """Trim phrases and reject empty, duplicate, or oversized entries."""
    normalized = [value.strip() for value in values]
    if any(not value or len(value) > 200 for value in normalized):
        raise ValueError(f"{field_name} entries must be non-empty and at most 200 characters")
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{field_name} entries must be unique")
    return normalized


class DeepgramFluxOptions(StrictASRModel):
    """Deepgram Flux V2 options."""

    schema_version: Literal[1] = 1
    language_hints: list[str] = Field(default_factory=list, max_length=10)
    eot_threshold: float = Field(default=0.7, ge=0.5, le=1.0)
    eot_timeout_ms: int = Field(default=5000, ge=500, le=60000)
    keyterms: list[str] = Field(default_factory=list, max_length=100)
    profanity_filter: bool = False
    numerals: bool = False
    redact: Literal["numbers", "aggressive_numbers"] | None = None

    @field_validator("keyterms")
    @classmethod
    def validate_keyterms(cls, values: list[str]) -> list[str]:
        """Keep repeated query parameters plain and deterministic."""
        return _normalize_phrases(values, field_name="Keyterm")

    @field_validator("language_hints")
    @classmethod
    def validate_language_hints(cls, values: list[str]) -> list[str]:
        """Restrict Flux hints to the provider's multilingual catalog."""
        if any(value not in FLUX_LANGUAGE_HINTS for value in values):
            raise ValueError("Flux language hints must come from the model catalog")
        if len(values) != len(set(values)):
            raise ValueError("Flux language hints must be unique")
        return values


class DeepgramNova3Options(StrictASRModel):
    """Deepgram Nova-3 V1 streaming options."""

    schema_version: Literal[1] = 1
    language: str = Field(default="multi", min_length=2, max_length=20)
    endpointing_ms: int = Field(default=300, gt=0)
    interim_results: bool = True
    vad_events: bool = True
    keyterms: list[str] = Field(default_factory=list, max_length=100)
    smart_format: bool = True
    numerals: bool = False
    profanity_filter: bool = False
    redact: Literal["numbers", "aggressive_numbers"] | None = None
    diarize_model: str | None = Field(default=None, max_length=100)

    @field_validator("keyterms")
    @classmethod
    def validate_keyterms(cls, values: list[str]) -> list[str]:
        """Map every line to one unweighted repeated keyterm parameter."""
        return _normalize_phrases(values, field_name="Keyterm")

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        """Restrict Nova-3 to the current Deepgram language catalog."""
        if value not in NOVA3_LANGUAGES:
            raise ValueError("Nova-3 language must come from the model catalog")
        return value


class SpeechmaticsVocabularyEntry(StrictASRModel):
    """One Speechmatics additional-vocabulary entry."""

    content: str = Field(min_length=1, max_length=200)
    sounds_like: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        """Reject whitespace-only vocabulary entries."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("Vocabulary content must not be empty")
        return normalized


class SpeechmaticsPunctuationOptions(StrictASRModel):
    """Speechmatics punctuation override settings."""

    sensitivity: float = Field(default=0.5, ge=0.0, le=1.0)
    permitted_marks: Literal["all"] | list[str] = "all"

    @field_validator("permitted_marks")
    @classmethod
    def validate_marks(cls, value: Literal["all"] | list[str]) -> Literal["all"] | list[str]:
        """Require a unique list of single Unicode characters for custom marks."""
        if value == "all":
            return value
        if not value or any(len(mark) != 1 or not mark.strip() for mark in value):
            raise ValueError("Custom permitted marks must contain one character per entry")
        if len(value) != len(set(value)):
            raise ValueError("Custom permitted marks must be unique")
        return value


class SpeechmaticsOptions(StrictASRModel):
    """Speechmatics Realtime Enhanced options."""

    schema_version: Literal[1] = 1
    language: str = Field(default="en", min_length=2, max_length=30)
    domain: str | None = Field(default=None, max_length=100)
    max_delay: float = Field(default=0.7, ge=0.0)
    include_partials: bool = True
    emit_sentences: bool = False
    turn_detection_mode: Literal["smart_turn", "adaptive", "fixed"] = "smart_turn"
    end_of_utterance_silence_trigger: float = Field(default=0.5, gt=0.0)
    end_of_utterance_max_delay: float = Field(default=10.0, gt=0.0)
    additional_vocab: list[SpeechmaticsVocabularyEntry] = Field(default_factory=list)
    punctuation_overrides: SpeechmaticsPunctuationOptions = Field(
        default_factory=SpeechmaticsPunctuationOptions
    )

    @model_validator(mode="after")
    def validate_turn_delays(self) -> SpeechmaticsOptions:
        """Keep the SDK maximum delay strictly above the silence trigger."""
        if self.end_of_utterance_max_delay <= self.end_of_utterance_silence_trigger:
            raise ValueError("Maximum EOU delay must be greater than the silence trigger")
        marks = self.punctuation_overrides.permitted_marks
        supported = SPEECHMATICS_PUNCTUATION_MARKS.get(self.language, ())
        if marks != "all" and any(mark not in supported for mark in marks):
            raise ValueError(
                "Custom permitted marks must come from the selected Language Pack catalog"
            )
        return self


class SonioxGeneralContext(StrictASRModel):
    """One Soniox general-context key/value pair."""

    key: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=1000)


class SonioxOptions(StrictASRModel):
    """Soniox stt-rt-v5 session options."""

    schema_version: Literal[1] = 1
    language_hints: list[str] = Field(default_factory=list, max_length=len(SONIOX_LANGUAGES))
    language_hints_strict: bool = False
    enable_language_identification: bool = True
    endpoint_sensitivity: float = Field(default=0.3, ge=-1.0, le=1.0)
    endpoint_latency_adjustment_level: int = Field(default=0, ge=0, le=3)
    max_endpoint_delay_ms: int = Field(default=1500, ge=500, le=3000)
    context_general: list[SonioxGeneralContext] = Field(default_factory=list)
    context_text: str = Field(default="", max_length=10000)
    context_terms: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("language_hints")
    @classmethod
    def validate_languages(cls, values: list[str]) -> list[str]:
        """Accept only languages advertised for stt-rt-v5."""
        if any(value not in SONIOX_LANGUAGES for value in values):
            raise ValueError("Soniox language hints must come from the model catalog")
        if len(values) != len(set(values)):
            raise ValueError("Soniox language hints must be unique")
        return values

    @field_validator("context_terms")
    @classmethod
    def validate_terms(cls, values: list[str]) -> list[str]:
        """Keep session terms normalized and unique."""
        return _normalize_phrases(values, field_name="Context term")


class AssemblyAIOptions(StrictASRModel):
    """AssemblyAI Universal-3.5 Pro realtime options."""

    schema_version: Literal[1] = 1
    language_codes: list[str] = Field(default_factory=list, max_length=10)
    mode: Literal["min_latency", "balanced", "max_accuracy"] = "balanced"
    prompt: str = Field(default="", max_length=10000)
    keyterms_prompt: list[str] = Field(default_factory=list, max_length=100)
    continuous_partials: bool = True
    min_turn_silence: int = Field(default=128, ge=0)
    max_turn_silence: int = Field(default=1280, gt=0)
    vad_threshold: float = Field(default=0.3, ge=0.0, le=1.0)
    interruption_delay: int = Field(default=500, ge=0, le=1000)
    agent_context_enabled: bool = True
    user_context_carryover_enabled: bool = True
    previous_context_n_turns: int = Field(default=5, ge=0, le=100)
    voice_focus: Literal["near-field", "far-field"] | None = None
    voice_focus_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    speaker_labels: bool = False

    @field_validator("language_codes")
    @classmethod
    def validate_languages(cls, values: list[str]) -> list[str]:
        """Restrict steering to the current U3.5 Pro language catalog."""
        if any(value not in ASSEMBLYAI_LANGUAGES for value in values):
            raise ValueError("AssemblyAI language codes must come from the model catalog")
        if len(values) != len(set(values)):
            raise ValueError("AssemblyAI language codes must be unique")
        return values

    @field_validator("keyterms_prompt")
    @classmethod
    def validate_keyterms(cls, values: list[str]) -> list[str]:
        """Normalize the provider's bounded keyterm prompt list."""
        return _normalize_phrases(values, field_name="Keyterm")

    @model_validator(mode="after")
    def validate_turn_window(self) -> AssemblyAIOptions:
        """Ensure dependent AssemblyAI settings form a valid request."""
        if self.max_turn_silence < self.min_turn_silence:
            raise ValueError("Maximum turn silence must not be below minimum turn silence")
        if self.voice_focus_threshold is not None and self.voice_focus is None:
            raise ValueError("Voice Focus threshold requires a Voice Focus mode")
        return self


ASROptions = (
    DeepgramFluxOptions
    | DeepgramNova3Options
    | SpeechmaticsOptions
    | SonioxOptions
    | AssemblyAIOptions
)

_MODEL_CONTRACTS: dict[tuple[str, str], tuple[type[StrictASRModel], tuple[str, ...], str]] = {
    ("deepgram", "flux-general-en"): (DeepgramFluxOptions, ("provider_native",), "provider_native"),
    ("deepgram", "flux-general-multi"): (
        DeepgramFluxOptions,
        ("provider_native",),
        "provider_native",
    ),
    ("deepgram", "nova-3"): (DeepgramNova3Options, ("off",), "off"),
    ("speechmatics", "enhanced"): (
        SpeechmaticsOptions,
        ("provider_native", "off"),
        "provider_native",
    ),
    ("soniox", "stt-rt-v5"): (SonioxOptions, ("provider_native",), "provider_native"),
    ("assemblyai", "universal-3-5-pro"): (
        AssemblyAIOptions,
        ("provider_native",),
        "provider_native",
    ),
}


def _advanced_fields(provider: str, model: str) -> list[dict[str, Any]]:
    """Return server-owned UI definitions for one provider/model branch."""
    common_format: list[dict[str, Any]] = [
        {
            "name": "profanity_filter",
            "id": "asr-profanity",
            "label": "Profanity filter",
            "kind": "boolean",
        },
        {"name": "numerals", "id": "asr-numerals", "label": "Numerals", "kind": "boolean"},
        {
            "name": "redact",
            "id": "asr-redact",
            "label": "Redact",
            "kind": "select",
            "options": [
                [None, "Off"],
                ["numbers", "Numbers"],
                ["aggressive_numbers", "Aggressive numbers"],
            ],
        },
    ]
    if provider == "deepgram" and model.startswith("flux-"):
        return [
            {
                "name": "eot_threshold",
                "id": "asr-eot-threshold",
                "label": "EOT threshold",
                "kind": "number",
                "min": 0.5,
                "max": 1.0,
                "step": 0.05,
            },
            {
                "name": "eot_timeout_ms",
                "id": "asr-eot-timeout",
                "label": "EOT timeout (ms)",
                "kind": "number",
                "min": 500,
                "max": 60000,
                "step": 1,
            },
            {
                "name": "keyterms",
                "id": "asr-keyterms",
                "label": "Keyterms · one per line",
                "kind": "lines",
            },
            *common_format,
        ]
    if provider == "deepgram":
        return [
            {
                "name": "endpointing_ms",
                "id": "asr-endpointing",
                "label": "Endpointing silence (ms)",
                "kind": "number",
                "min": 1,
                "step": 1,
            },
            {
                "name": "interim_results",
                "id": "asr-interim",
                "label": "Interim results",
                "kind": "boolean",
            },
            {
                "name": "vad_events",
                "id": "asr-vad-events",
                "label": "VAD events",
                "kind": "boolean",
            },
            {
                "name": "keyterms",
                "id": "asr-keyterms",
                "label": "Keyterms · one per line",
                "kind": "lines",
            },
            {
                "name": "smart_format",
                "id": "asr-smart-format",
                "label": "Smart format",
                "kind": "boolean",
            },
            *common_format[1:],
            common_format[0],
            {
                "name": "diarize_model",
                "id": "asr-diarize-model",
                "label": "Diarize model",
                "kind": "text",
            },
        ]
    if provider == "speechmatics":
        return [
            {"name": "domain", "id": "asr-domain", "label": "Domain", "kind": "domain"},
            {
                "name": "max_delay",
                "id": "asr-max-delay",
                "label": "Maximum delay (s)",
                "kind": "number",
                "min": 0,
                "step": 0.1,
            },
            {
                "name": "include_partials",
                "id": "asr-include-partials",
                "label": "Include partials",
                "kind": "boolean",
            },
            {
                "name": "emit_sentences",
                "id": "asr-emit-sentences",
                "label": "Emit completed sentences",
                "kind": "boolean",
                "help": "AddSegment accumulates text; only EndOfTurn submits to the LLM.",
            },
            {
                "name": "turn_detection_mode",
                "id": "asr-turn-mode",
                "label": "Turn mode",
                "kind": "select",
                "options": [
                    ["smart_turn", "Smart Turn"],
                    ["adaptive", "Adaptive"],
                    ["fixed", "Fixed silence"],
                ],
            },
            {
                "name": "end_of_utterance_silence_trigger",
                "id": "asr-silence-trigger",
                "label": "Silence trigger (s)",
                "kind": "number",
                "min": 0.1,
                "max": 2,
                "step": 0.1,
            },
            {
                "name": "end_of_utterance_max_delay",
                "id": "asr-max-eou-delay",
                "label": "Maximum EOU delay (s)",
                "kind": "number",
                "min": 0.2,
                "step": 0.1,
                "help": (
                    "Must be strictly greater than the silence trigger. SDK default: 10.0 seconds."
                ),
            },
            {
                "name": "additional_vocab",
                "id": "asr-vocabulary",
                "label": "Additional vocabulary",
                "kind": "vocabulary",
            },
            {
                "name": "punctuation_overrides.sensitivity",
                "id": "asr-punctuation-sensitivity",
                "label": "Punctuation sensitivity",
                "kind": "number",
                "min": 0,
                "max": 1,
                "step": 0.1,
            },
            {
                "name": "punctuation_overrides.permitted_marks",
                "id": "asr-punctuation-mode",
                "label": "Permitted punctuation marks",
                "kind": "marks",
            },
        ]
    if provider == "soniox":
        return [
            {
                "name": "language_hints_strict",
                "id": "asr-strict-hints",
                "label": "Strict language hints",
                "kind": "boolean",
            },
            {
                "name": "enable_language_identification",
                "id": "asr-language-id",
                "label": "Language identification",
                "kind": "boolean",
            },
            {
                "name": "endpoint_sensitivity",
                "id": "asr-endpoint-sensitivity",
                "label": "Endpoint sensitivity",
                "kind": "number",
                "min": -1,
                "max": 1,
                "step": 0.1,
            },
            {
                "name": "endpoint_latency_adjustment_level",
                "id": "asr-latency-level",
                "label": "Latency adjustment level",
                "kind": "select",
                "options": [[0, "0"], [1, "1"], [2, "2"], [3, "3"]],
            },
            {
                "name": "max_endpoint_delay_ms",
                "id": "asr-max-endpoint-delay",
                "label": "Max endpoint delay (ms)",
                "kind": "number",
                "min": 500,
                "max": 3000,
                "step": 1,
            },
            {
                "name": "context_general",
                "id": "asr-context-general",
                "label": "General context · key=value per line",
                "kind": "key_values",
            },
            {
                "name": "context_text",
                "id": "asr-context-text",
                "label": "Context text",
                "kind": "textarea",
            },
            {
                "name": "context_terms",
                "id": "asr-context-terms",
                "label": "Terms · one per line",
                "kind": "lines",
            },
        ]
    return [
        {
            "name": "mode",
            "id": "asr-assembly-mode",
            "label": "Mode",
            "kind": "select",
            "options": [
                ["balanced", "Balanced"],
                ["min_latency", "Minimum latency"],
                ["max_accuracy", "Maximum accuracy"],
            ],
        },
        {"name": "prompt", "id": "asr-prompt", "label": "Prompt", "kind": "textarea"},
        {
            "name": "keyterms_prompt",
            "id": "asr-keyterms-prompt",
            "label": "Keyterms prompt · one per line",
            "kind": "lines",
        },
        {
            "name": "continuous_partials",
            "id": "asr-continuous-partials",
            "label": "Continuous partials",
            "kind": "boolean",
        },
        {
            "name": "min_turn_silence",
            "id": "asr-min-silence",
            "label": "Minimum turn silence (ms)",
            "kind": "number",
            "min": 0,
            "step": 1,
            "class": "asr-assembly-mode-value",
        },
        {
            "name": "max_turn_silence",
            "id": "asr-max-silence",
            "label": "Maximum turn silence (ms)",
            "kind": "number",
            "min": 1,
            "step": 1,
            "class": "asr-assembly-mode-value",
        },
        {
            "name": "vad_threshold",
            "id": "asr-vad-threshold",
            "label": "VAD threshold",
            "kind": "number",
            "min": 0,
            "max": 1,
            "step": 0.05,
            "help": (
                "Lower detects quieter speech; higher reduces noise triggers. Independent of Mode."
            ),
        },
        {
            "name": "interruption_delay",
            "id": "asr-interruption-delay",
            "label": "Interruption delay (ms)",
            "kind": "number",
            "min": 0,
            "max": 1000,
            "step": 1,
            "class": "asr-assembly-mode-value",
        },
        {
            "name": "agent_context_enabled",
            "id": "asr-agent-context",
            "label": "Agent Context",
            "kind": "boolean",
        },
        {
            "name": "user_context_carryover_enabled",
            "id": "asr-user-context",
            "label": "User Context Carryover",
            "kind": "boolean",
        },
        {
            "name": "previous_context_n_turns",
            "id": "asr-previous-context",
            "label": "Previous context entries",
            "kind": "number",
            "min": 0,
            "max": 100,
            "step": 1,
        },
        {
            "name": "voice_focus",
            "id": "asr-voice-focus",
            "label": "Voice Focus",
            "kind": "select",
            "options": [[None, "Off"], ["near-field", "Near-field"], ["far-field", "Far-field"]],
        },
        {
            "name": "voice_focus_threshold",
            "id": "asr-voice-focus-threshold",
            "label": "Voice Focus threshold",
            "kind": "number",
            "min": 0,
            "max": 1,
            "step": 0.05,
            "placeholder": "Provider default",
        },
        {
            "name": "speaker_labels",
            "id": "asr-speaker-labels",
            "label": "Speaker labels",
            "kind": "boolean",
        },
    ]


def _catalog_model(provider: str, model: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Attach defaults and server-owned Advanced definitions to a model entry."""
    model_type = _MODEL_CONTRACTS[(provider, model)][0]
    defaults = model_type().model_dump(mode="json")
    fields = _advanced_fields(provider, model)
    for field in fields:
        value: Any = defaults
        for part in field["name"].split("."):
            value = value.get(part) if isinstance(value, dict) else None
        field["default"] = value
    titles = {
        ("deepgram", "flux-general-en"): "Deepgram Flux",
        ("deepgram", "flux-general-multi"): "Deepgram Flux",
        ("deepgram", "nova-3"): "Deepgram Nova-3",
        ("speechmatics", "enhanced"): "Speechmatics",
        ("soniox", "stt-rt-v5"): "Soniox",
        ("assemblyai", "universal-3-5-pro"): "AssemblyAI",
    }
    return {
        **payload,
        "advanced_title": titles[(provider, model)],
        "advanced_fields": fields,
    }


def normalize_provider(value: str) -> str:
    """Map the legacy Deepgram identifier onto the provider-level ID."""
    return "deepgram" if value == "deepgram_flux" else value


def validate_asr_options(
    *, provider: str, model: str, turn_detection_source: str, options: dict[str, Any]
) -> dict[str, Any]:
    """Validate and normalize one provider/model configuration branch.

    Args:
        provider: Provider ID, including the legacy Deepgram alias.
        model: Provider model ID.
        turn_detection_source: Product-level turn source.
        options: Provider-specific persisted JSON object.

    Returns:
        A JSON-compatible dictionary containing defaults and normalized values.

    Raises:
        ValueError: If the model, turn source, or options are unsupported.
    """
    canonical_provider = normalize_provider(provider)
    contract = _MODEL_CONTRACTS.get((canonical_provider, model))
    if contract is None:
        raise ValueError("Unsupported ASR provider/model combination")
    model_type, allowed_sources, _default_source = contract
    if turn_detection_source not in allowed_sources:
        raise ValueError("Turn Detection source is unavailable for the selected ASR model")
    parsed = model_type.model_validate(options)
    if isinstance(parsed, DeepgramFluxOptions):
        if model == "flux-general-en" and parsed.language_hints:
            raise ValueError("Language hints require Flux multilingual")
    if isinstance(parsed, SpeechmaticsOptions):
        if parsed.language not in SPEECHMATICS_LANGUAGE_PACKS:
            raise ValueError("Speechmatics language must come from the Language Pack catalog")
        if parsed.domain and parsed.domain not in SPEECHMATICS_DOMAINS.get(parsed.language, ()):
            raise ValueError("Speechmatics domain is unavailable for the selected Language Pack")
        if turn_detection_source == "off" and parsed.turn_detection_mode != "fixed":
            raise ValueError("Speechmatics Off requires Fixed silence mode")
    return parsed.model_dump(mode="json")


def default_turn_source(provider: str, model: str) -> str:
    """Return the catalog default turn source for one provider model."""
    contract = _MODEL_CONTRACTS.get((normalize_provider(provider), model))
    if contract is None:
        raise ValueError("Unsupported ASR provider/model combination")
    return contract[2]


def asr_provider_catalog() -> dict[str, Any]:
    """Return the public non-secret ASR capability catalog."""
    return {
        "providers": [
            {
                "id": "deepgram",
                "name": "Deepgram",
                "models": [
                    _catalog_model(
                        "deepgram",
                        "flux-general-en",
                        {
                            "id": "flux-general-en",
                            "name": "Flux ASR · English",
                            "language_control": {"kind": "fixed", "values": ["en"]},
                            "turn_sources": ["provider_native"],
                            "default_turn_source": "provider_native",
                        },
                    ),
                    _catalog_model(
                        "deepgram",
                        "flux-general-multi",
                        {
                            "id": "flux-general-multi",
                            "name": "Flux ASR · Multilingual",
                            "language_control": {
                                "kind": "hints",
                                "values": list(FLUX_LANGUAGE_HINTS),
                            },
                            "turn_sources": ["provider_native"],
                            "default_turn_source": "provider_native",
                        },
                    ),
                    _catalog_model(
                        "deepgram",
                        "nova-3",
                        {
                            "id": "nova-3",
                            "name": "Nova-3",
                            "language_control": {
                                "kind": "single",
                                "values": list(NOVA3_LANGUAGES),
                            },
                            "turn_sources": ["off"],
                            "default_turn_source": "off",
                        },
                    ),
                ],
            },
            {
                "id": "speechmatics",
                "name": "Speechmatics",
                "models": [
                    _catalog_model(
                        "speechmatics",
                        "enhanced",
                        {
                            "id": "enhanced",
                            "name": "Realtime Enhanced",
                            "language_control": {
                                "kind": "single",
                                "values": list(SPEECHMATICS_LANGUAGE_PACKS),
                                "account_filtered": False,
                                "source": "bundled Feature Discovery snapshot",
                            },
                            "domains_by_language": {
                                language: list(domains)
                                for language, domains in SPEECHMATICS_DOMAINS.items()
                            },
                            "punctuation_marks_by_language": {
                                language: list(marks)
                                for language, marks in SPEECHMATICS_PUNCTUATION_MARKS.items()
                            },
                            "turn_sources": ["provider_native", "off"],
                            "default_turn_source": "provider_native",
                        },
                    )
                ],
            },
            {
                "id": "soniox",
                "name": "Soniox",
                "models": [
                    _catalog_model(
                        "soniox",
                        "stt-rt-v5",
                        {
                            "id": "stt-rt-v5",
                            "name": "stt-rt-v5",
                            "language_control": {
                                "kind": "hints",
                                "values": list(SONIOX_LANGUAGES),
                                "labels": {
                                    code: LANGUAGE_DISPLAY_NAMES[code] for code in SONIOX_LANGUAGES
                                },
                                "source": "bundled GET /v1/models snapshot",
                            },
                            "turn_sources": ["provider_native"],
                            "default_turn_source": "provider_native",
                        },
                    )
                ],
            },
            {
                "id": "assemblyai",
                "name": "AssemblyAI",
                "models": [
                    _catalog_model(
                        "assemblyai",
                        "universal-3-5-pro",
                        {
                            "id": "universal-3-5-pro",
                            "name": "Universal-3.5 Pro",
                            "language_control": {
                                "kind": "steering",
                                "values": list(ASSEMBLYAI_LANGUAGES),
                                "labels": {
                                    code: LANGUAGE_DISPLAY_NAMES[code]
                                    for code in ASSEMBLYAI_LANGUAGES
                                },
                                "max_selected": 10,
                            },
                            "turn_sources": ["provider_native"],
                            "default_turn_source": "provider_native",
                        },
                    )
                ],
            },
        ]
    }
