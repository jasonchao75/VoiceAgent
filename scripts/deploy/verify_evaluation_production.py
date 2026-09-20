#!/usr/bin/env python3
"""Verify production Evaluation provenance and remove only legacy result history."""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from pathlib import Path

RESULT_COUNTS = {
    "batches": "evaluation_batches",
    "reports": "evaluation_reports",
    "reviews": "evaluation_reviews",
    "benchmarks": "evaluation_benchmarks",
}
KNOWN_LOCAL_BATCH_IDS = {
    "EV-20260918-2655",
    "EV-20260918-4966",
    "EV-20260920-566C",
    "EV-20260920-7878",
    "EV-20260920-9D33",
}


def _connect(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def verify(database_path: Path, *, mark_verified: bool) -> dict[str, int]:
    """Require provenance and verify empty history once for a new deployment."""
    if not database_path.is_file():
        raise RuntimeError(f"Evaluation database is missing: {database_path}")
    with _connect(database_path) as connection:
        provenance = connection.execute(
            "SELECT value FROM evaluation_meta WHERE key='deployment.provenance'"
        ).fetchone()
        if provenance is None or provenance[0] != "production":
            raise RuntimeError("Evaluation database has no production provenance marker")
        counts = {
            name: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for name, table in RESULT_COUNTS.items()
        }
        empty_history_verified = connection.execute(
            "SELECT value FROM evaluation_meta "
            "WHERE key='deployment.empty_history_verified'"
        ).fetchone()
        is_initial_verification = (
            empty_history_verified is None or empty_history_verified[0] != "true"
        )
        if is_initial_verification and any(counts.values()):
            raise RuntimeError(f"Production Evaluation history is not empty: {counts}")
        if mark_verified and is_initial_verification:
            connection.execute(
                """INSERT INTO evaluation_meta (key,value,updated_at)
                   VALUES ('deployment.empty_history_verified','true',datetime('now'))
                   ON CONFLICT(key) DO UPDATE SET value='true',updated_at=datetime('now')"""
            )
    return counts


def precheck(database_path: Path) -> dict[str, int]:
    """Reject copied local state before the production container is replaced."""
    if not database_path.exists():
        return {"known_local_batches": 0}
    with _connect(database_path) as connection:
        provenance = connection.execute(
            "SELECT value FROM evaluation_meta WHERE key='deployment.provenance'"
        ).fetchone()
        if provenance is None or provenance[0] != "production":
            raise RuntimeError("Refusing a pre-existing non-production Evaluation volume")
        placeholders = ",".join("?" for _ in KNOWN_LOCAL_BATCH_IDS)
        count = int(
            connection.execute(
                f"SELECT COUNT(*) FROM evaluation_batches WHERE id IN ({placeholders})",
                tuple(sorted(KNOWN_LOCAL_BATCH_IDS)),
            ).fetchone()[0]
        )
        if count:
            raise RuntimeError("Known local acceptance batch IDs exist in production storage")
    return {"known_local_batches": count}


def cleanup_legacy(data_root: Path) -> dict[str, int]:
    """Delete only Evaluation result rows and generated artifacts in a shared data root."""
    resolved_root = data_root.resolve()
    if resolved_root == Path("/") or not resolved_root.is_dir():
        raise RuntimeError(f"Unsafe legacy data root: {resolved_root}")
    database_path = resolved_root / "evaluation.db"
    if not database_path.exists():
        return {name: 0 for name in RESULT_COUNTS}
    with _connect(database_path) as connection:
        existing_tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        required = set(RESULT_COUNTS.values()) | {
            "evaluation_benchmark_revisions",
            "evaluation_proposed_tag_actions",
            "evaluation_commands",
            "evaluation_audit",
            "evaluation_benchmark_exports",
            "evaluation_elevenlabs_jobs",
        }
        missing = sorted(required - existing_tables)
        if missing:
            raise RuntimeError(f"Legacy Evaluation schema is incomplete: {missing}")
        connection.execute("DELETE FROM evaluation_proposed_tag_actions")
        connection.execute("DELETE FROM evaluation_benchmark_revisions")
        connection.execute("DELETE FROM evaluation_reviews")
        connection.execute("DELETE FROM evaluation_benchmarks")
        connection.execute("DELETE FROM evaluation_reports")
        connection.execute("DELETE FROM evaluation_commands")
        connection.execute("DELETE FROM evaluation_audit")
        connection.execute("DELETE FROM evaluation_benchmark_exports")
        connection.execute("DELETE FROM evaluation_elevenlabs_jobs")
        connection.execute("DELETE FROM evaluation_batches")
        counts = {
            name: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for name, table in RESULT_COUNTS.items()
        }
    for directory_name in (
        "evaluation-asr-clips",
        "evaluation-benchmark-clips",
        "evaluation-exports",
    ):
        directory = resolved_root / directory_name
        if directory.is_dir():
            shutil.rmtree(directory)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("precheck", "verify", "cleanup-legacy"))
    parser.add_argument("path", type=Path)
    parser.add_argument("--mark-verified", action="store_true")
    args = parser.parse_args()
    if args.mode == "precheck":
        result = precheck(args.path)
    elif args.mode == "verify":
        result = verify(args.path, mark_verified=args.mark_verified)
    else:
        result = cleanup_legacy(args.path)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
