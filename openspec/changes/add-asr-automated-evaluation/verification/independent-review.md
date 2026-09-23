# Independent Review — retry terminal state, Turn reconciliation, and review localization

- Date: 2026-09-23
- Reviewer: independent Change verifier
- Result: **PASS**
- Scope: tasks 12.94–12.96; KI-200–KI-204; Pass 2 canonical terminal reconciliation, historical Turn wrong-merge evidence/lifecycle, and bilingual Manual Review queue labels/counts

## Verdict

The increment passes independent verification. Pass 2 terminal state now depends only on the current canonical Case membership; historical failed checkpoints remain diagnostic while missing or failed current Cases still block completion. Historical Turn reconciliation suppresses pause fragments without independent-Turn evidence, preserves reproduced deferred state and revisions, supersedes disappeared open candidates, and leaves confirmed/rejected decisions untouched. The formal Manual Review route renders the ASR Case and historical Turn tabs plus the Turn queue title correctly in English and Chinese while retaining live counts.

Two defects found during the first review pass were recorded as KI-203/KI-204, corrected by the implementation agent, and independently re-tested before this PASS. No production data was changed, no paid provider was called, and `EV-20260923-E65A` was not retried.

## Requirement trace

### Pass 2 canonical terminal state

- The runner freezes `pass_2_canonical_case_keys` before dispatch and updates it when balanced Good Cases are added.
- `_current_pass2_failures` reports a current Case when its latest per-Case checkpoint is missing or not completed, so an active current failure still yields `partially_failed`.
- Historical failed Case/group rows outside the current canonical set do not affect terminal state, materialization, balancing, or reporting.
- The deterministic regression proves both sides: historical `R1=failed` is ignored when only `R2` is canonical, while `R1` blocks when it remains canonical.

### Historical Turn wrong-merge and lifecycle

- A same-provider customer turn spanning the assigned and orphan RMS islands suppresses `wrong_merge`.
- A candidate is allowed only with an intervening robot boundary or distinct customer-turn IDs from at least two providers; raw islands remain evidence and historical timestamps/text do not decide the boundary.
- Reproduced pending/deferred candidates are updated in place. The regression proves deferred version 2 survives replay with its revision intact.
- A disappeared open candidate transitions to `superseded` with an appended system revision and is excluded from report quality metrics; a later reproduction can reactivate it. Confirmed/rejected rows are outside reconciliation and remain immutable.

### Manual Review localization

- ASR Case and historical Turn tab labels use bilingual label nodes separate from their live count nodes.
- The Turn queue title also separates localized label and dynamic count, and historical Turn content is refreshed after a language change.
- The production `/evaluation.html` DOM passed the exact English-to-Chinese label/title/count assertions at both desktop and narrow Chromium viewports.
- The frozen prototype remains unchanged at SHA-256 `a37220ea1a24e7a538cfdf8677612fe0d29e00a6fca46063e01e316703f91e62`; retained V1.20 desktop/narrow review and report screenshots remain the visual baseline evidence.

## Reproducible evidence

| Check | Result |
|---|---|
| Focused Pass 2 / Turn lifecycle tests | PASS: 4 tests |
| Full repository test suite | PASS: 294 tests; 2 pre-existing dependency deprecation warnings |
| Manual Review localization Playwright check | PASS: 2 tests, desktop and narrow Chromium |
| Frontend production build | PASS |
| Scoped Ruff format/check | PASS |
| Scoped Mypy with the installed Python 3.13 environment | PASS: 2 changed Evaluation source files |
| Change gate | PASS: 0 errors, 20 disclosed warnings; the 2 unchecked tasks are pre-existing tasks 12.3a and 12.64 outside this increment |
| `git diff --check` | PASS |

## Evidence boundary

- **Static:** Delta Spec, design, decisions, tasks, delivery status, implementation, migration-compatible storage schema, frozen prototype, and retained UI screenshots.
- **Deterministic/local-real:** SQLite persistence and revision behavior, 294 repository tests, production frontend build, and formal-route desktop/narrow Chromium interaction.
- **External-real:** not performed. Existing open delivery warnings remain disclosed and do not invalidate this scoped increment; production retry/deployment requires its own authorization and verification.

No blocking finding remains in tasks 12.94–12.96.
