"""Provider-neutral source revisions and consumed audio ranges for custom TD."""

from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass, replace


class ASRSourceEvidenceError(RuntimeError):
    """A bounded ASR provenance failure; raw text and reasons stay in captured history."""

    code = "asr_source_evidence_unavailable"


def _validate_range(start_ms: float, end_ms: float) -> None:
    """Reject timings which cannot establish an ordered audio interval."""
    if not math.isfinite(start_ms) or not math.isfinite(end_ms):
        raise ValueError("Audio timing must be finite")
    if start_ms < 0 or end_ms < start_ms:
        raise ValueError("Audio range must be non-negative and ordered")


def _sample_boundary(time_ms: float, sample_rate: int) -> int:
    """Return the PCM boundary of a half-open interval without rewriting source times.

    Args:
        time_ms: Source time on the connection's audio clock.
        sample_rate: Explicit rate of that same PCM stream.

    Returns:
        The first sample index excluded by an end, or included by a start.

    Raises:
        ValueError: If an exact sample index cannot be represented reliably.
    """
    position = time_ms * sample_rate / 1000
    if not math.isfinite(position) or abs(position) > 2**53 - 1:
        raise ValueError("Sample boundary cannot be represented reliably")
    nearest = round(position)
    # Multiplication can move an exact integer by machine noise; this is not a
    # provider-wide timestamp tolerance or a licence to add another PCM sample.
    tolerance = 4 * max(math.ulp(position), math.ulp(nearest))
    if math.isclose(position, nearest, rel_tol=0, abs_tol=tolerance):
        return nearest
    return math.ceil(position)


def _strictly_before(left: float, right: float, *, sample_rate: int | None = None) -> bool:
    """Compare PCM boundaries, retaining strict time comparison for an unknown rate.

    Args:
        left: First boundary in milliseconds on the same source clock.
        right: Second boundary in milliseconds on that clock.
        sample_rate: Explicit stream rate, or None when it is not proven.

    Returns:
        Whether the first boundary precedes the second in actual samples.

    Raises:
        ValueError: If the sample coordinate exceeds reliable representation.
    """
    tolerance = 4 * max(math.ulp(left), math.ulp(right))
    if left >= right or math.isclose(left, right, rel_tol=0, abs_tol=tolerance):
        return False
    if sample_rate is not None:
        return _sample_boundary(left, sample_rate) < _sample_boundary(right, sample_rate)
    return True


@dataclass(frozen=True, slots=True)
class TimedWord:
    """Text tied to a provider-proven interval in connection audio time."""

    text: str
    start_ms: float
    end_ms: float

    def __post_init__(self) -> None:
        """Validate time evidence without deriving timing from arrival time."""
        _validate_range(self.start_ms, self.end_ms)


def words_cover_text(text: str, words: tuple[TimedWord, ...]) -> bool:
    """Validate complete word evidence before using its times to slice a source.

    Args:
        text: Full provider snapshot; never searched for a guessed suffix.
        words: Provider-timed words in their actual order.

    Returns:
        Whether all visible text is covered, allowing casing/Unicode/spacing format changes.
    """

    def canonical(value: str) -> str:
        """Compare formatting only; never infer omitted text or its timing."""
        return "".join(unicodedata.normalize("NFKC", value).casefold().split())

    return bool(words) and canonical(text) == canonical("".join(word.text for word in words))


@dataclass(frozen=True, slots=True)
class SourceSegment:
    """One replaceable provider source range, independent of TD ownership."""

    epoch: int
    source_id: str
    revision: int
    start_ms: float
    end_ms: float
    text: str
    final: bool
    words: tuple[TimedWord, ...] = ()
    timing_reliable: bool = True
    sample_rate: int | None = None
    text_is_token: bool = False

    def __post_init__(self) -> None:
        """Validate identity and time containment before accepting evidence."""
        _validate_range(self.start_ms, self.end_ms)
        if self.epoch < 0 or self.revision < 1 or not self.source_id:
            raise ValueError("Source identity and revision are required")
        if self.sample_rate is not None and (
            type(self.sample_rate) is not int or not 8000 <= self.sample_rate <= 384000
        ):
            raise ValueError("Source sample rate must be explicitly valid")
        if self.sample_rate is not None:
            _sample_boundary(self.start_ms, self.sample_rate)
            _sample_boundary(self.end_ms, self.sample_rate)
        previous_start = self.start_ms
        for word in self.words:
            if self.boundary_before(word.start_ms, previous_start) or self.boundary_before(
                self.end_ms, word.end_ms
            ):
                raise ValueError("Words must be ordered within their source range")
            # Providers may overlap adjacent words; preserve that evidence so a
            # later consumed boundary through either word remains unsplittable.
            previous_start = word.start_ms

    def boundary_before(self, left_ms: float, right_ms: float) -> bool:
        """Compare bounds on this source's known PCM grid, keeping all raw values intact."""
        return _strictly_before(left_ms, right_ms, sample_rate=self.sample_rate)


