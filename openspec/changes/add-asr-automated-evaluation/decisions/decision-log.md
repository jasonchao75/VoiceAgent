# Decision Log

仅记录有可追溯用户确认的决定。来源统一为当前 Codex 任务 `codex://threads/01a0a4bf-81a0-74e3-84ac-159a97f0640c`；消息 ID 可读取时直接记录，不可读取的早期 Browser Comment 用页面、评论和确认原话定位，不以 Agent 推断代替确认。

## Status

- Recorded decisions: 33 confirmed, 3 superseded, 1 invalidated
- Open product decisions: 0
- Engineering Checkpoint C: PASS (independent verification); User Gate 2 remains product-owner acceptance
- Last reviewed: 2026-09-20

## Decisions

### PD-044 — 先发布 Cost Settings 修复并保留生产数据

- Status: Confirmed
- Date: 2026-09-21
- Source question: KI-128 修复完成后的生产发布顺序
- Decision owner: Product owner
- Source thread/message: 当前 Codex 任务，用户在确认保存行为后明确要求先推送线上
- Confirmation quote: “可以先推送到线上。另外，现在线上有失败的evaluation之后就一直不生成cases，我现在还不知道怎么回事。你先把本次修复推到线上吧”
- Decision: 先将 KI-128 的 Cost Settings 模型价格增量保存、选择恢复、别名匹配及执行期冻结计价修复发布到生产；本次常规发布保留现有生产 Evaluation 数据，不执行首次上线时的一次性空历史清理。失败批次不生成 Cases 作为独立工程缺陷在发布后继续定位。
- Reason: 先恢复新批次的价格门禁可用性，避免与另一个运行时缺陷混在同一次未发布修复中。
- Consequences: 发布范围只能包含 KI-128 相关代码、测试和交付记录；不得夹带工作区其他改动。生产发布后仍需为从未成功落库的 `gemini-3.8-flash` 保存一次价格。
- Updated artifacts: `tasks.md`、`verification/delivery-status.json`、KI-128 修复提交与生产部署记录。
- Verification: GitHub CI/CD 全绿、线上健康检查成功、部署提交一致；生产 Evaluation 历史保持不变。

### PD-041 — 独立 Azure/OpenRouter 资源与失败批次部分结果

- Status: Confirmed
- Date: 2026-09-20
- Source question: Azure GPT 连接方式、OpenRouter 资源与失败批次结果可见性
- Decision owner: Product owner
- Source thread/message: 当前 Codex 任务，用户在 Azure 独立资源方案说明后明确扩展要求
- Confirmation quote: “新增独立Azure GPT资源；另外，再新增OpenRouter资源。最后，这个批次即使失败了，也应该有成功部分的内容啊，不能什么都不显示。”
- Decision: Azure GPT 与 OpenRouter 分别作为独立加密资源，不覆盖 OpenAI/GPT 或其他连接。Azure 按 deployment URL、`api-key` 与 `api-version` 调用；OpenRouter 使用其官方 OpenAI-compatible Base URL 和 Bearer Key。失败或部分失败批次必须提供明确标记为“部分结果、非完整报告”的入口，展示截至失败时已持久化的成功 Pass 1、事件级 ASR、成功 Pass 2 分组、成本和失败原因；不得把部分结果冻结或呈现为正常初步/最终报告。重试继续复用成功检查点。
- Reason: 新资源需要隔离凭证和路由语义；执行失败不能让已经付费并成功持久化的证据在界面消失。
- Consequences: 模型选择必须携带 provider 身份，避免不同资源的同名 Model ID 冲突。连接真实测试成功后才可登记模型；既有价格完整性规则继续生效，未配置对应 provider/model 冻结价格时不得启动批次。当前聊天中暴露的 Azure Key 不写入代码、日志或数据库，需轮换后由用户在页面输入。
- Updated artifacts: Delta Specs、design、tasks、prototype mapping、连接/执行器、部分结果 API/UI 与回归测试。
- Verification: Mock/fixture 覆盖 Azure 请求 URL 与鉴权、OpenRouter路由、同名模型隔离、密钥不回显、部分失败结果展示和成功检查点复用；真实外部连通测试仍需逐次授权。

### PD-040 — 删除旧批次并从空结果重新测试

- Status: Confirmed
- Date: 2026-09-20
- Source question: Qwen 与报告修复完成后的重新测试准备
- Decision owner: Product owner
- Source thread/message: 当前 Codex 任务，用户明确要求删除历史批次后自行重新测试
- Confirmation quote: “那你修完了是吧，把历史批次删掉吧，我重新再测一遍”
- Decision: 通过受支持的事务清理路径删除旧批次 `EV-20260920-566C` 及其批次自有报告、检查点、复核、Benchmark、成本和派生音频；保留共享的 56 通来源数据、连接和配置。删除后用户新建的运行批次不属于历史清理范围，不得误删。
- Reason: 用户需要在修复后的系统上从干净的结果状态重新验证完整流程。
- Consequences: 旧批次及其不可变 R1/R2 报告不再可访问；保留不含客户内容的删除审计墓碑。
- Updated artifacts: `tasks.md`、删除状态覆盖、回归测试和交付记录。
- Verification: `EV-20260920-566C` 所有含 `batch_id` 的归属表行数均为 0，删除墓碑存在；共享来源 56 通、1 个 Context 和 5 个连接仍存在。

### PD-039 — 修复重复报告入口、空 ASR 证据与 Qwen 第二轮 400

- Status: Confirmed
- Date: 2026-09-20
- Source question: 当前真实批次出现两个报告按钮且报告内 ASR 转写为空
- Decision owner: Product owner
- Source thread/message: 当前 Codex 任务，用户在根因说明后明确要求修复
- Confirmation quote: “好的，那你修复一下吧。Qwen HTTP 400的详细原因也最好看下”
- Decision: 批次列表只保留一个报告入口；报告直接展示已成功落库的事件级 ASR 转写与纯用户音频，不以第二轮 `vendor_evidence` 是否存在决定原始证据可见性；第二轮仍失败时保持可重试失败状态，不伪装成正常最终报告。Qwen 第二轮继续启用 Thinking，但不得同时发送其官方明确不兼容的 JSON Mode 参数，结构正确性由冻结 Prompt、JSON 解析和完整 Schema 校验保证。
- Reason: 当前批次三家 ASR 已有 166 条成功结果，却因 8/8 第二轮请求组被 Qwen HTTP 400 拒绝而在报告中显示为空；前端还把同一 report 动作拼接了两次。
- Consequences: 修复不改变冻结视觉基线；失败重试成功后追加新的不可变初步报告版本，历史版本不覆盖。
- Updated artifacts: Delta Spec、design、tasks、运行时、存储和回归测试。
- Verification: 定向后端测试、双视口页面测试、本地容器重建后核对当前批次。

### PD-001 — 每通数据包只有三类输入

