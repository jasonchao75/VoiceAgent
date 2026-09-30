#!/usr/bin/env python3
"""Rotate VOICE_AGENT_STORAGE_KEY in an environment file without revealing it."""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import re
import secrets
import tempfile
from pathlib import Path

LOGGER = logging.getLogger(__name__)
STORAGE_KEY_PATTERN = re.compile(r"^\s*VOICE_AGENT_STORAGE_KEY\s*=.*$")


def _generate_storage_key() -> str:
    """Generate a Fernet-compatible key without importing application packages.

    Returns:
        A URL-safe base64 encoding of 32 random bytes.
    """
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")


def rotate_storage_key(env_path: Path) -> dict[str, bool]:
    """Atomically replace the storage key while preserving other settings.

    Args:
        env_path: Existing dotenv file to update.

    Returns:
        Non-sensitive rotation facts suitable for logs.

    Raises:
        FileNotFoundError: If the environment file does not exist.
        RuntimeError: If duplicate storage-key entries are present.
    """
    original = env_path.read_text(encoding="utf-8")
    lines = original.splitlines()
    matches = [index for index, line in enumerate(lines) if STORAGE_KEY_PATTERN.match(line)]
    if len(matches) > 1:
        raise RuntimeError("environment file contains duplicate storage-key entries")

    replacement = f"VOICE_AGENT_STORAGE_KEY={_generate_storage_key()}"
    if matches:
        lines[matches[0]] = replacement
    else:
        lines.append(replacement)

    updated = "\n".join(lines) + ("\n" if original.endswith("\n") or lines else "")
    file_mode = env_path.stat().st_mode & 0o777
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            dir=env_path.parent,
            encoding="utf-8",
            prefix=f".{env_path.name}.",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            os.chmod(temporary_path, file_mode)
            temporary_file.write(updated)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, env_path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()

    return {"rotated": True, "replaced_existing": bool(matches)}


def main() -> None:
    """Rotate the requested dotenv file and log only non-sensitive facts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("env_path", type=Path)
    args = parser.parse_args()
    result = rotate_storage_key(args.env_path)
    LOGGER.info(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
