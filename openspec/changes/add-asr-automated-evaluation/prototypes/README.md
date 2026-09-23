# ASR 自动化评测原型说明

## 最新版本

- 原型：`index.html`
- 版本：V1.19（2026-09-22，六步流程与独立 Event Alignment）
- 状态：Gate 1 已确认并冻结，作为唯一当前 UI baseline
- 基线 SHA-256：`17829744d355bc86da3625cdf5fc24b94a6a44db5e67551046e046abbd89649c`
- 确认人/日期：Product owner / 2026-09-22（PD-067、PD-069；V1.18 历史基线见 PD-066）
- 需求基线：同目录 `../PRD.html` V1.17 与本 Change Delta Specs
- 数据：业务结果仍为固定演示数据；file 原型不调用真实 ASR、LLM 或音频接口，正式页面的“实测模型”复用现有 LLM 诊断接口
- 历史原型：无；本目录只保留当前最新版

## 已确认产品口径

1. 输入只支持逐通文件：`conversation_history/{conversation_id}.xlsx`、`record/{conversation_id}.mp3`、`user_record/{conversation_id}.wav`。
2. 第一轮从历史对话筛疑点，并从同一疑点对话建立额外 Good 候选池；完整对话不可拆分，整批能安全容纳时一次请求，超限时动态 Token 拆组（PD-045，不改变冻结视觉结构或基线文件）。
3. 疑点复判为 Good 和额外抽样都是 Good 来源；最终 Good:Bad 目标为 1:1。
4. 同一通完整录音每家评测 ASR 只转写一次；Event Aligner 命中的 provider turn 文本直接作为 Case 候选。纯用户 WAV 只裁片用于试听、人工复核和 Benchmark，不再增加 ASR 转写任务（PD-061）。
5. 第二轮页面使用“疑似 ASR 错误 / 大概率正确 / 需人工复核”，不暴露离线内部枚举。
6. 疑似错误占比分子为“第二轮 Bad + 需人工复核”，不包含第二轮 Good。
7. 人工复核以目标用户句子为最小单位，历史转写和当前建议标注必须就近展示。
8. 人工必须显式选择 Good 或 Bad；Good 使用历史转写，Bad 必须保存正确文本。
9. 听不清视为已复核但不进入 Benchmark、不计入人工 Good/Bad；保留排除审计。
10. 两轮 Prompt 不输出 LLM confidence，也不使用 confidence 阈值决定自动入库；依据结构、标注、证据定位和可用评测 ASR 判断。
11. Segment ID 只显示在技术证据中；播放器使用程序合并后的统一回听区间。
12. 英文模式不得出现中文 UI 或中文演示上下文；中文模式可显示原文加中文释义。
13. 报告中的 Case 试听必须就地提供播放/暂停、继续、可拖动进度与当前/总时长；同一时刻只播放一条。
14. 报告完整 Case 明细可按正式场景标签或“待归类（AI 建议）”筛选，显示命中数/总数，且不修改冻结报告。
15. 第二轮对待归类分组同时输出双语标签名称、双语标签描述和类型；报告就近展示，确认创建时完整写入全局标签并批量移动关联 Case。
16. 正式页面的模型列表来自服务端目录；“实测模型”发起一次最小真实 LLM 请求并展示脱敏诊断结果，不自动填写或改写价格。
17. Gemini 正式型号包含 `gemini-3.8-flash`；带 `Gemini/` 前缀的输入先规范化；厂商和 Base URL 一致时，可复用已有 Bot 的加密 Key 临时测试服务端目录内的所选型号，不修改原 Bot，也不要求重复填写 Key。
18. Benchmark 每页 20 条；“下载已选”支持跨页选择，“下载全部筛选结果”覆盖当前条件的所有分页；ZIP 根目录为 `benchmark.csv`，音频按 `wav/<语种>/<主场景标签>/<benchmark-id>.wav` 分组，CSV 至少记录音频路径、Benchmark ID 和标注文本。
19. 场景标签来自可维护的数据源，不在页面硬编码；支持新建、编辑和删除。编辑产生新版本；删除后不再供新批次和新标注选择，但历史批次、报告和 Benchmark 继续读取原标签快照。
20. “新建上下文”和“编辑新版本”必须打开完整表单；利雅得银行上下文预填业务目标、流程、术语、规则与风险，保存只创建新版本。
21. 上线初始两轮 Prompt 参考历史离线任务整理为中文；两轮均使用通用 `reference_dictionaries`，第一轮保留筛查档位和事件级输出，第二轮保留 segment 证据、Good/Bad/人工复核、双语建议标签和无 confidence 阈值规则。
22. Soniox、Speechmatics、ElevenLabs 均可在资源连接页直接测试并与异步能力卡片同步状态；LLM 四家复用现有真实诊断接口，在当前卡片显示测试中、诊断成功或缺少 Key/接口失败原因。
23. “分行词典”改为通用参考词典的一个业务实例；词典独立版本化并由上下文关联。页面明确展示 conversation history、context、dictionaries、screening strategy 和 scenario tags 的运行时来源，批次开始后统一冻结并传给两轮 LLM。
24. 两轮完整 System Prompt 默认只读，只能通过“编辑固定模板”进入修改；上下文列表与编辑表单可预览两轮模板与成品 Prompt。
25. Prompt 模板显式保留每个 Session 的 `{{variable}}` 插槽；预览提供“填写项 → 模板变量 → 成品字段”对应关系，并完整替换 Context、Session 与关联词典的所有 entries。
26. Benchmark 支持 All/Good/Bad 类型筛选、每页 20 条分页和样本编辑；保存编辑时追加不可变修订，不覆盖历史值。
27. 第二轮 Prompt 使用动态分组契约：输入显式包含 `request_group_id` 和组内 Case 数组，输出以同一 ID、`results[]` 及逐 Case `positioning_quality` 返回；不得继续使用单 Case 顶层输出。
28. 未启动的暂存上传可单独删除；audit-only、失败和已停止批次可二次确认后删除，运行中/暂停中任务必须先停止；有效完成批次继续固定留存 10 年。
29. 中文模式中的固定系统文案只使用前端词典；打开真实英文/阿文对话时按需复用批次冻结的第一轮 LLM，显示不可变原文与临时中文对照。译文不落库、不进入报告或 Benchmark，失败时仍保留原文（PD-030；本项不改变已冻结视觉结构或基线文件）。
30. Azure GPT 与 OpenRouter 复用现有连接卡片视觉与交互，但作为两个独立资源展示；失败/部分失败批次复用正式报告详情组件展示“部分结果 · 非完整报告”，不得用空白报告或正常报告状态代替（PD-041）。
31. Benchmark Library 的列表行和样本详情复用既有危险操作按钮与确认弹窗模式，支持单条硬删除；确认文案明确只删除样本、修订与派生 WAV，并保留源对话、批次、报告和人工复核（PD-050；不改变冻结页面结构）。
32. 失败重试不再只显示百分比：沿用批次状态区域展示 Case 与请求组的成功、失败、处理中和尝试次数；疑点全部成功前不追加 Good 平衡样本，超时父组拆分状态使用同一区域呈现（PD-052；不改变冻结页面结构）。
33. 两轮评测采用统一 128K 运行包络并在发送前完成去重与装箱；Pass 2 单通可按 Case 子集预拆。该行为继续复用既有 Case/请求组计数和错误状态，不新增页面区域、不修改冻结视觉基线（PD-058）。
34. Pass 2 的 Thinking 与可见 JSON 共享 32K 生成预算；规划失败保留最后阶段和进度。ASR 安全诊断复用批次错误区、部分结果提示与既有 provider 单元格，不新增页面区域、不修改冻结视觉基线（PD-059）。
35. 已有初步报告的暂停/部分失败批次在现有操作区增加“使用现有结果结束”，复用既有危险操作确认弹窗模式；文案明确保留成功结果、排除未完成项、生成不可变部分报告且不调用外部资源，不新增页面结构或修改冻结视觉基线（PD-060）。
36. 运行中的进度区域只展示当前正在等待的外部请求；每个并发请求独占一行，显示阶段/厂商、序号/总数和每秒变化的已等待时间。百分比和完成数仍由服务端检查点决定，计时不推动进度；心跳过期显示“状态同步中断”（PD-065）。
37. 暂停或部分失败的批次列表只显示 `N failed · M succeeded`；第一轮按 conversation、ASR 按完整通话 provider job、第二轮按 Case 计数，请求组与尝试明细只留在任务详情（PD-065）。
38. 批次详情采用六步：数据校验、第一轮分析、多 ASR 转写、Event Alignment、第二轮分析、人工复核。Align 的 Qwen 等待只显示在第 4 步；计时首帧直接显示当前请求实际耗时，多 ASR 活动行按每家 provider 自己的任务总数展示（PD-067、PD-069）。

