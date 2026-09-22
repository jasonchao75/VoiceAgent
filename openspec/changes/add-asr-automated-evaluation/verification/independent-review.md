# Independent Review — PD-060 finish with current results

- Status: **PASS**
- Date: 2026-09-22
- Scope: PD-060 and Tasks 12.66–12.68 verification portion only
- Reviewer boundary: independent verification only; no implementation fix, requirement change, deployment, push, production mutation, batch retry/resume, or paid provider call was performed.

## Decision

PD-060 passes independent deterministic/local verification. The new endpoint accepts only `paused` or `partially_failed` batches, checks the submitted version before entering the store, requires an existing preliminary report, and calls only `freeze_final_report(...)`; it has no executor or provider-dispatch dependency. The store freezes a new immutable `final_partial` version, moves the batch to `completed_partial` / `completed` / 100%, retains cost and checkpoint rows, preserves pending reviews as pending, and marks pending, incomplete and unclippable Cases as excluded from formal Good/Bad aggregation. Repeating the same idempotency key returns the same report.

The corrected production renderer treats `final_partial` as **“Final report · partial coverage / 最终报告 · 部分覆盖”**. It consumes the persisted `completion_mode`, `result_excluded_count` and `excluded_reasons`, explicitly states that current persisted results were used without an ASR/LLM retry, and displays the excluded total plus reason breakdown. The end-to-end browser regression follows the operator from the batch action, through the confirmation request, to the opened immutable final-partial report on both required viewports.

## Reproducible evidence

- Change gate: **PASS with warnings** (`0 errors`, `17 warnings`, `5 tasks remain unchecked` after resolving KI-174).
- Full Evaluation backend plus UI-contract suite: **103 passed**.
- Scoped Ruff and Mypy for the changed Python files: **PASS**.
- Frontend production build: **PASS**.
- PD-060 production-route confirmation-to-report flow: **2 passed** across 1440×1000 and 1024×1000 Chromium; the accessible dialog contains preservation/exclusion/no-provider copy with no horizontal overflow, submits the expected batch version, then opens a report labeled final partial coverage with current-results and `Unreviewed: 4` disclosure.
- Static final-report trace: `renderReport()` has an explicit `final_partial` branch and renders `completion_mode`, `result_excluded_count` and every positive persisted `excluded_reasons` row through a fixed bilingual reason map.
- Data-flow trace: `POST /api/evaluation/batches/{id}/complete-with-current-results` calls only store reads plus `freeze_final_report`; no runner start/resume, ASR adapter or LLM adapter is reachable from this route.

## Remaining boundary

- This review made no paid external call and did not operate production batch `EV-20260922-7D19`.
- Production deployment, deployed commit and public health remain the delivery agent's responsibility and are not claimed by this local PASS.
- The existing open KI-171 retry-scope defect and KI-172 Pass 1 corrective-instruction packing defect are outside PD-060 and remain unresolved.

---

# Independent Review — PD-059 budget, progress and safe ASR diagnostics

- Status: **PASS**
- Date: 2026-09-22
- Scope: PD-059 and Tasks 12.60–12.63 verification portion only
- Reviewer boundary: independent verification only; no implementation or requirement change, deployment, push, production mutation, batch retry/resume, or paid provider call was performed.

## Decision

PD-059 passes independent deterministic/local verification. Pass 2 now treats the effective generation ceiling as one shared allowance: visible JSON grows with Case count, and the reasoning reservation is reduced to the remaining allowance instead of being added above it. The same calculation is exercised for Gemini, DeepSeek, Qwen, GPT, Azure GPT and OpenRouter; a non-empty Gemini group no longer fails locally merely because its prior 32K reasoning reserve was combined with an additional JSON reserve.

Single-Case input and generation planning failures have separate content-free `preflight_input_limit` and `preflight_output_limit` categories. The guarded failure path reloads the current durable batch and changes only its lifecycle status and safe failure metadata, preserving the last stage, progress, cost and all stage checkpoints. A 75% Pass 2 batch therefore remains at Pass 2 / 75% rather than being rewritten to `failed` / 0%.

ASR failures follow one safe persisted-to-UI path. Provider adapters normalize exceptions into allowlisted categories; failed full-call and event-level checkpoint rows retain attempts independently; the partial-results projection discards every persisted provider message and reconstructs a fixed safe explanation from the allowlisted category. The existing partial-results note shows provider, full-call/event-clip scope, attempts, retryability, category and safe action. Existing provider cells show the event-level failure when no successful transcript exists. Raw provider bodies, injected customer text and source paths are not consumed by this projection.

The UI continues to use `frontend/evaluation.html`, `renderReport()` and the existing report note/Case table DOM. A temporary isolated local service plus intercepted deterministic payload exercised the same production route and component tree at 1440×1000 and 1024×1000; both displayed the safe diagnostics and kept `scrollWidth == clientWidth`.

