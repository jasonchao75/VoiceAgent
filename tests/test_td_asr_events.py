"""ASR-02: locked provider events preserve source identity and actual timing."""

from importlib import import_module, util

import pytest


def normalizer(provider, model):
    """Load the actual adapter normalization contract."""
    assert util.find_spec("src.asr.turn_events") is not None, "ASR source event bridge is absent"
    return import_module("src.asr.turn_events").SourceNormalizer(provider, model)


def test_soniox_unknown_range_recovers_only_within_the_same_sdk_snapshot_scope():
    """A complete replacement proves recovery; a subsequent provider turn does not."""
    from pipecat.frames.frames import InterimTranscriptionFrame, TranscriptionFrame
    from pipecat.processors.frame_processor import FrameProcessor

    from src.asr.factory import ASRService

    parser = normalizer("soniox", "stt-rt-v5")
    service = ASRService(FrameProcessor(), source_normalizer=parser)
    unknown = {"text": "one", "is_final": False}
    valid = {**unknown, "start_ms": 0, "end_ms": 100}
    assert (
        service.normalize_source_frame(InterimTranscriptionFrame("one", "", "", result=[unknown]))
        == ()
    )
    assert parser.unresolved_sources
    assert service.normalize_source_frame(InterimTranscriptionFrame("one", "", "", result=[valid]))
    assert not parser.unresolved_sources
    # An invalid endpoint still closes the SDK snapshot scope; the next turn cannot erase it.
    service.normalize_source_frame(
        TranscriptionFrame(
            "one",
            "",
            "",
            result=[{**unknown, "is_final": True}],
            finalized=True,
        )
    )
    assert parser.unresolved_sources
    following = service.normalize_source_frame(
        InterimTranscriptionFrame(
            "two",
            "",
            "",
            result=[{"text": "two", "is_final": False, "start_ms": 200, "end_ms": 300}],
        )
    )
    assert len(following) == 1 and following[0].text == "two"
    assert parser.unresolved_sources
    # The old incomplete Partial cannot be withdrawn using a different turn's snapshot.
    assert parser._previous["0.0"].text == "one"


@pytest.mark.parametrize(
    "provider,model,unknown,known",
    [
        (
            "deepgram",
            "flux-general-en",
            {"event": "Update", "transcript": "unknown"},
            {
                "event": "Update",
                "transcript": "later",
                "turn_index": 1,
                "audio_window_start": 1.0,
                "audio_window_end": 2.0,
            },
        ),
        (
            "deepgram",
            "flux-general-multi",
            {"event": "Update", "transcript": "unknown"},
            {
                "event": "Update",
                "transcript": "later",
                "turn_index": 1,
                "audio_window_start": 1.0,
                "audio_window_end": 2.0,
            },
        ),
        (
            "deepgram",
            "nova-3",
            {"channel": {"alternatives": [{"transcript": "unknown"}]}},
            {"channel": {"alternatives": [{"transcript": "later"}]}, "start": 1.0, "duration": 1.0},
        ),
        (
            "speechmatics",
            "enhanced",
            {"message": "AddPartialSegment", "segments": [{"text": "unknown"}]},
            {
                "message": "AddPartialSegment",
                "segments": [{"text": "later", "metadata": {"start_time": 1.0, "end_time": 2.0}}],
            },
        ),
        (
            "soniox",
            "stt-rt-v5",
            {"tokens": [{"text": "unknown"}]},
            {"tokens": [{"text": "later", "start_ms": 1000, "end_ms": 2000}]},
        ),
        (
            "assemblyai",
            "universal-3-5-pro",
            {"transcript": "unknown"},
            {
                "transcript": "later",
                "turn_order": 1,
                "words": [{"text": "later", "start": 1000, "end": 2000}],
            },
        ),
    ],
)
def test_unknown_identity_cannot_be_erased_by_unrelated_valid_source_or_reconnect(
    provider,
    model,
    unknown,
    known,
):
    """ASR-02/03: connection changes are not evidence that missing speech was recovered."""
    parser = normalizer(provider, model)
    assert parser.normalize(unknown) == ()
    assert parser.unresolved_sources
    gaps = parser.unresolved_sources.copy()
    assert parser.normalize(known)
    assert parser.unresolved_sources == gaps
    parser.reconnect()
    assert parser.normalize(known)
    assert parser.unresolved_sources == gaps


