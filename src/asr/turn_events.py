"""Normalize provider snapshots without granting provider endpoints turn ownership."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from src.asr.transcript import SourceSegment, TimedWord, words_cover_text


def _timestamp_source_id(value: Any) -> str:
    """Use one identity for numerically identical provider timestamp values.

    Args:
        value: Actual provider timestamp, not text or event arrival time.

    Returns:
        Canonical numeric identity within the current provider connection.

    Raises:
        ValueError: If the timestamp cannot identify an audio position.
    """
    if isinstance(value, bool):
        raise ValueError("Timestamp must be a number")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError("Timestamp must be finite and non-negative")
    return str(0.0 if number == 0 else number)


@dataclass(frozen=True, slots=True)
class _UnknownSourceGap:
    """Evidence absence has its own type and cannot collide with a provider source ID."""

    snapshot_scope: int | None = None


class SourceNormalizer:
    """Assign revisions to proven provider ranges within one connection epoch."""

    def __init__(self, provider: str, model: str, *, sample_rate: int | None = None) -> None:
        """Bind a normalizer to a validated provider/model selection."""
        self.provider = provider
        self.model = model
        self.sample_rate = sample_rate
        self.epoch = 0
        self.missing_reason: str | None = None
        self._previous: dict[str, SourceSegment] = {}
        self.unresolved_sources: set[tuple[int, str | _UnknownSourceGap]] = set()
        self._source_scopes: dict[str, int | None] = {}
        self._snapshot_scope: int | None = None

    def retain_unknown_source(self, *, snapshot_scope: int | None = None) -> None:
        """Keep an unresolved evidence marker, never invent an audio source or time range."""
        self.unresolved_sources.add((self.epoch, _UnknownSourceGap(snapshot_scope)))

    def reconnect(self) -> None:
        """Fence identifiers reused by a new provider WebSocket connection."""
        self.epoch += 1
        self._previous.clear()
        self._source_scopes.clear()
        self.missing_reason = None

    def normalize(self, payload: dict[str, Any]) -> tuple[SourceSegment, ...]:
        """Translate raw source events, preserving missing evidence explicitly.

        Args:
            payload: Raw provider snapshot (Soniox uses the SDK's accumulated tokens).

        Returns:
            Changed source ranges only. A missing range is diagnosed, never guessed.
        """
        self.missing_reason = None
        # SourceSegment is immutable: a shallow checkpoint restores every revision
        # if any row invalidates the returned snapshot before it reaches the ledger.
        previous_snapshot = self._previous.copy()
        previous_scopes = self._source_scopes.copy()
        previous_gaps = self.unresolved_sources.copy()
        scope = (
            payload.get("td_snapshot_scope") if payload.get("td_full_snapshot") is True else None
        )
        self._snapshot_scope = scope if type(scope) is int and scope >= 0 else None
        current_source: str | None = None
        current_text = ""
        try:
            if self.provider == "speechmatics":
                rows = payload.get("segments", [])
                final = payload.get("message") == "AddSegment"
                result = []
                for row in rows:
                    current_source = None
                    current_text = row.get("text", "")
                    speaker = row.get("speaker_id", "")
                    metadata = row.get("metadata") or {}
                    start, end = metadata.get("start_time"), metadata.get("end_time")
                    if start is not None:
                        current_source = f"{speaker}:{_timestamp_source_id(start)}"
                    if self._late_partial(current_source, final):
                        continue
                    words = self._words(row.get("fragments") or [], "start_time", "end_time", 1000)
                    if (start is None or end is None) and words_cover_text(
                        row.get("text", ""), words
                    ):
                        # Use actual complete word evidence, never receipt time or text length.
                        start = words[0].start_ms / 1000 if start is None else start
                        end = words[-1].end_ms / 1000 if end is None else end
                    if start is None or end is None:
                        if start is not None and row.get("text"):
                            gap_source = f"{speaker}:{_timestamp_source_id(start)}"
                            self.unresolved_sources.add((self.epoch, gap_source))
                        elif row.get("text"):
                            self.retain_unknown_source()
                        self.missing_reason = "source_audio_range_unavailable"
                        continue
                    segment = self._segment(
                        f"{speaker}:{_timestamp_source_id(start)}",
                        row.get("text", ""),
                        float(start) * 1000,
                        float(end) * 1000,
                        final,
                        words,
                    )
                    if segment:
                        result.append(segment)
                return tuple(result)
            if self.provider == "deepgram" and self.model.startswith("flux-"):
                if payload.get("event") not in {"Update", "EagerEndOfTurn", "EndOfTurn"}:
                    return ()
                current_text = payload.get("transcript", "")
                if payload.get("turn_index") is not None:
                    current_source = str(payload["turn_index"])
                if self._late_partial(current_source, payload.get("event") == "EndOfTurn"):
                    return ()
                words = self._words(payload.get("words") or [], "start", "end", 1000)
                start = payload.get("audio_window_start")
                end = payload.get("audio_window_end")
                if start is None and words:
                    start = words[0].start_ms / 1000
                if end is None and words:
                    end = words[-1].end_ms / 1000
                source = payload.get("turn_index")
                text = payload.get("transcript", "")
                final = payload.get("event") == "EndOfTurn"
                scale = 1000
            elif self.provider == "deepgram":
                alternative = ((payload.get("channel") or {}).get("alternatives") or [{}])[0]
                current_text = alternative.get("transcript", "")
                if payload.get("start") is not None:
                    current_source = _timestamp_source_id(payload["start"])
                if self._late_partial(current_source, payload.get("is_final") is True):
                    return ()
                words = self._words(alternative.get("words") or [], "start", "end", 1000)
                start = payload.get("start")
                duration = payload.get("duration")
                end = None if start is None or duration is None else start + duration
                source = None if start is None else _timestamp_source_id(start)
                text = alternative.get("transcript", "")
                final = payload.get("is_final") is True
                scale = 1000
            elif self.provider == "assemblyai":
                current_text = payload.get("transcript", "")
                if payload.get("turn_order") is not None:
                    current_source = str(payload["turn_order"])
                if self._late_partial(current_source, payload.get("end_of_turn") is True):
                    return ()
                words = self._words(payload.get("words") or [], "start", "end", 1)
                start = words[0].start_ms if words else None
                end = words[-1].end_ms if words else None
                source = payload.get("turn_order")
                text = payload.get("transcript", "")
                final = payload.get("end_of_turn") is True
                scale = 1
            elif self.provider == "soniox":
                result = []
                current_sources: set[str] = set()
                for token in payload.get("tokens", []):
                    current_source = None
                    current_text = token.get("text", "")
                    if token.get("text") in {"<end>", "<fin>"}:
                        continue
                    if token.get("start_ms") is not None:
                        current_source = _timestamp_source_id(token["start_ms"])
                        current_sources.add(current_source)
                    if self._late_partial(current_source, token.get("is_final") is True):
                        continue
                    if token.get("start_ms") is None or token.get("end_ms") is None:
                        if token.get("start_ms") is not None and token.get("text"):
                            gap_source = _timestamp_source_id(token["start_ms"])
                            self.unresolved_sources.add((self.epoch, gap_source))
                        elif token.get("text"):
                            self.retain_unknown_source(snapshot_scope=self._snapshot_scope)
                        self.missing_reason = "source_audio_range_unavailable"
                        continue
                    word = TimedWord(
                        token.get("text", ""), float(token["start_ms"]), float(token["end_ms"])
                    )
                    segment = self._segment(
                        _timestamp_source_id(word.start_ms),
                        word.text,
                        word.start_ms,
                        word.end_ms,
                        token.get("is_final") is True,
                        (word,),
                        text_is_token=True,
                    )
                    if segment:
                        result.append(segment)
                if (
                    payload.get("td_full_snapshot") is True
                    and current_sources
                    and self.missing_reason is None
                ):
                    # The SDK emits its accumulated stable prefix plus the whole
                    # mutable tail, not the vendor's incremental wire token list.
                    # A vanished Partial is a retracted source, not extra speech.
                    for source, previous in previous_snapshot.items():
                        if previous.final or not previous.text or source in current_sources:
                            continue
                        if previous_scopes.get(source) != self._snapshot_scope:
                            continue
                        removed = self._segment(
                            source, "", previous.start_ms, previous.end_ms, False, ()
                        )
                        if removed:
                            result.append(removed)
                    if self._snapshot_scope is not None:
                        # Only the same SDK turn's complete replacement proves recovery.
                        self.unresolved_sources.discard(
                            (self.epoch, _UnknownSourceGap(self._snapshot_scope))
                        )
                return tuple(result)
            else:
                raise ValueError("Unsupported source provider")
            if not text:
                return ()
            if source is None or start is None or end is None:
                if source is not None:
                    self.unresolved_sources.add((self.epoch, str(source)))
                else:
                    self.retain_unknown_source()
                self.missing_reason = "source_audio_range_unavailable"
                return ()
            segment = self._segment(
                str(source),
                text,
                float(start) * scale,
                float(end) * scale,
                final,
                words,
            )
            return (segment,) if segment else ()
        except (ValueError, TypeError, KeyError, IndexError):
            self._previous = previous_snapshot
            self._source_scopes = previous_scopes
            # A rejected frame cannot prove recovery of an earlier gap either.
            self.unresolved_sources.update(previous_gaps)
            if current_source is not None and current_text:
                self.unresolved_sources.add((self.epoch, current_source))
            elif current_text:
                self.retain_unknown_source(snapshot_scope=self._snapshot_scope)
            self.missing_reason = "invalid_source_audio_evidence"
            return ()

    def _late_partial(self, source: str | None, final: bool) -> bool:
        """Reject downgrades before malformed old timing can create a new gap.

        Args:
            source: Provider-proven identity in the current connection, if available.
            final: Whether this event claims a final snapshot.

        Returns:
            Whether this Partial belongs to an already finalized source.
        """
        previous = self._previous.get(source) if source is not None else None
        return previous is not None and previous.final and not final

    @staticmethod
    def _words(
        rows: list[dict[str, Any]],
        start_key: str,
        end_key: str,
        scale: float,
    ) -> tuple[TimedWord, ...]:
        """Retain complete actual timings; never distribute a segment duration by token."""
        return tuple(
            TimedWord(
                str(row.get("word") or row.get("text") or row.get("content") or ""),
                float(row[start_key]) * scale,
                float(row[end_key]) * scale,
            )
            for row in rows
            if row.get(start_key) is not None and row.get(end_key) is not None
        )

    def _segment(
        self,
        source: str,
        text: str,
        start: float,
        end: float,
        final: bool,
        words: tuple[TimedWord, ...],
        *,
        text_is_token: bool = False,
    ) -> SourceSegment | None:
        """Assign a new revision only when the source snapshot really changed."""
        previous = self._previous.get(source)
        revision = 1 if previous is None else previous.revision + 1
        segment = SourceSegment(
            self.epoch,
            source,
            revision,
            start,
            end,
            text,
            final,
            words,
            sample_rate=self.sample_rate,
            text_is_token=text_is_token,
        )
        self.unresolved_sources.discard((self.epoch, source))
        if previous and (
            previous.start_ms,
            previous.end_ms,
            previous.text,
            previous.final,
            previous.words,
        ) == (start, end, text, final, words):
            return None
        if previous and previous.final and not final:
            return None
        self._previous[source] = segment
        self._source_scopes[source] = self._snapshot_scope
        return segment
