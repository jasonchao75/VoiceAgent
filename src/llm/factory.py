"""Provider-aware Pipecat LLM service factory."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pipecat.processors.frame_processor import FrameProcessor
from pipecat.services.google.llm import GoogleLLMService, GoogleThinkingConfig
from pipecat.services.openai.llm import OpenAILLMService

from src.config import LLMConfig
from src.llm.capabilities import get_model_capability

if TYPE_CHECKING:
    from src.pipeline.response_scope import ResponseScope


def create_llm_service(
    *,
    api_key: str,
    config: LLMConfig,
    system_prompt: str,
    response_scope: ResponseScope | None = None,
) -> FrameProcessor:
    """Create the native Pipecat service for a validated LLM provider.

    Args:
        api_key: Session-scoped provider credential.
        config: Validated provider and model configuration.
        system_prompt: System instruction locked for the session.
        response_scope: Optional custom TD response/task ownership fence.

    Returns:
        A configured Pipecat LLM service.

    Raises:
        ValueError: If the provider is unsupported.
    """
    if response_scope is not None:
        # Load only after the factory module is initialized: pipeline's public
        # entry point also depends on this factory.
        from src.llm.scoped import ScopedGoogleLLMService, ScopedOpenAILLMService

    scoped_args: dict[str, Any] = (
        {"response_scope": response_scope} if response_scope is not None else {}
    )
    capability = get_model_capability(config.provider, config.model)
    if config.provider == "google_gemini":
        thinking: GoogleThinkingConfig | None = None
        if config.reasoning_mode == "off":
            thinking = GoogleLLMService.ThinkingConfig(thinking_budget=0, include_thoughts=False)
        elif (
            config.reasoning_mode == "minimal"
            and capability
            and capability.control_name == "thinking_budget"
        ):
            assert isinstance(capability.control_value, int)
            thinking = GoogleLLMService.ThinkingConfig(
                thinking_budget=capability.control_value, include_thoughts=False
            )
        elif (
            config.reasoning_mode == "minimal"
            and capability
            and capability.control_name == "thinking_level"
        ):
            thinking = GoogleLLMService.ThinkingConfig(
                thinking_level=str(capability.control_value), include_thoughts=False
            )
        google_service_type = (
            ScopedGoogleLLMService if response_scope is not None else GoogleLLMService
        )
        return google_service_type(
            **scoped_args,
            api_key=api_key,
            settings=GoogleLLMService.Settings(
                model=config.model,
                system_instruction=system_prompt,
                temperature=config.temperature,
                thinking=thinking,
                max_tokens=config.max_response_tokens,
            ),
            retry_timeout_secs=config.timeout_seconds,
            retry_on_timeout=False,
            stream_idle_timeout_secs=config.timeout_seconds,
        )

    if config.provider in {"openai", "custom"}:
        extra: dict[str, object] = {}
        if config.reasoning_mode == "off":
            extra["reasoning_effort"] = "none"
        elif (
            config.reasoning_mode == "minimal"
            and capability
            and capability.control_name == "reasoning_effort"
        ):
            extra["reasoning_effort"] = capability.control_value
        openai_service_type = (
            ScopedOpenAILLMService if response_scope is not None else OpenAILLMService
        )
        return openai_service_type(
            **scoped_args,
            api_key=api_key,
            base_url=config.base_url.rstrip("/") + "/",
            retry_timeout_secs=config.timeout_seconds,
            retry_on_timeout=False,
            timeout=config.timeout_seconds,
            settings=OpenAILLMService.Settings(
                model=config.model,
                system_instruction=system_prompt,
                temperature=config.temperature,
                max_completion_tokens=config.max_response_tokens,
                extra=extra,
            ),
        )
    raise ValueError(f"Unsupported LLM provider: {config.provider}")
