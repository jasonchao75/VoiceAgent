"""Runtime coordinator scenarios without external ASR, Jev or TTS requests."""

from importlib import import_module, util

import pytest
from pipecat.frames.frames import InterimTranscriptionFrame, ProposedUserStoppedSpeakingFrame

from src.asr.factory import ASRService
from src.asr.td_config import CustomTDSettings
from src.asr.turn_events import SourceNormalizer
from tests.test_td_config import td_settings


def coordinator(**kwargs):
    """Use the production processor and replace only its output transport in tests."""
    assert util.find_spec("src.pipeline.custom_td") is not None, "Runtime TD coordinator is absent"
    module = import_module("src.pipeline.custom_td")
    source = ASRService(
        processor=None, source_normalizer=SourceNormalizer("deepgram", "flux-general-en")
    )
    return module.CustomTDCoordinator(
        asr=source,
        settings=CustomTDSettings.model_validate(td_settings()),
        decide=kwargs.pop("decide", None),
        **kwargs,
    )


def interim(text="12"):
    """An actual raw Flux Update carried by the registered adapter."""
    return InterimTranscriptionFrame(
        text,
        "",
        "",
        result={
            "event": "Update",
            "turn_index": 0,
            "transcript": text,
            "audio_window_start": 0,
            "audio_window_end": 1,
            "words": [{"word": text, "start": 0, "end": 1}],
        },
    )


async def test_runtime_does_not_forward_provider_endpoint_or_partial():
    """Only a custom deadline may release aggregated user text downstream."""
    td = coordinator()
    out = []

    async def push(frame, *args, **kwargs):
        out.append(frame)

    td.push_frame = push
    await td.receive_transcript(interim())
    assert await td.filter_provider_frame(ProposedUserStoppedSpeakingFrame())
    assert out == []
    await td.speech_started()
    await td.speech_stopped(1000)
    await td.advance(3499)
    assert out != []
    from pipecat.frames.frames import TranscriptionFrame

    assert not any(isinstance(frame, TranscriptionFrame) for frame in out)
    await td.advance(3500)
    committed = [frame for frame in out if isinstance(frame, TranscriptionFrame)]
    assert len(committed) == 1 and committed[0].text == "12"
    assert committed[0].metadata["td_source_final"] is False
    await td.advance(3600)
    assert len([frame for frame in out if isinstance(frame, TranscriptionFrame)]) == 1


async def test_runtime_continuation_cancels_old_deadline():
    """A stale candidate cannot submit after new speech has started."""
    td = coordinator()
    out = []

    async def push(frame, *args, **kwargs):
        out.append(frame)

    td.push_frame = push
    await td.speech_started()
    await td.receive_transcript(interim())
    await td.speech_stopped(1000)
    await td.speech_started()
    await td.advance(5000)
    from pipecat.frames.frames import TranscriptionFrame

    assert not any(isinstance(frame, TranscriptionFrame) for frame in out)


async def test_real_pipecat_aggregator_releases_exactly_one_context_after_owned_commit():
    """Exercise the actual locked controller, strategy setup and aggregator, without providers."""
    import asyncio

    from pipecat.frames.frames import LLMContextFrame, StartFrame
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.worker import PipelineWorker
    from pipecat.processors.aggregators.llm_context import LLMContext
    from pipecat.processors.frame_processor import FrameProcessor
    from pipecat.workers.runner import WorkerRunner

    from src.pipeline.td_strategies import create_custom_aggregators

    ready, released = asyncio.Event(), asyncio.Event()
    contexts = []

    class Sink(FrameProcessor):
        """Capture the real LLM request boundary in the assembled pipeline."""

        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)
            if isinstance(frame, StartFrame):
                ready.set()
            if isinstance(frame, LLMContextFrame):
                contexts.append(list(frame.context.get_messages()))
                released.set()
            await self.push_frame(frame, direction)

    td = coordinator()
    context = LLMContext()
    user, _assistant = create_custom_aggregators(context, td.authority)
    worker = PipelineWorker(Pipeline([td, user, Sink()]), enable_rtvi=False)
    runner = WorkerRunner(handle_sigint=False, handle_sigterm=False)
    await runner.add_workers(worker)
    running = asyncio.create_task(runner.run())
    try:
        await asyncio.wait_for(ready.wait(), 3)
        await td.speech_started()
        await td.receive_transcript(interim())
        await td.speech_stopped(1000)
        from src.asr.factory import create_default_asr_registry
        from src.config import AudioConfig

        provider = create_default_asr_registry().create(
            provider="deepgram",
            model="flux-general-en",
            turn_detection_source="self_developed",
            options={},
            api_key="test-fixture-no-connection",
            audio=AudioConfig(),
        )
        await worker.queue_frames(
            [provider.processor.service_metadata_frame(), ProposedUserStoppedSpeakingFrame()]
        )
        await td.advance(3499)
        assert contexts == []
        await td.advance(3500)
        await asyncio.wait_for(released.wait(), 3)
        assert len(contexts) == 1
        assert contexts[0][-1]["role"] == "user" and contexts[0][-1]["content"] == "12"
        await td.advance(5000)
        assert len(contexts) == 1
        from pipecat.frames.frames import TranscriptionFrame

        released.clear()
        final = TranscriptionFrame(
            "13",
            "",
            "",
            result={
                **interim().result,
                "event": "EndOfTurn",
                "transcript": "13",
                "words": [{"word": "13", "start": 0, "end": 1}],
            },
        )
        await td.receive_transcript(final)
        await asyncio.wait_for(released.wait(), 3)
        assert len(contexts) == 2
        assert contexts[-1] == [{"role": "user", "content": "13"}]
        assert td.responses.user_submission_count == 1
        await td.receive_transcript(final)
        assert len(contexts) == 2
    finally:
        await worker.cancel()
        await asyncio.wait_for(running, 3)


async def test_bundled_silero_real_silence_and_pcm_validation():
    """Use the actual local ONNX model, with generated silence and no external calls."""
    import asyncio

    from pipecat.frames.frames import InputAudioRawFrame
    from pipecat.processors.frame_processor import FrameDirection

    from src.pipeline.custom_td import prepare_custom_td
    from tests.test_td_source_frames import Source

    events = []
    source = ASRService(
        processor=Source(), source_normalizer=SourceNormalizer("deepgram", "flux-general-en")
    )
    audio, td, client = await asyncio.wait_for(
        prepare_custom_td(
            asr=source,
            settings=CustomTDSettings.model_validate(td_settings()),
            api_key="test-fixture-not-sent",
            evidence_sink=events.append,
        ),
        10,
    )
    source.processor.record_source_diagnostic("asr_native_result", text_chars=0)
    assert events[-1]["event"] == "asr_native_result"
    forwarded = []

    async def push(frame, *args, **kwargs):
        forwarded.append(frame)

    audio.push_frame = push
    try:
        silence = InputAudioRawFrame(bytes(3200), sample_rate=16000, num_channels=1)
        await audio.process_frame(silence, FrameDirection.DOWNSTREAM)
        assert forwarded == [silence]
        assert td._audio_ms == 100 and not td._speaking
        assert audio.vad.params.model_dump() == td.settings.vad.model_dump()
        assert audio.vad.sample_rate == 16000 and audio.vad.num_channels == 1
        for invalid in (
            InputAudioRawFrame(bytes(100), sample_rate=8000, num_channels=1),
            InputAudioRawFrame(bytes(100), sample_rate=16000, num_channels=2),
            InputAudioRawFrame(bytes(3), sample_rate=16000, num_channels=1),
        ):
            with pytest.raises(ValueError, match="16 kHz mono"):
                await audio.process_frame(invalid, FrameDirection.DOWNSTREAM)
        assert forwarded == [silence]
    finally:
        await audio.cleanup()
        await td.cleanup()
        await client.aclose()


