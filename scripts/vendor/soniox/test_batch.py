#!/usr/bin/env python3
"""Batch-test library_ar through the existing Soniox streaming single test."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import os
import sys
import tempfile
import time
import wave
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence


ROOT_DIR = Path(__file__).resolve().parents[3]
VENDOR_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT_DIR / "benchmarks/library_ar/arabic_asr_benchmark_sheet3.csv"
RESULTS_DIR = ROOT_DIR / "benchmarks/library_ar/test-results/soniox"
SINGLE_SCRIPT = VENDOR_DIR / "test_soniox.py"
SINGLE_EXTRA_ARGS: tuple[str, ...] = ()
MODEL = "stt-rt-v4"
VENDOR = "soniox"
sys.path.insert(0, str(ROOT_DIR / "scripts/vendor/deepgram"))
import test_batch as result_store  # noqa: E402


def setup_logging(timestamp: str) -> Path:
    """Configure a retained batch log.

    Args:
        timestamp: Run timestamp.

    Returns:
        Created log path.
    """
    log_path = VENDOR_DIR / "logs" / f"batch_library_ar_{timestamp}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )
    return log_path


def load_records() -> list[result_store.BenchmarkRecord]:
    """Load benchmark rows using manifest audio paths.

    Returns:
        Ordered benchmark records.
    """
    records = []
    with MANIFEST_PATH.open(encoding="utf-8-sig", newline="") as stream:
        for order, row in enumerate(csv.DictReader(stream), start=1):
            records.append(
                result_store.BenchmarkRecord(
                    order=order,
                    benchmark_id=row["Benchmark ID"].strip(),
                    dialect=row["Dialect"].strip(),
                    audio_path=row["wav"].strip(),
                    reference_text=row[
                        "Annotation Text(pure Arabic/number formatted)"
                    ].strip(),
                )
            )
    return records


def result_without_api(
    record: result_store.BenchmarkRecord, status: str, error: str
) -> result_store.TestResult:
    """Build a vendor-labelled result for a row that cannot call the API.

    Args:
        record: Benchmark record.
        status: Result status.
        error: Human-readable reason.

    Returns:
        Unscored result.
    """
    result = result_store.result_without_score(
        record, MODEL, status, error, language="ar"
    )
    return replace(result, vendor=VENDOR)


async def transcribe_one(
    record: result_store.BenchmarkRecord,
    accuracy: Any,
    semaphore: asyncio.Semaphore,
    timeout_margin: float,
) -> result_store.TestResult:
    """Run one isolated Soniox streaming subprocess and score its output.

    Args:
        record: Benchmark record.
        accuracy: Loaded unchanged library accuracy module.
        semaphore: Concurrency limiter.
        timeout_margin: Seconds added to source audio duration.

    Returns:
        Scored, skipped, or failed result.
    """
    if not record.audio_path:
        return result_without_api(record, "skipped", "Audio path is empty")
    audio_path = MANIFEST_PATH.parent / record.audio_path
    if not audio_path.is_file():
        return result_without_api(record, "skipped", "Audio file is missing")
    with wave.open(str(audio_path), "rb") as wav_file:
        duration_ms = wav_file.getnframes() / wav_file.getframerate() * 1000.0
    temp_path = Path(tempfile.gettempdir()) / (
        f"voiceagent_{VENDOR}_{os.getpid()}_{record.benchmark_id}.json"
    )
    started_at = time.monotonic()
    try:
        async with semaphore:
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                str(SINGLE_SCRIPT),
                "--audio",
                str(audio_path),
                "--result-json",
                str(temp_path),
                *SINGLE_EXTRA_ARGS,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                _, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=duration_ms / 1000.0 + timeout_margin,
                )
            except TimeoutError:
                process.kill()
                await process.wait()
                return result_without_api(record, "failed", "Subprocess timeout")
        if process.returncode != 0 or not temp_path.exists():
            message = stderr.decode("utf-8", errors="replace").strip()
            return result_without_api(
                record, "failed", message[-500:] or f"Exit {process.returncode}"
            )
        payload = json.loads(temp_path.read_text(encoding="utf-8"))
        transcript = str(payload.get("transcript", ""))
        state = result_store.StreamState(
            [], first_result_latency_ms=payload.get("first_result_latency_ms")
        )
        if not record.reference_text:
            result = result_store.result_without_score(
                record,
                MODEL,
                "skipped",
                "Reference text is empty; transcript retained without scoring",
                transcript=transcript,
                state=state,
                processing_time_ms=(time.monotonic() - started_at) * 1000.0,
                audio_duration_ms=duration_ms,
                language="ar",
            )
        else:
            result = result_store.score_transcript(
                record,
                transcript,
                accuracy,
                MODEL,
                state,
                (time.monotonic() - started_at) * 1000.0,
                duration_ms,
                "ar",
            )
        return replace(result, vendor=VENDOR)
    except Exception as exc:
        return result_without_api(record, "failed", str(exc))
    finally:
        temp_path.unlink(missing_ok=True)


def save_daily(
    results: list[result_store.TestResult], timestamp: str, log_path: Path
) -> None:
    """Atomically update the three daily result files.

    Args:
        results: Complete merged daily result set.
        timestamp: Latest run timestamp.
        log_path: Retained run log path.
    """
    day = timestamp[:8]
    workbook = result_store.daily_result_path(RESULTS_DIR, day)
    details = result_store.build_compact_csv_rows(results)
    summary = result_store.build_summary(results)
    metadata = [
        {"key": "vendor", "value": VENDOR},
        {"key": "model", "value": MODEL},
        {"key": "library", "value": "library_ar"},
        {"key": "latest_run", "value": timestamp},
        {"key": "daily_record_count", "value": len(results)},
        {"key": "log", "value": str(log_path.relative_to(ROOT_DIR))},
        {
            "key": "accuracy_script",
            "value": "benchmarks/library_ar/asr_char_accuracy.py",
        },
    ]
    result_store.write_xlsx(
        workbook,
        [
            ("details", details),
            ("summary", summary),
            ("run_metadata", metadata),
            ("_state", result_store.build_state_rows(results)),
        ],
    )
    result_store.write_csv(workbook.with_suffix(".csv"), details)
    result_store.write_csv(
        workbook.with_name(f"{workbook.stem}_summary.csv"), summary
    )


async def run(args: argparse.Namespace) -> int:
    """Run or resume the full daily Soniox batch.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Process exit code.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = setup_logging(timestamp)
    workbook = result_store.daily_result_path(RESULTS_DIR, timestamp[:8])
    previous = result_store.load_state_rows(workbook)
    previous_ids = {item.benchmark_id for item in previous}
    records = load_records()
    if args.benchmark_id:
        requested = set(args.benchmark_id)
        records = [item for item in records if item.benchmark_id in requested]
    elif not args.rerun_existing:
        records = [item for item in records if item.benchmark_id not in previous_ids]
    if args.limit is not None:
        records = records[: args.limit]
    logging.info(
        "Starting %s batch selected=%d existing=%d concurrency=%d",
        VENDOR,
        len(records),
        len(previous),
        args.concurrency,
    )
    accuracy = result_store.load_accuracy_module()
    semaphore = asyncio.Semaphore(args.concurrency)
    tasks = [
        asyncio.create_task(
            transcribe_one(item, accuracy, semaphore, args.timeout_margin)
        )
        for item in records
    ]
    current = []
    for completed, task in enumerate(asyncio.as_completed(tasks), start=1):
        result = await task
        current.append(result)
        if result.status == "failed":
            logging.error("%s failed: %s", result.benchmark_id, result.error)
        elif completed % 10 == 0 or completed == len(tasks):
            logging.info("Progress %d/%d", completed, len(tasks))
        if completed % 25 == 0 or completed == len(tasks):
            save_daily(
                result_store.merge_daily_results(previous, current),
                timestamp,
                log_path,
            )
    if not tasks:
        save_daily(previous, timestamp, log_path)
    merged = result_store.merge_daily_results(previous, current)
    logging.info("Finished daily_records=%d log=%s", len(merged), log_path)
    return 0 if not any(item.status == "failed" for item in current) else 1


def build_parser() -> argparse.ArgumentParser:
    """Build the batch CLI parser.

    Returns:
        Configured parser.
    """
    parser = argparse.ArgumentParser(
        description=f"Batch-test {VENDOR} on library_ar"
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--benchmark-id", action="append")
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--timeout-margin", type=float, default=30.0)
    parser.add_argument("--rerun-existing", action="store_true")
    return parser


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(build_parser().parse_args())))
