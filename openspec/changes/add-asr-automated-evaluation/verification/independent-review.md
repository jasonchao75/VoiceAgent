# Independent Review — PD-067 / PD-069 Event Alignment increment

- Date: 2026-09-23
- Reviewer: independent Change verifier
- Result: **PASS**
- Scope: six-stage UI; Event Alignment request policy, splitting and restart recovery; target-event subsets; bulk projection persistence; provider-local ASR progress; elapsed-time continuity

## Verdict

PD-067/PD-069 passes independent static, deterministic/mock and isolated local-real verification. The four blockers from the previous review are resolved:

1. `mypy src` is green; the Event Alignment merge variable no longer conflicts with an optional result.
2. Persisted report results update Pass 2 at step 5, not Event Alignment at step 4. The formal-route browser test loads report data and asserts the completed Case count remains on Pass 2.
3. Execution-level regressions now prove timeout and schema-invalid parent supersession, deterministic conversation children, at most two singleton attempts, zero redispatch after restart, target-event subset merge, and reuse of the durable merged result.
4. The verification records now identify V1.19 consistently, report the actual 65 confirmed decisions, and leave PD-069 Checkpoint C pending until this review.

## Contract trace

- The frozen V1.19 prototype SHA-256 is `17829744d355bc86da3625cdf5fc24b94a6a44db5e67551046e046abbd89649c` and matches the declared baseline.
- The formal route renders six stages: validation, Pass 1, Multi-ASR, Event Alignment, Pass 2 and manual review. Event Alignment is step 4; Qwen activity is not shown under Multi-ASR.
- Event Alignment shares the 131,072-token operating envelope, with exact rendered final input capped at 65,536, output capped at 32,768 and the remaining 32,768 held as safety. The wire request contains one payload, Thinking is disabled, and Qwen timeout is 180 seconds.
- An oversized single conversation is split deterministically by target-event membership. Completed subsets merge by event ID into one conversation result and are skipped on restart.
- Timeout and schema failures supersede a multi-conversation parent and generate deterministic child groups. Singleton leaves receive at most two total attempts; completed and exhausted work is not dispatched again after restart.
- Case/provider turn projections are assembled first and persisted using one `BEGIN IMMEDIATE` bulk transaction with a 5-second SQLite busy timeout.
- Active Multi-ASR rows use provider-local ordinal/total values while durable stage totals remain provider × conversation. Active Event Alignment elapsed time is rendered immediately from persisted `started_at` and continues ticking without a first-frame `00:00` reset.

## Reproducible evidence

| Check | Result |
|---|---|
| `python3 scripts/quality/verify_change.py add-asr-automated-evaluation` | PASS: 0 errors, 18 disclosed warnings, 4 unchecked tasks |
| Focused Evaluation, packing, UI-contract and Qwen suite | PASS: 131 tests |
| Full repository test suite | PASS: 278 tests; 2 known dependency deprecation warnings |
| `ruff format --check src tests` and `ruff check src tests` | PASS |
| `mypy src` | PASS: 43 source files |
| `git diff --check` | PASS |
| Frontend production build | PASS; largest chunk 359.47 kB |
| Formal-route Event Alignment browser test | PASS: desktop and narrow Chromium, 2/2 |

The browser test used the production Evaluation route and DOM against an isolated temporary local API process. It verifies six stages, Event Alignment at step 4, report-loaded Pass 2 results at step 5, a continuous 65-second elapsed value, provider-local `/36` totals and no horizontal overflow. The temporary data directory was removed after the run.

## Evidence classification and boundary

- **Static:** PRD, proposal, Delta Spec, design, tasks, decisions, frozen prototype, delivery status and implementation trace.
- **Deterministic/mock:** 131 focused tests and 278 full-suite tests, including injected timeout/schema failures and restart replay.
- **Local-real:** production frontend bundle, SQLite transactions and the formal Evaluation route exercised through desktop and narrow Chromium.
- **External-real:** PD-068 remains the bounded historical evidence that a 3-conversation/10-event Qwen Align group completed in 22.947 seconds with zero reasoning tokens. This re-review made no external request.

This PASS does not claim deployment or a full paid production batch. Task 12.85, CI/CD, public health and deployed-SHA verification remain release-agent work. The gate's 18 disclosed warnings remain open as recorded, including external-real coverage gaps and pre-existing timeout cost-ledger/retry-scope issues.

No paid provider request was sent, and batch `EV-20260923-E65A` was not retried, resumed or mutated during this review.
