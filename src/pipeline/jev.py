"""Bounded backend-only System One client; no implicit retries or semantic defaults."""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx
from pydantic import SecretStr


@dataclass(frozen=True, slots=True)
class JevResult:
    """Safe decision evidence; failures carry no fabricated probabilities."""

    status: str
    noul: float | None = None
    probabilities: dict[str, float] | None = None


def parse_answer(
    payload: Any,
    *,
    noul_id: str,
    choice_id: str,
    option_ids: set[str],
) -> JevResult:
    """Validate the actual System One answer fields and complete Choice distribution.

    Raises:
        ValueError: If types, coverage or finite probability constraints are invalid.
    """
    try:
        answers = payload["answers"]
        noul_answer, choice_answer = answers[noul_id], answers[choice_id]
        if noul_answer["type"] != "noul" or choice_answer["type"] != "choice":
            raise ValueError("Unexpected answer type")
        noul, probabilities = noul_answer["noul"], choice_answer["probabilities"]
        if not isinstance(probabilities, dict) or probabilities.keys() != option_ids:
            raise ValueError("Incomplete probability coverage")
        values = [noul, *probabilities.values()]
        if any(
            isinstance(value, bool)
            or not isinstance(value, (float, int))
            or not math.isfinite(value)
            or not 0 <= value <= 1
            for value in values
        ):
            raise ValueError("Invalid probability")
        if not math.isclose(sum(probabilities.values()), 1, abs_tol=1e-6):
            raise ValueError("Invalid probability sum")
        return JevResult("ok", float(noul), dict(probabilities))
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError("Invalid System One response") from error


class JevClient:
    """One session's bounded, serial, explicitly timed cloud decision client."""

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        client: httpx.AsyncClient,
        max_calls: int,
    ) -> None:
        """Bind the server-held credential and caller-provided request budget.

        Args:
            endpoint: Explicit HTTPS System One endpoint without userinfo or query.
            api_key: Server-side secret, never recorded in result or repr.
            client: Session-owned asynchronous HTTP client, also injectable for tests.
            max_calls: Finite total budget for this client; failures consume attempts.

        Raises:
            ValueError: If the endpoint, credential or attempt budget is invalid.
        """
        parts = urlsplit(endpoint)
        if (
            parts.scheme != "https"
            or not parts.hostname
            or parts.username
            or parts.password
            or parts.query
            or parts.fragment
            or not api_key
            or max_calls < 1
        ):
            raise ValueError("Invalid Jev connection settings")
        self._endpoint = endpoint
        self._api_key = SecretStr(api_key)
        self._client = client
        self._remaining = max_calls
        self._busy = False

    async def decide(
        self,
        *,
        model: str,
        state: Any,
        questions: dict[str, Any],
        noul_id: str,
        choice_id: str,
        timeout: float = 10.0,
    ) -> JevResult:
        """Request one decision without blocking audio or queueing unbounded stale calls.

        Args:
            model: Configured Jev model, not an inferred provider alias.
            state: Latest assistant/user text and transcript status.
            questions: Official typed questions without local wait settings.
            noul_id: Configured yield-probability question key.
            choice_id: Configured speech-state question key.
            timeout: Positive request/whole-operation timeout in seconds.

        Returns:
            Safe probability evidence, or a bounded categorized failure.
        """
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Jev timeout must be positive and finite")
        if self._busy:
            return JevResult("busy")
        if self._remaining == 0:
            return JevResult("budget_exhausted")
        self._remaining -= 1
        self._busy = True
        try:
            async with asyncio.timeout(timeout):
                response = await self._client.post(
                    self._endpoint,
                    headers={"Authorization": f"Bearer {self._api_key.get_secret_value()}"},
                    json={"model": model, "state": state, "questions": questions},
                    timeout=timeout,
                    follow_redirects=False,
                )
            if response.status_code != 200:
                return JevResult(f"http_{response.status_code}")
            try:
                criteria = questions[choice_id]["criteria"]
                return parse_answer(
                    response.json(), noul_id=noul_id, choice_id=choice_id, option_ids=set(criteria)
                )
            except (ValueError, TypeError, KeyError):
                return JevResult("invalid_response")
        except (TimeoutError, httpx.TimeoutException):
            return JevResult("timeout")
        except httpx.HTTPError:
            return JevResult("transport_error")
        finally:
            self._busy = False
