# Decision Log

仅记录有可追溯用户确认的决定。来源统一为当前 Codex 任务 `codex://threads/01a0a4bf-81a0-74e3-84ac-159a97f0640c`；消息 ID 可读取时直接记录，不可读取的早期 Browser Comment 用页面、评论和确认原话定位，不以 Agent 推断代替确认。

## Status

- Recorded decisions: 74 confirmed, 3 superseded, 1 invalidated
- Open product decisions: 0
- Engineering Checkpoint C: PASS for PD-064/PD-065 independent re-review; User Gate 2 remains product-owner acceptance
- Last reviewed: 2026-09-23

## Decisions

### PD-078 — 发布 Pass 2、Turn 异常与复核双语修复到生产

- Status: Confirmed
- Date: 2026-09-23
- Source question: KI-200–KI-204 修复完成并独立验收通过后，是否提交到 `main` 并触发生产发布
- Decision owner: Product owner
- Source thread/message: 当前 Codex 任务；Agent 披露本地验证通过、生产尚未生效并请求发布授权
- Confirmation quote: “发布到生产”
- Decision: 只提交并发布本轮已独立验收的 Pass 2 canonical 终态、历史 Turn wrong-merge 证据门槛/状态保留及 Manual Review 双语修复和对应规格/测试/验收记录。推送到 `git@github.com:jasonchao75/VoiceAgent.git` 的 `main`，触发既有生产工作流并验证 CI、部署、公开健康与部署 SHA。
- Reason: 产品负责人要求上述已验证修复在线上生效。
- Consequences: 发布保留现有生产 Evaluation 数据，不清空历史、不自动重试 `EV-20260923-E65A`、不发起 ASR/LLM 付费调用。用户后续手动重试才会使用新规则。
- Updated artifacts: `decision-log.md`、`tasks.md`、`verification/delivery-status.json`、发布提交与 CI/CD 证据。
- Verification: 发布前全量测试、双视口 UI、构建、Change gate 与独立验收均 PASS；发布后需核对远端提交、CI/CD、生产健康、实际部署 SHA 与 E65A 未被自动操作。

### PD-077 — 修复 Pass 2 历史失败误判与 Turn 异常过量候选

- Status: Confirmed
- Date: 2026-09-23
- Source question: 生产重试成功替换旧 Pass 2 失败后批次仍被判为 `partially_failed`，且历史 Turn 异常队列因未分配语音岛过量膨胀
- Decision owner: Product owner
- Source thread/message: 当前 Codex 任务；产品负责人要求先验证两项发现，成立后直接修复
- Confirmation quote: “你先验证一下你的发现对不对。如果对，那就修复一下这两个问题：错误判定Partially——failed问题和Turn异常的问题”
- Decision: Pass 2 的终态只按本轮当前 canonical Case 集合及其最新检查点判定；已被新分组替代的历史失败组、已不属于当前 Case 集合的旧失败行只保留诊断，不得继续迫使批次进入 `partially_failed`。历史 Turn 的 `wrong_merge` 候选不得由“存在未分配语音岛”直接推导；原始语音岛继续作为不可变底层音频证据，但同一个 provider customer turn 跨越的多个岛视为同一口语 Turn 的停顿片段。只有相邻机器人 turn 或至少两家 provider 的独立 customer-turn 边界支持该岛为另一轮发言时，才创建 `wrong_merge` 人工复核候选。
- Reason: 生产 E65A 证明替代组已连续成功，但旧失败行仍参与终态统计；同批 137 个 Turn 异常中 119 个 `wrong_merge` 来自“所有 orphan island 均报错”的实现捷径，不能证明历史标注真的错误。
- Consequences: 修复不得删除原始失败/语音岛证据；Pass 2 仍对当前未完成 Case 如实部分失败。Turn 异常队列需在重新对齐时移除尚未人工确认且不再满足证据门槛的旧候选，已确认/已驳回记录保持不可变。不得触发新的外部付费调用。
- Updated artifacts: Delta Spec、`design.md`、`tasks.md`、执行器、Turn 异常持久化与回归测试。
- Verification: 使用 E65A 派生的确定性反例验证旧实现可复现两项误判；修复后需通过定向/全量测试、Change gate 和独立验收。

### PD-076 — 确认并冻结 V1.20 规格与原型基线

- Status: Confirmed
- Date: 2026-09-23
- Source question: 产品负责人查看已定位到“人工复核 → Turn 异常复核”的更新原型后，是否确认该流程与 V1.20 候选基线
- Decision owner: Product owner
- Source thread/message: 当前 Codex 任务；Agent 明确请求“请查看当前新打开的页面并确认流程”后，产品负责人回复确认
- Confirmation quote: “可以。”
- Decision: 确认 V1.20 的 audio-first 音频与证据对齐、仅歧义 Case 使用受控 LLM、历史 Turn 异常分组复核、报告双指标与覆盖率、Pass 2 历史幂等修复、Benchmark 全库去重及冲突候选直接丢弃等已记录行为；确认 `prototypes/index.html` 为新的唯一视觉基线。User Gate 1 通过，正式实现可在后续明确开发指令下开始。
- Reason: 产品负责人已完成逐项方案确认，并在直接打开更新后的 Turn 异常复核页面后确认该流程可用。
- Consequences: V1.19 降为历史基线，V1.20 的 SHA-256 成为本 Change 唯一当前冻结校验值；正式 UI 必须复用生产路由、组件和 DOM，并依次完成 Engineering Checkpoint A/B/C。此次确认不等于授权生产重试、付费调用、部署或 User Gate 2 最终验收。
- Updated artifacts: `decision-log.md`、`proposal.md`、`tasks.md`、`prototypes/README.md`、UI 注释/状态矩阵、Gate 1 记录、UI checklist 与 `verification/delivery-status.json`。
- Verification: User Gate 1 已完成；正式代码、迁移、持久化、双视口回归、独立验收和生产行为仍未实现或验证。

### PD-075 — 跨批次 Benchmark 冲突直接丢弃新结果

- Status: Confirmed
- Date: 2026-09-23
- Source question: Q-020；同一 conversation/event 已有正式 Benchmark，但后续批次产生不同 Good/Bad、标注文本或音频证据时如何处理
- Decision owner: Product owner
- Source thread/message: 当前 Codex 任务；产品负责人通过 Response Annotation 明确否决人工冲突复核和自动修订
- Confirmation quote: “不同批次结果冲突时，不新增、不自动覆盖，直接放弃新生成的那个”
- Decision: 当正式 Benchmark Library 已存在同一 `(conversation_id, event_id)` 样本，而后续批次生成的 Good/Bad、最终标注文本或音频证据与当前样本冲突时，系统直接丢弃新生成的 Benchmark 候选：不得新增样本、不得覆盖当前值、不得追加修订，也不得创建人工冲突复核任务。现有 Benchmark 及其既有追溯保持不变，新批次的 Benchmark 新增数不得包含该候选。
- Reason: 同一原始事件只保留一个正式 Benchmark；后续批次的冲突输出不应改变既有真值，也不值得引入额外人工处理流程。
- Consequences: Q-020 关闭。全局唯一键在写入前拦截冲突候选；相同结果仍幂等返回原 Benchmark ID，冲突结果返回明确的“重复冲突已放弃”处理状态但不保存其标注或音频为正式样本/修订。实现与回归必须证明跨批次冲突不会改变样本数、当前值、修订历史、导出内容或创建复核任务。
- Updated artifacts: `open-questions.md`、`decision-log.md`、Benchmark Delta Spec、`design.md`、`tasks.md`、原型说明、Gate 1 材料与 `verification/delivery-status.json`。
- Verification: 产品规则已确认并写入规格；全局唯一迁移、冲突丢弃路径和历史重复数据处理尚未实现或验证。

### PD-074 — 历史 Turn 异常必须人工复核后进入报告结论

