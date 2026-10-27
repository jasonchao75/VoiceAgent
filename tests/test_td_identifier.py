"""NUM-01/03: strict whole-input routing and controlled source-bound tools."""

from importlib import import_module, util

import pytest


def collection():
    """Create a production collection with explicit vocabulary and no cloud calls."""
    assert util.find_spec("src.pipeline.identifier") is not None, "Identifier state absent"
    module = import_module("src.pipeline.identifier")
    vocabulary = module.IdentifierVocabulary(
        {"1": ["1", "one", "一"], "2": ["2", "two", "二"], "3": ["3", "three", "三"]}
    )
    return module.IdentifierCollection(vocabulary, target_length=3)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("123", "123"),
        ("one two", "12"),
        ("一二三", "123"),
        ("1", "1"),
        ("12", "12"),
        ("1，2-3", "123"),
    ],
)
def test_strict_local_accepts_whole_identifier_without_minimum(text, expected):
    """Single units and two units do not gain an artificial minimum gate."""
    state = collection()
    assert state.vocabulary.normalize(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "one moment",
        "我的号码是123",
        "不是123，是124",
        "123，嗯，12",
        "123，接下来还要几位",
        "把第4位改成3",
    ],
)
def test_mixed_input_is_not_locally_extracted(text):
    """Presence of a substring is insufficient for the local path."""
    state = collection()
    assert state.vocabulary.normalize(text) is None


def test_repetition_revision_and_local_tool_dedup_share_state():
    """Distinct positions count, same range replaces, local/tool cannot double append."""
    state = collection()
    first = state.bind_source(0, "a", 1, "12")
    assert state.collect_local(first)["value"] == "12"
    assert state.submit_tool(first, "12")["value"] == "12"
    second = state.bind_source(0, "b", 1, "12")
    assert state.collect_local(second)["value"] == "1212"
    revised = state.bind_source(0, "a", 2, "13")
    assert state.collect_local(revised)["value"] == "1312"
    assert state.submit_tool(first, "12")["status"] == "stale"


def test_tool_rejects_hallucinated_or_cross_generation_content():
    """A tool must prove its number comes from the current source and generation."""
    state = collection()
    source = state.bind_source(0, "a", 1, "我的号码是123")
    assert state.value == ""
    assert state.submit_tool(source, "321")["status"] == "invalid"
    assert state.submit_tool(source, "123")["value"] == "123"
    assert state.clear_tool(source)["status"] == "cleared"
    newer = state.bind_source(0, "b", 1, "12")
    state.collect_local(newer)
    assert state.clear_tool(source)["status"] == "stale"
    assert state.submit_tool(source, "123")["status"] == "stale"
    assert state.value == "12"


def test_unfinished_reminder_preserves_and_success_new_start_clears():
    """Only explicit next collection after confirmed success clears old values."""
    state = collection()
    source = state.bind_source(0, "a", 1, "12")
    state.collect_local(source)
    state.begin_collection()
    assert state.value == "12"
    final = state.bind_source(0, "b", 1, "3")
    state.collect_local(final)
    assert state.mark_success(final=True)
    old_generation = state.generation
    state.begin_collection()
    assert state.value == "" and state.generation == old_generation + 1
    assert state.collect_local(source)["status"] == "stale"


def test_duplicate_aliases_are_rejected():
    """Ambiguous aliases cannot produce different audio or collected values."""
    state = collection()
    with pytest.raises(ValueError):
        type(state.vocabulary)({"1": ["one"], "2": ["ONE"]})


def test_audio_units_preserve_vocabulary_boundaries_and_repeated_values():
    """Echo composition cannot recover word boundaries from the concatenated collection."""
    from src.pipeline.identifier import IdentifierVocabulary

    vocabulary = IdentifierVocabulary({"12": ["twelve"], "alpha": ["alpha"], "1": ["one"]})
    assert vocabulary.audio_units("twelve alpha one one") == ("1", "2", "alpha", "1", "1")
    assert vocabulary.audio_units("twelve please") is None
    assert vocabulary.audio_units("---") is None
