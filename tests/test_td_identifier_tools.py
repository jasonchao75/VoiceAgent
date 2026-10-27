"""NUM-03: actual LLM tool handlers share local state and captured input authority."""

from importlib import import_module, util
from types import SimpleNamespace

import pytest
from pipecat.processors.aggregators.llm_context import LLMContext

from src.pipeline.response_revision import ResponseRevisions
from src.pipeline.response_scope import ResponseScope
from tests.test_td_identifier import collection


def tools():
    """Require production tool schemas, not a simulated LLM text interpreter."""
    assert util.find_spec("src.pipeline.identifier_tools") is not None, "Identifier tools absent"
    state = collection()
    owner = ResponseRevisions()
    version = owner.submit(turn_id="1", source_ids=((0, "a"),), text="号码123", final=False)
    boundary = ResponseScope(owner)
    handlers = import_module("src.pipeline.identifier_tools").IdentifierTools(boundary, state)
    source = state.bind_source(0, "a", 1, version.text)
    handlers.bind_response(version, source)
    return handlers, boundary, owner, state


def params(boundary, name, arguments, outputs):
    """Capture the inference snapshot before any later clear or source revision."""

    async def result(value):
        outputs.append(value)

    return SimpleNamespace(
        context=boundary.bind(LLMContext()),
        function_name=name,
        arguments=arguments,
        result_callback=result,
    )


async def test_submit_schema_handler_mutates_only_proven_source_and_returns_actual_state():
    handlers, boundary, owner, state = tools()
    schemas = {s.name: s for s in handlers.schemas()}
    assert set(schemas) == {"submit_identifier", "clear_identifier"}
    output = []
    await schemas["submit_identifier"].handler(
        params(boundary, "submit_identifier", {"identifier": "123"}, output)
    )
    assert state.value == "123" and output[-1]["status"] == "submitted"
    await boundary.close()


async def test_hallucinated_number_and_unbound_source_never_change_collection():
    handlers, boundary, owner, state = tools()
    output = []
    await handlers.submit(params(boundary, "submit_identifier", {"identifier": "321"}, output))
    assert state.value == "" and output[-1]["status"] == "invalid"
    owner.begin_speech()
    owner.submit(turn_id="2", source_ids=((0, "b"),), text="new", final=True)
    await handlers.submit(params(boundary, "submit_identifier", {"identifier": "123"}, output))
    assert state.value == "" and output[-1]["status"] == "stale"
    await boundary.close()


async def test_clear_reanswer_does_not_clear_a_new_collection_generation():
    handlers, boundary, owner, state = tools()
    output = []
    await handlers.clear(params(boundary, "clear_identifier", {}, output))
    new = state.bind_source(0, "b", 1, "12")
    state.collect_local(new)
    restart = owner.finalize(turn_id="1", source_ids=((0, "a"),), revision=2, text="号码123")
    handlers.bind_response(restart.new_response, state.bind_source(0, "a", 2, "号码123"))
    await handlers.clear(params(boundary, "clear_identifier", {}, output))
    assert state.value == "12" and state.generation == 1
    assert output[-1]["status"] == "superseded" and output[-1]["value"] == "12"
    await boundary.close()


async def test_clear_then_submit_from_the_old_generation_is_rejected():
    handlers, boundary, owner, state = tools()
    output = []
    captured = params(boundary, "submit_identifier", {"identifier": "123"}, output)
    await handlers.clear(params(boundary, "clear_identifier", {}, output))
    await handlers.submit(captured)
    assert state.value == "" and output[-1]["status"] == "stale"
    await boundary.close()


def test_context_contains_verified_state_without_mutating_conversation_history():
    handlers, boundary, owner, state = tools()
    source = state.bind_source(0, "a", 1, "号码123")
    state.submit_tool(source, "123")
    original = LLMContext(messages=[{"role": "user", "content": "号码123"}])
    boundary.enrich_context = handlers.enrich_context
    snapshot = boundary.bind(original)
    assert len(original.get_messages()) == 1
    assert any('"value": "123"' in str(m.get("content")) for m in snapshot.get_messages())
    assert any('"target_length": 3' in str(m.get("content")) for m in snapshot.get_messages())


async def test_same_mixed_final_keeps_applied_value_and_reanswer_does_not_replay():
    from src.asr.transcript import SourceSegment, TranscriptView

    handlers, boundary, owner, state = tools()
    snapshot = TranscriptView(
        "号码123", False, (SourceSegment(0, "a", 1, 0, 1000, "号码123", False),)
    )
    handlers.bind_snapshot(owner.current, snapshot, "编号")
    outputs = []
    await handlers.submit(params(boundary, "submit_identifier", {"identifier": "123"}, outputs))
    restart = owner.finalize(turn_id="1", source_ids=((0, "a"),), revision=2, text="号码123")
    final = TranscriptView("号码123", True, (SourceSegment(0, "a", 2, 0, 1000, "号码123", True),))
    handlers.bind_snapshot(restart.new_response, final, "编号")
    await handlers.submit(params(boundary, "submit_identifier", {"identifier": "123"}, outputs))
    assert state.value == "123" and outputs[-1]["value"] == "123"


async def test_reanswer_cannot_reuse_success_for_number_absent_from_revised_input():
    from src.asr.transcript import SourceSegment, TranscriptView

    handlers, boundary, owner, state = tools()
    outputs = []
    await handlers.submit(params(boundary, "submit_identifier", {"identifier": "123"}, outputs))
    restart = owner.finalize(turn_id="1", source_ids=((0, "a"),), revision=2, text="号码321")
    snapshot = TranscriptView(
        "号码321", True, (SourceSegment(0, "a", 2, 0, 1000, "号码321", True),)
    )
    handlers.bind_snapshot(restart.new_response, snapshot, "编号")
    await handlers.submit(params(boundary, "submit_identifier", {"identifier": "123"}, outputs))
    assert outputs[-1]["status"] == "invalid"
    assert state.value == "123"


