"""Call history persistence and retention contract tests."""

from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest

from src.history.models import HistoryTurn, TurnMetric
from src.history.recording import AudioRecorder
from src.history.storage import HistoryStore


@pytest.mark.asyncio
async def test_history_crud_persists_across_store_instances(tmp_path: Path) -> None:
    """A completed call should remain queryable and cascade-delete cleanly."""
    store = HistoryStore(tmp_path)
    await store.initialize()
    await store.start_call(
        call_id="call-1",
        bot_id="bot-1",
        bot_name="Gemini bot",
        llm_provider="google_gemini",
        llm_model="gemini-2.5-flash-lite",
        asr_provider="deepgram_flux",
        asr_model="flux-general-en",
        language="en",
        sample_rate=16000,
        channels=1,
    )
    recording = store.recordings_dir / "random.flac"
    recording.write_bytes(b"safe-test-audio")
    await store.finish_call(
        call_id="call-1",
        status="completed",
        duration_ms=1234.5,
        turns=[HistoryTurn(sequence=0, role="user", text="hello", created_ms=100)],
        metrics=[
            TurnMetric(
                turn_index=0,
                llm_first_token_ms=150,
                reasoning_tokens=0,
                reasoning_status="confirmed_off",
                reasoning_control="thinking_budget=0",
            )
        ],
        recording_path=recording,
        recording_status="available",
    )

    restarted = HistoryStore(tmp_path)
    await restarted.initialize()
    page = await restarted.list_calls(limit=10, offset=0)
    detail = await restarted.get_call("call-1")
    assert page.total == 1
    assert detail is not None
    assert detail.turns[0].text == "hello"
    assert detail.metrics[0].reasoning_status == "confirmed_off"
    assert await restarted.recording_path("call-1") == recording

    assert await restarted.delete_call("call-1") is True
    assert await restarted.get_call("call-1") is None
    assert not recording.exists()


@pytest.mark.asyncio
async def test_cleanup_is_idempotent_on_empty_store(tmp_path: Path) -> None:
    """Repeated retention passes should be safe when there is no history."""
    store = HistoryStore(tmp_path)
    await store.initialize()
    await store.cleanup()
    await store.cleanup()
    assert (await store.list_calls(limit=10, offset=0)).total == 0


@pytest.mark.asyncio
async def test_legacy_metric_column_order_is_migrated_safely(tmp_path: Path) -> None:
    """Explicit column writes must support databases migrated from the old schema."""
    database_path = tmp_path / "history.db"
    async with aiosqlite.connect(database_path) as database:
        await database.execute(
            """CREATE TABLE turn_metrics (
                   call_id TEXT NOT NULL,
                   turn_index INTEGER NOT NULL,
                   llm_first_token_ms REAL,
                   tts_first_audio_ms REAL,
                   server_to_playback_ms REAL,
                   turn_to_playback_ms REAL,
                   reasoning_tokens INTEGER,
                   reasoning_status TEXT NOT NULL,
                   reasoning_control TEXT,
                   PRIMARY KEY (call_id, turn_index)
               )"""
        )
        await database.commit()

    store = HistoryStore(tmp_path)
    await store.initialize()
    await store.start_call(
        call_id="legacy-call",
        bot_id=None,
        bot_name=None,
        llm_provider="custom",
        llm_model="gemini-3.5-flash-lite",
        asr_provider="deepgram_flux",
        asr_model="flux-general-en",
        language="en",
        sample_rate=16000,
        channels=1,
    )
    await store.finish_call(
        call_id="legacy-call",
        status="completed",
        duration_ms=500,
        turns=[],
        metrics=[
            TurnMetric(
                turn_index=0,
                asr_final_latency_ms=10,
                llm_request_splicing_ms=20,
                llm_first_token_ms=30,
                tts_initial_ms=40,
                tts_first_audio_ms=50,
                playback_ms=60,
                turn_to_playback_ms=210,
                reasoning_status="unverified",
            )
        ],
        recording_path=None,
        recording_status="unavailable",
    )

    detail = await store.get_call("legacy-call")
    assert detail is not None
    assert detail.status == "completed"
    assert detail.metrics[0].asr_final_latency_ms == 10
    assert detail.metrics[0].reasoning_status == "unverified"


@pytest.mark.asyncio
async def test_initialize_marks_abandoned_pending_calls_failed(tmp_path: Path) -> None:
    """A restart must not leave calls permanently pending when finalization was interrupted."""
    store = HistoryStore(tmp_path)
    await store.initialize()
    await store.start_call(
        call_id="abandoned-call",
        bot_id=None,
        bot_name=None,
        llm_provider="custom",
        llm_model="model",
        asr_provider="deepgram_flux",
        asr_model="flux-general-en",
        language="en",
        sample_rate=16000,
        channels=1,
    )

    restarted = HistoryStore(tmp_path)
    await restarted.initialize()
    detail = await restarted.get_call("abandoned-call")
    assert detail is not None
    assert detail.status == "failed"
    assert detail.error_category == "session_interrupted"


@pytest.mark.asyncio
async def test_audio_recorder_writes_flac_and_degrades_on_overflow(tmp_path: Path) -> None:
    """Recording failures should not block or leave a misleading partial file."""
    good = AudioRecorder(tmp_path / "good.flac", sample_rate=16000)
    await good.start()
    good.push(bytes(320))
    await good.stop()
    assert good.status == "available"
    assert good.path.read_bytes().startswith(b"fLaC")

    overflow = AudioRecorder(tmp_path / "overflow.flac", sample_rate=16000, max_chunks=1)
    await overflow.start()
    overflow.push(bytes(320))
    overflow.push(bytes(320))
    await overflow.stop()
    assert overflow.status == "failed"
    assert overflow.error == "recording_queue_overflow"
    assert not overflow.path.exists()
