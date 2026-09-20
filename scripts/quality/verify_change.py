#!/usr/bin/env python3
"""Validate structural delivery gates for an OpenSpec Change."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

REQUIRED_DECISION_FILES = ("open-questions.md", "assumptions.md", "decision-log.md")
FINAL_PHASES = {"ready_for_user_acceptance", "user_accepted", "archived"}
MOCK_PATTERN = re.compile(r"\b(mock|fake|simulated)\b", re.IGNORECASE)
DECISION_HEADING = re.compile(r"^### ((?:D|PD)-[^\n]+)", re.MULTILINE)
REQUIRED_DECISION_FIELDS = ("Date", "Source thread/message", "Confirmation quote", "Decision")
REQUIRED_QUESTION_FIELDS = ("Background", "Impact", "Recommendation", "User question")
DISCLOSURE_LISTS = ("known_issues", "unverified_items")
UI_DELIVERY_MODEL = "two-user-gates-three-engineering-checkpoints"


def load_manifest(path: Path) -> dict[str, Any]:
    """Load a JSON delivery manifest."""
    if not path.is_file():
        raise ValueError(f"missing delivery manifest: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid delivery manifest JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("delivery manifest must be a JSON object")
    return value


def unchecked_tasks(tasks_text: str) -> list[str]:
    """Return unchecked Markdown task lines."""
    return [line.strip() for line in tasks_text.splitlines() if re.match(r"^\s*- \[ \]", line)]


def open_questions(text: str) -> list[str]:
    """Return open questions and pending-audit markers."""
    results: list[str] = []
    if "待审计" in text:
        results.append("decision records are still pending audit")
    for block in re.split(r"(?=^### Q-)", text, flags=re.MULTILINE):
        heading = re.search(r"^### (Q-[^\n]+)", block, flags=re.MULTILINE)
        status = re.search(r"^- Status:\s*(.+)$", block, flags=re.MULTILINE)
        if heading and status and status.group(1).strip().lower().startswith("open"):
            results.append(heading.group(1).strip())
    return results


def decision_provenance_errors(text: str) -> list[str]:
    """Validate traceability fields for confirmed product decisions."""
    errors: list[str] = []
    blocks = re.split(r"(?=^### (?:D|PD)-)", text, flags=re.MULTILINE)
    for block in blocks:
        heading = DECISION_HEADING.search(block)
        if not heading:
            continue
        status = re.search(r"^- Status:\s*(.+)$", block, flags=re.MULTILINE)
        if status and not status.group(1).strip().lower().startswith("confirmed"):
            continue
        for field in REQUIRED_DECISION_FIELDS:
            if not re.search(rf"^- {re.escape(field)}:\s*\S.+$", block, flags=re.MULTILINE):
                errors.append(f"{heading.group(1).strip()} missing decision field: {field}")
        if re.search(r"(?:根据用户反馈|user feedback|结合上下文推断)", block, flags=re.IGNORECASE):
            errors.append(f"{heading.group(1).strip()} uses inferred confirmation evidence")
    return errors


def question_format_errors(text: str) -> list[str]:
    """Validate that open questions are concise and decision-ready."""
    errors: list[str] = []
    blocks = re.split(r"(?=^### Q-)", text, flags=re.MULTILINE)
    for block in blocks:
        heading = re.search(r"^### (Q-[^\n]+)", block, flags=re.MULTILINE)
        if not heading:
            continue
        status = re.search(r"^- Status:\s*(.+)$", block, flags=re.MULTILINE)
        if not status or not status.group(1).strip().lower().startswith("open"):
            errors.append(
                f"{heading.group(1).strip()} is not Open; move it out of open-questions.md"
            )
            continue
        for field in REQUIRED_QUESTION_FIELDS:
            if not re.search(rf"^- {re.escape(field)}:\s*\S.+$", block, flags=re.MULTILINE):
                errors.append(f"{heading.group(1).strip()} missing question field: {field}")
        option_count = len(re.findall(r"^- Option [A-C]:\s*\S.+$", block, flags=re.MULTILINE))
        if option_count not in {2, 3}:
            errors.append(f"{heading.group(1).strip()} must contain 2-3 Option fields")
    return errors


def baseline_identity_errors(change_dir: Path) -> list[str]:
    """Detect conflicting frozen prototype checksums across Change documents."""
    checksums: set[str] = set()
    for path in change_dir.rglob("*.md"):
        for line in path.read_text(encoding="utf-8").splitlines():
            # Evidence documents may contain checksums for uploads, reports, or
            # workbooks. Only checksum declarations that explicitly identify a
            # baseline participate in the uniqueness gate.
            if not re.search(r"(?:baseline|基线)", line, flags=re.IGNORECASE):
                continue
            checksums.update(
                value.lower() for value in re.findall(r"\b[0-9a-fA-F]{64}\b", line)
            )
    if len(checksums) > 1:
        return [f"multiple frozen baseline checksums declared: {', '.join(sorted(checksums))}"]
    return []


def external_call_errors(manifest: dict[str, Any], decision_text: str) -> list[str]:
    """Validate declared real-data or paid external-call authorizations."""
    calls = manifest.get("external_calls")
    if calls is None:
        return ["delivery manifest must declare external_calls (use an empty list when none)"]
    if not isinstance(calls, list):
        return ["delivery manifest external_calls must be a list"]
    errors: list[str] = []
    required = {
        "provider",
        "data_scope",
        "cost_ceiling",
        "stop_condition",
        "authorization_decision_id",
    }
    for index, call in enumerate(calls, start=1):
        if not isinstance(call, dict):
            errors.append(f"external_calls[{index}] must be an object")
            continue
        missing = sorted(field for field in required if not str(call.get(field, "")).strip())
        if missing:
            errors.append(f"external_calls[{index}] missing: {', '.join(missing)}")
            continue
        decision_id = str(call["authorization_decision_id"])
        if not re.search(rf"^### {re.escape(decision_id)}\b", decision_text, flags=re.MULTILINE):
            errors.append(
                f"external_calls[{index}] authorization not found in decision log: {decision_id}"
            )
    return errors


def disclosure_errors(manifest: dict[str, Any], phase: str) -> tuple[list[str], list[str]]:
    """Validate proactive disclosure of known issues and unverified scope."""
    errors: list[str] = []
    warnings: list[str] = []
    required = {"id", "summary", "status", "disclosed_to_user"}
    for list_name in DISCLOSURE_LISTS:
        items = manifest.get(list_name)
        if items is None:
            errors.append(
                f"delivery manifest must declare {list_name} (use an empty list when none)"
            )
            continue
        if not isinstance(items, list):
            errors.append(f"delivery manifest {list_name} must be a list")
            continue
        for index, item in enumerate(items, start=1):
            label = f"{list_name}[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{label} must be an object")
                continue
            missing = sorted(field for field in required if field not in item)
            if missing:
                errors.append(f"{label} missing: {', '.join(missing)}")
                continue
            if not str(item["id"]).strip() or not str(item["summary"]).strip():
                errors.append(f"{label} id and summary must not be empty")
            status = str(item["status"]).strip().lower()
            if status not in {"open", "resolved", "excluded"}:
                errors.append(f"{label} status must be Open, Resolved, or Excluded")
                continue
            if not isinstance(item["disclosed_to_user"], bool):
                errors.append(f"{label} disclosed_to_user must be boolean")
                continue
            if status == "open" and not item["disclosed_to_user"]:
                errors.append(f"{label} is Open but has not been disclosed to the user")
            elif status == "open" and phase in FINAL_PHASES:
                errors.append(f"phase '{phase}' is incompatible with Open {label}")
            elif status == "open":
                warnings.append(f"Open {label}: {str(item['summary']).strip()}")
    return errors, warnings


def ui_delivery_errors(change_dir: Path, manifest: dict[str, Any]) -> list[str]:
    """Validate the two-gate UI delivery contract for Changes with prototypes."""
    prototype = change_dir / "prototypes" / "index.html"
    if not prototype.is_file():
        return []
    delivery = manifest.get("ui_delivery")
    if not isinstance(delivery, dict):
        return ["UI Change must declare ui_delivery in the delivery manifest"]
    errors: list[str] = []
    if delivery.get("model") != UI_DELIVERY_MODEL:
        errors.append(f"ui_delivery.model must be '{UI_DELIVERY_MODEL}'")
    if delivery.get("fixture_uses_production_ui") is not True:
        errors.append("ui_delivery.fixture_uses_production_ui must be true")
    production_routes = delivery.get("production_routes")
    if not isinstance(production_routes, list) or not production_routes:
        errors.append("ui_delivery.production_routes must list the production UI entry points")
    checkpoints = delivery.get("engineering_checkpoints")
    if checkpoints != ["A", "B", "C"]:
        errors.append("ui_delivery.engineering_checkpoints must be ['A', 'B', 'C']")
    return errors


def verify_baseline(change_dir: Path) -> str | None:
    """Verify a declared frozen prototype checksum."""
    readme = change_dir / "prototypes" / "README.md"
    prototype = change_dir / "prototypes" / "index.html"
    if not readme.is_file() or not prototype.is_file():
        return None
    match = re.search(r"SHA-256[：:]\s*`?([0-9a-fA-F]{64})", readme.read_text(encoding="utf-8"))
    if not match:
        return None
    actual = hashlib.sha256(prototype.read_bytes()).hexdigest()
    expected = match.group(1).lower()
    return (
        None
        if actual == expected
        else f"frozen prototype checksum mismatch: expected {expected}, got {actual}"
    )


def scan_runtime_paths(root: Path, manifest: dict[str, Any]) -> list[str]:
    """Scan declared production paths for explicit Mock markers."""
    findings: list[str] = []
    allowed = set(manifest.get("allowed_mock_files", []))
    for raw_path in manifest.get("production_paths", []):
        if raw_path in allowed:
            continue
        candidate = root / raw_path
        files = (
            [candidate]
            if candidate.is_file()
            else list(candidate.rglob("*"))
            if candidate.is_dir()
            else []
        )
        for file_path in files:
            if not file_path.is_file() or file_path.suffix not in {".py", ".js", ".ts", ".html"}:
                continue
            try:
                text = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if MOCK_PATTERN.search(text):
                findings.append(str(file_path.relative_to(root)))
    return findings


def verify_change(root: Path, change_name: str) -> tuple[list[str], list[str]]:
    """Verify one Change and return errors and warnings."""
    errors: list[str] = []
    warnings: list[str] = []
    change_dir = root / "openspec" / "changes" / change_name
    if not change_dir.is_dir():
        return [f"change does not exist: {change_dir}"], warnings
    decisions_dir = change_dir / "decisions"
    for filename in REQUIRED_DECISION_FILES:
        if not (decisions_dir / filename).is_file():
            errors.append(f"missing decision file: decisions/{filename}")
    question_file = decisions_dir / "open-questions.md"
    if question_file.is_file():
        question_text = question_file.read_text(encoding="utf-8")
        errors.extend(
            f"unresolved product question: {item}" for item in open_questions(question_text)
        )
        errors.extend(question_format_errors(question_text))
    try:
        manifest = load_manifest(change_dir / "verification" / "delivery-status.json")
    except ValueError as exc:
        errors.append(str(exc))
        manifest = {}
    phase = str(manifest.get("phase", "developing"))
    acceptance = str(manifest.get("product_acceptance", "pending"))
    tasks_path = change_dir / "tasks.md"
    pending = (
        unchecked_tasks(tasks_path.read_text(encoding="utf-8")) if tasks_path.is_file() else []
    )
    if phase in FINAL_PHASES and pending:
        errors.append(f"phase '{phase}' is incompatible with {len(pending)} unchecked tasks")
    if phase == "user_accepted" and acceptance != "accepted":
        errors.append("user_accepted phase requires product_acceptance='accepted'")
    decision_log = decisions_dir / "decision-log.md"
    decision_text = decision_log.read_text(encoding="utf-8") if decision_log.is_file() else ""
    errors.extend(decision_provenance_errors(decision_text))
    errors.extend(external_call_errors(manifest, decision_text))
    errors.extend(ui_delivery_errors(change_dir, manifest))
    disclosure_blockers, disclosure_warnings = disclosure_errors(manifest, phase)
    errors.extend(disclosure_blockers)
    warnings.extend(disclosure_warnings)
    if (
        acceptance == "accepted"
        and decision_log.is_file()
        and "待追溯" in decision_log.read_text(encoding="utf-8")
    ):
        errors.append("product acceptance cannot rely on an unaudited decision log")
    baseline_error = verify_baseline(change_dir)
    if baseline_error:
        errors.append(baseline_error)
    errors.extend(baseline_identity_errors(change_dir))
    mock_files = scan_runtime_paths(root, manifest)
    if mock_files:
        message = "explicit Mock markers found in declared production paths: " + ", ".join(
            mock_files
        )
        (errors if phase in FINAL_PHASES else warnings).append(message)
    if pending:
        warnings.append(f"{len(pending)} tasks remain unchecked")
    return errors, warnings


def main() -> int:
    """Run the verifier CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("change_name", help="Directory name under openspec/changes")
    parser.add_argument(
        "--enforce-final-only",
        action="store_true",
        help="Return success for developing Changes while still printing findings",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    errors, warnings = verify_change(root, args.change_name)
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        if args.enforce_final_only:
            manifest_path = (
                root
                / "openspec"
                / "changes"
                / args.change_name
                / "verification"
                / "delivery-status.json"
            )
            try:
                phase = str(load_manifest(manifest_path).get("phase", "developing"))
            except ValueError:
                phase = "developing"
            if phase not in FINAL_PHASES:
                print(f"ADVISORY: developing phase has {len(errors)} blocker(s); CI remains green")
                return 0
        print(f"BLOCKED: {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1
    print(f"PASS: 0 errors, {len(warnings)} warning(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