- Status: Confirmed
- Date: 2026-09-23
- Source question: 原型中的历史 Turn 标注异常是否需要人工审核，以及复核入口如何呈现
- Decision owner: Product owner
- Source thread/message: 当前 Codex 任务；产品负责人先询问复核要求，随后明确要求补画复核入口指导开发
- Confirmation quote: “这个Turn异常需要复核的，你最好也画一个出来。方便指导后续开发，也能和我对齐”
- Decision: Audio-first 流程发现的历史 Turn 异常先作为待复核候选进入现有“人工复核”产品区域，但必须与 ASR Good/Bad 音频复核分栏展示。复核任务按异常组处理，展示 conversation、全部 source Turn、系统建议的 Case 映射、语音岛音频、历史文本顺序和 provider 证据。复核人员明确选择“确认 Turn 异常”或“不是 Turn 异常”；未提交或暂无法判断时保持待复核。只有人工确认的异常组和受影响 Turn 行进入报告的确定结论，驳回项不计数，待复核项单独披露覆盖率。复核不得回写源工作簿，也不得直接创建 Benchmark。
- Reason: 音频与证据对齐可以高召回发现历史切分、合并或顺序问题，但这些属于源数据质量结论，必须由人工试听并核对证据后确认，不能由系统自动定性。
- Consequences: V1.20 候选需增加 ASR Case / Turn 异常两个复核入口、Turn 异常组队列、证据区和确认/驳回动作；报告显示已确认组数、受影响 Turn 行数和 Turn 复核覆盖率。Delta Spec、设计、任务、状态矩阵与 UI checklist 同步，续订 User Gate 1 后才进入正式实现。
- Updated artifacts: `decision-log.md`、`proposal.md`、Delta Spec、`design.md`、`tasks.md`、V1.20 候选原型和 UI 验收材料。
- Verification: 仅完成规格与原型候选；正式页面、持久化、报告计算、权限与回归测试尚未实现或验证。

### PD-073 — Benchmark 以 conversation ID + event ID 全库去重

- Status: Confirmed
- Date: 2026-09-23
- Source question: Benchmark 是否已经按 conversation ID + event ID 去重
- Decision owner: Product owner
- Source thread/message: 当前 Codex 任务；产品负责人发现现有唯一键可能允许跨批次重复入库
- Confirmation quote: “Benchmark你存的时候，对话ID+事件相同的，你不能存啊，现在是不是没去重？”
- Decision: 正式 Benchmark Library 中，同一 `(conversation_id, event_id)` 全库只能对应一个 Benchmark 样本，批次 ID 不得参与决定样本是否重复。重试、恢复、重复 webhook、人工复核和后续批次再次命中该事件时都不得创建第二条样本。
- Reason: 同一原始对话事件代表同一个评测对象；批次只是发现和证据来源，不应把同一对象复制成多个 Benchmark 样本并污染数量、比例和导出。
- Consequences: 数据库需增加全局唯一约束并迁移既有数据；自动和人工入库都必须先按 conversation/event 查找已有样本。完全相同的重复结果幂等返回原 Benchmark ID；不同结果按 PD-075 直接丢弃新候选，不新增、不覆盖、不修订且不进入人工冲突复核。
- Updated artifacts: `decisions/open-questions.md`、`decision-log.md`、Benchmark Delta Spec、`design.md`、`tasks.md`、`verification/delivery-status.json`。
- Verification: 代码审阅确认现有约束是 `(batch_id, conversation_id, event_id)`，因此只保证批次内去重；全局去重、历史数据迁移和冲突路径尚未实现或验证。

### PD-072 — Audio-first 确定性对齐，歧义 Case 才使用 LLM 辅助

- Status: Confirmed
- Date: 2026-09-23
- Source question: Q-019；历史时间戳不可信时，是否完全移除 LLM Event Aligner，还是只在 ASR Turn 与历史事件无法唯一对应时保留受控辅助
- Decision owner: Product owner
- Source thread/message: 当前 Codex 任务；产品负责人逐项挑战时间重叠假设、确认 LLM 仅用于歧义 Case，并最终确认完整七项范围
- Confirmation quote: “那你是不是要在发现ASR Turn和历史文本记录的case对不上的时候，用LLM辅助来判断下？”；“采用方案 C，并按以上 7 项更新规格和原型”
- Decision: 批次第 4 步改为“音频与证据对齐”。系统先从 `user_record` 生成并冻结语音岛，以 worksheet/event 顺序为硬约束执行确定性单调序列匹配；历史时间戳不参与强约束。数字、拼写、大小写和标点归一化生成原文、数字序列和数值等可比较形式，例如 `223` 与 `two two three` 可通过 `2|2|3` 形成辅助证据。相邻机器人轮次和多 provider 文本一致性只用于在不改变音频边界的合法候选之间排序。只有仍无法唯一绑定历史 event、语音岛与 provider turn 的歧义 Case，才使用批次冻结的辅助 LLM；该 LLM 只能从输入中真实存在的 event ID、audio-island ID 和 provider turn ID 中选择并说明依据，不能生成时间戳、新 ID、改变音频边界或打破顺序。输出必须继续通过确定性的 ID、单调性、音频边界和跨 provider 证据校验；仍冲突、遗漏或结构无效则进入人工复核，不得伪装为成功。
- Reason: 纯时间重叠无法把不可信历史时间戳绑定到真实音频；完全移除语义辅助会让数字表达差异、粗粒度 provider turn 和事件/语音岛数量不一致的 Case 大量进入人工。受控方案 C 保留 audio-first 真相源，同时只让 LLM 处理确定性规则无法唯一裁决的小范围歧义。
- Consequences: 旧的“所有目标 conversation 批量调用 LLM Event Aligner”被替换；常规对齐不产生 LLM 请求，只有歧义 Case 产生受预算、幂等、超时和结构校验约束的辅助请求。第 4 步保留六阶段位置但改名；活动行必须区分本地确定性对齐与正在等待的辅助 LLM。历史失败 Align checkpoint 只保留诊断，不得直接重放；按新流程重建后仍歧义时才允许新的受控请求。Pass 2 历史组必须按幂等键和精确成员复用。报告单列历史 Turn 标注异常组数和受影响 Turn 行数。
- Updated artifacts: `decisions/open-questions.md`、`decision-log.md`、`proposal.md`、Delta Specs、`design.md`、`tasks.md`、V1.20 候选原型与 UI 验收材料。
- Verification: 本决定仅冻结产品范围；正式实现、确定性覆盖率、LLM 触发率、成本、生产恢复和 E65A 重试均尚未验证。User Gate 1 仍需产品负责人查看并确认 V1.20 候选原型。

### PD-070 — Case 音频边界以纯用户音轨为主，文本只作辅助证据

- Status: Confirmed
- Date: 2026-09-23
- Source question: `1030000000070676` 的 R28/R30 为什么在切分后显示音频不可用，以及事件边界应以文本映射还是音频信号为准
- Decision owner: Product owner
- Source thread/message: 当前 Codex 任务；产品负责人纠正单 Case 恢复思路并要求通盘调整定位标准
- Confirmation quote: “应该以音频切分的标准为主来判断，不应该以文本来为标准，文本现在切错的概率比语音高，语音反而很少切错。你不能只恢复一个case，要通盘考虑，是哪里有问题”；“我理解如果一个语音岛对应多个事件，那么需要把多个事件合并。”；“历史对话记录的时间戳不准，你要记得这件事”
- Decision: Case 音频定位与切分必须以 `user_record` 的实际语音活动、静音边界和事件顺序为主。历史对话记录的时间戳明确属于不可信数据，只能作为可丢弃的宽松提示，不能作为 Case 边界、事件归属或失败判定依据；历史事件首先按工作簿/事件序列做单调分配。完整录音 ASR 时间戳来自实际录音时间轴，可用于把 provider turn 投影到已经冻结的语音岛，但它仍只是证据，不能移动音频边界；文本语义同样只能用于质量判断。不得先用历史时间戳或文本/LLM turn 映射决定音频边界，再让波形只能被动验证或扩张。当一个语音岛对应多个相邻事件时，将这些事件合并为一个 Case，并保留全部原始 event ID 供展示、审计和结果追溯；不得再按文本强行切开。有效定位结果必须按 Case 独立持久化；同一 conversation 的其他 Case 失败不得使已可靠定位的 Case 变为音频不可用。
- Reason: 线上 `1030000000070676` 的纯用户 WAV 在不读取文本时清楚呈现 133.60–136.70 秒与 137.36–137.72 秒两个语音岛，而现有 ASR-turn 并集把 R28 裁成 133.42–137.97 秒并吞入 R30；文本映射与整通原子落库共同制造了错误边界和级联不可用。
- Consequences: 事件定位流程需改为 audio-first：先从纯用户音轨生成稳定语音岛，再以历史事件序列做单调分配；历史时间戳不得参与强约束、不得否决顺序映射。随后才按实际录音时间轴的重叠关系投影各 provider 完整通话 turn 文本。文本和 provider 时间戳不得移动已确认的音频边界。多事件命中同一语音岛时生成一个可追溯的合并 Case；其他仍无法唯一分配的范围只隔离受影响事件，并保留同通其他 Case。具体合并 Case 标识、最小时长、间隔阈值和旧检查点迁移必须在实现前补入 Delta Spec、design、tasks 与回归矩阵。
- Updated artifacts: `decisions/decision-log.md`、`verification/delivery-status.json`；实现材料待方案细化与 User Gate 1 修订后更新。
- Verification: 只读生产波形检查验证 8 kHz 单声道 `user_record` 在 132–141 秒窗口内存在 133.60–136.70 秒与 137.36–137.72 秒两个独立活动区间；当前代码仍为 text/turn-first，尚未实现本决定。

