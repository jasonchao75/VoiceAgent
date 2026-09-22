"""Pass 2 dynamic token packing regression tests."""

from __future__ import annotations

import pytest

from src.evaluation.executor import EvaluationRunner, _segment_id
from src.evaluation.pass2_packing import (
    FIXED_EVALUATION_USER_MESSAGE,
    ConversationUnit,
    ModelTokenPolicy,
    build_pass_two_payload,
    build_unit,
    evaluation_token_policy,
    final_request_input_tokens,
    pack_units,
    render_prompt,
    split_group,
)
from src.evaluation.prompts import PASS_TWO_SYSTEM_PROMPT


def _unit(
    conversation_id: str,
    event_count: int,
    payload_size: int,
    policy: ModelTokenPolicy,
) -> ConversationUnit:
    cases = [(conversation_id, f"R{index}") for index in range(event_count)]
    return build_unit(
        conversation_id,
        {
            "conversation_id": conversation_id,
            "conversation_history": [{"text": "x" * payload_size}],
            "candidate_cases": [{"event_id": event_id} for _, event_id in cases],
            "asr_results": [{"provider": "test", "text": "y" * payload_size}],
        },
        cases,
        policy,
    )


def test_pack_units_uses_one_request_when_everything_fits() -> None:
    """A batch that fits safely must not be split by conversation count."""
    policy = ModelTokenPolicy(200_000, 128_000, 2_000)
    units = [_unit(f"C{index}", 2, 200, policy) for index in range(56)]

    groups = pack_units(batch_id="EV-1", units=units, system_prompt="json", policy=policy)

    assert len(groups) == 1
    assert len(groups[0].units) == 56
    assert len(groups[0].case_keys) == 112


def test_split_group_is_deterministic_and_conversation_atomic() -> None:
    """Adaptive retry must split membership without splitting a conversation."""
    policy = ModelTokenPolicy(200_000, 128_000, 2_000)
    units = [_unit(f"C{index}", 2, 200 + index * 10, policy) for index in range(4)]
    parent = pack_units(
        batch_id="EV-1:suspects",
        units=units,
        system_prompt="json",
        policy=policy,
    )[0]

    first = split_group(
        batch_id="EV-1:suspects",
        parent=parent,
        system_prompt="json",
        policy=policy,
    )
    second = split_group(
        batch_id="EV-1:suspects",
        parent=parent,
        system_prompt="json",
        policy=policy,
    )

    assert first == second
    assert len(first) == 2
    child_conversations = [{unit.conversation_id for unit in child.units} for child in first]
    assert child_conversations[0].isdisjoint(child_conversations[1])
    assert child_conversations[0] | child_conversations[1] == {
        unit.conversation_id for unit in parent.units
    }
    assert {key for child in first for key in child.case_keys} == set(parent.case_keys)


def test_pack_units_splits_by_tokens_and_keeps_conversations_atomic() -> None:
    """Growing input creates the minimum sequential groups without splitting a call."""
    policy = ModelTokenPolicy(35_000, 30_000, 2_000)
    units = [_unit(f"C{index}", 2, 3_000, policy) for index in range(7)]

    groups = pack_units(batch_id="EV-2", units=units, system_prompt="json", policy=policy)

    assert len(groups) > 1
    assert sum(len(group.units) for group in groups) == 7
    assert len({key for group in groups for key in group.case_keys}) == 14
    assert all(
        len({key[0] for key in unit.case_keys}) == 1 for group in groups for unit in group.units
    )


def test_pack_units_has_stable_ids_for_retry() -> None:
    """Frozen membership must yield the same group and idempotency IDs on restart."""
    policy = ModelTokenPolicy(35_000, 30_000, 2_000)
    units = [_unit(f"C{index}", 1, 2_000, policy) for index in range(4)]

    first = pack_units(batch_id="EV-3", units=units, system_prompt="json", policy=policy)
    second = pack_units(
        batch_id="EV-3", units=list(reversed(units)), system_prompt="json", policy=policy
    )

    assert [(group.group_id, group.idempotency_key) for group in first] == [
        (group.group_id, group.idempotency_key) for group in second
    ]


@pytest.mark.parametrize("provider", ["deepseek", "gemini", "gpt", "qwen"])
def test_evaluation_policy_applies_one_shared_hard_envelope(provider: str) -> None:
    """Every supported evaluation provider must stay inside the same operating cap."""
    policy = evaluation_token_policy(provider)

    assert policy.context_limit <= 131_072
    assert policy.max_input_tokens is not None
    assert policy.max_input_tokens <= 65_536
    assert policy.max_output_tokens <= 32_768
    assert policy.safety_margin == 32_768


