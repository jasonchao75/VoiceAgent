"""Response ownership fences for Final replacement of a submitted Partial (D-049)."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, replace

SourceIds = tuple[tuple[int, str], ...]


def canonical_final_text(value: str) -> str:
    """Ignore only the user-approved punctuation and whitespace differences."""
    return "".join(
        c for c in value if not c.isspace() and not unicodedata.category(c).startswith("P")
    )


@dataclass(frozen=True, slots=True)
class ResponseVersion:
    """One answer version belonging to a single original user submission."""

    turn_id: str
    response_id: str
    source_ids: SourceIds
    text: str
    final: bool
    speech_generation: int
    response_revision: int


@dataclass(frozen=True, slots=True)
class ResponseRestart:
    """Required cancellation and replacement, without erasing prior playback facts."""

    cancel_response_id: str
    new_response: ResponseVersion
    source_revision: int
    reason: str = "final_replaces_submitted_partial"


class ResponseRevisions:
    """Session-local response identity and irreversible-operation deduplication."""

    def __init__(self) -> None:
        """Create an empty response owner and operation audit set."""
        self.user_submission_count = 0
        self._speech_generation = 0
        self._current: ResponseVersion | None = None
        self._submitted_turns: set[str] = set()
        self._operations: set[tuple[str, str, SourceIds]] = set()
        self.restarts: list[ResponseRestart] = []

    @property
    def current(self) -> ResponseVersion | None:
        """Return immutable provenance; callers must still validate its speech generation."""
        return self._current

    @property
    def speech_generation(self) -> int:
        """Expose the current input generation for unscoped synthesis cancellation."""
        return self._speech_generation

    def begin_speech(self) -> None:
        """Fence the previous response as soon as a new user speech generation starts."""
        self._speech_generation += 1

    def submit(
        self,
        *,
        turn_id: str,
        source_ids: SourceIds,
        text: str,
        final: bool,
    ) -> ResponseVersion:
        """Register exactly one original user submission with its source evidence.

        Raises:
            ValueError: If the submission is empty or the turn was submitted before.
        """
        if not text.strip() or not source_ids or turn_id in self._submitted_turns:
            raise ValueError("A nonempty user turn can only be submitted once")
        self._submitted_turns.add(turn_id)
        self.user_submission_count += 1
        self._current = ResponseVersion(
            turn_id,
            f"{turn_id}:1",
            source_ids,
            text,
            final,
            self._speech_generation,
            1,
        )
        return self._current

    def finalize(
        self,
        *,
        turn_id: str,
        source_ids: SourceIds,
        revision: int,
        text: str,
    ) -> ResponseRestart | None:
        """Finalize once, restarting only for content changes beyond punctuation and spaces.

        Args:
            turn_id: Original TD user turn, never a newly allocated turn.
            source_ids: Proven source ranges, including connection epochs.
            revision: Source revision retained for audit.
            text: Complete effective Final text for the submitted range.

        Returns:
            Cancellation and restart identity, or None for stale/duplicate/foreign Final.
        """
        current = self._current
        if (
            current is None
            or current.final
            or current.turn_id != turn_id
            or current.source_ids != source_ids
            or not text.strip()
            or revision < 1
            or current.speech_generation != self._speech_generation
        ):
            return None

        if canonical_final_text(current.text) == canonical_final_text(text):
            self._current = replace(current, text=text, final=True)
            return None
        replacement = ResponseVersion(
            current.turn_id,
            f"{turn_id}:{current.response_revision + 1}",
            source_ids,
            text,
            True,
            current.speech_generation,
            current.response_revision + 1,
        )
        restart = ResponseRestart(current.response_id, replacement, revision)
        self._current = replacement
        self.restarts.append(restart)
        return restart

    def accepts_output(self, response_id: str) -> bool:
        """Reject late tokens and audio from cancelled or older speech generations."""
        return bool(
            self._current
            and self._current.response_id == response_id
            and self._current.speech_generation == self._speech_generation
        )

    def claim_operation(self, turn_id: str, action: str, source_ids: SourceIds) -> bool:
        """Claim a business side effect once across response revisions.

        This only deduplicates operation identity. The tool executor must still
        validate its source revision, generation, arguments and execution result.
        """
        identity = (turn_id, action, source_ids)
        if identity in self._operations:
            return False
        self._operations.add(identity)
        return True