## Reproducible evidence

- Change gate: **PASS with warnings** (0 errors, 15 disclosed warnings, 3 unchecked tasks before this review/deployment update).
- PD-059 focused Evaluation/packing/UI-contract suites: **128 passed**.
- Full repository suite: **262 passed**, with the two already-disclosed dependency deprecation warnings.
- Scoped Ruff, Mypy, `git diff --check`, and frontend production build: **PASS**.
- Cross-provider budget trace: one Case packs successfully for `deepseek`, `gemini`, `gpt`, `qwen`, `azure_gpt` and `openrouter`, and each reserved generation value is at most the effective model ceiling.
- Durable failure trace: an isolated batch persisted at `pass_2`, 75% and USD 1.25 remains at the same stage/progress/cost after a `preflight_output_limit` guarded failure and becomes `partially_failed`.
- Redaction trace: checkpoint messages containing `secret upstream body` and `customer transcript must not leak` are absent from the partial-results JSON; the projection returns only fixed allowlisted messages with provider/scope/attempt/category/retryability.
- Production-route UI trace: desktop note `scrollWidth/clientWidth = 1072/1072`; narrow note `656/656`. Both render two full-call/event-clip failures with attempts and retryability in the existing partial-results region.

## Remaining boundary

- This PASS does not claim deployment or external-real provider behavior. CI, production deployment, deployed commit and public health remain the delivery agent's responsibility.
- `EV-20260922-7D19` and `EV-20260922-CB26` were not retried, resumed or mutated. Their final outcome under the corrected policy remains unverified until the product owner performs a later platform action.
- A historical checkpoint that already stored only the former generic exception name cannot recover a more specific past provider reason without a new provider attempt; future failures use the new safe category contract.

---

# Independent Review — PD-058 two-pass evaluation hard cap

- Status: **PASS**
- Date: 2026-09-22
- Scope: PD-058 and Tasks 12.54–12.59 only
- Reviewer boundary: independent verification only; no implementation change, deployment, push, production mutation, batch resume, or paid provider call was performed.

## Decision

PD-058 passes independent local verification. Pass 1 and Pass 2 now derive an effective policy from the lower of the frozen provider limits and the shared 131,072-token operating envelope, with final input capped at 65,536, combined reasoning/visible generation capped at 32,768, and 32,768 reserved as safety. Both packing and the final dispatch boundary measure the rendered System message, fixed content-free User instruction and protocol overhead before budget reservation or provider dispatch.

The runtime uses one canonical payload per pass and projects it only through the rendered System Prompt; Pass 2 no longer emits the former nested `conversations` copy alongside top-level fields or repeats the payload in the User message. Pass 2 reconstructs per-Case full-call context from persisted Event Aligner mappings and retains only the mapped provider turn plus its direct same-provider neighbors. Complete historical conversation text and event-level retranscriptions remain present.

An oversized Pass 2 conversation is deterministically bisected by ordered Case membership before dispatch until every unit fits; pre-split units from the same conversation cannot recombine. A still-oversized single Case, or an indivisible oversized Pass 1 conversation, raises the content-free `preflight_input_limit` category before any LLM request. Once a group is preflight-safe, schema/unknown-ID failures retry the same frozen membership and are not used as paid size-discovery signals. The CB26-shaped 34-Case/15-conversation regression preserves all unique Cases and keeps every final request below the common cap.

## Reproducible evidence

- Change gate: **PASS with warnings** (0 errors, 15 disclosed warnings, 2 unrelated unchecked tasks).
- PD-058 focused suites: **126 passed**.
- Full repository suite: **251 passed**, with the two already-disclosed dependency deprecation warnings.
- Scoped Ruff, Mypy for `src/evaluation`, and `git diff --check`: **PASS**.
- Static request trace: Gemini, Azure GPT, native Qwen and OpenAI-compatible providers all receive rendered evidence in the System role and only the fixed/retry execution instruction in the User role; preflight runs before budget reservation and the network call.
- Stored-data path trace: `evaluation_event_alignment_runs` supplies target turn IDs, `evaluation_asr_runs` supplies persisted full-call provider turns, and `evaluation_case_asr_runs` remains the separate event-level candidate source.

## Remaining boundary

- `UV-028` remains open: the stopped `EV-20260922-CB26` batch was not resumed or mutated, and no new user-initiated production batch has yet demonstrated the corrected policy with real provider usage/output.
- `UV-026` remains open: the integrated Event Aligner has deterministic/local coverage but no paid full-batch production run.
- This verdict covers static, deterministic and mocked local evidence. It does not claim production deployment or external-real provider validation.

---

# Independent Review — Event Aligner production-image packaging correction

