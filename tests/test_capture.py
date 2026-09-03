"""Tests for the non-blocking call history capture."""

from __future__ import annotations

import pytest
from pipecat.frames.frames import (
    LLMContextFrame,
    LLMFullResponseEndFrame,
    LLMTextFrame,
    TranscriptionFrame,
    TTSAudioRawFrame,
    TTSStartedFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)

from src.history.capture import CallCapture


@pytest.fixture
def capture() -> CallCapture:
    """Return a fresh capture with a known provider/model."""
    return CallCapture(provider="google_gemini", model="gemini-2.5-flash-lite")


def _simulate_single_turn(capture: CallCapture) -> None:
    """Replay one complete user/agent turn through the capture."""
    capture.observe(UserStartedSpeakingFrame())
    capture.observe(UserStoppedSpeakingFrame())
    capture.observe(TranscriptionFrame(text="Hello.", user_id="user", timestamp="0"))
    capture.observe(LLMContextFrame(context={}))
    capture.observe(LLMTextFrame("Hello! "))
    capture.observe(LLMTextFrame("How can I help you today?"))
    capture.observe(LLMFullResponseEndFrame())
    capture.observe(TTSStartedFrame())
    capture.observe(TTSAudioRawFrame(b"audio", sample_rate=16000, num_channels=1))
    capture.browser_event("first_playback", 0.0)


def test_single_turn_produces_one_metric(capture: CallCapture) -> None:
    """A normal single utterance should yield exactly one turn metric."""
    _simulate_single_turn(capture)
    turns, metrics = capture.finalize()

    assert len(turns) == 2
    assert turns[0].role == "user"
    assert turns[0].text == "Hello."
    assert turns[1].role == "assistant"
    assert "How can I help you today?" in turns[1].text
    assert len(metrics) == 1
    metric = metrics[0]
    assert metric.turn_index == 0
    assert metric.asr_final_latency_ms is not None
    assert metric.llm_request_splicing_ms is not None
    assert metric.llm_first_token_ms is not None
    assert metric.tts_initial_ms is not None
    assert metric.tts_first_audio_ms is not None
    assert metric.playback_ms is not None
    assert metric.turn_to_playback_ms is not None
    # Breakdown chain must sum to the end-to-end latency.
    assert (
        round(
            metric.asr_final_latency_ms
            + metric.llm_request_splicing_ms
            + metric.llm_first_token_ms
            + metric.tts_initial_ms
            + metric.tts_first_audio_ms
            + metric.playback_ms,
            1,
        )
        == metric.turn_to_playback_ms
    )


def test_duplicate_vad_stops_do_not_create_ghost_turns(capture: CallCapture) -> None:
    """Multiple UserStoppedSpeakingFrame events for one utterance must not become extra metrics."""
    capture.observe(UserStartedSpeakingFrame())
    capture.observe(UserStoppedSpeakingFrame())
    capture.observe(UserStoppedSpeakingFrame())  # Spurious duplicate stop.
    capture.observe(TranscriptionFrame(text="Hello.", user_id="user", timestamp="0"))
    capture.observe(LLMContextFrame(context={}))
    capture.observe(LLMTextFrame("Hello! How can I help you today?"))
    capture.observe(LLMFullResponseEndFrame())
    capture.observe(TTSStartedFrame())
    capture.observe(TTSAudioRawFrame(b"audio", sample_rate=16000, num_channels=1))
    capture.browser_event("first_playback", 0.0)

    turns, metrics = capture.finalize()

    assert len(turns) == 2
    assert len(metrics) == 1
    metric = metrics[0]
    assert metric.llm_first_token_ms is not None
    assert metric.tts_first_audio_ms is not None
    assert metric.turn_to_playback_ms is not None
    assert (
        round(
            metric.asr_final_latency_ms
            + metric.llm_request_splicing_ms
            + metric.llm_first_token_ms
            + metric.tts_initial_ms
            + metric.tts_first_audio_ms
            + metric.playback_ms,
            1,
        )
        == metric.turn_to_playback_ms
    )