def test_canonical_pass2_request_projects_business_evidence_once() -> None:
    """The final System Prompt owns evidence and the User message stays content-free."""
    policy = evaluation_token_policy("deepseek")
    marker = "UNIQUE-CUSTOMER-EVIDENCE-7f3a"
    unit = build_unit(
        "C1",
        {
            "conversation_id": "C1",
            "conversation_history": [{"event_id": "R1", "text": marker}],
            "candidate_cases": [{"conversation_id": "C1", "event_id": "R1"}],
            "production_transcripts": {"R1": "history"},
            "full_audio_context_asr": [],
            "asr_results": [{"event_id": "R1", "providers": []}],
        },
        [("C1", "R1")],
        policy,
    )
    payload = build_pass_two_payload("G0001-test", [unit], {})
    template = "Evidence={{conversation_history}} Cases={{candidate_case}}"
    rendered = render_prompt(template, payload)

    assert "conversations" not in payload
    assert rendered.count(marker) == 1
    assert marker not in FIXED_EVALUATION_USER_MESSAGE
    assert final_request_input_tokens(template, payload) <= 65_536


def test_explicit_input_cap_rejects_a_large_single_case_before_dispatch() -> None:
    """A single Case above 64K must fail locally even when provider context is larger."""
    policy = evaluation_token_policy("deepseek")
    unit = _unit("C-LARGE", 1, 40_000, policy)

    with pytest.raises(ValueError, match="C-LARGE"):
        pack_units(
            batch_id="EV-LARGE",
            units=[unit],
            system_prompt="{{conversation_history}} {{candidate_case}} {{asr_results}}",
            policy=policy,
        )


def test_pre_split_units_from_one_conversation_never_recombine() -> None:
    """Stable Case subsets must remain separate once one conversation is pre-split."""
    policy = ModelTokenPolicy(80_000, 20_000, 5_000, max_input_tokens=50_000)
    units = [
        build_unit(
            "C1",
            {
                "conversation_id": "C1",
                "conversation_history": [{"text": "history"}],
                "candidate_cases": [{"conversation_id": "C1", "event_id": event_id}],
                "asr_results": [],
            },
            [("C1", event_id)],
            policy,
        )
        for event_id in ("R1", "R2")
    ]

    groups = pack_units(batch_id="EV-SPLIT", units=units, system_prompt="json", policy=policy)

    assert len(groups) == 2
    assert {group.case_keys[0][1] for group in groups} == {"R1", "R2"}


def test_cb26_scale_plan_stays_under_the_final_wire_cap() -> None:
    """The 34-Case/15-conversation shape must pre-pack below 64K per final request."""
    policy = evaluation_token_policy("deepseek", "deepseek-v4-flash")
    units: list[ConversationUnit] = []
    for conversation_index in range(15):
        case_count = 3 if conversation_index < 4 else 2
        conversation_id = f"CB26-C{conversation_index:02d}"
        case_keys = [(conversation_id, f"R{case_index:02d}") for case_index in range(case_count)]
        units.append(
            build_unit(
                conversation_id,
                {
                    "conversation_id": conversation_id,
                    "conversation_history": [
                        {"event_id": "R00", "speaker": "customer", "text": "h" * 1_200}
                    ],
                    "candidate_cases": [
                        {
                            "conversation_id": conversation_id,
                            "event_id": event_id,
                            "issue_id": f"I{event_id}",
                        }
                        for _, event_id in case_keys
                    ],
                    "production_transcripts": {event_id: "production" for _, event_id in case_keys},
                    "full_audio_context_asr": [
                        {
                            "event_id": event_id,
                            "providers": [
                                {
                                    "provider": provider,
                                    "target_turn_id": f"{conversation_id}:{provider}:turn:5",
                                    "turns": [
                                        {"turn_id": f"{conversation_id}:{provider}:turn:{turn}"}
                                        for turn in (4, 5, 6)
                                    ],
                                }
                                for provider in ("soniox", "speechmatics", "elevenlabs")
                            ],
                        }
                        for _, event_id in case_keys
                    ],
                    "asr_results": [
                        {
                            "event_id": event_id,
                            "providers": [
                                {"provider": provider, "text": "a" * 240, "segments": []}
                                for provider in ("soniox", "speechmatics", "elevenlabs")
                            ],
                        }
                        for _, event_id in case_keys
                    ],
                },
                case_keys,
                policy,
            )
        )

    groups = pack_units(
        batch_id="EV-20260922-CB26-REGRESSION",
        units=units,
        system_prompt=PASS_TWO_SYSTEM_PROMPT,
        policy=policy,
        shared_payload={
            "evaluation_context": {},
            "reference_dictionaries": [],
            "screening_strategy": "focused",
            "scenario_tags": [],
        },
    )

    assert sum(len(group.case_keys) for group in groups) == 34
    assert len({key for group in groups for key in group.case_keys}) == 34
    assert all(group.estimated_input_tokens <= 65_536 for group in groups)
    assert all(group.reserved_output_tokens <= 32_768 for group in groups)