- Status: **PASS** (source/package contract only)
- Date: 2026-09-22
- Scope: KI-168 corrective patch only
- Reviewer boundary: independent verification only; no implementation fix, image build, deployment, push, production mutation, or paid provider call was performed.

## Decision

The packaging correction passes source-level independent review. `.dockerignore` now explicitly admits `riyadbank-event-aligner-system-prompt-v1.md` into the otherwise deny-by-default build context, and the runtime stage copies that same source path to the exact `/app/openspec/.../fixtures/` location resolved by `src/evaluation/prompts.py` during application import. The change touches only Docker packaging and its regression assertion; it does not alter Event Aligner prompts, validation, orchestration, persistence or other business logic.

The regression test checks both required boundaries: the active Prompt filename must remain in `Dockerfile`, and its exact allow-list path must remain in `.dockerignore`. Removing either packaging addition reproduces a test failure, so it prevents recurrence of the missing-file omission at source review/CI. It does not substitute for building and starting the actual image.

## Reproducible evidence

- `tests/test_evaluation.py::test_runtime_image_packages_active_prompt_fixtures`: **1 passed**.
- Direct source trace: `Dockerfile` copies the Event Aligner fixture at line 30; `.dockerignore` admits its exact path at line 15.
- Scoped Ruff and `git diff --check`: **PASS**.
- Change gate: **PASS with warnings** (0 errors); KI-168 and UV-027 correctly remain open.

## Remaining boundary

- `KI-168` remains open until the corrected deployment succeeds and public production health is verified.
- `UV-027` remains open because the local Docker daemon is unavailable; no corrected image was built or started during this review.

---

# Final Independent Re-review — Batch-first Event Aligner

- Status: **PASS**
- Date: 2026-09-22
- Scope: PD-056, Tasks 12.50–12.51 and KI-162 through KI-166
- Reviewer boundary: independent verification only; no implementation fix, deployment, push, production mutation, or paid provider call was performed.

## Decision

The KI-165/KI-166 corrections pass independent deterministic verification. Every Event Aligner conversation must now return one `speaker_roles` row for every provider. The server checks that `customer_speaker` and every non-empty `robot_speakers` value occur in that provider's real turn catalog and that the customer label is disjoint from robot labels. A mapped real turn whose speaker differs from the declared customer speaker is retained only as an event-scoped `selected_non_customer_speaker` failure and cannot be clipped.

Provider insufficiency is also event-scoped. A well-formed target with fewer than two mapped providers receives `fewer_than_two_providers`; valid sibling mappings remain in the completed conversation/group checkpoint. `_run_asr` converts only the affected mapping's `alignment_error` into a failed Case checkpoint while independently preparing and dispatching valid sibling clips. Structural response failures still invalidate and retry only their request group. Tasks 12.50 and 12.51, plus KI-162 through KI-166, are verified resolved within the deterministic scope.

## Reproducible evidence

- Focused Evaluation and Event Aligner packing/validation suites: **103 passed**.
- Full repository suite: **241 passed**, with two already-disclosed dependency deprecation warnings.
- Independent adversarial contract check: missing provider role, unknown customer label, unknown robot label, and overlapping customer/robot labels are all rejected; real Agent turns return `selected_non_customer_speaker` at event scope.
- Mixed-event regression: a valid two-provider R2 remains `alignment_error=null` while one-provider R4 returns `fewer_than_two_providers`; source trace confirms `_run_asr` records/dispatches them independently.
- Scoped Ruff, Mypy and `git diff --check`: **PASS**.
- Change gate: **PASS with warnings** (0 errors; 13 previously disclosed warnings and two unrelated unchecked tasks).

## Remaining boundary

- `UV-026` remains open: no integrated paid full-batch Event Aligner request has yet verified real mapping accuracy, latency or billed cost. This PASS covers static, deterministic, mock and stored external-real evidence only.

---

# Prior Independent Review — Batch-first Event Aligner

- Status: **BLOCKED**
- Date: 2026-09-22
- Scope: PD-056, Tasks 12.50–12.51 and KI-162 through KI-164
- Reviewer boundary: independent verification only; no implementation fix, deployment, push, production mutation, or paid provider call was performed.

## Decision

The provider-union boundary increment passes deterministic review: accepted overlapping provider turns produce the full union for the production-derived R6/R7/R13 intervals, and pure-user signal refinement can expand but cannot contract that union. Dynamic packing prefers one whole-batch request, keeps conversations indivisible when splitting, and the reviewed example reaches the minimum safe group count. Group membership, attempts and per-conversation results have durable SQLite checkpoints; completed groups are skipped on resume and failed groups retain monotonic attempts.

