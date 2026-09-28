# Pass 2 Prompt / executor contract conflict

## Frozen baseline

`fixtures/riyadbank-pass-2-system-prompt-v1.md` defines one top-level Case object with `conversation_id`, `issue_id`, `event_id`, `decision` and evidence fields. It does not define `request_group_id`, `results[]` or `positioning_quality`.

## Current executor

`EvaluationRunner._run_pass_two` dynamically packs multiple conversation-atomic units into one request. `_validate_pass_two_group` requires a top-level `results[]`, and `_validate_pass_two` requires every result to contain `positioning_quality`.

## Observed consequence

The frozen model instruction and parser cannot both be satisfied for a multi-Case request. A valid response that follows the frozen Prompt is rejected by the grouped parser; a response that follows the parser is not described by the complete Prompt visible to the administrator. The current batch has nine failed second-pass Cases, but existing evidence does not prove that every failure was caused by this conflict.

## Decision boundary

## Resolution

PD-025 selected Option A on 2026-09-17. The approved V2 fixture and V1.16 prototype now expose `request_group_id`, top-level `results[]`, and per-Case `positioning_quality`. The executor rejects a mismatched group ID or an incomplete/duplicate Case set before persisting any result. This resolution did not perform a real external retest; PD-018 remains in force.