def test_pack_units_rejects_one_oversized_conversation() -> None:
    """An unsafe conversation must pause instead of being split or silently truncated."""
    policy = ModelTokenPolicy(10_000, 30_000, 1_000)
    unit = _unit("C1", 1, 8_000, policy)

    with pytest.raises(ValueError, match="C1"):
        pack_units(batch_id="EV-4", units=[unit], system_prompt="json", policy=policy)


def test_reasoning_reserve_splits_qwen_before_json_output_can_be_starved() -> None:
    """Thinking headroom must reduce group size instead of consuming visible JSON space."""
    policy = ModelTokenPolicy(96_000, 32_000, 16_000, reasoning_reserve=20_000)
    units = [_unit(f"C{index}", 2, 300, policy) for index in range(12)]

    groups = pack_units(batch_id="EV-QWEN", units=units, system_prompt="json", policy=policy)

    assert len(groups) > 1
    assert all(group.reserved_output_tokens <= policy.max_output_tokens for group in groups)
    assert all(len(group.case_keys) <= 15 for group in groups)


def test_group_validation_requires_each_case_exactly_once() -> None:
    """A truncated or duplicated group response cannot create partial decisions."""
    rows = {
        "request_group_id": "group-1",
        "results": [
            {
                "conversation_id": "C1",
                "event_id": "R1",
                "decision": "Good Case",
                "reference_text": "one",
                "reason": "The evidence supports the historical transcript.",
                "scenario_tag": "numbers-codes",
                "evidence_completeness": "complete",
                "positioning_quality": "exact",
                "manual_review_question": None,
            },
            {
                "conversation_id": "C1",
                "event_id": "R2",
                "decision": "Bad Case",
                "reference_text": "two",
                "reason": "The evidence contradicts the historical transcript.",
                "scenario_tag": "numbers-codes",
                "evidence_completeness": "complete",
                "positioning_quality": "exact",
                "manual_review_question": None,
            },
        ],
    }

    indexed = EvaluationRunner._validate_pass_two_group(
        rows,
        (("C1", "R1"), ("C1", "R2")),
        {"C1": True},
        expected_group_id="group-1",
    )

    assert set(indexed) == {("C1", "R1"), ("C1", "R2")}
    with pytest.raises(ValueError, match="omitted"):
        EvaluationRunner._validate_pass_two_group(
            {"results": rows["results"][:1]},
            (("C1", "R1"), ("C1", "R2")),
            {"C1": True},
        )
    with pytest.raises(ValueError, match="duplicate"):
        EvaluationRunner._validate_pass_two_group(
            {"results": [rows["results"][0], rows["results"][0]]},
            (("C1", "R1"), ("C1", "R2")),
            {"C1": True},
        )

    with pytest.raises(ValueError, match="wrong request group"):
        EvaluationRunner._validate_pass_two_group(
            {**rows, "request_group_id": "another-group"},
            (("C1", "R1"), ("C1", "R2")),
            {"C1": True},
            expected_group_id="group-1",
        )


def test_group_validation_requires_traceable_segment_evidence() -> None:
    """Automatic decisions must reference segments from the same conversation payload."""
    row = {
        "conversation_id": "1030000000091506",
        "event_id": "R18",
        "decision": "Bad Case",
        "reference_text": "corrected text",
        "reason": "The evaluation transcript consistently differs.",
        "scenario_tag": "numbers-codes",
        "evidence_completeness": "complete",
        "positioning_quality": "exact",
        "vendor_evidence": [
            {
                "provider": "elevenlabs",
                "segment_ids": ["1030000000091506:elevenlabs:1"],
                "relationship_to_history": "differs",
            }
        ],
        "recommended_listening_segment_ids": ["1030000000091506:elevenlabs:1"],
        "manual_review_question": None,
        "proposed_tag": None,
    }
    valid_ids = {"1030000000091506": {"1030000000091506:elevenlabs:1"}}

    indexed = EvaluationRunner._validate_pass_two_group(
        {"results": [row]},
        (("1030000000091506", "R18"),),
        {"1030000000091506": True},
        valid_ids,
    )

    assert indexed[("1030000000091506", "R18")] == row
    row["recommended_listening_segment_ids"] = ["other-call:elevenlabs:1"]
    with pytest.raises(ValueError, match="unknown ASR segments"):
        EvaluationRunner._validate_pass_two_group(
            {"results": [row]},
            (("1030000000091506", "R18"),),
            {"1030000000091506": True},
            valid_ids,
        )


