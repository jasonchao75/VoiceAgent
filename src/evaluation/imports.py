"""Safely stage evaluation dataset uploads."""

from __future__ import annotations

import shutil
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

_FOLDER_BY_SUFFIX = {
    ".xlsx": "conversation_history",
    ".mp3": "record",
    ".wav": "user_record",
}
_ALLOWED_FOLDERS = frozenset(_FOLDER_BY_SUFFIX.values())


class PackageUploadError(ValueError):
    """Raised when an uploaded package cannot be staged safely."""


@dataclass(frozen=True)
class ArchiveLimits:
    """Bound archive extraction resource use."""

    max_files: int = 5000
    max_expanded_bytes: int = 2 * 1024 * 1024 * 1024
    max_single_file_bytes: int = 512 * 1024 * 1024
    max_compression_ratio: float = 200.0


def _is_ignored_path(parts: tuple[str, ...]) -> bool:
    """Ignore macOS metadata without accepting arbitrary extra package files."""
    return bool(parts) and (parts[0] == "__MACOSX" or parts[-1] == ".DS_Store")


def _member_parts(name: str) -> tuple[str, ...]:
    """Return normalized member components or reject unsafe paths."""
    if not name or "\x00" in name or "\\" in name:
        raise PackageUploadError("Archive contains an invalid path")
    path = PurePosixPath(name)
    parts = path.parts
    if path.is_absolute() or not parts or any(part in {"", ".", ".."} for part in parts):
        raise PackageUploadError(f"Archive contains an unsafe path: {name}")
    if ":" in parts[0]:
        raise PackageUploadError(f"Archive contains an unsafe path: {name}")
    return parts


def _logical_paths(
    archive: zipfile.ZipFile,
    limits: ArchiveLimits,
) -> list[tuple[zipfile.ZipInfo, tuple[str, str]]]:
    """Validate members and map an optional wrapper folder to package paths."""
    files: list[tuple[zipfile.ZipInfo, tuple[str, ...]]] = []
    for info in archive.infolist():
        parts = _member_parts(info.filename)
        mode = (info.external_attr >> 16) & 0o170000
        if mode and stat.S_ISLNK(mode):
            raise PackageUploadError(f"Archive symlinks are not allowed: {info.filename}")
        if info.is_dir() or _is_ignored_path(parts):
            continue
        files.append((info, parts))
    if not files:
        raise PackageUploadError("Archive contains no dataset files")
    if len(files) > limits.max_files:
        raise PackageUploadError(f"Archive contains more than {limits.max_files} files")

    if all(parts[0] in _ALLOWED_FOLDERS for _, parts in files):
        wrapper: str | None = None
    elif all(len(parts) >= 2 and parts[1] in _ALLOWED_FOLDERS for _, parts in files):
        wrappers = {parts[0] for _, parts in files}
        if len(wrappers) != 1:
            raise PackageUploadError("Archive uses multiple wrapper folders")
        wrapper = next(iter(wrappers))
    else:
        raise PackageUploadError(
            "Archive files must be inside conversation_history/, record/, or user_record/"
        )

    expanded_bytes = 0
    normalized: list[tuple[zipfile.ZipInfo, tuple[str, str]]] = []
    seen: set[str] = set()
    for info, raw_parts in files:
        parts = raw_parts[1:] if wrapper else raw_parts
        if len(parts) != 2 or parts[0] not in _ALLOWED_FOLDERS:
            raise PackageUploadError(f"Unexpected package path: {info.filename}")
        folder, filename = parts
        suffix = Path(filename).suffix.lower()
        if _FOLDER_BY_SUFFIX.get(suffix) != folder:
            raise PackageUploadError(f"File type does not match its folder: {info.filename}")
        stem = Path(filename).stem
        if (
            not stem
            or len(stem) > 128
            or any(not (character.isalnum() or character in {"-", "_"}) for character in stem)
        ):
            raise PackageUploadError(f"Invalid conversation ID in path: {info.filename}")
        key = f"{folder}/{filename}".casefold()
        if key in seen:
            raise PackageUploadError(f"Archive contains a duplicate path: {folder}/{filename}")
        seen.add(key)
        if info.file_size > limits.max_single_file_bytes:
            raise PackageUploadError(f"Archive member is too large: {info.filename}")
        expanded_bytes += info.file_size
        if expanded_bytes > limits.max_expanded_bytes:
            raise PackageUploadError("Archive expanded size exceeds the allowed limit")
        if info.file_size > 1024 * 1024:
            ratio = info.file_size / max(1, info.compress_size)
            if ratio > limits.max_compression_ratio:
                raise PackageUploadError(f"Archive compression ratio is unsafe: {info.filename}")
        normalized.append((info, (folder, filename)))
    return normalized


def extract_package_archive(
    archive_path: Path,
    target_root: Path,
    *,
    limits: ArchiveLimits | None = None,
) -> int:
    """Extract one dataset ZIP without trusting archive-owned paths."""
    active_limits = limits or ArchiveLimits()
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = _logical_paths(archive, active_limits)
            extracted_bytes = 0
            for info, (folder, filename) in members:
                destination = target_root / folder / filename
                destination.parent.mkdir(parents=True, exist_ok=True)
                written = 0
                with archive.open(info) as source, destination.open("xb") as output:
                    while chunk := source.read(1024 * 1024):
                        written += len(chunk)
                        extracted_bytes += len(chunk)
                        if written > active_limits.max_single_file_bytes:
                            raise PackageUploadError(
                                f"Archive member is too large: {info.filename}"
                            )
                        if extracted_bytes > active_limits.max_expanded_bytes:
                            raise PackageUploadError(
                                "Archive expanded size exceeds the allowed limit"
                            )
                        output.write(chunk)
    except zipfile.BadZipFile as exc:
        raise PackageUploadError("The uploaded file is not a readable ZIP archive") from exc
    return len(members)


def install_single_repair(source_path: Path, filename: str, target_root: Path) -> str:
    """Install one corrected workbook or audio file using its conversation ID."""
    safe_name = Path(filename).name
    if safe_name != filename:
        raise PackageUploadError("A repair filename must not contain a path")
    suffix = Path(safe_name).suffix.lower()
    folder = _FOLDER_BY_SUFFIX.get(suffix)
    if folder is None:
        raise PackageUploadError("Repair files must be XLSX, MP3, WAV, or a ZIP")
    stem = Path(safe_name).stem
    if (
        not stem
        or len(stem) > 128
        or any(not (character.isalnum() or character in {"-", "_"}) for character in stem)
    ):
        raise PackageUploadError("The repair filename must be a full conversation ID")
    destination = target_root / folder / safe_name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, destination)
    return f"{folder}/{safe_name}"