def test_flux_real_overlapping_word_times_keep_the_proven_source_range():
    """D-057: overlapping ASR word times are not reordered or guessed split points."""
    from src.asr.transcript import TranscriptLedger

    raw = {
        "event": "Update",
        "turn_index": 0,
        "transcript": "I was lying to",
        "audio_window_start": 0.0,
        "audio_window_end": 0.96,
        "words": [
            {"word": "I", "start": 0.0, "end": 0.08},
            {"word": "was", "start": 0.0, "end": 0.56},
            {"word": "lying", "start": 0.56, "end": 0.8},
            {"word": "to", "start": 0.8, "end": 0.96},
        ],
    }
    parser = normalizer("deepgram", "flux-general-en")
    segments = parser.normalize(raw)
    assert parser.missing_reason is None and len(segments) == 1
    segment = segments[0]
    assert segment.words[1].start_ms == 0 and segment.words[1].end_ms == 560
    ledger = TranscriptLedger()
    ledger.apply(segment)
    assert ledger.view().text == raw["transcript"]
    # A previous submission boundary through either overlapping word stays unsplittable.
    ledger._consumed[0] = 40
    assert ledger.view().missing_reason == "cross_commit_word_overlaps_boundary"


@pytest.mark.parametrize("word_end,accepted", [(4.5600000000000005, True), (4.560001, False)])
def test_flux_real_decimal_roundoff_does_not_reject_a_contained_word(word_end, accepted):
    """D-059: permit machine representation noise, never a real timing overrun."""
    parser = normalizer("deepgram", "flux-general-en")
    result = parser.normalize(
        {
            "event": "Update",
            "turn_index": 0,
            "transcript": "to",
            "audio_window_start": 0.0,
            "audio_window_end": 4.56,
            "words": [{"word": "to", "start": 4.4, "end": word_end}],
        }
    )
    assert bool(result) is accepted
    if accepted:
        assert result[0].words[0].end_ms == word_end * 1000


def test_soniox_full_snapshot_replaces_removed_partial_tokens_without_erasing_final_prefix():
    """ASR-01: retokenizing a mutable tail cannot append the retired tail a second time."""
    from pipecat.frames.frames import InterimTranscriptionFrame
    from pipecat.processors.frame_processor import FrameProcessor

    from src.asr.factory import ASRService
    from src.asr.transcript import TranscriptLedger

    parser = normalizer("soniox", "stt-rt-v5")
    ledger = TranscriptLedger()
    service = ASRService(FrameProcessor(), source_normalizer=parser)

    def normalize(tokens):
        """Use the actual SDK list-shaped frame boundary, not a guessed wire scope."""
        return service.normalize_source_frame(
            InterimTranscriptionFrame(
                "".join(row["text"] for row in tokens),
                "",
                "",
                result=tokens,
            )
        )

    prefix = {"text": "one ", "is_final": True, "start_ms": 0, "end_ms": 100}
    left = {"text": "two ", "is_final": False, "start_ms": 100, "end_ms": 200}
    right = {"text": "three", "is_final": False, "start_ms": 200, "end_ms": 300}
    for segment in normalize([prefix, left, right]):
        ledger.apply(segment)
    assert ledger.view().text == "one two three"
    merged = {**left, "text": "two three", "end_ms": 300}
    for segment in normalize([prefix, merged]):
        ledger.apply(segment)
    assert ledger.view().text == "one two three"
    assert normalize([prefix, merged]) == ()
    # Completed sources from an earlier provider turn remain part of unconsumed input.
    for segment in normalize([{**merged, "is_final": True}]):
        ledger.apply(segment)
    assert ledger.view().text == "one two three" and ledger.view().final


