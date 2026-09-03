#!/usr/bin/env python3
"""Batch-test Deepgram Nova-3 streaming ASR with a benchmark library."""

from __future__ import annotations

import argparse
import asyncio
import copy
import csv
import importlib.util
import json
import logging
import os
import re
import ssl
import sys
import time
import wave
import zipfile
from dataclasses import dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Sequence
from urllib.parse import urlencode
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

import websockets
import certifi
from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = ROOT_DIR / "configs/vendor/deepgram/config.json"
ACCURACY_SCRIPT_PATH = ROOT_DIR / "benchmarks/library_ar/asr_char_accuracy.py"
VENDOR_NAME = "deepgram"
INVALID_XML_RE = re.compile(
    "[\x00-\x08\x0B\x0C\x0E-\x1F\uD800-\uDFFF\uFFFE\uFFFF]"
)


@dataclass(frozen=True)
class BenchmarkRecord:
    """Represent one manifest row required for ASR evaluation."""

    order: int
    benchmark_id: str
    dialect: str
    audio_path: str
    reference_text: str


@dataclass
class StreamState:
    """Collect state emitted by one Deepgram streaming connection."""

    final_segments: list[str]
    interim_count: int = 0
    first_result_latency_ms: float | None = None
    request_id: str = ""


@dataclass(frozen=True)
class TestResult:
    """Represent one batch result and its library-defined metrics."""

    order: int
    benchmark_id: str
    audio_path: str
    reference_text: str
    transcript: str
    normalized_reference: str
    normalized_transcript: str
    char_substitutions: int | None
    char_deletions: int | None
    char_insertions: int | None
    reference_char_count: int | None
    cer: float | None
    character_accuracy: float | None
    word_substitutions: int | None
    word_deletions: int | None
    word_insertions: int | None
    reference_word_count: int | None
    wer: float | None
    word_accuracy: float | None
    first_result_latency_ms: float | None
    processing_time_ms: float | None
    audio_duration_ms: float | None
    request_id: str
    status: str
    error: str
    vendor: str
    model: str
    language: str


def load_json(path: Path) -> dict[str, Any]:
    """Load a UTF-8 JSON object.

    Args:
        path: JSON configuration path.

    Returns:
        Parsed JSON object.

    Raises:
        ValueError: If the root JSON value is not an object.
    """
    with path.open(encoding="utf-8") as config_file:
        value = json.load(config_file)
    if not isinstance(value, dict):
        raise ValueError(f"Config root must be an object: {path}")
    return value


