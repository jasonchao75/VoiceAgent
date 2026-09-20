"""Read and audit per-conversation evaluation source packages."""

from __future__ import annotations

import re
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any
from xml.etree import ElementTree

import soundfile as sf  # type: ignore[import-untyped]

_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_ARABIC_RE = re.compile(r"[\u0600-\u06ff]")
_LATIN_RE = re.compile(r"[A-Za-z]")
_WARNING_ISSUE_TYPES = frozenset(
    {
        "audio_timeline_mismatch",
        "decreasing_event_time",
        "event_outside_audio",
    }
)


def _issue_severity(issue: dict[str, Any]) -> str:
    """Classify source findings without treating historical timing drift as fatal."""
    explicit = issue.get("severity")
    if explicit in {"blocking", "warning"}:
        return str(explicit)
    return "warning" if issue.get("issue_type") in _WARNING_ISSUE_TYPES else "blocking"


def _serialize_issue(issue: dict[str, Any]) -> dict[str, Any]:
    """Return an issue with an explicit severity for API and report consumers."""
    return {**issue, "severity": _issue_severity(issue)}


@dataclass(frozen=True)
class DialogueEvent:
    """One source-backed row from a Dialogue Details worksheet."""

    event_id: str
    source_row: int
    time_s: float
    speaker: str
    text: str


@dataclass(frozen=True)
class AudioMetadata:
    """Audio properties read from the file contents."""

    path: str
    size_bytes: int
    duration_s: float
    sample_rate: int
    channels: int
    format: str
    subtype: str


@dataclass
class ConversationAudit:
    """Audited source state for one conversation ID."""

    conversation_id: str
    history_path: str | None = None
    record_path: str | None = None
    user_record_path: str | None = None
    events: list[DialogueEvent] = field(default_factory=list)
    record_audio: AudioMetadata | None = None
    user_audio: AudioMetadata | None = None
    detected_language: str = "unknown"
    issues: list[dict[str, Any]] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        """Return whether this conversation has no blocking source issue."""
        return not self.blocking_issues

    @property
    def blocking_issues(self) -> list[dict[str, Any]]:
        """Return findings that prevent this conversation from running safely."""
        return [issue for issue in self.issues if _issue_severity(issue) == "blocking"]

    @property
    def warnings(self) -> list[dict[str, Any]]:
        """Return reference-only findings that do not block evaluation."""
        return [issue for issue in self.issues if _issue_severity(issue) == "warning"]

    @property
    def user_event_count(self) -> int:
        """Count customer-authored source events."""
        return sum(event.speaker == "customer" for event in self.events)

    @property
    def robot_event_count(self) -> int:
        """Count robot-authored source events."""
        return sum(event.speaker == "robot" for event in self.events)

    def to_dict(self, *, include_events: bool = False) -> dict[str, Any]:
        """Serialize this audit record for persistence or an API response."""
        result = {
            "conversation_id": self.conversation_id,
            "history_path": self.history_path,
            "record_path": self.record_path,
            "user_record_path": self.user_record_path,
            "event_count": len(self.events),
            "user_event_count": self.user_event_count,
            "robot_event_count": self.robot_event_count,
            "detected_language": self.detected_language,
            "record_audio": asdict(self.record_audio) if self.record_audio else None,
            "user_audio": asdict(self.user_audio) if self.user_audio else None,
            "issues": [_serialize_issue(issue) for issue in self.issues],
            "blocking_issues": [_serialize_issue(issue) for issue in self.blocking_issues],
            "warnings": [_serialize_issue(issue) for issue in self.warnings],
            "blocking_issue_count": len(self.blocking_issues),
            "warning_count": len(self.warnings),
            "valid": self.valid,
        }
        if include_events:
            result["events"] = [asdict(event) for event in self.events]
        return result


