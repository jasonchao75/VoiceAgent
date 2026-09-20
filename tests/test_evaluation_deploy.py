"""Production Evaluation storage isolation and cleanup tests."""

from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest

from src.evaluation.storage import EvaluationStore


def _deploy_module():
    path = Path(__file__).parents[1] / "scripts/deploy/verify_evaluation_production.py"
    spec = importlib.util.spec_from_file_location("verify_evaluation_production", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_production_store_marks_only_a_fresh_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A copied local database must not be silently relabeled as production."""
    dataset_root = Path(__file__).parents[1] / "benchmarks/RiyadBankConversation"
    database_path = tmp_path / "evaluation.db"
    local_store = EvaluationStore(database_path, dataset_root)
    await local_store.initialize()
    monkeypatch.setenv("VOICE_AGENT_DEPLOYMENT_ENVIRONMENT", "production")

    with pytest.raises(RuntimeError, match="without production provenance"):
        await EvaluationStore(database_path, dataset_root).initialize()

    database_path.unlink()
    await EvaluationStore(database_path, dataset_root).initialize()
    with sqlite3.connect(database_path) as connection:
        marker = connection.execute(
            "SELECT value FROM evaluation_meta WHERE key='deployment.provenance'"
        ).fetchone()
    assert marker == ("production",)


def test_legacy_cleanup_preserves_configuration_and_removes_results(tmp_path: Path) -> None:
    """One-time cleanup must retain connections while clearing visible result history."""
    module = _deploy_module()
    database_path = tmp_path / "evaluation.db"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE evaluation_batches (id TEXT PRIMARY KEY);
            CREATE TABLE evaluation_reports (report_id TEXT PRIMARY KEY, batch_id TEXT);
            CREATE TABLE evaluation_reviews (id TEXT PRIMARY KEY, batch_id TEXT);
            CREATE TABLE evaluation_benchmarks (id TEXT PRIMARY KEY, batch_id TEXT);
            CREATE TABLE evaluation_benchmark_revisions (id TEXT PRIMARY KEY);
            CREATE TABLE evaluation_proposed_tag_actions (report_id TEXT);
            CREATE TABLE evaluation_commands (idempotency_key TEXT);
            CREATE TABLE evaluation_audit (id TEXT PRIMARY KEY);
            CREATE TABLE evaluation_benchmark_exports (id TEXT PRIMARY KEY);
            CREATE TABLE evaluation_elevenlabs_jobs (request_id TEXT PRIMARY KEY);
            CREATE TABLE evaluation_connections (provider TEXT PRIMARY KEY);
            INSERT INTO evaluation_batches VALUES ('EV-LOCAL');
            INSERT INTO evaluation_reports VALUES ('EV-LOCAL-R1','EV-LOCAL');
            INSERT INTO evaluation_reviews VALUES ('RV-LOCAL','EV-LOCAL');
            INSERT INTO evaluation_benchmarks VALUES ('BM-LOCAL','EV-LOCAL');
            INSERT INTO evaluation_connections VALUES ('azure_gpt');
            """
        )

    counts = module.cleanup_legacy(tmp_path)

    assert counts == {"batches": 0, "reports": 0, "reviews": 0, "benchmarks": 0}
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT provider FROM evaluation_connections").fetchall() == [
            ("azure_gpt",)
        ]


def test_empty_history_is_required_only_for_initial_production_deploy(
    tmp_path: Path,
) -> None:
    """Later releases must preserve legitimate production Evaluation history."""
    module = _deploy_module()
    database_path = tmp_path / "evaluation.db"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE evaluation_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE evaluation_batches (id TEXT PRIMARY KEY);
            CREATE TABLE evaluation_reports (report_id TEXT PRIMARY KEY);
            CREATE TABLE evaluation_reviews (id TEXT PRIMARY KEY);
            CREATE TABLE evaluation_benchmarks (id TEXT PRIMARY KEY);
            INSERT INTO evaluation_meta VALUES (
                'deployment.provenance', 'production', datetime('now')
            );
            INSERT INTO evaluation_batches VALUES ('EV-PRODUCTION');
            """
        )

    with pytest.raises(RuntimeError, match="history is not empty"):
        module.verify(database_path, mark_verified=True)

    with sqlite3.connect(database_path) as connection:
        connection.execute("DELETE FROM evaluation_batches")
    assert module.verify(database_path, mark_verified=True) == {
        "batches": 0,
        "reports": 0,
        "reviews": 0,
        "benchmarks": 0,
    }

    with sqlite3.connect(database_path) as connection:
        connection.execute("INSERT INTO evaluation_batches VALUES ('EV-PRODUCTION')")
    assert module.verify(database_path, mark_verified=True)["batches"] == 1
