# Delta: ASR Automated Evaluation

## Purpose

将既有离线 ASR 质检流程产品化为可追溯、可恢复、由 AI 筛选并由人工兜底的批次评测流程。

## ADDED Requirements

### Requirement: Environment-isolated evaluation data

本地开发、验收与生产环境 MUST 使用彼此独立的数据存储。生产部署 MUST 只初始化数据库结构和明确批准的正式配置，不得复制本地测试批次、报告、人工复核、Benchmark、成本台账、上传包、录音或测试生成物。

#### Scenario: Deploy a fresh production environment

- **WHEN** 运维首次部署或重建生产评测服务
- **THEN** 服务绑定明确的生产数据卷，启动后的批次、报告、复核和 Benchmark 列表均不包含任何本地测试 ID 或本地测试媒体

#### Scenario: Reject an accidental local-data migration

- **WHEN** 上线检查发现目标卷来自本地验收环境、包含本地批次 ID 或无法证明数据来源
- **THEN** 部署必须停止，不得通过复制 SQLite、Docker named volume、上传目录或生成物目录继续上线

### Requirement: Version-frozen evaluation batch

系统 MUST 允许有权限用户创建 ASR 评测批次，并在批次开始时冻结质检上下文、关联参考词典、场景标签、筛查策略、两轮 Prompt、评测 ASR、两轮 LLM、模型、资源连接引用、价格和预算版本。历史批次 MUST 始终使用其冻结快照，不受后续配置编辑影响。

#### Scenario: Start a valid batch

- **WHEN** 用户完成数据校验、选择至少一家可用评测 ASR、两轮 LLM 和有效预算并确认开始
- **THEN** 系统创建不可变配置快照、生成稳定 batch ID，并从数据校验检查点开始异步执行

#### Scenario: Reject a model without frozen pricing

- **WHEN** 用户选择的第一轮或第二轮 LLM 在当前价格版本中没有对应 Model ID 的价格
- **THEN** 系统在创建批次前拒绝请求，明确提示先在成本配置中补充价格，不得创建运行中批次或发起外部调用
- **AND** 新建评测弹窗保持打开，并在确认按钮附近持续显示可访问的错误说明，直到用户修改输入或再次提交，不得仅使用短暂 Toast

#### Scenario: Open a clean new-evaluation draft

- **WHEN** 用户点击“新建评测”
- **THEN** 系统丢弃上一份未启动的上传/修复候选包，恢复当前正式数据快照和默认表单值，不得将上一次弹窗中的文件名、候选 ID 或临时选择带入新草稿

#### Scenario: Discard a mistaken staged upload

- **WHEN** 用户在批次启动前删除本次暂存的上传或修复候选包
- **THEN** 系统只删除该未启动候选及其暂存文件，恢复当前正式数据快照，不得删除或替换已启用来源数据

#### Scenario: Delete a non-running batch

- **WHEN** 用户二次确认删除 audit-only、执行失败、已停止、待复核或已完成的批次
- **THEN** 系统原子删除该批次拥有的结果、复核、Benchmark、报告、执行检查点和成本记录，从列表与汇总中移除该批次，同时保留不含客户内容的删除审计墓碑；共享来源数据、连接和配置不得被删除

#### Scenario: Reject deletion while work can still run

- **WHEN** 用户尝试删除 running、paused 或 budget-paused 批次
- **THEN** 系统拒绝删除并提示先停止任务，不得让可能仍在供应商执行或计费的作业失去本地追踪

#### Scenario: Retry one batch creation request

- **WHEN** 同一新建草稿因重复点击、超时或响应丢失而使用同一幂等键再次提交
- **THEN** 系统返回首次创建的同一批次，不得重复冻结配置、启动任务或产生费用

#### Scenario: Configuration changes after start

- **WHEN** 管理员在批次开始后修改标签、上下文、Prompt、连接、模型或价格
- **THEN** 运行中和历史批次继续引用原快照，新版本只供后续批次选择

### Requirement: Per-conversation package contract