## 需求到页面区域映射

| Delta Requirement | 原型入口/区域 | 状态 |
|---|---|---|
| Version-frozen evaluation batch | 评测批次 → 新建评测；`#new-run-dialog`；失败/停止批次删除确认 | 已确认并冻结 |
| Per-conversation package contract | 新建评测的数据上传与校验区域 | 已确认并改为逐通 Excel fixture |
| First-pass / conversation ASR / Event Alignment / second-pass | `#page-run` 六阶段、资源和候选结果 | 已确认（V1.19 / PD-067、PD-069） |
| Explicit manual Good or Bad review | `#page-review` 对照、候选与 Good/Bad/听不清 | 已确认 |
| Evaluation metrics / reports | 批次入口 → `#page-report` | 已确认 |
| Benchmark ingestion, single deletion and download | `#page-library`、`#sample-dialog`、删除确认弹窗 | 已确认；删除复用冻结按钮与弹窗模式 |
| Tags / context / Prompt / connections / cost | Configuration 四个入口；Azure GPT/OpenRouter 独立连接卡片 | 已确认；新增资源复用冻结卡片模式 |
| Failed-batch partial results | 批次操作 → 复用 `#page-report` 详情组件并显示“部分结果 · 非完整报告”状态条 | 已确认；不改变正常报告基线 |
| Finish with current results | 批次操作 → 复用 `#finish-dialog` 确认模式 → `#page-report` 最终部分覆盖报告 | 已确认；复用冻结弹窗与报告结构 |
| Live external-request visibility | 批次列表运行行与 `#page-run` 当前阶段 → 每个活动请求一行计时；暂停/部分失败列表使用精简摘要 | 已确认并冻结（V1.18 / PD-066） |
| Bilingual and overflow-safe UI | 全页面、dialog、drawer | 已确认；截图和自动断言在 Engineering Checkpoint A/C 留证 |