@pytest.mark.parametrize("model", ["flux-general-en", "flux-general-multi"])
def test_flux_update_and_final_share_range(model):
    """Flux Update must be usable before EOT and retain raw timing."""
    parser = normalizer("deepgram", model)
    raw = {
        "type": "TurnInfo",
        "event": "Update",
        "turn_index": 7,
        "audio_window_start": 0,
        "audio_window_end": 1,
        "transcript": "12",
        "words": [{"word": "12", "start": 0.1, "end": 0.9}],
    }
    partial = parser.normalize(raw)[0]
    assert partial.text == "12" and not partial.final
    assert partial.words[0].start_ms == 100
    assert parser.normalize(raw) == ()
    final = parser.normalize({**raw, "event": "EndOfTurn"})[0]
    assert final.source_id == partial.source_id and final.final
    assert final.revision > partial.revision


def test_speechmatics_metadata_and_fragments():
    """Voice SDK 0.2.8 uses metadata/fragments, not the obsolete results field."""
    parser = normalizer("speechmatics", "enhanced")
    result = parser.normalize(
        {
            "message": "AddPartialSegment",
            "segments": [
                {
                    "text": "123",
                    "speaker_id": "S1",
                    "metadata": {"start_time": 0.1, "end_time": 2},
                    "fragments": [{"text": "123", "start_time": 0.1, "end_time": 2}],
                }
            ],
        }
    )[0]
    assert result.start_ms == 100 and result.end_ms == 2000
    assert result.words[0].text == "123" and not result.final


def test_nova_final_chunk_does_not_finalize_new_tail():
    """Result ranges remain independent of speech_final endpoint hints."""
    parser = normalizer("deepgram", "nova-3")
    raw = {
        "start": 0,
        "duration": 1,
        "is_final": True,
        "speech_final": False,
        "channel": {"alternatives": [{"transcript": "123", "words": []}]},
    }
    first = parser.normalize(raw)[0]
    tail = parser.normalize({**raw, "start": 1, "is_final": False, "speech_final": True})[0]
    assert first.final and not tail.final and first.source_id != tail.source_id


def test_soniox_stability_control_tokens_and_missing_time():
    """Control tokens never become spoken units; absent time is unavailable evidence."""
    parser = normalizer("soniox", "stt-rt-v5")
    tokens = [
        {"text": "1", "is_final": True, "start_ms": 0, "end_ms": 100},
        {"text": "2", "is_final": False, "start_ms": 100, "end_ms": 200},
        {"text": "<end>", "is_final": True},
    ]
    result = parser.normalize({"tokens": tokens})
    assert "".join(item.text for item in result) == "12"
    assert result[0].final and not result[1].final
    assert parser.normalize({"tokens": [{"text": "3", "is_final": False}]}) == ()
    assert parser.missing_reason == "source_audio_range_unavailable"


def test_assembly_formatting_and_connection_epochs():
    """Formatting revises a turn; a new connection starts a new source namespace."""
    parser = normalizer("assemblyai", "universal-3-5-pro")
    raw = {
        "type": "Turn",
        "turn_order": 1,
        "transcript": "12",
        "end_of_turn": True,
        "words": [{"text": "12", "start": 0, "end": 500}],
    }
    first = parser.normalize(raw)[0]
    formatted = parser.normalize({**raw, "transcript": "12.", "turn_is_formatted": True})[0]
    assert formatted.source_id == first.source_id and formatted.text == "12."
    parser.reconnect()
    new = parser.normalize(raw)[0]
    assert new.epoch == first.epoch + 1


def test_soniox_stable_prefix_allows_new_partial_tail():
    """A stable token is not a final whole utterance and cannot hide later tokens."""
    from src.asr.transcript import TranscriptLedger

    parser = normalizer("soniox", "stt-rt-v5")
    ledger = TranscriptLedger()
    stable = {"text": "1", "is_final": True, "start_ms": 0, "end_ms": 100}
    for item in parser.normalize({"tokens": [stable]}):
        ledger.apply(item)
    for item in parser.normalize(
        {"tokens": [stable, {"text": "2", "is_final": False, "start_ms": 100, "end_ms": 200}]}
    ):
        ledger.apply(item)
    assert ledger.view().text == "12" and not ledger.view().final