The overall PD-056 increment is nevertheless blocked by two contract defects. `KI-165`: the validator proves only that target turns use a consistent anonymous speaker label; it never establishes that this label belongs to the customer. An adversarial result selecting two real Agent turns is accepted. `KI-166`: fewer than two mappings for one target raises from whole-group validation before any valid result is returned. After retries, every conversation in that request group is marked failed, so a bad event prevents correctly mapped sibling events from reaching event-level ASR or Manual Review. This conflicts with the Delta Spec's customer-role check and corresponding-event failure semantics, and with the design requirement that invalid/insufficient mapping fail only the affected event.

Task 12.50 remains verified. Task 12.51 is reopened until both defects and their regressions are addressed. Existing green tests do not exercise Event Aligner runtime validation, group checkpoint retry isolation, or mixed valid/invalid event outcomes.

## Reproducible evidence

- Focused Evaluation and packing suites: **101 passed**.
- Full repository suite: **239 passed**, with two already-disclosed dependency deprecation warnings.
- Scoped Ruff, Mypy and `git diff --check`: **PASS**.
- Change gate: **PASS with warnings** before review findings (0 errors); after registering the blockers it correctly reports the open issues and unchecked Task 12.51.
- Provider-union regression: R6 resolves to `26.70–27.39s`, R7 to `18.86–20.48s`, and R13 to `45.10–45.87s`; the implementation retains overlap only as agreement evidence and uses the accepted turns' union as the clip core.
- No-contraction trace: `_validate_and_refine_user_interval` computes `start <= provider_union.start` and `end >= provider_union.end`, with a defensive rejection if contraction is attempted.
- Customer-role adversarial trace: `_validate_event_alignment_group` accepted two existing turn IDs both labelled `AGENT`, because `provider_speakers` checks only cross-target consistency and has no customer-role ownership evidence.
- Failure-isolation adversarial trace: a response containing valid two-provider R2 mappings plus one-provider R4 raises `ValueError: Event Aligner mapped fewer than two providers`; no partial indexed result survives. `checkpoint_event_alignment_group(... status="failed")` then writes the same failed status to every conversation member.

## Required before re-review

- Establish auditable provider speaker-role ownership and reject Agent turns for customer targets; add single-target and consistently-wrong multi-target regressions.
- Preserve valid event mappings when a sibling event is missing, ambiguous or below two-provider sufficiency; persist its specific reason and prove it does not block unrelated event-level ASR/manual-review flow.
- Add runtime tests for whole-batch execution, failed-group-only retry/resume, group checkpoints and actionable event errors, then rerun focused/full checks and the Change gate.

## Remaining boundary

- `UV-026` remains open: no integrated paid full-batch Event Aligner request has yet verified real mapping accuracy, latency or billed cost. The earlier GPT exercise used external-real stored inputs with a mock/deterministic invocation and is not production execution evidence.

---

# Independent Review — Partial Pass 2 result materialization

- Status: **PASS**
- Date: 2026-09-21
- Scope: KI-161 and Task 12.49 only
- Reviewer boundary: independent verification only; no implementation fix, production retry, paid provider call, deployment, push, or production-data mutation was performed.

## Decision

The KI-161 increment passes independent deterministic verification. Both Pass 2 partial-failure exits now project every already-completed decision through the existing idempotent materialization path before returning. `Needs manual audio review` decisions become pending Manual Review records; valid `Good Case` and `Bad Case` decisions become Benchmark records and managed clips. The persisted batch totals are read back from the database, so a retry cannot inflate the displayed review or Benchmark counts when deterministic IDs are encountered again.

Incomplete Case checkpoints and failed request groups remain failed and therefore eligible for the existing targeted retry path. Completed checkpoints are reused. The batch remains `partially_failed` at Pass 2, Good balancing stays deferred while suspect Cases are incomplete, and no normal preliminary/final report is frozen; the existing partial-results view remains ephemeral and explicitly non-final.

## Reproducible evidence

- New mixed-outcome runner regression: one completed Manual Review decision plus one failed sibling produces one pending review, persists `review_total=1`, leaves the batch `partially_failed`, and leaves `latest_report` absent.
- Static storage trace: only completed Pass 2 rows are projected; failed rows are skipped. Review and Benchmark IDs are deterministic per batch/conversation/event and use `INSERT OR IGNORE`; returned totals are fresh database counts rather than attempted insert counts.
- Existing partial-results regression confirms `persist=False`, `report_type=partial_results`, `ephemeral=true`, `non_final=true`, the completed/incomplete split, and no persisted latest report.
- Focused materialization/partial-result/retry suite: **8 passed**.
- Complete Evaluation suite: **88 passed**.
- Full repository suite: **234 passed**, with two already-disclosed dependency deprecation warnings.
- Scoped Ruff, Mypy and `git diff --check`: **PASS**.
- Change gate: **PASS with warnings** (0 errors; existing disclosed warnings and two unrelated unchecked tasks).

