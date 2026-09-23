# Independent Review — current Manual Review queue refresh

- Date: 2026-09-23
- Reviewer: independent Change verifier
- Result: **PASS**
- Scope: PD-079 / KI-205 and the KI-206 failure-path correction; current ASR/Turn review data on sidebar entry, batch entry, and review-mode switching

## Verdict

The implementation passes independent Engineering Checkpoint C for the scoped increment. All three entry paths call the same read-only bootstrap refresh before rendering or switching review queues. A successful refresh replaces the stale client arrays and counts; a failed refresh shows a bilingual safety notification, keeps the current view and visible count, and does not present cached data as newly refreshed.

The first independent pass found that `quiet` bootstrap failure was silently swallowed. That defect was recorded as KI-206, corrected by the implementation agent, and independently re-tested before this PASS. This verdict authorizes neither deployment nor User Gate 2 acceptance. Production deployment and a post-deploy page check showing the then-current open count remain task 13.10.

## Requirement trace

### Current source of truth

- `refreshReviewQueues()` reads `/api/evaluation/bootstrap`; the response replaces `runtime.bootstrap` before counts and queue rows are rendered.
- Sidebar Manual Review entry, a batch's Open Review action, and ASR Case / Historical Turn mode switching all await this same refresh.
- The operation is GET-only. It does not call batch execution, ASR, LLM, review mutation, reporting, Benchmark, or cost endpoints.
- Retained authenticated production evidence records E65A at 40 open Turn groups and 95 superseded groups, with 2 confirmed plus 40 pending in the latest report. This production database evidence was not mutated or re-queried during this review.

### Failure behavior

- `refreshBootstrap()` returns an explicit success boolean.
- On failure, `refreshReviewQueues()` shows “Review data could not be refreshed. Keeping the current page.” (and the Chinese equivalent) and returns false.
- Each entry path stops before `showPage`, `selectReviewMode`, or queue re-rendering when refresh fails. The sidebar path also prevents the generic navigation handler from exposing the old review page first.
- Browser regression proves the sidebar remains on batches, the batch action remains on task detail, and the mode switch remains on ASR while the old count is visibly retained with an explicit failure notification.

### Formal UI and frozen baseline

- Fixture and failure checks exercise the production `/evaluation.html` route, production runtime module, and existing review DOM; there is no parallel static acceptance shell.
- Desktop and narrow Chromium both prove the original Turn review, stale-count replacement, and failed-refresh behavior.
- The frozen prototype remains unchanged at SHA-256 `a37220ea1a24e7a538cfdf8677612fe0d29e00a6fca46063e01e316703f91e62`.
- The formal Turn-review screenshot evidence was recaptured by the production-route regression at both viewports; this increment changes data freshness and failure behavior, not the frozen layout.

## Reproducible evidence

| Check | Result |
|---|---|
| KI-205/KI-206 Playwright checks | PASS: 6/6 across desktop and narrow Chromium |
| Evaluation UI static contract | PASS: 8/8 |
| Full repository test suite | PASS: 294 tests; 2 pre-existing dependency deprecation warnings |
| Frontend production build | PASS |
| Change gate | PASS: 0 errors; disclosed pre-existing/open warnings remain |
| `git diff --check` | PASS |

## Evidence boundary and remaining work

- **Static:** PRD, unchanged frozen prototype, Delta Spec, design, PD-079, tasks, UI checklist, implementation, and delivery-status evidence.
- **Fixture/local-real:** local API service plus formal production route/DOM; success and HTTP 503 refresh paths at desktop and narrow viewports.
- **External-real retained evidence:** authenticated read-only production inspection showing 40 open and 95 superseded E65A Turn groups. This review made no production request or mutation.
- **Not yet verified:** the new frontend has not been deployed and reopened in production, so the live page has not yet demonstrated 40 (or the later current value). Task 13.10 and KI-205 remain open until CI/CD, deployed SHA/health, and post-deploy UI readback succeed.

No implementation blocker remains for PD-079 release.
