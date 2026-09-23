# Design: ASR Automated Evaluation

## Goals

- 将已验证的离线“历史文本筛选 → 多 ASR 交叉转写 → LLM 证据判断 → 人工回听”流程变成可恢复、可审计的线上批次任务。
- 以命中 conversation 的完整录音作为外部 ASR 调用单位，以 Event Aligner 映射出的 provider turn 文本作为 Case 证据；纯用户 event 切片只作为回听与 Benchmark 音频。
- 在没有预设 Ground Truth 的条件下，只自动接纳证据充分的 Good/Bad，把无法形成可靠标注的 Case 交给人工。
- 将最终样本沉淀为 Good:Bad 目标 1:1、可追溯且可下载的 Benchmark Library。
- 保持评测资源与生产流式 ASR 完全隔离，并为成本、失败恢复、敏感数据和长期留存提供工程保障。

## Current state

Change 启动时仓库只有实时 VoiceAgent 的 ASR/LLM/TTS Pipeline、Bot 配置、历史记录和前端页面，没有 evaluation 领域模型或后台作业系统。历史本地工作簿可以证明 56 通数据中的 30 个目标事件及当时使用的三家 ASR 输入，但原始事件级第二轮输出未找到；`20 Bad / 6 Good / 4 review` 只作为已明确标识的冻结 fixture，不是可复用的 local-real 结果证据。另有一份旧周报记录 13 通 P1、12 通建议回听且第三家使用 Deepgram，属于不同历史流程，详见 `verification/prior-30-event-evidence-audit.md`。

真实输入结构是每通一个 Excel、一个完整通话 MP3 和一个纯用户 WAV。原型曾展示单个 `conversation_history.xlsx`，该表达已判定为错误，正式实现与后续原型必须遵循逐通文件结构。

## Domain boundaries

| Boundary | Responsibility | Must not do |
|---|---|---|
| Import | 安全解包、校验、生成不可变输入清单 | 不调用外部模型，不猜测缺失关联 |
| Batch orchestrator | 状态机、检查点、预算、重试、任务依赖 | 不在请求线程执行长任务 |
| Evaluation ASR | 每命中 conversation/provider 一次完整通话转写，并从已映射 provider turn 投影事件候选 | 不接管生产流式 ASR 配置，不再次转录纯用户单句切片 |
| Pass 1 | 从历史对话筛疑点并建立额外 Good 候选池 | 不产生 Ground Truth |
| Pass 2 | 基于多源证据判定 Good/Bad/人工复核 | 不用多数票或 confidence 阈值替代证据规则 |
| Review | 人工明确 Good/Bad/听不清 | 不把未提交草稿当作结论 |
| Benchmark | 剪用户音频、入库、追溯、下载 | 不接纳听不清或未复核 Case |
| Report | 固化批次版本和指标 | 不宣称评测 ASR 的准确率或自动改生产配置 |

生产环境的数据边界独立于本地开发/验收环境。镜像只携带代码、静态资源和已评审的默认配置；SQLite、Docker named volume、上传包、录音、ASR 临时切片、报告、复核、Benchmark 和成本记录均属于环境数据，不进入镜像，也不得从本地 volume 迁移到生产。生产上线必须创建或绑定明确命名的生产数据卷，并在开放访问前执行空库/生产来源检查与本地测试 ID 负向检查。

## Architecture

建议在现有应用内新增 `src/evaluation/`，保持单体部署，使用 asyncio 后台 worker 与 SQLite 持久化检查点；本期不引入新的消息队列或独立服务。

| Module | Responsibility |
|---|---|
| `models` | 批次、输入、Case、任务、结果、复核、报告和 Benchmark 数据契约 |
| `storage` | SQLite schema、事务、版本快照、幂等键和分页查询 |
| `imports` | ZIP 安全解包、Excel/音频校验、修复会话和 issue 清单 |
| `orchestrator` | 阶段依赖、并发限制、检查点、暂停/恢复/停止和预算门禁 |
| `asr` | 三家异步文件 ASR 的统一接口与 provider adapter |
| `llm` | 两轮 Prompt 渲染、结构化输出校验和重试 |
| `alignment` | Event Aligner 输入/输出、真实 turn ID 校验、并集边界和定位精度 |
| `review` | 复核状态、显式 Good/Bad/听不清和审计 |
| `benchmark` | Good 抽样、用户 WAV 剪辑、入库与 ZIP 导出 |
| `reports` | 初步/最终不可变报告和聚合指标 |

### Execution model

