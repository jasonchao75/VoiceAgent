# Decision Log

## Status

- Recorded decisions: 22
- Last reviewed: 2026-09-28

## Decisions

### D-001：Change 范围为三家实时 ASR 产品接入

- Status: Confirmed
- Date: 2026-09-24
- Source question: Scope selection after deleting the previous benchmark Change
- Decision owner: Product owner
- Source thread/message: Current Codex task, user message on 2026-09-24 beginning “重新评估A”
- Confirmation quote: “重新评估A，三家实时 ASR 产品接入 Change”
- Decision: 新 Change 聚焦 Speechmatics、Soniox、AssemblyAI 实时产品接入，并以现有 Deepgram Flux 为兼容基线；不创建横向评测 Change。
- Reason: 用户明确选择产品接入范围 A。
- Consequences: Benchmark、排名和评测 UI 不进入本 Change。
- Updated artifacts: `proposal.md`、PRD、Delta Specs、design、tasks、prototype。
- Verification: Change 文件只描述产品接入，不包含横向榜单功能。

### D-002：严格执行 PRD 与原型先行

- Status: Confirmed
- Date: 2026-09-24
- Source question: Delivery sequence for the new Change
- Decision owner: Product owner
- Source thread/message: Current Codex task, same user message on 2026-09-24
- Confirmation quote: “要严格符合先写prd+原型的方式来创建。不要做别的。”
- Decision: 本轮只创建 PRD、OpenSpec 规划与高保真原型；User Gate 1 确认前不改正式产品代码、不接依赖、不调用外部服务。
- Reason: 用户明确要求规划和视觉基线先行。
- Consequences: 所有实现任务保持未开始；原型为 Draft，确认后才冻结。
- Updated artifacts: PRD、`proposal.md`、`tasks.md`、`prototypes/*`、`verification/*`。
- Verification: Git diff 不包含 `src/`、`frontend/`、依赖或数据库迁移改动。

### D-003：Turn Detection 作为可切换统一策略层

- Status: Superseded by D-008
- Date: 2026-09-24
- Source question: Streaming ASR 与自研 Turn Detection 是否可以解耦
- Decision owner: Product owner
- Source thread/message: Current Codex task, user message on 2026-09-24 beginning “1.为什么无法支持AssemblyAI ASR+Deepgram TTS混搭”
- Confirmation quote: “Turn Detection以后我想自己做一个统一层，但是也可以支持使用各自provider-native Turn detection。支持灵活切换。”
- Decision: VoiceAgent 提供独立 `TurnDetectionStrategy`，支持 `provider_native` 与 `voiceagent_unified`；默认使用 Provider-native，同一会话仅一个策略拥有最终 Turn 裁决权。
- Reason: 流式识别与 Turn 判定是可解耦职责，产品既要保留供应商能力，也要支持未来统一控制。
- Consequences: Catalog 声明模式能力；UI 提供来源选择；Adapter 把统一层结束信号映射成各家收口命令；测试矩阵覆盖两种模式。
- Updated artifacts: PRD、`design.md`、`tasks.md`、`specs/voice-pipeline/spec.md`、prototype、Gate 1 文件。
- Verification: 官方资料确认 Deepgram Flux 可用 `eot_threshold=1.0` + `ForceEndTurn`；当前 Pipecat 封装仍需实现期验证。

### D-004：AssemblyAI Context 与 TTS 并行分发

- Status: Confirmed
- Date: 2026-09-24
- Source question: Assistant Turn 的 TTS 与 ASR Context 时序
- Decision owner: Product owner
- Source thread/message: Current Codex task, same user message on 2026-09-24
- Confirmation quote: “LLM向下游发送TTS和向ASR发送Update，是互不冲突的”
- Decision: LLM 文本继续流式进入 TTS；Assistant Turn Aggregator 独立形成 Context 快照并发送 AssemblyAI `UpdateConfiguration.agent_context`，不等待 TTS 音频返回或播放完成。
- Reason: Context 是下一用户 Turn 的识别输入，TTS 是当前 Assistant Turn 的输出，两者无数据依赖。
- Consequences: Context 失败不阻塞 TTS；每个 Agent Turn 的 Context 内容与更新次数遵循 D-006。
- Updated artifacts: PRD、`design.md`、`specs/voice-pipeline/spec.md`、prototype 说明、Gate 1 文件。
- Verification: AssemblyAI 官方资料确认 `agent_context` 可在同一 WebSocket 内动态更新且作用于后续 Turn。

