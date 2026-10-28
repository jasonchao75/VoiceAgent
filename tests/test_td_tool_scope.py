"""M2-5: immutable request provenance and effect deduplication across Final restart."""

from importlib import import_module, util
from types import SimpleNamespace

from pipecat.processors.aggregators.llm_context import LLMContext

from src.pipeline.response_revision import ResponseRevisions


def scope():
    """Require the production tool boundary, rather than a test-only dedup model."""
    assert util.find_spec("src.pipeline.response_scope") is not None, "Response-scoped tools absent"
    module = import_module("src.pipeline.response_scope")
    owner = ResponseRevisions()
    owner.submit(turn_id="1", source_ids=((0, "a"),), text="faster", final=False)
    return module.ResponseScope(owner), owner


def params(context, result):
    """Use the same context field that the locked SDK carries into background tools."""

    async def callback(value):
        result.append(value)

    return SimpleNamespace(
        context=context,
        result_callback=callback,
        function_name="set_speech_speed",
        arguments={"action": "faster"},
    )


async def test_successful_effect_is_not_replayed_after_final():
    """A new tool_call_id/response version must not apply the same speed change again."""
    boundary, owner = scope()
    original = boundary.bind(LLMContext())
    outputs, actions = [], []

    async def apply():
        actions.append("faster")
        return {"status": "applied", "old_speed": 1, "effective_speed": 1.1}

    await boundary.execute(params(original, outputs), apply)
    owner.finalize(turn_id="1", source_ids=((0, "a"),), revision=2, text="faster please")
    revised = boundary.bind(LLMContext())
    await boundary.execute(params(revised, outputs), apply)
    assert actions == ["faster"] and len(outputs) == 2
    assert outputs[-1]["effective_speed"] == 1.1
    await boundary.close()


async def test_old_context_cannot_act_on_new_user_turn():
    """Reading global current state at callback time would incorrectly authorize this call."""
    boundary, owner = scope()
    old = boundary.bind(LLMContext())
    owner.begin_speech()
    owner.submit(turn_id="2", source_ids=((0, "b"),), text="new", final=True)
    actions, outputs = [], []

    async def apply():
        actions.append("wrong")
        return {"status": "applied"}

    await boundary.execute(params(old, outputs), apply)
    assert actions == [] and outputs == []
    await boundary.close()


async def test_final_arriving_during_effect_does_not_cancel_or_duplicate_it():
    """Once sent, a bounded provider update settles once even if old LLM work is cancelled."""
    import asyncio

    boundary, owner = scope()
    original = boundary.bind(LLMContext())
    entered, release = asyncio.Event(), asyncio.Event()
    actions, outputs = [], []

    async def apply():
        actions.append("faster")
        entered.set()
        await release.wait()
        return {"status": "applied", "effective_speed": 1.1}

    pending = asyncio.create_task(boundary.execute(params(original, outputs), apply))
    await entered.wait()
    owner.finalize(turn_id="1", source_ids=((0, "a"),), revision=2, text="faster")
    pending.cancel()
    await asyncio.gather(pending, return_exceptions=True)
    revised = boundary.bind(LLMContext())
    retry = asyncio.create_task(boundary.execute(params(revised, outputs), apply))
    release.set()
    await retry
    assert actions == ["faster"] and len(outputs) == 1
    await boundary.close()


async def test_failure_result_is_not_automatically_retried_by_reanswer():
    """An ambiguous provider timeout must not become another automatic side effect."""
    boundary, owner = scope()
    actions, outputs = [], []

    async def fail():
        actions.append("attempt")
        return {"status": "failed", "reason": "timeout"}

    await boundary.execute(params(boundary.bind(LLMContext()), outputs), fail)
    owner.finalize(turn_id="1", source_ids=((0, "a"),), revision=2, text="faster")
    await boundary.execute(params(boundary.bind(LLMContext()), outputs), fail)
    assert actions == ["attempt"] and outputs[-1]["status"] == "failed"
    await boundary.close()


