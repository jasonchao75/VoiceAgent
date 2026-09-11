"""Deterministic, session-scoped conversational speech-speed control."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

SpeedAction = Literal["faster", "slower", "normal", "configured"]
SpeedStatus = Literal["applied", "at_limit", "unsupported", "failed"]
SpeedApplier = Callable[[float], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class SpeedResult:
    """Safe result returned to the LLM after one deterministic update."""

    status: SpeedStatus
    action: SpeedAction
    old_speed: float
    target_speed: float
    effective_speed: float


class SessionSpeedController:
    """Serialize speed changes and commit state only after provider success."""

    def __init__(
        self,
        *,
        configured_speed: float,
        step: float,
        minimum: float,
        maximum: float,
        apply_speed: SpeedApplier,
    ) -> None:
        """Initialize isolated state for one active voice session."""
        self.configured_speed = configured_speed
        self.current_speed = configured_speed
        self.pending_speed: float | None = None
        self._step = step
        self._minimum = minimum
        self._maximum = maximum
        self._apply_speed = apply_speed
        self._lock = asyncio.Lock()

    async def update(self, action: SpeedAction) -> SpeedResult:
        """Calculate, clamp and apply one requested speed transition."""
        async with self._lock:
            old = self.current_speed
            requested = {
                "faster": old + self._step,
                "slower": old - self._step,
                "normal": 1.0,
                "configured": self.configured_speed,
            }[action]
            target = round(min(self._maximum, max(self._minimum, requested)) * 20) / 20
            if target == old:
                return SpeedResult("at_limit", action, old, target, old)
            self.pending_speed = target
            try:
                await self._apply_speed(target)
            except Exception:
                self.pending_speed = None
                return SpeedResult("failed", action, old, target, old)
            self.current_speed = target
            self.pending_speed = None
            return SpeedResult("applied", action, old, target, target)