@dataclass(frozen=True)
class DatasetAudit:
    """Aggregate audit result for one evaluation package root."""

    source: str
    expected_conversations: int
    conversations: tuple[ConversationAudit, ...]
    package_issues: tuple[dict[str, Any], ...]

    @property
    def valid(self) -> bool:
        """Return whether the package satisfies all import requirements."""
        return not any(
            _issue_severity(issue) == "blocking" for issue in self.package_issues
        ) and all(item.valid for item in self.conversations)

    @property
    def counts(self) -> dict[str, int]:
        """Return the number of discovered files for each required folder."""
        return {
            "conversation_history": sum(
                item.history_path is not None for item in self.conversations
            ),
            "record": sum(item.record_path is not None for item in self.conversations),
            "user_record": sum(item.user_record_path is not None for item in self.conversations),
        }

    def to_dict(self, *, include_conversations: bool = False) -> dict[str, Any]:
        """Serialize summary data, optionally including all conversation rows."""
        issues = [_serialize_issue(issue) for issue in self.package_issues]
        for conversation in self.conversations:
            issues.extend(_serialize_issue(issue) for issue in conversation.issues)
        blocking_issues = [issue for issue in issues if issue["severity"] == "blocking"]
        warnings = [issue for issue in issues if issue["severity"] == "warning"]
        languages: dict[str, int] = {}
        for conversation in self.conversations:
            languages[conversation.detected_language] = (
                languages.get(conversation.detected_language, 0) + 1
            )
        result: dict[str, Any] = {
            "source": self.source,
            "counts": self.counts,
            "matched_conversations": sum(
                item.history_path is not None
                and item.record_path is not None
                and item.user_record_path is not None
                for item in self.conversations
            ),
            "conversation_count": len(self.conversations),
            "valid_conversations": sum(item.valid for item in self.conversations),
            "event_count": sum(len(item.events) for item in self.conversations),
            "user_event_count": sum(item.user_event_count for item in self.conversations),
            "robot_event_count": sum(item.robot_event_count for item in self.conversations),
            "language_counts": languages,
            "valid": self.valid,
            "issues": issues,
            "blocking_issues": blocking_issues,
            "warnings": warnings,
            "blocking_issue_count": len(blocking_issues),
            "warning_count": len(warnings),
            "mode": "real_source_data",
            "provider_results": "not_run",
        }
        if include_conversations:
            result["conversations"] = [item.to_dict() for item in self.conversations]
        return result


class WorkbookError(ValueError):
    """Raised when a source workbook violates the package contract."""


def _column_index(reference: str) -> int:
    letters = "".join(character for character in reference if character.isalpha())
    result = 0
    for character in letters.upper():
        result = result * 26 + ord(character) - ord("A") + 1
    return result - 1


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return [
        "".join(node.text or "" for node in item.findall(f".//{{{_MAIN_NS}}}t"))
        for item in root.findall(f"{{{_MAIN_NS}}}si")
    ]


def _worksheet_path(archive: zipfile.ZipFile, sheet_name: str) -> str:
    workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    relationship_id = None
    for sheet in workbook.findall(f".//{{{_MAIN_NS}}}sheet"):
        if sheet.attrib.get("name") == sheet_name:
            relationship_id = sheet.attrib.get(f"{{{_REL_NS}}}id")
            break
    if not relationship_id:
        raise WorkbookError(f"Missing required worksheet: {sheet_name}")
    relationships = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    target = None
    for relationship in relationships.findall(f"{{{_PACKAGE_REL_NS}}}Relationship"):
        if relationship.attrib.get("Id") == relationship_id:
            target = relationship.attrib.get("Target")
            break
    if not target:
        raise WorkbookError(f"Worksheet relationship is missing: {sheet_name}")
    normalized = PurePosixPath(target.lstrip("/"))
    if not str(normalized).startswith("xl/"):
        normalized = PurePosixPath("xl") / normalized
    return str(normalized)


