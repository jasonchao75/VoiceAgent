"""Tests for confirmed Deepgram Flux runtime settings."""

import asyncio
from types import SimpleNamespace

import pytest

from src.tts.confirmed_flux import ConfirmedDeepgramFluxTTSService


class _FluxHarness(ConfirmedDeepgramFluxTTSService):
    """Small protocol harness that avoids opening a provider connection."""

    def __init__(self, *, timeout: float = 0.05) -> None:
        self._configure_timeout = timeout
        self._configure_result = None
        self._settings = SimpleNamespace(speed=1.1)
        self.sent: list[dict[str, object]] = []

    def _transport_is_active(self) -> bool:
        return True

    async def _transport_send_json(self, message: dict[str, object]) -> None:
        self.sent.append(message)


@pytest.mark.asyncio
async def test_configure_waits_for_provider_success() -> None:
    """A queued message alone must not be reported as applied."""
    service = _FluxHarness()
    update = asyncio.create_task(service._send_configure())
    await asyncio.sleep(0)

    assert not update.done()
    assert service.sent == [{"type": "Configure", "speed": 1.1}]
    assert service._configure_result is not None
    service._configure_result.set_result(None)
    await update


@pytest.mark.asyncio
async def test_configure_times_out_without_provider_result() -> None:
    """A missing provider acknowledgement fails within the configured bound."""
    service = _FluxHarness(timeout=0.001)

    with pytest.raises(TimeoutError):
        await service._send_configure()


@pytest.mark.asyncio
async def test_configure_rejects_disconnected_service() -> None:
    """A disconnected provider cannot produce a false successful update."""
    service = _FluxHarness()
    service._transport_is_active = lambda: False  # type: ignore[method-assign]

    with pytest.raises(ConnectionError):
        await service._send_configure()
