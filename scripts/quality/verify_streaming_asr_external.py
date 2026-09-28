#!/usr/bin/env python3
"""Run one explicitly authorized external-real ASR stream through production adapters."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
import wave
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pipecat.frames.frames import (
    ErrorFrame,
    InputAudioRawFrame,
    InterimTranscriptionFrame,
    ProposedUserStoppedSpeakingFrame,
    TranscriptionFrame,
)
from pipecat.pipeline import worker as pipecat_worker
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker, ProcessorUnusablePolicy
from pipecat.workers.runner import WorkerRunner

from src.asr import ASRService, create_default_asr_registry
from src.config import AudioConfig

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AUTHORIZATION_ID = "D-017"
MAX_AUDIO_SECONDS = 60.0
CHUNK_MILLISECONDS = 20


@dataclass(frozen=True, slots=True)
class ProviderSelection:
    """Describe one frozen production provider/model selection."""

    provider: str
    model: str
    turn_detection_source: str
    key_environment_variable: str
    options: dict[str, Any]
    opening_script: str = ""
    context_update: str = ""


@dataclass(slots=True)
class StreamEvidence:
    """Store secret-free evidence from one external-real stream."""

    provider: str
    model: str
    language: str
    audio_seconds: float
    submitted_seconds: float = 0.0
    interim_count: int = 0
    final_transcripts: list[str] = field(default_factory=list)
    turn_proposals: int = 0
    first_result_latency_ms: float | None = None
    turn_latency_ms: float | None = None
    context_applied: bool | None = None
    error_categories: list[str] = field(default_factory=list)
    status: str = "pending"


class ExternalVerificationError(RuntimeError):
    """Represent a safe, non-secret external verification failure."""


def provider_selection(provider: str, language: str) -> ProviderSelection:
    """Build the production selection used by one external-real probe.

    Args:
        provider: CLI provider identifier.
        language: Provider-compatible language code.

    Returns:
        Frozen provider/model selection.

    Raises:
        ValueError: If the provider identifier is unsupported.
    """
    if provider == "speechmatics":
        return ProviderSelection(
            provider="speechmatics",
            model="enhanced",
            turn_detection_source="provider_native",
            key_environment_variable="SPEECHMATICS_API_KEY",
            options={"language": language, "emit_sentences": True},
        )
    if provider == "soniox":
        return ProviderSelection(
            provider="soniox",
            model="stt-rt-v5",
            turn_detection_source="provider_native",
            key_environment_variable="SONIOX_API_KEY",
            options={"language_hints": [language]},
        )
    if provider == "assemblyai":
        return ProviderSelection(
            provider="assemblyai",
            model="universal-3-5-pro",
            turn_detection_source="provider_native",
            key_environment_variable="ASSEMBLYAI_API_KEY",
            options={"language_codes": [language], "agent_context_enabled": True},
            opening_script="The caller is testing a synthetic voice assistant session.",
            context_update="The assistant confirmed this is synthetic verification audio.",
        )
    if provider == "deepgram-nova3":
        return ProviderSelection(
            provider="deepgram",
            model="nova-3",
            turn_detection_source="off",
            key_environment_variable="DEEPGRAM_API_KEY",
            options={"language": language, "endpointing_ms": 300},
        )
    raise ValueError(f"Unsupported external-real provider: {provider}")


def load_pcm_wave(path: Path, *, tail_silence_seconds: float) -> tuple[bytes, float, float]:
    """Load and validate the exact audio bytes that will leave the machine.

    Args:
        path: Local synthetic WAV file.
        tail_silence_seconds: Silence appended to exercise provider endpointing.

    Returns:
        PCM bytes, source duration, and submitted duration.

    Raises:
        ExternalVerificationError: If format or duration violates authorization.
    """
    if tail_silence_seconds < 0 or tail_silence_seconds > 5:
        raise ExternalVerificationError("Tail silence must be between 0 and 5 seconds")
    try:
        with wave.open(str(path), "rb") as audio_file:
            channels = audio_file.getnchannels()
            sample_width = audio_file.getsampwidth()
            sample_rate = audio_file.getframerate()
            frame_count = audio_file.getnframes()
            compression = audio_file.getcomptype()
            audio = audio_file.readframes(frame_count)
    except (OSError, wave.Error) as exc:
        raise ExternalVerificationError("Audio must be a readable PCM WAV file") from exc
    if (channels, sample_width, sample_rate, compression) != (1, 2, 16000, "NONE"):
        raise ExternalVerificationError("Audio must be mono 16-bit 16 kHz uncompressed PCM WAV")
    source_seconds = frame_count / sample_rate
    submitted_seconds = source_seconds + tail_silence_seconds
    if source_seconds <= 0 or submitted_seconds > MAX_AUDIO_SECONDS:
        raise ExternalVerificationError(
            "Submitted audio must be greater than 0 and at most 60 seconds"
        )
    silence = bytes(round(tail_silence_seconds * sample_rate) * sample_width)
    return audio + silence, source_seconds, submitted_seconds


def _safe_error_category(frame: ErrorFrame) -> str:
    """Return a bounded error label without persisting upstream response text."""
    if frame.category is not None:
        return str(getattr(frame.category, "value", frame.category))
    if frame.processor is not None and not frame.processor.is_usable:
        return "processor_unusable"
    return "unknown_provider_error"


async def run_stream(
    *,
    selection: ProviderSelection,
    language: str,
    api_key: str,
    pcm_audio: bytes,
    source_seconds: float,
    submitted_seconds: float,
    result_timeout_seconds: float,
) -> StreamEvidence:
    """Run one production adapter stream and return secret-free evidence.

    Args:
        selection: Validated provider/model selection.
        language: Language code recorded in evidence.
        api_key: Provider credential retained only in memory.
        pcm_audio: Authorized PCM bytes including trailing silence.
        source_seconds: Source audio duration.
        submitted_seconds: Total duration sent to the provider.
        result_timeout_seconds: Maximum post-audio wait for a Turn boundary.

    Returns:
        Secret-free stream evidence.
    """
    service: ASRService = create_default_asr_registry().create(
        provider=selection.provider,
        model=selection.model,
        turn_detection_source=selection.turn_detection_source,
        options=selection.options,
        api_key=api_key,
        audio=AudioConfig(),
        opening_script=selection.opening_script,
    )
    # This ASR-only verifier never tokenizes LLM/TTS text. The production image
    # bundles punkt_tab; skipping its unrelated warmup prevents local test egress.
    pipecat_worker.warm_deferred_imports = lambda: None
    evidence = StreamEvidence(
        provider=selection.provider,
        model=selection.model,
        language=language,
        audio_seconds=round(source_seconds, 3),
        submitted_seconds=round(submitted_seconds, 3),
    )
    turn_event = asyncio.Event()
    error_event = asyncio.Event()
    first_audio_at: float | None = None
    feeder_error: Exception | None = None
    seen_frames: set[int] = set()

    pipeline = Pipeline([service.processor])
    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(audio_in_sample_rate=16000, audio_out_sample_rate=24000),
        enable_rtvi=False,
        enable_turn_tracking=False,
        idle_timeout_secs=None,
        processor_unusable_policy=ProcessorUnusablePolicy.END,
    )
    observed = (TranscriptionFrame, InterimTranscriptionFrame, ProposedUserStoppedSpeakingFrame)
    worker.set_reached_downstream_filter(observed)

    async def capture_frame(_worker: PipelineWorker, frame: Any) -> None:
        """Capture each observed frame once even when it is broadcast both ways."""
        nonlocal first_audio_at
        if frame.id in seen_frames:
            return
        seen_frames.add(frame.id)
        now = time.monotonic()
        if isinstance(frame, InterimTranscriptionFrame):
            evidence.interim_count += 1
            if evidence.first_result_latency_ms is None and first_audio_at is not None:
                evidence.first_result_latency_ms = round((now - first_audio_at) * 1000, 1)
        elif isinstance(frame, TranscriptionFrame):
            if frame.text.strip():
                evidence.final_transcripts.append(frame.text.strip())
            if evidence.first_result_latency_ms is None and first_audio_at is not None:
                evidence.first_result_latency_ms = round((now - first_audio_at) * 1000, 1)
        elif isinstance(frame, ProposedUserStoppedSpeakingFrame):
            evidence.turn_proposals += 1
            if first_audio_at is not None:
                evidence.turn_latency_ms = round((now - first_audio_at) * 1000, 1)
            turn_event.set()

    async def capture_error(_worker: PipelineWorker, frame: ErrorFrame) -> None:
        """Capture only normalized error categories and trigger the stop rule."""
        evidence.error_categories.append(_safe_error_category(frame))
        error_event.set()

    worker.event_handler("on_frame_reached_downstream")(capture_frame)
    worker.event_handler("on_pipeline_error")(capture_error)

    async def feed_audio() -> None:
        """Send real-time chunks, then wait for either one Turn or one error."""
        nonlocal feeder_error, first_audio_at
        try:
            if selection.context_update:
                await service.update_agent_context(selection.context_update)
                evidence.context_applied = True
            chunk_bytes = int(16000 * 2 * CHUNK_MILLISECONDS / 1000)
            first_audio_at = time.monotonic()
            for offset in range(0, len(pcm_audio), chunk_bytes):
                chunk = pcm_audio[offset : offset + chunk_bytes]
                await worker.queue_frame(
                    InputAudioRawFrame(audio=chunk, sample_rate=16000, num_channels=1)
                )
                await asyncio.sleep(len(chunk) / (16000 * 2))

            turn_wait = asyncio.create_task(turn_event.wait())
            error_wait = asyncio.create_task(error_event.wait())
            done, pending = await asyncio.wait(
                {turn_wait, error_wait},
                timeout=result_timeout_seconds,
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            if not done:
                raise ExternalVerificationError("Provider did not emit a Turn before timeout")
            if error_event.is_set():
                raise ExternalVerificationError("Provider emitted an error; stop rule activated")
            if not evidence.final_transcripts:
                raise ExternalVerificationError(
                    "Provider emitted a Turn without final transcript text"
                )
            if evidence.turn_proposals != 1:
                raise ExternalVerificationError(
                    f"Expected exactly one Turn proposal, received {evidence.turn_proposals}"
                )
            evidence.status = "pass"
        except Exception as exc:
            feeder_error = exc
            evidence.status = "failed"
            if selection.context_update and evidence.context_applied is None:
                evidence.context_applied = False
        finally:
            await worker.stop_when_done()

    feeder_task: asyncio.Task[None] | None = None

    async def start_feeder(_worker: PipelineWorker, _frame: Any) -> None:
        """Start feeding only after provider setup and StartFrame completion."""
        nonlocal feeder_task
        feeder_task = asyncio.create_task(feed_audio())

    worker.event_handler("on_pipeline_started")(start_feeder)
    runner = WorkerRunner(handle_sigint=False, handle_sigterm=False)
    await runner.add_workers(worker)
    await asyncio.wait_for(runner.run(), timeout=submitted_seconds + result_timeout_seconds + 30)
    if feeder_task is not None:
        await feeder_task
    if feeder_error is not None:
        raise ExternalVerificationError(str(feeder_error)) from feeder_error
    return evidence


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments with an explicit external-call authorization guard."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provider",
        required=True,
        choices=("speechmatics", "soniox", "assemblyai", "deepgram-nova3"),
    )
    parser.add_argument("--language", required=True)
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--authorization-id", required=True)
    parser.add_argument("--result-json", required=True, type=Path)
    parser.add_argument("--tail-silence-seconds", type=float, default=2.0)
    parser.add_argument("--result-timeout-seconds", type=float, default=15.0)
    return parser.parse_args()


async def async_main(args: argparse.Namespace) -> int:
    """Validate authorization and run exactly one provider call."""
    if args.authorization_id != AUTHORIZATION_ID:
        raise ExternalVerificationError(
            f"External call requires recorded authorization {AUTHORIZATION_ID}"
        )
    if args.result_json.exists():
        raise ExternalVerificationError("Refusing to overwrite existing external-call evidence")
    selection = provider_selection(args.provider, args.language)
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.getenv(selection.key_environment_variable, "")
    if not api_key:
        raise ExternalVerificationError(
            f"{selection.key_environment_variable} is not configured locally"
        )
    pcm_audio, source_seconds, submitted_seconds = load_pcm_wave(
        args.audio, tail_silence_seconds=args.tail_silence_seconds
    )
    evidence = await run_stream(
        selection=selection,
        language=args.language,
        api_key=api_key,
        pcm_audio=pcm_audio,
        source_seconds=source_seconds,
        submitted_seconds=submitted_seconds,
        result_timeout_seconds=args.result_timeout_seconds,
    )
    args.result_json.parent.mkdir(parents=True, exist_ok=True)
    args.result_json.write_text(
        json.dumps(asdict(evidence), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(asdict(evidence), ensure_ascii=False))
    return 0


def main() -> int:
    """Run the guarded external-real verifier."""
    try:
        return asyncio.run(async_main(parse_args()))
    except ExternalVerificationError as exc:
        print(f"EXTERNAL VERIFICATION STOPPED: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
