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

系统 MUST 同时在包含疑点的对话内维护额外 Good Case 候选池；候选池只包含第一轮未发现实质疑点且具备有效文本和音频关联的用户事件。Excel `time (s)` 的准确性不得决定候选是否有效。

第一轮请求 MUST 使用动态 Token 装箱。每通完整对话及其全部历史事件 MUST 作为不可拆分单元。系统 MUST 对最终将发送的完整消息执行统一运行包络预检：输入不得超过 64K Token，Thinking 与可见输出合计不得超过 32K Token，并在 128K 总包络中保留至少 32K Token 安全余量；若冻结模型的已验证限制更小，则使用较小值。业务证据 MUST 只在完成变量替换的 System Prompt 中出现一次，User message MUST 为不含业务证据的固定执行指令，不得再次序列化同一 payload。当整个批次可安全容纳时 MUST 只发送一个外部请求，超限时 MUST 自动形成最少安全分组，不得按固定对话数拆分、截断对话或遗漏事件。每组 MUST 使用稳定 `request_group_id` 和冻结成员关系，模型输出 MUST 对组内每通对话恰好返回一个完整结果；组 ID 不匹配、对话遗漏、重复或越界时 MUST 拒绝整组。重试 MUST 复用原组成员和幂等键，并且只重试失败组。

#### Scenario: Pack the complete first pass into one request

- **WHEN** 批次中所有完整对话及预留输出能够安全容纳在第一轮模型限制内
- **THEN** 系统只创建一个第一轮外部请求组，并在同一响应中校验和保存全部对话的事件结果

#### Scenario: Split an oversized first-pass batch safely

- **WHEN** 整个批次不能安全容纳，但每通完整对话均可独立容纳
- **THEN** 系统按 Token 和输出预留形成最少安全分组，保持每通对话完整且只出现一次

#### Scenario: Reject one oversized first-pass conversation before dispatch

- **WHEN** 单通完整对话在独立成组后仍超过最终消息的 64K 输入硬上限
- **THEN** 系统在外部调用前将该对话标记为可操作的尺寸失败，不得拆断历史事件、截断文本或先向供应商付费试错

#### Scenario: Retry only one failed first-pass group

- **WHEN** 某个第一轮请求组失败而其他组已经完成
- **THEN** 系统使用相同组 ID、成员关系和幂等键只重试失败组，不重复调用已完成组

#### Scenario: Screen a conversation inside a request group

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

### Requirement: Full-call ASR evidence and user-event clipping

第一轮识别出需要评估的目标用户事件后，系统 MUST 为每个命中 conversation/provider 至多提交一次显式启用 speaker diarization 的完整通话转写，并保存逐词/逐段文本、开始/结束时间、匿名 speaker 标签和稳定 turn ID。系统 MUST 先从 `user_record/{conversation_id}.wav` 的实际语音活动与静音边界生成有序语音岛，并在读取历史文本或 provider turn 之前冻结每个岛的 start/end、检测器版本和生效参数。历史 `time (s)` MUST 只保留为审计字段，不得参与强约束、边界、排序、tie-break、裁片或自动失败决定。

系统 MUST 以 worksheet/event 顺序为硬约束，将有序历史用户事件与有序语音岛做确定性单调序列匹配；MUST 支持多个相邻历史事件合并到一个语音岛，并为合并 Case 保留全部 source event ID。文本归一化 MUST 保留原文，同时生成至少 Unicode/大小写/标点规范形式、逐位数字序列和数值形式；例如 `223` 与 `two two three` 可通过共同数字序列形成辅助证据。归一化文本、相邻机器人轮次和跨 provider 一致性只可排序已满足事件/语音岛顺序的合法候选，MUST NOT 切分、移动或扩大已冻结的音频边界。