async def test_locked_sdk_background_tool_runner_preserves_source_identity():
    """Exercise SDK scheduling and lifecycle frames without an external inference request."""
    import asyncio
    from types import MethodType

    from pipecat.frames.frames import (
        FunctionCallFromLLM,
        FunctionCallResultFrame,
        LLMContextFrame,
        StartFrame,
    )
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.worker import PipelineWorker
    from pipecat.processors.frame_processor import FrameProcessor
    from pipecat.workers.runner import WorkerRunner

    from src.llm.scoped import ScopedOpenAILLMService

    boundary, owner = scope()
    ready, delivered = asyncio.Event(), asyncio.Event()
    actions, contexts, results = [], [], []
    llm = ScopedOpenAILLMService(
        api_key="test-fixture-no-network", response_scope=boundary, run_in_parallel=False
    )

    async def apply(params):
        contexts.append(params.context)

        async def operation():
            actions.append("faster")
            return {"status": "applied", "effective_speed": 1.1}

        await boundary.execute(params, operation)

    async def infer(self, context):
        await self.run_function_calls(
            [
                FunctionCallFromLLM(
                    function_name="set_speech_speed",
                    tool_call_id=f"call-{len(contexts)}",
                    arguments={"action": "faster"},
                    context=context,
                )
            ]
        )

    llm._process_context = MethodType(infer, llm)
    llm.register_function("set_speech_speed", apply)

    class Sink(FrameProcessor):
        """Observe actual downstream SDK result frames, including background callbacks."""

        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)
            if isinstance(frame, StartFrame):
                ready.set()
            if isinstance(frame, FunctionCallResultFrame):
                results.append(frame.result)
                delivered.set()
            await self.push_frame(frame, direction)

    worker = PipelineWorker(Pipeline([llm, Sink()]), enable_rtvi=False)
    runner = WorkerRunner(handle_sigint=False, handle_sigterm=False)
    await runner.add_workers(worker)
    running = asyncio.create_task(runner.run())
    try:
        await asyncio.wait_for(ready.wait(), 3)
        original = LLMContext(messages=[{"role": "user", "content": "faster"}])
        await worker.queue_frames([LLMContextFrame(original)])
        await asyncio.wait_for(delivered.wait(), 3)
        delivered.clear()
        owner.finalize(turn_id="1", source_ids=((0, "a"),), revision=2, text="faster please")
        original.get_messages()[0]["content"] = "faster please"
        await worker.queue_frames([LLMContextFrame(original)])
        await asyncio.wait_for(delivered.wait(), 3)
        assert len(results) == 2 and actions == ["faster"]
        assert contexts[0] is not original and contexts[1] is not contexts[0]
        assert contexts[0].get_messages()[0]["content"] == "faster"
        assert boundary.provenance(contexts[0]).response_id == "1:1"
        assert boundary.provenance(contexts[1]).response_id == "1:2"
    finally:
        await worker.cancel()
        await asyncio.wait_for(running, 3)
        await boundary.close()


async def test_final_before_scheduled_effect_allows_current_response_to_execute():
    """A skipped old task is not evidence that an operation has already been attempted."""
    import asyncio

    boundary, owner = scope()
    actions, outputs = [], []
    original = boundary.bind(LLMContext())

    async def apply():
        actions.append("faster")
        return {"status": "applied"}

    pending = asyncio.create_task(boundary.execute(params(original, outputs), apply))
    # execute schedules its business task then yields before that task starts.
    await asyncio.sleep(0)
    owner.finalize(turn_id="1", source_ids=((0, "a"),), revision=2, text="faster please")
    await pending
    await boundary.execute(params(boundary.bind(LLMContext()), outputs), apply)
    assert actions == ["faster"] and outputs == [{"status": "applied"}]
    await boundary.close()


async def test_llm_tokens_after_final_are_rejected_at_sdk_producer():
    """A provider continuing after cancellation cannot emit old tokens or end markers."""
    import asyncio
    from types import MethodType

    from pipecat.frames.frames import (
        LLMContextFrame,
        LLMFullResponseEndFrame,
        LLMFullResponseStartFrame,
        LLMTextFrame,
        StartFrame,
    )
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.worker import PipelineWorker
    from pipecat.processors.frame_processor import FrameProcessor
    from pipecat.workers.runner import WorkerRunner

    from src.llm.scoped import ScopedOpenAILLMService

    boundary, owner = scope()
    ready, entered, release, ended = (asyncio.Event() for _ in range(4))
    output = []
    llm = ScopedOpenAILLMService(api_key="test-fixture-no-network", response_scope=boundary)

    async def infer(self, context):
        await self.push_frame(LLMTextFrame("before"))
        entered.set()
        await release.wait()
        await self.push_frame(LLMTextFrame("stale"))
        ended.set()

    llm._process_context = MethodType(infer, llm)

    class Sink(FrameProcessor):
        """Capture output after the real SDK producer filter."""

        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)
            if isinstance(frame, StartFrame):
                ready.set()
            if isinstance(
                frame, (LLMTextFrame, LLMFullResponseStartFrame, LLMFullResponseEndFrame)
            ):
                output.append(frame)
            await self.push_frame(frame, direction)

    worker = PipelineWorker(Pipeline([llm, Sink()]), enable_rtvi=False)
    runner = WorkerRunner(handle_sigint=False, handle_sigterm=False)
    await runner.add_workers(worker)
    running = asyncio.create_task(runner.run())
    try:
        await asyncio.wait_for(ready.wait(), 3)
        await worker.queue_frames([LLMContextFrame(LLMContext())])
        await asyncio.wait_for(entered.wait(), 3)
        owner.finalize(turn_id="1", source_ids=((0, "a"),), revision=2, text="faster please")
        release.set()
        await asyncio.wait_for(ended.wait(), 3)
        # Drain the producer and the downstream data task, without a network service.
        await worker.queue_frames([LLMContextFrame(LLMContext())])
        for _ in range(20):
            await asyncio.sleep(0)
        texts = [f for f in output if isinstance(f, LLMTextFrame)]
        assert not any(f.text == "stale" and f.metadata["td_response_id"] == "1:1" for f in texts)
        assert any(f.text == "before" for f in texts)
        assert not any(
            isinstance(f, LLMFullResponseEndFrame) and f.metadata.get("td_response_id") == "1:1"
            for f in output
        )
    finally:
        release.set()
        await worker.cancel()
        await asyncio.wait_for(running, 3)
        await boundary.close()
