"""OpenAI-compatible streaming LLM provider mapping."""

from pipecat.services.openai.llm import OpenAILLMService

from src.config import LLMConfig


def create_openai_compatible_llm(
    *, api_key: str, config: LLMConfig, system_prompt: str
) -> OpenAILLMService:
    """Create an async streaming Chat Completions service.

    Args:
        api_key: Session-scoped LLM API key.
        config: Validated OpenAI-compatible endpoint configuration.
        system_prompt: System instruction locked for the session.

    Returns:
        Configured Pipecat OpenAI-compatible LLM service.
    """
    # Ensure the OpenAI-compatible endpoint URL ends with a slash so that
    # path concatenation produces the correct chat/completions URL. Some
    # SDK versions or providers are sensitive to the trailing slash.
    base_url = config.base_url.rstrip("/") + "/"
    return OpenAILLMService(
        api_key=api_key,
        base_url=base_url,
        retry_timeout_secs=config.timeout_seconds,
        retry_on_timeout=False,
        timeout=config.timeout_seconds,
        settings=OpenAILLMService.Settings(
            model=config.model,
            system_instruction=system_prompt,
        ),
    )
