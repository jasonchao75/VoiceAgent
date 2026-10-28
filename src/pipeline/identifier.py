"""Strict identifier format routing and shared source-bound collection state."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass

from src.asr.transcript import TranscriptView
from src.pipeline.response_revision import canonical_final_text

_SEPARATORS = frozenset(" \t\r\n,，、.-－—")


class IdentifierVocabulary:
    """Explicit aliases mapped to collection/echo units, never an intent classifier."""

    def __init__(self, rows: dict[str, list[str]]) -> None:
        """Validate aliases once so local and tool paths use the same normalization.

        Raises:
            ValueError: If targets or aliases are empty or aliases collide.
        """
        self._aliases: dict[str, str] = {}
        for target, aliases in rows.items():
            if not target.strip() or not aliases:
                raise ValueError("Vocabulary targets and aliases must be nonempty")
            for alias in aliases:
                key = unicodedata.normalize("NFKC", alias).strip().casefold()
                if not key or key in self._aliases:
                    raise ValueError("Vocabulary aliases must be unique and nonempty")
                self._aliases[key] = target
        if not self._aliases:
            raise ValueError("Vocabulary must not be empty")
        self._ordered = sorted(self._aliases, key=len, reverse=True)

    def normalize(self, text: str) -> str | None:
        """Accept only complete alias/separator input; do not extract mixed sentences."""
        units = self._units(text)
        return "".join(units) if units else None

    def audio_units(self, text: str) -> tuple[str, ...] | None:
        """Preserve configured word units while expanding numeric targets for digit audio."""
        units = self._units(text)
        if units is None:
            return None
        return tuple(
            unit for value in units for unit in (tuple(value) if value.isdigit() else (value,))
        )

    def _units(self, text: str) -> tuple[str, ...] | None:
        """Tokenize complete input once for both collection and resource lookup."""
        text = unicodedata.normalize("NFKC", text).casefold().strip()
        offset, units = 0, []
        while offset < len(text):
            if text[offset] in _SEPARATORS:
                offset += 1
                continue
            match = self._match(text, offset)
            if match is None:
                return None
            alias, target = match
            units.append(target)
            offset += len(alias)
        return tuple(units) if units else None

    def contains(self, text: str, identifier: str) -> bool:
        """Verify a tool's claimed contiguous identifier occurs in the actual source.

        This proves provenance only; conversation LLM remains responsible for intent.
        """
        text = unicodedata.normalize("NFKC", text).casefold()
        for start in range(len(text)):
            if start and text[start - 1].isascii() and text[start - 1].isalpha():
                continue
            units, offset = "", start
            while offset < len(text):
                match = self._match(text, offset)
                if match is None:
                    break
                alias, target = match
                units += target
                offset += len(alias)
                if units == identifier:
                    return True
                if not identifier.startswith(units):
                    break
                while offset < len(text) and text[offset] in _SEPARATORS:
                    offset += 1
        return False

    def _match(self, text: str, offset: int) -> tuple[str, str] | None:
        """Match an alias with English word boundaries, preserving adjacent digits/CJK."""
        for alias in self._ordered:
            if not text.startswith(alias, offset):
                continue
            end = offset + len(alias)
            if re.fullmatch("[a-z]+", alias):
                if end < len(text) and text[end].isascii() and text[end].isalpha():
                    continue
            return alias, self._aliases[alias]
        return None


@dataclass(frozen=True, slots=True)
class IdentifierSource:
    """Tool provenance with source revision and collection generation fences."""

    epoch: int
    source_id: str
    revision: int
    generation: int
    text: str
    evidence_ids: tuple[tuple[int, str], ...] = ()


class IdentifierCollection:
    """One source-indexed value shared by local collection and conversation tools."""

    def __init__(self, vocabulary: IdentifierVocabulary, *, target_length: int | None) -> None:
        """Initialize a collection without implying Partial target length is success."""
        if target_length is not None and target_length < 1:
            raise ValueError("Target length must be positive")
        self.vocabulary = vocabulary
        self.target_length = target_length
        self.generation = 0
        self.on_generation_change: Callable[[int], None] | None = None
        self._sources: dict[tuple[int, str], IdentifierSource] = {}
        self._values: dict[tuple[int, str], str] = {}
        self._successful = False
        self._ranges: dict[tuple[int, str], tuple[tuple[int, float, float], ...]] = {}
        self._fingerprints: dict[tuple[int, str], str] = {}
        self._bind_orders: dict[tuple[int, str], int] = {}
        self._bind_sequence = 0
        self._local_values: set[tuple[int, str]] = set()
        self._source_finals: dict[tuple[int, str], bool] = {}
        self._applied_texts: dict[tuple[int, str], str] = {}

    @property
    def value(self) -> str:
        """Return source-ordered collected value without string-based deduplication."""
        return "".join(self._values.values())

    @property
    def all_final(self) -> bool:
        """Require every stored contribution to be backed by its current finalized input."""
        return bool(self._values) and all(
            self._source_finals.get(key, False)
            and self._sources[key].text == self._applied_texts.get(key)
            and self._valid(self._sources[key])
            for key in self._values
        )

    @property
    def successful(self) -> bool:
        """Do not let changed or still-partial provenance authorize another collection."""
        return self._successful and self.all_final

    def bind_source(
        self,
        epoch: int,
        source_id: str,
        revision: int,
        text: str,
        *,
        evidence_ids: tuple[tuple[int, str], ...] = (),
    ) -> IdentifierSource:
        """Bind an actual current input before allowing local or LLM operations.

        Raises:
            ValueError: If an incoming revision is stale or lacks identity.
        """
        if epoch < 0 or not source_id or revision < 1:
            raise ValueError("Invalid identifier source identity")
        key = (epoch, source_id)
        previous = self._sources.get(key)
        source = IdentifierSource(epoch, source_id, revision, self.generation, text, evidence_ids)
        if previous and revision < previous.revision:
            raise ValueError("Stale identifier source revision")
        if previous and revision == previous.revision and previous != source:
            raise ValueError("Conflicting identifier source revision")
        if previous == source:
            return previous
        self._sources[key] = source
        self._source_finals[key] = False
        self._bind_sequence += 1
        self._bind_orders[key] = self._bind_sequence
        # A revised mixed sentence no longer qualifies for speculative local collection.
        if (
            previous
            and previous.text != source.text
            and key in self._local_values
            and self.vocabulary.normalize(text) is None
        ):
            self._values.pop(key, None)
            self._local_values.discard(key)
        return source

    def bind_snapshot(self, snapshot: TranscriptView) -> IdentifierSource:
        """Bind exact TD audio extents, preserving both adjacent tails and grouped input.

        Raises:
            ValueError: If the snapshot has no proven source extents.
        """
        if not snapshot.segments or snapshot.missing_reason:
            raise ValueError("Identifier input requires proven source ranges")
        origins = [(s.epoch, s.source_id, s.start_ms) for s in snapshot.segments]
        source_id = "range:" + hashlib.sha256(json.dumps(origins).encode()).hexdigest()
        epoch = snapshot.segments[0].epoch
        key = (epoch, source_id)
        fingerprint = json.dumps(
            [
                snapshot.text,
                [
                    (s.epoch, s.source_id, s.revision, s.start_ms, s.end_ms, s.final)
                    for s in snapshot.segments
                ],
            ]
        )
        previous = self._sources.get(key)
        if previous and self._fingerprints.get(key) == fingerprint:
            return previous
        source = self.bind_source(
            epoch,
            source_id,
            previous.revision + 1 if previous else 1,
            snapshot.text,
            evidence_ids=tuple((s.epoch, s.source_id) for s in snapshot.segments),
        )
        self._ranges[key] = tuple((s.epoch, s.start_ms, s.end_ms) for s in snapshot.segments)
        self._fingerprints[key] = fingerprint
        self._source_finals[key] = snapshot.final
        if self.vocabulary.normalize(snapshot.text) is None:
            for local in list(self._local_values):
                if self._overlap(key, local):
                    self._values.pop(local, None)
                    self._local_values.discard(local)
        return source

    def _overlap(self, first: tuple[int, str], second: tuple[int, str]) -> bool:
        """Use audio evidence rather than equal text to identify overlapping contributions."""
        if first == second:
            return True
        return any(
            a[0] == b[0] and max(a[1], b[1]) < min(a[2], b[2])
            for a in self._ranges.get(first, ())
            for b in self._ranges.get(second, ())
        )

    def begin_collection(self) -> None:
        """Clear only when a genuinely new collection follows confirmed success."""
        if self._successful:
            self._clear()

    def mark_success(self, *, final: bool) -> bool:
        """Mark complete only with finalized source evidence at the target length."""
        self._successful = (
            final and self.target_length is not None and (len(self.value) == self.target_length)
        )
        return self._successful

    def collect_local(self, source: IdentifierSource) -> dict[str, object]:
        """Collect pure input regardless of speed; echo eligibility is evaluated separately."""
        if not self._valid(source):
            return self._result("stale")
        normalized = self.vocabulary.normalize(source.text)
        if normalized is None:
            return self._result("mixed_input")
        result = self._write(source, normalized)
        self._local_values.add((source.epoch, source.source_id))
        return result

    def validate_submission(self, source: IdentifierSource, identifier: str) -> str | None:
        """Validate every current tool attempt, including retrieval of an earlier result."""
        if not self._valid(source):
            return "stale"
        normalized = self.vocabulary.normalize(identifier)
        if normalized is None or not self.vocabulary.contains(source.text, normalized):
            return "invalid"
        return None

    def locally_collected(self, source: IdentifierSource) -> bool:
        """Prove the pure input is already present before omitting redundant LLM tools."""
        key = (source.epoch, source.source_id)
        return (
            self._valid(source)
            and key in self._local_values
            and self._values.get(key) == self.vocabulary.normalize(source.text)
        )

    def confirm_submission(self, source: IdentifierSource, identifier: str) -> None:
        """Refresh proof after a validated replay without applying the number a second time."""
        key = (source.epoch, source.source_id)
        if self.validate_submission(source, identifier) is None and (
            self._values.get(key) == self.vocabulary.normalize(identifier)
        ):
            self._applied_texts[key] = source.text
            self.mark_success(final=self.all_final)

    def confirm_equivalent_final(self, source: IdentifierSource) -> None:
        """Finalize already-applied evidence without replaying a tool or writing a new value."""
        key = (source.epoch, source.source_id)
        applied = self._applied_texts.get(key)
        if (
            applied is not None
            and key in self._values
            and self._valid(source)
            and self._source_finals.get(key, False)
            and canonical_final_text(applied) == canonical_final_text(source.text)
        ):
            self._applied_texts[key] = source.text
            self.mark_success(final=self.all_final)

    def submit_tool(self, source: IdentifierSource, identifier: str) -> dict[str, object]:
        """Validate current provenance before applying an LLM-submitted identifier."""
        rejection = self.validate_submission(source, identifier)
        if rejection is not None:
            return self._result(rejection)
        normalized = self.vocabulary.normalize(identifier)
        assert normalized is not None
        key = (source.epoch, source.source_id)
        self._local_values = {
            local for local in self._local_values if not self._overlap(key, local)
        }
        return self._write(source, normalized)

    def clear_tool(self, source: IdentifierSource) -> dict[str, object]:
        """Clear atomically and advance generation so old tools cannot clear new data."""
        if not self._valid(source):
            return self._result("stale")
        self._clear()
        return self._result("cleared")

    def _valid(self, source: IdentifierSource) -> bool:
        """Require exact effective input identity, not merely matching text."""
        key = (source.epoch, source.source_id)
        return (
            source.generation == self.generation
            and self._sources.get(key) == source
            and not any(
                self._bind_orders[other] > self._bind_orders[key] and self._overlap(key, other)
                for other in self._sources
            )
        )

    def _write(self, source: IdentifierSource, value: str) -> dict[str, object]:
        """Replace one source contribution so revisions/local tools cannot double count."""
        key = (source.epoch, source.source_id)
        duplicate = self._values.get(key) == value
        # Replacing a group must keep its position ahead of later independent
        # audio. Adjacent equal numbers remain separate contributions.
        replacement: dict[tuple[int, str], str] = {}
        inserted = False
        for old_key, old_value in self._values.items():
            if self._overlap(key, old_key):
                if not inserted:
                    replacement[key] = value
                    inserted = True
            else:
                replacement[old_key] = old_value
        if not inserted:
            replacement[key] = value
        self._values = replacement
        self._applied_texts[key] = source.text
        return self._result("duplicate" if duplicate else "submitted")

    def _clear(self) -> None:
        """Invalidate all source-bound in-flight work with one generation change."""
        self.generation += 1
        self._sources.clear()
        self._values.clear()
        self._successful = False
        self._ranges.clear()
        self._fingerprints.clear()
        self._bind_orders.clear()
        self._local_values.clear()
        self._source_finals.clear()
        self._applied_texts.clear()
        if self.on_generation_change:
            self.on_generation_change(self.generation)

    def _result(self, status: str) -> dict[str, object]:
        """Return accurate state only after the corresponding transition."""
        return {
            "status": status,
            "value": self.value,
            "count": len(self.value),
            "generation": self.generation,
        }
