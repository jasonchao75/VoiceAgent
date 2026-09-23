# Gate 1 One-page Review — ASR Automated Evaluation

Status: PASS — V1.20 renewed User Gate 1 confirmed under PD-076
Date: 2026-09-23
Approver: Product owner confirmed the V1.20 visual baseline and Turn-review flow with “可以。” under PD-076
Historical prototype checksum prefix: `1c5313…` (superseded and unrecoverable; not a frozen baseline). The unique frozen baseline is declared in `prototypes/README.md` under PD-019.

## V1.19 confirmed amendment

- Running progress shows only current external requests, one row per concurrent request, with provider/stage, ordinal/total and a per-request elapsed timer that changes every second.
- Durable backend checkpoints remain authoritative; the timer never advances the percentage, and a stale heartbeat becomes “status sync interrupted.”
- Paused and partially failed batch rows show only `N failed · M succeeded`; request-group and attempt details remain in task detail/logs.
- The run page has six stages: Multi-ASR is stage 3, Event Alignment is an explicit stage 4, and Pass 2 is stage 5.
- Event Alignment uses bounded requests, deterministic timeout/schema splitting, durable restart reuse, and one continuously advancing elapsed timer per active request.
- Historical V1.19 checksum prefix: `17829744…`; this baseline is superseded by PD-076.

## V1.20 frozen amendment

- Stage 4 is renamed to “Audio & evidence alignment / 音频与证据对齐”; the all-conversation LLM Event Aligner is removed from the normal path.
- Pure-user audio freezes speech-island boundaries first. Historical timestamps are audit-only; event order is the hard constraint. Number/spelling normalization, adjacent robot turns and cross-provider consistency rank only legal assignments and cannot move audio boundaries.
- Multiple adjacent historical events assigned to one speech island become one Case with every source event ID retained. Each Case persists independently so an ambiguous sibling cannot discard a valid Case.
- Only non-unique or low-evidence Cases use the batch-frozen LLM. It may select existing IDs only; deterministic validation rejects illegal output and routes the Case to manual review.
- Reports separately show historical annotation issue groups and affected Turn-row counts, with group-first details and audio evidence; neither count changes the ASR error rate.
- Historical Turn candidates enter a dedicated tab inside Manual review. Reviewers confirm or reject one complete anomaly group; reports count only confirmed groups/rows and disclose Turn-review coverage. Turn review never rewrites the source workbook or creates Benchmark samples.
- Pass 2 restart reuses a canonical historical group by idempotency key plus exact Case membership. The legacy singleton Align structure failure remains immutable diagnostics and is never directly replayed.
- Benchmark identity is globally unique by conversation/event. Later identical results reuse the canonical sample; later conflicting results are discarded without adding, overwriting, revising or creating a conflict-review task.
- The unique current frozen SHA-256 is recorded in `prototypes/README.md`; V1.19 is superseded historical evidence and must not be used for current verification.

## Outcome

把已验证的离线 ASR 质检流程产品化：逐通导入历史与两类录音，第一轮筛疑点，多家异步 ASR 按对话转写一次，第二轮判断，人工只复核不确定句子，最后形成批次报告和可追溯 Benchmark。

## Confirmed flow

配置版本 → 上传逐通三件套 → 校验 → 第一轮疑点/额外 Good 池 → 每通多 ASR 一次转写 → 纯用户音频冻结语音岛 → 确定性证据匹配（仅歧义 Case 调 LLM）→ 第二轮 Good/Bad/人工 → 自动阶段先补 Good → 人工明确 Good/Bad/听不清 → 最终再补 Good 到 1:1 → 最终报告与 Benchmark。

## Acceptance anchors

| Anchor | Expected result |
|---|---|
| Input | 56 个 Excel + 56 MP3 + 56 WAV 按完整 ID 一对一关联；不是单一总 Excel |
| Historical regression reference | 现有 RiyadBank 56 通数据在此前离线运行中曾得到 30 个疑点：20 Bad、6 Good、4 复核；这不是固定产品指标，真实模型重跑允许变化 |
| Formula fixture | 仅当固定 mock 输入为 20 Bad、6 Good、4 复核、441 个有效用户句子时，结果必须为 `(20 + 4) / 441 = 24 / 441`，不得显示 30/441 |
| ASR cost | 同一对话每家一次；额外 Good 复用结果，不新增 ASR job |
| Good balance | 疑点复判 Good + 同对话正常池抽样，最终目标 Good:Bad=1:1；不足需披露 |
| Auto admission | Schema、决定、非空标注、证据定位、至少一家 ASR；不使用 confidence 阈值 |
| Manual review | 历史/建议就近；显式 Good 或 Bad；Bad 要正确文本；听不清已复核但不入库 |
| Reports | 自动阶段后初步报告；复核完成/提前结束后新最终版本；版本不可覆盖 |
| Benchmark | 用户 WAV、标注、类型、语种、标签、来源、两种 Good origin 和完整追溯；conversation/event 全库唯一，跨批次冲突直接放弃新候选 |
| UI | 中英双语；英文无中文残留；所有浮层无横向滚动 |

## Self-test route

1. 用 `benchmarks/RiyadBankConversation/` 派生固定 56 通测试包，另造缺失、损坏、时长偏移和错误 Excel。
2. 将此前离线结果固化为 mock 回归夹具，验证 20/6/4 输入下得到 24/441、统一回听区间和 1:1 Good 补足；另用真实 LLM 重跑观察结果，不要求仍为 30 个疑点。
3. 注入单家失败、全部失败、重复 webhook、重启和预算触顶，验证只重试失败项且不重复计费/入库。
4. 覆盖人工 Good、Bad 候选编辑、手填、听不清和提前结束，核对报告覆盖与 Benchmark 排除。
5. 完成桌面/窄屏、中英文、长阿文/ID、键盘、播放器、下载和浮层 overflow 验收。

## Gate decision

- [x] 产品确认原 V1.17 行为契约和验收锚点
- [x] 产品确认 V1.19 原型作为新的唯一 UI baseline
- [x] V1.19 Gate 1 amendment 已通过，允许实现本次正式页面改动
- [x] 产品确认 PD-072 方案 C 及本轮七项规格范围
- [x] 产品确认 V1.20 候选原型与修订后的行为规格，续订 User Gate 1（PD-076）
- [x] V1.20 User Gate 1 已通过；后续明确开发指令可进入正式 UI 与运行时实现