def _cell_text(cell: ElementTree.Element, shared: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(f".//{{{_MAIN_NS}}}t"))
    value = cell.find(f"{{{_MAIN_NS}}}v")
    raw = value.text if value is not None and value.text is not None else ""
    if cell_type == "s" and raw:
        try:
            return shared[int(raw)]
        except (IndexError, ValueError) as exc:
            raise WorkbookError("Workbook contains an invalid shared-string reference") from exc
    return raw


def read_dialogue_workbook(path: Path) -> list[DialogueEvent]:
    """Read validated dialogue events from one source XLSX file."""
    try:
        with zipfile.ZipFile(path) as archive:
            shared = _shared_strings(archive)
            worksheet = ElementTree.fromstring(
                archive.read(_worksheet_path(archive, "Dialogue Details"))
            )
    except (OSError, zipfile.BadZipFile, ElementTree.ParseError, KeyError) as exc:
        raise WorkbookError(f"Workbook cannot be decoded: {type(exc).__name__}") from exc

    rows: list[tuple[int, list[str]]] = []
    for row in worksheet.findall(f".//{{{_MAIN_NS}}}row"):
        row_number = int(row.attrib.get("r", len(rows) + 1))
        values = ["", "", ""]
        for cell in row.findall(f"{{{_MAIN_NS}}}c"):
            index = _column_index(cell.attrib.get("r", "A1"))
            if index < len(values):
                values[index] = _cell_text(cell, shared).strip()
        rows.append((row_number, values))
    if not rows:
        raise WorkbookError("Dialogue Details is empty")
    headers = [value.strip() for value in rows[0][1]]
    if headers != ["time (s)", "robot", "customer"]:
        raise WorkbookError(
            "Dialogue Details must contain time (s), robot, customer in columns A:C"
        )

    events: list[DialogueEvent] = []
    for row_number, values in rows[1:]:
        raw_time, robot, customer = values
        if not raw_time and not robot and not customer:
            continue
        try:
            time_s = float(raw_time)
        except ValueError as exc:
            raise WorkbookError(f"Row {row_number} has a non-numeric time") from exc
        if time_s < 0:
            raise WorkbookError(f"Row {row_number} has a negative time")
        if bool(robot) == bool(customer):
            raise WorkbookError(f"Row {row_number} must contain exactly one speaker text")
        events.append(
            DialogueEvent(
                event_id=f"R{row_number}",
                source_row=row_number,
                time_s=time_s,
                speaker="robot" if robot else "customer",
                text=robot or customer,
            )
        )
    if not events:
        raise WorkbookError("Dialogue Details has no dialogue events")
    return events


def _audio_metadata(path: Path, relative_path: str) -> AudioMetadata:
    info = sf.info(path)
    return AudioMetadata(
        path=relative_path,
        size_bytes=path.stat().st_size,
        duration_s=round(float(info.duration), 6),
        sample_rate=int(info.samplerate),
        channels=int(info.channels),
        format=str(info.format),
        subtype=str(info.subtype),
    )


def _detect_language(events: list[DialogueEvent]) -> str:
    text = " ".join(event.text for event in events if event.speaker == "customer")
    arabic = len(_ARABIC_RE.findall(text))
    latin = len(_LATIN_RE.findall(text))
    if arabic and latin:
        minor = min(arabic, latin)
        major = max(arabic, latin)
        return "mixed" if minor / major >= 0.05 else ("ar" if arabic > latin else "en")
    if arabic:
        return "ar"
    if latin:
        return "en"
    return "unknown"