- Status: Confirmed
- Date: 2026-09-16
- Source question: New Evaluation 上传包结构
- Decision owner: Product owner
- Source thread/message: `codex://threads/01a0a4bf-81a0-74e3-84ac-159a97f0640c`，Browser Comment 1，`evaluation.html` New Evaluation 弹窗，用户消息以“什么意思？你帮我尝试上传的时候遇到了问题吗”开头
- Confirmation quote: “这里有两个 conversation_history，实际上我要上传的只有三个内容啊。”
- Decision: 上传包只有 `conversation_history/`、`record/`、`user_record/` 三类输入；文件存在性与工作簿结构是同一输入的校验结果，不展示成第四种上传内容。
- Reason: 避免把校验维度误解成额外数据源。
- Consequences: 上传模板、校验结果和修复入口必须围绕三类目录组织。
- Updated artifacts: `tasks.md` 3.1–3.6；相关 Delta Specs 和 New Evaluation 原型。
- Verification: 一个 ZIP 只包含三类目录时可完成关联；UI 不出现第二个上传型 `conversation_history`。

### PD-002 — 历史事件时间与 duration 越界仅提示

- Status: Confirmed
- Date: 2026-09-16
- Source question: 历史源数据参考校验是否阻塞
- Decision owner: Product owner
- Source thread/message: 同一任务 Browser Comment 1（事件先后顺序）；message `01a0aa6c-5b79-7823-b816-24f2b63f2ddc`（duration）
- Confirmation quote: “这个只作为参考，不能强校验啊。”；“这个 duration 的问题也先忽略……都先只提醒吧。”
- Decision: `event_time` 倒退和事件超出音频 duration 都是参考警告，不阻塞批次启动。
- Reason: 两类问题可能来自历史系统缺陷，不能阻断评测。
- Consequences: 仍保留审计提示；结构缺失、无法解析等问题可以继续阻塞。
- Updated artifacts: `tasks.md` 3.2、3.4、9.9、11.10。
- Verification: 含此类警告的56通包仍显示56/56可运行。

### PD-003 — Gate 2 页面结构与视觉不得在接线时静默改版

- Status: Confirmed
- Date: 2026-09-16
- Source question: Gate 2 后续业务接线是否允许改变页面
- Decision owner: Product owner
- Source thread/message: message `01a0a938-098d-7582-b5ff-5f3af772b60f`；同一任务 Browser Comment 1，用户消息以“不对，怎么样式跟Gate2又不一样了”开头
- Confirmation quote: “这次感觉没什么问题了，可以推进下一阶段了。”；“你不就应该是gate2形成的页面都冻结了吗？”
- Decision: Gate 2 已确认的页面结构与视觉在业务接线阶段不得静默重做。
- Reason: API 接线不应改变已验收的页面基线。
- Consequences: 任何有意视觉偏离必须重新确认；本决定不确认某个 SHA，具体冻结文件仍由 Q-005 阻塞。
- Updated artifacts: `tasks.md` 0.6、8.17、11.7；`verification/ui-checklist.md`。
- Verification: 唯一 SHA 确认后，对固定桌面和窄屏做视觉 diff。

### PD-004 — 清除模拟结果并只用真实56通源数据

- Status: Confirmed
- Date: 2026-09-16
- Source question: Mock 结果是否可进入真实验收
- Decision owner: Product owner
- Source thread/message: message `01a0aa07-c891-7910-b8c3-6ed4ee917e3e`
- Confirmation quote: “确认，清除全部模拟结果，接通真实数据解析，审计现有56通数据。”
- Decision: 模拟结果不得进入正式报告、Benchmark 或 Gate 3；真实结果必须追溯到用户上传的56通源数据。
- Reason: 伪造文本与真实录音不匹配，没有验收意义。
- Consequences: Gate 2 fixture 只能用于静态回归并必须明确标识。
- Updated artifacts: `tasks.md` 9.7、11.1、11.11；`verification/delivery-status.json`。
- Verification: 运行时无模拟 batch/review/Benchmark 行，真实批次保留源文件关联。

### PD-005 — New Evaluation 每次打开都是新草稿

- Status: Confirmed
- Date: 2026-09-16
- Source question: 未提交创建记录是否跨弹窗保留
- Decision owner: Product owner
- Source thread/message: message `01a0aa6c-5b79-7823-b816-24f2b63f2ddc`
- Confirmation quote: “每次点击 new evaluation 的时候，历史提交记录还保存着，这个不合理。”
- Decision: 每次打开 New Evaluation 都创建干净草稿，不恢复上一次未提交的上传包、校验结果和批次配置。
- Reason: 防止误用上一批数据。
- Consequences: 已正式创建的批次不受影响；草稿关闭即清空。
- Updated artifacts: `tasks.md` 9.9。
- Verification: 关闭并重开弹窗后文件名、校验结果和临时选择恢复默认值。

### PD-006 — Resource Connections 必须安全持久化

- Status: Confirmed
- Date: 2026-09-16
- Source question: 代码更新或重启后是否要求重填连接
- Decision owner: Product owner
- Source thread/message: messages `01a0aa74-e18a-74f3-9afa-fca16a83e37f`、`01a0aa75-e21b-79d0-a972-0af5e78b33ad`
- Confirmation quote: “为什么我这每次保存的 resource connections 在你改了之后都需要重新填啊？上线之后也这样吗？”；“赶紧改啊。”
- Decision: 已保存连接必须跨刷新、重启和代码更新保留；密钥只可加密持久化，不能写入前端或仓库。
- Reason: 连接是长期配置，不是页面临时状态。
- Consequences: 缺少主密钥时必须显式失败，不能悄悄丢配置。
- Updated artifacts: `tasks.md` 1.3、2.4、9.10。
- Verification: 重启服务后连接仍可使用，API和日志不返回明文 Key。

### PD-007 — 确认创建后自动启动评测

- Status: Confirmed
- Date: 2026-09-16
- Source question: 创建批次后是否还需二次启动
- Decision owner: Product owner
- Source thread/message: messages `01a0aa87-4898-7153-903e-a6d8b4de5f24`、`01a0aa88-ed29-7481-af15-bae891e16ed9`
- Confirmation quote: “我都导入任务了，但是看起来没有开始，不是自动开始的吗？”；“那你改啊。”
- Decision: 用户在创建流程确认后自动进入真实执行，不再要求额外点击或在对话中授权启动。
- Reason: “确认并开始评测”本身就是启动动作。
- Consequences: 创建前必须完成预算、资源与数据确认；真实外部测试仍受逐次授权规则约束。
- Updated artifacts: `tasks.md` 4.2、9.1。
- Verification: 确认创建后服务端状态从 validating 进入 running，并显示真实阶段进度。

### PD-008 — 进度与状态必须来自真实后端

- Status: Confirmed
- Date: 2026-09-16
- Source question: 进度条和状态是否允许前端模拟
- Decision owner: Product owner
- Source thread/message: messages `01a0ace8-f318-71b1-a64b-f8e41cfc3fde`、`01a0acdc-6624-7a61-ac2c-4718ee6e5ba5`
- Confirmation quote: “这个进度条是真的假的？怎么不动。状态也不可见。”；“我要你做的程序能按按钮。”
- Decision: 页面展示真实阶段、完成数/总数、失败数和可操作状态，不得以定时器伪造进度。
- Reason: 评测工具必须能用于运行判断和故障恢复。
- Consequences: `items` 的含义和外部调用数不能混用。
- Updated artifacts: `tasks.md` 4.1–4.5、8.3、9.1、10.4。
- Verification: 页面数据能与持久化检查点逐项对账，暂停后数值不再增长。