## Remaining boundary

- Production batch `EV-20260921-BA92` was not retried during independent verification because that would issue paid external requests. The review verifies the same persisted checkpoint shapes locally and by source trace; the real provider recovery remains a separately authorized production action.

---

# Final Independent Re-review — Diarization-first user-event alignment

- Status: **PASS**
- Date: 2026-09-21
- Scope: PD-053, Task 12.48 and KI-156 through KI-160 only
- Reviewer boundary: independent verification only; no implementation fix, paid provider call, deployment, push, or production-data mutation was performed.

## Decision

The reviewed PD-053 increment passes deterministic independent verification. Excel `time (s)` is retained only as source data and does not enter positioning. Soniox, Speechmatics and ElevenLabs full-call requests explicitly enable diarization; normalized speaker/timestamp segments are aligned to historical text and event order; and the pure-user track validates/refines only the resulting narrow interval.

Consensus now excludes duplicate provider identities, enumerates distinct-provider subsets, requires a non-empty common interval, accepts only one uniquely largest agreeing subset and returns that intersection. Missing, gapped, bridged or competing evidence fails closed. Legacy or malformed completed full-call checkpoints are re-requested with monotonic attempts before clipping. Every completed provider transcription settles an attempt-scoped frozen-rate cost before diarization usability is judged, so unusable results remain charged and the hard budget can stop later attempts.

`KI-156` through `KI-160` are resolved with regression evidence. This PASS is limited to static, fixture, mock and local deterministic evidence; it does not mark User Gate 2 accepted and does not claim a current paid three-provider production run.

## Reproducible evidence

- Focused diarization/alignment/clip/adapter/retry/cost suite: **14 passed**.
- Full repository suite: **233 passed**, with two existing dependency deprecation warnings.
- Duplicate-provider, pairwise-gapped and three-provider bridge-conflict regressions fail closed; the normal two-provider result returns only the common overlap.
- Legacy completed context is replaced from monotonic attempt 2 with a valid `speaker_timestamps_v1` result before event clipping.
- Three completed one-speaker responses persist a failed context after the bounded third attempt while all three attempt-scoped ASR costs remain in the ledger; the low-budget regression prevents calls beyond the available budget.
- Soniox mock requests `enable_speaker_diarization=true`; Speechmatics requests `diarization="speaker"`; ElevenLabs retains `diarize=true`.
- Excel independence, bounded user-track signal validation and noise-only rejection regressions pass.
- Scoped Ruff, Mypy and `git diff --check`: **PASS**.
- Change gate: **PASS with warnings** (0 errors, 14 disclosed warnings, two unrelated unchecked tasks).

## Remaining boundary

- `UV-025` remains open: no current paid full-call sample has yet exercised all three provider response shapes and their real diarization quality. A paid run still requires separate authorization.

---

# Independent Review — Diarization-first user-event alignment

- Status: **BLOCKED**
- Date: 2026-09-21
- Scope: PD-053, Task 12.48 and KI-156 only
- Reviewer boundary: independent verification only; no implementation fix, paid provider call, deployment, push, or production-data mutation was performed.

## Decision

The increment is not ready for user acceptance. The intended data flow is present: Excel `time (s)` no longer enters event positioning; full-call Soniox, Speechmatics and ElevenLabs requests carry speaker diarization; normalized speaker/timestamp segments feed text-and-order alignment; and the pure-user track is examined only inside a narrow band around the proposed interval. Missing usable provider timelines fail closed, and event-level provider jobs reuse one generated clip.

Two contract defects block PASS. First, the interval cluster accepts ranges with up to a 0.75-second gap and counts rows rather than distinct provider identities. Soniox `4.0–4.5s` plus Speechmatics `5.0–5.5s` therefore produced a synthetic `4.5–5.0s` interval covered by neither provider; two rows both named Soniox also satisfied the two-provider threshold. This is not the overlapping multi-provider consensus required by PD-053. Second, resume skips every completed full-call checkpoint before verifying `diarization_contract=speaker_timestamps_v1` or usable speaker labels. A partially completed pre-PD-053 batch can therefore reuse legacy non-diarized Soniox/Speechmatics rows forever and cannot recover through retry or restart.

These findings are registered as `KI-157` and `KI-158` in `verification/delivery-status.json`. Task 12.48 and KI-156 must not remain accepted/resolved until both defects have fixes and regressions.

## Reproducible evidence

