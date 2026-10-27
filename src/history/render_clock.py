"""Causal server-time bounds for identified AudioWorklet frame coordinates."""

from __future__ import annotations

import math
import uuid
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RenderTimeBounds:
    """A measured interval, with the two immutable anchors that prove it."""

    lower_ms: float
    upper_ms: float
    anchor_ids: tuple[str, str]


@dataclass(frozen=True, slots=True)
class _Anchor:
    clock_id: str
    sample_rate: int
    issued_ms: float
    received_ms: float
    frame: int


class RenderClockLedger:
    """Bound a render event between actual challenge/ack observations.

    No sample-duration extrapolation, clock-offset midpoint or symmetric-network
    assumption is used. Strict frame ordering proves only a causal interval.
    Pending work and retained anchors are bounded per live session.
    """

    def __init__(self, *, now_ms: Callable[[], float]) -> None:
        """Initialize a ledger on its owning capture's server monotonic clock."""
        self._now_ms = now_ms
        self._pending: dict[str, tuple[str, int, float]] = {}
        self._anchors: dict[str, _Anchor] = {}

    @staticmethod
    def _valid_clock(clock_id: str, sample_rate: int) -> bool:
        return (
            isinstance(clock_id, str)
            and len(clock_id) == 32
            and all(char in "0123456789abcdef" for char in clock_id)
            and type(sample_rate) is int
            and 8000 <= sample_rate <= 384000
        )

    def issue(self, clock_id: str, sample_rate: int) -> str:
        """Issue an opaque, one-clock challenge or reject an exhausted budget.

        Raises:
            ValueError: The clock is invalid or eight live probes are outstanding.
        """
        now = self._now_ms()
        if not self._valid_clock(clock_id, sample_rate) or not math.isfinite(now):
            raise ValueError("Invalid render clock")
        self._pending = {
            key: value for key, value in self._pending.items() if now - value[2] <= 2000
        }
        if len(self._pending) >= 8:
            raise ValueError("Render clock pending budget exhausted")
        if any(
            anchor.clock_id == clock_id and anchor.sample_rate != sample_rate
            for anchor in self._anchors.values()
        ):
            raise ValueError("Render clock sample rate changed")
        sample_id = uuid.uuid4().hex
        self._pending[sample_id] = (clock_id, sample_rate, now)
        return sample_id

    def ack(self, sample_id: str, clock_id: str, sample_rate: int, frame: int) -> bool:
        """Retain one causal frame observation; replay cannot alter its first receipt time."""
        if (
            not self._valid_clock(clock_id, sample_rate)
            or type(frame) is not int
            or not 0 <= frame <= 9_007_199_254_740_991
        ):
            return False
        previous = self._anchors.get(sample_id)
        if previous is not None:
            return (clock_id, sample_rate, frame) == (
                previous.clock_id,
                previous.sample_rate,
                previous.frame,
            )
        pending = self._pending.pop(sample_id, None)
        now = self._now_ms()
        if (
            pending is None
            or pending[:2] != (clock_id, sample_rate)
            or not math.isfinite(now)
            or not 0 <= now - pending[2] <= 2000
        ):
            return False
        for anchor in self._anchors.values():
            if anchor.clock_id != clock_id:
                continue
            if (
                anchor.sample_rate != sample_rate
                or (frame < anchor.frame and pending[2] > anchor.received_ms)
                or (frame > anchor.frame and now < anchor.issued_ms)
            ):
                return False
        self._anchors[sample_id] = _Anchor(clock_id, sample_rate, pending[2], now, frame)
        if len(self._anchors) > 32:
            self._anchors.pop(next(iter(self._anchors)))
        return True

    def bounds(self, clock_id: str, sample_rate: int, frame: int) -> RenderTimeBounds | None:
        """Return only strictly bracketed, recent bounds in the capture's clock domain."""
        now = self._now_ms()
        if not self._valid_clock(clock_id, sample_rate) or type(frame) is not int:
            return None
        anchors = {
            key: anchor
            for key, anchor in self._anchors.items()
            if anchor.clock_id == clock_id
            and anchor.sample_rate == sample_rate
            and 0 <= now - anchor.issued_ms <= 2000
        }
        before = [(key, anchor) for key, anchor in anchors.items() if anchor.frame < frame]
        after = [(key, anchor) for key, anchor in anchors.items() if anchor.frame > frame]
        if not before or not after:
            return None
        lower_id, lower = max(before, key=lambda pair: pair[1].issued_ms)
        upper_id, upper = min(after, key=lambda pair: pair[1].received_ms)
        if lower.issued_ms > upper.received_ms:
            return None
        return RenderTimeBounds(lower.issued_ms, upper.received_ms, (lower_id, upper_id))

    def observation(self, sample_id: str) -> dict[str, object] | None:
        """Return safe immutable-clock evidence for history, without exposing pending work."""
        anchor = self._anchors.get(sample_id)
        if anchor is None:
            return None
        return {
            "sample_id": sample_id,
            "render_clock_id": anchor.clock_id,
            "render_sample_rate": anchor.sample_rate,
            "render_frame": anchor.frame,
            "server_issued_ms": anchor.issued_ms,
            "server_received_ms": anchor.received_ms,
            "evidence_source": "authenticated_worklet_causal_bracket",
        }