@pytest.mark.asyncio
async def test_registered_flux_update_reaches_pipeline_with_raw_timing(runtime_config):
    """Exercise the actual registry adapter, not just a detached event parser."""
    from pipecat.frames.frames import InterimTranscriptionFrame

    from src.asr.factory import create_default_asr_registry

    service = create_default_asr_registry().create(
        provider="deepgram",
        model="flux-general-en",
        turn_detection_source="provider_native",
        options={},
        api_key="test-fixture-inert-key",
        audio=runtime_config.audio,
    )
    seen = []

    async def capture(frame, *args, **kwargs):
        seen.append(frame)

    service.processor.push_frame = capture
    event = {
        "type": "TurnInfo",
        "event": "Update",
        "turn_index": 3,
        "transcript": "12",
        "audio_window_start": 0,
        "audio_window_end": 0.8,
        "words": [{"word": "12", "start": 0.1, "end": 0.7}],
    }
    await service.processor._handle_turn_info(event)
    updates = [frame for frame in seen if isinstance(frame, InterimTranscriptionFrame)]
    assert len(updates) == 1
    assert updates[0].result == event
    normalized = service.normalize_source_frame(updates[0])[0]
    assert normalized.words[0].start_ms == 100 and not normalized.final


@pytest.mark.asyncio
async def test_registered_speechmatics_preserves_segment_metadata(runtime_config):
    """The real Voice SDK frame path must retain metadata/fragments for downstream TD."""
    from src.asr.factory import create_default_asr_registry

    service = create_default_asr_registry().create(
        provider="speechmatics",
        model="enhanced",
        turn_detection_source="provider_native",
        options={},
        api_key="test-fixture-inert-key",
        audio=runtime_config.audio,
    )
    seen = []

    async def capture(frame, *args, **kwargs):
        seen.append(frame)

    service.processor.push_frame = capture
    segment = {
        "speaker_id": "S1",
        "text": "123",
        "is_active": True,
        "language": "en",
        "timestamp": "fixture",
        "metadata": {"start_time": 0, "end_time": 1},
        "fragments": [{"content": "123", "start_time": 0, "end_time": 1}],
    }
    await service.processor._send_frames([segment])
    assert len(seen) == 1
    assert seen[0].result["segments"][0]["metadata"] == segment["metadata"]
    assert seen[0].result["segments"][0]["fragments"] == segment["fragments"]


def test_speechmatics_null_fragments_preserve_segment_text_and_range():
    """Optional word details must not erase valid segment-level text evidence."""
    parser = normalizer("speechmatics", "enhanced")
    segment = parser.normalize(
        {
            "message": "AddPartialSegment",
            "segments": [
                {
                    "text": "12",
                    "speaker_id": "S1",
                    "metadata": {"start_time": 0, "end_time": 1},
                    "fragments": None,
                }
            ],
        }
    )[0]
    assert segment.text == "12" and segment.end_ms == 1000 and segment.words == ()


def test_speechmatics_complete_fragments_supply_actual_missing_segment_range():
    parser = normalizer("speechmatics", "enhanced")
    segments = parser.normalize(
        {
            "message": "AddPartialSegment",
            "segments": [
                {
                    "speaker_id": "S1",
                    "text": "12",
                    "metadata": None,
                    "fragments": [
                        {"text": "1", "start_time": 0.1, "end_time": 0.2},
                        {"text": "2", "start_time": 0.2, "end_time": 0.4},
                    ],
                }
            ],
        }
    )
    assert len(segments) == 1
    assert (segments[0].start_ms, segments[0].end_ms) == (100, 400)
    assert parser.missing_reason is None


def test_speechmatics_incomplete_fragments_do_not_invent_missing_range():
    parser = normalizer("speechmatics", "enhanced")
    assert (
        parser.normalize(
            {
                "message": "AddPartialSegment",
                "segments": [
                    {
                        "speaker_id": "S1",
                        "text": "123",
                        "metadata": None,
                        "fragments": [
                            {"text": "1", "start_time": 0.1, "end_time": 0.2},
                            {"text": "2"},
                            {"text": "3", "start_time": 0.3, "end_time": 0.4},
                        ],
                    }
                ],
            }
        )
        == ()
    )
    assert parser.missing_reason == "source_audio_range_unavailable"


