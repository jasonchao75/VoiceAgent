# ASR Evaluation 稳定性差距矩阵

## 1. 审查口径

- 审查基线：`main` / `68fe2d8`（`fix(evaluation): reconcile retries and turn reviews`）。
- 当前工作区仍有其他任务产生的未提交文档、测试和交付记录改动；这些改动不作为已部署证据。
- 本矩阵只审查稳定性收口，不重新评审 ASR 判断质量或新增产品功能。
- 证据等级：`static` < `fixture/mock` < `local-real` < `external-real canary` < `production batch`。
- 状态定义：
  - **已强制**：规则已由数据约束或统一运行逻辑强制，且存在匹配测试；仍可能缺更高等级证据。
  - **部分强制**：某些阶段或路径已实现，但存在旁路、范围缺口或证据不足。
  - **未强制**：规则只存在于文档/UI，或当前代码明确违反该规则。

## 2. 总结

| 结论 | 数量 | 含义 |
|---|---:|---|
| 已强制 | 2 | 配置快照、Benchmark 全局去重已有明确数据/代码约束 |
| 部分强制 | 9 | 主流程、部分结果、canonical 终态、成功复用、attempt 审计、幂等、Lease、SQLite、分级证据已有局部实现 |
| 未强制 | 6 | 数据集绑定、重试计划、统计范围、超时费用、统一执行器、放量门禁仍缺失 |

当前不能进入 82 通正式重跑。P0 中至少有四项仍未形成硬约束：批次数据集绑定、可重试计划、超时费用不丢失、分级放量门禁。

## 3. 第一层：产品流程与数据职责

| ID | 稳定规则 | 当前状态 | 代码/测试证据 | 高等级证据 | 缺口与处理 | 优先级 |
|---|---|---|---|---|---|---|
| P-01 | 固定六阶段；完整 `record` 每 conversation/provider 一次；`user_record` 只负责语音岛、试听和 Benchmark | 部分强制 | `design.md` 与 Delta Spec 已冻结职责；执行器已有 full-call ASR、audio-first alignment 和 Pass2 投影；相关 fixture/mock 覆盖在 `tests/test_evaluation.py` | 小包 Event Aligner 有 external-real；PD-061 完整链路尚无新生产批次证据 | 不再改流程；在 S2/S3 对任务数、Case 数和外部调用数逐项对账 | P1 |
| P-02 | 每个批次永久绑定创建时的数据集版本 | **未强制** | 上传会生成 `dataset_id`，但激活新包时会替换全局 source index（`src/evaluation/storage.py:1930`）；建批快照只保存 source 名称和数量，没有 `dataset_id`（`src/evaluation/storage.py:5539`） | 无跨数据集恢复 production batch 证据 | 增加 batch→dataset 外键/快照和批次所属 source rows；查看、重试、报告必须按 batch dataset 读取 | **P0** |
| P-03 | 部分资源失败时合格 Case 继续；负责人可明确使用现有结果结束 | 部分强制 | `complete-with-current-results` API、`completed_partial` 状态和测试已存在；单家 ASR 成功继续路径有 mock 覆盖 | 既有批次路径有生产诊断，但“新稳定基线”未完整重跑 | 纳入 S1/S2：失败资源排除、成功结果保留、报告覆盖率和零外部调用逐项对账 | P1 |
| P-04 | 重试前展示计划、不可重试项、预计费用和停止条件；无可重试资源时不启动 | **未强制** | 页面仍只有通用 `Retry failed resources`；`act_on_batch()` 直接把 `partially_failed/completed_partial` 改回 `running`（`src/evaluation/storage.py:5685`），没有先生成/确认 retry plan | KI-171 仍为 Open | 先实现只读 retry-plan API，再由确认命令携带 plan version 执行；空计划保持原状态 | **P0** |
| P-05 | 当前批次、最近冻结报告、跨批次去重累计分开展示 | **未强制** | `summary()` 同时取当前 active source conversation 数、最近有报告批次的错误率和全局 Benchmark（`src/evaluation/storage.py:6597`）；前端把它们并列为同一组卡片 | 生产 56/82 通页面已复现误导 | 拆为三个有显式 scope/type 的 API 投影；前端标题和分母必须携带 scope | P1 |

## 4. 第二层：数据与状态不变量