- Focused diarization/alignment/clip/adapter/retry suite: **10 passed**.
- Full repository suite: **229 passed**, with two existing dependency deprecation warnings.
- Soniox mock request contains `enable_speaker_diarization=true`; Speechmatics multipart config contains `diarization="speaker"`; the existing ElevenLabs request uses `diarize=true`.
- Excel independence regression passes after changing the target event time from `999` to `-1000`; static tracing shows `prepare_case_asr_clip` passes only ordered events, target ID and persisted full-call results into alignment.
- Independent adversarial trace: gapped intervals (`4.0–4.5s`, `5.0–5.5s`) were accepted as consensus `4.5–5.0s`; duplicate provider rows returned `['soniox', 'soniox']`.
- Restart trace: `EvaluationRunner._run_asr` returns immediately for any completed `(provider, conversation)` context row, while the new contract marker is written only after a fresh request. No migration/validation branch exists before reuse.
- Scoped Ruff, Mypy and `git diff --check`: **PASS**.
- Change gate: **PASS with warnings** (0 errors, 14 warnings, two unchecked tasks). `UV-025` correctly records that no current paid three-provider full-call run has been performed.

## Required before re-review

- Require two or more distinct providers with a non-empty common interval overlap; reject gapped and duplicate-provider evidence and add deterministic regressions.
- Validate the persisted diarization contract and usable speaker timeline before checkpoint reuse; add a legacy-checkpoint restart regression and an auditable re-request/migration path.
- Rerun focused/full tests, scoped static checks and the Change gate, then request a new independent review. Do not perform paid external calls without separate authorization.

---

# Independent Review — Adaptive Pass 2 retry and truthful progress

- Status: **PASS**
- Date: 2026-09-21
- Scope: PD-052, KI-152, KI-153 and KI-154 only
- Reviewer boundary: independent verification only; no production retry, paid provider call, deployment, push, or production-data mutation was performed.

## Decision

The reviewed increment passes deterministic independent verification. A failed multi-conversation Pass 2 group receives bounded attempts and, only for timeout or structured-response/Segment-ID contract failures, is marked superseded and deterministically bisected at complete-conversation boundaries. Child identities derive from exact membership and the parent identity. A restart encountering a superseded parent resumes those same children; completed children and completed original groups return without another provider request. Splitting stops at one complete conversation, whose final failure remains explicit after bounded local attempts. Non-size-related failures such as authentication errors remain failed and are not multiplied through recursive splitting.

Additional-Good balancing now stops before creating new controls whenever any eligible suspect Case is not completed. Pass 2 persists a frozen suspect Case universe separately from existing or later Good controls, so historical controls do not inflate suspect completion. ASR progress combines conversation-context and event-level provider checkpoints into one non-shrinking stage total; Pass 2 percentage advances only on successful suspect Cases rather than treating failures as success.

The Evaluation list renders suspect Case success/failure/pending counts, active request-group success/failure/pending counts, cumulative active-group attempts, and a separate Good-control breakdown. The same current-source component passed desktop and narrow runtime checks.

## Reproducible evidence

- Focused packing, Pass 2, progress and Good-control suite: **19 passed**.
- Split/resume regression: one two-conversation parent times out three times, splits into two one-conversation children, both complete, and a second runner invocation makes no further request. Persisted state contains one superseded parent, two completed children and two completed Case checkpoints.
- Error classification trace: only `timeout` and `schema_*` persisted errors support splitting; unrelated provider failures remain bounded failures.
- BA92-compatible isolated-state and committed regression checks: 38 frozen suspects retain `total=38`; six pre-existing completed Good controls are independently exposed as `total=6` and do not change suspect progress or suspect request-group totals.
- Full repository suite: **226 passed**, with two previously disclosed dependency deprecation warnings.
- Current-source frontend lifecycle/progress check: **2/2 PASS** across `desktop-chromium` (1440×1000) and `narrow-chromium` (1024×1000), including suspect, request-group, attempt and Good-control text.
- Scoped Ruff and Mypy, frontend production build, `git diff --check`, and Change gate: **PASS**. The gate reports 0 errors and existing disclosed warnings/one unrelated remaining task.

## Remaining boundary

- Production batch `EV-20260921-BA92` was not retried during independent verification because that would issue paid external requests. Compatibility is supported by its documented persisted shape, unchanged checkpoint schema, deterministic legacy failed-group splitting and an isolated 38-suspect + 6-control state reproduction; the actual provider retry remains a post-deployment user action.

---

# Prior Independent Review — Single-sample Benchmark deletion

- Status: **PASS**
- Date: 2026-09-21
- Scope: PD-050 and Task 12.43 only
- Reviewer boundary: independent verification only; no product implementation, production mutation, deployment, push, or external paid call was performed.

## Decision

The reviewed increment passes independent verification. Benchmark Library exposes a single-sample Delete action in both the list row and sample detail. Both paths open the same explicit confirmation dialog; cancel performs no request, while confirm issues one item-scoped DELETE and refreshes the library state. There is no batch-delete or restore action.