### D-005：Pipeline 必须显式依赖 ASR Service 抽象

- Status: Confirmed
- Date: 2026-09-24
- Source question: 多供应商 ASR 的客户端抽象边界
- Decision owner: Product owner
- Source thread/message: Current Codex task, same user message on 2026-09-24
- Confirmation quote: “我们的客户端应该是有一个ASR服务抽象层的是吧。”
- Decision: Browser 只负责传输 PCM；服务端 Pipeline 只面向 `ASRService`，由 Registry 选择 Provider Adapter，Turn Detection 与 Context Bridge 通过 ASR Service 的公共控制面协作。
- Reason: 供应商协议、终点命令和动态配置不应泄漏到 Pipeline 或浏览器。
- Consequences: 时序图、数据流、Delta Spec 与任务均明确 `ASRService → Registry → Adapter` 层次。
- Updated artifacts: PRD、`design.md`、`tasks.md`、`specs/voice-pipeline/spec.md`。
- Verification: Change 规格禁止下游依赖 Provider 专属协议。

### D-006：AssemblyAI Agent Context 每个 Agent Turn 只使用本轮回复

- Status: Confirmed
- Date: 2026-09-24
- Source question: AssemblyAI Agent Context 的更新粒度与 barge-in 文本边界
- Decision owner: Product owner
- Source thread/message: Current Codex task, user message on 2026-09-24 beginning “对的，这次是对了”
- Confirmation quote: “agent-context仅使用本轮Agent的回复，不追求实际播放文本前缀。”
- Decision: `agent_context` 每个 Agent Turn 只更新一次，内容来自该 Turn 的 Agent 回复；不依据 TTS 音频、浏览器或 SIP 播放游标截取，不进行同一 Turn 内的渐进式高频更新。
- Reason: `agent_context` 是下一用户 Turn 的识别上下文，不是实际播放审计记录；官方推荐在每次 Agent reply 后刷新最近一次回复。
- Consequences: Assistant Turn Aggregator 在本轮回复形成后独立发送一次 `UpdateConfiguration.agent_context`；barge-in 不触发基于实际播放前缀的二次修订。播放游标只服务于打断控制、历史和体验指标。
- Updated artifacts: PRD、`design.md`、`specs/voice-pipeline/spec.md`、`tasks.md`、prototype 文案、Gate 1 文件。
- Verification: Static review against AssemblyAI Conversation Context guidance; external-real timing remains unverified.

### D-007：Provider Key 全局维护并由所有 Bot 复用

- Status: Superseded by D-015
- Date: 2026-09-24
- Source question: Provider Key 是按 Bot 保存还是全局复用
- Decision owner: Product owner
- Source thread/message: Current Codex task, user message on 2026-09-24 beginning “改成全局维护吧”
- Confirmation quote: “改成全局维护吧。”
- Decision: Provider Credential 按 `component + provider` 全局保存一次，所有选择该组件/Provider 的 Bot 自动引用；Bot 不再复制或拥有 Provider Key。
- Reason: 避免相同 Provider Key 在多个 Bot 中重复维护，并使凭证轮换一次影响所有引用 Bot。
- Consequences: ASR Drawer 的 Key 区域必须位于 Advanced 之后并沿用现网页交互：单一密码输入、显示动作和“Save API key”开关；已有全局 Key 时留空即自动沿用，不出现“Use saved key”按钮。替换全局 Key 会影响所有引用 Bot，页面必须提示作用范围；Bot 配置可独立保存，但缺少当前全局 Key 时禁止启动真实会话。
- Updated artifacts: proposal、PRD、`design.md`、`specs/bot-config/spec.md`、`tasks.md`、prototype、Gate 1 文件。
- Verification: Static comparison with the current Bot editor DOM and persistence flow; formal migration and runtime behavior remain unimplemented.

### D-008：本期 Turn Detection Source 仅提供 Provider native 与 Off