def load_accuracy_module() -> Any:
    """Load the existing library_ar calculator without modifying its logic.

    Returns:
        Loaded Python module.

    Raises:
        RuntimeError: If the module cannot be loaded.
    """
    spec = importlib.util.spec_from_file_location(
        "library_ar_asr_char_accuracy", ACCURACY_SCRIPT_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load accuracy script: {ACCURACY_SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def validate_config(config: dict[str, Any]) -> None:
    """Validate required Deepgram and benchmark configuration.

    Args:
        config: Parsed configuration.

    Raises:
        ValueError: If a required setting is missing or incompatible.
    """
    endpoint = str(config.get("endpoint", ""))
    if endpoint != "wss://api.deepgram.com/v1/listen":
        raise ValueError("Deepgram Nova streaming endpoint must be /v1/listen")

    audio = config.get("audio", {})
    transcription = config.get("transcription", {})
    connection = config.get("connection", {})
    batch = config.get("batch", {})
    if transcription.get("model") != "nova-3":
        raise ValueError("This test requires transcription.model=nova-3")
    if not transcription.get("language"):
        raise ValueError("transcription.language must be explicit")
    if audio.get("encoding") != "linear16":
        raise ValueError("This benchmark requires audio.encoding=linear16")
    for key in ("sample_rate", "sample_width_bits", "channels", "chunk_size_ms"):
        if int(audio.get(key, 0)) <= 0:
            raise ValueError(f"audio.{key} must be greater than zero")
    if int(audio.get("tail_silence_ms", 0)) < 0:
        raise ValueError("audio.tail_silence_ms must be zero or greater")
    for key in (
        "open_timeout_seconds",
        "close_timeout_seconds",
        "finalize_timeout_seconds",
        "keepalive_interval_seconds",
    ):
        if float(connection.get(key, 0)) <= 0:
            raise ValueError(f"connection.{key} must be greater than zero")
    for key in (
        "library",
        "manifest",
        "benchmark_id_column",
        "dialect_column",
        "audio_path_column",
        "reference_columns",
        "language_by_dialect",
        "results_directory",
    ):
        if not batch.get(key):
            raise ValueError(f"batch.{key} is required")


def resolve_project_path(value: str) -> Path:
    """Resolve a configuration path relative to the project root.

    Args:
        value: Absolute or project-relative path.

    Returns:
        Resolved path.
    """
    path = Path(value)
    return path if path.is_absolute() else ROOT_DIR / path


def load_manifest(config: dict[str, Any]) -> tuple[Path, list[BenchmarkRecord]]:
    """Load benchmark records using configured column mappings.

    Args:
        config: Parsed Deepgram configuration.

    Returns:
        Manifest path and ordered benchmark records.

    Raises:
        ValueError: If required manifest columns are absent.
    """
    batch = config["batch"]
    manifest_path = resolve_project_path(str(batch["manifest"]))
    id_column = str(batch["benchmark_id_column"])
    dialect_column = str(batch["dialect_column"])
    audio_column = str(batch["audio_path_column"])
    reference_columns = [str(item) for item in batch["reference_columns"]]
    records: list[BenchmarkRecord] = []
    with manifest_path.open(encoding="utf-8-sig", newline="") as manifest_file:
        reader = csv.DictReader(manifest_file)
        available = set(reader.fieldnames or [])
        required = {id_column, dialect_column, audio_column, *reference_columns}
        missing = sorted(required - available)
        if missing:
            raise ValueError(f"Manifest missing columns: {', '.join(missing)}")
        for order, row in enumerate(reader, start=1):
            reference = next(
                (str(row.get(column, "")).strip() for column in reference_columns if str(row.get(column, "")).strip()),
                "",
            )
            records.append(
                BenchmarkRecord(
                    order=order,
                    benchmark_id=str(row.get(id_column, "")).strip(),
                    dialect=str(row.get(dialect_column, "")).strip(),
                    audio_path=str(row.get(audio_column, "")).strip(),
                    reference_text=reference,
                )
            )
    return manifest_path, records


def validate_audio(path: Path, audio_config: dict[str, Any]) -> tuple[int, float]:
    """Validate a WAV file against configured raw PCM properties.

    Args:
        path: WAV file path.
        audio_config: Expected audio settings.

    Returns:
        Frame count and duration in milliseconds.

    Raises:
        ValueError: If the WAV properties do not match the configuration.
    """
    with wave.open(str(path), "rb") as wav_file:
        actual = {
            "sample_rate": wav_file.getframerate(),
            "sample_width_bits": wav_file.getsampwidth() * 8,
            "channels": wav_file.getnchannels(),
        }
        if wav_file.getcomptype() != "NONE":
            raise ValueError(f"Compressed WAV is unsupported: {path}")
        for key, value in actual.items():
            if value != int(audio_config[key]):
                raise ValueError(
                    f"Audio {key} mismatch for {path}: expected "
                    f"{audio_config[key]}, got {value}"
                )
        frames = wav_file.getnframes()
        duration_ms = frames * 1000.0 / actual["sample_rate"]
    return frames, duration_ms


def query_value(value: Any) -> str:
    """Convert a JSON configuration value to a query-string value.

    Args:
        value: Scalar configuration value.

    Returns:
        Deepgram-compatible string value.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def build_websocket_url(config: dict[str, Any]) -> str:
    """Build the documented Deepgram v1 streaming URL.

    Args:
        config: Parsed configuration.

    Returns:
        WebSocket URL including query parameters.
    """
    audio = config["audio"]
    transcription = config["transcription"]
    query_items: list[tuple[str, str]] = [
        ("encoding", query_value(audio["encoding"])),
        ("sample_rate", query_value(audio["sample_rate"])),
        ("channels", query_value(audio["channels"])),
    ]
    for key, value in transcription.items():
        if value is None or value == "" or value == []:
            continue
        if isinstance(value, list):
            query_items.extend((key, query_value(item)) for item in value)
        else:
            query_items.append((key, query_value(value)))
    return f"{config['endpoint']}?{urlencode(query_items, doseq=True)}"


async def receive_messages(
    websocket: Any,
    state: StreamState,
    first_audio_sent_at: float,
    finalized: asyncio.Event,
) -> None:
    """Receive transcripts concurrently with audio transmission.

    Args:
        websocket: Connected Deepgram WebSocket.
        state: Mutable connection result state.
        first_audio_sent_at: Monotonic timestamp of the first audio chunk.
        finalized: Event set after Deepgram flushes final results.
    """
    async for raw_message in websocket:
        if not isinstance(raw_message, str):
            continue
        message = json.loads(raw_message)
        message_type = message.get("type", "")
        if message_type == "Results":
            alternatives = message.get("channel", {}).get("alternatives", [])
            transcript = alternatives[0].get("transcript", "").strip() if alternatives else ""
            if transcript and state.first_result_latency_ms is None:
                state.first_result_latency_ms = (
                    time.monotonic() - first_audio_sent_at
                ) * 1000.0
            if message.get("is_final") and transcript:
                state.final_segments.append(transcript)
            elif transcript:
                state.interim_count += 1
            metadata = message.get("metadata", {})
            state.request_id = str(metadata.get("request_id", state.request_id))
            if message.get("from_finalize"):
                finalized.set()
        elif message_type == "Metadata":
            state.request_id = str(message.get("request_id", state.request_id))
        elif message_type == "UtteranceEnd":
            logging.debug("Received Deepgram UtteranceEnd")
        elif message_type == "SpeechStarted":
            logging.debug("Received Deepgram SpeechStarted")


async def send_keepalive(
    websocket: Any, interval_seconds: float, stopped: asyncio.Event
) -> None:
    """Send documented KeepAlive messages until streaming stops.

    Args:
        websocket: Connected Deepgram WebSocket.
        interval_seconds: Heartbeat interval.
        stopped: Event indicating stream completion.
    """
    while not stopped.is_set():
        try:
            await asyncio.wait_for(stopped.wait(), timeout=interval_seconds)
        except TimeoutError:
            await websocket.send(json.dumps({"type": "KeepAlive"}))


async def send_audio(
    websocket: Any, path: Path, audio_config: dict[str, Any]
) -> float:
    """Stream raw PCM WAV frames in configured real-time chunks.

    Args:
        websocket: Connected Deepgram WebSocket.
        path: Validated WAV path.
        audio_config: Audio format and pacing settings.

    Returns:
        Monotonic timestamp immediately before the first chunk.
    """
    sample_rate = int(audio_config["sample_rate"])
    chunk_frames = max(
        1, round(sample_rate * int(audio_config["chunk_size_ms"]) / 1000)
    )
    realtime_pacing = bool(audio_config["realtime_pacing"])
    tail_silence_frames = round(
        sample_rate * int(audio_config.get("tail_silence_ms", 0)) / 1000
    )
    first_audio_sent_at = time.monotonic()
    sent_frames = 0
    with wave.open(str(path), "rb") as wav_file:
        frame_width = wav_file.getsampwidth() * wav_file.getnchannels()
        while True:
            chunk = wav_file.readframes(chunk_frames)
            if not chunk:
                break
            await websocket.send(chunk)
            sent_frames += len(chunk) // frame_width
            if realtime_pacing:
                target_time = first_audio_sent_at + sent_frames / sample_rate
                await asyncio.sleep(max(0.0, target_time - time.monotonic()))
        remaining_silence_frames = tail_silence_frames
        while remaining_silence_frames > 0:
            frames_to_send = min(chunk_frames, remaining_silence_frames)
            await websocket.send(bytes(frames_to_send * frame_width))
            sent_frames += frames_to_send
            remaining_silence_frames -= frames_to_send
            if realtime_pacing:
                target_time = first_audio_sent_at + sent_frames / sample_rate
                await asyncio.sleep(max(0.0, target_time - time.monotonic()))
    return first_audio_sent_at


async def transcribe_stream(
    path: Path, config: dict[str, Any], api_key: str
) -> tuple[str, StreamState, float]:
    """Transcribe one WAV through Deepgram Nova-3 streaming.

    Args:
        path: Validated WAV path.
        config: Parsed Deepgram configuration.
        api_key: Deepgram API key.

    Returns:
        Final transcript, connection state, and total processing milliseconds.
    """
    connection = config["connection"]
    websocket_url = build_websocket_url(config)
    headers = {"Authorization": f"Token {api_key}"}
    started_at = time.monotonic()
    state = StreamState(final_segments=[])
    stopped = asyncio.Event()
    finalized = asyncio.Event()
    logging.debug("Connecting to Deepgram URL: %s", websocket_url)
    ssl_context = ssl.create_default_context(cafile=certifi.where())

    async with websockets.connect(
        websocket_url,
        additional_headers=headers,
        ssl=ssl_context,
        open_timeout=float(connection["open_timeout_seconds"]),
        close_timeout=float(connection["close_timeout_seconds"]),
        max_size=int(connection["max_message_bytes"]),
    ) as websocket:
        first_audio_sent_at = time.monotonic()
        receiver = asyncio.create_task(
            receive_messages(websocket, state, first_audio_sent_at, finalized)
        )
        keepalive = asyncio.create_task(
            send_keepalive(
                websocket,
                float(connection["keepalive_interval_seconds"]),
                stopped,
            )
        )
        try:
            first_audio_sent_at = await send_audio(websocket, path, config["audio"])
            await websocket.send(json.dumps({"type": "Finalize"}))
            try:
                await asyncio.wait_for(
                    finalized.wait(),
                    timeout=float(connection["finalize_timeout_seconds"]),
                )
            except TimeoutError:
                logging.warning("Finalize response timed out for %s", path.name)
            await websocket.send(json.dumps({"type": "CloseStream"}))
            try:
                await asyncio.wait_for(
                    receiver,
                    timeout=float(connection["close_timeout_seconds"]),
                )
            except TimeoutError:
                receiver.cancel()
                await asyncio.gather(receiver, return_exceptions=True)
        finally:
            stopped.set()
            keepalive.cancel()
            await asyncio.gather(keepalive, return_exceptions=True)
            if not receiver.done():
                receiver.cancel()
                await asyncio.gather(receiver, return_exceptions=True)

    transcript = " ".join(state.final_segments).strip()
    processing_time_ms = (time.monotonic() - started_at) * 1000.0
    return transcript, state, processing_time_ms


def score_transcript(
    record: BenchmarkRecord,
    transcript: str,
    accuracy: Any,
    model: str,
    state: StreamState,
    processing_time_ms: float,
    audio_duration_ms: float,
    language: str,
) -> TestResult:
    """Score a transcript with the unchanged library_ar functions.

    Args:
        record: Source benchmark record.
        transcript: Deepgram final transcript.
        accuracy: Loaded library_ar accuracy module.
        model: Deepgram model name.
        state: Streaming metadata and latency.
        processing_time_ms: End-to-end processing duration.
        audio_duration_ms: Source audio duration.
        language: Deepgram language code used for this record.

    Returns:
        Fully scored test result.
    """
    normalized_reference = accuracy.normalize_combined(record.reference_text)
    normalized_transcript = accuracy.normalize_combined(transcript)
    char_counts = accuracy.levenshtein_counts(
        normalized_reference, normalized_transcript
    )
    reference_char_count = len(normalized_reference)
    cer = (
        char_counts.total / reference_char_count
        if reference_char_count
        else (0.0 if not normalized_transcript else 1.0)
    )
    reference_words = accuracy.normalize_combined_words(record.reference_text)
    transcript_words = accuracy.normalize_combined_words(transcript)
    word_counts = accuracy.levenshtein_counts(reference_words, transcript_words)
    reference_word_count = len(reference_words)
    wer = (
        word_counts.total / reference_word_count
        if reference_word_count
        else (0.0 if not transcript_words else 1.0)
    )
    return TestResult(
        order=record.order,
        benchmark_id=record.benchmark_id,
        audio_path=record.audio_path,
        reference_text=record.reference_text,
        transcript=transcript,
        normalized_reference=normalized_reference,
        normalized_transcript=normalized_transcript,
        char_substitutions=char_counts.substitutions,
        char_deletions=char_counts.deletions,
        char_insertions=char_counts.insertions,
        reference_char_count=reference_char_count,
        cer=cer,
        character_accuracy=1.0 - cer,
        word_substitutions=word_counts.substitutions,
        word_deletions=word_counts.deletions,
        word_insertions=word_counts.insertions,
        reference_word_count=reference_word_count,
        wer=wer,
        word_accuracy=1.0 - wer,
        first_result_latency_ms=state.first_result_latency_ms,
        processing_time_ms=processing_time_ms,
        audio_duration_ms=audio_duration_ms,
        request_id=state.request_id,
        status="success",
        error="",
        vendor=VENDOR_NAME,
        model=model,
        language=language,
    )


def result_without_score(
    record: BenchmarkRecord,
    model: str,
    status: str,
    error: str,
    transcript: str = "",
    state: StreamState | None = None,
    processing_time_ms: float | None = None,
    audio_duration_ms: float | None = None,
    language: str = "",
) -> TestResult:
    """Create a failed or skipped result without metric values.

    Args:
        record: Source benchmark record.
        model: Deepgram model name.
        status: Result status.
        error: Sanitized reason.
        transcript: Optional unscored ASR transcript.
        state: Optional streaming metadata and latency.
        processing_time_ms: Optional end-to-end processing duration.
        audio_duration_ms: Optional source audio duration.
        language: Deepgram language code selected for this record.

    Returns:
        Unscored test result.
    """
    return TestResult(
        order=record.order,
        benchmark_id=record.benchmark_id,
        audio_path=record.audio_path,
        reference_text=record.reference_text,
        transcript=transcript,
        normalized_reference="",
        normalized_transcript="",
        char_substitutions=None,
        char_deletions=None,
        char_insertions=None,
        reference_char_count=None,
        cer=None,
        character_accuracy=None,
        word_substitutions=None,
        word_deletions=None,
        word_insertions=None,
        reference_word_count=None,
        wer=None,
        word_accuracy=None,
        first_result_latency_ms=(
            state.first_result_latency_ms if state is not None else None
        ),
        processing_time_ms=processing_time_ms,
        audio_duration_ms=audio_duration_ms,
        request_id=state.request_id if state is not None else "",
        status=status,
        error=error,
        vendor=VENDOR_NAME,
        model=model,
        language=language,
    )


def language_for_record(record: BenchmarkRecord, config: dict[str, Any]) -> str:
    """Resolve the configured Deepgram language for one dialect.

    Args:
        record: Source benchmark record.
        config: Parsed Deepgram configuration.

    Returns:
        Explicit Deepgram language code.
    """
    mapping = config["batch"]["language_by_dialect"]
    return str(mapping.get(record.dialect, config["transcription"]["language"]))


async def process_record(
    record: BenchmarkRecord,
    manifest_dir: Path,
    config: dict[str, Any],
    api_key: str,
    accuracy: Any,
    semaphore: asyncio.Semaphore,
) -> TestResult:
    """Process one record without aborting the surrounding batch.

    Args:
        record: Source benchmark record.
        manifest_dir: Directory used to resolve audio paths.
        config: Parsed Deepgram configuration.
        api_key: Deepgram API key.
        accuracy: Loaded library_ar accuracy module.
        semaphore: Batch concurrency limiter.

    Returns:
        Successful, failed, or skipped result.
    """
    model = str(config["transcription"]["model"])
    language = language_for_record(record, config)
    if not record.audio_path:
        return result_without_score(
            record, model, "skipped", "Audio path is empty", language=language
        )
    audio_path = manifest_dir / record.audio_path
    if not audio_path.is_file():
        return result_without_score(
            record,
            model,
            "failed",
            f"Audio file not found: {record.audio_path}",
            language=language,
        )
    try:
        _, audio_duration_ms = validate_audio(audio_path, config["audio"])
        record_config = copy.deepcopy(config)
        record_config["transcription"]["language"] = language
        async with semaphore:
            transcript, state, processing_time_ms = await transcribe_stream(
                audio_path, record_config, api_key
            )
        if not record.reference_text:
            logging.warning(
                "%s transcribed but accuracy skipped: reference text is empty",
                record.benchmark_id,
            )
            return result_without_score(
                record,
                model,
                "skipped",
                "Reference text is empty; transcript retained without scoring",
                transcript=transcript,
                state=state,
                processing_time_ms=processing_time_ms,
                audio_duration_ms=audio_duration_ms,
                language=language,
            )
        result = score_transcript(
            record,
            transcript,
            accuracy,
            model,
            state,
            processing_time_ms,
            audio_duration_ms,
            language,
        )
        logging.info(
            "%s success char_accuracy=%.2f%% latency_ms=%s",
            record.benchmark_id,
            result.character_accuracy * 100.0,
            (
                f"{result.first_result_latency_ms:.1f}"
                if result.first_result_latency_ms is not None
                else "n/a"
            ),
        )
        return result
    except Exception as exc:
        logging.exception("%s failed", record.benchmark_id)
        return result_without_score(
            record, model, "failed", str(exc), language=language
        )


def percentile(values: list[float], quantile: float) -> float | None:
    """Calculate a nearest-rank percentile.

    Args:
        values: Numeric observations.
        quantile: Quantile from zero through one.

    Returns:
        Percentile or None for an empty collection.
    """
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * quantile)))
    return ordered[index]


def build_summary(results: list[TestResult]) -> list[dict[str, Any]]:
    """Build batch-level micro-averaged metrics.

    Args:
        results: Ordered test results.

    Returns:
        Metric/value rows for the summary sheet.
    """
    scored = [result for result in results if result.status == "success"]
    char_errors = sum(
        int(result.char_substitutions or 0)
        + int(result.char_deletions or 0)
        + int(result.char_insertions or 0)
        for result in scored
    )
    reference_chars = sum(int(result.reference_char_count or 0) for result in scored)
    word_errors = sum(
        int(result.word_substitutions or 0)
        + int(result.word_deletions or 0)
        + int(result.word_insertions or 0)
        for result in scored
    )
    reference_words = sum(int(result.reference_word_count or 0) for result in scored)
    overall_cer = char_errors / reference_chars if reference_chars else None
    overall_wer = word_errors / reference_words if reference_words else None
    latencies = [
        result.first_result_latency_ms
        for result in scored
        if result.first_result_latency_ms is not None
    ]
    rows = [
        {"metric": "total", "value": len(results)},
        {"metric": "success", "value": len(scored)},
        {
            "metric": "failed",
            "value": sum(result.status == "failed" for result in results),
        },
        {
            "metric": "skipped",
            "value": sum(result.status == "skipped" for result in results),
        },
        {
            "metric": "success_rate",
            "value": len(scored) / len(results) if results else 0.0,
        },
        {"metric": "overall_cer", "value": overall_cer},
        {
            "metric": "overall_character_accuracy",
            "value": 1.0 - overall_cer if overall_cer is not None else None,
        },
        {"metric": "overall_wer", "value": overall_wer},
        {
            "metric": "overall_word_accuracy",
            "value": 1.0 - overall_wer if overall_wer is not None else None,
        },
        {
            "metric": "average_first_result_latency_ms",
            "value": sum(latencies) / len(latencies) if latencies else None,
        },
        {
            "metric": "p95_first_result_latency_ms",
            "value": percentile(latencies, 0.95),
        },
    ]
    return rows


def column_letters(index: int) -> str:
    """Convert a one-based column index to Excel letters.

    Args:
        index: One-based column index.

    Returns:
        Excel column letters.
    """
    letters: list[str] = []
    while index:
        index, remainder = divmod(index - 1, 26)
        letters.append(chr(ord("A") + remainder))
    return "".join(reversed(letters))


def xml_text(value: Any) -> str:
    """Return XML-safe text for an inline XLSX cell.

    Args:
        value: Arbitrary cell value.

    Returns:
        Escaped XML text.
    """
    return escape(INVALID_XML_RE.sub("", str(value)))


def worksheet_xml(rows: list[dict[str, Any]]) -> str:
    """Serialize dictionary rows as a minimal XLSX worksheet.

    Args:
        rows: Homogeneous dictionaries.

    Returns:
        Worksheet XML.
    """
    headers = list(rows[0]) if rows else []
    all_rows: list[list[Any]] = [headers]
    all_rows.extend([[row.get(header) for header in headers] for row in rows])
    row_xml: list[str] = []
    for row_index, values in enumerate(all_rows, start=1):
        cells: list[str] = []
        for column_index, value in enumerate(values, start=1):
            reference = f"{column_letters(column_index)}{row_index}"
            if value is None:
                cells.append(f'<c r="{reference}"/>')
            elif isinstance(value, bool):
                cells.append(f'<c r="{reference}" t="b"><v>{int(value)}</v></c>')
            elif isinstance(value, (int, float)):
                cells.append(f'<c r="{reference}"><v>{value}</v></c>')
            else:
                cells.append(
                    f'<c r="{reference}" t="inlineStr"><is><t xml:space="preserve">'
                    f"{xml_text(value)}</t></is></c>"
                )
        row_xml.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(row_xml)}</sheetData></worksheet>'
    )


def daily_result_path(directory: Path, day: str) -> Path:
    """Return the single XLSX path used for one vendor day.

    Args:
        directory: Vendor result directory.
        day: Local calendar day formatted as YYYYMMDD.

    Returns:
        Daily result path that may be atomically replaced.
    """
    return directory / f"{day}.xlsx"


def write_xlsx(path: Path, sheets: list[tuple[str, list[dict[str, Any]]]]) -> None:
    """Write a dependency-free XLSX workbook.

    Args:
        path: Destination workbook path.
        sheets: Ordered sheet names and dictionary rows.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    content_overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index in range(1, len(sheets) + 1)
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        f"{content_overrides}</Types>"
    )
    workbook_sheets = "".join(
        f'<sheet name="{xml_text(name)}" sheetId="{index}" r:id="rId{index}"'
        f'{" state=\"hidden\"" if name == "_state" else ""}/>'
        for index, (name, _) in enumerate(sheets, start=1)
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{workbook_sheets}</sheets></workbook>"
    )
    workbook_relationships = "".join(
        '<Relationship '
        f'Id="rId{index}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        f'Target="worksheets/sheet{index}.xml"/>'
        for index in range(1, len(sheets) + 1)
    )
    root_relationships = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/></Relationships>'
    )
    temporary_path = path.with_name(f".{path.name}.tmp")
    with zipfile.ZipFile(
        temporary_path, "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_relationships)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f"{workbook_relationships}</Relationships>",
        )
        for index, (_, rows) in enumerate(sheets, start=1):
            archive.writestr(
                f"xl/worksheets/sheet{index}.xml", worksheet_xml(rows)
            )
    temporary_path.replace(path)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write dictionary rows as a UTF-8 CSV for direct VS Code viewing.

    Args:
        path: Destination CSV path.
        rows: Homogeneous dictionaries to serialize.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = list(rows[0]) if rows else []
    temporary_path = path.with_name(f".{path.name}.tmp")
    with temporary_path.open(
        "w", encoding="utf-8-sig", newline=""
    ) as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    temporary_path.replace(path)