### PD-071 — 评测报告单列历史 Turn 标注错误

- Status: Confirmed
- Date: 2026-09-23
- Source question: Audio-first 合并事件后，历史 Turn 标注错误是否只作为内部 Align 错误，还是进入评测报告
- Decision owner: Product owner
- Source thread/message: 当前 Codex 任务；产品负责人通过 Response Annotation 明确要求作为独立报告信息
- Confirmation quote: “另外，要单独标记出来，有几个turn被标记错了。”；“在评测报告页面上，你要单独列出来，有几个turn被历史标记错了。这也是有价值的信息”；“使用A和C的组合，组数+Turn行数都要有”
- Decision: 初步报告、最终报告、部分最终报告和部分结果页都必须单独展示历史 Turn 标注错误指标，不得把它混入 ASR Bad Case、人工确认错误率或普通 Align 技术错误。报告汇总同时展示异常组数与受影响历史 Turn 行数；一个语音岛对应 3 个历史事件时记为 `1 组 / 3 Turn`。详情按异常组展开到受影响 conversation、原始 event ID、audio-first 合并 Case、错误类型和可回听音频证据。历史标注事实保持不可变，系统只记录评测发现，不回写源工作簿。
- Reason: 历史 Turn 的过度拆分、错误合并或顺序标注问题本身是评测数据质量结论，能解释 ASR/Align 异常并支持后续数据治理。
- Consequences: 报告 Schema 必须分别冻结 `historical_turn_error_group_count` 与 `affected_historical_turn_count`，详情组保留稳定 group ID 和完整 source event ID 集合；两者不得互相替代，也不得改变现有疑似 ASR 错误率分子/分母。Delta Spec、设计、正式原型、状态矩阵、导出与回归测试必须同步，并重新执行 User Gate 1。
- Updated artifacts: `decisions/open-questions.md`、`decisions/decision-log.md`、`verification/delivery-status.json`；其余实现材料在 audio-first Event Alignment 职责确认后同步。
- Verification: 需求已确认，统计口径、原型和实现尚未冻结或验证。

### PD-066 — 冻结 V1.18 并在独立验收后发布

- Status: Confirmed
- Date: 2026-09-22
- Source question: V1.18 逐请求计时与非运行状态精简摘要原型是否作为新的唯一 UI baseline，并继续实现上线
- Decision owner: Product owner
- Source thread/message: 当前 Codex 任务；产品负责人查看原型后的明确回复
- Confirmation quote: “确认，实现并上线吧”
- Decision: 将 `prototypes/index.html` V1.18 冻结为本 Change 唯一当前 UI baseline。按 PD-064/PD-065 完成生产后端、正式页面和回归测试；通过 Engineering Checkpoint A/B/C、Change 门禁和独立验收后，提交并发布到现有生产流程。发布必须保留线上 Evaluation 数据，不自动重试、恢复或改写 `EV-20260923-E65A`，也不由 Agent 发起新的付费 ASR/LLM 调用。
- Reason: 产品负责人已确认行为方案和高保真原型，并明确授权实现与上线。
- Consequences: V1.17 降为历史基线；V1.18 的完整 SHA-256 成为唯一冻结校验值。正式 UI 必须复用现有生产路由和 DOM，不另造静态验收页。发布完成后仍由用户决定是否重试历史失败批次。
- Updated artifacts: `prototypes/README.md`、`verification/gate-1-review.md`、proposal/design/spec/tasks、正式实现、测试、独立验收与发布证据。
- Verification: Implementation, 271 backend tests, frontend build, focused desktop/narrow production-route checks, independent re-review, CI run 35819386530, deployment run 35819576769, exact deployed SHA and public health pass. Exact E65A post-deploy readback remains UV-032 because the protected website session expired.

### PD-065 — 运行中逐请求显示秒级等待，非运行状态只显示成功与失败

- Status: Confirmed
- Date: 2026-09-22
- Source question: 长时间 ASR/LLM 调用如何在进度区域证明仍在等待，而不堆叠过多中间态
- Decision owner: Product owner
- Source thread/message: 当前 Codex 任务；产品负责人连续确认逐请求计时和历史状态精简方案
- Confirmation quote: “就是每一秒都能看到数字在动，这样状态可见。你先设计一下，不要改代码。”；“应该展示当前每个请求处理的时长吧？”；“历史这个部分失败数据，和暂停的数据，也不用显示这么长。就写有几个failed，有几个success就行了”；“好的，现在方案确认了”
- Decision: 批次列表与任务详情的活动阶段只展示当前正在执行的外部请求，每个并发请求使用一条紧凑状态，包含阶段/供应商、当前请求序号与总数、等待动作和从服务端请求开始时间计算的秒级耗时。完成请求立即移除并由下一条活动请求替换；排队项和历史尝试不进入该区域。进度百分比仍只来自持久化完成量，不随计时器伪增长。暂停和部分失败状态只按当前阶段业务单位显示 `N failed · M succeeded`：Pass 1 按 conversation、Multi-ASR 按完整录音 provider job、Pass 2 按 Case；请求组、尝试次数和详细错误只保留在任务详情/日志。
- Reason: 秒级变化可区分“正在等待供应商”与“页面卡住”，逐请求计时又避免“最久等待”隐藏其他并发请求；非运行状态无需重复展示 Case、请求组、pending 和 attempts 的长串技术统计。
- Consequences: 后端需为活动请求暴露安全的 operation ID、stage、provider、ordinal/total、started_at 和 heartbeat；前端每秒只更新显示耗时，并继续短轮询真实状态。心跳过期时显示状态同步异常，不得继续把请求呈现为健康运行。计时变化不进入屏幕阅读器逐秒播报；状态切换才通过 live region 通知。桌面、窄屏和最小移动视口不得横向溢出。
- Updated artifacts: Delta Spec、`design.md`、`tasks.md`、`prototypes/`；V1.18 已由 PD-066 冻结，正式代码与测试进入实施。
- Verification: User Gate 1, Engineering Checkpoints A/B/C and production deployment pass; exact E65A post-deploy readback remains UV-032.

### PD-064 — 恢复并实施 Qwen 分阶段超时、medium Thinking 与失败拆分

- Status: Confirmed
- Date: 2026-09-22
- Source question: PD-062 证明真实两 Case 请求在 medium 下需 223.373 秒后，如何修复 Pass 1/Pass 2 超时与重复失败
- Decision owner: Product owner
- Source thread/message: 当前 Codex 任务；产品负责人确认推荐方案，并在 PD-061 发布完成后明确恢复实施和上线
- Confirmation quote: “明白了，就是太慢。可以这样做。”；“好的。执行修复吧，修复完成后就上线。”
- Decision: Qwen Pass 1 保持非 Thinking，单次 timeout 为 180 秒；初始动态装箱必须为最长纠正提示预留最终消息空间。timeout 或结构失败后按完整 conversation 稳定二分，失败父组标记 superseded 且不得原样重放。Qwen Pass 2 固定 `reasoning_effort=medium`，单次 timeout 为 300 秒；timeout 或结构失败后按完整 Case 稳定二分，父组同样不得原样重放。可继续拆分的子组递归拆分；最小 conversation/Case 最多额外重试一次后明确失败。任何已成功子组、conversation 或 Case 均立即持久化并在恢复/重试中复用。
- Reason: 外部真实验证已排除上下文溢出并证明 120 秒不足；medium 原组在 223.373 秒正确完成。原样重放父组不能改变失败条件，且 Pass 1 的较长纠正指令会把贴近 64K 的组推过发送前上限。
- Consequences: PD-063 的临时顺序发布暂停已经解除；本决定只改变新执行或产品负责人主动重试的失败资源，不自动重跑或改写 E65A。超时拆分仍受批次预算、幂等、成功检查点复用和可重试分类约束。完成实现、独立验收和生产发布后，不由 Agent 自动操作旧批次。
- Updated artifacts: Delta Spec、`design.md`、`tasks.md`、执行器、Qwen 原生请求、持久化分组状态、进度 UI 和回归测试。
- Verification: PD-062 external-real 作为 timeout/medium 参数证据；拆分、恢复、最长纠正提示预留和不重复成功检查点已由 deterministic/mock 回归验证，生产发布后仍由用户主动批次提供 external-real 验收。

### PD-063 — 先发布完整录音 turn 投影，再开发新的 LLM 调用逻辑

