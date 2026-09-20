"""Tests for the OpenSpec Change delivery verifier."""

from pathlib import Path

from scripts.quality.verify_change import (
    FINAL_PHASES,
    baseline_identity_errors,
    decision_provenance_errors,
    disclosure_errors,
    external_call_errors,
    open_questions,
    question_format_errors,
    ui_delivery_errors,
    unchecked_tasks,
    verify_change,
)


def test_open_questions_detects_open_items_and_pending_audit() -> None:
    """Pending audits and Open questions block delivery."""
    text = "# Open Questions\n- Count: 待审计\n### Q-001: Choice\n- Status: Open\n"
    assert open_questions(text) == ["decision records are still pending audit", "Q-001: Choice"]


def test_unchecked_tasks_returns_only_pending_items() -> None:
    """Only unchecked Markdown tasks are returned."""
    assert unchecked_tasks("- [x] done\n- [ ] pending\n") == ["- [ ] pending"]


def test_missing_change_is_blocked(tmp_path: Path) -> None:
    """A missing Change must fail rather than silently pass."""
    errors, warnings = verify_change(tmp_path, "missing")
    assert errors == [f"change does not exist: {tmp_path}/openspec/changes/missing"]
    assert warnings == []


def test_only_acceptance_phases_are_ci_enforced() -> None:
    """Development remains advisory while acceptance phases are enforced."""
    assert "developing" not in FINAL_PHASES
    assert "ready_for_user_acceptance" in FINAL_PHASES
    assert "user_accepted" in FINAL_PHASES
    assert "archived" in FINAL_PHASES


def test_confirmed_decision_requires_traceable_source() -> None:
    """Confirmed decisions require a date, source, quote, and decision."""
    text = "### D-001: Choice\n- Status: Confirmed\n- Date: 2026-09-16\n"
    errors = decision_provenance_errors(text)
    assert any("Source thread/message" in error for error in errors)
    assert any("Confirmation quote" in error for error in errors)
    assert any("Decision" in error for error in errors)


def test_open_question_requires_two_options_and_product_fields() -> None:
    """An open question must be compact and ready for a decision."""
    text = "### Q-001: Choice\n- Status: Open\n- Background: Missing rule\n- Option A: A\n"
    errors = question_format_errors(text)
    assert any("2-3 Option" in error for error in errors)
    assert any("User question" in error for error in errors)


def test_external_call_requires_authorization_record() -> None:
    """Paid or real-data calls must reference explicit authorization."""
    manifest = {
        "external_calls": [
            {
                "provider": "Example",
                "data_scope": "one test file",
                "cost_ceiling": "$1",
                "stop_condition": "one request",
                "authorization_decision_id": "D-007",
            }
        ]
    }
    assert external_call_errors(manifest, "") == [
        "external_calls[1] authorization not found in decision log: D-007"
    ]


def test_open_issue_must_be_disclosed_before_turn_ends() -> None:
    """An agent cannot silently retain a known Open issue."""
    manifest = {
        "known_issues": [
            {
                "id": "ISSUE-001",
                "summary": "Real upload path is unverified",
                "status": "Open",
                "disclosed_to_user": False,
            }
        ],
        "unverified_items": [],
    }
    errors, warnings = disclosure_errors(manifest, "developing")
    assert errors == ["known_issues[1] is Open but has not been disclosed to the user"]
    assert warnings == []


def test_baseline_identity_ignores_non_baseline_artifact_checksums(tmp_path: Path) -> None:
    """Evidence checksums must not be mistaken for frozen UI baselines."""
    (tmp_path / "prototypes").mkdir()
    (tmp_path / "verification").mkdir()
    (tmp_path / "prototypes" / "README.md").write_text(
        "Baseline SHA-256: `" + "a" * 64 + "`\n",
        encoding="utf-8",
    )
    (tmp_path / "verification" / "artifact.md").write_text(
        "Workbook SHA-256: `" + "b" * 64 + "`\n",
        encoding="utf-8",
    )

    assert baseline_identity_errors(tmp_path) == []


def test_disclosed_open_issue_warns_during_development_but_blocks_delivery() -> None:
    """Disclosed risks may remain visible during development, never final acceptance."""
    manifest = {
        "known_issues": [
            {
                "id": "ISSUE-001",
                "summary": "Real upload path is unverified",
                "status": "Open",
                "disclosed_to_user": True,
            }
        ],
        "unverified_items": [],
    }
    errors, warnings = disclosure_errors(manifest, "developing")
    assert errors == []
    assert warnings == ["Open known_issues[1]: Real upload path is unverified"]

    errors, warnings = disclosure_errors(manifest, "ready_for_user_acceptance")
    assert errors == ["phase 'ready_for_user_acceptance' is incompatible with Open known_issues[1]"]
    assert warnings == []


def test_ui_change_requires_two_gate_three_checkpoint_contract(tmp_path: Path) -> None:
    """A UI Change must prove fixtures exercise the production UI."""
    (tmp_path / "prototypes").mkdir()
    (tmp_path / "prototypes" / "index.html").write_text("<main></main>", encoding="utf-8")

    assert ui_delivery_errors(tmp_path, {}) == [
        "UI Change must declare ui_delivery in the delivery manifest"
    ]
    assert (
        ui_delivery_errors(
            tmp_path,
            {
                "ui_delivery": {
                    "model": "two-user-gates-three-engineering-checkpoints",
                    "fixture_uses_production_ui": True,
                    "production_routes": ["frontend/evaluation.html"],
                    "engineering_checkpoints": ["A", "B", "C"],
                }
            },
        )
        == []
    )
