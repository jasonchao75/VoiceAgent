#!/usr/bin/env python3
"""Batch-test library_ar through the Speechmatics streaming single test."""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[3]
RUNNER_PATH = ROOT_DIR / "scripts/vendor/soniox/test_batch.py"
SPEC = importlib.util.spec_from_file_location("library_ar_batch_runner", RUNNER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot load batch runner: {RUNNER_PATH}")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)

runner.VENDOR_DIR = Path(__file__).resolve().parent
runner.RESULTS_DIR = ROOT_DIR / "benchmarks/library_ar/test-results/speechmatics"
runner.SINGLE_SCRIPT = runner.VENDOR_DIR / "test_speechmatics.py"
runner.SINGLE_EXTRA_ARGS = (
    "--config",
    str(ROOT_DIR / "configs/vendor/speechmatics/library_ar_config.json"),
)
runner.MODEL = "enhanced"
runner.VENDOR = "speechmatics"


if __name__ == "__main__":
    raise SystemExit(asyncio.run(runner.run(runner.build_parser().parse_args())))