- Status: Confirmed
- Date: 2026-09-22
- Source question: PD-061 独立验收通过后，是否先发布到生产，并与另一任务计划中的 LLM 调用逻辑改动隔离
- Decision owner: Product owner
- Source thread/message: 当前 Codex 任务；产品负责人明确要求顺序发布
- Confirmation quote: “可以，发布到线上吧……先把你这次的发布发到线上。后面我让它再改，等你发到线上之后再改新的”
- Decision: 先提交并发布已独立验收通过的 PD-061。发布范围可包含已经完成、但不改变运行逻辑的 Qwen 诊断记录；不得包含新的 LLM 调用逻辑实现。共享工作区中的另一任务必须暂停代码、OpenSpec、提交与发布，直到本次生产部署完成且产品负责人另行恢复。
- Reason: PD-061 与后续 Qwen/LLM 超时、Thinking 和拆组策略会触及同一执行器及 Change 文件；顺序发布可以建立清晰生产基线，避免共享工作区交叉提交和无法归因的线上行为。
- Consequences: 本次发布不得自动重跑或改写 E65A，不得触发付费 ASR/LLM；发布后需核对 CI、部署、生产健康和生产提交 SHA。后续 LLM 逻辑由另一任务在收到明确恢复通知后继续。
- Updated artifacts: `decision-log.md`、`tasks.md`、`verification/delivery-status.json`、提交与发布证据。
- Verification: PASS。代码提交 `ec373a4` 与格式修复 `ca2e80a` 已进入 `main`；CI run `35813859148`、生产部署 run `35814003041` 和公网健康检查成功。生产服务器运行 `ca2e80aa289d0c9f5276767baeb0cf334bd7cf4e`；E65A 的 `updated_at=2026-09-23T02:26:50+00:00`、8 个失败组和 30 个失败 Case 均未变化，未触发供应商调用。

### PD-062 — 修复前以最小 Qwen Pass 2 原组和按 Case 拆分验证超时根因

- Status: Confirmed
- Date: 2026-09-22
- Source question: Q-017；`EV-20260923-E65A` 的 Qwen3.8-Max Pass 2 是否主要因默认 `xhigh` 思考强度超时，以及 Pass 1/Pass 2 是否需要在超时后拆分
- Decision owner: Product owner
- Source thread/message: 当前 Codex 任务；产品负责人要求修复前先验证未验证项，并在 Agent 明确数据、接收方、调用次数、停止条件后确认费用上限
- Confirmation quote: “确认。但是修复前，你需要先验证尚未验证的问题。我授权你可以调用外部接口”；“确认上述调用范围，USD 5 上限。”
- Decision: 在修改生产逻辑前，仅重放 `EV-20260923-E65A` 最小失败组 `G0008` 的两个 Case 文本证据至 `dashscope.aliyuncs.com/api/v1` 的 `qwen3.8-max`。第一次保持原组、显式设置 `reasoning_effort=medium`、`max_completion_tokens=32768`、300 秒客户端超时且不自动重试；若原组成功立即停止。仅当原组发生 timeout、无效响应或结构失败时，才按 Case 拆成两个单 Case 请求，各调用一次并停止。不得回写、恢复或改变生产批次，不发送音频、凭证或其他批次数据。
- Reason: 先用原始最小失败证据区分默认高思考强度、120 秒等待上限和组大小的影响，再据真实结果确定修复参数与超时拆组策略，避免直接重试整批或凭推断改行为。
- Consequences: 最多三次 Qwen 调用，总供应商费用上限 USD 5；原组成功、两子组完成、预计下一次调用会超过上限，或出现鉴权、限流、端点/模型配置错误时立即停止。授权仅覆盖本次只读诊断，不授权实现、发布或重跑整批。
- Updated artifacts: `decisions/open-questions.md`、`decisions/decision-log.md`、`verification/delivery-status.json` 和本次外部验证证据。
- Verification: External-real execution completed on 2026-09-22. The original two-Case group returned HTTP 200 in 223.373 seconds with 20,529 input, 5,199 reasoning and 5,713 visible output tokens; both Cases passed the production schema/ID checks. One call cost an estimated USD 0.031441, so no split fallback was triggered. Evidence: `verification/qwen-g0008-medium-diagnostic-2026-09-22.md`.

### PD-061 — 完整录音 ASR 片段作为正式候选，纯用户切片只用于回听与 Benchmark

- Status: Confirmed
- Date: 2026-09-22
- Source question: `EV-20260923-E65A` 为什么在 22 通命中 conversation 上生成 174 个 Multi-ASR 任务，以及纯用户单句切片是否应再次转录
- Decision owner: Product owner
- Source thread/message: 当前 Codex 任务；产品负责人先纠正目标数据流，随后明确要求修改
- Confirmation quote: “不应该是用完整的上下文录音里面的那个文本片段直接对比就好了吗？只是把36个片段的user_record切出来就好了”；“对的。改一下吧。”
- Decision: 每家启用的评测 ASR 只对每个命中 conversation 的完整 `record` 提交一次带说话人时间轴的转写。Event Aligner 把目标事件映射到各 provider 的真实 turn 后，系统直接使用这些 turn 的文本作为该 Case 的正式 ASR 候选和 Pass 2 证据。`user_record` 仍按 provider turn 区间并集生成稳定纯用户 WAV，但只用于回听、人工复核和 Benchmark 音频，不再提交任何评测 ASR。Multi-ASR 外部任务总数只统计 conversation/provider 完整录音任务，不把本地音频切片或派生 Case 证据计作 provider job。
- Reason: 纯用户单句片段脱离完整上下文，再次转录仍可能产生新的识别错误；完整录音 ASR 已经在上下文中完成识别，其目标 turn 文本更符合评测证据目的。重复提交切片会额外增加调用、费用和失败点。
- Consequences: PD-035、PD-048、PD-049、PD-053、PD-056、PD-058 中要求事件级纯用户重转录作为正式候选的部分被本决定取代；完整录音转写、Event Aligner、provider turn 区间并集和用户轨只扩不缩规则继续有效。既有批次、费用和报告保持历史事实，不自动改写或重跑；新逻辑只作用于新建或明确按新版本恢复的工作。
- Updated artifacts: `proposal.md`、Delta Spec、`design.md`、`tasks.md`、`prototypes/README.md`、实现、回归测试与独立验收。
- Verification: Independent review PASS；145 项定向回归、267 项全库测试、Scoped Ruff/Mypy、前端生产构建、diff check 与 Change gate 全部通过。未调用付费外部服务，未修改或重跑 E65A；新生产批次真实运行仍由 `UV-030` 跟踪。

### PD-060 — 暂停或部分失败批次使用现有结果结束并发布

- Status: Confirmed
- Date: 2026-09-22
- Source question: `EV-20260922-7D19` 已保存 17 条 Pass 2 结果、7 条人工复核和 10 条 Benchmark，但因确定性失败停在暂停状态时，能否不增加复杂人工流程而直接结束
- Decision owner: Product owner
- Source thread/message: 当前 Codex 任务；产品负责人确认推荐的“使用现有结果结束”方案
- Confirmation quote: “确认这个修复方案。”
- Decision: 对已有初步报告的 `paused` 或 `partially_failed` 批次，在现有批次操作区提供“使用现有结果结束”。二次确认后系统只使用已持久化的成功 Pass 2、已完成人工复核和已生成 Benchmark，排除待复核、未完成、失败或未能可靠裁片的 Case，事务性冻结不可变 `final_partial` 报告并将批次置为 `completed_partial`/100%。操作不得恢复执行器、重试失败资源、调用 ASR/LLM、删除成功结果或改写费用/检查点。运行中批次必须先暂停；发布本能力但不得由 Agent 代为操作生产批次 7D19。
- Reason: 7D19 已有足够的成功成果形成部分覆盖交付，但现有提前结束入口只允许 `awaiting_review`，导致确定性失败批次只能重复重试或长期停在暂停状态。
- Consequences: 确认弹窗复用现有产品弹窗模式并明确保留、排除、不可变与不发起外部调用；部分报告必须披露排除数量和结束方式。该修复不替代 KI-171 的重试范围修正或 KI-172 的 Pass 1 纠正指令装箱修正。
- Updated artifacts: `proposal.md`、Delta Spec、`design.md`、`tasks.md`、`prototypes/README.md`、实现、回归测试、独立验收与发布证据。
- Verification: Implementation and independent review PASS; commit `ff0100a51067295e8ae3966fa5159906bf82fdca`, CI run `35726185927`, production deployment run `35726412542` and public health all PASS. The release did not operate 7D19 or make a paid provider call.