@dataclass(frozen=True, slots=True)
class TranscriptView:
    """Current unconsumed text and its actual completeness evidence."""

    text: str
    final: bool
    segments: tuple[SourceSegment, ...]
    missing_reason: str | None = None


def join_source_segments(segments: tuple[SourceSegment, ...]) -> str:
    """Preserve token whitespace, adding word boundaries only between independent segments.

    Args:
        segments: Ordered provider source extents, including their token provenance.

    Returns:
        Text with original spaces, digit runs and unspaced scripts preserved.
    """
    text = ""
    for segment in segments:
        part = segment.text
        if (
            text
            and part
            and not segment.text_is_token
            and not text[-1].isspace()
            and not part[0].isspace()
        ):
            left = text.rstrip(".,!?;:")[-1:]
            right = part[0]
            # CJK scripts are not whitespace-delimited; numeric identifier runs are contiguous.
            chars = left + right
            spaced = all(
                char.isalnum()
                and not any(
                    script in unicodedata.name(char, "")
                    for script in ("CJK", "HIRAGANA", "KATAKANA", "HANGUL")
                )
                for char in chars
            )
            if len(chars) == 2 and spaced and any(char.isalpha() for char in chars):
                text += " "
        text += part
    return text


def slice_word_text(segment: SourceSegment, words: tuple[TimedWord, ...]) -> str | None:
    """Slice covered provider text without inventing spacing between subword tokens.

    Args:
        segment: Full provider snapshot with ordered word evidence.
        words: Contiguous selected timed words from that snapshot.

    Returns:
        The corresponding original text span, or None for incomplete/ambiguous coverage.
    """
    if not words or not words_cover_text(segment.text, segment.words):
        return None
    text = unicodedata.normalize("NFKC", segment.text)
    positions = [
        index for index, char in enumerate(text) if not char.isspace() for _ in char.casefold()
    ]
    lengths = [
        len("".join(unicodedata.normalize("NFKC", word.text).casefold().split()))
        for word in segment.words
    ]
    if not all(lengths):
        return None
    first = segment.words.index(words[0])
    last = first + len(words)
    if segment.words[first:last] != words:
        return None
    start, end = sum(lengths[:first]), sum(lengths[:last])
    if (
        start
        and positions[start - 1] == positions[start]
        or end < len(positions)
        and positions[end - 1] == positions[end]
    ):
        return None
    return text[positions[start] : positions[end - 1] + 1]


