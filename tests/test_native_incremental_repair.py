"""Approved native playback and incremental source-position regression contracts."""

import asyncio
import hashlib
import json
import wave
from dataclasses import replace
from pathlib import Path

from pipecat.processors.frame_processor import FrameDirection

from src.pipeline.incremental_identifier_output import IncrementalIdentifierOutput
from src.pipeline.native_output import NativeSerialAudioOutput
from src.pipeline.response_revision import ResponseRevisions
from tests.test_td_identifier_output import view
from tests.test_td_identifier_rules import policy


async def test_incremental_native_append_format_correction_and_partial_send():
    """An append during the first unit preserves unsent old positions without replay."""
    rules = policy()
    sent = []
    entered, release = asyncio.Event(), asyncio.Event()
    events = []

    async def write(frame):
        sent.append(int.from_bytes(frame.audio[:2], "little"))
        if len(sent) == 1:
            entered.set()
            await release.wait()
        return True

    async def cancel():
        await asyncio.sleep(0)

    output = NativeSerialAudioOutput(
        responses=ResponseRevisions(),
        write=write,
        cancel_audio=cancel,
        evidence_sink=events.append,
    )

    async def push(frame, direction=FrameDirection.DOWNSTREAM):
        pass

    output.push_frame = push

    class Audio:
        gap_samples = 0
        sample_rate = 24000

        async def chunks(self, text, **kwargs):
            unit = kwargs["units"][0]
            if unit == "1":
                await asyncio.sleep(0.02)
            yield int(unit).to_bytes(2, "little") * 480

    echo = IncrementalIdentifierOutput(collection=rules.collection, audio=Audio(), output=output)
    pump = asyncio.create_task(output._run_pump())
    first = view("12")
    echo.consider(first, rules.evaluate(first, "编号"))
    await asyncio.wait_for(entered.wait(), 1)
    expanded = view("123", 2)
    echo.consider(expanded, rules.evaluate(expanded, "编号"))
    release.set()
    await echo.wait_pending()
    for _ in range(100):
        if len(sent) >= 3 and output.arbiter._active is None:
            break
        await asyncio.sleep(0.005)
    assert sent == [1, 2, 3]
    formatted = view("1, 2, 3.", 3, True)
    echo.consider(formatted, rules.evaluate(formatted, "编号"))
    await echo.wait_pending()
    await asyncio.sleep(0.02)
    assert sent == [1, 2, 3]
    corrected = view("121", 4, True)
    echo.consider(corrected, rules.evaluate(corrected, "编号"))
    await echo.wait_pending()
    for _ in range(100):
        if len(sent) >= 6:
            break
        await asyncio.sleep(0.005)
    assert sent == [1, 2, 3, 1, 2, 1]
    assert not any(e.get("event", "").startswith("playback_client_") for e in events)
    await echo.close()
    output._closed = True
    pump.cancel()
    await asyncio.gather(pump, return_exceptions=True)


def test_private_recording_is_original_mono_pcm_and_not_silence():
    """Validate the exact approved private clip without transmitting customer audio."""
    clip = Path("/tmp/voiceagent-private-regression-935dbcf8/digits-27s-42s.wav")
    if not clip.exists():
        import pytest

        pytest.skip("Private customer clip is intentionally not stored in Git/CI")
    manifest = json.loads(clip.with_name("manifest.json").read_text())
    assert hashlib.sha256(clip.read_bytes()).hexdigest() == manifest["sha256"]
    with wave.open(str(clip)) as audio:
        assert (audio.getframerate(), audio.getnchannels(), audio.getsampwidth()) == (16000, 1, 2)
        assert audio.getnframes() == 240000
        pcm = audio.readframes(audio.getnframes())
    assert len(set(pcm)) > 100