### PD-059 — 修复跨厂商输出预算、失败进度与 ASR 安全诊断并发布

- Status: Confirmed
- Date: 2026-09-22
- Source question: `EV-20260922-7D19` 在 Pass 1 和 Event Aligner 已完成后为何变为部分失败且进度归零，以及 ASR 失败为何只显示笼统错误
- Decision owner: Product owner
- Source thread/message: 当前 Codex 任务；产品负责人在三项缺陷摘要上直接批注并授权修复、验证和上线
- Confirmation quote: “那这三个缺陷你修一下吧。修完了发布上线。”
- Decision: 修复 Gemini、DeepSeek、Qwen、GPT/Azure/OpenRouter 共用的生成预算：在冻结的生成上限内先预留结构化可见 JSON，Thinking 只能使用剩余额度，二者合计不得超过上限。发送前的单 Case 输入或输出规划失败使用专用 preflight 分类，不得冒充供应商无效响应；批次进入部分失败时保留最后阶段、已完成进度、检查点和费用，不得归零。ASR 失败只公开安全诊断，包括 provider、完整录音或事件切片范围、尝试次数、是否可重试、受控分类和可操作原因；不得公开供应商原始响应、客户文本、文件路径或凭证。发布本修复，但不自动恢复或重跑 `EV-20260922-7D19`、`EV-20260922-CB26`，Agent 不主动发起付费 ASR/LLM 调用。
- Reason: 7D19 的 Gemini 策略把 32K Thinking 预留与每个 Case 的可见 JSON 预留相加，导致任何非空 Pass 2 Case 都在本地确定性失败；通用异常映射又把它标为供应商响应错误，并把已完成阶段的 75% 进度覆盖为 0%。同时 ASR 检查点仅保存 `EvaluationExecutionError` 类名，无法判断失败范围和后续操作。
- Consequences: 现有页面复用批次错误区、部分结果提示和 Case provider 单元格展示安全诊断，不新增页面区域或改变冻结视觉基线。历史成功资源、费用和报告不可变；旧批次只有产品负责人主动重试时才按新契约执行。
- Updated artifacts: `proposal.md`、Delta Spec、`design.md`、`tasks.md`、`prototypes/README.md`、实现、回归测试、独立验收与发布证据。
- Verification: 128 项定向与 262 项全库测试、Scoped Ruff/Mypy、前端构建、Change gate、独立验收和桌面/窄屏生产 DOM 检查均 PASS；提交 `e13502b` 的 CI `35717197895`、生产部署 `35717398439` 和公网健康检查均成功。未自动重试 CB26/7D19，也未发起真实付费调用。

### PD-058 — 两轮评测使用统一 128K 包络并去除重复证据投影

- Status: Confirmed
- Date: 2026-09-22
- Source question: CB26 第二轮为何在 DeepSeek 标称 1M 上下文内仍持续返回无效 JSON/未知 Segment ID，以及应如何限制两轮评测请求
- Decision owner: Product owner
- Source thread/message: 当前 Codex 任务；产品负责人先确认推荐的两轮共同硬上限方案，随后确认修订现有 `add-asr-automated-evaluation` Change，而不是建立并行 Change
- Confirmation quote: “可以，不过当时为什么有重复投影啊？”；“同意”；“完成这个需求直至上线吧。如果有疑问再来找我”
- Decision: Pass 1 与 Pass 2 采用与供应商无关的 128K Token 运行包络：最终序列化输入硬上限 64K，Thinking 与可见输出合计最多 32K，并保留 32K 安全余量；实际生效值取该公共上限与冻结模型已验证限制中的较小者。装箱必须基于最终发送的完整消息计算，而不是只统计去重后的 conversation unit。动态证据只在完成变量替换的 System Prompt 中出现一次，User message 仅保留不含业务证据的固定执行指令，不得再次序列化同一 payload。Pass 2 保留每个 Case 所属 conversation 的完整历史文本，但完整录音 ASR 上下文只发送 Event Aligner 已映射的目标 turns 及每家 provider 的直接相邻 turns；同一 conversation 仍超限时，发送前按稳定 Case 子集拆组并重复必要的完整历史。单个 Pass 1 conversation 或单个 Pass 2 Case 在上述裁剪后仍无法满足 64K 输入上限时，必须在外部调用前明确失败，不得靠付费请求或失败后递归拆分发现超限。Event Aligner 不在本决定范围内。
- Reason: `EV-20260922-CB26` 的 77 万“Token”是 UTF-8 字节上界，不是供应商实际 Token；真实 DeepSeek Pass 2 输入仍达到 534,095–604,856 Token，并在未触发上下文长度错误的情况下返回无效 JSON或引用不存在的 ASR Segment ID。根因是同一证据同时存在于嵌套 `conversations`、旧顶层字段、完成变量替换的 System Prompt 和 User JSON 中，且完整录音 ASR 占去重后输入约 74.6%。标称上下文容量不能保证超长、重复结构化任务的 ID 与 JSON 可靠性。
- Consequences: PD-017、PD-052 中“Pass 2 单通完整对话永不拆分”和“失败后才递归拆组”的部分被本决定收窄：完整历史仍不截断，但 Case 可在同一 conversation 内预拆；尺寸规划在付费调用前完成。第一轮继续保持 conversation 不可拆。已有批次和报告保持不可变，已停止的 CB26 不自动恢复或重跑。该范围作为现有 Change 的增量里程碑实施，不另建并行 Change。
- Updated artifacts: `proposal.md`、Delta Specs、`design.md`、`tasks.md`、`prototypes/README.md`、`verification/delivery-status.json`。
- Verification: 126 项定向回归、251 项全库测试、Scoped Ruff/Mypy、Change gate 与独立验收 PASS；提交 `a18a963` 的 CI `35712072904`、生产部署 `35712275233` 及公网健康检查均成功。未恢复 CB26，也未发起真实付费调用；真实新批次结果仍由 `UV-028` 跟踪。

### PD-057 — 发布 Event Aligner 增量供线上验收

- Status: Confirmed
- Date: 2026-09-22
- Source question: PD-056 实现、回归与独立复验通过后，是否推送现有生产发布流程
- Decision owner: Product owner
- Source thread/message: 当前 Codex 任务；独立复验 PASS 后的用户明确指令
- Confirmation quote: “推送线上。”
- Decision: 仅提交并推送 PD-056 Event Aligner 增量到 `git@github.com:jasonchao75/VoiceAgent.git` 的 `main`，触发现有 CI 与生产部署流程。发布包含整批优先/超限最少完整对话分组、真实 turn ID 与 speaker role 校验、provider 区间并集、用户轨只扩不缩、事件级失败隔离、可恢复检查点、回归测试与验收记录；不得夹带工作区其他改动。常规发布保留生产现有 Evaluation 数据，不自动重试旧批次、不启动新批次，也不主动发起付费 ASR/LLM 调用。
- Reason: 产品负责人要在线上通过新建或主动操作的批次验收 R6/R7/R13 修正，同时保持本次发布范围独立、可追溯和可回滚。
- Consequences: 推送后必须核对 CI、生产部署、部署提交一致性与公网健康；真实整批 Event Aligner 的准确率、延迟和费用仍由用户后续主动批次验证。
- Updated artifacts: PD-056 实现、Delta Spec、design、tasks、Prompt fixture、测试、交付状态、独立验收与部署证据。
- Verification: 发布前 241 项测试、Scoped Ruff/Mypy、Change gate 与独立复验 PASS；发布后以 GitHub Actions 与公网健康检查为准。

### PD-056 — 使用批量动态装箱的 Event Aligner 映射目标事件

