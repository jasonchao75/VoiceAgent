"""Strict identifier priority evaluation using ordinary reply snapshots and proven timing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import pairwise

from src.asr.td_config import IdentifierRuleSettings
from src.asr.transcript import TranscriptView
from src.pipeline.identifier import IdentifierCollection, IdentifierSource

_BUSINESS_UNITS = re.compile(
    r"[\u3400-\u9fff]|\d|[^\W\d_\u3400-\u9fff]+(?:['’][^\W\d_\u3400-\u9fff]+)*"
)


def business_units(text: str) -> int:
    """Count actual words/CJK characters/digits independently of provider tokenization."""
    return len(_BUSINESS_UNITS.findall(text))


@dataclass(frozen=True, slots=True)
class IdentifierEvaluation:
    """Observed routing and echo eligibility, without claiming any playback happened."""

    path: str
    matched_keyword: str | None
    source: IdentifierSource | None = None
    units: int = 0
    start_ms: float | None = None
    end_ms: float | None = None
    wpm: float | None = None
    timing_reason: str | None = None
    echo_eligible: bool = False


class IdentifierRules:
    """Evaluate one actual candidate against the same collection used by LLM tools."""

    def __init__(self, settings: IdentifierRuleSettings, collection: IdentifierCollection) -> None:
        """Keep explicit per-session policy; no request, timer or audio synthesis occurs here."""
        self.settings = settings
        self.collection = collection
        self._start_new = False
        self._committed = False

    def begin_input(self) -> None:
        """Capture success at actual new speech, never at an ASR chunk or keyword repetition."""
        self._start_new = self.collection.successful

    def can_begin_collection(self) -> bool:
        """Expose original new-speech eligibility to the controlled mixed-input path."""
        return self._start_new

    def committed(self) -> None:
        """Only a completed TD submission can finalize a pure collection."""
        self._committed = True
        self.confirm_committed()

    def confirm_committed(self) -> None:
        """A matching late Final may complete proof for an already submitted collection."""
        if self._committed:
            self.collection.mark_success(final=self.collection.all_final)

    def evaluate(
        self, snapshot: TranscriptView, assistant: str, *, allow_new_collection: bool = True
    ) -> IdentifierEvaluation:
        """Route the entire input, always collect valid pure input, and separately assess speed."""
        keyword = next(
            (word for word in self.settings.keywords if word.casefold() in assistant.casefold()),
            None,
        )
        if not self.settings.enabled or keyword is None or not snapshot.text:
            return IdentifierEvaluation("ordinary", keyword)
        if snapshot.missing_reason or not snapshot.segments:
            return IdentifierEvaluation(
                "ordinary", keyword, timing_reason="source_range_unavailable"
            )
        if self.collection.vocabulary.normalize(snapshot.text) is None:
            source = self.collection.bind_snapshot(snapshot)
            return IdentifierEvaluation("ordinary", keyword, source=source)
        if self._start_new and allow_new_collection:
            self.collection.begin_collection()
            self._start_new = False
            self._committed = False
        source = self.collection.bind_snapshot(snapshot)
        result = self.collection.collect_local(source)
        if result["status"] not in {"submitted", "duplicate"}:
            return IdentifierEvaluation("ordinary", keyword, source=source)
        path = "local"
        if self.settings.collection:
            count = len(self.collection.value)
            target = self.settings.collection.target_length
            path = (
                "incomplete" if count < target else "complete" if count == target else "overlength"
            )
        units = business_units(snapshot.text)
        start, end, reason = self._timing(snapshot)
        wpm = units * 60000 / (end - start) if start is not None and end is not None else None
        eligible = (
            wpm is not None
            and self.settings.wpm_threshold is not None
            and (wpm < self.settings.wpm_threshold)
        )
        return IdentifierEvaluation(path, keyword, source, units, start, end, wpm, reason, eligible)

    def _timing(self, snapshot: TranscriptView) -> tuple[float | None, float | None, str | None]:
        """Require full unit coverage by word intervals, never arrival/window duration."""
        epochs = {segment.epoch for segment in snapshot.segments}
        if len(epochs) != 1:
            return None, None, "cross_connection_timing_unavailable"
        if any(not segment.timing_reliable or not segment.words for segment in snapshot.segments):
            return None, None, "word_timing_unavailable"
        words = tuple(word for segment in snapshot.segments for word in segment.words)
        vocabulary = self.collection.vocabulary
        if vocabulary.normalize(" ".join(word.text for word in words)) != vocabulary.normalize(
            snapshot.text
        ):
            return None, None, "word_timing_coverage_incomplete"
        if any(right.start_ms < left.end_ms for left, right in pairwise(words)):
            return None, None, "word_timing_overlap"
        start, end = words[0].start_ms, words[-1].end_ms
        if end <= start:
            return None, None, "word_duration_unavailable"
        return start, end, None
