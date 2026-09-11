"""Tests for deterministic, session-scoped speech-speed updates."""

from __future__ import annotations

import asyncio

import pytest

from src.pipeline.speed_control import SessionSpeedController


@pytest.mark.asyncio
async def test_speed_changes_are_serialized_and_clamped() -> None:
    """Concurrent requests build on the last provider-accepted value."""
    applied: list[float] = []

    async def apply_speed(value: float) -> None:
        await asyncio.sleep(0)
        applied.append(value)

    controller = SessionSpeedController(
        configured_speed=1.0,
        step=0.1,
        minimum=0.5,
        maximum=1.15,
        apply_speed=apply_speed,
    )
    first, second = await asyncio.gather(controller.update("faster"), controller.update("faster"))
    assert first.effective_speed == 1.1
    assert second.effective_speed == 1.15
    assert applied == [1.1, 1.15]


@pytest.mark.asyncio
async def test_failed_update_keeps_previous_speed() -> None:
    """A provider failure never commits pending session state."""

    async def fail(_value: float) -> None:
        raise TimeoutError

    controller = SessionSpeedController(
        configured_speed=0.95,
        step=0.1,
        minimum=0.7,
        maximum=1.2,
        apply_speed=fail,
    )
    result = await controller.update("faster")
    assert result.status == "failed"
    assert controller.current_speed == 0.95
    assert controller.pending_speed is None