- Status: Confirmed
- Date: 2026-09-21
- Source question: Q-016 目标 R 事件如何映射到完整录音 ASR 时间线，以及 Event Aligner 的调用粒度
- Decision owner: Product owner
- Source thread/message: 当前 Codex 任务；产品负责人先确认四段职责方案，随后明确否决逐通调用并确认整批动态装箱
- Confirmation quote: “确认采用这个四段职责清晰的Event Aligner方案”；“确认 Event Aligner 改成‘整批优先、超限才按完整对话拆成最少请求组’”
- Decision: 保持 Pass 1 先从 Excel 历史中选择目标 R 事件，只对命中 conversation 执行三家完整录音 ASR。随后由独立 Event Aligner 读取有序 worksheet 事件与三家按相邻同 speaker 合并的真实 ASR turns，把全部目标 R 映射到各 provider 的既有 `turn_id`。Event Aligner 按批次动态 Token 装箱：整批安全可容纳时只发起一次请求，超限时才按完整 conversation 不可拆分原则生成最少请求组；失败只重试失败组。模型不得生成时间戳或不存在的 ID；程序验证 group/conversation/event/provider/turn ID、用户角色、单调顺序和至少两家映射后，从真实 turns 回查时间并取并集作为裁片基础。纯用户轨可向外补齐语音边缘但不得向内缩短该并集，不设置“10 秒”硬阈值；异常宽区间必须明确失败而不是静默截短。
- Reason: 生产 R6 证明逐家短文本规则会拒绝正确数字轮次，R7/R13 证明厂商 VAD 边界天然不同且交集会丢音。独立 GPT 模拟可以从整通顺序、speaker、相邻话术和多家时间槽中选择正确真实 ID；动态装箱避免逐通 LLM 调用的费用与等待。
- Consequences: 新增可恢复、可计费的 Event Aligner 分组检查点和专用 Prompt/Schema，复用批次冻结的 Pass 1 LLM 资源但不冒充原 Pass 1 请求。完整录音 ASR、Event Aligner、确定性裁片和事件级重转录职责分离；既有报告保持不可变，新流程只作用于新建或明确重试的相关工作。
- Updated artifacts: Q-016、Delta Spec、`proposal.md`、`design.md`、`tasks.md`、Event Aligner 实现/测试与 `verification/event-aligner-gpt-simulation-2026-09-22.md`。
- Verification: deterministic/mock 必须覆盖整批单组、超限最少分组、对话不可拆、错误/虚构 ID 拒绝、失败组重试、R6/R7/R13 映射、并集边界和纯用户轨不缩短；不主动发起真实付费调用。

### PD-055 — 顺序发布 KI-161 并补投 BA92 已成功结果

- Status: Confirmed
- Date: 2026-09-21
- Source question: 等待并行的 PD-053 发布结束后，是否发布部分失败结果投放修复并恢复现有 BA92 成功结果
- Decision owner: Product owner
- Source thread/message: 当前 Codex 任务；用户要求等待上一任务完成后再补推
- Confirmation quote: “好的，现在应该是还有一个独立分支在发布，你看看你改的代码有没有问题？如果没有问题的话，等上一个任务完成后，你再补推一版”
- Decision: 在上一任务 CI 与生产部署成功后发布 KI-161；随后对 `EV-20260921-BA92` 执行不调用外部模型的幂等补投，将已完成的第二轮决定投放到人工复核和 Benchmark，同时保留失败项及部分失败状态。
- Reason: 避免并行发布冲突，并恢复已经付费且成功持久化但未进入正常产品工作流的结果。
- Consequences: 补投前保存生产数据库备份；不得重跑 ASR/LLM、不得产生新增供应商费用、不得生成正常完整报告或改变 6 条失败项。
- Updated artifacts: KI-161 实现、测试、交付记录与生产批次投放状态。
- Verification: CI、生产部署与公网健康检查通过；只读核对为 18 条人工复核、20 条 Benchmark、6 条 Pass 2 失败、0 份冻结报告，批次仍为 `partially_failed`。

### PD-054 — 发布说话人分离定位增量供产品验收

- Status: Confirmed
- Date: 2026-09-21
- Source question: PD-053 完成独立复验后，是否将本次定位逻辑单独推送生产供用户验收
- Decision owner: Product owner
- Source thread/message: 当前 Codex 任务，用户明确询问并授权本次修改先推送线上验收
- Confirmation quote: “本次修改的这部分能不能先推送到线上，我来验收”
- Decision: 仅提交并推送 PD-053 的完整录音说话人分离、文本/顺序角色映射、多厂商共同区间、用户轨校验、旧检查点迁移、成本记账及对应规格/测试/独立验收记录。不得夹带当前工作区内其他未提交改动；发布本身不触发真实评测、不发送客户录音，也不主动产生 ASR/LLM 费用。
- Reason: 让产品负责人通过现有线上入口发起受控真实批次并验收新定位效果，同时保持本轮发布范围可追溯、可回滚。
- Consequences: `main` 推送将触发现有 CI/生产发布流程；既有报告保持不可变，旧批次仅在用户主动重试时才可能按新契约重新请求不合格的完整录音检查点并产生相应费用。
- Updated artifacts: PD-053 实现、Delta Spec、design、tasks、交付状态、独立验收与部署证据。
- Verification: 实现提交 `f0ce94372c7ce591e8e3f20d4ec1ba36d3c7d641` 已推送；CI run `35683722888` 与生产部署 run `35683865638` 均成功，部署流程完成公网健康检查。

### PD-053 — Excel 时间完全退出定位，使用完整录音说话人分离与文本顺序对齐

- Status: Confirmed
- Date: 2026-09-21
- Source question: Excel VAD 时间不可靠时，如何从完整录音 ASR 结果确定目标用户事件的真实说话区间
- Decision owner: Product owner
- Source thread/message: 当前 Codex 任务，用户先确认 Excel 时间完全退出，随后确认说话人分离为主的实现方案
- Confirmation quote: “完全退出。”；“行，那你改一下这个逻辑？然后再和我对一下”
- Decision: Excel `time (s)` 不得参与用户事件定位，仅作源数据审计字段保留。完整录音 ASR 必须显式启用说话人分离并保存逐词/逐段时间表；系统通过历史转写文本、对话顺序和说话人标签将匿名 speaker 映射为 Agent/User，并以至少两家成功 ASR 的时间区间共识生成目标用户句子边界。`user_record` 只用于校验该区间存在用户信号和微调裁剪边缘，不得用简单能量/VAD 在全局中选择目标句。不足两家或结果冲突时必须失败关闭，不得回退到 Excel 时间或猜测 speaker。
- Reason: Excel 时间由不准确的开源 VAD 产生，局部能量检测也可被线路底噪和呼吸声误导；完整录音异步 ASR 同时具备全局上下文、说话人标签和精确时间戳，更适合作为主定位证据。
- Consequences: Soniox 和 Speechmatics 完整录音请求需显式开启 speaker diarization，ElevenLabs 保留已有 `diarize=true`；不启用 ElevenLabs 额外计费的自动角色识别。既有报告保持不可变，新建或重新执行的事件定位必须满足新共识契约。
- Updated artifacts: Delta Spec、`design.md`、`tasks.md`、ASR 适配器、事件对齐/裁片逻辑、回归测试和交付记录。
- Verification: deterministic/mock 覆盖三家 diarization 请求、匿名 speaker 角色映射、两家时间共识、Excel 时间完全不影响结果、底噪下的用户轨校验以及冲突/缺失失败关闭；不主动发起付费外部调用。

### PD-052 — 失败组自适应拆分、真实进度与稳定 Case 口径

- Status: Confirmed
- Date: 2026-09-21
- Source question: EV-20260921-BA92 重试持续超时、进度误导及 Case 从 38 增至 44 的修复方案
- Decision owner: Product owner
- Source thread/message: 当前 Codex 任务，用户确认先修复发布、再重试既有失败批次
- Confirmation quote: “好的，修复并发布吧”
- Decision: 第二轮超时或 Segment ID 契约失败时，不再原样重复同一失败组；系统按完整对话不可拆分原则递归拆成更小的稳定子组，成功检查点继续复用。页面同时展示 Case 与请求组的成功、失败、处理中和尝试次数，失败不得计作成功进度，后续子批次不得覆盖全阶段总数。只有全部疑点 Case 第二轮成功后才可生成额外 Good 平衡样本；重试期间疑点总数保持稳定，并单独展示后续新增 Good 数量。
- Reason: 线上真实批次证明 34–72 万估算输入 Token 的大组会连续触发 120 秒超时，原样重试六次不能改变失败条件；旧进度把失败当成完成，且在疑点未完成时增加 Good 样本，造成状态误导和额外费用。
- Consequences: 单通完整对话仍是最小不可拆单元；拆至单通仍失败时明确保留失败，不无限重试。`EV-20260921-BA92` 发布后可复用 11 个成功结果，只重试失败 Case/组；已有 6 个提前创建的 Good 检查点保留但不得参与疑点完成口径，待疑点全部成功后再按最终差额复用或补齐。
- Updated artifacts: Delta Spec、design、tasks、运行时状态/页面文案、第二轮分组检查点与回归测试。
- Verification: deterministic mock 覆盖超时拆组、Segment 契约拆组、成功检查点复用、单通失败上限、真实成功/失败/处理中计数、全局 ASR 总数和疑点完成前不新增 Good；发布后由用户对现有失败批次主动重试，Agent 不代发付费请求。

### PD-051 — 发布音频定位与 Benchmark 删除增量

