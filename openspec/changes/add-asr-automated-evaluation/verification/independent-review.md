# Independent Review — PD-080–PD-082 stability closure

- Date: 2026-09-23
- Reviewer: independent Change verifier
- Result: **PASS**
- Scope: tasks 12.64 and 14.1–14.7; batch/provider/Case state separation, immutable dataset binding, authoritative retry planning and Event Alignment lineage, timeout budget accounting, dashboard scope, migration/restart/repeated-retry coverage, and the production UI route

## Verdict

The PD-080–PD-082 stability increment passes independent verification. The implementation now keeps a terminal batch `completed` independently from provider availability and Case evidence coverage, persists Case exclusions, freezes dataset identity, and makes the versioned retry plan an enforced dispatch whitelist. The first-review blockers B-01 through B-07 are closed by implementation traces and regressions.

This PASS covers local implementation readiness through task 14.7. It does **not** authorize deployment, paid provider calls, E65A recovery, production migration, or User Gate 2; those remain task 14.8 and require separate authorization and production evidence.

## First-review blocker closure

| Finding | Closure evidence |
|---|---|
| B-01 canonical retry scope | Retry planning filters superseded/non-canonical rows and suppresses failed sibling provider attempts when every current Case already has completed evidence. The mixed-provider `C-SATISFIED` regression proves the failed full-call provider is skipped. |
| B-02 authoritative dispatch whitelist | The consumed retry plan is checked at grouped Pass 1, legacy Pass 1, ASR, current and legacy Event Alignment, ambiguous-audio fallback, and Pass 2 dispatch boundaries. Event Alignment opens a bounded new lineage and the plan exposes a cost ceiling. The legacy-bypass regression proves alternate paths cannot escape the plan. |
| B-03 legacy error classification | Structured categories remain explicit and unrecognized/string-form legacy failures fail closed instead of defaulting to retryable; deterministic failures are skipped. |
| B-04 uncertain usage after restart | Reservation states are durable. Existing `sent`, `usage_unknown`, and `settled` identities cannot be reserved or dispatched again after restart, while their estimates remain in the hard budget. |
| B-05 frozen historical source | Conversation and audio APIs accept `batch_id`; storage resolves the batch-bound dataset; report audio and conversation DOM carry the selected batch ID. API and dual-viewport tests prove an active-source change cannot redirect a historical report. |
| B-06 durable Case state | `evaluation_case_outcomes` durably separates `eligible` from `excluded_insufficient_evidence` and preserves provider diagnostics. A terminal plan produces a completed report for zero, partial, or full evaluable coverage. |
| B-07 recovery and UI evidence | Exact/non-destructive legacy migration, second-restart stability, no redispatch after restart, canonical/satisfied filtering, bounded Event Alignment lineage, timeout ledger, mixed providers, Case exclusion, batch-scoped API, and the production DOM have regressions. Desktop and narrow Chromium both pass the three affected user paths. |

## Reproducible evidence

| Check | Result |
|---|---|
| `.venv/bin/pytest -q` | PASS: 304 tests; two pre-existing dependency deprecation warnings |
| Stability-focused backend selection | PASS: 13 tests, including exact legacy migration/restart, reservation restart, canonical/satisfied filtering, Event Alignment lineage, legacy dispatch bypass, batch-scoped API, and Case exclusion |
| `.venv/bin/ruff check src/evaluation tests/test_evaluation.py` | PASS |
| `git diff --check` | PASS |
| `npm run build` | PASS |
| Production route, desktop + narrow Chromium | PASS: 6/6 — persisted historical report, completed batch with scoped coverage retry, and separated active-source/selected-report/global scopes |
| `python3 scripts/quality/verify_change.py add-asr-automated-evaluation` | PASS; remaining warnings are disclosed pre-existing or external-real items outside this local stability increment |
| Paid provider call / production mutation | Not performed, as required |

## Representative trace conclusions

1. A completed batch remains completed when one provider is unavailable; the affected Case is either satisfied by other completed evidence or durably excluded for insufficient evidence.
2. A retry starts only from the exact versioned plan the operator confirmed. Empty, deterministic, superseded, already-satisfied, or non-whitelisted work cannot reach a provider dispatch path.
3. A timeout after send becomes `usage_unknown`: its estimate remains reserved, restart does not redispatch the same identity, and the UI discloses unknown usage and the retry cost ceiling.
4. Historical reports, conversation detail, and audio use the batch-bound immutable dataset. Provable legacy history is bound exactly; ambiguous history remains `legacy_unbound`, is preserved, and cannot be source-reprocessed.
5. Dashboard cards expose active-source, selected-report/batch, and global Benchmark identities and denominators separately on the same production route and DOM.

## Evidence boundary

- **Static:** Delta Spec, design, PD-080–PD-082, decisions, tasks, implementation, migrations, production UI runtime, prototype mapping, checklist, and delivery-status records were reviewed.
- **Fixture/mock:** the full repository suite, focused stability regressions, and intercepted production-route UI scenarios pass.
- **Local-real:** SQLite migration/restart/idempotency behavior and the built production frontend route were exercised without external providers or production data.
- **External-real / production:** intentionally not exercised. Supplier billing reconciliation, paid canary behavior, E65A recovery, deployment/rollback, and authenticated production UI confirmation remain task 14.8 evidence, not part of this PASS.