- Status: Confirmed
- Date: 2026-09-24
- Source question: Current Turn Detection Source options and future self-developed mode
- Decision owner: Product owner
- Source thread/message: Current Codex task, user message on 2026-09-24 beginning “另外，Turn Detection Source现在只有”
- Confirmation quote: “Turn Detection Source现在只有Provider native和‘Off’是可选项，其他的还没有，后面再考虑增加Self-development这一可选项。现在没有，你在原型和prd里面也要更新这一说明。”
- Decision: 本 Change 的 Turn Detection Source 只定义 `provider_native` 与 `off`。`self_developed` 仅作为未来方向，不出现在本期 UI、配置枚举或实现任务中；`off` 的 Provider 能力判定与映射由 D-009 细化。
- Reason: 当前产品尚无可用的自研 Turn Detection，实现与产品入口必须保持一致，不能把未来能力伪装成已支持选项。
- Consequences: 移除 `voiceagent_unified` 选项、统一策略参数和当前实现任务；Native 参数仅在 `provider_native` 下展示。
- Updated artifacts: PRD、proposal、`design.md`、`tasks.md`、Delta Specs、prototype、Gate 1 review、UI verification files。
- Verification: Prototype interaction and Change consistency validation; runtime implementation remains pending after User Gate 1.

### D-009：Off 表示关闭 Provider Turn Detection，并按模型能力开放

- Status: Superseded by D-012
- Date: 2026-09-24
- Source question: Meaning and Provider support of Turn Detection Off
- Decision owner: Product owner
- Source thread/message: Current Codex task, user message on 2026-09-24 beginning “Off指的是”
- Confirmation quote: “Off指的是，关闭Turn detection。相当于不启用资源方的相关按钮。不过你得看看是不是所有的都支持这个？是不是soniox就不支持关闭Turn Detection”
- Decision: `off` 表示不启用供应商的 Turn Detection 能力，不是 VoiceAgent 拦截或重解释 Provider Final。Off 由 Provider/model capability 控制；不得用近似参数伪装为真正关闭。各模型在关闭后的端到端可运行性必须单独判定。
- Reason: Speechmatics `end_of_utterance_silence_trigger=0` 可关闭检测；Deepgram Flux 即使 `eot_threshold=1.0` 仍有 `eot_timeout_ms` 兜底；AssemblyAI U3.5 Pro 官方只提供内置 Turn 调节，没有关闭参数。Soniox 虽可设 `enable_endpoint_detection=false`，但随后不会自动返回 `<end>`，当前产品缺少 Self-developed Turn Detection，因此本期不开放 Off。
- Consequences: Catalog 增加 Provider/model 级 Off 能力、端到端可运行性与不可用原因；下拉仅有 Native/Off 两种定义，但按当前模型能力禁用不可运行选项。Off 时隐藏并不提交该 Provider 的 Native Turn 参数；Self-developed 仍不出现。
- Updated artifacts: PRD、`design.md`、Delta Specs、prototype、Gate 1 review、UI verification files。
- Verification: Static review against current official Provider documentation; external-real mapping remains pending.

### D-010：Deepgram 增加 Nova-3，并与 Flux 使用独立参数契约

- Status: Confirmed
- Date: 2026-09-24
- Source question: Add Deepgram Nova-3 model and distinguish it from Flux
- Decision owner: Product owner
- Source thread/message: Current Codex task, user message on 2026-09-24 beginning “另外，Deepgram的Nova3”
- Confirmation quote: “Deepgram的Nova3不支持Turn detection，你能不能额外对接Nova3模型？（Nova3模型可配参数和Flux的不一样，你要仔细对比。）”
- Decision: Deepgram Provider 增加 `nova-3` 模型。Flux 继续使用 V2 Conversational API 与模型原生 EOT 参数；Nova-3 使用 V1 Streaming API、`language` 和 Nova-3 专属识别参数，禁止复用 Flux 的 EOT 与 `language_hint` 配置。
- Reason: Deepgram 官方把 Flux 定义为原生 Turn Detection 模型，把 Nova-3 定义为不含模型原生 Turn Detection 的通用 ASR；两者 API 版本、语言控制和可配参数不同。
- Consequences: Deepgram Model 切换会替换 Language、Turn Detection Source 能力与 Advanced 面板。Nova-3 的 Turn Detection Source 固定为 Off，不把 V1 `endpointing`/`speech_final` 命名或呈现为 Provider-native Turn Detection；产品默认仍为现有 Flux。
- Updated artifacts: PRD、proposal、`design.md`、Delta Specs、`tasks.md`、prototype、Gate 1 与 UI verification files。
- Verification: Static review against Deepgram Live Audio、Models & Languages、Endpointing、Utterance End 与 Keyterm official documentation; external-real verification remains pending.

### D-011：Soniox 固定 Provider native；Nova-3 固定 Off