async def test_runtime_watchdog_does_not_wait_for_slow_jev():
    """Cloud work remains asynchronous; a missing result cannot extend audio silence."""
    import asyncio

    from pipecat.frames.frames import TranscriptionFrame

    from src.pipeline.jev import JevResult

    td = coordinator()
    started, release = asyncio.Event(), asyncio.Event()

    async def slow(**kwargs):
        started.set()
        await release.wait()
        return JevResult("ok", 0.9, {"complete": 0.8, "incomplete": 0.2})

    td._decide = slow
    out = []

    async def push(frame, *args, **kwargs):
        out.append(frame)

    td.push_frame = push
    try:
        await td.speech_started()
        await td.receive_transcript(interim())
        await td.speech_stopped(1000)
        await asyncio.wait_for(started.wait(), 1)
        await td.advance(3500)
        assert len([frame for frame in out if isinstance(frame, TranscriptionFrame)]) == 1
        release.set()
        await td._decision
        assert td._candidate is None
    finally:
        await td.cleanup()


async def test_runtime_unexpected_jev_error_is_safe_and_falls_back():
    """Unexpected exceptions become safe evidence rather than a dead watchdog task."""
    evidence = []
    td = coordinator()
    td._sink = evidence.append

    async def fail(**kwargs):
        raise RuntimeError("secret provider response")

    td._decide = fail
    out = []

    async def push(frame, *args, **kwargs):
        out.append(frame)

    td.push_frame = push
    await td.speech_started()
    await td.receive_transcript(interim())
    await td.speech_stopped(1000)
    await td._decision
    await td.advance(3500)
    assert any(event.get("status") == "request_failed:RuntimeError" for event in evidence)
    assert "secret provider response" not in str(evidence)
    assert td.responses.user_submission_count == 1
    await td.cleanup()


async def test_candidate_and_commit_evidence_share_the_original_user_turn():
    """Pre-commit candidate records must not be attached to the preceding user turn."""
    td = coordinator()
    evidence = []
    td._sink = evidence.append

    async def push(frame, *args, **kwargs):
        pass

    td.push_frame = push
    await td.speech_started()
    await td.receive_transcript(interim())
    await td.speech_stopped(1000)
    await td.advance(3500)
    related = [item for item in evidence if item["event"] in {"candidate_created", "td_commit"}]
    assert {item["turn_id"] for item in related} == {1}


@pytest.mark.parametrize("split_sources", [False, True])
async def test_coordinator_binds_mixed_input_to_the_actual_registered_tool_handler(split_sources):
    """The production TD submit boundary gives tools the same source/response owner."""
    from types import SimpleNamespace

    from pipecat.processors.aggregators.llm_context import LLMContext

    from src.pipeline.identifier import IdentifierCollection, IdentifierVocabulary
    from src.pipeline.identifier_tools import IdentifierTools
    from src.pipeline.response_revision import ResponseRevisions
    from src.pipeline.response_scope import ResponseScope

    owner = ResponseRevisions()
    state = IdentifierCollection(
        IdentifierVocabulary({"1": ["1"], "2": ["2"], "3": ["3"]}), target_length=3
    )
    boundary = ResponseScope(owner)
    tools = IdentifierTools(boundary, state, keywords=("编号",))
    td = coordinator(responses=owner, bind_input=tools.bind_snapshot)
    boundary.enrich_context = tools.enrich_context
    output, results = [], []

    async def push(frame, *args, **kwargs):
        output.append(frame)

    async def result(value):
        results.append(value)

    td.push_frame = push
    td.assistant_context("请提供编号")
    await td.speech_started()
    if split_sources:
        await td.receive_transcript(interim("号码"))
        frame = interim("123")
        frame.result.update(
            turn_index=1,
            audio_window_start=1,
            audio_window_end=2,
            words=[{"word": "123", "start": 1, "end": 2}],
        )
        await td.receive_transcript(frame)
    else:
        await td.receive_transcript(interim("号码123"))
    assert state.value == ""
    await td.speech_stopped(2000 if split_sources else 1000)
    await td.advance(4500 if split_sources else 3500)
    context = boundary.bind(LLMContext())
    await tools.submit(
        SimpleNamespace(
            context=context,
            function_name="submit_identifier",
            arguments={"identifier": "123"},
            result_callback=result,
        )
    )
    assert results[-1]["status"] == "submitted" and state.value == "123"
    assert boundary.provenance(context).turn_id == "1"
    assert len(boundary.provenance(context).source_ids) == (2 if split_sources else 1)
    await boundary.close()


async def test_final_reanswer_keeps_original_input_keyword_gate_and_generation():
    """The answer to a Partial is not a new collection prompt authorizing that same input."""
    from types import SimpleNamespace

    from pipecat.processors.aggregators.llm_context import LLMContext

    from src.asr.transcript import SourceSegment, TranscriptView
    from src.pipeline.identifier import IdentifierCollection, IdentifierVocabulary
    from src.pipeline.identifier_tools import IdentifierTools
    from src.pipeline.response_revision import ResponseRevisions
    from src.pipeline.response_scope import ResponseScope

    owner = ResponseRevisions()
    collection = IdentifierCollection(IdentifierVocabulary({"1": ["1"]}), target_length=1)
    boundary = ResponseScope(owner)
    tools = IdentifierTools(boundary, collection, keywords=("编号",))
    original = owner.submit(turn_id="1", source_ids=((0, "a"),), text="号码1", final=False)
    snapshot = TranscriptView("号码1", False, (SourceSegment(0, "a", 1, 0, 1000, "号码1", False),))
    tools.bind_snapshot(original, snapshot, "普通开场，没有采集要求")
    final = owner.finalize(turn_id="1", source_ids=((0, "a"),), revision=2, text="号码1")
    tools.bind_snapshot(final.new_response, snapshot, "请提供编号")
    results = []

    async def callback(value):
        results.append(value)

    await tools.submit(
        SimpleNamespace(
            context=boundary.bind(LLMContext()),
            function_name="submit_identifier",
            arguments={"identifier": "1"},
            result_callback=callback,
        )
    )
    assert collection.value == "" and results[-1]["status"] == "stale"
    await boundary.close()