- Status: Confirmed
- Date: 2026-09-21
- Source question: PD-048/PD-049 音频定位、完整录音上下文与 PD-050 Benchmark 删除完成后的生产发布
- Decision owner: Product owner
- Source thread/message: 当前 Codex 任务，独立验收通过后用户明确授权
- Confirmation quote: “完成之后，就推送到线上环境吧”
- Decision: 将已独立验收通过的纯用户语音定位、每通完整录音 ASR 上下文和 Benchmark 单条硬删除增量提交到 `main` 并推送现有生产发布流程。保留生产现有批次、报告、复核、Benchmark 与配置；本次发布不主动执行 Benchmark 删除、不清理生产数据，也不发起付费外部 ASR/LLM 调用。
- Reason: 让后续真实评测使用修正后的纯用户片段与独立完整录音上下文，并让用户可以在产品内受控删除单个 Benchmark。
- Consequences: 新评测按新音频规则执行；已有报告与历史证据保持不变。Benchmark 仅在用户从页面二次确认时删除。本次提交不得夹带暂停中的 Voice Bot 设计改动、本地录音、测试数据库或凭证。
- Updated artifacts: 本 Change 实现、测试、交付状态、独立验收和生产部署记录。
- Verification: 提交 `f61dd1f` 推送前全量 223 项测试、Ruff、Mypy、前端构建、双视口删除回归、Change gate 与独立验收通过；GitHub CI `35613404650`、生产部署及公网健康检查 `35613635940` 均成功，生产数据保持不变。

### PD-050 — Benchmark Library 单条硬删除

- Status: Confirmed
- Date: 2026-09-21
- Source question: Benchmark Library 删除范围与恢复策略（Q-016）
- Decision owner: Product owner
- Source thread/message: 当前 Codex 任务，用户在 Option A 边界说明后明确确认
- Confirmation quote: “确认。”
- Decision: Benchmark Library 在列表和详情提供单条删除入口；用户二次确认后，硬删除该 Benchmark 当前记录、不可变修订和托管派生 WAV，不提供批量删除或恢复入口。保留源对话、源批次、报告、人工复核和不含客户内容的删除审计墓碑。
- Reason: 满足删除正式样本的明确诉求，同时将不可恢复范围限制在单个 Benchmark 及其派生文件，不破坏上游评测证据链。
- Consequences: 删除后样本立即从列表、筛选、汇总和后续导出中消失，详情和音频返回不存在；已生成的历史下载包不回写修改。删除操作不可恢复，确认文案必须明确影响范围。
- Updated artifacts: Benchmark Library Delta Spec、design、tasks、正式页面、API、存储与回归测试。
- Verification: 定向验证列表和详情入口、二次确认、数据库级联范围、派生 WAV 删除、上游数据保留、审计墓碑及固定桌面/窄屏无横向溢出。

### PD-047 — 发布本轮 LLM 可靠性与 Qwen 原生协议修复

- Status: Confirmed
- Date: 2026-09-21
- Source question: 本轮 Gemini/Qwen 可靠性修复是否推送并部署生产
- Decision owner: Product owner
- Source thread/message: 当前 Codex 任务，完成独立验收后用户明确授权
- Confirmation quote: “可以推送到线上吧。”
- Decision: 将已独立验收通过的 Cost Settings 诊断、第一轮动态装箱、Gemini/Qwen 结构化重试与 Qwen 原生/兼容双协议修复提交到 `main`，推送 `git@github.com:jasonchao75/VoiceAgent.git` 并触发既有生产发布流程；保留现有生产 Evaluation 数据，不执行额外历史清理或付费模型调用。
- Reason: 恢复 `gemini-3.8-flash`、`qwen3.8-max` 从连接、定价、建批到两轮执行的完整产品链路，并降低重复失败与无结果批次。
- Consequences: 部署只包含本 Change 的相关代码、测试和交付记录，不夹带暂停中的 Voice Bot 设计改动、本地测试数据或凭证。线上真实模型权限和供应商返回仍需用户后续正常操作验证。
- Updated artifacts: 本 Change 实现、测试、交付状态、独立验收和生产部署记录。
- Verification: 推送前全量 220 项测试、Ruff、Mypy、前端构建、Change gate 和独立验收均 PASS；推送后核对 CI/CD、生产健康和部署提交一致性。

### PD-046 — Qwen 同时支持原生 DashScope 与兼容协议

- Status: Confirmed
- Date: 2026-09-21
- Source question: 是否一起修复 Qwen 中国站连接和 qwen3.8-max 调用问题
- Decision owner: Product owner
- Source thread/message: 当前 Codex 任务；延续用户已明确提供的 `https://prem.dashscope.aliyuncs.com/api/v1`
- Confirmation quote: “Qwen的问题你能一起修吗”
- Decision: Qwen 资源不再固定到共享 OpenAI-compatible Endpoint；保留 compatible-mode 支持，同时允许已确认的 `prem.dashscope.aliyuncs.com/api/v1` 原生 Endpoint，并通过阿里云原生消息协议诊断和执行 `qwen3.8-max`。连接、模型目录、成本配置和两轮评测必须使用同一冻结协议与 Base URL。
- Reason: 用户账号只有 prem 原生 Endpoint；旧实现强制替换为共享 compatible-mode，导致实际可调用的 qwen3.8-max 无法通过连接与模型登记流程。
- Consequences: 原生请求使用 Bearer 鉴权、官方 generation 路由和原生消息/usage 结构；URL 仅允许 HTTPS DashScope/Model Studio 域名及官方协议路径。真实连通仍需单独付费调用授权。
- Updated artifacts: Evaluation configuration Delta Spec、design、tasks、Qwen 原生适配器、连接验证、诊断/执行器、前端模型目录和回归测试。
- Verification: deterministic mock/static 测试验证 URL 白名单、qwen3.8-max 路由、Thinking 参数、响应与 usage 解析；本轮不发起真实外部调用。

### PD-045 — 第一轮采用动态 Token 装箱

- Status: Confirmed
- Date: 2026-09-21
- Source question: 第一轮疑点筛选的 LLM 请求粒度
- Decision owner: Product owner
- Source thread/message: 当前 Codex 任务，用户核对现有逐通调用后明确要求修改
- Confirmation quote: “把第一轮改成‘完整对话为不可拆分单元，容量允许则全批一次请求，超限动态拆组’”
- Decision: 第一轮以每通完整对话及其全部历史事件为不可拆分单元，按冻结模型的上下文上限、结构化输出预留和安全余量动态装箱；整批能够安全容纳时只发一个外部请求，不能容纳时使用最少安全分组。每组使用稳定 `request_group_id` 和冻结成员关系，输出必须逐通完整返回且不得遗漏、重复或跨组混入对话；失败只重试失败组，成功组和成功对话检查点不得重复调用。
- Reason: 用户原始目标是先汇总批次中的对话文本，让模型在同一请求中统一生成疑点事件；逐通调用增加请求次数，也失去跨对话批量处理的成本与一致性优势。
- Consequences: 第一轮 Prompt 从单通顶层输出升级为分组输出契约；进度继续按唯一对话数统计，同时记录外部请求组数。任一完整对话自身超出安全限制时必须明确失败，不得拆开、截断或静默丢弃事件。现有冻结报告保持不可变，新契约只作用于后续或明确重试的运行。
- Updated artifacts: Delta Spec、`design.md`、`proposal.md`、`tasks.md`、`prototypes/README.md`、第一轮 Prompt V2、装箱/检查点实现与回归测试。
- Verification: deterministic mock 覆盖整批单组、超限多组、完整对话不可拆分、稳定组 ID、失败组重试、逐通输出完整性及对话不漏不重；本次不发送真实客户文本或发起付费调用。

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
- Consequences: PD-010 的“永久保留旧批次审计证据”被本决定取代；删除只清理该批次拥有的结果、复核、Benchmark、报告、执行检查点和成本记录，不删除共享源数据、连接、上下文、词典、标签或价格版本；保留不含客户内容的删除审计墓碑。V1.17 历史基线（SHA-256 前缀 `fd400add…`）已被 PD-066 的 V1.18 取代。
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

### PD-048 — Excel 时间只作定位锚点，正式 ASR 候选来自纯用户真实声音区间