原始语音岛 MUST 作为不可变底层音频证据保留，但语音岛与口语 Turn 不得被假设为一对一。同一个 provider customer turn 跨越的多个岛 MUST 视为同一口语 Turn 的停顿片段，不得仅因其中一个岛未被 Case 使用就生成 `wrong_merge`。只有相邻机器人 turn，或至少两家 provider 都把该岛与已分配岛识别为不同 customer turn 时，系统才可创建 `wrong_merge` 待复核候选；证据不足时保持为同 Turn 片段且不占用人工复核队列。

正式页面每次打开人工复核、从批次进入复核或切换 ASR Case/Turn 异常分栏时 MUST 重新读取当前开放复核数据，再渲染数量与队列；不得继续使用页面首次加载时的旧候选数组冒充当前状态。刷新 MUST 为只读操作，不得重跑批次或调用外部资源。

完整录音 provider turn MUST 按与已冻结 Case 区间的时间重叠投影为候选文本。只有存在唯一且满足冻结证据策略的映射时，系统才可标记 `deterministic_aligned`。事件/语音岛数量不一致、多个合法路径同分、粗粒度 provider turn 横跨多个岛或 provider 证据冲突时，受影响 Case MUST 标记 `ambiguous` 并进入受控 LLM 辅助；不得直接声称成功。

辅助 LLM MUST 使用批次冻结的资源/模型，并且只接收受影响 Case 的真实 event ID、audio-island ID、provider turn ID、原始/归一化文本及必要相邻上下文。模型只能从输入候选 ID 中选择并说明依据，MUST NOT 生成时间戳、新 ID、改变语音岛边界或打破事件顺序。程序 MUST 在使用结果前校验请求/Case 身份、完整候选集合、真实 ID、conversation/provider 归属、单调顺序、冻结边界和跨 provider 证据；结构无效、遗漏、冲突或仍不唯一时，该 Case MUST 进入人工复核。

每个 Case 及其 provider turn 投影 MUST 独立持久化；一个 Case 的歧义或失败 MUST NOT 使同 conversation 的有效 sibling Case 变为音频不可用。生成的纯用户音频 MUST 只用于回听、人工复核和 Benchmark，MUST NOT 再提交给任何评测 ASR。Multi-ASR 任务数、调用费用和 provider 失败数 MUST 只统计完整通话 provider job；本地切片、确定性匹配和派生 Case 证据不得计作外部任务，只有实际触发的歧义 LLM 辅助请求计入 LLM 成本。

#### Scenario: Prepare one target user event

- **WHEN** 第一轮将一个有效用户事件识别为疑点 Case 或额外 Good Case
- **THEN** 系统先冻结对应语音岛边界，再保存确定性或经校验 LLM 辅助选中的 provider turn 文本；不创建事件级 provider 转录任务

#### Scenario: One conversation contains multiple cases

- **WHEN** 同一 conversation ID 包含多个需要第二轮判断的目标用户事件
- **THEN** 系统按语音岛分别生成 Case；多个相邻事件落在同一岛时合并为一个 Case 并保留全部 event ID，不得按历史时间戳或文本强行拆开

#### Scenario: Reuse one full-call ASR context

- **WHEN** 同一 conversation 包含一个或多个目标用户事件
- **THEN** 系统为每家启用的评测 ASR 至多提交一次完整通话录音并跨该 conversation 的所有 Case 复用结果，只在本地为每个 Case 生成纯用户单句切片

#### Scenario: Normalize different written forms without moving audio

- **WHEN** 历史文本为 `223`，某家 ASR turn 为 `two two three`，且二者属于同一合法顺序候选
- **THEN** 系统保留两份原文并生成共同的逐位数字序列用于候选排序；该文本证据不得创建、切分或移动语音岛边界

#### Scenario: Use the LLM only for one ambiguous Case

- **WHEN** 确定性单调匹配和文本归一化后，一个 Case 仍有多个合法 event/island/turn 组合
- **THEN** 系统只把该 Case 的受限候选集合发送给批次冻结的辅助 LLM；其他已唯一对齐 Case 不产生 LLM 请求且不得被重算

#### Scenario: Reject an unverified LLM-assisted mapping