系统 MUST 接受包含 `conversation_history/`、`record/` 和 `user_record/` 的压缩包。每通对话 MUST 分别对应 `conversation_history/{full_conversation_id}.xlsx`、`record/{full_conversation_id}.mp3` 和 `user_record/{full_conversation_id}.wav`，不得要求把多通对话合并到单个 `conversation_history.xlsx`。

每个 Excel MUST 包含 `Dialogue Details` 工作表及 `time (s)`、`robot`、`customer` 三列；每行按时间表达一个事件且只能有一个角色文本。系统 MUST 从文件名取得完整 conversation ID，并读取文件实际内容验证音频编码、采样率、声道和时长。

#### Scenario: Import the RiyadBank fixture structure

- **WHEN** 用户上传按完整 ID 命名的逐通 Excel、完整通话 MP3 和纯用户 WAV
- **THEN** 系统按 ID 建立一对一关联，并显示可处理通数、文件数、实际音频属性和校验结果

#### Scenario: Reject a malformed conversation

- **WHEN** 任一对话缺少三类文件之一、ID 重复或不一致、Excel 缺少工作表/列、同一行有双角色文本，或音频不可解码
- **THEN** 系统阻止批次开始，生成包含 issue type、conversation ID、期望路径、来源文件/行和说明的问题清单，并允许定向上传修复文件

#### Scenario: Validate the shared audio timeline

- **WHEN** 完整通话 MP3 与纯用户 WAV 的时长差或时间轴校验超过系统允许误差
- **THEN** 系统把时长差、事件时间超出音频时长标为可审计的参考警告，不得仅因此阻止批次开始；但下游不得把受影响时间段当作可靠的精确剪切依据，须保留警告或排除该 Benchmark 切片

#### Scenario: Preserve historical row order when timestamps go backwards

- **WHEN** Excel 行可以正常解析且音频关联有效，但相邻历史事件的 `time (s)` 出现倒退
- **THEN** 系统保留工作表行顺序作为对话顺序，把时间倒退作为可审计的参考警告展示，不自动重排事件，也不得仅因此阻止批次开始

### Requirement: First-pass candidate screening

第一轮 LLM MUST 只评估历史 Excel 中的用户事件，使用完整对话、冻结的质检上下文、通用参考词典集合、筛查策略和场景标签识别可能改变业务含义的疑点 Case。机器人事件、空白事件和损坏事件 MUST NOT 计入有效用户句子或疑点候选。

质检目标 MUST 仅限于检测线上 ASR 是否准确保留用户实际语音及必要业务含义。用户未回答机器人、回答不符合预期流程、意图不合理、业务未完成或机器人表现异常本身 MUST NOT 构成 ASR 疑点；只有历史转写文本存在可被录音或评测 ASR 核验的遗漏、替换、截断、边界或说话人归属风险时才可进入候选。

系统 MUST 同时在包含疑点的对话内维护额外 Good Case 候选池；候选池只包含第一轮未发现实质疑点且具备有效文本、时间和音频关联的用户事件。

#### Scenario: Screen a conversation

- **WHEN** 第一轮分析一通有效历史对话
- **THEN** 系统保存每个用户事件的 pass、candidate 或 data issue 结果、原因、业务影响和上下文引用，但不把第一轮结果直接作为 Ground Truth

#### Scenario: Build the additional Good pool

- **WHEN** 一通对话至少产生一个疑点 Case
- **THEN** 系统把同一对话中合格的非疑点用户事件加入该批次的额外 Good Case 候选池，不从无疑点对话扩大抽样范围

#### Scenario: All first-pass requests fail

- **WHEN** 第一轮所有对话在重试后均失败且没有任何成功结果
- **THEN** 批次进入可重试失败状态并显示第一轮失败，不得继续进入评测 ASR 或显示空的 0/0 运行任务

#### Scenario: First pass finds no candidates

- **WHEN** 第一轮至少有成功结果但没有任何疑点或额外 Good 候选需要重转录
- **THEN** 系统生成零候选初步报告并正常结束批次，不创建评测 ASR 或第二轮任务

### Requirement: User-event ASR retranscription

