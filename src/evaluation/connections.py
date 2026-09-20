"""Real, secret-safe connectivity checks for evaluation ASR providers."""

from __future__ import annotations

import uuid
from typing import Any

import httpx


class ASRConnectionError(RuntimeError):
    """Classified ASR connection failure safe to show in the browser."""

    def __init__(self, category: str, message: str) -> None:
        """Store a bounded category and secret-free explanation."""
        super().__init__(message)
        self.category = category


_ASR_PROBES: dict[str, tuple[str, str, str, str]] = {
    "soniox": (
        "GET",
        "https://api.soniox.com/v1/models",
        "Authorization",
        "Bearer {key}",
    ),
    "speechmatics": (
        "GET",
        "https://asr.api.speechmatics.com/v2/jobs?limit=1",
        "Authorization",
        "Bearer {key}",
    ),
    # User-profile access is a separate permission and rejects valid restricted Scribe keys.
    # A batch token verifies the exact STT capability without uploading or billing audio.
    "elevenlabs": (
        "POST",
        "https://api.elevenlabs.io/v1/single-use-token/batch_scribe",
        "xi-api-key",
        "{key}",
    ),
}


async def test_asr_connection(
    provider: str,
    api_key: str,
    *,
    timeout: float = 10.0,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    """Run a non-billable authenticated provider probe without uploading audio."""
    probe = _ASR_PROBES.get(provider)
    if probe is None:
        raise ASRConnectionError("unsupported_provider", "Unsupported ASR provider.")
    method, url, header_name, header_template = probe
    headers = {header_name: header_template.format(key=api_key)}
    try:
        async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
            response = await client.request(method, url, headers=headers)
    except httpx.TimeoutException as exc:
        raise ASRConnectionError("timeout", "The provider did not respond before timeout.") from exc
    except httpx.HTTPError as exc:
        raise ASRConnectionError(
            "connection_failed", "The server could not connect to the provider."
        ) from exc
    if response.status_code in {401, 403}:
        raise ASRConnectionError("authentication_failed", "The provider rejected this API key.")
    if response.status_code == 429:
        raise ASRConnectionError("rate_limited", "The provider rate-limited the request.")
    if response.status_code >= 400:
        raise ASRConnectionError(
            "upstream_error", f"The provider returned HTTP {response.status_code}."
        )
    return {
        "success": True,
        "category": "ok",
        "diagnostic_id": str(uuid.uuid4()),
        "summary": "Authenticated provider probe passed.",
        "suggestion": "The connection is saved and ready for evaluation.",
    }