- API 请求只创建或更新持久化任务，不等待 ASR/LLM 完成。
- 后台 worker 使用有限并发从 SQLite 领取可运行任务；任务领取、完成和重试均带 lease 与幂等键。
- 每个阶段完成后事务性写入检查点，再解锁后续阶段。
- 应用重启后扫描非终态批次，释放过期 lease 并从最后检查点恢复。
- “停止”只阻止新任务；进行中的外部调用允许安全收尾并保存结果。“暂停”保留全部状态并允许恢复。

## Batch state model

| State | Meaning | Allowed next states |
|---|---|---|
| `draft` | 上传或配置未完成 | validating, cancelled |
| `validating` | 校验输入 | ready, validation_failed |
| `ready` | 校验通过、等待确认 | running, cancelled |
| `running` | 自动阶段执行中 | awaiting_review, partially_failed, budget_paused, stopped |
| `partially_failed` | 至少一个可恢复资源失败 | running, awaiting_review, completed_partial, stopped |
| `budget_paused` | 已达费用上限 | running, stopped |
| `paused` | 用户暂停；保留全部成功检查点 | running, completed_partial, stopped |
| `awaiting_review` | 自动分析完成且存在人工任务 | completed, completed_partial |
| `completed` | 全部复核完成并已生成最终报告 | terminal |
| `completed_partial` | 负责人提前结束并生成部分覆盖最终报告 | terminal |
| `validation_failed` | 输入不符合契约 | validating, cancelled |
| `stopped` / `cancelled` | 用户终止 | terminal |

单资源失败可使批次显示 `partially_failed`，但只要每个相关对话仍满足“历史转写 + 至少一家评测 ASR”，合格 Case 可继续第二轮；全部评测 ASR 失败的对话停在资源错误，不生成结论。

## Data model

| Entity | Key fields and constraints |
|---|---|
| `EvaluationBatch` | batch_id, status, snapshot_id, budget_limit, spent, counters, version |
| `BatchSnapshot` | context/reference-dictionary/tag/screening-strategy/prompt/provider/model/pricing versions; immutable JSON plus normalized references |
| `UploadSession` | upload_id, archive checksum, staging path, expires_at, status |
| `ConversationInput` | batch_id + conversation_id unique; three file references, hashes, audio metadata, timeline status |
| `ConversationEvent` | conversation_id + event_id unique; timestamp, role, source text, validity/exclusion reason |
| `EvaluationCase` | batch_id + conversation_id + event_id unique; origin, decision, language, tag, time range, evidence status |
| `ScenarioTag` / `ScenarioTagVersion` | stable tag ID; bilingual name/description, type, status, version, deleted_at; versions append-only |
| `ReferenceDictionary` / `ReferenceDictionaryVersion` | stable dictionary key; name, purpose, generic schema, entries, status and append-only versions; context links reference exact versions |
| `ProposedScenarioTag` | report_id + proposal_key unique; type, name_en/name_zh, description_en/description_zh, related case IDs, status |
| `ProviderJob` | batch_id + conversation_id + provider unique; full-call provider job ID, attempt, status, cost and error |
| `ASRSegment` | full-call provider job + stable turn/segment ID; source-relative start/end, speaker, language and text |
| `LLMRun` | pass, prompt/model snapshot, input hash, output, schema status, token/cost metadata |
| `ReviewResult` | case_id unique current result plus append-only revisions; Good/Bad/unclear, label, reviewer, time |
| `EvaluationReport` | batch_id + version unique; preliminary/final, coverage, immutable payload, generated_at |
| `BenchmarkSample` | batch_id + conversation_id + event_id unique; source, case type, label, clip, trace |
| `AuditEvent` | actor, action, object, time, outcome, safe metadata; never raw transcript/key/audio |

## Import and storage design

### Safe package handling

- Reject absolute paths, `..`, symlinks, unsupported entries, duplicate normalized paths, excessive file count and decompressed-size expansion.
- Copy accepted files into a batch-owned staging directory using generated internal names; never trust archive paths as storage paths.
- Compute content hashes before validation and preserve the original relative path only as metadata.
- Do not log archive contents, conversation text or audio bytes.

### Per-conversation validation

- Enumerate basenames in all three directories and require exact one-to-one sets.
- Open every workbook and validate `Dialogue Details`, required columns, numeric times, one role per row and non-empty event IDs derived deterministically from row order. Preserve worksheet row order as conversation order; report decreasing historical timestamps as non-blocking reference warnings instead of reordering or rejecting the conversation.
- Probe every audio file by content, not extension. Record codec, duration, sample rate, bit depth where applicable and channels.
- Compare `record` and `user_record` durations and retain drift or events beyond audio duration as reference warnings. These findings do not block evaluation, but the affected ranges are not reliable sources for precise Benchmark clips until repaired or explicitly handled by a reviewed fallback.
- Repair uploads replace only identified paths after checksum and scope validation, then rerun affected checks and the global ID-set check.