第一轮识别出需要评估的目标用户事件后，系统 MUST 按该事件开始时间至下一历史事件开始时间，从已校验同时间轴的 `user_record/{conversation_id}.wav` 裁出只含用户声音的事件音频，并将该音频分别提交给每家启用的评测 ASR。第二轮和人工复核 MUST 使用这些事件级重转录结果，不得从完整通话 ASR 结果或带上下文余量的播放区间拼接候选文本。

#### Scenario: Transcribe one target user event

- **WHEN** 第一轮将一个有效用户事件识别为疑点 Case 或额外 Good Case
- **THEN** 系统为该 Case 生成稳定的纯用户音频切片，并为每个启用的评测 ASR 至多创建一个可恢复、可计费的事件级转录任务

#### Scenario: One conversation contains multiple cases

- **WHEN** 同一 conversation ID 包含多个需要第二轮判断的目标用户事件
- **THEN** 系统分别裁切每个事件并独立重转录，不得使用相邻机器人事件或其他用户事件的 ASR 文本填充当前 Case

#### Scenario: Reject an unreliable user-event clip

- **WHEN** 纯用户 WAV 与事件时间轴不一致、事件边界无效或无法生成非空切片
- **THEN** 对应事件级 ASR 任务明确失败且不产生候选文本，不得回退到完整通话转写片段冒充纯用户结果

#### Scenario: Receive an asynchronous callback twice

- **WHEN** 供应商 webhook 或轮询重复返回同一 job 的完成结果
- **THEN** 系统按 provider job ID 幂等保存一次，不重复触发费用、第二轮分析或 Benchmark 入库

### Requirement: Independent ASR result and partial failure

Soniox `stt-async-v5`、Speechmatics `melia-1` batch/multi 和 ElevenLabs `scribe_v2` webhook 的任务、segments、时间戳、说话人、状态和错误 MUST 独立保存。失败 MUST NOT 被表示为空转写，也不得覆盖已成功资源。

#### Scenario: One evaluation ASR fails

- **WHEN** 线上历史转写和至少一家评测 ASR 成功，但其他资源在自动重试后仍失败
- **THEN** 第二轮继续，Case 标记为证据不完整；用户可只重试失败资源，已成功资源不得重复调用

#### Scenario: All evaluation ASRs fail

- **WHEN** 某通对话的全部评测 ASR 均无法产生可用结果
- **THEN** 该对话暂停进入第二轮并显示可操作错误，不生成默认 Good/Bad 结论

#### Scenario: Report preserves successful event-level ASR evidence

- **WHEN** 某个 Case 至少一家评测 ASR 已成功，无论第二轮是否为每家结果生成引用片段
- **THEN** 报告 Case 明细均直接展示每家已落库的事件级 ASR 转写；第二轮引用只能缩小或补充证据定位，不得决定原始 ASR 转写是否可见

### Requirement: Evidence-based second-pass decision

第二轮 LLM MUST 将历史转写和每家评测 ASR 都视为证据而非真值，并结合完整对话、语义、实体、数字、否定、语种、说话人和事件边界，为每个被评估用户事件输出 `Good Case`、`Bad Case` 或 `需人工复核`。

第二轮 MUST 启用所选模型的 Thinking 能力，并使用动态 Token 装箱：同一通对话的完整历史、全部可用评测 ASR 证据及其候选 Case MUST 作为不可拆分单元；系统 MUST 根据已验证上下文上限、System Prompt、推理/输出预留、安全余量和 Case 输出数量计算最少安全分组，不得使用固定“每组几通”。全部单元可安全容纳时 MUST 只发起一组请求。系统 MUST 分别记录唯一 Case 数和外部请求组数，失败重试不得导致 Case 漏失、重复判断或重复计费。

每个请求组 MUST 携带稳定 `request_group_id`。第二轮结构化输出 MUST 原样返回该 ID，并以顶层 `results[]` 为组内每个输入 Case 恰好返回一个结果；每个结果 MUST 包含匹配的 conversation/issue/event ID 和 `positioning_quality`。组 ID 不匹配、Case 遗漏、重复或越界 MUST 使整个组失败并按相同冻结成员重试，不得保存部分结论。

#### Scenario: Dynamic packing grows with the batch

