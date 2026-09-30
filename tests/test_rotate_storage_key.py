"""Tests for the storage-key rotation utility."""

from __future__ import annotations

import base64
import importlib.util
from pathlib import Path

import pytest

SCRIPT_PATH = (
    Path(__file__).parents[1] / "scripts/deploy/rotate_storage_key.py"
)
SPEC = importlib.util.spec_from_file_location("rotate_storage_key", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_rotate_storage_key_replaces_only_target(tmp_path: Path) -> None:
    """Rotation should preserve unrelated values and emit a valid new key."""
    env_path = tmp_path / ".env"
    env_path.write_text(
        "OTHER=value\nVOICE_AGENT_STORAGE_KEY=old-value\nLAST=setting\n",
        encoding="utf-8",
    )

    result = MODULE.rotate_storage_key(env_path)

    lines = env_path.read_text(encoding="utf-8").splitlines()
    key = lines[1].split("=", 1)[1]
    assert result == {"rotated": True, "replaced_existing": True}
    assert lines[0] == "OTHER=value"
    assert lines[2] == "LAST=setting"
    assert key != "old-value"
    assert len(base64.urlsafe_b64decode(key.encode("ascii"))) == 32


def test_rotate_storage_key_rejects_duplicate_entries(tmp_path: Path) -> None:
    """Ambiguous dotenv files should fail closed without modification."""
    env_path = tmp_path / ".env"
    original = "VOICE_AGENT_STORAGE_KEY=one\nVOICE_AGENT_STORAGE_KEY=two\n"
    env_path.write_text(original, encoding="utf-8")

    with pytest.raises(RuntimeError, match="duplicate"):
        MODULE.rotate_storage_key(env_path)

    assert env_path.read_text(encoding="utf-8") == original
