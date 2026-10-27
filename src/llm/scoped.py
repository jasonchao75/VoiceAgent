"""Response-scoped provider services loaded after the base factory is initialized."""

from pipecat.services.google.llm import GoogleLLMService
from pipecat.services.openai.llm import OpenAILLMService

from src.pipeline.response_scope import ResponseScopedLLMMixin


class ScopedOpenAILLMService(ResponseScopedLLMMixin, OpenAILLMService):
    """Use the locked OpenAI service with self-developed response provenance."""


class ScopedGoogleLLMService(ResponseScopedLLMMixin, GoogleLLMService):
    """Use the locked Google service with the same response and tool fences."""
