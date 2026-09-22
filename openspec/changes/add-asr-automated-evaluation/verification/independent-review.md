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