### PD-009 — 实测通过的 Custom Model ID 进入模型目录

- Status: Confirmed
- Date: 2026-09-16
- Source question: 自定义模型如何供后续批次选择
- Decision owner: Product owner
- Source thread/message: 同一任务 Browser Comment 1，`evaluation.html` Cost settings 的 model cascade，用户消息以“cost setting里面的这个custom model ID”开头
- Confirmation quote: “custom model ID 填了之后，应该放在数据字典里面啊，否则后面 Evaluation batch 的时候都选不了这个自定义模型啊。”
- Decision: Custom Model ID 使用已保存连接完成最小真实诊断后，持久化到模型目录并可供后续批次两轮模型选择。
- Reason: 自定义 ID 不能只存在于单次表单。
- Consequences: 诊断成功不自动同步价格，也不保存重复凭证。
- Updated artifacts: `tasks.md` 8.8、8.9、9.8。
- Verification: 重启后该 ID 仍在 New Evaluation 两轮模型选择器中。

### PD-010 — 当前真实批次整批隔离

- Status: Superseded by PD-026
- Date: 2026-09-16
- Source question: Q-002（旧）当前真实批次结果处置
- Decision owner: Product owner
- Source thread/message: message `01a0ad33-5226-7903-b524-7ef3530724b2`
- Confirmation quote: “隔离批次我懂了，可以这样隔离。”
- Decision: `EV-20260916-1400` 只保留为审计证据，不进入正式报告、指标、Benchmark 或 Gate 3。
- Reason: 该批次在未确认粒度和不完整成本台账下执行过真实调用。
- Consequences: 不删除源数据、供应商结果与检查点；后续是否复用 ASR 证据另行验证。
- Updated artifacts: `tasks.md` 9.7、11.8；批次处置待业务开发恢复后实现。
- Verification: 所有正式结果查询默认排除该批次，审计入口仍可追溯。

### PD-011 — 评测数据固定留存10年且不提供设置入口

- Status: Confirmed
- Date: 2026-09-16
- Source question: Q-003（旧）正式留存策略
- Decision owner: Product owner
- Source thread/message: message `01a0ad33-5226-7903-b524-7ef3530724b2`
- Confirmation quote: “留存策略就固定10年就行。不用设置别的。”
- Decision: 原始录音、历史对话、评测结果和 Benchmark 固定留存10年，不新增全局、项目或批次配置入口。
- Reason: 产品选择统一固定策略。
- Consequences: 服务端必须记录留存类别和到期日；UI只可展示，不可修改。
- Updated artifacts: `tasks.md` 1.5、10.5；相关 Delta Specs/design 待恢复开发前同步。
- Verification: 新批次快照包含固定策略与到期日，普通清理任务不会提前删除。

### PD-012 — 先验证整批一次，再决定第二轮粒度

- Status: Confirmed
- Date: 2026-09-16
- Source question: Q-001 第二轮请求粒度
- Decision owner: Product owner
- Source thread/message: message `01a0ad33-5226-7903-b524-7ef3530724b2`
- Confirmation quote: “你先测试‘整批一次’，如果效果不好再说改的事情，别乱改我的需求。”
- Decision: 在改变第二轮粒度前先用真实批次验证整批一次；失败必须先判定是产品限制还是测试参数/程序缺陷。
- Reason: 不以未经验证的成本假设改写需求。
- Consequences: 第一次探针因参数和范围问题结论无效，Q-001仍为 Open。
- Updated artifacts: `verification/whole-batch-pass2-probe-2026-09-16.md`、`decisions/open-questions.md`。
- Verification: 只有按明确授权和完整参数执行的有效测试才能支持粒度决定。

### PD-013 — ASR 与 LLM 成本分账

- Status: Confirmed
- Date: 2026-09-16
- Source question: 成本台账口径
- Decision owner: Product owner
- Source thread/message: message `01a0ad4d-5dbf-7721-8053-2d70cbd1fdba`，Response Annotation 1
- Confirmation quote: “成本核帐看起来问题不大，那可以这样，但是要拆分ASR和LLM的账单。”
- Decision: ASR 按厂商记录音频量与费用；LLM 按轮次/模型记录输入、缓存输入、推理/输出、重试与费用；预算预留和实际账单分开展示。
- Reason: 两类服务计费单位不同，合并数字无法审计。
- Consequences: 批次可展示总计，但底层必须保留两本账和供应商明细。
- Updated artifacts: `tasks.md` 4.4、10.4。
- Verification: 任一批次均可独立汇总 ASR 与 LLM 估算/实际费用并解释差额。

### PD-014 — 第一次 DeepSeek 整批探针的一次性授权

- Status: Confirmed
- Date: 2026-09-16
- Source question: Q-001 第一次整批测试
- Decision owner: Product owner
- Source thread/message: message `01a0ad3c-860a-7c51-971e-797f9c116628`
- Confirmation quote: “将这56通对话、三家ASR证据和120个候选一次性发送给已保存连接的 DeepSeek。”
- Decision: 仅授权一次向已保存 DeepSeek 连接发送指定真实批次的整批探针。
- Reason: 用真实证据判断整批请求是否可行。
- Consequences: 实际调用只发送53通候选对话且未设置输出预算，偏离授权范围；结果不得作为粒度依据，完整审计见证据文档。
- Updated artifacts: `verification/delivery-status.json`、`verification/whole-batch-pass2-probe-2026-09-16.md`。
- Verification: 调用次数、实际数据范围、模型、费用、参数和停止原因全部留证。

### PD-015 — 第二轮质量判断必须启用 Thinking

- Status: Confirmed
- Date: 2026-09-16
- Source question: Q-001 第二轮推理模式
- Decision owner: Product owner
- Source thread/message: 当前任务 active turn `01a0ad81-ebb4-7a40-8787-4ea2819d33ab`
- Confirmation quote: “如果不用thinking，输出的质量不好，要跑多次，反而会增加调用次数，重新测试，导致成本反而更高。因此还是需要thinking。”
- Decision: 第二轮正式方案与后续有效测试必须启用 Thinking；成本评估必须包含 reasoning tokens，不能仅比较单次非思考价格。
- Reason: 产品优先控制判定质量和返工次数，而非只压低单次调用费用。
- Consequences: Q-001 的所有候选粒度均以 Thinking 为前提；仍需真实质量/成本证据验证。
- Updated artifacts: `decisions/open-questions.md`；Spec/design/Prompt fixture 待问题关闭后同步。
- Verification: 请求与供应商 usage 均能证明 Thinking 已启用并记录 reasoning tokens。

### PD-016 — 暂停开发、部署和新的真实外部调用