- **WHEN** 辅助 LLM 返回不存在的 ID、时间戳、跨序映射、遗漏候选、修改边界、结构无效或与跨 provider 证据冲突
- **THEN** 系统拒绝该结果并把对应 Case 标记为需人工复核；不得使用模型解释替代确定性校验

#### Scenario: Merge historical turns into one audio Case

- **WHEN** 多个相邻历史用户事件被唯一映射到同一个语音岛
- **THEN** 系统创建一个稳定合并 Case、保留有序 source event ID 列表，并记录一个历史 Turn 标注异常组及其受影响 Turn 行数

#### Scenario: Keep pauses inside one spoken Turn out of anomaly review

- **WHEN** 一个 provider customer turn 跨越多个 RMS 语音岛，且没有相邻机器人 turn 或两家 provider 的独立 customer-turn 边界证明它们是不同发言轮次
- **THEN** 系统保留全部原始语音岛作为音频证据，但把它们视为同一口语 Turn 的停顿片段，不生成 `wrong_merge` 待复核候选

#### Scenario: Detect a real extra spoken Turn

- **WHEN** 一个未分配语音岛与最近 Case 之间存在相邻机器人 turn，或至少两家 provider 均以不同 customer turn ID 覆盖这两个岛
- **THEN** 系统可生成 `wrong_merge` 待复核候选，并同时保存已分配岛、额外岛和支持独立 Turn 的 provider 证据

#### Scenario: Refresh the current Turn review queue

- **GIVEN** 后端已把不再成立的候选标记为 `superseded`
- **WHEN** 用户打开人工复核、从批次进入复核或切换 Turn 异常分栏
- **THEN** 页面重新读取服务端开放候选，只显示当前 `pending`/`deferred` 数量，不继续显示刷新前的旧数量
- **AND** 该操作不改变批次、复核、报告、Benchmark 或费用，也不产生 ASR/LLM 请求

#### Scenario: Persist projected ASR evidence per Case
- **WHEN** 同一 conversation 的一个 Case 已唯一对齐，而 sibling Case 仍歧义或失败
- **THEN** 系统以稳定 Case 事务保存已完成 Case 及其 provider 投影；不得因 sibling 未完成而丢弃或回滚该结果

### Requirement: Six-stage execution visibility

批次详情 MUST 依次展示数据校验、第一轮分析、多 ASR 转写、音频与证据对齐、第二轮分析和人工复核六步。第 4 步 MUST 区分本地确定性对齐数量、歧义 Case 数和辅助 LLM 请求；只有实际触发的辅助请求显示批次冻结的真实 provider/model、请求序号和等待时间，不得固定显示 Qwen。活动请求首帧 MUST 由 `started_at` 计算当前耗时，轮询重绘不得短暂回到 `00:00`。多 ASR 的每一行 MUST 使用该 provider 内部的序号和总数；阶段总进度仍按全部 provider job 汇总。

#### Scenario: Bind evidence only to real provider turns

- **WHEN** 确定性或 LLM 辅助对齐返回目标 Case 与各 provider turn 的映射
- **THEN** 每个映射 MUST 引用请求输入中真实存在且属于对应 conversation/provider 的 turn ID；程序回查真实时间戳，拒绝虚构 ID、越权 ID、事件遗漏/重复、非单调顺序或非用户角色

#### Scenario: Freeze a target Case without historical time

- **WHEN** 系统在纯用户 WAV 上检测到语音岛并将历史事件序列唯一分配到该岛
- **THEN** 语音岛 start/end 成为 Case 冻结边界；修改历史 `time (s)`、provider turn 边界或文本不得改变该区间

#### Scenario: Reject an unreliable user-event clip

- **WHEN** 语音岛为空/无效，或确定性与辅助 LLM 后事件归属仍歧义/不合法
- **THEN** 只把对应 Case 标记为定位失败或需人工复核，不得回退到历史时间、扩大到完整录音、使用单家猜测或影响已完成 sibling Case

#### Scenario: Receive an asynchronous callback twice

- **WHEN** 供应商 webhook 或轮询重复返回同一 job 的完成结果
- **THEN** 系统按 provider job ID 幂等保存一次，不重复触发费用、第二轮分析或 Benchmark 入库