async def test_pure_incomplete_identifier_bypasses_jev_and_ordinary_maximum():
    """Collection protection is independent; a fast segment still contributes without echo."""
    from pipecat.frames.frames import TranscriptionFrame, TTSSpeakFrame

    from src.asr.td_config import IdentifierRuleSettings
    from src.pipeline.identifier import IdentifierCollection, IdentifierVocabulary
    from src.pipeline.identifier_rules import IdentifierRules
    from tests.test_td_rule_settings import priority_settings

    settings = IdentifierRuleSettings.model_validate(priority_settings())
    state = IdentifierCollection(
        IdentifierVocabulary({"1": ["1"], "2": ["2"], "3": ["3"]}), target_length=3
    )
    rules = IdentifierRules(settings, state)
    from src.pipeline.jev import JevResult

    calls = []

    async def decide(**kwargs):
        calls.append(kwargs)
        return JevResult("fixture_error")

    td = coordinator(identifier_rules=rules, decide=decide)
    output = []

    async def push(frame, *args, **kwargs):
        output.append(frame)

    td.push_frame = push
    td.assistant_context("请提供编号")
    await td.speech_started()
    await td.receive_transcript(interim("12"))
    await td.speech_stopped(1000)
    await td.advance(3500)
    assert state.value == "12"
    assert not any(isinstance(frame, TranscriptionFrame) for frame in output)
    await td.advance(9000)
    reminders = [frame for frame in output if isinstance(frame, TTSSpeakFrame)]
    assert len(reminders) == 1 and reminders[0].text == settings.collection.incomplete_text
    await td.advance(18000)
    import asyncio

    await asyncio.sleep(0)
    assert calls == []
    assert len([frame for frame in output if isinstance(frame, TTSSpeakFrame)]) == 1
    assert state.value == "12"


async def test_question_after_processed_pure_input_reuses_state_without_resubmitting_digits():
    """Once a local segment was independently handled, only the later question enters LLM."""
    from pipecat.frames.frames import TranscriptionFrame

    from src.asr.td_config import IdentifierRuleSettings
    from src.pipeline.identifier import IdentifierCollection, IdentifierVocabulary
    from src.pipeline.identifier_rules import IdentifierRules
    from tests.test_td_rule_settings import priority_settings

    settings = IdentifierRuleSettings.model_validate(priority_settings())
    state = IdentifierCollection(
        IdentifierVocabulary({"1": ["1"], "2": ["2"], "3": ["3"]}), target_length=3
    )
    td = coordinator(identifier_rules=IdentifierRules(settings, state))
    output = []

    async def push(frame, *args, **kwargs):
        output.append(frame)

    td.push_frame = push
    td.assistant_context("请提供编号")
    await td.speech_started()
    await td.receive_transcript(interim("12"))
    await td.speech_stopped(1000)
    await td.advance(1350)
    await td.speech_started()
    question = interim("还要几位")
    question.result.update(
        turn_index=1,
        audio_window_start=1,
        audio_window_end=2,
        words=[{"word": "还要几位", "start": 1, "end": 2}],
    )
    await td.receive_transcript(question)
    await td.speech_stopped(2000)
    await td.advance(4500)
    commits = [frame for frame in output if isinstance(frame, TranscriptionFrame)]
    assert len(commits) == 1 and commits[0].text == "还要几位"
    assert state.value == "12"


@pytest.mark.parametrize("revised,expected", [("12，嗯，还要几位", ""), ("123", "123")])
async def test_local_processing_revision_routes_latest_input_once(revised, expected):
    """A consumed local range can be revised, but must not be counted as another user turn."""
    from pipecat.frames.frames import TranscriptionFrame

    from src.asr.td_config import IdentifierRuleSettings
    from src.pipeline.identifier import IdentifierCollection, IdentifierVocabulary
    from src.pipeline.identifier_rules import IdentifierRules
    from tests.test_td_rule_settings import priority_settings

    settings = IdentifierRuleSettings.model_validate(priority_settings())
    state = IdentifierCollection(
        IdentifierVocabulary({"1": ["1"], "2": ["2"], "3": ["3"]}), target_length=3
    )
    td = coordinator(identifier_rules=IdentifierRules(settings, state))
    frames = []

    async def push(frame, *args, **kwargs):
        frames.append(frame)

    td.push_frame = push
    td.assistant_context("请提供编号")
    await td.speech_started()
    await td.receive_transcript(interim("12"))
    await td.speech_stopped(1000)
    await td.advance(1350)
    assert state.value == "12"
    await td.receive_transcript(interim(revised))
    await td.advance(3500)
    commits = [frame for frame in frames if isinstance(frame, TranscriptionFrame)]
    assert len(commits) == 1 and commits[0].text == revised
    assert state.value == expected and td.responses.user_submission_count == 1


@pytest.mark.parametrize(
    "finalized,committed,expected,generation",
    [(True, True, "1", 1), (False, True, "1231", 0), (True, False, "1231", 0)],
)
async def test_new_pure_input_resets_only_after_committed_final_success(
    finalized, committed, expected, generation
):
    """Only a finalized, committed collection authorizes a new collection generation."""
    from src.asr.td_config import IdentifierRuleSettings
    from src.pipeline.identifier import IdentifierCollection, IdentifierVocabulary
    from src.pipeline.identifier_rules import IdentifierRules
    from tests.test_td_rule_settings import priority_settings

    state = IdentifierCollection(
        IdentifierVocabulary({"1": ["1"], "2": ["2"], "3": ["3"]}), target_length=3
    )
    rules = IdentifierRules(IdentifierRuleSettings.model_validate(priority_settings()), state)
    td = coordinator(identifier_rules=rules)

    async def push(frame, *args, **kwargs):
        pass

    td.push_frame = push
    td.assistant_context("请提供编号")
    await td.speech_started()
    first = interim("123")
    if finalized:
        first.result["event"] = "EndOfTurn"
    await td.receive_transcript(first)
    await td.speech_stopped(1000)
    await td.advance(3500 if committed else 1350)
    assert state.value == "123"
    await td.speech_started()
    following = interim("1")
    following.result.update(
        turn_index=1,
        audio_window_start=1,
        audio_window_end=2,
        words=[{"word": "1", "start": 1, "end": 2}],
    )
    await td.receive_transcript(following)
    await td.speech_stopped(2000)
    assert state.value == expected and state.generation == generation
    if generation == 1:
        late = interim("321")
        late.result["event"] = "EndOfTurn"
        await td.receive_transcript(late)
        assert state.value == "1" and state.generation == 1