## Two-pass analysis

### Pass 1

Pass 1 uses dynamic token packing. One conversation's complete history and all of its user events form an indivisible unit. Before dispatch, the orchestrator builds the exact final message and applies the common evaluation envelope: no more than 65,536 input tokens, no more than 32,768 combined reasoning and visible-output tokens, and 32,768 tokens of safety within a 131,072-token operating ceiling. The effective values are the lower of these caps and the frozen model's verified limits. Preflight uses a conservative upper bound over the final serialized System/User messages; provider-reported usage is recorded after a call but is never used to justify an oversized dispatch. If the complete batch fits safely, Pass 1 sends one request; otherwise it creates the minimum safe number of groups. A conversation is never split or truncated; a single oversized conversation fails before dispatch with an actionable size error.

Each group receives the frozen runtime envelope containing the evaluation context, linked generic reference dictionaries, screening strategy and enabled scenario tags. It has a stable `request_group_id` and frozen conversation membership. The model must echo the group ID and return exactly one result per conversation, with one structured record per user event: candidate, pass or data issue, plus a short reason, business impact and scenario suggestions. The application validates group identity, conversation ownership and event IDs independently of the LLM. Initial packing reserves the longest corrective instruction in the exact final message so a retry cannot turn a dispatched near-cap group into a local input-cap failure. For Qwen, Pass 1 keeps Thinking disabled and uses a 180-second request timeout. A timeout or structured-response failure supersedes the parent and deterministically halves complete-conversation membership; children may split again, while a single-conversation leaf receives at most one additional attempt. Completed groups and conversations are never resent.

After Pass 1 checkpoints settle, the orchestrator distinguishes an empty valid result from total execution failure. If every conversation failed, the batch becomes retryable `partially_failed/failed` and never advances to ASR. If at least one conversation completed but the resulting Case set is empty, the service freezes a zero-candidate preliminary report and completes without creating ASR or Pass 2 jobs.

All valid pass events in conversations containing at least one candidate form the additional Good pool. They are not immediately called Good; they remain candidates for Pass 2 evidence confirmation.

### Evaluation ASR fan-out

After Pass 1 identifies target user events, each selected provider produces one diarized full-call timeline for every candidate-bearing conversation. Consecutive segments from the same anonymous speaker are persisted as stable turns. A dedicated Event Aligner then maps all target R events to existing provider turn IDs. Conversation units are dynamically packed against the frozen Pass 1 model's verified context limit: the whole batch uses one request when safe, otherwise the minimum safe groups are formed without splitting a conversation. Deterministic validation rejects invented IDs, wrong ownership, non-monotonic mappings, non-user turns and fewer than two provider mappings. Accepted provider turn intervals are unioned, validated on `user_record`, and may be expanded to cover user signal but never contracted inside the union. Excel `time (s)` is retained only for audit and never enters alignment. Pass 2 consumes the mapped full-call provider turn text directly; the generated pure-user WAV is playback and Benchmark evidence, not a second ASR input.

Provider responses are normalized but raw safe response payloads may be retained access-controlled for troubleshooting. Local segment IDs use full conversation ID and provider identity; UI only exposes them inside technical evidence.

Failed ASR checkpoints expose only a safe diagnostic contract: provider, full-call or event-clip scope, attempt count, retryability, controlled category and an actionable allowlisted reason. Provider raw bodies, customer transcript, source paths and credentials remain excluded. The partial-result note and existing provider cells consume this contract without adding a new page area.

### Pass 2 and automatic admission

Pass 2 evaluates each first-pass candidate and only the additional Good candidates needed to satisfy the balance target. It receives the complete historical conversation, the same frozen context/dictionary/strategy/tag envelope, mapped target provider-turn texts, and a bounded full-call provider-turn window around each target. The application accepts an automatic Good/Bad only when:

