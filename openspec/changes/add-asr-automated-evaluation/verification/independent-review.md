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