- Status: Confirmed
- Date: 2026-09-24
- Source question: Final capability mapping for Soniox and Deepgram Nova-3 Turn Detection Source
- Decision owner: Product owner
- Source thread/message: Current Codex task, user message and two browser comments on 2026-09-24 beginning “Soniox不允许Off”
- Confirmation quote: “Soniox不允许Off。禁用。另外Nova3你做的Turn Detection Source选项也不对”；“Nova-3里面，这个turn detector开关不应该是Off吗？无法选provider native啊，因为就没有”；“这个不用展示啊，和上面合并逻辑就好”。
- Decision: Soniox `stt-rt-v5` 的 Turn Detection Source 固定为 `provider_native`，Off 禁用。Deepgram Nova-3 的 Turn Detection Source 固定为 `off`，Provider native 禁用。Nova-3 不展示独立的“无 Flux semantic Turn Detection”Advanced 提示卡，相关说明合并到 Turn Detection Source 帮助文案。
- Reason: 产品层 Turn Detection Source 只表达可被用户选择的完整轮次能力；Soniox 对话必须依赖 `<end>`，Nova-3 不具备本产品定义下的 Provider-native Turn Detection。
- Consequences: Catalog 必须提供每个 Provider/model 的 allowed/default source，而不是仅提供 supports_off 布尔值；Nova-3 不展示或提交 Flux 类智能 Turn Detection 参数，具体 Off 的 VAD/固定静音映射由 D-012 纠正。
- Updated artifacts: PRD、`design.md`、Delta Specs、`tasks.md`、prototype、Gate 1 与 UI verification files。
- Verification: Prototype interaction and Change consistency validation; external-real behavior remains unverified.

### D-012：Off 关闭智能判断但保留 VAD/固定静音切分

- Status: Confirmed
- Date: 2026-09-24
- Source question: Exact product meaning of Turn Detection Off and Provider mappings
- Decision owner: Product owner
- Source thread/message: Current Codex task, user messages on 2026-09-24 beginning “你奶奶的，我说的Turn detection off的概念” and “你给我牢牢记住这个事儿”
- Confirmation quote: “Turn detection off的概念是‘只用VAD来切’，不用senmatic和声学特征来切。”；“不能自己瞎猜。”
- Decision: `off` 关闭语义、声学或模型原生的智能 Turn Detection，但必须保留 VAD/固定静音切分并继续自动提交完整用户 Turn。Speechmatics Off 映射为 `end_of_utterance_mode=FIXED` 与正数 `conversation_config.end_of_utterance_silence_trigger`；Nova-3 Off 保留正数 V1 `endpointing`。`0` 或 `false` 这类会完全移除自动边界的值不得用于本产品 Off。
- Reason: 产品需要在智能 Turn Detection 与确定性静音切分之间切换，而不是在自动对话与无轮次边界之间切换。Speechmatics 官方说明 FIXED 使用固定静音阈值，阈值 `0` 会完全禁用检测；Deepgram Nova-3 的 V1 `endpointing` 可提供固定静音后的 `speech_final=true`。
- Consequences: Speechmatics 选择 Off 时仍展示并要求正数 Silence trigger，模式固定为 Fixed；Nova-3 恢复 Endpointing silence；所有关于 Off“不自动提交 Turn”的规格均作废。Soniox 因无可用 VAD-only `<end>` 映射继续禁用 Off。AssemblyAI Universal-3.5 Pro Realtime 的 Provider API 仍使用标点/语音上下文内置 Turn Detection，`max_turn_silence` 只是兜底且没有 Provider-side VAD-only 开关，因此继续禁用 Off；Pipecat/local VAD + `ForceEndpoint` 属未来 Self-developed/external 范围。
- Updated artifacts: PRD、proposal、`design.md`、Delta Specs、`tasks.md`、prototype、Gate 1 与 UI verification files。
- Verification: Static review against current Speechmatics fixed-silence documentation, Deepgram V1 endpointing documentation and AssemblyAI Universal-3.5 Pro Realtime documentation; external-real behavior remains unverified.

### D-013：AssemblyAI Mode 自动带入且允许修改三个 Turn 参数