@pytest.mark.parametrize("after_reminder", [False, True])
async def test_late_old_identifier_range_revises_without_submitting_new_speech(after_reminder):
    """An old range survives next speech/reminder, yet never becomes a new LLM turn."""
    from src.asr.td_config import IdentifierRuleSettings
    from src.pipeline.identifier import IdentifierCollection, IdentifierVocabulary
    from src.pipeline.identifier_rules import IdentifierRules
    from tests.test_td_rule_settings import priority_settings

    state = IdentifierCollection(
        IdentifierVocabulary({"1": ["1"], "2": ["2"], "3": ["3"]}),
        target_length=3,
    )
    td = coordinator(
        identifier_rules=IdentifierRules(
            IdentifierRuleSettings.model_validate(priority_settings()),
            state,
        )
    )
    frames, events = [], []
    td._sink = events.append

    async def push(frame, *args, **kwargs):
        frames.append(frame)

    td.push_frame = push
    td.assistant_context("请提供编号")
    await td.speech_started()
    await td.receive_transcript(interim("1"))
    await td.speech_stopped(1000)
    await td.advance(9000 if after_reminder else 1350)
    await td.speech_started()
    following = interim("2")
    following.result.update(
        turn_index=1,
        audio_window_start=10,
        audio_window_end=11,
        words=[{"word": "2", "start": 10, "end": 11}],
    )
    await td.receive_transcript(following)
    await td.speech_stopped(11000)
    assert state.value == "12"
    old_final = interim("3")
    old_final.result["event"] = "EndOfTurn"
    await td.receive_transcript(old_final)
    assert state.value == "32"
    assert td.responses.user_submission_count == 0
    revisions = [event for event in events if event["event"] == "identifier_retained_revision"]
    assert len(revisions) == 1
    await td.receive_transcript(old_final)
    assert len([event for event in events if event["event"] == "identifier_retained_revision"]) == 1
    state.clear_tool(state.bind_source(0, "clear", 1, "clear"))
    stale = interim("1")
    stale.result["event"] = "EndOfTurn"
    await td.receive_transcript(stale)
    assert state.value == ""
    await td.advance(20000)
    assert td.responses.user_submission_count == 0


async def test_identifier_audio_hook_waits_for_pause_and_refreshes_same_text_final():
    from src.asr.td_config import IdentifierRuleSettings
    from src.pipeline.identifier_rules import IdentifierRules
    from tests.test_td_identifier import collection
    from tests.test_td_rule_settings import priority_settings

    received = []
    rules = IdentifierRules(
        IdentifierRuleSettings.model_validate(priority_settings()), collection()
    )
    td = coordinator(
        identifier_rules=rules,
        identifier_output=lambda view, evaluation, turn_id: received.append((view, evaluation)),
    )

    async def push(frame, *args, **kwargs):
        pass

    td.push_frame = push
    td.assistant_context("请提供编号")
    await td.speech_started()
    await td.receive_transcript(interim("1"))
    await td.speech_stopped(1000)
    await td.advance(1349)
    assert not received
    await td.advance(1350)
    assert len(received) == 1 and received[0][1].echo_eligible
    final = interim("1")
    final.result["event"] = "EndOfTurn"
    await td.receive_transcript(final)
    assert received[-1][0].final and received[-1][0].text == "1"
    assert td.responses.user_submission_count == 0


@pytest.mark.parametrize("late_text", ["3", "我的3"])
async def test_retained_final_and_echo_keep_original_turn_after_a_new_turn_started(late_text):
    from src.asr.td_config import IdentifierRuleSettings
    from src.pipeline.identifier_rules import IdentifierRules
    from tests.test_td_identifier import collection
    from tests.test_td_rule_settings import priority_settings

    events, offered = [], []
    td = coordinator(
        identifier_rules=IdentifierRules(
            IdentifierRuleSettings.model_validate(priority_settings()), collection()
        ),
        identifier_output=lambda view, evaluation, turn_id: offered.append(turn_id),
        evidence_sink=events.append,
    )

    async def push(frame, *args, **kwargs):
        pass

    td.push_frame = push
    td.assistant_context("请提供编号")
    await td.speech_started()
    await td.receive_transcript(interim("1"))
    await td.speech_stopped(1000)
    await td.advance(1350)
    await td.speech_started()
    question = interim("where")
    question.result.update(
        turn_index=1,
        audio_window_start=10,
        audio_window_end=11,
        words=[{"word": "where", "start": 10, "end": 11}],
    )
    await td.receive_transcript(question)
    await td.speech_stopped(11000)
    await td.advance(13500)
    await td.speech_started()
    late = interim(late_text)
    late.result["event"] = "EndOfTurn"
    await td.receive_transcript(late)
    revision = [event for event in events if event["event"] == "identifier_retained_revision"][-1]
    raw = [
        event
        for event in events
        if event["event"] == "source_transcript" and event["text"] == late_text
    ][-1]
    assert revision["turn_id"] == 1 and raw["turn_id"] == 1 and offered[-1] == 1
    assert td.responses.user_submission_count == 1
    assert td._current_view().text == ""
    assert not td._pending_mixed


async def test_jev_history_keeps_sent_snapshot_duration_and_wait_decomposition():
    import asyncio

    from src.pipeline.jev import JevResult

    events = []

    async def decide(**kwargs):
        return JevResult("ok", noul=0.9, probabilities={"complete": 0.8, "incomplete": 0.2})

    td = coordinator(decide=decide, evidence_sink=events.append)

    async def push(*args, **kwargs):
        pass

    td.push_frame = push
    td.assistant_context("original assistant")
    await td.speech_started()
    await td.receive_transcript(interim())
    await td.speech_stopped(1000)
    await asyncio.wait_for(td._decision, 1)
    request = next(e for e in events if e["event"] == "jev_decision_attempt")
    assert request["assistant"] == "original assistant" and request["text"] == "12"
    assert request["transcript_status"] == "Partial"
    result = next(e for e in events if e["event"] == "jev_result")
    assert result["duration_ms"] >= 0 and result["turn_id"] == 1
    wait = next(e for e in events if e["event"] == "jev_wait_calculated")
    assert wait["noul_ms"] == pytest.approx(790)
    assert wait["choice_ms"] == pytest.approx(860)
    assert wait["target_ms"] == pytest.approx(825)
    assert wait["remaining_ms"] == pytest.approx(825)
    await td._close_tasks()


async def test_late_cancel_ignoring_jev_result_keeps_original_turn_in_discard_history():
    import asyncio

    from src.pipeline.jev import JevResult

    started, cancelled, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    events = []

    async def decide(**kwargs):
        started.set()
        try:
            await release.wait()
        except asyncio.CancelledError:
            cancelled.set()
            await release.wait()
        return JevResult("timeout")

    td = coordinator(decide=decide, evidence_sink=events.append)

    async def push(*args, **kwargs):
        pass

    td.push_frame = push
    await td.speech_started()
    await td.receive_transcript(interim())
    await td.speech_stopped(1000)
    await started.wait()
    pending = td._decision
    await td.advance(3500)
    await td.speech_started()
    await cancelled.wait()
    release.set()
    await asyncio.wait_for(pending, 1)
    discard = next(e for e in events if e["event"] == "jev_discarded")
    assert discard["turn_id"] == 1 and td._active_turn_id == 2
    await td._close_tasks()