def build_compact_csv_rows(results: list[TestResult]) -> list[dict[str, Any]]:
    """Build the fixed seven-column detail view used for CSV output.

    Args:
        results: Full batch results retained in the XLSX archive.

    Returns:
        Compact rows intended for direct inspection in VS Code.
    """
    return [
        {
            "benchmark_id": result.benchmark_id,
            "audio_path": result.audio_path,
            "annotated_text": result.reference_text,
            "transcript": result.transcript,
            "normalized_annotated_text": result.normalized_reference,
            "normalized_transcript": result.normalized_transcript,
            "wer": result.wer,
        }
        for result in results
    ]


def build_state_rows(results: list[TestResult]) -> list[dict[str, Any]]:
    """Serialize full results for the hidden daily merge state sheet.

    Args:
        results: Complete daily result set.

    Returns:
        Rows containing every TestResult field.
    """
    names = [field.name for field in fields(TestResult)]
    return [{name: getattr(result, name) for name in names} for result in results]


def load_state_rows(path: Path) -> list[TestResult]:
    """Load the hidden daily merge state from an existing workbook.

    Args:
        path: Daily XLSX path.

    Returns:
        Previously stored full results, or an empty list for a new day.

    Raises:
        RuntimeError: If an existing daily workbook has no merge state.
    """
    if not path.exists():
        return []
    sheet_path = "xl/worksheets/sheet4.xml"
    with zipfile.ZipFile(path) as archive:
        if sheet_path not in archive.namelist():
            raise RuntimeError(
                f"Existing daily workbook has no merge state: {path}"
            )
        root = ET.fromstring(archive.read(sheet_path))
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    matrix: list[list[Any]] = []
    for row in root.findall(".//x:sheetData/x:row", namespace):
        values: list[Any] = []
        for cell in row.findall("x:c", namespace):
            cell_type = cell.get("t")
            if cell_type == "inlineStr":
                values.append(
                    "".join(
                        node.text or ""
                        for node in cell.findall(".//x:t", namespace)
                    )
                )
            else:
                value = cell.find("x:v", namespace)
                if value is None:
                    values.append(None)
                elif cell_type == "b":
                    values.append(value.text == "1")
                else:
                    values.append(float(value.text))
        matrix.append(values)
    if len(matrix) <= 1:
        return []
    headers = [str(value) for value in matrix[0]]
    integer_fields = {
        "order",
        "char_substitutions",
        "char_deletions",
        "char_insertions",
        "reference_char_count",
        "word_substitutions",
        "word_deletions",
        "word_insertions",
        "reference_word_count",
    }
    results: list[TestResult] = []
    for values in matrix[1:]:
        row = dict(zip(headers, values))
        for name in integer_fields:
            if row.get(name) is not None:
                row[name] = int(row[name])
        results.append(TestResult(**row))
    return results


