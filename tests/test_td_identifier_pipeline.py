"""Local-real SDK: TD -> existing aggregators -> scoped LLM -> tools -> continuation/Final."""

import asyncio
from types import MethodType

import pytest
from pipecat.frames.frames import FunctionCallFromLLM, LLMTextFrame, StartFrame, TranscriptionFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext, is_given
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.workers.runner import WorkerRunner

from src.asr.td_config import IdentifierRuleSettings
from src.llm.scoped import ScopedOpenAILLMService
from src.pipeline.identifier import IdentifierCollection, IdentifierVocabulary
from src.pipeline.identifier_rules import IdentifierRules
from src.pipeline.identifier_tools import IdentifierTools
from src.pipeline.response_revision import ResponseRevisions
from src.pipeline.response_scope import ResponseScope
from src.pipeline.td_strategies import create_custom_aggregators
from tests.test_td_rule_settings import priority_settings
from tests.test_td_runtime import coordinator, interim


@pytest.mark.parametrize("input_path", ["mixed", "pure", "retained_mixed"])
async def test_real_sdk_identifier_tool_continuation_and_final_share_one_effect(input_path):
    """Use actual SDK dispatch/context aggregation; replace only external LLM inference."""
    pure_input = input_path == "pure"
    retained_mixed = input_path == "retained_mixed"
    owner = ResponseRevisions()
    events = []
    boundary = ResponseScope(owner, events.append)
    state = IdentifierCollection(
        IdentifierVocabulary({"1": ["1"], "2": ["2"], "3": ["3"]}), target_length=3
    )
    handlers = IdentifierTools(boundary, state, keywords=("编号",))
    boundary.enrich_context = handlers.enrich_context
    td = coordinator(
        responses=owner,
        bind_input=handlers.bind_snapshot,
        identifier_rules=IdentifierRules(
            IdentifierRuleSettings.model_validate(priority_settings()), state
        ),
    )
    td.assistant_context("请提供编号")
    context = LLMContext(tools=handlers.schemas())
    user, assistant = create_custom_aggregators(context, td.authority)
    llm = ScopedOpenAILLMService(api_key="test-fixture-no-network", response_scope=boundary)
    invoked = set()
    ready, replied = asyncio.Event(), asyncio.Event()
    responses = []

    async def infer(self, snapshot):
        version = boundary.provenance(snapshot)
        if pure_input:
            assert not is_given(snapshot.tools)
            assert state.value == "123"
            await self.push_frame(LLMTextFrame("verified:" + version.response_id))
        elif version.response_id not in invoked:
            invoked.add(version.response_id)
            await self.run_function_calls(
                [
                    FunctionCallFromLLM(
                        function_name="submit_identifier",
                        tool_call_id=version.response_id,
                        arguments={"identifier": "123"},
                        context=snapshot,
                    )
                ]
            )
        else:
            messages = snapshot.get_messages()
            assert any(
                message.get("role") == "tool" and "123" in str(message.get("content"))
                for message in messages
            )
            assert any('"value": "123"' in str(message.get("content")) for message in messages)
            await self.push_frame(LLMTextFrame("verified:" + version.response_id))

    llm._process_context = MethodType(infer, llm)

    class Sink(FrameProcessor):
        """Observe real downstream frames after tool result aggregation and reinference."""

        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)
            if isinstance(frame, StartFrame):
                ready.set()
            if (
                direction is FrameDirection.DOWNSTREAM
                and isinstance(frame, LLMTextFrame)
                and frame.text.startswith("verified:")
            ):
                responses.append(frame.text)
                replied.set()
            await self.push_frame(frame, direction)

    worker = PipelineWorker(Pipeline([td, user, llm, Sink(), assistant]), enable_rtvi=False)
    runner = WorkerRunner(handle_sigint=False, handle_sigterm=False)
    await runner.add_workers(worker)
    running = asyncio.create_task(runner.run())
    try:
        await asyncio.wait_for(ready.wait(), 3)
        await td.speech_started()
        text = "123" if pure_input else "号码123"
        if retained_mixed:
            first = interim("1")
            first.result.update(audio_window_end=2, words=[{"word": "1", "start": 0, "end": 2}])
            await td.receive_transcript(first)
            await td.speech_stopped(2000)
            await td.advance(2350)
            assert state.value == "1" and owner.user_submission_count == 0
            await td.speech_started()
            revised = interim("号码1")
            revised.result.update(
                event="EndOfTurn",
                audio_window_end=2,
                words=[{"word": "号码1", "start": 0, "end": 2}],
            )
            await td.receive_transcript(revised)
            following = interim("23")
            following.result.update(
                event="EndOfTurn",
                turn_index=1,
                audio_window_start=2,
                audio_window_end=4,
                words=[{"word": "23", "start": 2, "end": 4}],
            )
            await td.receive_transcript(following)
            await td.speech_stopped(4000)
            await td.advance(6500)
        else:
            await td.receive_transcript(interim(text))
            await td.speech_stopped(1000)
            await td.advance(3500)
        await asyncio.wait_for(replied.wait(), 3)
        if retained_mixed:
            assert owner.current.text == "号码123"
            assert state.value == "123" and owner.user_submission_count == 1
            assert len(invoked) == 1
            return
        replied.clear()
        await td.receive_transcript(
            TranscriptionFrame(
                text,
                "",
                "",
                result={
                    "event": "EndOfTurn",
                    "turn_index": 0,
                    "transcript": text,
                    "audio_window_start": 0,
                    "audio_window_end": 1,
                    "words": [{"word": text, "start": 0, "end": 1}],
                },
            )
        )
        await asyncio.wait_for(replied.wait(), 3)
        assert state.value == "123" and owner.user_submission_count == 1
        assert responses == ["verified:1:1", "verified:1:2"]
        starts = [event for event in events if event["event"] == "tool_started"]
        assert len(starts) == (0 if pure_input else 1)
        results = [event for event in events if event["event"] == "identifier_tool_result"]
        assert len(results) == (0 if pure_input else 1)
        if results:
            assert results[0]["value"] == "123" and results[0]["count"] == 3
            assert results[0]["source_ranges"][0]["source_id"] == "0"
            assert results[0]["source_ranges"][0]["source_revision"] == 1
    finally:
        await worker.cancel()
        await asyncio.wait_for(running, 3)
        await boundary.close()
        handlers.close()