@pytest.mark.parametrize("provider,model", [("speechmatics", "enhanced"), ("deepgram", "nova-3")])
@pytest.mark.parametrize("first_start,revised_start", [(0, 0.0), (0.0, -0.0), (2, 2.0)])
def test_same_numeric_start_uses_one_source_despite_json_number_format(
    provider, model, first_start, revised_start
):
    from src.asr.transcript import TranscriptLedger

    parser = normalizer(provider, model)
    ledger = TranscriptLedger()
    if provider == "speechmatics":

        def event(start, text):
            return {
                "message": "AddPartialSegment",
                "segments": [
                    {
                        "speaker_id": "S1",
                        "text": text,
                        "metadata": {"start_time": start, "end_time": start + 1},
                    }
                ],
            }
    else:

        def event(start, text):
            return {
                "start": start,
                "duration": 1,
                "is_final": False,
                "channel": {"alternatives": [{"transcript": text}]},
            }

    first = parser.normalize(event(first_start, "1"))[0]
    revised = parser.normalize(event(revised_start, "12"))[0]
    assert first.source_id == revised.source_id
    assert revised.revision == 2
    ledger.apply(first)
    ledger.apply(revised)
    assert ledger.view().text == "12"


@pytest.mark.parametrize(
    "provider,model,valid,invalid",
    [
        (
            "speechmatics",
            "enhanced",
            {"speaker_id": "a", "text": "12", "metadata": {"start_time": 0, "end_time": 0.2}},
            {"speaker_id": "a", "text": "34", "metadata": {"start_time": 0.4, "end_time": 0.3}},
        ),
        (
            "soniox",
            "stt-rt-v5",
            {"text": "12", "start_ms": 0, "end_ms": 200, "is_final": False},
            {"text": "34", "start_ms": 400, "end_ms": 300, "is_final": False},
        ),
    ],
)
@pytest.mark.parametrize("previous_text", [None, "1"])
@pytest.mark.parametrize("pending_gap", [False, True])
def test_rejected_snapshot_does_not_consume_valid_sibling_revision(
    provider,
    model,
    valid,
    invalid,
    previous_text,
    pending_gap,
):
    """A later malformed row cannot poison deduplication of an undelivered sibling."""
    parser = normalizer(provider, model)
    field = "segments" if provider == "speechmatics" else "tokens"
    payload = {"message": "AddPartialSegment", field: [valid, invalid]}
    if previous_text is not None:
        accepted = parser.normalize({**payload, field: [{**valid, "text": previous_text}]})
        assert accepted[0].revision == 1
    if pending_gap:
        incomplete = {**valid}
        if provider == "speechmatics":
            incomplete["metadata"] = {"start_time": 0}
        else:
            incomplete.pop("end_ms")
        assert parser.normalize({**payload, field: [incomplete]}) == ()
        assert parser.unresolved_sources
    assert parser.normalize(payload) == ()
    assert parser.missing_reason == "invalid_source_audio_evidence"
    if pending_gap:
        assert parser.unresolved_sources
    recovered = parser.normalize({**payload, field: [valid]})
    assert len(recovered) == 1
    assert recovered[0].text == "12"
    assert recovered[0].revision == (1 if previous_text is None else 2)
    # The failed sibling still owns a gap; recovery of another row cannot clear it.
    assert parser.unresolved_sources
    fixed_sibling = {**invalid}
    if provider == "speechmatics":
        fixed_sibling["metadata"] = {"start_time": 0.4, "end_time": 0.5}
    else:
        fixed_sibling["end_ms"] = 500
    assert parser.normalize({**payload, field: [fixed_sibling]})[0].text == "34"
    assert not parser.unresolved_sources
    assert parser.normalize({**payload, field: [valid]}) == ()