- **WHEN** 一个批次的完整第二轮输入无法在预留 Thinking 和结构化输出空间后放入一个请求
- **THEN** 系统按对话不可拆分地生成最少安全分组，只重试失败组，并保持每个唯一 Case 恰好获得一个最终决定

#### Scenario: Reject a mismatched grouped response

- **WHEN** 第二轮返回错误的 `request_group_id`，或 `results[]` 遗漏、重复、增加了任一 Case
- **THEN** 系统拒绝整组响应且不保存部分决定，并使用原组成员和幂等键进入可审计重试

#### Scenario: Qwen Thinking returns structured JSON

- **WHEN** 第二轮选择 Qwen 且必须启用 Thinking
- **THEN** 系统不得同时发送 Qwen 不兼容的 JSON Mode 参数，而应依赖冻结 Prompt、JSON 解析与完整 Schema 校验；格式或契约失败仍按同一冻结请求组重试

#### Scenario: Second-pass groups remain failed

- **WHEN** 任一第二轮请求组在自动重试后仍失败
- **THEN** 批次保持可重试的部分失败状态，不得冻结或展示为正常完成的初步/最终报告；已成功的 Pass 1、事件级 ASR 和第二轮分组结果继续独立保存且不得被空值覆盖，页面提供明确标记为“部分结果、非完整报告”的只读入口

#### Scenario: Inspect successful work after a batch failure

- **WHEN** 批次在任一阶段进入失败或部分失败，且至少一个检查点已经成功持久化
- **THEN** 部分结果页按实际完成阶段展示成功 Pass 1 数量与候选、每家事件级 ASR 转写、已完成第二轮结论、成本台账、失败阶段和可操作错误；尚未执行的区域显示“未运行”而不是空结果，且重试后继续复用既有成功检查点

自动 Good/Bad 准入 MUST 同时满足：输出 Schema 合法、决定值合法、建议标注文本非空、证据可定位，并且至少一家评测 ASR 成功。系统 MUST NOT 使用 LLM confidence 数值或供应商简单多数票替代这些规则。

当 Case 无法匹配批次冻结的已有场景标签时，第二轮 LLM MUST 同时输出建议标签的中英文名称、中英文自然语言描述及声学/语义类型；只有名称或只有描述的建议 MUST 视为结构不完整，不得直接创建全局标签。建议标签 MUST 描述可复用的中性 ASR 质检维度，不得把用户行为、业务流程完成度、用户意图或机器人表现命名为错误类别。Good Case 可归入同一中性质检维度，但标签文案不得暗示用户行为本身有错。

#### Scenario: Production transcript is supported

- **WHEN** 证据表明历史转写保留了必要业务含义且满足自动准入规则
- **THEN** 第二轮输出 Good Case，并以历史转写作为建议标注文本

#### Scenario: Production transcript is contradicted

- **WHEN** 证据表明历史转写改变或遗漏必要业务含义、能够形成证据支持的正确文本且满足自动准入规则
- **THEN** 第二轮输出 Bad Case，并保存建议标注、场景、语种、差异和证据定位

#### Scenario: Evidence is irreducibly ambiguous

- **WHEN** 多个候选无法可靠区分、无法形成非空正确文本、音频定位不足或输出不满足自动准入规则
- **THEN** Case 进入人工复核并预填具体回听问题，不得强行输出 Good/Bad

#### Scenario: Propose a new scenario tag

- **WHEN** 一个或多个 Case 无法匹配任何已启用场景标签
- **THEN** 第二轮将这些 Case 暂存为“待归类（AI 建议）”，并输出可在报告核对的双语标签名称、双语标签描述、类型和关联 Case

#### Scenario: A user does not follow the expected dialogue flow

- **WHEN** 用户没有回答当前机器人问题、表达与当前业务阶段无关或未推动流程，但历史转写准确保留了实际发言
- **THEN** 系统不得仅因该用户行为判为 ASR Bad Case，也不得生成描述该用户行为为问题的建议标签；如需归类，只能使用中性的 ASR 质检维度

### Requirement: One-to-one Good and Bad balance