def test_two_distinct_utterances_produce_two_metrics(capture: CallCapture) -> None:
    """Two real user turns separated by VAD boundaries should each get a metric."""
    # First turn.
    capture.observe(UserStartedSpeakingFrame())
    capture.observe(UserStoppedSpeakingFrame())
    capture.observe(TranscriptionFrame(text="Hello.", user_id="user", timestamp="0"))
    capture.observe(LLMContextFrame(context={}))
    capture.observe(LLMTextFrame("Hi there."))
    capture.observe(LLMFullResponseEndFrame())
    capture.observe(TTSStartedFrame())
    capture.observe(TTSAudioRawFrame(b"audio1", sample_rate=16000, num_channels=1))

    # Second turn.
    capture.observe(UserStartedSpeakingFrame())
    capture.observe(UserStoppedSpeakingFrame())
    capture.observe(TranscriptionFrame(text="Help.", user_id="user", timestamp="1"))
    capture.observe(LLMContextFrame(context={}))
    capture.observe(LLMTextFrame("Sure."))
    capture.observe(LLMFullResponseEndFrame())
    capture.observe(TTSStartedFrame())
    capture.observe(TTSAudioRawFrame(b"audio2", sample_rate=16000, num_channels=1))

    turns, metrics = capture.finalize()

    user_turns = [t for t in turns if t.role == "user"]
    assert len(user_turns) == 2
    assert len(metrics) == 2
    assert metrics[0].turn_index == 0
    assert metrics[1].turn_index == 1


def test_opening_script_tts_does_not_create_user_turn(capture: CallCapture) -> None:
    """Assistant-only audio before the user speaks must not be counted as a user turn."""
    capture.observe(TTSStartedFrame())
    capture.observe(TTSAudioRawFrame(b"opening", sample_rate=16000, num_channels=1))
    capture.observe(UserStartedSpeakingFrame())
    capture.observe(UserStoppedSpeakingFrame())
    capture.observe(TranscriptionFrame(text="Hello.", user_id="user", timestamp="0"))
    capture.observe(LLMContextFrame(context={}))
    capture.observe(LLMTextFrame("Hello!"))
    capture.observe(LLMFullResponseEndFrame())
    capture.observe(TTSStartedFrame())
    capture.observe(TTSAudioRawFrame(b"response", sample_rate=16000, num_channels=1))

    turns, metrics = capture.finalize()

    assert len([t for t in turns if t.role == "user"]) == 1
    assert len(metrics) == 1
    assert metrics[0].turn_index == 0


def test_latency_chain_sums_to_e2e(capture: CallCapture, monkeypatch: pytest.MonkeyPatch) -> None:
    """The full breakdown must telescope exactly to turn_to_playback_ms."""
    capture.started = 0.0
    # Timestamps for: user_start, user_stop, asr_final, llm_request, llm_first,
    # LLM end, tts_start, tts_audio, browser_playback, finalize.
    ticks = [0.100, 0.200, 0.300, 0.310, 0.320, 0.330, 0.340, 0.350, 0.360, 0.370]
    tick_iter = iter(ticks)
    monkeypatch.setattr("time.monotonic", lambda: next(tick_iter))

    capture.observe(UserStartedSpeakingFrame())
    capture.observe(UserStoppedSpeakingFrame())
    capture.observe(TranscriptionFrame(text="Hello.", user_id="user", timestamp="0"))
    capture.observe(LLMContextFrame(context={}))
    capture.observe(LLMTextFrame("Hello!"))
    capture.observe(LLMFullResponseEndFrame())
    capture.observe(TTSStartedFrame())
    capture.observe(TTSAudioRawFrame(b"audio", sample_rate=16000, num_channels=1))
    capture.browser_event("first_playback", 0.0)

    turns, metrics = capture.finalize()

    assert len(metrics) == 1
    metric = metrics[0]
    assert metric.asr_final_latency_ms == 100.0  # 0.300 - 0.200
    assert metric.llm_request_splicing_ms == 10.0  # 0.310 - 0.300
    assert metric.llm_first_token_ms == 10.0  # 0.320 - 0.310
    assert metric.tts_initial_ms == 20.0  # 0.340 - 0.320 (LLM end at 0.330)
    assert metric.tts_first_audio_ms == 10.0  # 0.350 - 0.340
    assert metric.playback_ms == 10.0  # 0.360 - 0.350
    assert metric.turn_to_playback_ms == 160.0  # sum of breakdown


def test_llm_first_token_is_from_llm_request_not_asr_final(
    capture: CallCapture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """llm_first_token_ms measures LLM request to first token, not ASR final to first token."""
    capture.started = 0.0
    ticks = [0.100, 0.200, 0.300, 0.310, 0.320, 0.330, 0.340]
    tick_iter = iter(ticks)
    monkeypatch.setattr("time.monotonic", lambda: next(tick_iter))

    capture.observe(UserStartedSpeakingFrame())
    capture.observe(UserStoppedSpeakingFrame())
    capture.observe(TranscriptionFrame(text="Hello.", user_id="user", timestamp="0"))
    capture.observe(LLMContextFrame(context={}))
    capture.observe(LLMTextFrame("Hello!"))
    capture.observe(LLMFullResponseEndFrame())

    turns, metrics = capture.finalize()

    assert len(metrics) == 1
    # 0.310 - 0.300 = 10 ms, not 0.310 - 0.200 = 110 ms.
    assert metrics[0].llm_first_token_ms == 10.0
