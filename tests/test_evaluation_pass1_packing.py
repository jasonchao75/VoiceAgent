"""Pass 1 conversation-atomic dynamic packing regression tests."""

from __future__ import annotations

import random

import pytest

from src.evaluation.executor import EvaluationRunner
from src.evaluation.pass2_packing import (
    EventAlignmentUnit,
    ModelTokenPolicy,
    PassOneUnit,
    build_event_alignment_unit,
    build_pass_one_unit,
    model_token_policy,
    pack_event_alignment_units,
    pack_pass_one_units,
)


def _alignment_unit(
    conversation_id: str, payload_size: int, target_count: int = 1
) -> EventAlignmentUnit:
    """Build one complete synthetic Event Aligner conversation."""
    return build_event_alignment_unit(
        conversation_id,
        {"conversation_id": conversation_id, "full_call_asr": "x" * payload_size},
        target_count,
        3,
    )


def test_event_aligner_prefers_one_batch_request_when_it_fits() -> None:
    """The common path must submit the whole candidate batch once."""
    units = [_alignment_unit(f"C{index:02d}", 100) for index in range(20)]
    groups = pack_event_alignment_units(
        batch_id="EV-EA-ONE",
        units=units,
        system_prompt="json",
        policy=ModelTokenPolicy(200_000, 80_000, 2_000),
    )

    assert len(groups) == 1
    assert set(groups[0].conversation_ids) == {unit.conversation_id for unit in units}


def test_event_aligner_overflow_uses_minimum_whole_conversation_groups() -> None:
    """Overflow may split between calls but never split one full conversation."""
    units = [
        EventAlignmentUnit(f"C{index}", {}, 1, 3, size)
        for index, size in enumerate((1_000, 1_000, 1_000, 1_500, 3_000, 3_500))
    ]
    groups = pack_event_alignment_units(
        batch_id="EV-EA-MIN",
        units=units,
        system_prompt="",
        policy=ModelTokenPolicy(18_000, 10_000, 1_000),
    )

    assert len(groups) == 2
    assert sum(len(group.units) for group in groups) == len(units)
    assert {item for group in groups for item in group.conversation_ids} == {
        unit.conversation_id for unit in units
    }


def _event_aligner_validation_input() -> dict[str, dict[str, object]]:
    """Build server-owned turn evidence for Event Aligner contract tests."""
    lookup: dict[str, dict[str, object]] = {}
    for provider in ("soniox", "elevenlabs"):
        lookup[f"C1:{provider}:turn:0"] = {
            "provider": provider,
            "speaker": "A",
            "turn_index": 0,
        }
        lookup[f"C1:{provider}:turn:1"] = {
            "provider": provider,
            "speaker": "B",
            "turn_index": 1,
        }
        lookup[f"C1:{provider}:turn:2"] = {
            "provider": provider,
            "speaker": "B",
            "turn_index": 2,
        }
    return {
        "C1": {
            "target_events": [{"event_id": "R2"}, {"event_id": "R4"}],
            "providers": ["soniox", "elevenlabs"],
            "turn_lookup": lookup,
        }
    }


def test_event_aligner_rejects_robot_turns_at_event_scope() -> None:
    """Real IDs are insufficient unless each selected turn belongs to the customer."""
    result = {
        "request_group_id": "EAG1",
        "results": [
            {
                "conversation_id": "C1",
                "speaker_roles": [
                    {
                        "provider": provider,
                        "customer_speaker": "B",
                        "robot_speakers": ["A"],
                    }
                    for provider in ("soniox", "elevenlabs")
                ],
                "events": [
                    {
                        "event_id": event_id,
                        "providers": [
                            {
                                "provider": provider,
                                "status": "mapped",
                                "turn_id": f"C1:{provider}:turn:{turn_index}",
                            }
                            for provider in ("soniox", "elevenlabs")
                        ],
                    }
                    for event_id, turn_index in (("R2", 0), ("R4", 2))
                ],
            }
        ],
    }

    indexed = EvaluationRunner._validate_event_alignment_group(
        result,
        expected_group_id="EAG1",
        units_by_conversation=_event_aligner_validation_input(),
    )

    assert indexed["C1"]["events"][0]["alignment_error"] == ("selected_non_customer_speaker")
    assert indexed["C1"]["events"][1]["alignment_error"] is None


