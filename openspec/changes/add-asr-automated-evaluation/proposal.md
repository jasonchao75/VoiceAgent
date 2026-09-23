# Change: Add ASR Automated Evaluation

## Why

项目交付目前依赖离线脚本和人工整理，从历史对话中筛选 ASR Bad Case、调用多家 ASR 交叉转写、回听不确定片段并生成 Benchmark。该流程可以验证方法，但缺少统一的数据校验、任务状态、失败恢复、人工复核、追溯、权限和产品化页面，无法稳定地重复执行或交付给非研发人员使用。

本 Change 将已验证的离线流程产品化：AI 负责高召回筛选、证据归纳和明确样本标注，人工只复核无法可靠判断的目标用户句子；最终形成可追溯、可下载的 ASR Benchmark Library 和批次报告。

## What Changes

### 评测批次与数据导入

- 新增独立的 ASR Evaluation 产品区域，提供批次列表、新建评测、任务详情、人工复核、结果报告和 Benchmark Library。
- 每个压缩包包含 `conversation_history/`、`record/`、`user_record/`；每通对话分别提供同名 Excel、完整通话 MP3 和纯用户 WAV，并以完整 conversation ID 文件名关联。
- 导入时读取实际音频属性，验证目录、数量、ID、Excel 工作表/列、解码、时长和两类录音时间轴；问题必须可定位并支持定向修复。
- 创建批次时冻结质检上下文、两轮 Prompt、标签字典、ASR/LLM 资源、模型、价格和预算版本。

### 两阶段自动分析

- 第一轮 LLM 仅从历史对话的用户事件中筛选可能改变业务含义的疑点 Case，同时保留同一疑点对话中的正常用户句子作为额外 Good Case 候选池；完整对话作为不可拆分单元动态装箱，整批安全可容纳时一次请求，超限时才按 Token 拆组。
- Pass 1 与 Pass 2 使用统一的 128K 运行包络（最终输入最多 64K、Thinking 与可见输出合计最多 32K、保留 32K 安全余量），并按最终序列化消息预检；业务证据只在完成变量替换的 System Prompt 中出现一次，不再同时复制到 User JSON。
- 已有初步报告的暂停或部分失败批次可由负责人二次确认“使用现有结果结束”：保留成功结果，排除未完成项，冻结不可变部分覆盖报告，且不恢复执行器或调用外部资源。
- 生成预算先预留按 Case 数量增长的可见 JSON，Thinking 仅使用剩余额度；本地输入/输出规划失败采用专用 preflight 分类并保留既有阶段进度。ASR 失败通过现有部分结果区域展示 provider、任务范围、尝试次数、是否可重试及脱敏原因。
- Qwen Pass 1 保持非 Thinking/180 秒并为最长纠正提示预留装箱空间；Pass 2 固定 medium Thinking/300 秒。两轮 timeout 或结构失败不再原样重放父组：第一轮按完整 conversation、第二轮按完整 Case 稳定拆分，成功检查点继续复用，最小单元只允许一次额外尝试。
- 运行中的进度区域按每个当前外部请求显示真实请求序号、供应商与秒级等待时间；暂停和部分失败只显示当前阶段业务单位的成功/失败数，详细请求组和尝试历史留在任务详情/日志。
- 每家评测 ASR 对每个命中的完整对话只提交一次显式开启说话人分离的异步文件转写；批量动态装箱的 Event Aligner 将目标 R 事件映射到各家既有 turn ID，程序要求至少两家映射同一用户发言并以这些真实 turn 区间的并集定位。Excel `time (s)` 不参与定位，纯用户 WAV 只校验并向外补齐边缘、不得缩短并集；生成的单句切片只用于回听、人工复核和 Benchmark，不再提交评测 ASR。
- 第二轮 LLM 综合线上历史转写、完整对话、质检上下文、标签字典和 Event Aligner 命中的各家完整录音 ASR turn 文本，输出 `Good Case`、`Bad Case` 或 `需人工复核`，不使用置信度阈值控制入库。完整历史文本保留；完整录音 ASR 证据只携带目标 turns 和直接相邻 turns，单通仍超限时在发送前按稳定 Case 子集拆组。
- 第一轮疑点被第二轮判为 Good 是 Good Case 的一个来源；系统再从同一批疑点对话的正常候选池中抽取额外 Good Case，使最终可用 Good:Bad 目标为 1:1。候选不足时允许低于目标并披露差额。
- 首期评测 ASR 为 Soniox `stt-async-v5`、Speechmatics `melia-1` batch/multi 和 ElevenLabs `scribe_v2` webhook。

