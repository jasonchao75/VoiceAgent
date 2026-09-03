"""Provider-aware Pipecat LLM service factory."""

from __future__ import annotations

from pipecat.services.google.llm import GoogleLLMService
from pipecat.services.openai.llm import OpenAILLMService

from src.config import LLMConfig
from src.llm.capabilities import get_model_capability


def create_llm_service(*, api_key: str, config: LLMConfig, system_prompt: str) -> object:
    """Create the native Pipecat service for a validated LLM provider.

    Args:
        api_key: Session-scoped provider credential.
        config: Validated provider and model configuration.
        system_prompt: System instruction locked for the session.

    Returns:
        A configured Pipecat LLM service.

    Raises:
        ValueError: If the provider is unsupported.
    """
    capability = get_model_capability(config.provider, config.model)
    if config.provider == "google_gemini":
        thinking: GoogleLLMService.ThinkingConfig | None = None
        if capability and capability.control_name == "thinking_budget":
            assert isinstance(capability.control_value, int)
            thinking = GoogleLLMService.ThinkingConfig(
                thinking_budget=capability.control_value, include_thoughts=False
            )
        elif capability and capability.control_name == "thinking_level":
            thinking = GoogleLLMService.ThinkingConfig(
                thinking_level=str(capability.control_value), include_thoughts=False
            )
        return GoogleLLMService(
            api_key=api_key,
            settings=GoogleLLMService.Settings(
                model=config.model,
                system_instruction=system_prompt,
                thinking=thinking,
            ),
            retry_timeout_secs=config.timeout_seconds,
            retry_on_timeout=False,
            stream_idle_timeout_secs=config.timeout_seconds,
        )

    if config.provider in {"openai", "custom"}:
        extra: dict[str, object] = {}
        if capability and capability.control_name == "reasoning_effort":
            extra["reasoning_effort"] = capability.control_value
        return OpenAILLMService(
            api_key=api_key,
            base_url=config.base_url.rstrip("/") + "/",
            retry_timeout_secs=config.timeout_seconds,
            retry_on_timeout=False,
            timeout=config.timeout_seconds,
            settings=OpenAILLMService.Settings(
                model=config.model,
                system_instruction=system_prompt,
                extra=extra,
            ),
        )
    raise ValueError(f"Unsupported LLM provider: {config.provider}")
