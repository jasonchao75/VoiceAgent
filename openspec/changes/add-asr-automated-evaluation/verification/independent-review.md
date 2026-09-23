# Independent Review — V1.20 audio-first recovery

- Date: 2026-09-23
- Reviewer: independent Change verifier
- Result: **PASS**
- Scope: tasks 12.87–12.93; PD-070–PD-076; audio-first alignment, ambiguity-only LLM fallback, Pass 2 restart identity, legacy Align isolation, historical Turn review/reporting, and global Benchmark uniqueness

## Verdict

V1.20 passes independent Engineering Checkpoint C. The implementation matches the frozen Delta Spec and prototype for the reviewed scope, the prior B1/B2 findings are closed, and the newly found overlapping historical-Turn metric defect (KI-199) was corrected and regression-tested during this re-review. Task 12.92 may be closed and the release may proceed through its separately authorized deployment controls.

This PASS is not evidence of production deployment or a paid-provider run. It does not authorize retrying `EV-20260923-E65A`; no production data was changed and no external provider was called.

## Requirement trace

### PD-070 / PD-072 — audio-first Case alignment and bounded LLM assistance

- Pure-user audio islands are frozen before text ranking. Historical timestamps are excluded (`historical_time_used=false`), event order is the hard monotonic constraint, and text cannot move waveform boundaries.
- Numeric normalization maps forms such as `223` and `two two three` to the same digit sequence. Adjacent robot context and cross-provider text consistency are implemented as auditable legal-path ranking components.
- Many adjacent historical events may map to one island/Case while preserving every source/target event ID.
- Strong provider digit, inferred-role, and semantic conflicts keep a Case ambiguous. After an LLM selection, the runner rebuilds the Case through the deterministic path and rejects any selection that still has a deterministic conflict.
- Alignment is persisted per Case, so an ambiguous event does not discard valid sibling Cases.

### Pass 2 identity and legacy Event Alignment

- Pass 2 retry reconciliation reuses the persisted canonical group ID for the same idempotency key and exact membership, even when its ordinal changes; membership drift is rejected.
- The current audio-first ASR path does not replay legacy Event Alignment. A retained failed singleton checkpoint remains historical diagnostics while valid Cases are rebuilt and continue independently.

### PD-071 / PD-074 — historical Turn quality

- Detection covers over-split, wrong-merge, and order-anomaly groups and persists all source Turns, suggested Case/island mappings, provider evidence, and exact-island audio URLs.
- Formal review supports confirm, reject, and defer in a queue separate from ASR review. The report includes confirmed-only group count, deduplicated affected Turn rows, review coverage/pending count, group detail, and audio playback without changing ASR rates, the source workbook, or Benchmark ingestion.
- KI-199 is closed: affected rows are the union of `(conversation_id, source_event_id)` across confirmed groups. The overlapping wrong-merge/order-anomaly regression confirms two groups covering the same two source Turns report `2` rows, not `3`.
- The formal production route/DOM displays source Turns, suggested Case mapping, provider evidence, per-island playback, and the report drill-down. Desktop and narrow Chromium checks pass without document/panel horizontal overflow.

### PD-073 / PD-075 — global Benchmark identity

- Migration installs global `(conversation_id, event_id)` uniqueness only after archiving legacy duplicates and their revisions/trace evidence.
- Identical cross-batch AI/manual candidates reuse the canonical Benchmark ID. Conflicting later candidates are discarded before sample, revision, review-task, count, or export creation.

## Reproducible evidence

| Check | Result |
|---|---|
| Frozen prototype SHA-256 | PASS: `a37220ea1a24e7a538cfdf8677612fe0d29e00a6fca46063e01e316703f91e62` |
| `python3 scripts/quality/verify_change.py add-asr-automated-evaluation` | PASS: 0 errors, 20 disclosed warnings; 3 unchecked tasks include the independent-verification task itself and pre-existing out-of-scope work |
| `.venv/bin/pytest -q` | PASS: 292 tests; 2 pre-existing dependency deprecation warnings |
| `.venv/bin/pytest -q tests/test_evaluation.py tests/test_evaluation_ui_contract.py` | PASS: 127 tests |
| V1.20 Turn review/report Playwright checks | PASS: 4 tests across desktop and narrow Chromium |
| `.venv/bin/ruff format --check ...` and `.venv/bin/ruff check ...` (Evaluation scope) | PASS |
| Scoped Mypy with current Python 3.13 environment | PASS: 5 affected Evaluation source files |
| Default-target Mypy (`python_version=3.11`) in the current Python 3.13 venv | Environment-limited: NumPy's installed stub uses Python 3.12 type-statement syntax; project analysis does not start. CI remains the Python 3.11 authority. |
| `npm run build` | PASS: production bundle built successfully |
| `git diff --check` | PASS |

The Playwright rerun used an isolated local data directory and the formal `/evaluation.html` route. Its temporary data was removed after the run. Backend tests independently cover exact-island clip generation; browser fixtures verify the production DOM and exact audio URLs without making provider calls.

## Evidence boundary and residual items

- **Static:** frozen PRD/prototype, Delta Spec, design, tasks, decision records, migrations, implementation, and delivery status.
- **Deterministic/mock:** 292 repository tests, including audio boundary, numeric normalization, context/consistency ranking, deterministic LLM rejection, Pass 2 restart identity, legacy isolation, Turn anomaly/metric behavior, and Benchmark migration/ingestion.
- **Local-real:** SQLite migrations/transactions, frontend production build, formal-route desktop/narrow Chromium rendering and interaction.
- **External-real:** none for V1.20. Deployment, production migration, and post-deploy verification remain pending under UV-035; E65A was not retried.

No blocking finding remains in the reviewed V1.20 scope.