### Requirement: Independent ASR result and partial failure

Soniox `stt-async-v5`、Speechmatics `melia-1` batch/multi 和 ElevenLabs `scribe_v2` webhook 的任务、segments、时间戳、说话人、状态和错误 MUST 独立保存。失败 MUST NOT 被表示为空转写，也不得覆盖已成功资源。

#### Scenario: One evaluation ASR fails

- **WHEN** 线上历史转写和至少一家评测 ASR 成功，但其他资源在自动重试后仍失败
- **THEN** 该 provider 只标记为 `unavailable`；其他 provider 达到 Case 证据门槛时第二轮继续，已成功资源不得重复调用，该局部结果不得使批次显示为失败

#### Scenario: All evaluation ASRs fail

- **WHEN** 某通对话的全部评测 ASR 均无法产生可用结果
- **THEN** 受影响 Case 标记 `excluded_insufficient_evidence`，不生成默认 Good/Bad 结论；其他 Case 继续，计划工作终结后批次仍以“已完成”生成报告并披露排除数和原因

### Requirement: Frozen dataset identity and truthful completion

每个新批次 MUST 永久绑定创建时的 dataset ID、不可变清单、conversation/event 成员和内容指纹。历史批次只在证据唯一时回填；无法证明时 MUST 保留为 `legacy_unbound` 并禁止依赖原数据的再处理，不删除历史结果。

#### Scenario: Replace the active source after a batch starts

- **WHEN** 新数据集被激活，而旧批次被查看、恢复、重试或生成报告
- **THEN** 旧批次只从自己冻结的 dataset version 读取 conversation/event/文件，不得读取当前活动数据集

#### Scenario: Finish with unavailable evidence

- **WHEN** 所有计划任务均达到成功、不可用或排除等可解释终态
- **THEN** 系统生成覆盖报告并将 batch lifecycle 置为 `completed`；只有执行未能走到终点或无法生成报告的系统级故障才能使用 `failed`

### Requirement: Versioned retry plan and uncertain usage

任何付费重试前 MUST 从当前 canonical workset 生成只读、版本化的 retry plan，列出可重试项、跳过项/原因、未知用量、预计费用上限和停止条件。空计划不得启动执行器。已发送但超时的 LLM 请求 MUST 持久化为 `usage_unknown` 并按预留估算继续占用硬预算，直到可核销证据出现。

#### Scenario: Retry exhausted Event Alignment work

- **WHEN** 历史 Event Alignment timeout 已耗尽旧尝试次数，但按当前分类仍属于可恢复工作
- **THEN** retry plan 为其创建新的有界 retry lineage 并按当前拆分策略执行；旧失败只作审计，不得因旧 attempts 为空循环或决定终态

#### Scenario: Time out after provider dispatch

- **WHEN** LLM 请求已发送但客户端在用量返回前超时
- **THEN** 保留该 reservation，标记 `usage_unknown`，将估算金额纳入后续预算门禁；不得当作“未调用/未花费”直接释放

#### Scenario: Report preserves mapped full-call ASR evidence

- **WHEN** 某个 Case 至少一家评测 ASR 已成功，无论第二轮是否为每家结果生成引用片段
- **THEN** 报告 Case 明细均直接展示每家已落库的目标 turn 文本；第二轮引用只能缩小或补充证据定位，不得决定原始 ASR 候选是否可见

#### Scenario: Inspect a safe ASR failure diagnostic

- **WHEN** 完整录音 ASR 在自动重试后失败，或 Case 映射/裁片失败，且批次存在可查看的部分结果
- **THEN** 现有批次错误区、部分结果提示或 provider 单元格显示 provider、任务范围、尝试次数、是否可重试、受控分类和可操作原因；不得显示供应商原始响应、客户文本、源文件路径或凭证

### Requirement: Evidence-based second-pass decision

