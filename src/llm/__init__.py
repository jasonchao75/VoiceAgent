"""Language model provider construction."""

from src.llm.openai_compatible import create_openai_compatible_llm

__all__ = ["create_openai_compatible_llm"]