async def test_unsubmitted_old_local_range_revised_to_mixed_returns_to_current_td_once():
    from pipecat.frames.frames import TranscriptionFrame

    from src.asr.td_config import IdentifierRuleSettings
    from src.pipeline.identifier_rules import IdentifierRules
    from tests.test_td_identifier import collection
    from tests.test_td_rule_settings import priority_settings

    rules = IdentifierRules(
        IdentifierRuleSettings.model_validate(priority_settings()), collection()
    )
    td = coordinator(identifier_rules=rules)
    td.assistant_context("编号")
    out = []

    async def push(frame, *args, **kwargs):
        out.append(frame)

    td.push_frame = push
    first = interim("1")
    first.result.update(audio_window_end=2, words=[{"word": "1", "start": 0, "end": 2}])
    await td.speech_started()
    await td.receive_transcript(first)
    await td.speech_stopped(2000)
    await td.advance(2350)
    assert rules.collection.value == "1" and td.responses.user_submission_count == 0
    await td.speech_started()
    revised = interim("我的1")
    revised.result.update(
        event="EndOfTurn", audio_window_end=2, words=[{"word": "我的1", "start": 0, "end": 2}]
    )
    await td.receive_transcript(revised)
    following = interim("2")
    following.result.update(
        turn_index=1,
        audio_window_start=2,
        audio_window_end=4,
        words=[{"word": "2", "start": 2, "end": 4}],
    )
    await td.receive_transcript(following)
    await td.speech_stopped(4000)
    await td.advance(6500)
    committed = [f for f in out if isinstance(f, TranscriptionFrame)]
    assert len(committed) == 1 and committed[0].text == "我的12"
    assert rules.collection.value == ""
    await td.advance(7000)
    assert td.responses.user_submission_count == 1


@pytest.mark.parametrize("result", [None, "unstructured"])
async def test_missing_provider_payload_preserves_unowned_transcript_evidence(result):
    """Missing provenance must remain visible without borrowing the active turn."""
    events = []
    td = coordinator(evidence_sink=events.append)
    frame = InterimTranscriptionFrame("raw text without range", "", "", result=result)
    await td.receive_transcript(frame)
    assert td.unranged_text == frame.text
    record = next(event for event in events if event["event"] == "unranged_transcript")
    assert record["text"] == frame.text
    assert record["turn_id"] is None
    assert record["reason"] == "source_payload_unavailable"
    assert record["stream_epoch"] == 0
    assert td.ledger.view().text == ""
    await td.receive_transcript(interim("later valid text"))
    assert td._current_view().missing_reason == "unresolved_source_audio_range"


async def test_missing_range_fails_once_at_maximum_without_submitting_or_executing_tools():
    """D-061: unresolved evidence must terminate at the existing silence maximum."""
    events, errors, output = [], [], []
    td = coordinator(evidence_sink=events.append)

    async def error(error_msg, **kwargs):
        errors.append((error_msg, kwargs.get("force_treat_as_permanent")))

    async def push(frame, *args, **kwargs):
        output.append(frame)

    td.push_error = error
    td.push_frame = push
    await td.speech_started()
    await td.receive_transcript(InterimTranscriptionFrame("unknown original", "", "", result=None))
    await td.speech_stopped(1000)
    await td.advance(3499)
    assert errors == []
    await td.advance(3500)
    assert errors == [("asr_source_evidence_unavailable", True)]
    assert td.source_evidence_error is not None
    assert td.responses.user_submission_count == 0
    assert not any(type(frame).__name__ == "TranscriptionFrame" for frame in output)
    failure = next(event for event in events if event["event"] == "asr_source_evidence_failed")
    assert failure["turn_id"] is None
    assert failure["silence_start_ms"] == 1000
    assert failure["deadline_ms"] == 3500
    assert any(
        event["event"] == "unranged_transcript" and event["text"] == "unknown original"
        for event in events
    )
    assert failure["reason"] == "unresolved_source_audio_range"
    await td.advance(3600)
    assert len(errors) == 1


async def test_same_snapshot_recovery_before_maximum_keeps_normal_submission():
    """D-061 does not turn recoverable interim evidence into a premature call failure."""
    from pipecat.processors.frame_processor import FrameProcessor

    td = coordinator()
    td.asr = ASRService(FrameProcessor(), source_normalizer=SourceNormalizer("soniox", "stt-rt-v5"))
    output = []

    async def push(frame, *args, **kwargs):
        output.append(frame)

    td.push_frame = push
    await td.speech_started()
    await td.receive_transcript(
        InterimTranscriptionFrame(
            "one",
            "",
            "",
            result=[{"text": "one", "is_final": False}],
        )
    )
    await td.speech_stopped(1000)
    await td.advance(3499)
    await td.receive_transcript(
        InterimTranscriptionFrame(
            "one",
            "",
            "",
            result=[{"text": "one", "is_final": False, "start_ms": 0, "end_ms": 100}],
        )
    )
    await td.advance(3500)
    assert td.source_evidence_error is None
    assert td.responses.user_submission_count == 1


async def test_partially_unranged_snapshot_preserves_full_text_beside_known_segments():
    """A valid sibling segment cannot hide a missing range in the same raw frame."""
    events = []
    td = coordinator(evidence_sink=events.append)
    td.asr.source_normalizer = SourceNormalizer("speechmatics", "enhanced")
    frame = InterimTranscriptionFrame(
        "1234",
        "",
        "",
        result={
            "message": "AddPartialSegment",
            "segments": [
                {"speaker_id": "a", "text": "12", "metadata": {"start_time": 0, "end_time": 0.2}},
                {"speaker_id": "a", "text": "34", "metadata": None},
            ],
        },
    )
    await td.receive_transcript(frame)
    assert td.ledger.view().text == "12"
    assert td.unranged_text == "1234"
    record = next(event for event in events if event["event"] == "unranged_transcript")
    assert record["text"] == "1234"
    assert record["turn_id"] is None
    assert record["normalized_segment_count"] == 1
    await td.receive_transcript(
        InterimTranscriptionFrame(
            "56",
            "",
            "",
            result={
                "message": "AddPartialSegment",
                "segments": [
                    {
                        "speaker_id": "b",
                        "text": "56",
                        "metadata": {"start_time": 0.4, "end_time": 0.6},
                    },
                ],
            },
        )
    )
    assert td._current_view().missing_reason == "unresolved_source_audio_range"


async def test_incomplete_word_coverage_blocks_commit_even_with_a_newer_valid_tail():
    """A known later segment cannot hide an unresolved cross-submission source gap."""
    from pipecat.frames.frames import TranscriptionFrame

    td = coordinator()
    out = []

    async def push(frame, *args, **kwargs):
        out.append(frame)

    td.push_frame = push
    first = interim("1")
    first.result.update(audio_window_end=0.1, words=[{"word": "1", "start": 0, "end": 0.1}])
    await td.receive_transcript(first)
    td.ledger.consume()
    revision = interim("123")
    revision.result.update(
        audio_window_end=0.3,
        words=[
            {"word": "1", "start": 0, "end": 0.1},
            {"word": "3", "start": 0.2, "end": 0.3},
        ],
    )
    await td.receive_transcript(revision)
    tail = interim("4")
    tail.result.update(
        turn_index=1,
        audio_window_start=0.3,
        audio_window_end=0.4,
        words=[{"word": "4", "start": 0.3, "end": 0.4}],
    )
    await td.receive_transcript(tail)
    assert td.ledger.view().text == "4"
    assert td.ledger.view().missing_reason == "cross_commit_word_timing_incomplete"
    await td.speech_stopped(1000)
    await td.advance(9999)
    assert not any(isinstance(frame, TranscriptionFrame) for frame in out)