系统 MUST 将第一轮疑点被第二轮判为 Good 的 Case 计入 Good 数量，并从额外 Good 候选池中抽样补足，使本批次最终可入库 Good Case 与 Bad Case 的目标比例为 1:1。抽样 MUST 只使用已完成第二轮证据判断且满足自动准入规则的候选。

#### Scenario: Additional Good samples are available

- **WHEN** 最终 Bad 数量大于已确认 Good 数量且额外 Good 候选充足
- **THEN** 系统以可复现的抽样规则补足差额，最终 Good 数量等于 Bad 数量

#### Scenario: Good pool is insufficient

- **WHEN** 合格额外 Good 候选少于所需差额
- **THEN** 系统入库全部合格 Good，报告实际比例、目标比例和短缺数量，不重复或伪造样本

### Requirement: Unified playback interval

系统 MUST 使用目标用户事件在纯用户 WAV 上的稳定切片作为统一回听区间。事件级 ASR 返回的 Segment ID 和时间戳相对于该切片，仅作为默认折叠的技术证据；人工播放器和 Benchmark 剪辑 MUST 使用同一纯用户事件切片，不得增加会跨入相邻事件的上下文余量。

#### Scenario: Vendor segment boundaries differ

- **WHEN** 多家 ASR 对同一纯用户事件切片返回不同的切句边界
- **THEN** 系统保留各家事件级候选文本和片段证据，但三家共用同一源切片回听，不根据供应商边界扩大音频范围

#### Scenario: Precise alignment is unavailable

- **WHEN** 系统无法可靠定位到句子级时间范围
- **THEN** 回听范围降级为更宽区间或完整录音并明确定位精度，不伪造精确时间戳

#### Scenario: Control inline Case playback

- **WHEN** 用户在报告的建议标签明细或 Case 明细中点击试听
- **THEN** 页面在当前行就地展示播放/暂停、继续播放、可拖动进度条、当前时间和总时长；开始播放另一条 Case 时停止并收起上一条播放器

### Requirement: Explicit manual Good or Bad review

人工复核 MUST 以一个目标用户句子为最小任务单位，并就近展示历史转写、当前建议标注、各 ASR 候选、统一用户音频、必要上下文、语种和场景标签。复核人员 MUST 明确提交 Good、Bad 或听不清。

#### Scenario: Submit Good

- **WHEN** 复核人员试听后选择 `Good · 历史转写正确`
- **THEN** 系统以历史转写作为人工标注，保存 Good、语种、标签、操作者、时间和证据快照，并进入下一任务

#### Scenario: Submit Bad

- **WHEN** 复核人员选择或手填非空正确文本并选择 `Bad · 保存正确标注`
- **THEN** 系统保存 Bad、最终人工标注、候选来源/编辑差异、语种、标签、操作者、时间和证据快照，并进入下一任务

#### Scenario: Submit unclear audio

- **WHEN** 复核人员确认目标音频听不清
- **THEN** 系统将 Case 记录为已复核且不可标注，从正式 Benchmark 和人工 Good/Bad 统计中排除，但保留审计与排除原因

#### Scenario: Switch review items without submitting

- **WHEN** 复核人员点击左侧其他任务
- **THEN** 页面允许直接切换，不得把未提交的当前草稿误记为已复核

#### Scenario: Read Arabic evidence during manual review in Chinese mode

- **WHEN** 用户在中文模式打开一个包含阿语历史转写、上下文或评测 ASR 候选的人工复核任务
- **THEN** 页面保留每段阿语原文，并按需复用该批次冻结的第一轮 LLM 自动显示中文对照；只发送当前任务中确实含阿语的业务文本，译文不得写入人工结论、报告或 Benchmark

#### Scenario: Recover from malformed display translation output

- **WHEN** 中文对照调用返回网络错误、非 JSON、缺失索引或不完整译文
- **THEN** 系统先对原组自动重试一次；仍失败且原组超过 4 条时，按稳定顺序拆为每组最多 4 条并分别重试后合并，所有调用继续受冻结预算约束；预算拒绝不得重试，最终失败不得隐藏或覆盖原文