async def test_private_recording_replays_through_bundled_silero():
    """Replay all approved uplink samples locally; no ASR transcript truth is inferred."""
    clip = Path("/tmp/voiceagent-private-regression-935dbcf8/digits-27s-42s.wav")
    if not clip.exists():
        import pytest

        pytest.skip("Private recording is intentionally absent from CI")
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    from pipecat.audio.vad.vad_analyzer import VADParams

    def build():
        analyzer = SileroVADAnalyzer(
            sample_rate=16000,
            params=VADParams(
                confidence=0.7,
                start_secs=0.2,
                stop_secs=0.2,
                min_volume=0.6,
            ),
        )
        analyzer.set_sample_rate(16000)
        return analyzer

    vad = await asyncio.to_thread(build)
    with wave.open(str(clip)) as audio:
        pcm = audio.readframes(audio.getnframes())
    states = []
    try:
        for offset in range(0, len(pcm), 1024):
            state = await vad.analyze_audio(pcm[offset : offset + 1024])
            if not states or states[-1]["state"] != state.name:
                states.append({"audio_ms": offset / 32, "state": state.name})
    finally:
        await vad.cleanup()
    assert any(s["state"] == "SPEAKING" for s in states)
    assert any(s["state"] == "QUIET" for s in states)
    Path("/tmp/voiceagent-native-recording-replay.json").write_text(
        json.dumps(
            {
                "evidence": "local-real",
                "sha256": hashlib.sha256(clip.read_bytes()).hexdigest(),
                "samples_replayed": len(pcm) // 2,
                "sample_rate": 16000,
                "vad_transitions": states,
                "external_calls": 0,
                "asr_accuracy_verified": False,
            },
            indent=2,
        )
    )


async def test_cancelled_before_cache_preparation_can_resume_without_losing_positions():
    """A transient ineligible observation must not permanently occupy unsent positions."""
    from src.pipeline.serial_output import SerialAudioOutput

    rules = policy()
    output = SerialAudioOutput(responses=ResponseRevisions())

    class Audio:
        gap_samples = 0
        sample_rate = 24000

        async def chunks(self, text, **kwargs):
            yield b"\1\0" * 480

    echo = IncrementalIdentifierOutput(collection=rules.collection, audio=Audio(), output=output)
    current = view("12")
    evaluation = rules.evaluate(current, "编号")
    echo.consider(current, evaluation)
    echo.observe(current, replace(evaluation, echo_eligible=False))
    await echo.wait_pending()
    assert not output.arbiter.tasks
    echo.consider(current, evaluation)
    await echo.wait_pending()
    assert len(output.arbiter.tasks) == 2
    for task in output.arbiter.tasks.values():
        output.arbiter._cancel_unplayed(task)
        output._drop_buffer(task.playback_id)
    echo.consider(current, evaluation)
    await echo.wait_pending()
    assert sum(t.status == "queued" for t in output.arbiter.tasks.values()) == 2
    await echo.close()


async def test_recorded_asr_sequence_outputs_only_appended_units():
    """Replay the documented 935dbcf8 ASR revisions, independently of VAD/ASR accuracy."""
    from src.pipeline.identifier import IdentifierCollection, IdentifierVocabulary
    from src.pipeline.identifier_rules import IdentifierRules

    original = policy()
    rules = IdentifierRules(
        original.settings.model_copy(update={"wpm_threshold": 1000}),
        IdentifierCollection(
            IdentifierVocabulary({str(i): [str(i)] for i in range(10)}), target_length=11
        ),
    )
    sent = []

    async def write(frame):
        value = int.from_bytes(frame.audio[:2], "little")
        if value:
            sent.append(str(value))
        await asyncio.sleep(0.001)
        return True

    async def cancel():
        await asyncio.sleep(0)

    output = NativeSerialAudioOutput(
        responses=ResponseRevisions(), write=write, cancel_audio=cancel
    )

    async def push(*args, **kwargs):
        pass

    output.push_frame = push

    class Audio:
        sample_rate = 24000
        gap_samples = 0

        async def chunks(self, text, **kwargs):
            unit = kwargs["units"][0]
            await asyncio.sleep(0.003 if unit == "1" else 0.001)
            yield int(unit).to_bytes(2, "little") * 480

    echo = IncrementalIdentifierOutput(collection=rules.collection, audio=Audio(), output=output)
    pump = asyncio.create_task(output._run_pump())
    try:
        history = ["1234", "12345", "123453", "1, 2, 3, 4, 5, 3."]
        for revision, text in enumerate(history, 1):
            current = view(text, revision, revision == 4)
            echo.consider(current, rules.evaluate(current, "编号"))
            await echo.wait_pending()
            for _ in range(100):
                if output.arbiter._active is None and not any(
                    t.status == "queued" for t in output.arbiter.tasks.values()
                ):
                    break
                await asyncio.sleep(0.005)
        assert "".join(sent) == "123453"
        assert rules.collection.value == "123453"
    finally:
        await echo.close()
        output._closed = True
        pump.cancel()
        await asyncio.gather(pump, return_exceptions=True)