def merge_daily_results(
    previous: list[TestResult], current: list[TestResult]
) -> list[TestResult]:
    """Append new IDs and replace repeated IDs with their latest result.

    Args:
        previous: Results already stored for the day.
        current: Results produced by the latest run.

    Returns:
        Deduplicated daily results in manifest order.
    """
    merged = {result.benchmark_id: result for result in previous}
    merged.update({result.benchmark_id: result for result in current})
    return sorted(merged.values(), key=lambda result: result.order)


def save_result_files(
    result_path: Path,
    results: list[TestResult],
    metadata_rows: list[dict[str, Any]],
) -> None:
    """Atomically save the daily XLSX and its two CSV views.

    Args:
        result_path: Daily XLSX destination.
        results: Complete merged daily results.
        metadata_rows: Workbook run metadata rows.
    """
    detail_rows = build_compact_csv_rows(results)
    summary_rows = build_summary(results)
    write_xlsx(
        result_path,
        [
            ("details", detail_rows),
            ("summary", summary_rows),
            ("run_metadata", metadata_rows),
            ("_state", build_state_rows(results)),
        ],
    )
    write_csv(result_path.with_suffix(".csv"), detail_rows)
    write_csv(
        result_path.with_name(f"{result_path.stem}_summary.csv"), summary_rows
    )