Pass 2 uses the selected model's Thinking mode and the same 65,536-input / 32,768-generation / 32,768-safety envelope as Pass 1. Qwen3.8 explicitly uses `reasoning_effort=medium` and a 300-second request timeout. The 32,768 generation budget is shared: the planner first reserves the visible JSON required by the Case count, then gives only the remaining allowance to Thinking. It never adds a full reasoning reserve on top of the visible-output reserve. A Case unit contains the complete historical conversation text, the mapped full-call target turn texts as formal provider candidates, and only the immediately preceding and following turn from the same provider as bounded context when present. Unrelated full-call turns are excluded from Pass 2; they remain stored as read-only evidence. The planner first packs by conversation, then deterministically partitions an oversized conversation by stable Case subsets while repeating its necessary complete history. If one Case still exceeds the final-input or generation cap after this evidence selection, it fails before any provider call with a dedicated preflight category. Progress records unique Cases and external request groups separately. Each group has a stable `request_group_id`; the model must echo it and return one `results[]` element per Case, including `positioning_quality`. A mismatched group ID or incomplete/duplicate Case set rejects the whole response. A timeout or structured-response failure supersedes the parent instead of replaying it unchanged, then deterministically halves complete Case membership. Children may split again, while a single-Case leaf receives at most one additional attempt. Stable child identity derives from exact Case membership, completed Cases are never resent, and pre-dispatch size failures remain local rather than triggering paid split discovery.

1. the response validates against the frozen schema;
2. decision is Good or Bad;
3. reference text is non-empty;
4. evidence contains a real, bounded location or an explicit degraded location;
5. at least one evaluation ASR result is successful.

Prompt 不输出 confidence，系统也不保存或使用 confidence 阈值。A failed rule routes the Case to manual review rather than inventing a default.

上线默认数据来自 Change 内的四份可审计 fixture：`fixtures/riyadbank-evaluation-context-v1.md`、`fixtures/riyadbank-reference-dictionary-v1.csv`、`fixtures/riyadbank-pass-1-system-prompt-v1.md` 和 `fixtures/riyadbank-pass-2-system-prompt-v2.md`。V1 第二轮 Prompt 仅作历史审计，V2 是 PD-025 确认的分组输出契约。配置迁移使用稳定 seed key 幂等追加缺失契约版本；历史版本保留，生效模板缺少 `request_group_id`、`results[]` 或 `positioning_quality` 时升级到 V2，后续管理员编辑始终另存新版本。

运行时渲染器固定组装一个与客户无关的变量包：`evaluation_context` 来自上下文版本，`reference_dictionaries` 来自上下文关联的词典版本，`screening_strategy` 来自批次候选范围，`scenario_tags` 来自启用标签快照。第一轮增加 `request_group_id` 和按 conversation ID 分组的 `conversations`；第二轮增加 `request_group_id`、候选数组 `candidate_case`、按 conversation ID 分组的 `conversation_history`、`production_transcript` 和按 Case 限定的 `asr_results`。完整 System Prompt 以稳定模板保存，并用 `{{variable}}` 显式标记动态数据的注入位置；运行时将各变量序列化后替换为成品 Prompt。成品 System Prompt 是业务证据的唯一线上投影，User message 只能发送固定且不含客户数据的执行指令；不得再把变量包或嵌套 `conversations` JSON 复制到 User message。装箱和硬上限检查基于这两个最终消息以及协议所需结构开销。RiyadBank 的分行词典只是 `reference_dictionaries` 中一个 `dictionary_key=riyadbank_branches` 的实例，平台数据模型和 Prompt 契约不得出现分行专属字段。

If no frozen tag matches, Pass 2 emits a structured `proposed_tag` with `type`, `name_en`, `name_zh`, `description_en` and `description_zh`. The proposal is an ASR-quality taxonomy dimension, not a user-behavior, business-completion or bot-quality category. Its wording stays neutral across Good, Bad and manual-review outcomes: for example, language selection means whether language-related speech was preserved accurately, not whether the user complied with the bot's question. The report stores this proposal in its immutable payload for review. Confirming creation copies all five fields into a new global tag version and moves the grouped Cases in one transaction; incomplete proposals cannot be created directly.

## Good Case balancing

The balance is computed after suspect candidates receive Pass 2 decisions:

- `bad_count` is the number of admitted automatic Bad plus submitted manual Bad available at the time a report is frozen.
- `good_count` includes first-pass suspects reclassified as Good plus submitted manual Good.
- The missing Good count is the positive difference between Bad and Good.
- The orchestrator selects up to that number of events from the additional Good pool and runs Pass 2 on them. Candidates that fail Good admission are skipped or routed according to their resulting decision; selection continues while eligible pool remains.

Selection is deterministic from the batch snapshot and favors coverage across conversation, language and known scenario before selecting a second event from the same subgroup. The exact seed and algorithm version are stored. If the pool cannot reach 1:1, the actual ratio and shortage are reported.

Because provider transcription is conversation-scoped and these events come only from already transcribed conversations, extra Good selection creates no additional ASR job. It can add Pass 2 LLM tokens, which remain subject to the batch budget.

## Audio alignment and clipping