async def test_hanging_track_cancel_finishes_before_next_writer_starts():
    """A normal stop does not wait for the five-second transport failure deadline."""
    from src.pipeline.audio_identity import audio_frame_type

    entered, cleaned = asyncio.Event(), asyncio.Event()
    calls = []

    async def write(frame):
        unit = int.from_bytes(frame.audio[:2], "little")
        calls.append(unit)
        if unit == 1:
            entered.set()
            await asyncio.Event().wait()
        assert cleaned.is_set()
        return True

    async def cancel():
        await asyncio.sleep(0.01)
        cleaned.set()

    output = NativeSerialAudioOutput(
        responses=ResponseRevisions(), write=write, cancel_audio=cancel
    )

    async def push(*args, **kwargs):
        pass

    output.push_frame = push
    cls = audio_frame_type(playback_id="old", kind="normal", response_id=None)
    await output._audio(cls(b"\1\0" * 480, 24000, 1))
    pump = asyncio.create_task(output._run_pump())
    try:
        await asyncio.wait_for(entered.wait(), 1)
        output.arbiter._request_stop(output.arbiter._active)
        output._wake.set()
        await asyncio.wait_for(cleaned.wait(), 0.5)
        cls = audio_frame_type(playback_id="new", kind="normal", response_id=None)
        await output._audio(cls(b"\2\0" * 480, 24000, 1))
        output._end("new")
        for _ in range(100):
            if 2 in calls:
                break
            await asyncio.sleep(0.005)
        assert calls == [1, 2]
        assert output.arbiter.tasks["old"].status == "send_cancelled"
    finally:
        output._closed = True
        pump.cancel()
        await asyncio.gather(pump, return_exceptions=True)


async def test_started_unit_continues_when_new_wpm_is_not_echo_eligible():
    """New speed evidence affects new units, not the remainder of a started valid unit."""
    rules = policy()
    entered, release = asyncio.Event(), asyncio.Event()
    sent = []

    async def write(frame):
        sent.append(frame.audio)
        if len(sent) == 1:
            entered.set()
            await release.wait()
        return True

    async def cancel():
        raise AssertionError("Continuation must not cancel valid active echo")

    output = NativeSerialAudioOutput(
        responses=ResponseRevisions(), write=write, cancel_audio=cancel
    )

    async def push(*args, **kwargs):
        pass

    output.push_frame = push

    class Audio:
        sample_rate = 24000
        gap_samples = 0

        async def chunks(self, text, **kwargs):
            yield b"\1\0" * 480
            yield b"\1\0" * 480

    echo = IncrementalIdentifierOutput(collection=rules.collection, audio=Audio(), output=output)
    current = view("1")
    evaluation = rules.evaluate(current, "编号")
    echo.consider(current, evaluation)
    pump = asyncio.create_task(output._run_pump())
    try:
        await asyncio.wait_for(entered.wait(), 1)
        echo.observe(current, replace(evaluation, echo_eligible=False))
        release.set()
        await echo.wait_pending()
        for _ in range(100):
            if len(sent) == 2:
                break
            await asyncio.sleep(0.005)
        assert len(sent) == 2
    finally:
        await echo.close()
        output._closed = True
        pump.cancel()
        await asyncio.gather(pump, return_exceptions=True)