- Status: Confirmed
- Date: 2026-09-16
- Source question: 开发清账边界
- Decision owner: Product owner
- Source thread/message: 当前任务 active turn `01a0ad81-ebb4-7a40-8787-4ea2819d33ab`
- Confirmation quote: “先暂停业务开发、部署和所有真实外部调用。不要执行第二次整批测试。”
- Decision: 清账期间只允许文档、证据和任务状态整理；禁止业务代码、部署、真实数据外发和付费测试。
- Reason: 先恢复需求、证据与完成状态的一致性。
- Consequences: 新探针必须重新取得逐次明确授权，旧授权不可复用。
- Updated artifacts: `verification/delivery-status.json`、`decisions/open-questions.md`。
- Verification: 本轮无业务代码/部署变更，外部调用列表只包含第一次历史探针。

### PD-017 — 第二轮采用动态 Token 装箱

- Status: Confirmed
- Date: 2026-09-16
- Source question: Q-001 第二轮 Thinking 请求如何聚合
- Decision owner: Product owner
- Source thread/message: 当前任务 user message，紧接开发清账结果后的三项答复
- Confirmation quote: “第二轮选择动态 Token 装箱。”
- Decision: 第二轮启用 Thinking，并以每通完整对话及其三家 ASR 证据和候选为不可拆分单元，按模型上下文、输出预留和 Case 数动态装箱；全部能安全容纳时只发一组，不能容纳时自动增加组数，不设置固定每组对话数。
- Reason: 在保证完整证据和质量的前提下减少重复上下文及调用次数，并可随批次规模扩展。
- Consequences: 进度必须分别展示唯一 Case 数和外部请求组数；重试只重试失败组，幂等键覆盖组内 Case 集合和输入快照。
- Updated artifacts: `design.md`、`specs/asr-automated-evaluation/spec.md`、`tasks.md` 6.9。
- Verification: 覆盖整批单组、超限多组、超大单通、输出预留不足、失败组重试和 Case 不漏不重。

### PD-018 — 不执行 Agent 重测，由用户在平台完成测试

- Status: Confirmed
- Date: 2026-09-16
- Source question: Q-004 修正后的真实测试授权
- Decision owner: Product owner
- Source thread/message: 当前任务 user message，紧接开发清账结果后的三项答复
- Confirmation quote: “你不用重测，做好了工具之后我自己用平台测试。”
- Decision: 不授权 Agent 执行第二次整批探针；工具完成后由用户通过平台主动发起测试。
- Reason: 真实数据外发和费用由产品用户在可见平台流程中控制。
- Consequences: 第一次探针继续仅作无效审计证据；开发恢复前仍受 PD-016 暂停约束，平台测试入口必须展示模型、范围、预算和停止条件。
- Updated artifacts: `decisions/open-questions.md`、`verification/delivery-status.json`。
- Verification: Agent 无新增真实调用；平台测试需要用户显式操作并生成完整成本/状态记录。

### PD-019 — V1.14 冻结原型基线（已被 PD-024 授权更新）

- Status: Superseded by PD-024
- Date: 2026-09-16
- Source question: Q-005 原型基线冲突
- Decision owner: Product owner
- Source thread/message: 当前任务 user message，查看当前 `prototypes/index.html` 后的确认
- Confirmation quote: “可以确认当前为唯一基线。”
- Decision: 当时的 `prototypes/index.html` V1.14（历史 SHA-256 前缀 `1c61fb…`）是该次冻结基线；旧 `1c5313…` 只保留为无法恢复的失效历史记录。V1.14 已被 PD-024 授权更新，不再是当前冻结基线。
- Reason: 当前文件是唯一仍可执行、校验且经产品重新确认的版本。
- Consequences: 该 SHA 仅作历史审计记录；当前唯一基线由 PD-024 和 `prototypes/README.md` 声明。
- Updated artifacts: `prototypes/README.md`、`verification/gate-1-review.md`、`verification/baseline-provenance-audit-2026-09-16.md`、`decisions/open-questions.md`。
- Verification: 校验当前文件 SHA，并确保 Change 内只声明一个完整冻结校验值。

### PD-020 — 恢复本地修复并保持 Tags 版本化维护能力

- Status: Invalidated — mixed statement was misread as confirmation
- Date: 2026-09-16
- Source question: 清账完成后是否恢复开发，以及 Tags 应按哪一侧行为对齐
- Decision owner: Product owner
- Source thread/message: 当前任务 user message，紧接唯一原型基线确认之后
- Confirmation quote: “如果没有，着手开始修复，过程中有问题记得随时问我。我现在看基线里面tags不能编辑/删除，这个跟现在修改的不一样”
- Invalidity reason: 原话前半句授权在无问题时恢复修复，后半句明确指出冻结基线与当前 Tags 行为不一致；它没有确认采用编辑/删除能力。此前把冲突当作确认，违反了“产品决定必须可追溯”的证据要求。
- Consequences: 恢复本地修复的授权由后续 PD-021 单独承接；Tags 的创建/编辑/删除边界重新登记为 Q-006，确认前暂停该部分业务修改和验收声明。
- Updated artifacts: `decisions/open-questions.md`、`tasks.md`。
- Verification: 不再使用 PD-020 作为 Tags CRUD 的确认依据。

### PD-021 — 继续开发至本地可验收部署

- Status: Confirmed
- Date: 2026-09-16
- Source question: 清账后是否继续完成本地交付
- Decision owner: Product owner
- Source thread/message: 当前任务 user message，询问剩余待办是否继续后给出的明确执行要求
- Confirmation quote: “那你现在需要我确认什么吗？没有的话，请继续开发，直至本地部署，可以让我验收。除非你遇到了不确定的问题，需要我确认，才暂停下来向我询问”
- Decision: 在不存在开放产品问题时持续完成本地业务开发、验证和本地部署，直到用户可以验收；只有遇到无法由现有 PRD、Delta Spec、冻结原型和已确认决定唯一确定的产品问题时才暂停询问。
- Reason: 当前剩余项属于已确认范围内的工程实现和验证，不应逐项要求产品重新确认。
- Consequences: PD-020 中“部署未获授权”的限制对本地验收部署解除；生产部署仍未授权。PD-018 继续有效，Agent 不得替用户发起真实厂商调用或第二次整批测试。
- Updated artifacts: `decisions/open-questions.md`、`verification/delivery-status.json`、`tasks.md`。
- Verification: 本地服务可启动、核心验收路径可操作、自动化门禁通过；真实厂商结果仍由用户在平台显式触发。

### PD-022 — Tags 支持完整维护能力

- Status: Confirmed
- Date: 2026-09-17
- Source question: Q-006 场景标签在当前版本允许哪些维护操作
- Decision owner: Product owner
- Source thread/message: 当前任务 user message，回答 Tags 权限边界
- Confirmation quote: “Tags应该可以新增、编辑、查看、删除啊。”
- Decision: 当前版本的场景标签支持新增、查看、编辑和删除；编辑生成不可变新版本，删除从当前可选标签库移除，但已冻结批次、报告和 Benchmark 的历史引用继续可读。
- Reason: 产品负责人明确选择完整维护能力。
- Consequences: 关闭 Q-006；保留当前版本化编辑和删除墓碑实现，并以自动化测试验证历史快照不被破坏。
- Updated artifacts: `decisions/open-questions.md`、`tasks.md`、场景标签接口和页面验证证据。
- Verification: API 与页面覆盖新增、查看、版本化编辑、删除及历史版本保留。