#### Scenario: Preserve successful display-translation chunks

- **WHEN** DeepSeek 用于中文对照或拆分后只有部分翻译小组成功
- **THEN** 系统 MUST 仅为显示翻译显式关闭 Thinking，第一轮和第二轮行为不得改变；页面 MUST 按原索引展示成功译文，并只在失败文本旁显示中文对照暂不可用，不得整体丢弃已成功小组

### Requirement: Early review completion

负责人 MUST 能在二次确认后提前结束人工复核。系统 MUST 保留未复核 Case 状态，不将其写入正式 Benchmark 或人工结论，并生成标记为部分覆盖的最终报告。

#### Scenario: Confirm early completion

- **WHEN** 负责人确认提前结束且仍有未复核 Case
- **THEN** 系统冻结未完成队列，生成最终报告，并明确展示复核完成率、已复核、未复核、听不清及结论覆盖范围

### Requirement: Evaluation metrics

系统 MUST 使用以下稳定口径并同时展示分子、分母、排除数量和原因：

- 疑似错误用户句子占比 = 第二轮 `Bad Case + 需人工复核` 数量 ÷ 成功完成第一轮分析的有效用户句子总数；
- 人工确认错误占比 = 人工复核判为 Bad 的数量 ÷ 同一批次有效用户句子总数；
- 复核完成率 = 已提交 Good、Bad 或听不清的人工任务数 ÷ 应人工复核任务总数。

#### Scenario: Calculate a fixed 20/6/4 formula fixture

- **WHEN** 自动化测试使用固定 mock 输入：20 个 Bad、6 个 Good、4 个需人工复核和 441 个有效用户句子
- **THEN** 疑似错误分子为 24 而不是 30，页面显示 `24 / 441`、百分比和被排除事件明细

### Requirement: Immutable preliminary and final reports

系统 MUST 在自动分析完成后生成不可变初步报告，并在全部人工复核完成或负责人提前结束后生成新的不可变最终报告。报告 MUST 归属于单一批次，历史版本不得被覆盖。

#### Scenario: Automated analysis finishes

- **WHEN** 第二轮和 Good:Bad 抽样完成但仍有人工任务
- **THEN** 系统生成初步报告，立即从批次列表和批次详情提供报告入口，明确其人工复核覆盖率为当前值，不伪装为最终结论

#### Scenario: Repair an unlinked frozen report

- **WHEN** 服务恢复时发现初步报告已经冻结、但所属批次缺少报告类型或入口指针
- **THEN** 系统自动恢复批次与既有不可变报告的链接，不重新生成或覆盖报告内容

#### Scenario: Review finishes

- **WHEN** 所有人工任务提交完成
- **THEN** 系统生成最终报告版本，包含疑似/人工确认占比、复核覆盖、语言/场景分布、标签建议、证据和批次观察

#### Scenario: Report production ASR observations

- **WHEN** 报告按场景汇总识别问题
- **THEN** 页面只把历史转写称为线上 ASR 结果，不猜测其供应商；Soniox、Speechmatics 和 ElevenLabs 只作为评测证据，不输出直接调优或模型选型动作

#### Scenario: Canonicalize report tags and result totals

- **WHEN** 第二轮使用同一冻结标签的 key、英文名或中文名返回结果
- **THEN** 报告按该标签的冻结 key 合并为一个分组，并分别展示候选数、最终疑似数以及实际自动生成的 Good/Bad Benchmark 数，不得混用三个口径

#### Scenario: Filter report Cases by scenario tag

- **WHEN** 用户在批次报告的完整 Case 明细中选择一个正式场景标签或“待归类（AI 建议）”
- **THEN** 页面只展示匹配的 Case，并同时显示匹配数量与本批次 Case 总数；筛选不得修改不可变报告、标签或 Case 归类

#### Scenario: Create an AI-proposed tag from the report

- **WHEN** 用户在建议标签明细中确认创建某个 AI 建议标签
- **THEN** 系统在同一事务中使用报告内的双语名称、双语描述和类型创建全局场景标签，并把全部关联 Case 批量移动到新标签；单条 Case 后续仍可人工改组