| ID | 稳定规则 | 当前状态 | 代码/测试证据 | 高等级证据 | 缺口与处理 | 优先级 |
|---|---|---|---|---|---|---|
| D-01 | Prompt、上下文、词典、模型、协议、价格和预算在批次内冻结 | **已强制** | `create_batch()` 将配置和 pricing version 写入 `snapshot_json`；冻结价格和配置已有回归测试 | 多个真实批次已使用冻结配置 | 保留；补入 S1 重启前后一致性断言 | P2 |
| D-02 | 批次终态只根据当前 canonical Case 的最新有效检查点计算；superseded/历史失败不污染终态 | 部分强制 | `68fe2d8` 增加 canonical Case reconciliation 和回归；执行器只以当前 canonical keys 计算 Pass2 失败 | CI、生产部署、公开健康和部署 SHA 已通过；尚未用真实“父组失败→子组成功”路径验证终态 | 在 S2 运行真实恢复场景，并用登录态只读核对 Case、组谱系和最终状态 | **P0，待证据** |
| D-03 | 已成功结果不得因 sibling 失败、重试或重启退回 | 部分强制 | Pass1、Align、Pass2 分别有成功检查点复用和拆组测试；Event Aligner restart-safe mock 已覆盖 | 没有六阶段逐阶段强制重启的 local-real 证据 | 建立跨阶段 success-monotonic 属性测试和 S1 强制重启脚本 | P1 |
| D-04 | 尝试历史追加保存，当前结果由 canonical 指针解析 | 部分强制 | group、telemetry、cost 有历史/幂等记录；但部分 checkpoint 使用业务键 `UPSERT` 更新 status/attempt/result，不能单靠 checkpoint 表还原每次尝试 | 无完整 attempt audit 对账 | 不立即改 Schema；先审计现有 telemetry/cost/group 是否足够重建每次外部调用，证据不足再补 append-only attempt 表 | P1 |
| D-05 | 请求发送后超时不得直接释放为“未花费”；必须保留 `usage_unknown` 或等价待核销状态 | **未强制** | `_llm_json()` 的各 provider 分支在未取得 usage 时都会在 `finally` 调用 `release_budget()`；reservation 表无状态字段，只有存在/删除两态 | KI-177 已由生产超时行为证明风险 | reservation 增加 `reserved/sent/settled/usage_unknown/released` 状态；只有发送前失败可 release | **P0** |
| D-06 | Benchmark 以 `(conversation_id,event_id)` 全库唯一，冲突候选不覆盖 | **已强制** | 全局唯一迁移、写入前查询与冲突丢弃已经实现；测试覆盖重复迁移、复用和冲突 | 尚未作为稳定 canary 的重点对账项 | S2/S3 验证重跑不增加重复样本即可 | P2 |

## 5. 第三层：统一执行、重试与恢复

| ID | 稳定规则 | 当前状态 | 代码/测试证据 | 高等级证据 | 缺口与处理 | 优先级 |
|---|---|---|---|---|---|---|
| E-01 | Pass1、辅助对齐、Pass2 和 ASR 使用统一失败分类、retryability、幂等和恢复语义 | **未强制** | LLM 底层请求 `_llm_json()` 共用，但 Pass1、Align、Pass2 仍分别维护重试/拆组循环；ASR 又有独立调度逻辑。KI-171 证明顶层 retry action 没有统一计划 | 无跨阶段统一故障矩阵 | 先定义 `ExecutionAttempt/FailureClass/RetryPlan` 契约，再逐阶段接入；不一次性大重写 | P1 |
| E-02 | 外部请求拥有稳定幂等身份；失败父组 superseded；成功子项不重发 | 部分强制 | Pass1/Align/Pass2 group ID 和 membership 测试较完整；命令 API 也使用 idempotency key | Event Aligner 小包 external-real 成功；失败拆组只有 mock | S2 人为触发一次可控结构失败或超时，核对调用数、组谱系和费用 | P1 |
| E-03 | Lease、心跳和重启恢复能区分正在执行、结果未知和可安全重试 | 部分强制 | batch lease/heartbeat 存在；有 lease 互斥和 Event Aligner 模拟重启测试 | 无每个外部阶段的 local-real 进程中断证据 | S1 在发送前、等待中、成功落库后分别杀进程；断言零重复调用和正确状态 | P1 |
| E-04 | SQLite 锁竞争不能伪装成供应商失败；写入使用有界并发和事务 | 部分强制 | Event Alignment 已使用批量事务和 busy timeout；相关定向测试通过 | 只验证了特定 Align 写入路径 | 对 Pass1、ASR、Pass2、复核和报告统一做并发写压力；保留 SQLite 还是升级数据库以证据决定 | P1 |