def setup_logging(timestamp: str) -> Path:
    """Configure console and file logging for a batch run.

    Args:
        timestamp: Batch timestamp.

    Returns:
        Created log path.
    """
    logs_dir = Path(__file__).resolve().parent / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"batch_library_ar_{timestamp}.log"
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


def validate_dataset(
    records: list[BenchmarkRecord], manifest_dir: Path, config: dict[str, Any]
) -> tuple[int, int]:
    """Validate all referenced WAV files without API calls.

    Args:
        records: Benchmark records.
        manifest_dir: Manifest directory.
        config: Parsed configuration.

    Returns:
        Counts of runnable and skipped records.

    Raises:
        ValueError: If a referenced WAV is missing or malformed.
    """
    runnable = 0
    skipped = 0
    for record in records:
        if not record.audio_path:
            skipped += 1
            continue
        audio_path = manifest_dir / record.audio_path
        if not audio_path.is_file():
            raise ValueError(f"Audio file not found: {record.audio_path}")
        validate_audio(audio_path, config["audio"])
        runnable += 1
    return runnable, skipped


async def run_batch(
    records: list[BenchmarkRecord],
    manifest_path: Path,
    config: dict[str, Any],
    api_key: str,
    limit: int | None,
    benchmark_ids: Sequence[str] | None,
    checkpoint: Callable[[list[TestResult]], None] | None = None,
) -> list[TestResult]:
    """Run ordered Deepgram streaming tests with bounded concurrency.

    Args:
        records: Source benchmark records.
        manifest_path: Benchmark manifest path.
        config: Parsed configuration.
        api_key: Deepgram API key.
        limit: Optional number of records to process.
        benchmark_ids: Optional explicit Benchmark IDs.
        checkpoint: Optional callback invoked every 25 completed records.

    Returns:
        Results sorted by manifest order.
    """
    selected = records
    if benchmark_ids:
        requested = set(benchmark_ids)
        selected = [record for record in records if record.benchmark_id in requested]
        found = {record.benchmark_id for record in selected}
        missing = sorted(requested - found)
        if missing:
            raise ValueError(f"Benchmark IDs not found: {', '.join(missing)}")
    if limit is not None:
        selected = selected[:limit]
    accuracy = load_accuracy_module()
    semaphore = asyncio.Semaphore(int(config["batch"]["concurrency"]))
    tasks = [
        asyncio.create_task(
            process_record(
                record,
                manifest_path.parent,
                config,
                api_key,
                accuracy,
                semaphore,
            )
        )
        for record in selected
    ]
    results: list[TestResult] = []
    for completed, task in enumerate(asyncio.as_completed(tasks), start=1):
        result = await task
        results.append(result)
        logging.info("Progress %d/%d", completed, len(tasks))
        if checkpoint is not None and (
            completed % 25 == 0 or completed == len(tasks)
        ):
            checkpoint(sorted(results, key=lambda item: item.order))
    return sorted(results, key=lambda item: item.order)