- Retain the workbook event time only as source audit metadata; it never participates in alignment, ranking, tie-breaking or clipping.
- Transcribe the full-call recording once per selected provider and candidate-bearing conversation with speaker diarization explicitly enabled. Persist word/segment text, start/end timestamps and anonymous speaker labels separately from event-level candidates.
- Group consecutive same-speaker segments into immutable provider turns with stable IDs. The Event Aligner receives complete ordered worksheet events, all target R IDs and each provider's turns; it selects only existing turn IDs or returns missing/ambiguous and never emits timestamps.
- Dynamically pack complete conversation units into the fewest safe Event Aligner groups. Persist group membership, attempts, usage, cost and results so only failed groups retry and completed mappings are reused after restart.
- Validate group identity, conversation/event/provider ownership, existing turn IDs, monotonic event order, customer speaker role and at least two providers mapped to the same user utterance. Invalid or insufficient mapping fails only the affected event and records an actionable reason.
- Derive the source interval from the union of accepted provider turns (`min(start)`, `max(end)`), not their intersection. Use the verified shared `record`/`user_record` timeline to validate signal and expand to nearby user activity when needed; never shrink inside the provider union. Noise/energy detection must never choose a different event or replace missing Event Aligner evidence.
- Do not impose a fixed ten-second limit from the earlier example. If the selected turns create an implausibly broad or cross-event interval, fail explicitly rather than truncate and risk dropping speech.
- Write one stable user-event WAV and reuse it across the review player and Benchmark materialization; never submit it to an ASR provider.
- Treat provider segment timestamps as clip-relative technical evidence; never expand the source interval from provider boundaries or LLM references.
- Fail the affected Case evidence explicitly when the shared timeline or interval is invalid; never invent a candidate or fall back to Excel time.
- Only use an MP3-derived range on WAV after import verified the common timeline. Never infer user/robot from stereo channels; the RiyadBank fixture has identical channel content and requires provider diarization plus historical roles.

## Review behavior

The page keeps one unresolved user event active. Historical production transcript and the current proposed label are visually adjacent. Provider candidates are equally weighted and have no preselected answer.

- Good: one action; label is the unchanged historical transcript.
- Bad: requires selecting a provider candidate or entering/editing a non-empty correct label before submission.
- Unclear: records completion and exclusion reason; produces no Benchmark and no manual Good/Bad count.
- Direct queue switching leaves the current unsubmitted draft pending.
- Every submission records reviewer identity available from the shared authenticated session, timestamp, source selection, edits, language, tag and evidence version.

## Metrics and reports

Mapped full-call provider turn texts are first-class report evidence. Report
materialization reads the persisted Case projection derived from immutable full-call
turns; Pass 2 `vendor_evidence` may replace the displayed text with a narrower quoted
span but must never be the only path by which a successful provider result becomes visible.
If any Pass 2 request group remains failed, the automated stage stays retryable and
does not freeze a normal preliminary report. A later successful retry appends a new
immutable preliminary version rather than overwriting an earlier retained version.

Older Qwen models may reject JSON Mode when `enable_thinking=true`; for those
models the runner omits `response_format` while retaining the frozen JSON-only
Prompt, parser, whole-group membership checks and full response-schema validation.
The verified `qwen3.8-*` family supports JSON Object with Thinking and therefore
enables it in both native and compatible protocols. Non-thinking Qwen and other
compatible providers continue to use JSON Mode.

Qwen connections preserve the administrator-selected Alibaba protocol. Compatible-mode URLs continue through the OpenAI client. Native URLs ending in `/api/v1`, including `prem.dashscope.aliyuncs.com`, use direct authenticated DashScope HTTP: `qwen3.8-*` routes to `services/aigc/multimodal-generation/generation`, uses `max_completion_tokens` so the frozen cap includes both reasoning and visible answer tokens, and enables its documented JSON Object response format for both evaluation passes. Compatible-mode `qwen3.8-*` also uses `max_completion_tokens`; older text models retain `max_tokens` compatibility. The exact verified qwen3.8-max packing policy uses its official 1,000,000-token context ceiling and 131,072-token maximum output, while unknown Qwen IDs retain the conservative provider fallback. Both passes preserve the same Thinking, JSON parsing, full schema validation, budget reservation and cost-ledger contracts. URL validation allows only HTTPS DashScope/Model Studio hosts and the two documented protocol paths.

Metrics are computed from immutable event/result rows, never from UI counters:

| Metric | Numerator | Denominator |
|---|---|---|
| Suspected ASR error rate | Pass 2 Bad + needs manual review | All valid user events successfully analyzed by Pass 1 |
| Manually confirmed error rate | Manual review Bad | Same valid user-event denominator |
| Review completion | Submitted Good + Bad + unclear | Total manual-review tasks |