def audit_dataset(
    dataset_root: Path,
    *,
    expected_conversations: int | None = 56,
    timeline_tolerance_s: float = 0.25,
) -> DatasetAudit:
    """Audit every workbook and audio pair in one source package."""
    specs = {
        "conversation_history": ".xlsx",
        "record": ".mp3",
        "user_record": ".wav",
    }
    file_sets = {
        folder: {path.stem: path for path in (dataset_root / folder).glob(f"*{suffix}")}
        for folder, suffix in specs.items()
    }
    all_ids: set[str] = set()
    for paths in file_sets.values():
        all_ids.update(paths)
    package_issues: list[dict[str, Any]] = []
    if not all_ids:
        package_issues.append(
            {
                "issue_type": "empty_package",
                "conversation_id": None,
                "message": "No conversation files were found in the three required folders",
            }
        )
    if expected_conversations is not None and len(all_ids) != expected_conversations:
        package_issues.append(
            {
                "issue_type": "unexpected_conversation_count",
                "conversation_id": None,
                "message": f"Expected {expected_conversations} IDs, found {len(all_ids)}",
            }
        )

    conversations: list[ConversationAudit] = []
    for conversation_id in sorted(all_ids):
        history = file_sets["conversation_history"].get(conversation_id)
        record = file_sets["record"].get(conversation_id)
        user_record = file_sets["user_record"].get(conversation_id)
        audit = ConversationAudit(
            conversation_id=conversation_id,
            history_path=(f"conversation_history/{history.name}" if history else None),
            record_path=(f"record/{record.name}" if record else None),
            user_record_path=(f"user_record/{user_record.name}" if user_record else None),
        )
        for folder, path in (
            ("conversation_history", history),
            ("record", record),
            ("user_record", user_record),
        ):
            if path is None:
                audit.issues.append(
                    {
                        "issue_type": "missing_file",
                        "conversation_id": conversation_id,
                        "expected_path": f"{folder}/{conversation_id}{specs[folder]}",
                    }
                )
        if history:
            try:
                audit.events = read_dialogue_workbook(history)
                audit.detected_language = _detect_language(audit.events)
                previous_event: DialogueEvent | None = None
                for event in audit.events:
                    if previous_event and event.time_s < previous_event.time_s:
                        audit.issues.append(
                            {
                                "issue_type": "decreasing_event_time",
                                "conversation_id": conversation_id,
                                "source_file": audit.history_path,
                                "source_row": event.source_row,
                                "severity": "warning",
                                "message": (
                                    f"R{event.source_row} starts at {event.time_s:.3f}s before "
                                    f"R{previous_event.source_row} at {previous_event.time_s:.3f}s"
                                ),
                            }
                        )
                    previous_event = event
            except WorkbookError as exc:
                audit.issues.append(
                    {
                        "issue_type": "invalid_workbook",
                        "conversation_id": conversation_id,
                        "source_file": audit.history_path,
                        "message": str(exc),
                    }
                )
        for field_name, path, relative in (
            ("record_audio", record, audit.record_path),
            ("user_audio", user_record, audit.user_record_path),
        ):
            if path and relative:
                try:
                    setattr(audit, field_name, _audio_metadata(path, relative))
                except (OSError, RuntimeError) as exc:
                    audit.issues.append(
                        {
                            "issue_type": "invalid_audio",
                            "conversation_id": conversation_id,
                            "source_file": relative,
                            "message": type(exc).__name__,
                        }
                    )
        if audit.record_audio and audit.user_audio:
            difference = abs(audit.record_audio.duration_s - audit.user_audio.duration_s)
            if difference > timeline_tolerance_s:
                audit.issues.append(
                    {
                        "issue_type": "audio_timeline_mismatch",
                        "conversation_id": conversation_id,
                        "message": f"MP3/WAV duration difference is {difference:.3f}s",
                    }
                )
        if audit.events and audit.record_audio:
            for event in audit.events:
                if event.time_s <= audit.record_audio.duration_s + timeline_tolerance_s:
                    continue
                audit.issues.append(
                    {
                        "issue_type": "event_outside_audio",
                        "conversation_id": conversation_id,
                        "source_file": audit.history_path,
                        "source_row": event.source_row,
                        "message": (
                            f"R{event.source_row} starts at {event.time_s:.3f}s but audio "
                            f"duration is {audit.record_audio.duration_s:.3f}s"
                        ),
                    }
                )
        conversations.append(audit)
    return DatasetAudit(
        source=str(dataset_root),
        expected_conversations=expected_conversations or len(all_ids),
        conversations=tuple(conversations),
        package_issues=tuple(package_issues),
    )