### PD-023 — 混合币种保留原币账单并冻结汇率

- Status: Confirmed
- Date: 2026-09-17
- Source question: Q-007 混合币种预算核算
- Decision owner: Product owner
- Source thread/message: 当前任务 Response Annotation 1，选项 A/B/C 的明确答复
- Confirmation quote: “选A”
- Decision: ASR 与 LLM 费用保留供应商原币账单；每个价格版本冻结人民币兑美元汇率，批次快照使用该汇率折算到统一美元预算，但仍展示原币、折算值和汇率版本。
- Reason: 同时满足供应商账单可追溯和统一预算停止条件。
- Consequences: Qwen 等人民币报价不得被静默当作美元；汇率变更只影响新价格版本和新批次。
- Updated artifacts: `design.md`、`tasks.md`、成本配置与账单实现、`verification/delivery-status.json`。
- Verification: 混合币种批次能分别对账原币费用，并以冻结汇率复算同一美元预算总额。

### PD-024 — Benchmark 增加类型筛选、可审计编辑和分页

- Status: Confirmed
- Date: 2026-09-17
- Source question: Q-008 冻结原型缺少 Benchmark 控件
- Decision owner: Product owner
- Source thread/message: 当前任务 Response Annotation 2，选项 A/B 的明确答复
- Confirmation quote: “选A，更新原型，并增加筛选和样本编辑入口，同时支持分页展示”
- Decision: 更新唯一冻结原型和运行时 Benchmark Library，增加 All/Good/Bad 类型筛选、样本编辑入口与每页20条分页；编辑必须追加不可变修订记录。
- Reason: 正式样本库需要在正常用户流程中完成查找、校正和追溯，不能只保留后台接口。
- Consequences: 本次经产品明确授权更新 UI baseline；旧 V1.14 校验值作为历史记录。V1.15（历史 SHA-256 前缀 `b3c5aea…`）随后由 PD-025 授权更新。
- Updated artifacts: `prototypes/index.html`、`prototypes/README.md`、`tasks.md` 8.6、运行时页面与浏览器证据。
- Verification: 类型筛选、跨分页、查看、编辑、保存冲突和修订历史均通过 API 与双视口浏览器验证。

### PD-025 — 第二轮 Prompt 公开使用分组输出契约

- Status: Confirmed
- Date: 2026-09-17
- Source question: Q-009 第二轮冻结 Prompt 如何承载动态 Token 装箱
- Decision owner: Product owner
- Source thread/message: 当前任务 user message，明确回复 Q-009 并授权本地容器操作
- Confirmation quote: “Q009 选 A，并允许重建和重启本地 Docker 服务”
- Decision: 更新冻结第二轮 Prompt 和原型为动态分组输出；输入显式包含 `request_group_id`，输出以同一 ID 和 `results[]` 返回组内每个 Case，且每个结果包含 `positioning_quality`。完整契约继续对管理员可见，不在代码中隐藏追加规则。
- Reason: 与已确认的动态 Token 装箱保持一致，同时保证页面预览、批次快照、模型输出和解析器使用同一公开契约。
- Consequences: 第二轮旧 V1 单 Case Prompt 仅保留为历史审计；默认 Prompt 升级为 V2，缺少分组字段的活动 seed 模板通过不可变新版本迁移。错误组 ID、遗漏、重复或越界 Case 会拒绝整组结果。该决定当时形成的 V1.16（历史 SHA-256 前缀 `1357e3dd…`）已被 PD-026 的 V1.17 基线取代。
- Updated artifacts: `fixtures/riyadbank-pass-2-system-prompt-v2.md`、`specs/`、`design.md`、`prototypes/`、`tasks.md` 12.11、执行器与测试。
- Verification: Prompt/预览包含全部分组变量和结构；后端验证组 ID 与 Case 完整性；本地构建、回归、门禁和 Docker 验收服务验证。

### PD-026 — 删除旧无效批次并提供误建批次删除能力

- Status: Confirmed
- Date: 2026-09-17
- Source question: 旧 audit-only 批次和误传/误建内容如何处置
- Decision owner: Product owner
- Source thread/message: 当前任务 user message，紧接 `EV-20260916-1400` 的 33 条历史待复核数据说明之后
- Confirmation quote: “不对啊，那你应该把这个删了。而且现在传错的内容也没法删除。你先继续吧，我已经发起真实评测了”
- Decision: 删除旧无效批次 `EV-20260916-1400`；页面为 audit-only、失败或已停止的批次提供显式删除入口，并允许删除未启动的暂存上传。运行中的真实评测不得直接删除，必须先停止，避免留下仍计费的外部任务。正式完成且有效的评测仍执行 PD-011 的 10 年留存。
- Reason: 仅隐藏无效批次不能解决脏记录和误建内容不可撤销的问题，同时直接删除运行中任务会造成状态、费用和供应商作业失联。
- Consequences: PD-010 的“永久保留旧批次审计证据”被本决定取代；删除只清理该批次拥有的结果、复核、Benchmark、报告、执行检查点和成本记录，不删除共享源数据、连接、上下文、词典、标签或价格版本；保留不含客户内容的删除审计墓碑。当前唯一 UI baseline 更新为 V1.17（SHA-256 `fd400adde2eb769570d3766dcbe5fea4d5f6ab6976565dcdfb84be2c1fec7d5e`）。
- Updated artifacts: `specs/asr-automated-evaluation/spec.md`、`design.md`、`tasks.md`、批次 API/页面和回归测试。
- Verification: 旧批次从列表和正式统计消失；失败/停止批次可二次确认后删除；运行中批次删除返回冲突；暂存上传可主动丢弃且不影响当前正式数据。

### PD-027 — UI 交付改为两个用户 Gate 与三个研发检查点

- Status: Confirmed
- Date: 2026-09-19
- Source question: 是否将原三 Gate 流程改为两个用户 Gate 与三个研发检查点
- Decision owner: Product owner
- Source thread/message: 当前任务 user message，确认流程调整
- Confirmation quote: “行，那你改一改吧，改成你说的这种，2个用户Gate+3个研发检查点。”
- Decision: User Gate 1 冻结规格与原型；研发依次完成 Checkpoint A（同一正式 UI 加载 fixture）、Checkpoint B（真实 API、持久化和失败恢复）、Checkpoint C（独立验收）；全部通过后进入 User Gate 2 最终产品验收。
- Reason: 原 Gate 2 容易被误解为需要用户验收的独立静态页面，造成静态壳与真实接线页面分叉及重复确认。
- Consequences: 历史 Gate 2/Gate 3 文件名和证据名称保留用于追溯，但不再代表当前流程中的用户 Gate；fixture 只能切换数据源，不能另建页面或组件树。
- Updated artifacts: `AGENTS.md`、`docs/engineering/ui-prototype-delivery.md`、交付与验收 Skills、`design.md`、`tasks.md`、`verification/ui-checklist.md`、`verification/delivery-status.json`。
- Verification: 自动门禁检查 UI Change 声明统一交付模型、正式 UI 路径、fixture 复用和 A/B/C 三个检查点。