async def test_legacy_planner_reproduces_historical_whole_source_replays():
    """Keep a labelled old-path reproduction against the same recorded ASR sequence."""
    from src.pipeline.identifier import IdentifierCollection, IdentifierVocabulary
    from src.pipeline.identifier_output import IdentifierOutput
    from src.pipeline.identifier_rules import IdentifierRules
    from src.pipeline.serial_output import SerialAudioOutput

    original = policy()
    rules = IdentifierRules(
        original.settings.model_copy(update={"wpm_threshold": 1000}),
        IdentifierCollection(
            IdentifierVocabulary({str(i): [str(i)] for i in range(10)}), target_length=11
        ),
    )
    output = SerialAudioOutput(responses=ResponseRevisions())
    prepared = []

    class Audio:
        async def chunks(self, text, **kwargs):
            prepared.append(text)
            yield b"\1\0" * 480

    echo = IdentifierOutput(collection=rules.collection, audio=Audio(), output=output)
    for revision, text in enumerate(["1234", "12345", "123453", "1, 2, 3, 4, 5, 3."], 1):
        current = view(text, revision, revision == 4)
        echo.consider(current, rules.evaluate(current, "编号"))
        await echo.wait_pending()
        active = output.arbiter.dispatch()
        assert active is not None
        output.arbiter.client_finished(active.playback_id)
    assert prepared == ["1234", "12345", "123453", "1, 2, 3, 4, 5, 3."]
    await echo.close()


async def test_format_final_persists_effective_text_and_original_submission(tmp_path):
    """Reopening stored history retains Final text without a second user message."""
    from src.history.capture import CallCapture
    from src.history.models import HistoryTurn
    from src.history.storage import HistoryStore

    capture = CallCapture(provider="openai", model="fixture")
    capture.turns.append(HistoryTurn(sequence=0, role="user", text="我要办理", created_ms=1))
    capture.record_td_event(
        {
            "event": "conversation_utterance",
            "role": "user",
            "turn_id": 1,
            "text": "我要办理",
            "history_sequence": 0,
            "source_final": False,
        }
    )
    capture.record_td_event(
        {
            "event": "response_final_confirmed",
            "turn_id": 1,
            "text": "我 要办理。",
            "response_id": "1:1",
        }
    )
    assert len(capture.turns) == 1 and capture.turns[0].text == "我 要办理。"
    utterance = capture.td_events[0]
    assert utterance["submitted_text"] == "我要办理" and utterance["source_final"]
    store = HistoryStore(tmp_path)
    await store.initialize()
    await store.start_call(
        call_id="final",
        bot_id="fixture",
        bot_name="fixture",
        llm_provider="openai",
        llm_model="fixture",
        tts_provider="elevenlabs",
        tts_model="fixture",
        tts_voice="fixture",
        tts_text_aggregation="sentence",
        asr_provider="deepgram",
        asr_model="flux-general-en",
        language="zh",
        sample_rate=16000,
        channels=1,
    )
    await store.finish_call(
        call_id="final",
        status="completed",
        duration_ms=10,
        turns=capture.turns,
        metrics=[],
        recording_path=None,
        recording_status="unavailable",
        td_events=capture.td_events,
    )
    reopened = HistoryStore(tmp_path)
    await reopened.initialize()
    detail = await reopened.get_call("final")
    assert len(detail.turns) == 1 and detail.turns[0].text == "我 要办理。"
    assert detail.td_events[0]["submitted_text"] == "我要办理"


async def test_mixed_identifier_format_final_confirms_success_without_tool_replay():
    """Final evidence completes an applied mixed collection and permits a fresh collection."""
    from src.asr.transcript import SourceSegment, TranscriptView
    from tests.test_td_identifier_tools import params, tools

    handlers, scope, owner, collection = tools()
    partial = TranscriptView(
        "号码123", False, (SourceSegment(0, "a", 1, 0, 1000, "号码123", False),)
    )
    handlers.bind_snapshot(owner.current, partial, "编号")
    results = []
    await handlers.submit(params(scope, "submit_identifier", {"identifier": "123"}, results))
    assert collection.value == "123" and not collection.successful
    final_text = "号码 1,2,3。"
    assert owner.finalize(turn_id="1", source_ids=((0, "a"),), revision=2, text=final_text) is None
    final = TranscriptView(final_text, True, (SourceSegment(0, "a", 2, 0, 1000, final_text, True),))
    handlers.bind_snapshot(owner.current, final, "编号")
    assert collection.successful and collection.all_final
    assert len(results) == 1 and owner.restarts == []
    collection.begin_collection()
    assert collection.value == "" and collection.generation == 1
    await scope.close()
