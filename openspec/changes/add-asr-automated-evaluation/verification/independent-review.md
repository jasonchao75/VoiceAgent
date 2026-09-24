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

## KI-210 hotfix re-review

- Date: 2026-09-24
- Result: **PASS — local implementation only**
- Scope: `_AUDIO_ALIGNMENT_FALLBACK_PROMPT`, its regression, task 14.10, KI-210, and the stopped PD-084 S2 evidence

### Root-cause conclusion

The reported root cause is confirmed. The old fallback system prompt contained `{{payload}}`, while the runtime payload is a dictionary of business fields such as `request_id` and `assignment_candidates`; it has no field named `payload`. The shared strict renderer therefore raised `ValueError: Prompt has unresolved runtime slots: payload` before budget reservation or Qwen dispatch. This exactly explains why the five Pass 1 conversations and twelve full-context ASR requests could finish while all four ambiguous fallback paths stopped before any Qwen reservation/dispatch, followed by failed Case-ASR projections and nine evidence exclusions.

### Fix assessment

The fix is minimal and correct: it removes the invalid runtime slot from the fallback system prompt and states that the complete JSON is carried once in the user message. The existing non-`system_only_payload` branch of `_llm_json` serializes the payload exactly once as `user_message`; the rendered system prompt now contains neither a runtime slot nor the request payload. No retry, state, budget, provider, Case, or batch semantics changed.

The new regression fails on the old template and passes on the new one: it requires strict rendering to succeed, rejects any unresolved `{{...}}` slot, proves the request payload is absent from the system prompt, and confirms the one-user-message contract. Existing ambiguous-audio tests continue to validate legal-ID selection and deterministic evidence rejection.

### Reproducible evidence

| Check | Result |
|---|---|
| Old-template deterministic reproduction | PASS: strict rendering raises `ValueError: Prompt has unresolved runtime slots: payload` |
| New prompt regression | PASS as part of the repository suite |
| Existing ambiguous-audio fallback regressions | PASS as part of the repository suite |
| `.venv/bin/pytest -q` | PASS: 305 tests; two pre-existing dependency deprecation warnings |
| `.venv/bin/ruff check src/evaluation/executor.py tests/test_evaluation.py` | PASS |
| `.venv/bin/ruff format --check src/evaluation/executor.py tests/test_evaluation.py` | PASS |
| `git diff --check` | PASS |
| `python3 scripts/quality/verify_change.py add-asr-automated-evaluation` | PASS with warnings; KI-210 remains Open pending production deployment and authorized S2 rerun |
| External provider call / production mutation | Not performed |

### Remaining boundary

KI-210 is cleared for the code-release step, but it is not yet production-resolved. Task 14.10 must remain incomplete until the hotfix is independently deployed and the separately authorized, stopped five-conversation PD-084 S2 scope is rerun. That production rerun must prove the four fallback items reach durable Qwen reservation/dispatch without duplicate payload, then verify downstream Case-ASR, Case outcomes, Event Alignment, Pass 2, cost ceiling, and stop conditions. No evidence in this review authorizes a broader S3/S4 or E65A run.

## KI-211 and PD-085 / KI-212 pre-deployment review

- Date: 2026-09-24
- Result: **PASS — local implementation only**
- Scope: Qwen3.8-Max audio-alignment strict JSON Schema, safe rejection and alignment-failure classification; immediate Historical Turn presentation/write suspension without deleting history

### KI-211 conclusion

The native DashScope request now carries a call-specific `response_format` with `type=json_schema`, a named schema, `strict=true`, required fields, `additionalProperties=false`, and enums limited to the frozen request, assignment, island, provider, and turn identifiers. The request uses Qwen3.8-Max with thinking disabled, and keeps the existing deterministic tuple/ownership/order validation after parsing. A rejected response is logged with a bounded, content-safe reason; downstream projection failures are classified as non-retryable `event_alignment_failed` rather than an ASR provider outage.

This matches Alibaba Cloud's current native DashScope contract: Qwen3.8-Max supports JSON Schema structured output; native requests place `response_format` under `parameters`; the documented object contains `type`, `json_schema.name`, `json_schema.schema`, and `json_schema.strict`; and the documented constraints include `enum`, `required`, and `additionalProperties`. The initial use of undocumented `const` was rejected during this review and replaced with a supported one-value `enum` before PASS.

Official references:

- https://docs.modelstudio.console.alibabacloud.com/en/model-studio/qwen-structured-output
- https://docs.modelstudio.console.alibabacloud.com/en/model-studio/qwen-api-via-dashscope

### PD-085 / KI-212 conclusion

The suspension is fail-closed at every exposed Historical Turn surface: bootstrap and list return an empty queue without reading candidates, decision writes return HTTP 409, and audio returns HTTP 404. The production HTML hides the Turn tab, Turn panel, and report card. ASR Case review remains available and passed its existing desktop/narrow regression.

Historical data is preserved. The regression creates a real persisted Historical Turn row, records `issue_group_id/status/version`, calls the suspended bootstrap/list/write routes, then reads SQLite directly and proves the row is unchanged. No delete, migration, recomputation, or candidate-generation behavior was added to the suspension.

### Reproducible evidence

| Check | Result |
|---|---|
| KI-211 / KI-212 focused backend selection | PASS: 7 tests before the final persistence strengthening; final regression is included in the full suite |
| Historical Turn hidden report/tab, desktop + narrow Chromium | PASS: 4/4 |
| Existing ASR Case review, desktop + narrow Chromium | PASS: 2/2 |
| `.venv/bin/pytest -q` | PASS: 308 tests; two pre-existing dependency deprecation warnings |
| `.venv/bin/ruff check src/evaluation src/llm/qwen_dashscope.py tests/test_evaluation.py tests/test_qwen_dashscope.py` | PASS |
| `.venv/bin/ruff format --check src/evaluation src/llm/qwen_dashscope.py tests/test_evaluation.py tests/test_qwen_dashscope.py` | PASS |
| `npm run build` | PASS |
| `git diff --check` | PASS |
| `python3 scripts/quality/verify_change.py add-asr-automated-evaluation` | PASS with warnings; KI-211 and KI-212 remain Open pending deployment/production evidence |
| Provider call / production write | Not performed |

### Remaining boundary

The increment is cleared for the code-release step, not declared production-resolved. KI-211 still requires deployment and a separately authorized external-real rerun proving that the production Qwen endpoint accepts the exact schema and that validated fallback output reaches usable Case-ASR, Event Alignment, and Pass 2 without misclassifying ASR providers. KI-212 still requires deployment and authenticated production read-only confirmation that the Turn tab/report/counts are absent, list/bootstrap are empty, writes are blocked, ASR Case review remains usable, and historical row counts/versions are unchanged. Recalculation and re-enabling the Turn feature remain task 14.13 and are outside this PASS.