def test_already_collected_pure_input_has_no_extra_identifier_tools_in_inference():
    """Local collection must not ask the LLM to submit the same pure number again."""
    handlers, boundary, owner, state = tools()
    owner.begin_speech()
    version = owner.submit(turn_id="2", source_ids=((0, "b"),), text="123", final=True)
    source = state.bind_source(0, "b", 1, "123")
    state.collect_local(source)
    handlers.bind_response(version, source)
    boundary.enrich_context = handlers.enrich_context
    context = LLMContext(tools=handlers.schemas())
    snapshot = boundary.bind(context)
    assert len(context.tools.standard_tools) == 2
    from pipecat.processors.aggregators.llm_context import is_given

    assert not is_given(snapshot.tools)


async def test_invalid_tool_arguments_do_not_change_collection_success_proof():
    """A rejected tool call cannot silently authorize a future collection reset."""
    from src.asr.transcript import SourceSegment, TranscriptView

    handlers, boundary, owner, state = tools()
    restart = owner.finalize(turn_id="1", source_ids=((0, "a"),), revision=2, text="号码123")
    snapshot = TranscriptView(
        "号码123", True, (SourceSegment(0, "a", 2, 0, 1000, "号码123", True),)
    )
    handlers.bind_snapshot(restart.new_response, snapshot, "编号")
    source = state.bind_snapshot(snapshot)
    state.submit_tool(source, "123")
    assert not state.successful
    output = []
    await handlers.submit(
        params(boundary, "submit_identifier", {"identifier": "123", "unexpected": True}, output)
    )
    assert output[-1]["status"] == "invalid" and not state.successful
    await boundary.close()


async def test_parallel_submit_clear_delivers_actual_state_not_a_stale_success_snapshot():
    """SDK parallel tools must not claim a cleared value is still the current collection."""
    import asyncio

    handlers, boundary, owner, state = tools()
    observed = []

    async def result(value):
        observed.append((value["value"], state.value, value["status"]))

    submit = params(boundary, "submit_identifier", {"identifier": "123"}, [])
    clear = params(boundary, "clear_identifier", {}, [])
    submit.result_callback = result
    clear.result_callback = result
    await asyncio.gather(handlers.submit(submit), handlers.clear(clear))
    assert state.value == ""
    assert all(reported == actual for reported, actual, status in observed)
    await boundary.close()


async def test_parallel_replacements_report_current_value_at_each_delivery():
    """Two allowed numbers in one input can replace each other but cannot report stale state."""
    import asyncio

    handlers, boundary, owner, state = tools()
    restart = owner.finalize(turn_id="1", source_ids=((0, "a"),), revision=2, text="号码123与321")
    source = state.bind_source(0, "a", 2, "号码123与321")
    handlers.bind_response(restart.new_response, source)
    observed = []

    async def result(value):
        observed.append((value["value"], state.value))

    first = params(boundary, "submit_identifier", {"identifier": "123"}, [])
    second = params(boundary, "submit_identifier", {"identifier": "321"}, [])
    first.result_callback = result
    second.result_callback = result
    await asyncio.gather(handlers.submit(first), handlers.submit(second))
    assert observed and all(reported == actual for reported, actual in observed)
    await boundary.close()


@pytest.mark.parametrize("new_final", [True, False])
async def test_new_mixed_input_after_success_resets_only_when_valid_submit_runs(new_final):
    """Questions/invalid parameters preserve the old number; accepted new provision starts fresh."""
    from src.asr.transcript import SourceSegment, TranscriptView

    handlers, boundary, owner, state = tools()
    first = owner.finalize(turn_id="1", source_ids=((0, "a"),), revision=2, text="号码123")
    snapshot = TranscriptView(
        "号码123", True, (SourceSegment(0, "a", 2, 0, 1000, "号码123", True),)
    )
    handlers.bind_snapshot(first.new_response, snapshot, "编号")
    output = []
    await handlers.submit(params(boundary, "submit_identifier", {"identifier": "123"}, output))
    assert state.successful
    owner.begin_speech()
    version = owner.submit(turn_id="2", source_ids=((0, "b"),), text="新的号码321", final=new_final)
    next_input = TranscriptView(
        "新的号码321", new_final, (SourceSegment(0, "b", 1, 1000, 2000, "新的号码321", new_final),)
    )
    handlers.bind_snapshot(version, next_input, "请提供下一个编号")
    assert state.value == "123" and state.generation == 0
    await handlers.submit(params(boundary, "submit_identifier", {"identifier": "111"}, output))
    assert output[-1]["status"] == "invalid" and state.value == "123"
    await handlers.submit(params(boundary, "submit_identifier", {"identifier": "321"}, output))
    assert state.value == "321" and state.generation == 1
    await handlers.submit(params(boundary, "submit_identifier", {"identifier": "321"}, output))
    assert state.value == "321" and state.generation == 1
    if not new_final:
        revised = owner.finalize(
            turn_id="2", source_ids=((0, "b"),), revision=2, text="新的号码321"
        )
        final_snapshot = TranscriptView(
            "新的号码321", True, (SourceSegment(0, "b", 2, 1000, 2000, "新的号码321", True),)
        )
        handlers.bind_snapshot(revised.new_response, final_snapshot, "编号")
        await handlers.submit(params(boundary, "submit_identifier", {"identifier": "321"}, output))
        assert state.value == "321" and state.generation == 1 and state.successful
    await boundary.close()