The preliminary report freezes after the automated stage and shows zero/current manual coverage. Freezing also updates the owning batch's report pointer and final suspected numerator before the operation returns; startup recovery links and reconciles an already-frozen report when a prior interruption left those batch fields stale. Scenario tags are canonicalized to the frozen tag key before aggregation, while the renderer provides the same canonical projection for already-immutable historical payloads. The final report is a new version created after full or explicitly early review completion. Reports include excluded counts/reasons, actual Good:Bad balance, labels, language/scenario distributions, evidence-linked observations and structured proposed tags. They do not directly recommend changing production resources.

For a paused or partially failed batch that already has a preliminary report, an explicit “use current results” command reuses the immutable-report transaction but always freezes `final_partial` and `completed_partial`. It retains successful Pass 2 decisions, completed reviews, Benchmark rows, costs and checkpoints; pending reviews and incomplete/failed/unclippable Cases remain visible only as excluded coverage. The version-checked and idempotent command never starts the executor or any provider call.

## Benchmark lifecycle

- Automatic Good/Bad is inserted idempotently after admission.
- Manual Good/Bad is inserted after submission.
- Unclear and unreviewed Cases never create samples.
- Clip creation and database insertion use a recoverable two-phase status: pending clip, ready, or failed; failed files cannot appear downloadable.
- Later corrections create a new sample revision and retain the previous label/tag/source history.
- ZIP export is an async, expiring artifact for either a cross-page selected-ID set or a frozen all-pages filter snapshot. It contains root-level UTF-8 `benchmark.csv` plus `wav/<language>/<primary-scenario-tag>/<benchmark-id>.wav`; stable filesystem-safe slugs are used for folders, and a manifest is included when any item fails.

## Scenario-tag lifecycle

- The tag page queries persisted tag records; built-in display fixtures never define the production taxonomy.
- Editing appends a new `ScenarioTagVersion`; frozen batch, report and Benchmark references keep their prior version.
- Deleting an unreferenced tag removes it from the current taxonomy. Deleting a referenced tag writes `deleted_at`/tombstone state so it disappears from new selections while immutable snapshots and audit history remain readable.

## Configuration and credentials

- Reuse the existing Fernet and `VOICE_AGENT_STORAGE_KEY` pattern for credentials, but isolate evaluation connections from Bot-owned provider settings.
- ASR cards store Key only; provider capability stores the official async Endpoint and model parameters. LLM connections store Base URL when needed.
- Connection testing uses unsaved values, returns classified safe errors and persists only after explicit save.
- Persist evaluation connections in the `/data` SQLite volume as encrypted provider-owned records. Browser reloads and container rebuilds read safe metadata from the server; connection state must never depend on JavaScript memory.
- Azure GPT and OpenRouter use separate provider keys (`azure_gpt`, `openrouter`). Azure stores the validated full deployment chat-completions URL as non-secret metadata and sends the decrypted secret only as the Azure `api-key` header; OpenRouter uses the fixed `https://openrouter.ai/api/v1` OpenAI-compatible endpoint and Bearer authentication. Model selectors carry provider-qualified identities so identical model labels cannot resolve to the wrong connection or price row.
- A Resource Connections action is an atomic test-and-save operation: Soniox lists authenticated STT models, Speechmatics lists jobs without creating one, ElevenLabs creates and immediately discards an unused `batch_scribe` single-use token to validate the exact STT permission without uploading audio or requiring unrelated user-profile access, and LLM providers run the existing minimal streamed diagnostic. Only a successful test may replace the encrypted credential.
- Prompt versions store the complete visible text, explicit variable slots, and required schema metadata. Templates are read-only by default and require an explicit edit action; saving validates variable slots and outputs before activation. Context preview shows both the slot-bearing template and the fully rendered Prompt, with clickable field correspondence and complete dictionary entries.
- Pricing versions record unit, supplier currency, source and effective time. Website synchronization populates a draft; a person confirms before activation.
- Mixed-currency versions retain every supplier-native amount and freeze a reviewed CNY→USD rate. Batch snapshots use that immutable version for the unified USD safety budget while reports continue showing native amount, conversion rate and converted USD amount.
- Official-price synchronization uses only fixed provider allow-list URLs. The server verifies provider/model markers and the reviewed public price evidence before returning an all-or-nothing draft; network, unsupported-model or evidence drift failures never mutate the browser fields. Public list rates remain distinct from manually maintained contract/volume rates.
- Batch creation validates both selected LLM model IDs against the exact active pricing version before inserting the batch. A verified connection/model without a matching frozen rate is selectable for diagnostics but cannot start paid evaluation work; the user must first save a price version containing that model.
- A failed or partially failed batch does not create an immutable preliminary report. Instead, a read-only partial-results projection is assembled from persisted checkpoints and the cost ledger on request, labeled incomplete and non-final, and rendered through the same report-detail components. Retrying never mutates already-successful checkpoints and a later valid immutable report supersedes the partial-results entry.
- Reuse the existing `GET /api/catalogs` response for OpenAI and Gemini built-in model choices and `POST /api/llm/diagnostics` for an explicit minimal live model test. Diagnostics never mutate pricing. When and only when Cost settings explicitly requests evaluation-catalog registration and the real diagnostic succeeds, upsert the provider/model plus safe host and diagnostic metadata into the SQLite-backed evaluation model catalog; never persist the credential. New-batch selectors merge this catalog with built-in choices through `GET /api/evaluation/llm-models`.
- The production Evaluation UI may read safe Bot metadata from `GET /api/bots` and send `bot_id` plus a server-listed `llm_model` override when provider and normalized Base URL match and `has_saved_keys` is true. The diagnostic decrypts the Bot-owned Key server-side for this one request, never returns or copies it into Evaluation storage, and never mutates the Bot; otherwise the user must supply a new Key. Provider-prefixed input such as `Gemini/gemini-3.8-flash` is normalized before lookup.

