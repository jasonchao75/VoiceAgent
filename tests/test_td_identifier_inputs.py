"""NUM-03/ASR-03: source groups and clipped audio extents share one identifier state."""

from src.asr.transcript import SourceSegment, TranscriptView
from src.pipeline.identifier_tools import IdentifierTools
from src.pipeline.response_revision import ResponseRevisions
from src.pipeline.response_scope import ResponseScope
from tests.test_td_identifier import collection


def view(*segments):
    """Build the coordinator's proven effective snapshot, not a model supplied source ID."""
    return TranscriptView(
        "".join(s.text for s in segments), all(s.final for s in segments), segments
    )


def test_adjacent_commits_from_one_provider_source_both_contribute():
    state = collection()
    first = state.bind_snapshot(view(SourceSegment(0, "a", 1, 0, 1000, "12", True)))
    state.collect_local(first)
    second = state.bind_snapshot(view(SourceSegment(0, "a", 2, 1000, 1500, "3", True)))
    assert state.collect_local(second)["value"] == "123"
    assert first.evidence_ids == second.evidence_ids == ((0, "a"),)


def test_multi_source_mixed_input_tool_uses_exact_group_and_local_path_deduplicates():
    state = collection()
    snapshot = view(
        SourceSegment(0, "a", 1, 0, 500, "号码", True),
        SourceSegment(0, "b", 1, 500, 1500, "123", True),
    )
    source = state.bind_snapshot(snapshot)
    assert state.submit_tool(source, "123")["value"] == "123"
    revised = view(
        SourceSegment(0, "a", 2, 0, 500, "", True), SourceSegment(0, "b", 2, 500, 1500, "123", True)
    )
    local = state.bind_snapshot(revised)
    assert state.collect_local(local)["value"] == "123"
    assert state.submit_tool(source, "123")["status"] == "stale"


def test_overlapping_source_groups_replace_but_adjacent_repeat_is_preserved():
    state = collection()
    a = SourceSegment(0, "a", 1, 0, 1000, "12", False)
    first = state.bind_snapshot(view(a))
    state.collect_local(first)
    b = SourceSegment(0, "b", 1, 1000, 1500, "3", True)
    combined = state.bind_snapshot(view(a, b))
    assert state.collect_local(combined)["value"] == "123"
    assert state.collect_local(first)["status"] == "stale"
    repeated = state.bind_snapshot(view(SourceSegment(0, "c", 1, 1500, 2500, "12", True)))
    assert state.collect_local(repeated)["value"] == "12312"


def test_tools_bind_the_coordinator_snapshot_for_multi_source_request():
    state = collection()
    snapshot = view(
        SourceSegment(0, "a", 1, 0, 500, "号码", True),
        SourceSegment(0, "b", 1, 500, 1500, "123", True),
    )
    owner = ResponseRevisions()
    response = owner.submit(
        turn_id="1", source_ids=((0, "a"), (0, "b")), text=snapshot.text, final=True
    )
    handlers = IdentifierTools(ResponseScope(owner), state)
    handlers.bind_response(response, state.bind_snapshot(snapshot))