def test_group_validation_rejects_incomplete_proposed_tag() -> None:
    """AI-proposed tags require the complete bilingual contract before persistence."""
    row = {
        "conversation_id": "C1",
        "event_id": "R1",
        "decision": "Needs manual audio review",
        "reference_text": None,
        "manual_review_question": "Which digits are audible?",
        "proposed_tag": {
            "type": "semantic",
            "name_en": "Digit ambiguity",
            "name_zh": "数字歧义",
            "description_en": "Use for conflicting digit evidence.",
        },
        "reason": "The candidates conflict.",
        "scenario_tag": "unclassified",
        "evidence_completeness": "partial",
        "positioning_quality": "unavailable",
    }

    with pytest.raises(ValueError, match="bilingual schema"):
        EvaluationRunner._validate_pass_two_group(
            {"results": [row]},
            (("C1", "R1"),),
            {"C1": True},
        )


def test_segment_id_includes_full_conversation_and_provider() -> None:
    """Packed evidence IDs remain unambiguous across conversations and vendors."""
    assert _segment_id("1030000000091506", "elevenlabs", 7) == ("1030000000091506:elevenlabs:7")


def test_manual_result_allows_explicit_degraded_location() -> None:
    """Missing precise segments may route to review with an honest fallback."""
    row = {
        "conversation_id": "C1",
        "event_id": "R1",
        "decision": "Needs manual audio review",
        "reference_text": None,
        "reason": "The provider returned no bounded segment timestamps.",
        "scenario_tag": "numbers-codes",
        "evidence_completeness": "partial",
        "positioning_quality": "full_recording",
        "manual_review_question": "Which digits are audible?",
        "proposed_tag": None,
        "vendor_evidence": [
            {
                "provider": "elevenlabs",
                "segment_ids": [],
                "relationship_to_history": "ambiguous",
            }
        ],
        "recommended_listening_segment_ids": [],
    }

    indexed = EvaluationRunner._validate_pass_two_group(
        {"results": [row]},
        (("C1", "R1"),),
        {"C1": True},
        {"C1": set()},
    )

    assert indexed[("C1", "R1")]["positioning_quality"] == "full_recording"


def test_event_clip_allows_exact_decision_without_provider_segments() -> None:
    """A stable source clip remains exact when a provider omits word timestamps."""
    row = {
        "conversation_id": "C1",
        "event_id": "R1",
        "decision": "Good Case",
        "reference_text": "فرع الرياض الرئيسي",
        "reason": "The event-level evidence supports the historical transcript.",
        "scenario_tag": "branches",
        "evidence_completeness": "complete",
        "positioning_quality": "exact",
        "manual_review_question": None,
        "proposed_tag": None,
        "vendor_evidence": [
            {
                "provider": "elevenlabs",
                "segment_ids": [],
                "quoted_text": "فرع الرياض الرئيسي",
                "relationship_to_history": "agrees",
            }
        ],
        "recommended_listening_segment_ids": [],
    }

    indexed = EvaluationRunner._validate_pass_two_group(
        {"results": [row]},
        (("C1", "R1"),),
        {("C1", "R1"): True},
        {("C1", "R1"): set()},
    )

    assert indexed[("C1", "R1")]["positioning_quality"] == "exact"


def test_good_pool_uses_pass_events_only_from_suspect_conversations() -> None:
    """Additional controls stay inside transcribed conversations and round-robin them."""
    rows = [
        {
            "conversation_id": "C1",
            "result": {
                "event_results": [
                    {"event_id": "R1", "decision": "candidate"},
                    {"event_id": "R2", "decision": "pass", "reason": "No issue."},
                    {"event_id": "R3", "decision": "pass", "reason": "No issue."},
                ]
            },
        },
        {
            "conversation_id": "C2",
            "result": {
                "event_results": [
                    {"event_id": "R1", "decision": "candidate"},
                    {"event_id": "R2", "decision": "pass", "reason": "No issue."},
                ]
            },
        },
        {
            "conversation_id": "C3",
            "result": {
                "event_results": [{"event_id": "R1", "decision": "pass", "reason": "No issue."}]
            },
        },
    ]
    conversations = [
        {
            "conversation_id": conversation_id,
            "events": [
                {"event_id": "R1", "speaker": "customer", "text": "one"},
                {"event_id": "R2", "speaker": "customer", "text": "two"},
                {"event_id": "R3", "speaker": "customer", "text": "three"},
            ],
        }
        for conversation_id in ("C1", "C2", "C3")
    ]

    pool = EvaluationRunner._good_pool(rows, conversations, {"C1", "C2"})

    assert [(item["conversation_id"], item["event_id"]) for item in pool] == [
        ("C1", "R2"),
        ("C2", "R2"),
        ("C1", "R3"),
    ]
    assert all(item["origin"] == "additional_good_pool" for item in pool)