@pytest.mark.parametrize(
    "provider,model",
    [
        ("deepgram", "flux-general-en"),
        ("deepgram", "flux-general-multi"),
        ("deepgram", "nova-3"),
        ("assemblyai", "universal-3-5-pro"),
        ("speechmatics", "enhanced"),
        ("soniox", "stt-rt-v5"),
    ],
)
@pytest.mark.parametrize("range_kind", ["missing", "invalid"])
async def test_stable_source_missing_time_blocks_other_sources_until_same_id_recovers(
    provider,
    model,
    range_kind,
):
    """A later unrelated turn is not evidence that a missing source range recovered."""
    from pipecat.frames.frames import TranscriptionFrame

    from src.asr.config import validate_asr_options

    validate_asr_options(
        provider=provider,
        model=model,
        turn_detection_source="self_developed",
        options={},
    )
    td = coordinator()
    td.asr.source_normalizer = SourceNormalizer(provider, model)
    out = []

    async def push(frame, *args, **kwargs):
        out.append(frame)

    def frame(source, text, start=None, end=None):
        if provider == "deepgram" and model.startswith("flux-"):
            payload = {"event": "Update", "turn_index": source, "transcript": text}
            if start is not None:
                payload.update(audio_window_start=start, audio_window_end=end)
        elif provider == "deepgram":
            payload = {"start": source * 0.2, "channel": {"alternatives": [{"transcript": text}]}}
            if start is not None:
                payload["duration"] = end - start
        elif provider == "speechmatics":
            metadata = {"start_time": source * 0.2}
            if end is not None:
                metadata["end_time"] = end
            payload = {
                "message": "AddPartialSegment",
                "segments": [
                    {"speaker_id": "a", "text": text, "metadata": metadata},
                ],
            }
        elif provider == "soniox":
            token = {"text": text, "start_ms": source * 200}
            if end is not None:
                token["end_ms"] = end * 1000
            payload = {"tokens": [token]}
        else:
            payload = {"turn_order": source, "transcript": text}
            if start is not None:
                payload["words"] = [{"text": text, "start": start * 1000, "end": end * 1000}]
        return InterimTranscriptionFrame(text, "", "", result=payload)

    td.push_frame = push
    first = frame(0, "12") if range_kind == "missing" else frame(0, "12", 0, -0.1)
    await td.receive_transcript(first)
    await td.receive_transcript(frame(1, "34", 0.2, 0.4))
    await td.speech_stopped(1000)
    await td.advance(3499)
    assert not any(isinstance(item, TranscriptionFrame) for item in out)
    await td.receive_transcript(frame(0, "12", 0, 0.2))
    await td.advance(3500)
    committed = [item for item in out if isinstance(item, TranscriptionFrame)]
    assert len(committed) == 1 and committed[0].text == "1234"


async def test_watchdog_cannot_commit_while_received_audio_awaits_vad():
    """An arrived frame is not proof of silence until asynchronous VAD resolves it."""
    import asyncio

    from pipecat.audio.vad.vad_analyzer import VADState
    from pipecat.frames.frames import InputAudioRawFrame, TranscriptionFrame
    from pipecat.processors.frame_processor import FrameDirection

    from src.pipeline.custom_td import CustomTDAudioInput

    entered, release = asyncio.Event(), asyncio.Event()
    out = []

    class DelayedVAD:
        state = VADState.STARTING

        async def analyze_audio(self, audio):
            entered.set()
            await release.wait()
            return self.state

    td = coordinator()
    td.clock.media_healthy = False

    async def push(frame, *args, **kwargs):
        out.append(frame)

    td.push_frame = push
    await td.receive_transcript(interim())
    await td.speech_stopped(0)
    audio = CustomTDAudioInput(td, DelayedVAD())
    audio.push_frame = push
    processing = asyncio.create_task(
        audio.process_frame(
            InputAudioRawFrame(bytes(320), 16000, 1),
            FrameDirection.DOWNSTREAM,
        )
    )
    try:
        await asyncio.wait_for(entered.wait(), 1)
        await td.advance(3000)
        assert not any(isinstance(frame, TranscriptionFrame) for frame in out)
        release.set()
        await processing
        assert td._suspected
        assert not any(isinstance(frame, TranscriptionFrame) for frame in out)
        audio.vad.state = VADState.QUIET
        await audio.process_frame(
            InputAudioRawFrame(bytes(320), 16000, 1),
            FrameDirection.DOWNSTREAM,
        )
        committed = [frame for frame in out if isinstance(frame, TranscriptionFrame)]
        assert len(committed) == 1 and committed[0].text == "12"
        assert td._audio_processing == 0
    finally:
        release.set()
        await processing


@pytest.mark.parametrize("failure", ["cancel", "error"])
async def test_vad_analysis_failure_releases_guard_without_claiming_silence(failure):
    """Failure/cancellation cannot strand the guard or turn unknown media into silence."""
    import asyncio

    from pipecat.frames.frames import InputAudioRawFrame, TranscriptionFrame
    from pipecat.processors.frame_processor import FrameDirection

    from src.pipeline.custom_td import CustomTDAudioInput

    entered, release = asyncio.Event(), asyncio.Event()
    out = []

    class FailingVAD:
        async def analyze_audio(self, audio):
            entered.set()
            await release.wait()
            raise RuntimeError("local VAD failed")

    td = coordinator()

    async def push(frame, *args, **kwargs):
        out.append(frame)

    td.push_frame = push
    await td.receive_transcript(interim())
    await td.speech_stopped(0)
    audio = CustomTDAudioInput(td, FailingVAD())
    audio.push_frame = push
    processing = asyncio.create_task(
        audio.process_frame(
            InputAudioRawFrame(bytes(320), 16000, 1),
            FrameDirection.DOWNSTREAM,
        )
    )
    await asyncio.wait_for(entered.wait(), 1)
    if failure == "cancel":
        processing.cancel()
        expected = asyncio.CancelledError
    else:
        release.set()
        expected = RuntimeError
    with pytest.raises(expected):
        await processing
    assert td._audio_processing == 0
    assert not td.clock.media_healthy
    await td.advance(3000)
    assert not any(isinstance(frame, TranscriptionFrame) for frame in out)


