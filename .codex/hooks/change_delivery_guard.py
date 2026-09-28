#!/usr/bin/env python3
"""Keep Codex working turns from ending without delivery disclosure."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REPORT_LABELS = ("本轮完成", "发现的问题", "尚未验证", "需要用户决定")
CODE_DIRECTORY_NAMES = frozenset({"frontend", "scripts", "src", "tests"})
PATCH_PATH_PREFIXES = ("*** Add File: ", "*** Delete File: ", "*** Update File: ")


def read_event() -> dict[str, Any]:
    """Read the Codex hook event from stdin."""
    try:
        value = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return {}
    return value if isinstance(value, dict) else {}


def state_path(event: dict[str, Any]) -> Path:
    """Return an isolated marker for one Codex turn."""
    session_id = str(event.get("session_id", "unknown")).replace("/", "_")
    turn_id = str(event.get("turn_id", "unknown")).replace("/", "_")
    return Path(tempfile.gettempdir()) / "voiceagent-codex-hooks" / session_id / turn_id


def active_change_names(root: Path) -> list[str]:
    """Return active Changes that carry a delivery manifest."""
    changes = root / "openspec" / "changes"
    if not changes.is_dir():
        return []
    return sorted(
        path.name
        for path in changes.iterdir()
        if path.is_dir() and (path / "verification" / "delivery-status.json").is_file()
    )


def verifier_summary(root: Path, names: list[str]) -> str:
    """Run advisory verification and return a concise combined summary."""
    lines: list[str] = []
    verifier = root / "scripts" / "quality" / "verify_change.py"
    for name in names:
        result = subprocess.run(
            [sys.executable, str(verifier), name, "--enforce-final-only"],
            cwd=root,
            capture_output=True,
            check=False,
            text=True,
            timeout=20,
        )
        findings = [
            line
            for line in result.stdout.splitlines()
            if line.startswith(("WARNING:", "ERROR:", "BLOCKED:", "ADVISORY:"))
        ]
        if findings:
            lines.append(f"{name}: " + " | ".join(findings[:8]))
    return "\n".join(lines)[:6000]


def patched_paths(event: dict[str, Any], root: Path) -> list[Path]:
    """Return repository-relative paths changed by an apply_patch event.

    Args:
        event: Codex PostToolUse hook payload.
        root: Repository root used to normalize absolute patch paths.

    Returns:
        Paths declared by Add, Delete, or Update patch headers.
    """
    tool_input = event.get("tool_input")
    if event.get("tool_name") != "apply_patch" or not isinstance(tool_input, dict):
        return []
    command = tool_input.get("command")
    if not isinstance(command, str):
        return []

    paths: list[Path] = []
    for line in command.splitlines():
        for prefix in PATCH_PATH_PREFIXES:
            if not line.startswith(prefix):
                continue
            path = Path(line.removeprefix(prefix).strip())
            if path.is_absolute():
                try:
                    path = path.relative_to(root)
                except ValueError:
                    break
            paths.append(path)
            break
    return paths


def touches_code_directory(event: dict[str, Any], root: Path) -> bool:
    """Return whether a patch changes a file in a guarded code directory.

    Args:
        event: Codex PostToolUse hook payload.
        root: Repository root used to normalize absolute patch paths.

    Returns:
        True when at least one changed path starts in a guarded directory.
    """
    return any(
        path.parts and path.parts[0] in CODE_DIRECTORY_NAMES
        for path in patched_paths(event, root)
    )


def mark(event: dict[str, Any], root: Path) -> int:
    """Remember that this turn changed a guarded code directory.

    Args:
        event: Codex PostToolUse hook payload.
        root: Repository root used to classify patched paths.

    Returns:
        Process exit code.
    """
    if not touches_code_directory(event, root):
        return 0
    marker = state_path(event)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("worked\n", encoding="utf-8")
    return 0


def stop(event: dict[str, Any], root: Path) -> int:
    """Request one continuation when a working turn omits its delivery report."""
    marker = state_path(event)
    if not marker.is_file():
        print(json.dumps({"continue": True}))
        return 0

    marker.unlink(missing_ok=True)
    message = str(event.get("last_assistant_message") or "")
    if all(label in message for label in REPORT_LABELS):
        print(json.dumps({"continue": True}))
        return 0

    if bool(event.get("stop_hook_active")):
        print(json.dumps({"continue": True}))
        return 0

    changes = active_change_names(root)
    findings = verifier_summary(root, changes) if changes else "当前没有带交付清单的活动 Change。"
    reason = (
        "结束前必须主动披露，不能等用户追问。请检查交付记录，并用四个简短标签补充最终回复："
        "本轮完成、发现的问题、尚未验证、需要用户决定。没有内容时明确写‘无’。"
        f"\n自动门禁摘要：\n{findings}"
    )
    print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
    return 0


def main() -> int:
    """Run the selected hook mode."""
    if len(sys.argv) != 2 or sys.argv[1] not in {"mark", "stop"}:
        return 2
    event = read_event()
    root = Path.cwd()
    if sys.argv[1] == "mark":
        return mark(event, root)
    return stop(event, root)


if __name__ == "__main__":
    raise SystemExit(main())
