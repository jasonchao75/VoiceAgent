"""Native DashScope HTTP support for Qwen evaluation models."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


def is_qwen_dashscope_host(base_url: str) -> bool:
    """Return whether a URL belongs to an approved Alibaba Model Studio host."""
    parsed = urlparse(base_url)
    host = (parsed.hostname or "").casefold()
    return parsed.scheme == "https" and (
        host == "dashscope.aliyuncs.com"
        or host.endswith(".dashscope.aliyuncs.com")
        or host.endswith(".maas.aliyuncs.com")
    )


def is_native_dashscope_url(base_url: str) -> bool:
    """Detect the native `/api/v1` protocol without confusing compatible mode."""
    parsed = urlparse(base_url.rstrip("/"))
    return is_qwen_dashscope_host(base_url) and parsed.path.rstrip("/") == "/api/v1"


def validate_qwen_base_url(base_url: str) -> str:
    """Validate and normalize a supported Qwen native or compatible endpoint."""
    normalized = base_url.rstrip("/")
    parsed = urlparse(normalized)
    if not is_qwen_dashscope_host(normalized):
        raise ValueError("Qwen Base URL must use an approved HTTPS DashScope host")
    if parsed.path.rstrip("/") not in {"/api/v1", "/compatible-mode/v1"}:
        raise ValueError("Qwen Base URL must end with /api/v1 or /compatible-mode/v1")
    if parsed.query or parsed.fragment or parsed.username or parsed.password or parsed.port:
        raise ValueError("Qwen Base URL cannot include credentials, port, query, or fragment")
    return normalized


def native_dashscope_generation_url(base_url: str, model: str) -> str:
    """Choose the documented native generation route for one Qwen model."""
    route = (
        "multimodal-generation/generation"
        if model.casefold().startswith("qwen3.8-")
        else "text-generation/generation"
    )
    return f"{base_url.rstrip('/')}/services/aigc/{route}"


def native_dashscope_request(
    *,
    model: str,
    system_prompt: str,
    user_message: str,
    max_output_tokens: int,
    enable_thinking: bool | None,
    structured_json: bool = False,
) -> dict[str, Any]:
    """Build a text-only request using the native DashScope message contract."""
    output_limit_key = (
        "max_completion_tokens" if model.casefold().startswith("qwen3.8-") else "max_tokens"
    )
    parameters: dict[str, Any] = {
        "result_format": "message",
        output_limit_key: max_output_tokens,
    }
    if enable_thinking is not None:
        parameters["enable_thinking"] = enable_thinking
    if structured_json and model.casefold().startswith("qwen3.8-"):
        parameters["response_format"] = {"type": "json_object"}
    return {
        "model": model,
        "input": {
            "messages": [
                {"role": "system", "content": [{"text": system_prompt}]},
                {"role": "user", "content": [{"text": user_message}]},
            ]
        },
        "parameters": parameters,
    }


def parse_native_dashscope_response(payload: dict[str, Any]) -> tuple[str, dict[str, int]]:
    """Extract visible text and usage from a native DashScope response."""
    output = payload.get("output") or {}
    choices = output.get("choices") or []
    message = (choices[0].get("message") if choices else None) or {}
    content = message.get("content") or ""
    if isinstance(content, list):
        text = "".join(
            str(item.get("text") or "") for item in content if isinstance(item, dict)
        )
    else:
        text = str(content)
    usage = payload.get("usage") or {}
    output_details = usage.get("output_tokens_details") or {}
    prompt_details = usage.get("prompt_tokens_details") or {}
    return text, {
        "input_tokens": int(usage.get("input_tokens") or 0),
        "cached_input_tokens": int(prompt_details.get("cached_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or 0),
        "reasoning_tokens": int(output_details.get("reasoning_tokens") or 0),
    }