def test_event_aligner_isolates_one_insufficient_event_from_valid_sibling() -> None:
    """One event with one mapped provider must not discard a valid sibling event."""
    provider_roles = [
        {"provider": provider, "customer_speaker": "B", "robot_speakers": ["A"]}
        for provider in ("soniox", "elevenlabs")
    ]
    result = {
        "request_group_id": "EAG1",
        "results": [
            {
                "conversation_id": "C1",
                "speaker_roles": provider_roles,
                "events": [
                    {
                        "event_id": "R2",
                        "providers": [
                            {
                                "provider": provider,
                                "status": "mapped",
                                "turn_id": f"C1:{provider}:turn:1",
                            }
                            for provider in ("soniox", "elevenlabs")
                        ],
                    },
                    {
                        "event_id": "R4",
                        "providers": [
                            {
                                "provider": "soniox",
                                "status": "mapped",
                                "turn_id": "C1:soniox:turn:2",
                            },
                            {
                                "provider": "elevenlabs",
                                "status": "missing",
                                "turn_id": None,
                            },
                        ],
                    },
                ],
            }
        ],
    }

    indexed = EvaluationRunner._validate_event_alignment_group(
        result,
        expected_group_id="EAG1",
        units_by_conversation=_event_aligner_validation_input(),
    )

    assert indexed["C1"]["events"][0]["alignment_error"] is None
    assert indexed["C1"]["events"][1]["alignment_error"] == "fewer_than_two_providers"


def _unit(
    conversation_id: str,
    user_event_count: int,
    payload_size: int,
) -> PassOneUnit:
    """Build one complete synthetic conversation unit."""
    return build_pass_one_unit(
        conversation_id,
        {
            "conversation_id": conversation_id,
            "conversation_history": [
                {"event_id": f"R{index}", "speaker": "customer", "text": "x" * payload_size}
                for index in range(user_event_count)
            ],
        },
        user_event_count,
    )


def test_pass_one_packing_uses_one_request_when_batch_fits() -> None:
    """Every complete conversation should share one request when limits allow it."""
    policy = ModelTokenPolicy(500_000, 128_000, 2_000)
    units = [_unit(f"C{index:02d}", 2, 100) for index in range(56)]

    groups = pack_pass_one_units(
        batch_id="EV-1",
        units=units,
        system_prompt="json",
        shared_payload={"screening_strategy": "focused"},
        policy=policy,
    )

    assert len(groups) == 1
    assert len(groups[0].conversation_ids) == 56


def test_pass_one_packing_splits_by_tokens_without_splitting_conversations() -> None:
    """An oversized batch should split only between complete conversations."""
    policy = ModelTokenPolicy(30_000, 20_000, 2_000)
    units = [_unit(f"C{index}", 2, 2_000) for index in range(7)]

    groups = pack_pass_one_units(
        batch_id="EV-2",
        units=units,
        system_prompt="json",
        shared_payload={},
        policy=policy,
    )

    assert len(groups) > 1
    assert {item for group in groups for item in group.conversation_ids} == {
        unit.conversation_id for unit in units
    }
    assert sum(len(group.units) for group in groups) == len(units)


def test_pass_one_packing_has_stable_group_ids() -> None:
    """Retry planning must preserve group membership and idempotency identities."""
    policy = ModelTokenPolicy(30_000, 20_000, 2_000)
    units = [_unit(f"C{index}", 1, 1_500) for index in range(4)]

    first = pack_pass_one_units(
        batch_id="EV-3",
        units=units,
        system_prompt="json",
        shared_payload={},
        policy=policy,
    )
    second = pack_pass_one_units(
        batch_id="EV-3",
        units=list(reversed(units)),
        system_prompt="json",
        shared_payload={},
        policy=policy,
    )

    assert [(group.group_id, group.idempotency_key) for group in first] == [
        (group.group_id, group.idempotency_key) for group in second
    ]


def test_pass_one_packing_rejects_one_oversized_conversation() -> None:
    """One unsafe conversation cannot be truncated to make the batch fit."""
    policy = ModelTokenPolicy(10_000, 8_000, 1_000)

    with pytest.raises(ValueError, match="C1"):
        pack_pass_one_units(
            batch_id="EV-4",
            units=[_unit("C1", 1, 12_000)],
            system_prompt="json",
            shared_payload={},
            policy=policy,
        )