第二轮 LLM MUST 将历史转写和每家评测 ASR 都视为证据而非真值，并结合完整对话、语义、实体、数字、否定、语种、说话人和事件边界，为每个被评估用户事件输出 `Good Case`、`Bad Case` 或 `需人工复核`。

第二轮 MUST 启用所选模型的 Thinking 能力，并使用与第一轮相同的 128K 运行包络和最终消息预检。可见结构化 JSON MUST 先按 Case 数量在生成上限内预留，Thinking MUST 只使用剩余额度；二者合计不得超过所选模型与公共 32K 上限中的较小者。每个 Case MUST 保留所属 conversation 的完整历史文本、音频与证据对齐阶段投影出的目标 provider turn 文本、全部 source event ID 和必要配置证据；完整录音 ASR 上下文 MUST 只包含同一 provider 中紧邻目标 turn 的前一条和后一条 turn（存在时），不得重复目标候选或把无关的完整录音 turns 投影到请求中。系统 MUST 先按 conversation 装箱；单通仍超过 64K 输入硬上限时，MUST 在发送前按稳定 Case 子集拆组并为各子组重复必要的完整历史，不得截断历史文本。单个 Case 经限定证据后仍超过输入或生成上限时 MUST 在外部调用前以专用 preflight 分类明确失败。系统 MUST 分别记录唯一 Case 数和外部请求组数，失败重试不得导致 Case 漏失、重复判断或重复计费。

每个请求组 MUST 携带稳定 `request_group_id`。第二轮结构化输出 MUST 原样返回该 ID，并以顶层 `results[]` 为组内每个输入 Case 恰好返回一个结果；每个结果 MUST 包含匹配的 conversation/issue/event ID 和 `positioning_quality`。组 ID 不匹配、Case 遗漏、重复或越界 MUST 使整个组失败并按相同冻结成员重试，不得保存部分结论。

#### Scenario: Dynamic packing grows with the batch

- **WHEN** 一个批次的完整第二轮输入无法在预留 Thinking 和结构化输出空间后放入一个请求
- **THEN** 系统先按完整对话形成最少安全分组；单通超限时再按稳定 Case 子集预拆，同时在每个子组保留完整历史，并保持每个唯一 Case 恰好出现一次

#### Scenario: Share one generation budget across supported providers

- **WHEN** Gemini、DeepSeek、Qwen、GPT/Azure 或 OpenRouter 的 Pass 2 请求包含至少一个 Case
- **THEN** 规划器先预留该组可见 JSON，再把剩余生成额度分配给 Thinking，二者之和不得超过冻结模型的生效上限；不得因固定 reasoning reserve 与 JSON reserve 相加而拒绝所有非空请求

#### Scenario: Send one canonical evidence projection

- **WHEN** 系统完成任一 Pass 1 或 Pass 2 请求组的变量渲染
- **THEN** 最终 System Prompt 包含且仅包含一份业务证据，User message 只含固定执行指令；预检统计完整最终消息和协议结构开销，不得只统计去重前的逻辑单元或把同一 payload 再发送一次

#### Scenario: Reject one oversized second-pass case before dispatch

- **WHEN** 一个 Case 在保留完整历史、音频与证据对齐阶段的目标 turn 候选和直接相邻 turns 后仍超过最终输入硬上限
- **THEN** 系统在供应商调用前记录明确尺寸失败，不得截断证据、扩大输出上限或通过付费递归请求发现该失败

#### Scenario: Reject a mismatched grouped response

- **WHEN** 第二轮返回错误的 `request_group_id`，或 `results[]` 遗漏、重复、增加了任一 Case
- **THEN** 系统拒绝整组响应且不保存部分决定，并使用原组成员和幂等键进入可审计重试

#### Scenario: Qwen Thinking returns structured JSON

- **WHEN** 第二轮选择 Qwen 且必须启用 Thinking
- **THEN** 对已验证支持 Thinking + JSON Object 的 `qwen3.8-*`，系统 MUST 同时启用 JSON Object、冻结 Prompt、JSON 解析与完整 Schema 校验
- **AND** 对尚未验证该组合能力的旧 Qwen 型号，系统 MUST 保守省略 JSON Mode，并继续依赖冻结 Prompt、JSON 解析与完整 Schema 校验；任一格式或契约失败仍按同一冻结请求组重试