async def test_sdk_queued_audio_blocks_deadline_before_vad_begins():
    """Use the SDK's paused input queue, rather than faking its backlog state."""
    import asyncio

    from pipecat.audio.vad.vad_analyzer import VADState
    from pipecat.frames.frames import InputAudioRawFrame, StartFrame, TranscriptionFrame
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.worker import PipelineWorker
    from pipecat.processors.frame_processor import FrameProcessor
    from pipecat.workers.runner import WorkerRunner

    from src.pipeline.custom_td import CustomTDAudioInput

    ready, processed = asyncio.Event(), asyncio.Event()
    callback_called = asyncio.Event()
    out = []

    class StartingVAD:
        async def analyze_audio(self, audio):
            return VADState.STARTING

        async def cleanup(self):
            pass

    class Sink(FrameProcessor):
        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)
            if isinstance(frame, StartFrame):
                ready.set()
            if isinstance(frame, InputAudioRawFrame):
                processed.set()
            if isinstance(frame, TranscriptionFrame):
                out.append(frame)
            await self.push_frame(frame, direction)

    td = coordinator()
    audio = CustomTDAudioInput(td, StartingVAD())
    worker = PipelineWorker(Pipeline([audio, td, Sink()]), enable_rtvi=False)
    runner = WorkerRunner(handle_sigint=False, handle_sigterm=False)
    await runner.add_workers(worker)
    running = asyncio.create_task(runner.run())
    try:
        await asyncio.wait_for(ready.wait(), 2)
        await td.receive_transcript(interim())
        await td.speech_stopped(0)
        await audio.pause_processing_system_frames()

        async def native_callback(processor, frame, direction):
            assert processor is audio
            callback_called.set()

        await audio.queue_frame(
            InputAudioRawFrame(bytes(320), 16000, 1),
            callback=native_callback,
        )
        await td.advance(3000)
        # Commit counters change before downstream queue delivery, so inspect both.
        assert td.responses.user_submission_count == 0
        assert not out
        await audio.resume_processing_system_frames()
        await asyncio.wait_for(processed.wait(), 2)
        await asyncio.wait_for(callback_called.wait(), 2)
        assert td._audio_pending == 0 and td._audio_processing == 0
        assert td._suspected
        assert td.responses.user_submission_count == 0
    finally:
        await audio.resume_processing_system_frames()
        await worker.cancel()
        await asyncio.wait_for(running, 3)


async def test_input_cleanup_discards_queued_audio_without_claiming_silence():
    """SDK cancellation may discard PCM before VAD; cleanup must release its fence safely."""
    from pipecat.frames.frames import InputAudioRawFrame, TranscriptionFrame

    from src.pipeline.custom_td import CustomTDAudioInput

    class UnusedVAD:
        async def cleanup(self):
            pass

    td = coordinator()
    out = []

    async def push(frame, *args, **kwargs):
        out.append(frame)

    td.push_frame = push
    await td.receive_transcript(interim())
    await td.speech_stopped(0)
    audio = CustomTDAudioInput(td, UnusedVAD())
    queued = InputAudioRawFrame(bytes(320), 16000, 1)
    # Before StartFrame, the real SDK retains both queued occurrences without consuming PCM.
    await audio.queue_frame(queued)
    await audio.queue_frame(queued)
    assert td._audio_pending == 2
    await audio.cleanup()
    assert td._audio_pending == 0
    assert not td.clock.media_healthy
    await td.advance(3000)
    assert not any(isinstance(frame, TranscriptionFrame) for frame in out)
    await audio.cleanup()
    assert td._audio_pending == 0


async def test_actual_watchdog_marks_stale_media_without_advancing_a_commit():
    """Run the watchdog with a stale receive timestamp, rather than setting its gap flag."""
    import asyncio
    import time

    from pipecat.frames.frames import TranscriptionFrame

    gap = asyncio.Event()
    out = []

    def record(event):
        if event["event"] == "media_gap":
            gap.set()

    td = coordinator(evidence_sink=record)

    async def push(frame, *args, **kwargs):
        out.append(frame)

    td.push_frame = push
    await td.receive_transcript(interim())
    await td.speech_stopped(0)
    td._audio_ms = 3000
    td._last_audio_wall = time.monotonic() - 1
    td._watchdog = asyncio.create_task(td._watch())
    try:
        await asyncio.wait_for(gap.wait(), 1)
        assert not td.clock.media_healthy
        assert td.responses.user_submission_count == 0
        assert not any(isinstance(frame, TranscriptionFrame) for frame in out)
    finally:
        await td._close_tasks()


def test_pending_mixed_and_new_english_source_keep_independent_word_boundaries():
    """The coordinator's retained-input merge must share the ledger's boundary policy."""
    from src.asr.transcript import SourceSegment, TranscriptView

    td = coordinator()
    first = SourceSegment(0, "first", 1, 0, 1000, "one", False)
    td._pending_mixed["first"] = TranscriptView("one", False, (first,))
    td.ledger.apply(SourceSegment(0, "second", 1, 1000, 2000, "two", True))
    assert td._current_view().text == "one two"


async def test_incomplete_cross_range_final_never_restarts_with_a_missing_negation():
    """Retain full provider evidence while refusing an unsafe Final reconstruction."""
    from pipecat.frames.frames import TranscriptionFrame

    from src.pipeline.td_strategies import TDResponseRestartFrame

    td = coordinator()
    td.asr.source_normalizer = SourceNormalizer("deepgram", "nova-3", sample_rate=16000)
    frames = []

    async def push(frame, *args, **kwargs):
        frames.append(frame)

    td.push_frame = push
    await td.receive_transcript(
        InterimTranscriptionFrame(
            "I agree",
            "",
            "",
            result={
                "start": 0,
                "duration": 1,
                "is_final": False,
                "channel": {"alternatives": [{"transcript": "I agree"}]},
            },
        )
    )
    await td.speech_stopped(1000)
    await td.advance(3500)
    assert len([f for f in frames if isinstance(f, TranscriptionFrame)]) == 1
    await td.receive_transcript(
        TranscriptionFrame(
            "I do not agree now",
            "",
            "",
            result={
                "start": 0,
                "duration": 2,
                "is_final": True,
                "channel": {
                    "alternatives": [
                        {
                            "transcript": "I do not agree now",
                            "words": [
                                {"word": "I", "start": 0, "end": 0.1},
                                {"word": "do"},
                                {"word": "not"},
                                {"word": "agree", "start": 0.4, "end": 0.9},
                                {"word": "now", "start": 1.1, "end": 1.5},
                            ],
                        }
                    ]
                },
            },
        )
    )
    assert not any(isinstance(f, TDResponseRestartFrame) for f in frames)
    assert td.ledger.view().missing_reason == "cross_commit_word_timing_incomplete"


async def test_new_vad_diagnostics_cannot_block_audio_on_sink_failure():
    """Additional state evidence is best effort even when its sink fails."""
    from pipecat.audio.vad.vad_analyzer import VADState
    from pipecat.frames.frames import InputAudioRawFrame
    from pipecat.processors.frame_processor import FrameDirection

    from src.pipeline.custom_td import CustomTDAudioInput

    events = []

    def broken(event):
        events.append(event)
        raise RuntimeError("test evidence storage unavailable")

    class StartingVAD:
        async def analyze_audio(self, data):
            return VADState.STARTING

        async def cleanup(self):
            pass

    td = coordinator(evidence_sink=broken)
    audio = CustomTDAudioInput(td, StartingVAD())
    forwarded = []

    async def push(frame, *args, **kwargs):
        forwarded.append(frame)

    audio.push_frame = push
    frame = InputAudioRawFrame(bytes(640), sample_rate=16000, num_channels=1)
    try:
        await audio.process_frame(frame, FrameDirection.DOWNSTREAM)
        assert forwarded == [frame]
        assert events[0]["event"] == "vad_state_changed"
        assert events[0]["trigger"] == "local_vad"
        assert events[0]["input_audio_ms"] == 20
    finally:
        await audio.cleanup()
        await td.cleanup()


