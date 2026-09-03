"""Call history persistence and retention contract tests."""

from __future__ import annotations

from pathlib import Path

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