### PD-028 — 未完成人工复核不阻塞产品验收

- Status: Confirmed
- Date: 2026-09-19
- Source question: 当前真实批次的 24 条待复核是否阻塞产品验收
- Decision owner: Product owner
- Source thread/message: 当前任务 user message，紧接 `EV-20260918-4966` 失败批次说明之后
- Confirmation quote: “24条复核不完成后有什么结果呢？我认为不影响产品验收”
- Decision: 人工复核队列是否完成只决定该批次是否生成完整或部分覆盖的最终报告，不作为当前 Change 的 Engineering Checkpoint C 或 User Gate 2 前置条件；产品验收可以使用真实初步报告、人工复核功能回归和状态/持久化证据完成。
- Reason: 人工复核是持续业务运营工作，不能要求产品验收前人工处理完某个真实批次的全部队列。
- Consequences: `EV-20260918-2655` 可保持初步报告和 24 条待复核状态；完成全部复核会生成完整最终报告，负责人提前结束会生成标记覆盖率的部分最终报告，保持未完成则不会生成最终报告，但不影响产品功能验收。
- Updated artifacts: `design.md`、`tasks.md`、`verification/delivery-status.json`。
- Verification: Checkpoint C 验证初步报告、逐条复核、提前结束、最终报告生成和持久化契约，不以清空当前真实队列作为通过条件。

### PD-029 — 使用现有真实批次作为当前验收证据

- Status: Confirmed
- Date: 2026-09-19
- Source question: 当前真实批次以及新的双 Gate 规范如何用于验收
- Decision owner: Product owner
- Source thread/message: 当前任务 user message，回复历史 30-event 与 Gate 证据核对
- Confirmation quote: “使用现有`EV-20260918-2655` 作为 Gate 3 真实证据。但是现在规范改了，Gate2和Gate3合并了，现在只有Gate1和Gate2，请遵守新规范”
- Decision: `EV-20260918-2655` 作为当前 Engineering Checkpoint B/C 的 external-real 证据，不再使用旧 Gate 3 作为当前验收阶段名称；UI 交付继续遵循 User Gate 1、Engineering Checkpoint A/B/C、User Gate 2。
- Reason: 现有用户主动发起的真实批次已包含三家 ASR、两轮 LLM、不可变初步报告、Benchmark 和人工复核队列，可避免为了验收重复发送真实数据或产生额外费用。
- Consequences: 历史文件名和历史文字中的 Gate 2/Gate 3 仅作追溯；`EV-20260918-2655` 本身不自动证明 Checkpoint C PASS，仍需独立核对功能、可访问性、视觉差异、失败/恢复状态和证据完整性，之后才能请求 User Gate 2 最终验收。
- Updated artifacts: `decisions/decision-log.md`；后续 Checkpoint C 独立验收与交付状态必须引用该批次。
- Verification: 批次当前为 `awaiting_review`，初步报告入口可用，24 条待复核不阻塞验收（PD-028）；不得发起新的付费重测来替代已有证据。

### PD-030 — 中文对照按需复用第一轮 LLM，系统文案仅本地翻译

- Status: Confirmed
- Date: 2026-09-19
- Source question: Q-010 中文模式如何生成真实英文/阿文的中文对照
- Decision owner: Product owner
- Source thread/message: 当前任务 user message，回复按需翻译方案并追问系统文案是否进入 LLM
- Confirmation quote: “可以选A，并复用第一轮LLM，但是有一些系统文案，这些没有给LLM作为入参吧？”
- Decision: 固定系统文案、按钮、字段名、状态和提示只使用前端本地词典，绝不作为翻译入参。用户在中文模式打开含真实英文/阿文的相关内容时，服务端按需复用该批次冻结的第一轮 LLM，只发送当前可见原始对话文本并返回“原文 + 中文对照”；译文仅在当前浏览器会话缓存，不写入原始对话、报告或 Benchmark，也不得作为评测证据。翻译失败时保留原文并显示译文暂不可用。调用只记录不含对话内容的 Token、费用和安全审计元数据。
- Reason: 满足中文阅读需求，同时保持源数据和评测证据不可变，并避免将可由本地词典解决的界面文案发送给外部模型。
- Consequences: 关闭 Q-010；中文对照首次打开会有延迟并产生少量第一轮 LLM 费用，仍受批次冻结价格和预算上限约束；用户在中文模式主动打开相关内容是本次按需发送的触发动作。本决定不授权 Agent 为验证主动发送真实客户数据，自动化验证必须使用 mock。
- Updated artifacts: `decisions/open-questions.md`、Delta Spec、`design.md`、`tasks.md`、`prototypes/README.md`、页面/API 与回归测试。
- Verification: 自动化测试断言系统文案不进入请求、响应不持久化且不改变报告/Benchmark；真实翻译由用户在页面主动触发，不作为 Checkpoint C 的准确性证据。

### PD-031 — 质检结论和新增标签只描述 ASR 质量维度

- Status: Confirmed
- Date: 2026-09-19
- Source question: KI-077 中“语言选择”建议标签把用户未回答语种选择描述成问题
- Decision owner: Product owner
- Source thread/message: 当前任务 user message，紧接 KI-077 根因说明后的确认
- Confirmation quote: “对，要按照中性质检维度，但是不是只有‘用户本身为选择语言不算错误’，只是要强调质检和新增标签的目的是‘检测ASR有没有错误’”
- Decision: 第一轮候选、第二轮结论和建议新增标签都必须以“检测线上 ASR 是否准确保留用户实际语音及必要业务含义”为唯一质量目标。不得把用户是否回答机器人、回答是否符合流程、用户意图是否合理、业务是否成功或机器人表现本身当作 ASR 错误。标签名称和描述必须是可复用的中性 ASR 质检维度；Good Case 允许归入该维度，但不得被描述为用户行为问题。
- Reason: 场景标签用于组织 ASR 质量证据，不是用户行为、业务流程或机器人体验的问题分类器。
- Consequences: “语言选择”可作为中性质检维度，但应描述语种相关发言是否被准确识别；“用户未明确选择语言”本身不是错误。无真实转写差异证据时不得因流程未推进而判 Bad，也不得建议以正常用户行为命名的全局标签。
- Updated artifacts: Delta Spec、`design.md`、两轮 Prompt fixture、Prompt 迁移与回归测试、`tasks.md`、`verification/delivery-status.json`。
- Verification: Prompt 回归必须覆盖 ASR-only scope、中性标签规则和正常非回答不构成错误；历史 `EV-20260918-2655` 报告保持不可变，新规则只作用于后续批次。

### PD-032 — 人工复核与 Benchmark 当前可见阿语自动显示中文对照

