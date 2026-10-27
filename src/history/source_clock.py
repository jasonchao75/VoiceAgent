"""Exact provenance from forwarded PCM sample offsets to microphone frames."""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class _Span:
    offset: int
    count: int
    clock_id: str
    sample_rate: int
    frame: int


class CaptureSampleLedger:
    """Keep bounded source spans without interpolating gaps or connection clocks."""

    def __init__(self, *, max_spans: int = 4096) -> None:
        """Initialize a session-local ledger.

        Args:
            max_spans: Maximum retained input spans.

        Raises:
            ValueError: The retention budget is not positive.
        """
        if type(max_spans) is not int or max_spans < 1:
            raise ValueError("Invalid source span budget")
        self._spans: deque[_Span] = deque(maxlen=max_spans)
        self._offset = 0
        self._last: tuple[str, int, int] | None = None

    @property
    def offset(self) -> int:
        """Return the actual forwarded offset, including chunks with missing provenance."""
        return self._offset

    def append(
        self,
        count: int,
        *,
        clock_id: str | None = None,
        sample_rate: int | None = None,
        source_spans: list[tuple[int, int]] | None = None,
    ) -> bool:
        """Consume actual PCM length, accepting only complete ordered provenance.

        Args:
            count: Actual forwarded mono PCM sample count.
            clock_id: Immutable capture context identity.
            sample_rate: Capture and forwarded PCM rate; resampling needs separate proof.
            source_spans: Ordered capture frame starts and counts for this PCM chunk.

        Returns:
            Whether the entire chunk has valid source provenance.

        Raises:
            ValueError: Actual PCM count is invalid.
        """
        if type(count) is not int or count <= 0:
            raise ValueError("Invalid PCM sample count")
        offset = self._offset
        self._offset += count
        if (
            not isinstance(clock_id, str)
            or len(clock_id) != 32
            or any(char not in "0123456789abcdef" for char in clock_id)
            or type(sample_rate) is not int
            or not 8000 <= sample_rate <= 384000
            or not source_spans
            or len(source_spans) > 64
        ):
            return False
        previous_end = (
            self._last[2]
            if self._last is not None and self._last[:2] == (clock_id, sample_rate)
            else -1
        )
        total = 0
        for frame, length in source_spans:
            if (
                type(frame) is not int
                or type(length) is not int
                or frame < 0
                or length <= 0
                or frame + length > 9_007_199_254_740_991
                or frame < previous_end
            ):
                return False
            previous_end = frame + length
            total += length
        if total != count:
            return False
        for frame, length in source_spans:
            self._spans.append(_Span(offset, length, clock_id, sample_rate, frame))
            offset += length
        self._last = (clock_id, sample_rate, previous_end)
        return True

    def locate(self, offset: int) -> tuple[str, int, int] | None:
        """Map an exact sample boundary only when every adjacent span agrees.

        Args:
            offset: Session forwarded PCM sample boundary.

        Returns:
            Clock identity, rate and frame, or None for missing/ambiguous evidence.
        """
        if type(offset) is not int or offset < 0:
            return None
        if offset > 0 and not any(
            span.offset < offset <= span.offset + span.count for span in self._spans
        ):
            return None
        matches = {
            (span.clock_id, span.sample_rate, span.frame + offset - span.offset)
            for span in self._spans
            if span.offset <= offset <= span.offset + span.count
        }
        return next(iter(matches)) if len(matches) == 1 else None

    def evidence(self, offset: int) -> list[dict[str, int | str]]:
        """Return the retained spans proving one exact input boundary for audit.

        Args:
            offset: Forwarded PCM boundary whose provenance is requested.

        Returns:
            Matching immutable spans, or an empty list for ambiguous/missing evidence.
        """
        if self.locate(offset) is None:
            return []
        return [
            {
                "input_offset": span.offset,
                "count": span.count,
                "clock_id": span.clock_id,
                "sample_rate": span.sample_rate,
                "source_frame": span.frame,
            }
            for span in self._spans
            if span.offset <= offset <= span.offset + span.count
        ]


def observe_input_source(
    ledger: CaptureSampleLedger, *, name: str, sample_count: int, sample_rate: int, channels: int
) -> bool:
    """Consume input PCM and validate its optional versioned provenance envelope.

    Args:
        ledger: Owning live session sample ledger.
        name: Existing protobuf audio name; no PCM bytes are repurposed.
        sample_count: Actual forwarded mono sample count.
        sample_rate: Actual input PCM rate.
        channels: Actual input channel count.

    Returns:
        Whether metadata fully proves this chunk's capture identity.
    """
    prefix = "voice-agent-input-v1:"
    try:
        if not name.startswith(prefix) or len(name) > 4096:
            raise ValueError("Missing source envelope")
        data = json.loads(name[len(prefix) :])
        if (
            not isinstance(data, dict)
            or set(data) != {"clock_id", "sample_rate", "offset", "spans"}
            or type(data["offset"]) is not int
            or data["offset"] != ledger._offset
            or type(data["sample_rate"]) is not int
            or data["sample_rate"] != sample_rate
            or channels != 1
            or sample_rate != 16000
            or not isinstance(data["spans"], list)
            or any(not isinstance(item, list) or len(item) != 2 for item in data["spans"])
        ):
            raise ValueError("Invalid source envelope")
        return ledger.append(
            sample_count,
            clock_id=data["clock_id"],
            sample_rate=sample_rate,
            source_spans=data["spans"],
        )
    except (ValueError, TypeError, KeyError):
        return ledger.append(sample_count)