#### Scenario: Second-pass groups remain failed

- **WHEN** 任一第二轮请求组在自动重试后仍失败
- **THEN** 批次保持可重试的部分失败状态，不得冻结或展示为正常完成的初步/最终报告；已成功的 Pass 1、映射的完整录音目标 turn Case 证据和第二轮分组结果继续独立保存且不得被空值覆盖，页面提供明确标记为“部分结果、非完整报告”的只读入口

#### Scenario: Inspect successful work after a batch failure

- **WHEN** 批次在任一阶段进入失败或部分失败，且至少一个检查点已经成功持久化
- **THEN** 部分结果页按实际完成阶段展示成功 Pass 1 数量与候选、每家映射的完整录音目标 turn Case 证据、已完成第二轮结论、成本台账、失败阶段和可操作错误；尚未执行的区域显示“未运行”而不是空结果，且重试后继续复用既有成功检查点

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

系统 MUST 使用纯用户 WAV 上已冻结的 Case 语音岛作为统一回听区间。正式 ASR 候选的 turn ID 和时间戳来自完整录音的确定性或经校验 LLM 辅助投影，仅作为默认折叠的技术证据；人工播放器和 Benchmark 剪辑 MUST 使用同一 Case 音频切片，不得增加会跨入相邻语音岛的上下文余量。

#### Scenario: Vendor segment boundaries differ

- **WHEN** 多家完整录音 ASR 对同一目标事件返回不同的 turn 边界
- **THEN** 系统保留各家映射 turn 的候选文本和时间证据，但所有 provider 共用同一纯用户源切片回听，不再次提交该切片转写

#### Scenario: Precise alignment is unavailable

- **WHEN** 系统无法可靠定位到句子级时间范围
- **THEN** 对应 Case 明确标记为定位失败且不生成事件级回听或 Benchmark 切片，不得回退到更宽区间、完整录音或 Excel 时间

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

#### Scenario: Finish a paused or partially failed batch with current results

- **WHEN** 负责人对已有初步报告的 `paused` 或 `partially_failed` 批次二次确认“使用现有结果结束”
- **THEN** 系统 MUST 保留已完成 Pass 2 结论、已提交人工复核、现有 Benchmark、费用和检查点，排除待复核、未完成、失败或无法可靠裁片的 Case，事务性冻结不可变 `final_partial` 报告并将批次设为 `completed_partial` 和 100%
- **AND** 该操作 MUST NOT 恢复执行器、重试失败资源、调用 ASR/LLM、删除成功结果或把被排除 Case 写入 Benchmark/正式结论；运行中批次 MUST 先暂停

### Requirement: Evaluation metrics

系统 MUST 使用以下稳定口径并同时展示分子、分母、排除数量和原因：

- 疑似错误用户句子占比 = 第二轮 `Bad Case + 需人工复核` 数量 ÷ 成功完成第一轮分析的有效用户句子总数；
- 人工确认错误占比 = 人工复核判为 Bad 的数量 ÷ 同一批次有效用户句子总数；
- 复核完成率 = 已提交 Good、Bad 或听不清的人工任务数 ÷ 应人工复核任务总数。
- 历史 Turn 标注错误组数 = 人工明确确认的稳定异常组数量；
- 受影响历史 Turn 行数 = 已确认异常组覆盖的去重 source event/Turn 行数量；
- 历史 Turn 复核覆盖率 = 已确认或已驳回的异常组数量 ÷ 系统发现的全部待复核异常组数量。

历史 Turn 指标 MUST 作为独立数据质量信息展示，不得进入疑似 ASR 错误率或人工确认错误率的分子/分母。每个候选异常组 MUST 保留 conversation、全部 source event ID、建议对应 Case、错误类型和可回听音频证据，并进入独立的 Turn 异常人工复核。只有明确选择“确认 Turn 异常”的组可进入异常组数和受影响 Turn 行数；“不是 Turn 异常”不计数，未提交或暂无法判断保持待复核并单独披露。系统 MUST NOT 回写源工作簿，也 MUST NOT 因 Turn 复核直接创建 Benchmark。