def test_pass_one_packing_finds_minimum_group_count_beyond_greedy() -> None:
    """Packing must prove the minimum group count, not stop at a greedy result."""
    policy = ModelTokenPolicy(12_500, 10_000, 1_000)
    sizes = (1_000, 1_000, 1_000, 1_500, 3_000, 3_500)
    units = [
        PassOneUnit(
            conversation_id=f"C{index}",
            payload={"conversation_id": f"C{index}"},
            user_event_count=0,
            estimated_input_tokens=size,
        )
        for index, size in enumerate(sizes)
    ]

    groups = pack_pass_one_units(
        batch_id="EV-MINIMUM",
        units=units,
        system_prompt="",
        shared_payload={},
        policy=policy,
    )

    assert len(groups) == 2


def test_pass_one_packing_uses_lower_bound_for_large_three_group_plan() -> None:
    """A provable three-group plan must not enter an exponential two-bin search."""
    generator = random.Random(4)
    units = [
        PassOneUnit(
            conversation_id=f"C{index:02d}",
            payload={"conversation_id": f"C{index:02d}"},
            user_event_count=generator.randint(1, 4),
            estimated_input_tokens=generator.randint(1_500, 4_500),
        )
        for index in range(56)
    ]

    groups = pack_pass_one_units(
        batch_id="EV-LARGE",
        units=units,
        system_prompt="",
        shared_payload={},
        policy=ModelTokenPolicy(100_000, 50_000, 1_000),
    )

    assert len(groups) == 3


def test_qwen38_verified_limit_keeps_a_120k_input_batch_in_one_group() -> None:
    """Qwen 3.8 must not inherit the conservative 96k unknown-model fallback."""
    policy = model_token_policy("qwen", "qwen3.8-max")
    units = [PassOneUnit(f"C{index:02d}", {}, 1, 6_000) for index in range(20)]

    groups = pack_pass_one_units(
        batch_id="EV-QWEN38",
        units=units,
        system_prompt="json",
        shared_payload={},
        policy=policy,
    )

    assert policy.context_limit == 1_000_000
    assert policy.max_output_tokens == 131_072
    assert len(groups) == 1

    oversized = PassOneUnit("OVERSIZED", {}, 1, 970_000)
    with pytest.raises(ValueError, match="OVERSIZED"):
        pack_pass_one_units(
            batch_id="EV-QWEN38-LIMIT",
            units=[oversized],
            system_prompt="json",
            shared_payload={},
            policy=policy,
        )


def test_pass_one_group_validation_requires_every_conversation_once() -> None:
    """A grouped response must not omit, duplicate, or invent conversations."""
    conversations = {
        conversation_id: {
            "conversation_id": conversation_id,
            "events": [
                {"event_id": "R1", "speaker": "customer", "text": "hello"},
            ],
        }
        for conversation_id in ("C1", "C2")
    }

    def row(conversation_id: str) -> dict[str, object]:
        return {
            "conversation_id": conversation_id,
            "summary": "No suspect found.",
            "issues": [],
            "event_results": [
                {"event_id": "R1", "decision": "pass", "reason": "No textual signal."}
            ],
        }

    valid = {"request_group_id": "P1G1", "results": [row("C1"), row("C2")]}
    indexed = EvaluationRunner._validate_pass_one_group(
        valid,
        "P1G1",
        ("C1", "C2"),
        conversations,
        "focused",
    )
    assert set(indexed) == {"C1", "C2"}

    with pytest.raises(ValueError, match="omitted"):
        EvaluationRunner._validate_pass_one_group(
            {"request_group_id": "P1G1", "results": [row("C1")]},
            "P1G1",
            ("C1", "C2"),
            conversations,
            "focused",
        )
    with pytest.raises(ValueError, match="duplicated"):
        EvaluationRunner._validate_pass_one_group(
            {"request_group_id": "P1G1", "results": [row("C1"), row("C1")]},
            "P1G1",
            ("C1", "C2"),
            conversations,
            "focused",
        )
    with pytest.raises(ValueError, match="wrong request group"):
        EvaluationRunner._validate_pass_one_group(
            {"request_group_id": "other", "results": [row("C1"), row("C2")]},
            "P1G1",
            ("C1", "C2"),
            conversations,
            "focused",
        )