## 6. 第四层：验证和放量门禁

| ID | 稳定规则 | 当前状态 | 代码/测试证据 | 高等级证据 | 缺口与处理 | 优先级 |
|---|---|---|---|---|---|---|
| V-01 | 发布必须依次通过 S0 静态/Mock、S1 本地恢复、S2 3–5 通真实 canary、S3 20 通重复运行 | **未强制** | 当前 Change gate 会列出 Known Issues/Unverified Items，但多个稳定性问题仍只是 WARNING，不阻止发布 | 既有真实探针和生产批次是碎片化证据，不构成阶梯 | 在 verifier 中新增 stability gate：P0/P1 Open 或前级证据缺失时返回非零 | **P0** |
| V-02 | 只有 production batch 能证明大批量稳定；低等级证据不得代替高等级 | 部分强制 | delivery-status 已区分 unverified items，文档也区分证据等级 | PD-061、超时拆分、完整 Event Aligner 等仍缺整批真实证据 | 严格按 S2→S3→S4 放量，禁止直接用 82 通发现下一轮架构问题 | **P0，待执行** |

## 7. 已知问题映射

| 交付记录 | 本矩阵位置 | 处置 |
|---|---|---|
| KI-177：超时请求可能已计费但预算记录被释放 | D-05 | Phase 1 P0 |
| KI-171：Retry failed resources 会重跑不可重试/确定性失败 | P-04、E-01 | Phase 1 先做 retry plan，Phase 2 统一执行 |
| KI-188：历史批次没有冻结 dataset identity | P-02 | Phase 1 P0 |
| KI-189：顶部错误率混用历史报告与当前数据 | P-05 | Phase 3；API 先于 UI |
| KI-200：历史失败污染当前 Pass2 终态 | D-02 | `68fe2d8` 已合入并部署；真实恢复场景未验证前保持“部分强制” |
| UV-030/021/026 等真实路径未验证项 | V-01、V-02 | 纳入 S2/S3，不再各自零散补探针 |

## 8. 推荐实施顺序

### Milestone A：阻止继续制造错误状态

1. P-02：批次冻结 dataset identity。
2. D-05：超时费用改为 `usage_unknown`，不再直接释放。
3. P-04：只读 retry plan；过滤不可重试资源；空计划不启动。
4. D-02：完成登录态只读回证，并纳入 S2 的真实失败拆组恢复验证。

退出条件：四项均有数据层/服务层测试；Change gate 将对应 Open P0 视为 blocker。

### Milestone B：统一状态和执行语义

1. 定义 canonical workset、attempt、superseded 和 retry plan 数据契约。
2. 先迁移 Pass1 与 Pass2，再迁移辅助 Align 和 ASR；每阶段独立回归。
3. 建立成功单调、重复命令、重启和预算的属性/故障测试。

退出条件：E-01–E-03 全部至少达到“部分强制”，S1 通过。

### Milestone C：修正产品投影

1. API 拆分当前批次、最近报告、跨批次累计三个 scope。
2. UI 展示 retry plan、费用上限和不可重试项。
3. 双视口检查所有状态、长错误和部分结果。

退出条件：P-04、P-05 达到“已强制”，Checkpoint A/B/C 重新通过。

### Milestone D：分级真实放量

依次执行 S2 3–5 通、S3 20 通两次、S4 82 通。任一级出现数据错误、重复调用、状态卡死或费用失真，回退对应 Milestone，不通过增加补丁绕过 Gate。

## 9. 当前可信结论

可以相信的：

- 当前代码已经具备大量有价值的局部能力：冻结配置、稳定 group identity、部分失败保留、Benchmark 去重、Lease 和多阶段检查点。
- `68fe2d8` 对 Pass2 canonical 终态和 Turn 复核的修复有静态/fixture/mock/独立验收证据。

现在不能宣称的：

- 不能宣称历史批次已绑定自己的数据集。
- 不能宣称 Retry failed resources 只会运行安全且可重试的任务。
- 不能宣称超时调用的费用不会漏记。
- 不能宣称顶部统计属于同一个范围。
- 不能宣称完整六阶段已经通过可恢复的生产 canary。