class TranscriptLedger:
    """Replace source snapshots and fence already consumed audio by connection."""

    def __init__(self) -> None:
        """Initialize one session with an empty first connection."""
        self.epoch = 0
        self._segments: dict[tuple[int, str], SourceSegment] = {}
        self._consumed: dict[int, float] = {}
        self._local_sources: set[tuple[int, str]] = set()

    def reconnect(self) -> int:
        """Advance connection identity while preserving unsubmitted old speech."""
        self.epoch += 1
        return self.epoch

    def apply(self, segment: SourceSegment) -> bool:
        """Apply a newer source revision, rejecting stale or foreign connections.

        Args:
            segment: Adapter-normalized evidence from the active connection.

        Returns:
            Whether the current source view changed.
        """
        if segment.epoch != self.epoch:
            return False
        key = (segment.epoch, segment.source_id)
        previous = self._segments.get(key)
        if previous is not None and segment.revision <= previous.revision:
            return False
        # A partial cannot downgrade a provider-final range through late delivery.
        if previous is not None and previous.final and not segment.final:
            return False
        self._segments[key] = segment
        return True

    def view(self) -> TranscriptView:
        """Combine only unconsumed source intervals, retaining an explicit gap reason."""
        segments: list[SourceSegment] = []
        missing_reason = None
        for segment in sorted(
            self._segments.values(), key=lambda item: (item.epoch, item.start_ms, item.source_id)
        ):
            if (segment.epoch, segment.source_id) in self._local_sources:
                continue
            consumed = self._consumed.get(segment.epoch, -1.0)
            if not segment.boundary_before(consumed, segment.end_ms):
                continue
            if segment.boundary_before(segment.start_ms, consumed):
                if not segment.words or not segment.timing_reliable:
                    missing_reason = "cross_commit_word_timing_unavailable"
                    continue
                if not words_cover_text(segment.text, segment.words):
                    missing_reason = "cross_commit_word_timing_incomplete"
                    continue
                if any(
                    segment.boundary_before(word.start_ms, consumed)
                    and segment.boundary_before(consumed, word.end_ms)
                    for word in segment.words
                ):
                    missing_reason = "cross_commit_word_overlaps_boundary"
                    continue
                words = tuple(
                    word
                    for word in segment.words
                    if not segment.boundary_before(word.start_ms, consumed)
                )
                selected_text = slice_word_text(segment, words)
                if selected_text is None:
                    missing_reason = "cross_commit_word_timing_incomplete"
                    continue
                text = selected_text
                # A submission owns only this tail, even if the provider keeps
                # revising a source that also includes already committed speech.
                segment = replace(segment, start_ms=consumed, text=text, words=words)
            else:
                text = segment.text
            if text:
                segments.append(segment)
        return TranscriptView(
            text=join_source_segments(tuple(segments)),
            final=bool(segments) and all(item.final for item in segments) and not missing_reason,
            segments=tuple(segments),
            missing_reason=missing_reason,
        )

    def resolve_snapshot(
        self,
        snapshot: TranscriptView,
        *,
        require_final: bool = True,
        expand_local: bool = False,
    ) -> TranscriptView | None:
        """Resolve only a submitted source extent when its corresponding Final arrives."""
        resolved = []
        for original in snapshot.segments:
            current = self._segments.get((original.epoch, original.source_id))
            if (
                current is None
                or (require_final and not current.final)
                or current.sample_rate != original.sample_rate
            ):
                return None
            if expand_local and (original.epoch, original.source_id) in self._local_sources:
                resolved.append(current)
                continue
            if (
                not current.boundary_before(current.start_ms, original.start_ms)
                and not current.boundary_before(original.start_ms, current.start_ms)
                and not current.boundary_before(current.end_ms, original.end_ms)
                and not current.boundary_before(original.end_ms, current.end_ms)
            ):
                text = current.text
            else:
                if not current.timing_reliable or not words_cover_text(current.text, current.words):
                    return None
                if any(
                    current.boundary_before(word.start_ms, boundary)
                    and current.boundary_before(boundary, word.end_ms)
                    for word in current.words
                    for boundary in (original.start_ms, original.end_ms)
                ):
                    return None
                words = [
                    word
                    for word in current.words
                    if not current.boundary_before(word.start_ms, original.start_ms)
                    and not current.boundary_before(original.end_ms, word.end_ms)
                ]
                if not words or not current.timing_reliable:
                    return None
                selected_text = slice_word_text(current, tuple(words))
                if selected_text is None:
                    return None
                text = selected_text
                current = replace(
                    current,
                    start_ms=original.start_ms,
                    end_ms=original.end_ms,
                    text=text,
                    words=tuple(words),
                )
            resolved.append(current)
        return TranscriptView(
            join_source_segments(tuple(resolved)),
            bool(resolved) and all(item.final for item in resolved),
            tuple(resolved),
        )

    def consume(self) -> TranscriptView:
        """Atomically snapshot pending text and mark its proven audio extent consumed.

        Returns:
            The submitted snapshot; empty snapshots do not advance the fence.

        Raises:
            ValueError: If unresolved range evidence prevents lossless submission.
        """
        snapshot = self.view()
        if snapshot.missing_reason:
            raise ValueError(snapshot.missing_reason)
        if snapshot.text:
            for segment in snapshot.segments:
                self._consumed[segment.epoch] = max(
                    self._consumed.get(segment.epoch, -1.0), segment.end_ms
                )
        return snapshot

    def consume_local(self, snapshot: TranscriptView | None = None) -> TranscriptView:
        """Own whole local sources without inventing digit boundaries for their revisions."""
        snapshot = snapshot if snapshot is not None else self.view()
        if snapshot.missing_reason:
            raise ValueError(snapshot.missing_reason)
        for segment in snapshot.segments:
            self._consumed[segment.epoch] = max(
                self._consumed.get(segment.epoch, -1.0), segment.end_ms
            )
            current = self._segments.get((segment.epoch, segment.source_id))
            if current is not None and current.start_ms == segment.start_ms:
                self._local_sources.add((segment.epoch, segment.source_id))
        return snapshot

    def freeze_submission(self, snapshot: TranscriptView) -> None:
        """Restore strict audio fences when locally collected content reaches the LLM."""
        for segment in snapshot.segments:
            self._local_sources.discard((segment.epoch, segment.source_id))
            self._consumed[segment.epoch] = max(
                self._consumed.get(segment.epoch, -1.0), segment.end_ms
            )