## API surface

### Ephemeral Chinese comparison translation

- Static interface copy is resolved entirely from the frontend locale dictionary and is never included in a model request.
- In Chinese mode, opening a real report conversation requests translations only for the currently visible original event texts through an authenticated evaluation API. The runner reuses the batch snapshot's frozen Pass 1 provider/model and never exposes credentials to the browser.
- The response is ephemeral. The browser keeps it in a session-scoped cache; neither source events nor translated text are stored in SQLite, reports, Benchmark rows, logs, or evidence payloads.
- The external call still uses the batch's frozen pricing and hard-budget reservation. A rejected display request does not change an already frozen batch's lifecycle status. Only content-free usage, cost and audit metadata are persisted under a display-translation stage; these records cannot change report metrics or labels.
- Requests are bounded by event count and text size. Failure, unavailable credentials, malformed model output, or exhausted budget leaves the original text visible and returns a safe “translation unavailable” state.
- PD-032 extends the same display-only path to manual review and Benchmark Library. Manual review batches the current task's Arabic production transcript, Arabic context turns and Arabic provider candidates. Benchmark Library groups the current page's Arabic labels by source batch, with at most 20 visible samples per page; sample details add the Arabic historical event text and label. A browser-session cache keyed by batch and exact source text prevents repeat calls without persisting translations.
- Under PD-033, display translation makes at most two attempts for the original group. If both fail and the group has more than four texts, it falls back to stable chunks of at most four texts with at most two attempts per chunk, then restores the original ordering. Budget rejection short-circuits immediately; malformed-output recovery never pauses the evaluation batch and records only content-free attempt/count audit metadata.
- PD-034 passes DeepSeek's documented `extra_body={"thinking":{"type":"disabled"}}` only from the display-translation call site through an opt-in `_llm_json` flag; its default remains false so Pass 1/Pass 2 and every existing caller retain their prior reasoning behavior. Chunk failures produce `null` translation slots plus content-free partial metadata, while successful slots remain renderable and cacheable.
- Automated verification injects a mock translator and asserts that local UI copy is absent from the request. Agent-driven verification must not send real customer text or incur a paid call.

The implementation should group authenticated JSON APIs under `/api/evaluation` for configurations, upload sessions, batches, cases, reviews, reports, Benchmark queries and exports. Audio playback and downloads use short-lived, authorization-checked URLs or streaming endpoints. State mutations require expected version and idempotency key; stale edits return conflict rather than silently overwrite.

Batch deletion is a non-running cleanup command, not a lifecycle shortcut. It is allowed for `audit_only`, terminal failed, explicitly stopped, awaiting-review, or completed batches after explicit confirmation. Active, paused, and budget-paused work must be stopped first so remote jobs and costs remain traceable. The transaction removes batch-owned child rows before the batch, leaves shared source/configuration tables intact, and appends a content-free audit tombstone after deletion. A New Evaluation dialog owns one stable creation idempotency key for its lifetime; network retries reuse it, while opening a fresh clean draft creates a new key. Unstarted upload candidates can be discarded independently without changing the active source dataset.

## Security and retention