### Requirement: Verifiable model-specific pricing draft

系统 MUST 按具体 ASR 能力或 LLM Model ID、计费单位和币种维护价格。点击官网同步时，服务端 MUST 从固定白名单官网核对当前公开价及型号证据，并只生成待保存草稿；不得仅更新时间或复用其他型号价格来伪装同步。官网不可访问、型号无公开价或证据发生变化时 MUST 保留当前输入并明确失败。

#### Scenario: Sync public ASR list prices

- **WHEN** 用户同步 Soniox 异步转写、Speechmatics Melia 1 和 ElevenLabs Scribe v2 的公开价
- **THEN** 系统从各自官网核对按音频小时公开价、显示可点击来源和核对时间，并将结果作为未保存草稿

#### Scenario: Sync the two selected LLM models

- **WHEN** 用户为两轮分别选择或输入准确 Model ID 并点击同步
- **THEN** 系统逐行按对应厂商、Model ID 和币种载入输入、缓存输入及输出单价；切换型号后旧价格立即失效并要求重新同步

#### Scenario: Official evidence cannot be verified

- **WHEN** 官网不可访问、页面证据与受审价格不一致，或自定义 Model ID 没有受审公开价
- **THEN** 系统不得覆盖任一价格字段或显示“已同步”，并提示用户人工录入合同价或稍后重试

### Requirement: Recoverable batch execution and cost stop

所有外部调用 MUST 显式配置超时、限流、最多三次自动重试和幂等标识。批次 MUST 保存阶段检查点；预算达到批次硬上限时 MUST 停止创建新的外部调用，但保留已完成结果并允许调整后恢复。

#### Scenario: Budget limit is reached

- **WHEN** 已核算费用达到批次预算上限
- **THEN** 批次进入已暂停，停止新建 ASR/LLM 任务，展示已花费、上限和待处理数量，并可从检查点恢复

#### Scenario: Retry a failed provider

- **WHEN** 用户对部分失败批次执行定向重试
- **THEN** 系统只为失败且可重试的 provider/conversation job 创建新尝试，复用成功结果且不重复生成 Case 或 Benchmark

### Requirement: Bilingual and overflow-safe evaluation UI

Evaluation 页面 MUST 支持 English 与中文。英文模式不得出现中文 UI 或中文化的演示上下文；固定系统文案、按钮、字段名、状态和提示 MUST 使用前端本地词典，MUST NOT 作为 LLM 翻译入参。中文模式打开真实英文/阿文对话时，系统 MUST 保留原文并按需复用批次冻结的第一轮 LLM 生成中文对照；只发送当前可见原始对话文本，译文仅在当前浏览器会话缓存，MUST NOT 写入原始转写、报告或 Benchmark，也 MUST NOT 作为评测证据。厂商名、Model ID 和 Prompt 原文不得被翻译。翻译失败时 MUST 保留原文并明确显示译文暂不可用。所有 dialog、drawer 和 popover 在固定桌面与窄屏视口 MUST 满足 `scrollWidth <= clientWidth`。

#### Scenario: Review an English case in English mode

- **WHEN** 用户以 English 模式打开人工复核
- **THEN** 页头、必要上下文、按钮、帮助文案、错误和动态状态均为英文，原始转写保持原文

#### Scenario: Open a real English or Arabic conversation in Chinese mode

- **WHEN** 用户在中文模式主动打开报告中的真实对话历史
- **THEN** 页面立即展示不可变原文，并把当前可见原始对话文本发送给批次冻结的第一轮 LLM 生成中文对照；系统文案不在请求中，译文失败不遮挡原文

#### Scenario: Reuse a display translation in the same browser session

- **WHEN** 用户在同一浏览器会话再次打开已翻译的对话
- **THEN** 页面使用会话缓存，不重复调用 LLM，且源数据、冻结报告、Benchmark 和证据字段均保持不变

#### Scenario: Open long content on a narrow viewport

- **WHEN** 长 conversation ID、阿文、Prompt 或错误路径出现在窄屏浮层
- **THEN** 内容收缩或换行且只有必要的纵向滚动，不产生横向滚动
