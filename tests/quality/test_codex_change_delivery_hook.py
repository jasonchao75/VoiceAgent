"""Tests for the project-local Codex delivery hook."""

import importlib.util
import json
from pathlib import Path
from types import ModuleType

HOOK_PATH = Path(__file__).parents[2] / ".codex" / "hooks" / "change_delivery_guard.py"
HOOK_CONFIG_PATH = Path(__file__).parents[2] / ".codex" / "hooks.json"


def load_hook() -> ModuleType:
    """Load the hook script as a testable module."""
    spec = importlib.util.spec_from_file_location("change_delivery_guard", HOOK_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_non_working_turn_can_stop(tmp_path: Path, monkeypatch, capsys) -> None:
    """A conversational turn without local tools should not be interrupted."""
    hook = load_hook()
    monkeypatch.setattr(hook.tempfile, "gettempdir", lambda: str(tmp_path))
    assert hook.stop({"session_id": "s", "turn_id": "t"}, tmp_path) == 0
    assert json.loads(capsys.readouterr().out) == {"continue": True}


def test_working_turn_without_report_requests_continuation(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """A working turn must add the compact disclosure report before stopping."""
    hook = load_hook()
    monkeypatch.setattr(hook.tempfile, "gettempdir", lambda: str(tmp_path))
    event = {"session_id": "s", "turn_id": "t", "last_assistant_message": "完成了"}
    event.update(
        {
            "tool_name": "apply_patch",
            "tool_input": {"command": "*** Update File: src/example.py"},
        }
    )
    hook.mark(event, tmp_path)
    assert hook.stop(event, tmp_path) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["decision"] == "block"
    assert "本轮完成" in output["reason"]


def test_working_turn_with_report_can_stop(tmp_path: Path, monkeypatch, capsys) -> None:
    """A complete four-part report satisfies the Stop hook."""
    hook = load_hook()
    monkeypatch.setattr(hook.tempfile, "gettempdir", lambda: str(tmp_path))
    report = "本轮完成：A\n发现的问题：无\n尚未验证：无\n需要用户决定：无"
    event = {"session_id": "s", "turn_id": "t", "last_assistant_message": report}
    event.update(
        {
            "tool_name": "apply_patch",
            "tool_input": {"command": "*** Update File: frontend/example.ts"},
        }
    )
    hook.mark(event, tmp_path)
    assert hook.stop(event, tmp_path) == 0
    assert json.loads(capsys.readouterr().out) == {"continue": True}


def test_openspec_patch_does_not_mark_turn(tmp_path: Path, monkeypatch, capsys) -> None:
    """An OpenSpec-only patch must not activate the development disclosure."""
    hook = load_hook()
    monkeypatch.setattr(hook.tempfile, "gettempdir", lambda: str(tmp_path))
    event = {
        "session_id": "s",
        "turn_id": "t",
        "last_assistant_message": "Updated the specification.",
        "tool_name": "apply_patch",
        "tool_input": {"command": "*** Update File: openspec/changes/demo/spec.md"},
    }
    hook.mark(event, tmp_path)
    assert hook.stop(event, tmp_path) == 0
    assert json.loads(capsys.readouterr().out) == {"continue": True}


def test_mixed_patch_marks_turn(tmp_path: Path, monkeypatch, capsys) -> None:
    """A patch touching code and OpenSpec must activate the disclosure."""
    hook = load_hook()
    monkeypatch.setattr(hook.tempfile, "gettempdir", lambda: str(tmp_path))
    event = {
        "session_id": "s",
        "turn_id": "t",
        "last_assistant_message": "Updated files.",
        "tool_name": "apply_patch",
        "tool_input": {
            "command": "\n".join(
                (
                    "*** Update File: openspec/changes/demo/spec.md",
                    "*** Update File: tests/test_example.py",
                )
            )
        },
    }
    hook.mark(event, tmp_path)
    assert hook.stop(event, tmp_path) == 0
    assert json.loads(capsys.readouterr().out)["decision"] == "block"


def test_absolute_code_path_is_guarded(tmp_path: Path) -> None:
    """An absolute path below the repository must be classified correctly."""
    hook = load_hook()
    event = {
        "tool_name": "apply_patch",
        "tool_input": {"command": f"*** Add File: {tmp_path}/scripts/check.py"},
    }
    assert hook.touches_code_directory(event, tmp_path)


def test_hook_configuration_observes_only_apply_patch() -> None:
    """Read-only shell commands must not activate the development marker."""
    config = json.loads(HOOK_CONFIG_PATH.read_text(encoding="utf-8"))
    assert config["hooks"]["PostToolUse"][0]["matcher"] == "^apply_patch$"
