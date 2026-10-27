"""Identifier audio jobs share collection fences and never replay obsolete cached results."""

import asyncio
from dataclasses import replace
from importlib import import_module, util

from src.asr.transcript import TimedWord, TranscriptView
from src.pipeline.response_revision import ResponseRevisions
from src.pipeline.serial_output import SerialAudioOutput
from tests.test_td_identifier_rules import policy, snapshot


def controller(rules, audio, output):
    assert util.find_spec("src.pipeline.identifier_output") is not None, (
        "Identifier output binding absent"
    )
    return import_module("src.pipeline.identifier_output").IdentifierOutput(
        collection=rules.collection,
        audio=audio,
        output=output,
    )


def view(text, revision=1, final=False):
    original = snapshot(text, words=(TimedWord(text, 0, 3000),), final=final)
    return TranscriptView(text, final, (replace(original.segments[0], revision=revision),))


async def test_revised_preparing_echo_discards_old_result_and_metadata_only_final_reuses_latest():
    rules = policy()
    output = SerialAudioOutput(responses=ResponseRevisions())
    started, release = asyncio.Event(), asyncio.Event()

    class Audio:
        async def chunks(self, text, *, generation, trace=None):
            if text == "12":
                started.set()
                await release.wait()
            yield b"\x02\x00" * 240

    echo = controller(rules, Audio(), output)
    first = view("12")
    echo.consider(first, rules.evaluate(first, "编号"))
    await started.wait()
    revised = view("13", 2)
    echo.consider(revised, rules.evaluate(revised, "编号"))
    release.set()
    await echo.wait_pending()
    assert len(output._buffers) == 1
    task = next(iter(output.arbiter.tasks.values()))
    assert task.kind == "echo" and task.revision == 2
    final = view("13", 3, True)
    echo.consider(final, rules.evaluate(final, "编号"))
    await echo.wait_pending()
    assert len(output._buffers) == 1
    assert next(iter(output._buffers.values())).valid()
    await echo.close()


async def test_collection_clear_invalidates_a_pending_recovery_before_any_audio_is_queued():
    rules = policy()
    output = SerialAudioOutput(responses=ResponseRevisions())
    started, release = asyncio.Event(), asyncio.Event()

    class Audio:
        async def chunks(self, text, *, generation, trace=None):
            started.set()
            await release.wait()
            yield b"\x01\x00" * 240

    echo = controller(rules, Audio(), output)
    first = view("12")
    echo.consider(first, rules.evaluate(first, "编号"))
    await started.wait()
    rules.collection.clear_tool(rules.collection.bind_source(0, "clear", 1, "clear"))
    release.set()
    await echo.wait_pending()
    assert output.arbiter.generation == 1 and not output._buffers
    await echo.close()


async def test_late_final_echo_cannot_pass_an_already_ready_ordinary_response():
    """Input order is shared with output readiness, even across many earlier observed ranges."""
    from src.pipeline.audio_identity import audio_frame_type

    rules = policy()
    output = SerialAudioOutput(responses=ResponseRevisions())
    started, release = asyncio.Event(), asyncio.Event()

    class Audio:
        async def chunks(self, text, *, generation, trace=None):
            started.set()
            await release.wait()
            yield b"\x01\x00" * 240

    echo = controller(rules, Audio(), output)
    # An independent counter per input/output would reverse these logical orders.
    for index in range(30):
        output.source_order("earlier:" + str(index), 0)
    final = view("123", final=True)
    evaluated = rules.evaluate(final, "编号")
    assert evaluated.path == "complete" and evaluated.echo_eligible
    echo.observe(final, evaluated, 1)
    echo.consider(final, evaluated, 1)
    await started.wait()
    cls = audio_frame_type(playback_id="ordinary", kind="normal", response_id=None)
    await output._audio(cls(b"\x02\x00" * 240, 24000, 1))
    release.set()
    await echo.wait_pending()
    tasks = list(output.arbiter.tasks.values())
    assert len(tasks) == 2
    assert next(t for t in tasks if t.kind == "echo").status == "cancelled_unplayed"
    assert output.arbiter.dispatch().playback_id == "ordinary"
    await echo.close()


async def test_sent_revision_is_corrected_before_ordinary_without_erasing_original_facts():
    from src.pipeline.audio_identity import audio_frame_type

    rules = policy()
    output = SerialAudioOutput(responses=ResponseRevisions())

    class Audio:
        async def chunks(self, text, *, generation, trace=None):
            yield b"\x01\x00" * 240

    echo = controller(rules, Audio(), output)
    first = view("12")
    echo.consider(first, rules.evaluate(first, "编号"), 1)
    await echo.wait_pending()
    original = output.arbiter.dispatch()
    revised = view("13", 2, True)
    echo.consider(revised, rules.evaluate(revised, "编号"), 1)
    await echo.wait_pending()
    cls = audio_frame_type(playback_id="ordinary", kind="normal", response_id=None)
    await output._audio(cls(b"\x02\x00" * 240, 24000, 1))
    assert original.status == "sent_unknown" and not original.started
    assert output.arbiter.dispatch() is None
    assert output.arbiter.client_finished(original.playback_id, event="task_stopped")
    correction = output.arbiter.dispatch()
    assert correction.kind == "correction" and correction.revision == 2
    assert original.status == "stopped" and not original.started
    await echo.close()


async def test_metadata_final_does_not_retry_a_failed_queued_echo():
    """D-074 skips a failed source; a metadata-only Final is not a new user request."""
    rules = policy()
    output = SerialAudioOutput(responses=ResponseRevisions())
    calls = []

    class Audio:
        async def chunks(self, text, *, generation, trace=None):
            calls.append(text)
            yield b"\x01\x00" * 240
            raise ValueError("inert source failure after buffered audio")

    echo = controller(rules, Audio(), output)
    first = view("12")
    echo.consider(first, rules.evaluate(first, "编号"))
    await echo.wait_pending()
    final = view("12", 2, True)
    echo.consider(final, rules.evaluate(final, "编号"))
    await echo.wait_pending()
    assert calls == ["12"]
    await echo.close()