def build_parser() -> argparse.ArgumentParser:
    """Build the batch-test command-line parser.

    Returns:
        Configured argument parser.
    """
    parser = argparse.ArgumentParser(
        description="Batch-test Arabic ASR with Deepgram Nova-3 streaming"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Deepgram JSON config path",
    )
    parser.add_argument(
        "--limit", type=int, help="Process only the first N manifest rows"
    )
    parser.add_argument(
        "--benchmark-id",
        action="append",
        help="Process one Benchmark ID; repeat for multiple IDs",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate config, manifest, and WAV files without API calls",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run validation or update the current daily Deepgram result set.

    Args:
        argv: Optional command-line arguments.

    Returns:
        Process exit code.
    """
    args = build_parser().parse_args(argv)
    config = load_json(args.config.resolve())
    validate_config(config)
    manifest_path, records = load_manifest(config)
    runnable, skipped = validate_dataset(records, manifest_path.parent, config)
    if args.validate_only:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
        logging.info(
            "Validation passed: records=%d runnable=%d skipped=%d",
            len(records),
            runnable,
            skipped,
        )
        return 0

    load_dotenv(ROOT_DIR / ".env")
    api_key_env = str(config.get("api_key_env", "DEEPGRAM_API_KEY"))
    api_key = os.environ.get(api_key_env, "")
    if not api_key:
        raise RuntimeError(f"Missing API key environment variable: {api_key_env}")

    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    day = now.strftime("%Y%m%d")
    log_path = setup_logging(timestamp)
    results_dir = resolve_project_path(str(config["batch"]["results_directory"]))
    result_path = daily_result_path(results_dir, day)
    previous_results = load_state_rows(result_path)
    logging.info(
        "Starting Deepgram batch model=%s language=%s runnable=%d skipped=%d",
        config["transcription"]["model"],
        config["transcription"]["language"],
        runnable,
        skipped,
    )
    started_at = datetime.now().astimezone()

    def save_checkpoint(partial_results: list[TestResult]) -> None:
        """Persist completed records without waiting for the whole batch."""
        merged = merge_daily_results(previous_results, partial_results)
        save_result_files(
            result_path,
            merged,
            [
                {"key": "vendor", "value": VENDOR_NAME},
                {"key": "model", "value": config["transcription"]["model"]},
                {"key": "library", "value": config["batch"]["library"]},
                {"key": "run_status", "value": "in_progress"},
                {"key": "started_at", "value": started_at.isoformat()},
                {"key": "daily_record_count", "value": len(merged)},
                {"key": "checkpoint_record_count", "value": len(partial_results)},
            ],
        )

    current_results = asyncio.run(
        run_batch(
            records,
            manifest_path,
            config,
            api_key,
            args.limit,
            args.benchmark_id,
            save_checkpoint,
        )
    )
    results = merge_daily_results(previous_results, current_results)
    finished_at = datetime.now().astimezone()

    metadata_rows = [
        {"key": "vendor", "value": VENDOR_NAME},
        {"key": "model", "value": config["transcription"]["model"]},
        {"key": "language", "value": config["transcription"]["language"]},
        {"key": "library", "value": config["batch"]["library"]},
        {"key": "manifest", "value": str(manifest_path.relative_to(ROOT_DIR))},
        {"key": "started_at", "value": started_at.isoformat()},
        {"key": "finished_at", "value": finished_at.isoformat()},
        {"key": "daily_record_count", "value": len(results)},
        {"key": "latest_run_record_count", "value": len(current_results)},
        {"key": "config", "value": json.dumps(config, ensure_ascii=False)},
        {
            "key": "accuracy_script",
            "value": str(ACCURACY_SCRIPT_PATH.relative_to(ROOT_DIR)),
        },
    ]
    save_result_files(result_path, results, metadata_rows)
    detail_csv_path = result_path.with_suffix(".csv")
    summary_csv_path = result_path.with_name(f"{result_path.stem}_summary.csv")
    logging.info("Results saved: %s", result_path)
    logging.info("CSV details saved: %s", detail_csv_path)
    logging.info("CSV summary saved: %s", summary_csv_path)
    logging.info("Log saved: %s", log_path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        logging.warning("Batch test interrupted by user")
        raise SystemExit(130) from None
    except Exception:
        logging.exception("Deepgram batch test failed")
        raise SystemExit(1) from None