### 人工复核、报告和指标

- 人工复核以目标用户句子为最小单位，页面就近展示历史转写、当前建议标注、多家候选、统一回听区间和必要上下文。
- 复核人员必须明确选择 `Good` 或 `Bad`；Good 使用历史转写作为人工标注，Bad 必须选择或填写正确标注文本。`听不清`视为已复核，但不进入正式 Benchmark，也不计入人工 Good/Bad。
- 疑似错误用户句子占比的分子为第二轮 `Bad Case + 需人工复核`，分母为成功完成第一轮分析的有效用户句子；页面同时展示分子、分母和排除原因。
- 自动分析完成后生成不可变初步报告；全部人工复核完成或负责人确认提前结束后生成新的不可变最终报告，部分覆盖必须披露复核覆盖率。
- 报告只评价未知厂商的线上历史转写，不把评测 ASR 当成被测生产模型，也不直接输出生产调优或供应商选型结论。

### Benchmark、配置与治理

- 第二轮明确 Good/Bad 且满足证据准入规则时，以 `AI 标注`幂等入库；人工 Good/Bad 提交后以 `人工标注`入库。
- Benchmark 保存纯用户 WAV 片段、历史转写、最终标注、Good/Bad、语种、场景、标注来源及完整追溯快照，支持筛选、复听和勾选后下载 ZIP。
- 新增版本化的全局场景标签、质检上下文、两轮完整可编辑 Prompt、资源连接和成本价格配置。
- API Key 仅允许写入或替换，使用 Fernet 加密保存；原始录音、历史对话和正式 Benchmark 至少保存 10 年，访问和处置可审计。
- 单批次预算默认上限不超过 10 美元；达到上限停止创建新的外部任务并保存检查点。

## Not in Scope

- TTS、LLM 或端到端语音体验评测。
- 修改、切换或直接接入线上流式 ASR。
- 使用 Benchmark 自动批量计算各供应商 WER/CER。
- 任务领取、复核分配、多人并发锁定和细粒度角色权限。
- 根据本批次报告自动修改生产词表、Prompt、模型或供应商。

## Impact

- Affected specs: 新增 `asr-automated-evaluation`、`evaluation-configuration`、`benchmark-library`。
- Affected code: 新增 evaluation 领域模型、SQLite 表与存储、异步任务编排、ASR/LLM 适配、音频处理、API、Evaluation 前端页面和测试。
- External dependencies: Soniox、Speechmatics、ElevenLabs 异步 ASR，以及用户配置的两轮 LLM；所有调用均需显式超时、重试、限流和幂等。
- Data impact: 录音与对话属于敏感业务数据；不得写入普通日志或提交仓库，第三方处理必须使用批次中明确选择且已验证的资源。
- UI risk: High。涉及新产品区域、多页面、弹窗、抽屉、长文本、双语、音频和批量状态，必须按两个 User Gate 与 Engineering Checkpoint A/B/C 验收。

## Confirmed Product Decisions

- `PRD.html V1.17` 与 `prototypes/index.html V1.18`（SHA-256 `e88e8be8f79572d4118399e3030d227a181f504799a0e06e3421d1b5bc8922c0`）共同构成本 Change 的唯一当前需求基线；V1.17 及更早原型仅保留历史审计记录，旧 `PRD.md V0.1` 和旧评审页已删除。
- 输入保持真实离线数据结构：每通一个 Excel，而不是把多通对话合并到单个工作簿。
- 疑似错误占比分子只包含第二轮 Bad 与需人工复核，不包含第二轮 Good。
- Good Case 最终目标与 Bad Case 为 1:1；同一完整通话的 ASR 结果复用。
- 人工必须显式选择 Good/Bad；听不清完成复核后从 Benchmark 候选中排除。
- 不使用 LLM 置信度阈值作为自动入库条件。