The backend deletion transaction targets only `evaluation_benchmark_revisions` for the selected ID and the corresponding `evaluation_benchmarks` row, then writes a content-free `benchmark.deleted` tombstone containing only the object ID and a derived-clip boolean. After commit, file removal is restricted to a resolved path below the managed Benchmark clip root. Conversations, batches, reports, manual reviews and unrelated Benchmark rows are not deletion targets or cascading children of this operation.

## Reproducible evidence

- Backend lifecycle/API regression: **PASS**. It proves the current row and all revisions disappear, detail/audio/revision endpoints return 404, list/search count becomes zero, repeated deletion returns 404, and the managed WAV is removed while the source conversation and audit tombstone remain.
- Static schema/code trace: only revisions reference `evaluation_benchmarks`; the delete transaction names only the selected revisions/current row and the audit insert. Upstream batch/report/review tables are neither updated nor deleted.
- Runtime list/detail confirmation flow: **2/2 PASS** across `desktop-chromium` (1440×1000) and `narrow-chromium` (1024×1000), including cancel-without-delete and confirmed detail deletion.
- Runtime horizontal-overflow check: **2/2 PASS** across the same desktop and narrow projects; document and dialogs remain within `scrollWidth <= clientWidth` tolerance.
- Full repository suite: **223 passed**, with two previously disclosed dependency deprecation warnings.
- Scoped Ruff and Mypy, frontend production build, `git diff --check`, and Change gate: **PASS**. The gate reports 0 errors and only existing disclosed warnings/one unrelated remaining task.

## Remaining boundary

- The browser flow used deterministic API interception so it did not delete a real user Benchmark. Backend deletion semantics were exercised against an isolated temporary database and managed clip.

---

# Prior Independent Review — Speech-aligned event clips and full-call ASR context

- Status: **PASS**
- Date: 2026-09-21
- Scope: PD-048, PD-049 and KI-149 only
- Reviewer boundary: independent verification only; no implementation, paid provider call, deployment, push, or production-data mutation was performed. Q-016 Benchmark deletion is a separate open product question and is explicitly outside this scoped verdict.

## Decision

The reviewed increment passes deterministic independent verification. Excel event time is now used only as an approximate anchor: the implementation calibrates energy near the anchor, selects a bounded speech island from the pure-user WAV, adds small guard margins, and fails closed when no island is close enough or the two nearest candidates are materially ambiguous. The exact resulting `source_clip` is reused across providers, report playback and downstream evidence; the prior event-to-next-event interval is no longer reconstructed.

The full-call MP3 is independently submitted at most once per candidate-bearing conversation/provider and persisted in the conversation-scoped checkpoint table. Event candidates remain separate provider/event checkpoints generated only from the pure-user WAV clip. Pass 2 receives full-call ASR under `full_audio_context_asr`, while candidate comparison continues to consume only event-level `asr_results`; failed context jobs cannot populate or overwrite event candidates.

## Reproducible evidence

- Real source `benchmarks/RiyadBankConversation/user_record/1030000000086502.wav`: R6 anchor `11.984s` resolves to guarded clip `9.94–10.87s` with detected speech `10.12–10.62s`; R10 anchor `60.254s` resolves to guarded clip `57.58–59.61s` with detected speech `57.76–59.36s`.
- Focused alignment/context/retry suite: **8 passed**. It covers late anchors, a louder earlier utterance, equal-distance ambiguity rejection, stable pure-user clipping, invalid-timeline fail-closed behavior, one reusable full-call checkpoint, and frozen Pass 2 retry context.
- Full repository suite: **223 passed**, with the two previously disclosed dependency deprecation warnings.
- Scoped Ruff, Mypy and `git diff --check`: **PASS**.
- Change gate: the only error is Q-016, which is explicitly outside this review scope. Existing disclosed warnings remain unchanged, including the lack of a paid external-real run for the new three-provider flow.

## Remaining boundary

- No real customer audio was sent to Soniox, Speechmatics or ElevenLabs in this review. The provider-paid execution, supplier billing and production behavior remain unverified; this PASS covers source-backed local-real alignment plus deterministic/mock orchestration evidence.

---

# Prior Independent Review — Qwen native DashScope and grouped LLM reliability

- Status: **PASS**
- Date: 2026-09-21
- Scope: PD-045 grouped LLM reliability plus PD-046 Qwen native/compatible integration (`KI-130` through `KI-148`)
- Reviewer boundary: independent verification only; no product implementation, paid provider call, deployment, push, or production-data mutation was performed

## Decision

The reviewed increment passes deterministic independent verification. The implementation now preserves the administrator-selected Qwen protocol, accepts the approved shared, premium and workspace-native URL families, routes `qwen3.8-max` to native multimodal generation, and keeps compatible mode available. Both evaluation passes use a model-specific 1,000,000-token context policy, total reasoning-plus-answer output caps, JSON Object where the selected Qwen generation supports it, application schema validation, durable attempt numbering, cost reservation, usage accounting and stable idempotency keys.