#### Scenario: Review a historical Turn anomaly group

- **WHEN** 用户从人工复核区域打开一个系统发现的历史 Turn 异常组
- **THEN** 页面展示完整 conversation ID、全部 source Turn、建议 Case 映射、每个冻结语音岛的音频、历史顺序/文本及 provider 证据，并要求明确选择“确认 Turn 异常”或“不是 Turn 异常”

#### Scenario: Confirm a historical Turn anomaly

- **WHEN** 复核人员确认该组确实存在过度切分、错误合并或顺序异常
- **THEN** 系统保存不可变复核记录，将该组及去重 Turn 行计入报告指标，但不修改源工作簿或创建 Benchmark

#### Scenario: Reject or defer a historical Turn anomaly

- **WHEN** 复核人员选择“不是 Turn 异常”或暂不提交
- **THEN** 驳回组不进入异常指标；未提交组保持待复核，报告单独展示待复核数与覆盖率，不得把候选当作确定结论

#### Scenario: Calculate a fixed 20/6/4 formula fixture

- **WHEN** 自动化测试使用固定 mock 输入：20 个 Bad、6 个 Good、4 个需人工复核和 441 个有效用户句子
- **THEN** 疑似错误分子为 24 而不是 30，页面显示 `24 / 441`、百分比和被排除事件明细

#### Scenario: Count one merged historical-turn issue

- **WHEN** 一个语音岛对应 3 个相邻历史 Turn 并合并为一个 Case
- **THEN** 系统先生成 `1 组 / 3 行 Turn` 的待复核候选；只有人工确认后报告才将其计为 `1 个已确认异常组 / 3 行 Turn`，且不改变任何 ASR 错误率

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

#### Scenario: Preserve historical-turn metrics across report states

- **WHEN** 页面生成初步报告、最终报告、部分最终报告或部分结果投影
- **THEN** 所有状态使用同一冻结口径展示已确认历史 Turn 异常组数、受影响 Turn 行数、Turn 复核覆盖率和 group-first 明细；待复核候选必须单独披露，已冻结报告不得被后续重算覆盖

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

所有外部调用 MUST 显式配置按阶段和厂商区分的超时、限流、有界重试/拆分策略和幂等标识。批次 MUST 保存阶段检查点；预算达到批次硬上限时 MUST 停止创建新的外部调用，但保留已完成结果并允许调整后恢复。

#### Scenario: Budget limit is reached

- **WHEN** 已核算费用达到批次预算上限
- **THEN** 批次进入已暂停，停止新建 ASR/LLM 任务，展示已花费、上限和待处理数量，并可从检查点恢复

#### Scenario: Retry a failed provider

- **WHEN** 用户对部分失败批次执行定向重试
- **THEN** 系统只为失败且可重试的 provider/conversation job 创建新尝试，复用成功结果且不重复生成 Case 或 Benchmark

#### Scenario: Execute Qwen with stage-specific reasoning and timeout

- **WHEN** 批次选择原生 Qwen3.8 执行第一轮或第二轮分析
- **THEN** 第一轮 MUST 关闭 Thinking 并使用 180 秒请求超时；第二轮 MUST 显式使用 `reasoning_effort=medium` 并使用 300 秒请求超时

#### Scenario: Reserve the corrective instruction before Pass 1 dispatch

- **WHEN** 系统为第一轮请求组执行最终输入装箱
- **THEN** 预检 MUST 预留最长纠正指令，保证首次请求成功进入发送队列后，不会仅因附加纠正指令而在重试时确定性超过 64K 输入上限

#### Scenario: Split a failed Pass 1 request group

- **WHEN** 第一轮请求组超时或返回结构失败
- **THEN** 系统 MUST 将父组标记为已被子组取代，按完整 conversation 边界确定性拆分并仅派发未完成 conversation；单 conversation 叶子最多再尝试一次

