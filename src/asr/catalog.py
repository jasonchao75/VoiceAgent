"""Authenticated provider catalog discovery and normalization."""

from __future__ import annotations

from typing import Any

import httpx

from src.asr.config import LANGUAGE_DISPLAY_NAMES, asr_provider_catalog

CATALOG_TIMEOUT_SECONDS = 10.0
SPEECHMATICS_FEATURES_URL = "https://eu1.asr.api.speechmatics.com/v1/discovery/features"
SONIOX_MODELS_URL = "https://api.soniox.com/v1/models"


async def discover_asr_model_catalog(
    provider: str,
    api_key: str,
    *,
    timeout: float = CATALOG_TIMEOUT_SECONDS,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Fetch and normalize the account-visible model catalog.

    Args:
        provider: Provider whose account catalog should be loaded.
        api_key: Decrypted provider credential; never returned or logged.
        timeout: Maximum seconds for provider discovery requests.
        client: Optional injected client used by no-network contract tests.

    Returns:
        One normalized model entry compatible with the public ASR catalog.

    Raises:
        ValueError: If the provider has no authenticated discovery contract.
        RuntimeError: If the provider response cannot prove the required model.
        httpx.HTTPError: If discovery fails at the transport or HTTP layer.
    """
    owns_client = client is None
    if timeout <= 0:
        raise ValueError("Catalog timeout must be positive")
    active_client = client or httpx.AsyncClient(timeout=timeout)
    try:
        if provider == "speechmatics":
            response = await active_client.get(
                SPEECHMATICS_FEATURES_URL,
                headers={"Authorization": f"Bearer {api_key}"},
            )
            response.raise_for_status()
            return _normalize_speechmatics(response.json())
        if provider == "soniox":
            response = await active_client.get(
                SONIOX_MODELS_URL,
                headers={"Authorization": f"Bearer {api_key}"},
            )
            response.raise_for_status()
            return _normalize_soniox(response.json())
        raise ValueError("Authenticated catalog discovery is unavailable for this provider")
    finally:
        if owns_client:
            await active_client.aclose()


def _base_model(provider: str) -> dict[str, Any]:
    catalog = asr_provider_catalog()
    entry = next(item for item in catalog["providers"] if item["id"] == provider)
    return dict(entry["models"][0])


def _normalize_speechmatics(payload: Any) -> dict[str, Any]:
    """Normalize the Feature Discovery language-pack response."""
    if not isinstance(payload, dict):
        raise RuntimeError("Speechmatics Feature Discovery returned an invalid response")
    entries = payload.get("language_packs") or payload.get("languages") or []
    values: list[str] = []
    domains: dict[str, list[str]] = {}
    for entry in entries if isinstance(entries, list) else []:
        if isinstance(entry, str):
            values.append(entry)
            continue
        if not isinstance(entry, dict):
            continue
        code = entry.get("language") or entry.get("code") or entry.get("id")
        if not isinstance(code, str) or not code or code == "auto":
            continue
        values.append(code)
        raw_domains = entry.get("domains") or []
        normalized = [
            item if isinstance(item, str) else item.get("id")
            for item in raw_domains
            if isinstance(item, (str, dict))
        ]
        supported = [item for item in normalized if isinstance(item, str) and item]
        if supported:
            domains[code] = supported
    if not values:
        raise RuntimeError("Speechmatics account returned no Realtime language packs")
    model = _base_model("speechmatics")
    model["language_control"] = {
        "kind": "single",
        "values": list(dict.fromkeys(values)),
        "account_filtered": True,
        "source": "Speechmatics Feature Discovery",
    }
    model["domains_by_language"] = domains
    return model


def _normalize_soniox(payload: Any) -> dict[str, Any]:
    """Normalize GET /v1/models for the selected realtime model."""
    if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
        raise RuntimeError("Soniox model discovery returned an invalid response")
    model_payload = next(
        (
            item
            for item in payload["models"]
            if isinstance(item, dict) and (item.get("id") or item.get("model")) == "stt-rt-v5"
        ),
        None,
    )
    if model_payload is None:
        raise RuntimeError("Soniox account does not expose stt-rt-v5")
    raw_languages = model_payload.get("languages") or []
    languages: list[str] = []
    labels: dict[str, str] = {}
    for item in raw_languages:
        if isinstance(item, str):
            code = item
            display_name = LANGUAGE_DISPLAY_NAMES.get(code, code)
        elif isinstance(item, dict):
            raw_code = item.get("code")
            if not isinstance(raw_code, str) or not raw_code:
                continue
            code = raw_code
            provider_name = item.get("name") or item.get("language_name")
            display_name = (
                provider_name
                if isinstance(provider_name, str) and provider_name.strip()
                else LANGUAGE_DISPLAY_NAMES.get(code, code)
            )
        else:
            continue
        if not isinstance(code, str) or not code:
            continue
        languages.append(code)
        labels[code] = display_name
    if not languages:
        raise RuntimeError("Soniox stt-rt-v5 returned no languages")
    unique_languages = list(dict.fromkeys(languages))
    model = _base_model("soniox")
    model["language_control"] = {
        "kind": "hints",
        "values": unique_languages,
        "labels": {code: labels[code] for code in unique_languages},
        "source": "Soniox GET /v1/models",
    }
    return model