@pytest.mark.parametrize(
    "provider,model",
    [
        ("deepgram", "flux-general-en"),
        ("deepgram", "flux-general-multi"),
        ("deepgram", "nova-3"),
        ("speechmatics", "enhanced"),
        ("soniox", "stt-rt-v5"),
        ("assemblyai", "universal-3-5-pro"),
    ],
)
@pytest.mark.parametrize("bad_range", ["missing", "invalid"])
def test_final_source_cannot_reopen_a_gap_from_late_partial(provider, model, bad_range):
    """A rejected late downgrade must not strand a later user turn behind a false gap."""
    parser = normalizer(provider, model)

    def payload(final, source, text, broken=None):
        start, end = source * 100, source * 100 + 100
        if provider == "deepgram" and model.startswith("flux-"):
            data = {
                "event": "EndOfTurn" if final else "Update",
                "turn_index": source,
                "transcript": text,
                "audio_window_start": start / 1000,
            }
            if broken != "missing":
                data["audio_window_end"] = -1 if broken else end / 1000
        elif provider == "deepgram":
            data = {
                "start": start / 1000,
                "is_final": final,
                "channel": {"alternatives": [{"transcript": text}]},
            }
            if broken != "missing":
                data["duration"] = -1 if broken else 0.1
        elif provider == "speechmatics":
            metadata = {"start_time": start / 1000}
            if broken != "missing":
                metadata["end_time"] = -1 if broken else end / 1000
            data = {
                "message": "AddSegment" if final else "AddPartialSegment",
                "segments": [{"speaker_id": "a", "text": text, "metadata": metadata}],
            }
        elif provider == "soniox":
            token = {"text": text, "start_ms": start, "is_final": final}
            if broken != "missing":
                token["end_ms"] = -1 if broken else end
            data = {"tokens": [token]}
        else:
            data = {"turn_order": source, "transcript": text, "end_of_turn": final}
            if broken != "missing":
                data["words"] = [{"text": text, "start": start, "end": -1 if broken else end}]
        return data

    original = parser.normalize(payload(True, 0, "12"))[0]
    assert original.final
    assert parser.normalize(payload(False, 0, "old", bad_range)) == ()
    assert not parser.unresolved_sources
    following = parser.normalize(payload(False, 1, "34"))
    assert following[0].text == "34"
    assert not parser.unresolved_sources


def test_saved_flux_digits_boundary_uses_only_its_known_pcm_sample_extent(runtime_config):
    """D-062: retain raw times while accepting the same actual 16kHz sample extent."""
    import copy
    import json
    from pathlib import Path

    from pipecat.frames.frames import InterimTranscriptionFrame

    from src.asr.factory import create_default_asr_registry

    records = [
        json.loads(line)
        for line in Path(
            "openspec/changes/archive/2026-10-27-add-jev-semantic-turn-detection/verification/"
            "development-20261023-r47/deepgram-td-asr-synthetic-v1-D-062.jsonl"
        )
        .read_text()
        .splitlines()
    ]
    event = records[-1]["events"][-1]
    payload = copy.deepcopy(event["source_evidence"])
    payload["transcript"] = event["text"]
    service = create_default_asr_registry().create(
        provider="deepgram",
        model="flux-general-en",
        api_key="inert-no-network",
        turn_detection_source="self_developed",
        options={},
        audio=runtime_config.audio,
    )
    before = copy.deepcopy(payload)
    frame = InterimTranscriptionFrame(event["text"], "", "", result=payload)
    segments = service.normalize_source_frame(frame)
    assert len(segments) == 1
    assert segments[0].end_ms == 2.6399999 * 1000
    assert segments[0].words[-1].end_ms == 2640
    assert frame.result == before
    assert normalizer("deepgram", "flux-general-en").normalize(payload) == ()
    # A full additional sample is not the same PCM extent and must remain a gap.
    overshoot = copy.deepcopy(payload)
    overshoot["words"][-1]["end"] = 2.6400625
    assert (
        service.normalize_source_frame(
            InterimTranscriptionFrame(event["text"], "", "", result=overshoot)
        )
        == ()
    )
    assert service.source_normalizer.missing_reason == "invalid_source_audio_evidence"
    overshoot["words"][-1]["end"] = 2.6400001
    assert (
        service.normalize_source_frame(
            InterimTranscriptionFrame(event["text"], "", "", result=overshoot)
        )
        == ()
    )