The earlier specification conflict is closed: verified `qwen3.8-*` models enable JSON Object with Thinking, while older unverified Qwen models retain the conservative no-JSON-mode fallback. This PASS covers static, mock and local deterministic evidence only. It does not claim a real paid `qwen3.8-max` diagnostic/evaluation or current-source dual-viewport browser run; those remain disclosed as `UV-023` and `UV-022`.

## Verified behavior

- URL and routing: shared `dashscope.aliyuncs.com/api/v1`, user-confirmed `prem.dashscope.aliyuncs.com/api/v1`, and workspace `*.maas.aliyuncs.com/api/v1` register as Qwen; unsupported schemes, hosts, paths, credentials, ports, query strings and fragments are rejected before an external call. Native `qwen3.8-max` uses `services/aigc/multimodal-generation/generation`; compatible-mode remains on the OpenAI client.
- Model/catalog/UI: `qwen3.8-max` is visible in Resource Connections, Cost Settings and New Evaluation. Successful Qwen connection/model tests request exact catalog registration, saved `*.maas.aliyuncs.com` Bot connections are recognized, and executor fallback resolves the predefined Qwen 3.8 family.
- Output and Thinking: native and compatible Qwen 3.8 requests use `max_completion_tokens`; Pass 1 disables Thinking, Pass 2 enables it, both send JSON Object, and legacy Qwen keeps `max_tokens` plus the conservative Thinking fallback. SDK retries are disabled so the application owns retry count and ledger identity.
- Packing/checkpoints: Pass 1 keeps whole conversations atomic and uses exact minimum-safe grouping; Pass 2 keeps whole conversation/Case units atomic. The qwen3.8 policy uses the official 1,000,000 context and 131,072 output ceilings, keeps a 120k batch in one group, and rejects a 970k unit after output/reasoning/safety reserves. Failed groups retain membership, checkpoint every paid attempt, and resume with monotonic attempt numbers.
- Usage/cost/idempotency: independent executor mocks exercised native and compatible Pass 1/Pass 2. Both parsed 100 input / 40 cached / 30 reasoning / 20 visible-output tokens, recorded the expected CNY cost, used distinct reserve and ledger keys per stage/attempt, and released no settled reservation.
- Diagnostics: native synchronous diagnostics no longer fabricate first-token latency, HTTP 400/401/404/429 retain actionable categories, reasoning-only provider responses are accepted, and diagnostic clients do not multiply retries.
- UI semantics: durable conversation checks and external request groups are presented separately. Static UI contracts and the production frontend build pass.
- Shared workspace: no unrelated user change was reverted or overwritten by this verification.

## Contract sources

- Alibaba Model Studio Base URL overview: `https://help.aliyun.com/en/model-studio/base-url`
- Alibaba native DashScope API reference: `https://help.aliyun.com/en/model-studio/qwen-api-via-dashscope`
- Alibaba Qwen3.8 Max model limits: `https://help.aliyun.com/en/model-studio/qwen3-8-max`
- Alibaba structured output reference: `https://help.aliyun.com/en/model-studio/qwen-structured-output`
- Alibaba OpenAI-compatible chat reference: `https://help.aliyun.com/en/model-studio/qwen-api-via-openai-chat-completions`

## Reproducible evidence

- Change gate: **PASS**, 0 errors, 10 disclosed warnings and 1 intentionally open supplier-bill reconciliation task.
- Focused Qwen/evaluation/API/UI-contract suite: **134 passed**, with the two already disclosed dependency deprecation warnings.
- Full repository suite: **220 passed**, with the same two warnings.
- Scoped Ruff: **PASS**.
- Mypy across `src/llm/qwen_dashscope.py`, `src/llm/diagnostics.py`, `src/evaluation`, and `src/api.py`: **PASS** (15 source files).
- Frontend production build: **PASS**.
- Independent native executor mock: **PASS** for Pass 1/Pass 2 request URL/body, Thinking, JSON Object, `max_completion_tokens`, cached/reasoning usage, CNY cost and reserve/ledger idempotency.
- Independent compatible executor mock: **PASS** for Pass 1/Pass 2 request body, zero SDK retries, Thinking, JSON Object, `max_completion_tokens`, cached/reasoning usage, CNY cost and reserve/ledger idempotency.

## Remaining boundaries

- `UV-023`: no external-real request was sent to `prem.dashscope.aliyuncs.com` or `qwen3.8-max` in this review.
- `UV-022`: the current source was not exercised through the dual-viewport browser suite; static UI contracts and the production build passed.
- Existing unrelated/open warnings remain recorded in `delivery-status.json`; none is newly hidden by this PASS.