## 原型状态覆盖

2026-09-20 的运行时修复不更新冻结视觉基线：原型本来就只展示一个“评测报告”入口，并要求 Case 明细展示三家 ASR 证据。实现去除重复按钮并恢复已落库证据，是回归已确认基线而非视觉改版。

| Object | States |
|---|---|
| Batch | validating, running, paused, awaiting review, completed, completed partial, partially failed, safe terminal deletion, active deletion rejected |
| Import | empty, valid, missing file, malformed workbook/audio, repair upload, discard unstarted upload |
| ASR | pending, running, complete, partial failure, retry |
| Pass 2 | suspected error, likely correct, needs manual review, incomplete evidence |
| Review | pending, candidate selected, manual text, Good, Bad, unclear, submitted, early completion |
| Report | preliminary, final, final partial, immutable version history |
| Benchmark | AI/manual label, Good/Bad, type filter, both Good origins, 20 rows/page, selected/all-filtered download, detail/edit/new revision, grouped ZIP, unavailable audio |
| Scenario tag | created, edited as new version, deleted unreferenced, deleted referenced with historical snapshot retained |
| Evaluation context | prepared data, create, edit as new version, required-field error, historical snapshot retained |
| Prompt | read-only prepared Chinese template, explicit edit mode, valid new version, required-contract error, confidence-output rejection |
| Context Prompt preview | pass 1/pass 2 tabs, variable-bearing template, fully rendered Prompt, clickable field correspondence, all dictionary entries, current draft values, no horizontal overflow |

## Offline fixture provenance

The UI fixture is derived from the prior offline thread `01a09dd7-2f06-7392-ae69-ad6fd88d20db` and the local `benchmarks/RiyadBankConversation/` package. The prior run happened to produce 30 suspicious events split into 20 Bad, 6 Good and 4 review items. These values are fixed only for mocked formula/UI regression tests; a real LLM rerun may produce different counts and they are not product accuracy commitments.