- Status: Confirmed
- Date: 2026-09-20
- Source question: Q-011 人工复核与 Benchmark 阿语中文对照的触发范围
- Decision owner: Product owner
- Source thread/message: 当前任务 user message，在确认自动翻译会额外调用第一轮 LLM 后授权实施
- Confirmation quote: “可以，那就做吧。”
- Decision: 采用 Q-011 Option A。中文模式进入人工复核时，自动翻译当前任务内可见的阿语历史转写、阿语上下文和阿语 ASR 候选；进入 Benchmark Library 时，将当前页最多 20 条可见阿语按所属批次合并请求翻译，样本详情中的阿语历史转写和标注文本也显示中文对照。仅发送确实含阿语的原始业务文本，系统文案不得进入请求；阿语原文始终保留，译文只在当前浏览器会话缓存，不写入评测、复核、报告或 Benchmark 数据。
- Reason: 中文使用者需要在人工复核和历史 Benchmark 全链路直接阅读阿语证据，同时保持后端源数据和正式评测证据不可变。
- Consequences: 首次打开当前任务、列表页或详情会产生额外第一轮 LLM 调用、少量等待与费用；同一浏览器会话中相同批次和文本复用缓存。失败时保留原文并显示中文对照暂不可用，不阻塞复核或 Benchmark 操作。
- Updated artifacts: Q-011、Delta Specs、`design.md`、`tasks.md`、生产页面与回归测试。
- Verification: Mock 测试必须证明只发送可见阿语、按批次合并、系统文案不入参、原文不被覆盖、缓存避免重复请求；真实翻译质量仍由用户主动页面操作验证。

### PD-033 — 中文对照格式异常自动重试并拆小批次

- Status: Confirmed
- Date: 2026-09-20
- Source question: KI-090 中真实 DeepSeek 翻译返回 HTTP 200 但 JSON 解析失败
- Decision owner: Product owner
- Source thread/message: 当前任务 user message，确认增加推荐的翻译容错
- Confirmation quote: “增加”
- Decision: 中文对照请求遇到网络、解析或结构校验异常时，先以相同文本自动重试一次；整组仍失败且超过安全小组大小时，将可见文本按稳定顺序拆成不超过 4 条的小组，每组最多再尝试两次并按原顺序合并。预算拒绝不得重试或拆分；最终仍失败时继续保留原文并显示中文对照暂不可用。
- Reason: 真实第一轮模型可能偶发返回非 JSON 内容，小批次能降低结构化输出遗漏和截断概率，同时限制最坏调用次数。
- Consequences: 异常场景可能产生额外 LLM 调用和费用，但每次调用都经过冻结价格预算预留；正常成功路径仍只调用一次，不持久化译文。
- Updated artifacts: Delta Spec、`design.md`、`tasks.md`、翻译执行器、回归测试与交付记录。
- Verification: 单元测试覆盖首次成功、整组重试后拆分成功、稳定顺序、预算拒绝不重试及最终失败；真实页面由用户再次触发验证。

### PD-034 — 显示翻译显式关闭推理并保留分组成功结果

- Status: Confirmed
- Date: 2026-09-20
- Source question: KI-093 中 deepseek-flash 默认推理耗尽显示翻译输出预算，且后续分组失败会丢弃此前成功译文
- Decision owner: Product owner
- Source thread/message: 当前任务 user message，要求保证不影响其他现有流程后确认实施
- Confirmation quote: “行啊，只要保证不影响其他现有的就行。”
- Decision: 仅 `display_translation` 调用依据 DeepSeek 官方 OpenAI 兼容参数传入 `extra_body.thinking.type=disabled`；第一轮、第二轮及其他 LLM 调用保持原行为。拆分回退中每个小组独立产生成功或失败结果，成功译文按原索引立即返回，失败位置返回空值并在页面单独显示“中文对照暂不可用”，不得因后续小组失败丢弃此前成功译文。
- Reason: 显示翻译不需要推理链；真实费用台账证明默认推理消耗了 3,152/1,080 Token 且可见输出为 0。局部返回能降低单个异常对整页可读性的影响。
- Consequences: 翻译 API 响应允许 `translations[]` 中个别位置为空，并返回 partial/failed_count 元数据；预算拒绝仍整体短路。改动不触碰评测 Prompt、Pass 1/Pass 2 Thinking、冻结模型或正式证据。
- Updated artifacts: Delta Spec、`design.md`、`tasks.md`、翻译执行器/API 消费端、回归测试和交付记录。
- Verification: 测试必须断言仅显示翻译传入 DeepSeek disabled 参数，其他 `_llm_json` 调用默认不变；分组部分成功保留、失败索引为空且前端逐条降级。

### PD-035 — 三家评测 ASR 只转录纯用户事件切片

- Status: Confirmed
- Date: 2026-09-20
- Source question: KI-098 中人工复核候选混入相邻机器人话术
- Decision owner: Product owner
- Source thread/message: 当前任务 user message，在确认现有完整通话片段拼接问题后授权实施
- Confirmation quote: “不需要降级人工复核吧。用三家ASR找到纯用户录音那部分，重新转录一下就好了啊。只转录纯用户录音”；“对的，就是这样。你来改吧。我允许你在验证的时候自己先调接口验证做一遍，涉及费用”
- Decision: 第一轮确定目标用户事件后，系统按该事件时间边界从纯用户 WAV 裁出单句音频，并分别交给 Soniox、Speechmatics、ElevenLabs 重新转录。第二轮与人工复核只消费这些事件级转录结果，不再从完整通话 ASR 结果或带上下文的播放窗口拼接候选文本。完整对话仍用于第一轮上下文和历史明细。
- Reason: 从 ASR 输入源头排除机器人声音，比依赖 LLM 引用、speaker 标签或事后文本过滤更可靠。
- Consequences: ASR 计费单位从命中 conversation/provider 改为目标 event/provider；同一目标事件的切片跨三家复用并保持幂等。时间轴或边界无效时对应事件级资源明确失败，禁止回退到混合通话文本。一次性真实验证限定为 `1030000000082501 · R15` 的纯用户 WAV（51.222–53.255 秒），分别发送 Soniox、Speechmatics、ElevenLabs 各一次，总费用上限 USD 0.05，任一失败不重试且三次尝试后停止。
- Updated artifacts: Delta Spec、`design.md`、`tasks.md`、执行器、存储、成本台账、人工复核与测试。
- Verification: 固定 fixture 必须证明目标切片不跨相邻机器人事件、三家收到同一纯用户 WAV、Pass 2/复核仅使用事件级结果、失败不回退；另以 1 条用户事件对三家各调用 1 次完成 external-real 验证。

### PD-036 — 保留本地旧批次且生产环境不迁移测试历史