- Status: Confirmed
- Date: 2026-09-27
- Source question: AssemblyAI Mode 与细粒度 Turn 参数的产品交互
- Decision owner: Product owner
- Source thread/message: Current Codex task, user message on 2026-09-27 beginning “不采用Mode-only”
- Confirmation quote: “不采用Mode-only，需要能够选择Mode之后，自动带入这些min silence /max silence/ Interruption delay 参数。然后支持自主修改。”
- Decision: 选择 `min_latency`、`balanced` 或 `max_accuracy` 时，页面立即用该 Mode 的官方预设覆盖并回填 `min_turn_silence`、`max_turn_silence` 和 `interruption_delay`；回填后用户可修改任意值。保存及运行时同时提交 Mode 和三个最终显式值，页面以“已修改”而非 Provider 原生 `Custom` Mode 表达偏离预设。
- Reason: 用户需要预设起点与细粒度可调能力，同时要避免切换 Mode 后旧值静默保留、造成名称与实际行为不一致。
- Consequences: Mode 变更会重置三个字段，手动修改则标记当前 Mode 已自定义；`vad_threshold` 不属于这三个 Mode 预设字段，作为独立的内置 Silero VAD 灵敏度保留。
- Updated artifacts: PRD、`design.md`、`specs/bot-config/spec.md`、`tasks.md`、prototype 及 Gate 1 文件。
- Verification: Static review against AssemblyAI Universal-3.5 Pro Realtime Mode, Turn Detection and VAD guidance; prototype interaction and external-real behavior require separate verification.

### D-014：User Gate 1 通过并冻结当前 PRD 与原型

- Status: Confirmed
- Date: 2026-09-27
- Source question: User Gate 1 approval for the current PRD and prototype baseline
- Decision owner: Product owner
- Source thread/message: Current Codex task, user message on 2026-09-27
- Confirmation quote: “以当前 PRD 和原型通过 User Gate 1，并授权冻结基线、进入开发”
- Decision: 以当时的 PRD 与 `prototypes/index.html` 通过 User Gate 1，授权按照已确认 Delta Specs、design 与 tasks 进入正式开发；凭证范围随后由 D-015 明确修订，当前唯一有效的基线版本与校验值以 D-015 为准。
- Reason: 产品负责人已明确确认当前需求契约和视觉交互基线。
- Consequences: 后续实现必须遵循冻结规格与原型；任何有意行为或视觉偏离都必须先更新 Change 并重新确认。User Gate 2 仍保留为最终产品验收。
- Updated artifacts: PRD、`proposal.md`、`tasks.md`、`prototypes/README.md`、`verification/gate-1-review.md`、`verification/ui-checklist.md`、`verification/delivery-status.json`。
- Verification: SHA-256 重新计算必须与 D-015 的唯一有效冻结值一致；Change verifier 必须无结构或基线错误。

### D-015：本期 Provider Key 按 Bot、按组件保存

- Status: Confirmed
- Date: 2026-09-27
- Source question: 是否必须使用全局 Key，还是先允许每个 Bot 保存自己的 Key
- Decision owner: Product owner
- Source thread/message: Current Codex task, user message on 2026-09-27 beginning “为什么一定要有一个全局的”
- Confirmation quote: “就先在bot里面保存不行吗？每个bot可以有一个key啊”
- Decision: 本期不建设全局 Provider Connection 或资源管理页。凭证归属于 Bot，并按 `component + provider` 分开加密保存；不同 Bot 可以使用不同 Key。AssemblyAI ASR + Deepgram TTS 等混搭 Bot 分别保存各组件对应 Provider 的 Key，禁止跨组件误用。未来资源管理页再负责可复用资源和迁移。
- Reason: 全局复用不是技术必需，且用户明确要求把资源管理延后，先保留 Bot 级凭证边界。
- Consequences: 取消 Q-006 和全局凭证迁移；保留现有 Bot 密文兼容性并扩展为 Provider-aware 的 ASR/TTS/LLM Bot 凭证。Key 区域仍位于组件 Advanced 之后，留空保留当前 Bot 已存 Key；替换只影响当前 Bot。
- Updated artifacts: proposal、PRD、`design.md`、`specs/bot-config/spec.md`、`tasks.md`、prototype、Gate/UI verification files。
- Verification: Bot A/B 使用不同 Key 的持久化与会话快照测试；混搭组件不得共享错误凭证；D-015 当时的原型 hash 已由用户随后明确确认的 D-019/D-020 视觉修订取代，当前唯一有效值见 `prototypes/README.md`。

### D-016：安装锁定版本的 Speechmatics SDK 依赖

