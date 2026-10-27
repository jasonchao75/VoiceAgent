"""Deterministic timing core for one session's custom turn authority.

All timestamps are milliseconds in the caller's monotonic audio clock. Network
responses only propose a target; they never submit a turn themselves.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WaitResult:
    """Auditable waiting decomposition, with silence subtracted exactly once."""

    noul_ms: float
    choice_ms: float
    target_ms: float
    remaining_ms: float
    conflict: bool


@dataclass(frozen=True, slots=True)
class WaitPolicy:
    """Explicit caller-supplied values; prototype examples are not runtime defaults."""

    minimum_ms: float
    maximum_ms: float
    final_wait_ms: float
    alpha: float
    conflict_threshold: float

    def __post_init__(self) -> None:
        """Reject inconsistent or non-finite timing and fusion settings."""
        values = (
            self.minimum_ms,
            self.maximum_ms,
            self.final_wait_ms,
            self.alpha,
            self.conflict_threshold,
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("Wait settings must be finite")
        if not 0 <= self.minimum_ms <= self.maximum_ms or self.maximum_ms <= 0:
            raise ValueError("Invalid silence bounds")
        if self.final_wait_ms < 0 or not 0 <= self.alpha <= 1:
            raise ValueError("Invalid Final wait or fusion weight")
        if not 0 <= self.conflict_threshold <= 1:
            raise ValueError("Invalid conflict threshold")

    def fuse(
        self,
        noul: float,
        probabilities: dict[str, float],
        option_waits: dict[str, float],
        *,
        elapsed_ms: float,
    ) -> WaitResult:
        """Compute the full-distribution wait and apply conservative conflict protection.

        Args:
            noul: Probability of yielding the floor, never confidence.
            probabilities: Complete Choice probability distribution.
            option_waits: Configured target silence per Choice option.
            elapsed_ms: Already elapsed continuous silence including network time.

        Returns:
            Finite bounded target and remaining silence with decomposition.

        Raises:
            ValueError: If probabilities, option coverage or timing are invalid.
        """
        if not math.isfinite(noul) or not 0 <= noul <= 1:
            raise ValueError("Invalid Noul probability")
        if not probabilities or probabilities.keys() != option_waits.keys():
            raise ValueError("Choice distribution must cover every configured option")
        if any(not math.isfinite(p) or not 0 <= p <= 1 for p in probabilities.values()):
            raise ValueError("Invalid Choice probability")
        if not math.isclose(sum(probabilities.values()), 1.0, abs_tol=1e-6):
            raise ValueError("Choice probabilities must sum to one")
        if any(not math.isfinite(wait) or wait < 0 for wait in option_waits.values()):
            raise ValueError("Invalid option wait")
        if not math.isfinite(elapsed_ms) or elapsed_ms < 0:
            raise ValueError("Invalid elapsed silence")
        noul_ms = self.minimum_ms + (1 - noul) * (self.maximum_ms - self.minimum_ms)
        choice_ms = sum(probabilities[key] * wait for key, wait in option_waits.items())
        complete = probabilities.get("complete", 0)
        incomplete = probabilities.get("incomplete", 0) + probabilities.get("holding_floor", 0)
        threshold = self.conflict_threshold
        conflict = (noul >= threshold and incomplete >= threshold) or (
            1 - noul >= threshold and complete >= threshold
        )
        target = (
            max(noul_ms, choice_ms)
            if conflict
            else (self.alpha * noul_ms + (1 - self.alpha) * choice_ms)
        )
        target = min(self.maximum_ms, max(self.minimum_ms, target))
        return WaitResult(noul_ms, choice_ms, target, max(0.0, target - elapsed_ms), conflict)


@dataclass(frozen=True, slots=True)
class CandidateToken:
    """Generation identity used to reject asynchronous results after continuation."""

    generation: int


@dataclass(frozen=True, slots=True)
class TurnCommit:
    """A single atomic submission, distinct from a provider Final."""

    candidate: CandidateToken
    text: str
    final: bool
    reason: str
    committed_at_ms: float


class TurnClock:
    """Single-threaded atomic state transitions for an asyncio session owner."""

    def __init__(self, policy: WaitPolicy) -> None:
        """Create an idle clock with no candidate and explicit timing policy."""
        self.policy = policy
        self.media_healthy = True
        self._generation = 0
        self.text_revision = 0
        self._candidate: CandidateToken | None = None
        self._silence_at = 0.0
        self._text = ""
        self._final = False
        self._target_ms: float | None = None
        self._final_deadline: float | None = None
        self._committed = False

    def pause(self, speech_end_ms: float) -> CandidateToken:
        """Start a new candidate at proven speech end, not at VAD confirmation time."""
        if not math.isfinite(speech_end_ms) or speech_end_ms < 0:
            raise ValueError("Invalid speech end time")
        self._generation += 1
        self._candidate = CandidateToken(self._generation)
        self._silence_at = speech_end_ms
        self._text = ""
        self._final = False
        self._target_ms = None
        self._final_deadline = None
        self._committed = False
        return self._candidate

    def resume(self) -> None:
        """Invalidate every pending result before processing new speech."""
        self._generation += 1
        self._candidate = None
        self._target_ms = None
        self._final_deadline = None

    def transcript(self, token: CandidateToken, text: str, *, final: bool) -> bool:
        """Update valid candidate text; changed text invalidates its semantic verdict."""
        if token != self._candidate or self._committed:
            return False
        if text != self._text:
            self.text_revision += 1
            self._target_ms = None
        self._text, self._final = text, final
        return True

    def semantic(
        self,
        token: CandidateToken,
        target_ms: float,
        *,
        text_revision: int,
    ) -> bool:
        """Install a valid target without changing the independent maximum deadline."""
        if token != self._candidate or self._committed:
            return False
        if text_revision != self.text_revision:
            return False
        if not math.isfinite(target_ms):
            raise ValueError("Invalid semantic target")
        self._target_ms = max(self.policy.minimum_ms, min(self.policy.maximum_ms, target_ms))
        return True

    def poll(self, now_ms: float) -> TurnCommit | None:
        """Commit at most once when valid silence, text and timing all permit it.

        Args:
            now_ms: Current monotonic audio time in milliseconds.

        Returns:
            One submission or None. No await separates the final check and commit.
        """
        if not math.isfinite(now_ms) or now_ms < self._silence_at:
            raise ValueError("Invalid current audio time")
        if self._candidate is None or self._committed or not self.media_healthy:
            return None
        if not self._text.strip():
            return None
        maximum = self._silence_at + self.policy.maximum_ms
        reason = "maximum_silence"
        if now_ms < maximum:
            # A prior Final window cannot authorize text whose semantic target was invalidated.
            if self._target_ms is None or now_ms < self._silence_at + self._target_ms:
                return None
            reason = "semantic_final" if self._final else "final_wait_expired"
            if not self._final:
                if self._final_deadline is None:
                    self._final_deadline = min(maximum, now_ms + self.policy.final_wait_ms)
                if now_ms < self._final_deadline:
                    return None
        self._committed = True
        return TurnCommit(self._candidate, self._text, self._final, reason, now_ms)