- Use the existing authenticated product boundary; this release intentionally gives the shared evaluation role access to all evaluation batches.
- Audit create/start/stop/resume, configuration changes, connection tests, review submission, early completion, playback, download and label edits.
- Do not emit raw transcript, original filename beyond safe relative path, audio content, provider raw body or credential in ordinary logs.
- Evaluation source data and formal Benchmark use a separate minimum 10-year retention class and are exempt from normal call-history cleanup.
- Provider-side deletion capability and retention vary; adapters should delete remote source/result artifacts after successful local capture where supported and record the outcome. Failure is surfaced for operational follow-up without deleting local evidence.
- A blocked upload is an unstarted dialog draft, not durable batch history. Opening New Evaluation discards the prior pending-candidate metadata and its exact managed candidate directory, then renders the active dataset and default controls. Active datasets and started/frozen batches are never removed by this reset.
- Historical timestamp regressions, events beyond recorded duration and MP3/WAV duration drift remain visible audit warnings. They do not block batch creation, but affected ranges cannot be admitted as reliable precise-cut Benchmark clips without a later repair or explicit fallback.
- Benchmark deletion is a single-sample hard delete. One transaction removes the current row and revision rows and writes a content-free tombstone; after commit, the service removes only the resolved clip path when it is inside the managed Benchmark clip root. Upstream conversation, batch, report and review rows are never deletion targets.
- Pass 2 planning computes final-message size before dispatch and deterministically partitions oversized conversations by Case membership. Runtime timeout/structure recovery creates stable child groups from the exact failed Case membership, marks the parent superseded, and never repays successful work. A size violation never reaches the provider; a single-Case leaf receives at most one additional attempt before remaining explicitly failed.
- Stage progress persists one whole-stage business-unit universe plus active external operations. Each in-flight operation exposes only a safe identifier, stage, provider, ordinal/total, `started_at` and `last_heartbeat_at`. The browser derives elapsed time from the server start time and updates its display once per second; it never increments the durable percentage. Every concurrent in-flight request is shown as one compact row and disappears on completion. Paused/partially-failed summaries show only succeeded and failed business units (Pass 1 conversations, Multi-ASR full-call provider jobs, Pass 2 Cases); group/attempt/error detail remains in the task detail or log. A stale heartbeat changes the copy to state synchronization interrupted rather than presenting a healthy wait.
- A guarded planning or execution failure changes the batch to `partially_failed` without replacing the last meaningful stage, progress, completed checkpoints or recorded cost. Local input/output-cap rejection uses a preflight category distinct from provider timeout, invalid JSON and invalid Segment ID.

## UI delivery workflow

This is a high-risk page Change.

1. User Gate 1: approve Delta Specs, current prototype, annotations, state matrix, fixed RiyadBank-derived fixture and baseline screenshots.
2. Engineering Checkpoint A: use the production Evaluation route/components with fixture data to verify information hierarchy, Good/Bad controls, report entry, dialogs/drawers and responsive layout.
3. Engineering Checkpoint B: keep the same UI code, wire real APIs and persistence, and cover loading/empty/error/partial/long-content/bilingual, refresh and restart states.
4. Engineering Checkpoint C: run independent functional, accessibility, visual-diff and evidence verification.
5. User Gate 2: request final product acceptance only after Checkpoints A-C pass.

Manual review is an ongoing operational queue rather than a delivery-gate checklist. A
real batch may remain on its immutable preliminary report with pending reviews while
Checkpoint C and User Gate 2 assess the implemented review workflow, persistence,
early-completion path, and report-version contract. Completing every review in that
specific batch is not required for product acceptance (PD-028).

Fixture mode may replace only the data source through the runtime adapter. It must not use a separate static page, route or component tree.

Baseline updates require a recorded reason and renewed product confirmation. Automated screenshots detect differences but do not replace User Gate 2 acceptance.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| LLM confidently invents a label | Schema plus evidence admission; no confidence threshold; ambiguous cases go manual |
| Extra Good biases toward easy cases | Deterministic stratified selection and origin disclosure |
| Duplicate webhook or restart duplicates cost/data | conversation/provider and batch/conversation/event idempotency keys |
| Historical duration/timeline defects cut wrong audio | Keep evaluation non-blocking, retain an audit warning and exclude affected ranges from precise Benchmark clipping until repaired or explicitly reviewed |
| Long-term audio grows storage | Separate retention class, storage monitoring and explicit compliance policy; no silent cleanup |
| One provider outage blocks all work | Partial evidence rule and targeted retry |
| English UI contains Chinese fixture text | Stable bilingual fixture and English-residue browser assertion |
| Sensitive data appears in logs | Structured safe logging, redaction tests and audit metadata allowlist |

## Decisions intentionally deferred

- Automated WER/CER comparison of ASR resources after the Library exists.
- Fine-grained roles, assignment and concurrent review locking.
- Production ASR configuration changes generated from report observations.
- Distributed queue/storage architecture needed only after measured single-node capacity is insufficient.