#### Scenario: Split a failed Pass 2 request group

- **WHEN** 已通过最终消息硬上限预检的第二轮请求组超时、返回无效 JSON 或引用不存在的 Segment ID
- **THEN** 系统 MUST 保留成功 Case 检查点，将父组标记为已被子组取代，按完整 Case 边界确定性拆分并仅派发未完成 Case；单 Case 叶子最多再尝试一次，已完成 Case 不得重复提交

#### Scenario: Ignore superseded Pass 2 failures at terminal reconciliation

- **WHEN** 当前 canonical Case 集合均已完成，但历史请求组或已被新 Case 映射替代的旧检查点仍保留失败状态
- **THEN** 系统按当前 canonical Case 集合的最新检查点进入报告或人工复核阶段；历史失败只保留为诊断，不得把批次重新判为 `partially_failed` 或再次派发

#### Scenario: Reuse a historical Pass 2 group by idempotency key

- **WHEN** 对齐恢复改变了 retry ordinal 或派生 group ID，但新计划的精确 Case membership 与输入快照产生已存在的 `(batch_id, idempotency_key)`
- **THEN** 系统复用该 key 对应的 canonical persisted group ID 和成功/失败检查点，不得插入冲突行或重复派发；只有同 key membership 漂移才记录确定性冲突并停止发送

#### Scenario: Report truthful retry progress

- **WHEN** 批次处于首次执行或失败重试
- **THEN** 页面分别展示 Case 和外部请求组的成功、失败、处理中及尝试次数；失败不得计入成功进度，后续子批次不得用局部总数覆盖全阶段总数

#### Scenario: Preserve progress after a guarded planning failure

- **WHEN** 批次在已有阶段检查点和费用后发生发送前输入或输出规划失败
- **THEN** 批次进入可重试的部分失败并保留最后有意义的阶段、进度、检查点和费用；不得把进度归零或把本地 preflight 失败标记为供应商无效 JSON

#### Scenario: Defer Good balancing until suspect completion

- **WHEN** 任一疑点 Case 的第二轮结果仍为失败或处理中
- **THEN** 系统不得创建新的额外 Good 平衡样本；疑点 Case 总数在重试期间保持稳定，并将既有或后续 Good 控制样本与疑点数分开统计

### Requirement: Live external-request visibility

运行中的评测 MUST 在进度区域逐条展示当前正在等待的外部请求及其已等待时长；服务端 MUST 提供脱敏的阶段、厂商、当前序号、总数、开始时间和最近心跳。前端 MUST 每秒刷新可见计时，但不得以本地计时伪造完成百分比，也不得让辅助技术每秒播报。暂停或部分失败的历史批次 MUST 只显示该阶段的成功数与失败数，技术尝试和请求组细节保留在任务详情。

#### Scenario: Show every active request separately

- **WHEN** 一个批次同时有多个 ASR 或 LLM 请求正在等待厂商返回
- **THEN** 进度区域为每个请求显示一行“厂商/阶段 · 当前序号/总数 · 已等待 mm:ss”，计时每秒变化；请求完成后该行消失或被下一项替换

#### Scenario: Keep durable progress authoritative

- **WHEN** 前端仅因本地计时器经过一秒而更新活动请求时长
- **THEN** Case、conversation、provider job 和 request group 的完成百分比及成功/失败数量保持由服务端检查点决定，不随本地计时增加

#### Scenario: Detect a stale operation heartbeat

- **WHEN** 活动请求的最近心跳超过服务端定义的健康窗口
- **THEN** 页面 MUST 显示“状态同步中断”而不是继续把它呈现为正常等待

#### Scenario: Summarize a non-running batch compactly

- **WHEN** 批次处于暂停或部分失败
- **THEN** 列表状态只显示 `N failed · M succeeded`；第一轮按 conversation、ASR 按完整通话 provider job、第二轮按 Case 计数，不显示 pending、request group 或 attempt 长串

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