- Status: Confirmed
- Date: 2026-09-27
- Source question: 是否允许为项目锁定的 Pipecat 1.8.1 安装 Speechmatics extra
- Decision owner: Product owner
- Source thread/message: Current Codex task, user message on 2026-09-27
- Confirmation quote: “允许安装对应依赖”
- Decision: 将生产依赖声明更新为 `pipecat-ai[deepgram,google,openai,runner,speechmatics,websocket]==1.8.1`，安装并锁定其 Speechmatics SDK 传递依赖；不升级 Pipecat，不授权真实或付费 ASR 调用。
- Reason: Speechmatics Adapter 的本地配置构造和运行需要官方 SDK extra。
- Consequences: `pyproject.toml` 与 `requirements.lock` 增加 Speechmatics SDK 依赖；外部真实流式测试仍须另行逐次授权。
- Updated artifacts: `pyproject.toml`、`requirements.lock`、delivery status、Adapter tests。
- Verification: 本地 import、无网络构造、`split_sentences` 兼容回归及依赖一致性检查。

### D-017：授权四家 ASR external-real 最小流式验证

- Status: Confirmed
- Date: 2026-09-28
- Source question: 是否授权发送受控合成音频以完成 Gate 2 前的 external-real 验证
- Decision owner: Product owner
- Source thread/message: Current Codex task, user message on 2026-09-28
- Confirmation quote: “授权四家各调用一次、仅用合成音频、每家 ≤60 秒、总费用上限 USD 1，首次鉴权/网络/计费错误即停止”
- Decision: 允许针对 Speechmatics、Soniox、AssemblyAI 和 Deepgram Nova-3 各执行一次真实流式 ASR 调用；仅发送本地合成的 16 kHz PCM 语音，每家最多 60 秒，累计费用不得超过 USD 1。
- Stop condition: 任一调用首次出现鉴权、网络或计费错误时立即停止，不调用后续 Provider；不自动重试。
- Consequences: 调用前必须通过本地 Key、音频格式、时长与费用预检；证据不得包含密钥或原始上游响应。
- Updated artifacts: `verification/delivery-status.json`、external-real 证据文档。
- Verification: All four authorized Providers completed bounded external-real streams with synthetic 16 kHz PCM; normalized results are recorded in `verification/external-real-asr-2026-09-28.md`.

### D-018：继续 external-real 授权并允许有界重试

- Status: Confirmed
- Date: 2026-09-28
- Source question: Speechmatics 首次网络错误触发 D-017 停止条件后，是否允许修复并继续
- Decision owner: Product owner
- Source thread/message: Current Codex task, user message on 2026-09-28
- Confirmation quote: “继续授权，可以重试最多5次”
- Decision: 继续 D-017 的四家 external-real 验证，保持仅合成音频、每家不超过 60 秒、累计费用不超过 USD 1；在首次已停止调用之外，允许总计最多 5 次额外重试。
- Execution rule: 每次失败后先完成本地诊断与针对性修复，再决定是否消耗下一次重试；禁止无差别自动连续请求。
- Consequences: D-017 的“首次错误即停止”已对后续执行解除，其余数据、时长、接收方与费用边界不变。
- Updated artifacts: `verification/delivery-status.json`、external-real 证据文档。
- Verification: Speechmatics passed after three targeted retries, Soniox passed after one targeted retry, and Deepgram Nova-3 plus AssemblyAI passed on their first calls; four of the five authorized additional retries were consumed.

### D-019：账号 Catalog 刷新使用紧凑次级按钮

- Status: Confirmed
- Date: 2026-09-28
- Source question: User Gate 2 页面评审中的 Refresh account catalog 视觉调整
- Decision owner: Product owner
- Source thread/message: Current Codex task, user message on 2026-09-28
- Confirmation quote: “A。”
- Decision: Speechmatics 与 Soniox 的 `Refresh account catalog` 使用带刷新图标的紧凑次级描边按钮；宽度随内容，提供 hover、loading 和 disabled 状态，说明文字保留在按钮下方。
- Reason: 该操作是低频账号能力同步，不应与保存 Bot 等主操作竞争视觉层级，同时需要比浏览器默认按钮更清晰、精致。
- Consequences: 更新冻结原型、正式页面样式、按钮忙碌态与桌面/窄屏回归证据；不改变 Catalog API 或持久化行为。
- Updated artifacts: PRD、prototype、formal UI、UI tests、verification evidence。
- Verification: 正式 UI、原型及 loading/disabled 状态已实现；桌面与窄屏浏览器回归通过。D-019/D-020 共同修订后的唯一原型 SHA-256 为 `b6835ca7da9f0ee120081bb682a319f60be296029800c6b83e28a111b400b277`。

