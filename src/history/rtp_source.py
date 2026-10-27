"""Bounded late joins from actual RTC PCM to native reported capture timestamps."""

from __future__ import annotations

import copy
import math
import re
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from typing import Any


@dataclass(frozen=True, slots=True)
class RTPCapturePoint:
    """A reported worker-clock envelope, never a hardware/ADC calibration."""

    clock_id: str
    lower_frame: int
    upper_frame: int
    proofs: tuple[dict[str, Any], ...]


class RTPCaptureLedger:
    """Join only server-observed PCM and one live epoch's immutable packet reports."""

    def __init__(self, *, now_ms: Callable[[], float]) -> None:
        """Initialize on the owning capture's monotonic clock with fixed retention budgets."""
        self._now = now_ms
        self.epoch: str | None = None
        self._clock: str | None = None
        self._chunks: OrderedDict[int, tuple[int, dict[str, Any], float]] = OrderedDict()
        self._packets: OrderedDict[tuple[int, int, str], tuple[str, float, float]] = OrderedDict()

    def begin_epoch(self, epoch: str) -> None:
        """Bind a server-created connection identity without carrying old ranges across it."""
        if not re.fullmatch("[a-f0-9]{32}", epoch):
            raise ValueError("Invalid RTC source epoch")
        if epoch != self.epoch:
            self.epoch, self._clock = epoch, None
            self._chunks.clear()
            self._packets.clear()

    def _prune(self) -> None:
        """Expire proof rather than extrapolating beyond the existing clock-anchor TTL."""
        now = self._now()
        for offset, chunk in list(self._chunks.items()):
            if not 0 <= now - chunk[-1] <= 2000:
                del self._chunks[offset]
        for key, record in list(self._packets.items()):
            if not 0 <= now - record[-1] <= 2000:
                del self._packets[key]

    def observe(self, offset: int, count: int, proof: dict[str, Any]) -> bool:
        """Retain an actual forwarded chunk only if native extents exactly cover its PCM.

        Args:
            offset: The actual forwarded 16k mono PCM offset, including unknown chunks.
            count: Its actual sample count.
            proof: Server-native r86 decoder/resampler evidence, not a client POST.

        Returns:
            Whether the chunk has complete native provenance; missing metadata stays pending.
        """
        self._prune()
        try:
            start, end = proof["processed_start"], proof["processed_end"]
            if (
                self.epoch is None
                or type(offset) is not int
                or offset < 0
                or type(count) is not int
                or count <= 0
                or type(start) is not int
                or type(end) is not int
                or start < 0
                or end - start != count * 3
                or proof["samples"] != count
                or proof["sample_rate"] != 16000
                or proof["source_rate"] != 48000
                or not 1 <= len(proof["packets"]) <= 64
            ):
                return False
            cursor = start
            for part in proof["packets"]:
                if (
                    part["connection_id"] != self.epoch
                    or any(
                        type(part[k]) is not int
                        for k in (
                            "ssrc",
                            "rtp_timestamp",
                            "decoded_start",
                            "decoded_end",
                            "segment_start",
                            "segment_end",
                        )
                    )
                    or not 0 <= part["ssrc"] < 2**32
                    or not 0 <= part["rtp_timestamp"] < 2**32
                    or not re.fullmatch("[a-f0-9]{64}", part["payload_sha256"])
                    or not 0 <= part["decoded_start"] <= part["segment_start"]
                    or part["segment_start"] != cursor
                    or not cursor < part["segment_end"] <= part["decoded_end"]
                    or (cursor - part["decoded_start"]) % 3
                    or (part["segment_end"] - cursor) % 3
                ):
                    return False
                cursor = part["segment_end"]
            if cursor != end:
                return False
            old = self._chunks.get(offset)
            if old is not None:
                return old[:2] == (count, proof)
            self._chunks[offset] = (count, copy.deepcopy(proof), self._now())
            while len(self._chunks) > 128:
                self._chunks.popitem(last=False)
            return True
        except (KeyError, TypeError, ValueError):
            return False

    def add_records(self, epoch: str, records: list[dict[str, Any]]) -> bool:
        """Accept authenticated native reports; replay cannot refresh or retarget first evidence."""
        self._prune()
        if epoch != self.epoch or not records or len(records) > 16:
            return False
        parsed = []
        try:
            clocks = {row["clock_id"] for row in records}
            if len(clocks) != 1 or (self._clock is not None and clocks != {self._clock}):
                return False
            for row in records:
                clock, captured = row["clock_id"], row["capture_time_ms"]
                key = (row["ssrc"], row["rtp_timestamp"], row["payload_sha256"])
                if (
                    not re.fullmatch("[a-f0-9]{32}", clock)
                    or type(captured) not in {float, int}
                    or not math.isfinite(captured)
                    or abs(captured) > 9_007_199_254_740_991 / 16
                    or row.get("capture_clock") != "worker_performance"
                    or any(type(n) is not int or not 0 <= n < 2**32 for n in key[:2])
                    or not re.fullmatch("[a-f0-9]{64}", key[2])
                ):
                    return False
                previous = self._packets.get(key)
                if previous is not None and previous[:2] != (clock, captured):
                    return False
                parsed.append((key, clock, float(captured)))
            if len({(key, clock, captured) for key, clock, captured in parsed}) != len(
                {key for key, _, _ in parsed}
            ):
                return False
        except (KeyError, TypeError, ValueError):
            return False
        for key, clock, captured in parsed:
            self._packets.setdefault(key, (clock, captured, self._now()))
            self._clock = clock
        while len(self._packets) > 512:
            self._packets.popitem(last=False)
        return True

    def locate_sample(self, sample: int) -> RTPCapturePoint | None:
        """Locate a VAD sample only when every adjacent native interval agrees exactly."""
        self._prune()
        if type(sample) is not int or sample < 0:
            return None
        if sample and not any(
            start < sample <= start + item[0] for start, item in self._chunks.items()
        ):
            return None
        matches: set[tuple[str, Fraction]] = set()
        evidence = []
        for offset, (count, proof, _) in self._chunks.items():
            if not offset <= sample <= offset + count:
                continue
            native_sample = proof["processed_start"] + (sample - offset) * 3
            for part in proof["packets"]:
                if not part["segment_start"] <= native_sample <= part["segment_end"]:
                    continue
                record = self._packets.get(
                    (part["ssrc"], part["rtp_timestamp"], part["payload_sha256"])
                )
                if record is None:
                    return None
                clock, captured, _ = record
                point = Fraction.from_float(captured) * 16 + Fraction(
                    native_sample - part["decoded_start"], 3
                )
                matches.add((clock, point))
                evidence.append(
                    {
                        **part,
                        "input_offset": offset,
                        "count": count,
                        "input_sample": sample,
                        "processed_sample": native_sample,
                        "capture_time_ms": captured,
                        "capture_clock_id": clock,
                        "coordinate_kind": "reported_worker_performance_16k_ticks",
                    }
                )
        if len(matches) != 1:
            return None
        clock, point = next(iter(matches))
        lower, upper = math.floor(point), math.ceil(point)
        if lower < 0 or upper > 9_007_199_254_740_991:
            return None
        return RTPCapturePoint(clock, lower, upper, tuple(evidence))