@pytest.mark.parametrize("resume", [False, True])
@pytest.mark.parametrize("target", [3, 11])
async def test_nova_cumulative_merged_digits_stay_local_until_complete(resume, target):
    """A provider's merged numeric word must not cross a local-only commit fence."""
    from pipecat.frames.frames import TranscriptionFrame

    from src.asr.td_config import IdentifierRuleSettings
    from src.pipeline.identifier import IdentifierCollection, IdentifierVocabulary
    from src.pipeline.identifier_rules import IdentifierRules
    from tests.test_td_rule_settings import priority_settings

    config = priority_settings()
    config["collection"]["target_length"] = target
    config["wpm_threshold"] = 200
    state = IdentifierCollection(
        IdentifierVocabulary({"1": ["1"], "2": ["2"], "3": ["3"]}), target_length=target
    )
    offers = []
    td = coordinator(
        identifier_rules=IdentifierRules(IdentifierRuleSettings.model_validate(config), state),
        identifier_output=lambda snapshot, evaluation, turn: offers.append(
            (snapshot.text, snapshot.final)
        ),
    )
    td.asr.source_normalizer = SourceNormalizer("deepgram", "nova-3", sample_rate=16000)
    frames = []

    async def push(frame, *args, **kwargs):
        frames.append(frame)

    td.push_frame = push
    td.assistant_context("编号")

    def nova(text, end, final=False):
        """Replay actual Nova cumulative source shape, with one merged word."""
        return InterimTranscriptionFrame(
            text,
            "",
            "",
            result={
                "start": 0,
                "duration": end,
                "is_final": final,
                "channel": {
                    "alternatives": [
                        {"transcript": text, "words": [{"word": text, "start": 0, "end": end}]}
                    ]
                },
            },
        )

    await td.speech_started()
    await td.receive_transcript(nova("12", 1.2))
    await td.speech_stopped(1200)
    await td.advance(1550)
    assert state.value == "12"
    assert offers == [("12", False)]
    assert td.responses.user_submission_count == 0
    if resume:
        await td.speech_started()
    await td.receive_transcript(nova("123", 2.4))
    assert offers == [("12", False)]
    await td.receive_transcript(nova("123", 2.4, True))
    assert offers == [("12", False)]
    if resume:
        await td.speech_stopped(2400)
    await td.advance(6500)
    assert state.value == "123"
    assert td.source_evidence_error is None
    commits = [f for f in frames if isinstance(f, TranscriptionFrame)]
    assert len(commits) == (1 if target == 3 else 0)
    if commits:
        assert commits[0].text == "123"
    if target == 11:
        await td.advance(10400 if resume else 9200)
        from pipecat.frames.frames import TTSSpeakFrame

        assert len([f for f in frames if isinstance(f, TTSSpeakFrame)]) == 1


async def test_late_local_correction_is_echoed_but_not_in_next_question():
    """Late same-range correction remains local even after its candidate is closed."""
    from pipecat.frames.frames import TranscriptionFrame

    from src.asr.td_config import IdentifierRuleSettings
    from src.pipeline.identifier import IdentifierCollection, IdentifierVocabulary
    from src.pipeline.identifier_rules import IdentifierRules
    from tests.test_td_rule_settings import priority_settings

    config = priority_settings()
    config["collection"] = None
    config["wpm_threshold"] = 200
    state = IdentifierCollection(
        IdentifierVocabulary({str(i): [str(i)] for i in range(4)}), target_length=11
    )
    echoes, frames = [], []
    td = coordinator(
        identifier_rules=IdentifierRules(IdentifierRuleSettings.model_validate(config), state),
        identifier_output=lambda snapshot, evaluation, turn: echoes.append(snapshot.text),
    )

    async def push(frame, *args, **kwargs):
        frames.append(frame)

    td.push_frame = push
    td.assistant_context("编号")
    await td.speech_started()
    await td.receive_transcript(interim("12"))
    await td.speech_stopped(1000)
    await td.advance(1350)
    correction = interim("13")
    correction.result["event"] = "EndOfTurn"
    await td.receive_transcript(correction)
    await td.receive_transcript(correction)
    assert echoes == ["12", "13"]
    await td.speech_started()
    question = interim("hello")
    question.result.update(
        turn_index=1,
        audio_window_start=1,
        audio_window_end=2,
        words=[{"word": "hello", "start": 1, "end": 2}],
    )
    await td.receive_transcript(question)
    await td.speech_stopped(2000)
    await td.advance(4500)
    assert [f.text for f in frames if isinstance(f, TranscriptionFrame)] == ["hello"]
    assert state.value == "13"


async def test_clear_rejects_late_cumulative_nova_source():
    """Clearing an identifier must invalidate every later revision of its old source."""
    target = 11
    from pipecat.frames.frames import TranscriptionFrame

    from src.asr.td_config import IdentifierRuleSettings
    from src.pipeline.identifier import IdentifierCollection, IdentifierVocabulary
    from src.pipeline.identifier_rules import IdentifierRules
    from tests.test_td_rule_settings import priority_settings

    config = priority_settings()
    config["collection"]["target_length"] = target
    config["wpm_threshold"] = 200
    state = IdentifierCollection(
        IdentifierVocabulary({"1": ["1"], "2": ["2"], "3": ["3"]}), target_length=target
    )
    offers = []
    td = coordinator(
        identifier_rules=IdentifierRules(IdentifierRuleSettings.model_validate(config), state),
        identifier_output=lambda snapshot, evaluation, turn: offers.append(
            (snapshot.text, snapshot.final)
        ),
    )
    td.asr.source_normalizer = SourceNormalizer("deepgram", "nova-3", sample_rate=16000)
    frames = []

    async def push(frame, *args, **kwargs):
        frames.append(frame)

    td.push_frame = push
    td.assistant_context("编号")

    def nova(text, end, final=False):
        """Replay actual Nova cumulative source shape, with one merged word."""
        return InterimTranscriptionFrame(
            text,
            "",
            "",
            result={
                "start": 0,
                "duration": end,
                "is_final": final,
                "channel": {
                    "alternatives": [
                        {"transcript": text, "words": [{"word": text, "start": 0, "end": end}]}
                    ]
                },
            },
        )

    await td.speech_started()
    await td.receive_transcript(nova("12", 1.2))
    await td.speech_stopped(1200)
    await td.advance(1550)
    assert state.value == "12"
    assert offers == [("12", False)]
    assert td.responses.user_submission_count == 0
    state.clear_tool(state.bind_source(0, "clear", 1, "clear"))
    await td.speech_started()
    await td.receive_transcript(nova("123", 2.4))
    await td.receive_transcript(nova("123", 2.4, True))
    await td.speech_stopped(2400)
    await td.advance(10400)
    assert offers == [("12", False)]
    assert state.value == ""
    assert not any(isinstance(f, TranscriptionFrame) for f in frames)
    assert td.source_evidence_error is None