- Status: Superseded by PD-037
- Date: 2026-09-20
- Source question: Q-012 现有冻结批次的 24 条复核记录是否补充事件级重转录
- Decision owner: Product owner
- Source thread/message: 当前任务 user message，在 Option A/B 说明后明确选择
- Confirmation quote: “选择A，但是后面推上线之后，这些本地的测试历史记录，不应该展示到线上，对吧。”
- Decision: 选择 Option A。`EV-20260918-2655` 及其他本地测试批次保留在本地环境作为历史审计，不补充或改写事件级证据。生产部署必须使用独立的数据卷或空数据库，只初始化数据库结构和正式配置，不复制本地批次、报告、人工复核、Benchmark、成本台账、上传包、录音或测试生成物。
- Reason: 保持历史证据不可变，同时确保生产用户不会看到本地测试数据或客户测试录音。
- Consequences: 新流程只由新建批次验证；部署脚本和上线检查必须证明生产数据目录与本地验收数据隔离。任何生产数据迁移均需独立、明确授权。
- Updated artifacts: `decisions/open-questions.md`、`verification/delivery-status.json`。
- Verification: 生产部署前检查目标数据卷为空或为明确的生产卷，启动后批次、报告、复核和 Benchmark 列表均不包含本地测试 ID。

### PD-037 — 删除本地全部 Evaluation 测试历史

- Status: Confirmed
- Date: 2026-09-20
- Source question: 本地批次列表仍展示历史测试数据后的处置
- Decision owner: Product owner
- Source thread/message: 当前任务，用户在看到本地 `Evaluation batches` 仍有 `EV-20260918-2655` 后的明确指令
- Confirmation quote: “全部删除”
- Decision: 删除当前本地验收环境中的全部 Evaluation 测试历史，包括批次自有的报告、人工复核、Benchmark、成本台账、检查点、临时上传和派生音频；保留共享源通话数据、Resource Connections、Cost Settings、场景标签与其他系统配置。生产环境仍必须使用独立空数据卷。
- Reason: 用户不再需要本地历史测试记录，且要求当前页面清空。
- Consequences: PD-036 关于“保留本地旧批次”的部分被取代；历史测试结果不可恢复，不能再作为本地页面验收样本。生产隔离要求继续有效。
- Updated artifacts: `verification/delivery-status.json`；本地 Evaluation 数据存储。
- Verification: 清理后批次、人工复核、Benchmark、报告和批次成本列表均为 0；共享配置和源通话索引仍存在；`http://localhost:8000/evaluation.html` 返回正常。

### PD-038 — 缺少冻结价格时阻止创建且空工作集必须终止

- Status: Confirmed
- Date: 2026-09-20
- Source question: `EV-20260920-7878` 长期停留在 ASR 75% 且显示 0/0 jobs
- Decision owner: Product owner
- Source thread/message: 当前任务，Agent 说明根因和推荐处理后用户确认
- Confirmation quote: “可以的。”
- Decision: 新建批次必须在创建前验证两轮所选 LLM 均存在于当前价格版本；缺少价格时不创建批次并明确提示先配置价格。第一轮全部失败时批次直接进入可重试失败状态；第一轮成功但没有任何候选时生成零候选报告并正常结束，不得进入 0/0 的 ASR 运行状态。删除当前无效批次 `EV-20260920-7878`，不自动重跑。
- Reason: 预算门禁依赖不可变价格快照，且空工作集不能继续伪装为正在执行。
- Consequences: Qwen 等已验证模型只有在当前价格版本包含对应价格时才可创建新批次；现有无效批次删除后不可恢复。
- Updated artifacts: Delta Specs、`design.md`、`tasks.md`、批次创建/执行器、测试与交付记录。
- Verification: 缺价创建返回明确错误且不落批次；全部第一轮失败终止于失败状态；零候选成功批次生成报告并以 100% 结束；当前无效批次通过正式删除接口移除。

## Explicit non-decisions

- 无。Engineering Checkpoint C 已完成独立验收；产品负责人在 PD-042 中确认页面走查无问题，并授权最终复核通过后发布，视为 User Gate 2 接受。

### PD-042 — 授权单次报告翻译验证及通过后生产发布

- Status: Confirmed
- Date: 2026-09-20
- Source question: KI-119 中文报告修复后的真实翻译验证与生产发布范围
- Decision owner: Product owner
- Source thread/message: 当前任务，Agent 明确说明接收方、批次、费用上限和停止条件后的用户回复
- Confirmation quote: “授权。另外，之后我看着是没问题了，最后你再看一遍吧，没有问题的话你就发版到线上，记得要把历史测试数据都清空。”
- Decision: 授权 Agent 对 `EV-20260920-9D33` 的当前报告执行一次中文模式真实验证，将报告内含阿语的历史转写和评测 ASR 文本发送给该批次冻结的 Qwen 第一轮模型，费用上限 USD 0.10，失败即停止。完成最终检查且无阻塞问题后，授权发布当前 Change 到 `platform.voiceagentdemo.org`；生产 Evaluation 必须以空历史上线，清理范围仅限批次、报告、复核、Benchmark、成本台账、检查点、临时上传和派生音频，保留机器人配置、资源连接、成本配置、场景标签和共享源数据。
- Reason: 产品负责人已完成页面走查，希望在最后工程复核后上线，同时确保本地测试历史不进入生产页面。
- Consequences: 真实翻译调用仅限上述一个批次和一次页面触发；生产部署及生产 Evaluation 历史清理已获明确授权，但仍须先确认部署提交边界、生产数据卷和可回滚路径，不能把工作区中其他未确认改动一并发布。
- Updated artifacts: `verification/delivery-status.json`、生产发布检查与部署记录。
- Verification: 单次中文报告验证已于 2026-09-20 完成：Qwen 一次请求翻译 179 条去重后的阿语文本，`attempt_count=1`、`split_used=false`、`failed_count=0`；页面动态系统文案、标签、状态和阿语中文对照均正常显示。发布前自动门禁与独立验收仍须通过；发布后 `/health` 正常，生产批次、报告、复核和 Benchmark 列表为空。

### PD-043 — 确认推送发布并清空生产 Evaluation 历史

- Status: Confirmed
- Date: 2026-09-20
- Source question: Agent 在最终复核通过后请求确认，将已验收的发布提交推送至 `git@github.com:jasonchao75/VoiceAgent.git` 的 `main` 并触发生产部署。
- Decision owner: Product owner
- Source thread/message: 当前任务，用户在收到精确推送范围与生产清理边界后回复。
- Confirmation quote: “确认推送，但是要记得数据清空的事情哈”
- Decision: 授权推送本 Change 的已验收发布提交到上述远端 `main` 并触发生产部署；首次上线必须清空且验证生产 Evaluation 的批次、报告、人工复核和 Benchmark 历史，不清理机器人配置及其他非 Evaluation 数据。
- Reason: 产品负责人确认进入正式发布，并再次强调线上不能出现本地测试历史。
- Consequences: 部署采用独立生产 Evaluation 数据卷；空历史门禁只在首次生产初始化时执行并留标记，后续常规发布必须保留线上产生的真实 Evaluation 数据。
- Updated artifacts: `verification/delivery-status.json`、`tasks.md`、部署验证记录。
- Verification: 以 Git 远端提交、GitHub Actions 部署结果、线上健康检查及首次空历史门禁输出为准。