- Status: Confirmed
- Date: 2026-09-21
- Source question: KI-149 中 `1030000000086502 R6/R10` 的事件切片明显偏离真实用户声音
- Decision owner: Product owner
- Source thread/message: 当前任务 user message，纠正原有事件起点到下一事件起点的切分假设
- Confirmation quote: “Excel时间不是正确的时间啊，我之前说过。你需要根据excel的时间，找纯用户录音的部分，找到对应的声音，然后单独发送给ASR。”
- Decision: Excel `time (s)` 只能作为目标用户事件在 `user_record` 上的近似定位锚点，不得直接作为裁剪起点或终点。系统必须在锚点附近定位与该事件对应的真实用户发声区间，只把该单句纯用户音频作为三家评测 ASR 的正式重转录输入；边界无法唯一确认时必须明确失败，不得用长静音、相邻事件或完整通话转写冒充候选。
- Reason: 实际源数据证明时间值可能位于发声结束之后、乱序或超出音频总长；机械使用“本事件时间到下一事件时间”会漏掉目标句并截入几十秒静音或其他声音。
- Consequences: PD-035 中“按事件时间边界”的实现解释被本决定修正；既有错误事件级结果保持可追溯但不能作为有效质检证据，后续批次必须使用声音区间定位。完整历史上下文的外部接收方和费用范围仍由 Q-015 待确认。
- Updated artifacts: `decisions/open-questions.md`、`tasks.md`、`verification/delivery-status.json`；待 Q-015 关闭后同步 Delta Spec、design、实现与测试。
- Verification: 固定回归必须至少覆盖 `1030000000086502 R6` 和 `R10`，证明裁片包含目标用户发声、排除相邻机器人轮次和长静音，并在无法可靠定位时 fail closed。

### PD-049 — 完整录音发送三家 ASR 作为上下文，正式候选仅取纯用户单句

- Status: Confirmed
- Date: 2026-09-21
- Source question: Q-015 “历史上下文发送全部录音”的接收方和用途
- Decision owner: Product owner
- Source thread/message: 当前任务 user message，对 A/B/C 方案作出选择
- Confirmation quote: “选择A”
- Decision: 对每个进入评测 ASR 阶段的 conversation，系统向每家启用的评测 ASR 提交一次完整通话录音并将结果保存为只读上下文证据；对每个目标用户事件，仍另外提交从 `user_record` 声音定位得到的单句纯用户切片。第二轮可读取完整录音上下文转写辅助理解，但正式 ASR 候选、Good/Bad 判定对比和人工标注候选只能使用事件级纯用户切片结果，完整录音结果不得覆盖或冒充事件候选。
- Reason: ASR 需要完整通话理解上下文，同时最终对比必须排除机器人轮次和相邻用户发言。
- Consequences: 每个命中 conversation/provider 增加一次完整录音 ASR 调用、成本和可恢复检查点；完整上下文与事件候选必须独立计费、独立失败、独立展示来源。完整上下文失败不允许用其文本填充事件候选；事件切片失败仍按 PD-048 fail closed。
- Updated artifacts: Q-015、Delta Spec、`design.md`、`tasks.md`、执行器、存储、成本与回归测试。
- Verification: Mock 回归证明每通/provider 完整录音至多调用一次、同通多个 Case 复用上下文、每个 Case/provider 单独调用相同纯用户切片、第二轮同时接收完整上下文与事件证据且候选来源不混淆；真实付费调用仍需逐次授权。

### PD-067 — Event Alignment 作为独立第 4 步

- Status: Confirmed
- Date: 2026-09-22
- Source question: Event Aligner 的 Qwen 请求应继续归入多 ASR、合并到第二轮，还是成为独立阶段
- Decision owner: Product owner
- Source thread/message: 当前任务 user message，在 Agent 提出六步与合并卡片两个方案后明确按六步继续讨论 Align 设计
- Confirmation quote: “那你要怎么改呢？除了改成六步之外，Align这部分要怎么改”
- Decision: 批次流程扩为六步：1 数据校验、2 第一轮分析、3 多 ASR 转写、4 Event Alignment、5 第二轮分析、6 人工复核。Event Aligner 的 Qwen 请求、进度和失败不得再显示在多 ASR 阶段。
- Reason: Event Alignment 是完整通话 ASR 与 Pass 2 之间的独立 LLM 映射职责；单独展示才能准确表达当前等待、失败位置和恢复范围。
- Consequences: Delta Spec、设计、原型、阶段枚举、进度投影、历史批次兼容和 UI 回归都需同步更新；Align 内部的限包、拆分、失败隔离和恢复机制在本决定基础上继续细化。
- Updated artifacts: `decisions/open-questions.md`、`decision-log.md`、`verification/delivery-status.json`；其余实现材料待方案确认后更新。
- Verification: 六张阶段卡必须在桌面与窄屏可读；Event Alignment 运行时只在第 4 步显示逐请求耗时，完成后才进入 Pass 2；历史批次仍可正确映射旧阶段数据。

### PD-068 — 授权 E65A 小包 Event Aligner external-real 探针

- Status: Confirmed
- Date: 2026-09-22
- Source question: 在无法仅靠静态证据确定去重、限包和超时拆分方案是否能让真实 Qwen Event Aligner 稳定完成时，是否发送一个受限真实分组验证
- Decision owner: Product owner
- Source thread/message: 当前任务；Agent 明确数据接收方、最多调用次数、费用上限和停止条件后，产品负责人选择方案 A
- Confirmation quote: “你可以按照你的这个思路，我授权你调用Qwen尝试一下看看行不行，因为我也不确定你这个方式是不是行的。”；“A”
- Decision: 使用 `EV-20260923-E65A` 已持久化的历史事件、目标事件和三家完整通话 ASR turn，构建一个业务载荷只出现一次、最终输入不超过 64K 的真实 Event Aligner 分组，发送到该批次冻结的 Alibaba DashScope `qwen3.8-max`。Thinking 关闭、客户端超时 180 秒；首次成功立即停止。仅当超时或结构失败时，按完整 conversation 稳定拆成两个子组并各调用一次。不得发送音频、Key、其他批次或无关对话，不得恢复、改写或更新生产批次。
- Reason: 线上失败组达到约 79 万保守输入 Token，静态分析可以证明分组缺陷，但仍需一个最小 external-real 证据验证小包、去重、非 Thinking 请求能否在目标时限内返回合法映射。
- Consequences: 最多 3 次真实 Qwen 调用，总供应商费用上限 USD 1；成功、两个子组完成、预计下一次调用会触顶，或出现鉴权、限流、端点/模型配置错误时立即停止。本授权仅覆盖该只读探针，不授权重跑整批、实现或发布。
- Updated artifacts: `decisions/open-questions.md`、`decision-log.md`、`verification/delivery-status.json` 和 external-real 证据文件。
- Verification: External-real PASS。36 通 eligible conversation 被规划为 7 个不超过 64K 的组，无单通超限；选取最接近上限的 3 通/10 事件组（最终输入估算 65,294、输出预留 11,904）调用一次，在 22.947 秒内返回，Thinking Token 为 0，3 通/10 事件全部通过现有 Schema、turn ID 与归属校验。实际 usage 为 20,049 input / 1,190 visible output，估算费用 USD 0.021239；首次成功后未触发拆分，生产批次状态、阶段、版本、更新时间和成本均未变化。证据：`verification/qwen-event-aligner-bounded-probe-2026-09-22.md`。

### PD-069 — 实现、验证并发布 Event Alignment 修复

- Status: Confirmed
- Date: 2026-09-22
- Source question: 已验证的 Event Aligner 限包方案是否进入实现、测试和生产发布
- Source thread/message: 当前任务 user message
- Confirmation quote: “那就按已验证方案进入实现、测试并上线吧”
- Decision: 实现并发布 PD-067/PD-068 已验证方案：六步进度独立展示 Event Alignment；Align 使用统一 64K 最终输入/32K 输出包络、业务载荷只出现一次、Thinking 关闭、180 秒超时；超时或结构失败时父组标记 superseded 并按完整 conversation 稳定二分，单 conversation 叶子最多再尝试一次；成功 conversation 立即持久化并在恢复时复用。ASR 投影采用单事务批量落库并启用 SQLite busy timeout，避免并发写锁掩盖根因。活动请求首帧直接显示实际已等待时长，ASR 行使用 provider 内部序号/总数。发布不得自动重试或改写 `EV-20260923-E65A`，不得产生新的供应商调用。
- Consequences: 更新 Delta Spec、设计、任务、V1.19 原型与正式页面；完成定向/全量测试、Change gate、独立验收、CI/CD、生产健康与部署 SHA 核对后才可声明上线。
- Verification: 独立验收 PASS；131 项定向与 278 项全量测试、Ruff、Mypy、前端构建及双视口正式路由检查通过。提交 `6f40a1ad3ac05f48f18d3d14f284d68da229fea1` 通过 CI `35831058133` 与生产部署 `35831260997`，容器 Healthy、公开 `/health` 返回 `status=ok`。部署后只读核对 E65A 仍为 `partially_failed`，更新时间停留在部署前的 `2026-09-23T05:49:14+00:00`，8 个 Pass 2 失败组与 30 个失败 Case 未被自动重试；本次发布未产生供应商调用。