### D-020：Soniox 与 AssemblyAI 语言提示同时显示代码和语言名

- Status: Confirmed
- Date: 2026-09-28
- Source question: User Gate 2 页面评审中的 language hint 可读性调整
- Decision owner: Product owner
- Source thread/message: Current Codex task, same user message on 2026-09-28
- Confirmation quote: “另外，能不能把soniox和assembly的language hint后面的语言代码加一个括号，说明是什么语言呢？两个字母看着不方便”
- Decision: Soniox 与 AssemblyAI 的 Language hints/steering 选项显示为 `代码（英文语言名）`，例如 `ar (Arabic)`；Soniox 原有搜索可匹配代码或语言名。保存、校验和发送给 Provider 的值仍为原始语言代码。
- Reason: 两字母代码难以快速理解，同时显示代码与名称可提升配置效率且不改变 Provider 契约。
- Consequences: 语言显示名由服务端 Catalog 提供，Browser 不维护 Provider 专属硬编码映射；账号 Catalog 刷新后仍保留 Soniox 返回的语言名称。
- Updated artifacts: PRD、Delta Spec、design、prototype、server Catalog、formal UI、tests、verification evidence。
- Verification: Server Catalog labels、Provider 名称回退、Soniox code/name 搜索、18 个 AssemblyAI code 唯一性及 raw-code 提交、桌面/窄屏 UI 回归通过。D-019/D-020 共同修订后的唯一原型 SHA-256 为 `b6835ca7da9f0ee120081bb682a319f60be296029800c6b83e28a111b400b277`。

### D-021：User Gate 2 最终产品验收通过

- Status: Confirmed
- Date: 2026-09-28
- Source question: D-019/D-020 修订并通过独立验收后，是否通过 User Gate 2
- Decision owner: Product owner
- Source thread/message: Current Codex task, user message on 2026-09-28
- Confirmation quote: “通过User Gate2”
- Decision: 接受 `add-streaming-asr-providers` 的最终产品行为、D-019/D-020 视觉与可读性修订以及现有验收证据；授权将 Delta Specs 合并至主规格并归档 Change。
- Reason: 产品负责人完成最终页面评审并明确通过 User Gate 2。
- Consequences: `product_acceptance` 更新为 accepted；合并三份 Delta Specs，归档至 `openspec/changes/archive/2026-09-28-add-streaming-asr-providers/`。后续行为调整需开启新 Change。
- Updated artifacts: `verification/gate-2-review.md`、`verification/delivery-status.json`、主规格、归档 Change。
- Verification: 归档前后运行 Change/OpenSpec validation；主规格必须反映最终实现，归档目录保留完整决策与证据。

### D-022：授权完整依赖链推送 main 并触发生产上线

- Status: Confirmed
- Date: 2026-09-28
- Source question: 是否允许把本地 `main` 的三个提交（含 224 文件完整依赖链）推送至默认分支并触发生产部署
- Decision owner: Product owner
- Source thread/message: Current Codex task, user message on 2026-09-28
- Confirmation quote: “确认将本地 main 的 3 个提交（含 224 文件完整依赖链）推送到 origin/main 并触发生产上线。”
- Decision: 授权推送当前本地 `main` 的三个提交，其中 `5560514` 包含已验收的 Voice Bot 页面重构、评测 Change 归档迁移与多 Provider Streaming ASR Change 完整依赖链；推送后允许 GitHub CI/CD 自动部署生产环境。
- Reason: 该提交边界无法在不破坏已验证运行状态的情况下安全拆分，且默认分支推送会直接影响共享生产环境，因此需要产品负责人对精确范围再次授权。
- Consequences: 推送前保留无关本地模型、客户语料、Excel、评测临时资料和下载脚本为未提交状态；只有远程 CI、生产镜像构建、部署任务和公网冒烟测试全部通过后才能宣称上线完成。
- Updated artifacts: `verification/delivery-status.json`、发布提交记录。
- Verification: `origin/main` 更新、GitHub Actions `VoiceAgent CI` 与 `Deploy VoiceAgent Platform` 成功、公网健康和产品页面冒烟检查。
