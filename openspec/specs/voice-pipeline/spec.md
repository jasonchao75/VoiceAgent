# Voice Pipeline Specification

## Purpose

定义浏览器实时语音会话中 ASR、LLM、TTS 的异步流式编排、打断与终止、provider-neutral 指标、历史采集和会话级语速控制行为。

## Requirements

### Requirement: Asynchronous streaming pipeline

系统 MUST 通过异步流式 Pipeline 处理浏览器音频输入、统一 ASR、对话上下文、OpenAI-compatible LLM、用户选择的 TTS Provider 和浏览器音频输出，核心热路径不得使用同步阻塞 I/O。Pipeline MUST 提供统一 `ASRService` 抽象，并由 ASR Provider Registry 创建 Deepgram Flux/Nova-3、Speechmatics Realtime Enhanced、Soniox stt-rt-v5 或 AssemblyAI Universal-3.5 Pro Adapter。TTS 必须支持 Deepgram Flux 与 ElevenLabs WebSocket 双向流式服务；后续 LLM、TTS、浏览器输出和历史持久化不得依赖 ASR Provider 专属协议。

#### Scenario: Browser starts a conversation

- **WHEN** 客户端使用有效令牌建立 WebSocket 并发送音频
- **THEN** 音频和生成结果以流式方式经过 Pipeline，不要求整段音频落盘后再处理

#### Scenario: ElevenLabs is selected

- **WHEN** Bot 选择 `elevenlabs`、有效 voice/model 且会话具备 ElevenLabs Key
- **THEN** LLM token 流立即进入 TTS processor，按 Bot 的 `token` 或 `sentence` 策略持续送入 ElevenLabs WebSocket；返回的 24 kHz PCM chunk 持续送往浏览器，不等待 LLM 完整回复或完整音频

#### Scenario: ElevenLabs voice settings are applied

- **WHEN** 会话使用已保存的 ElevenLabs model 和 voice settings
- **THEN** 工厂仅将当前 model 支持的 Stability、Similarity、Style、Speed、Speaker Boost 与 Text normalization 传入 settings，将聚合策略派生的 Auto mode 传入 WebSocket 连接配置，且不改变 PCM 格式、打断或时延埋点契约

#### Scenario: ElevenLabs aggregation derives Auto mode

- **WHEN** ElevenLabs Bot 选择 `token` 或 `sentence`
- **THEN** 系统分别强制 `auto_mode=false` 或 `auto_mode=true`，页面仅展示联动结果而不提供独立开关

#### Scenario: Deepgram Flux aggregation is selected

- **WHEN** Deepgram Flux Bot 选择 `token` 或 `sentence`
- **THEN** TTS service 分别立即转发 LLM text frame 或聚合到句末再发送，不改变 Flux WebSocket 的音频流、打断与时延事件契约

#### Scenario: Deepgram remains selected

- **WHEN** Bot 选择 `deepgram_flux`
- **THEN** 系统继续使用现有 Flux TTS 行为，且不要求 ElevenLabs Key

#### Scenario: User interrupts ElevenLabs playback

- **WHEN** 用户在 ElevenLabs 仍生成或播放音频时开始说话
- **THEN** 当前合成和播放被取消，残留音频不得污染下一轮，后续会话保持可用

#### Scenario: Start a Web Call with a selected ASR provider

- **WHEN** Web Call 使用合法 Provider 配置和凭证启动
- **THEN** 16 kHz mono PCM 连续进入选定 ASR，Interim/Final 转写以公共 Frame 进入相同 LLM/TTS Pipeline

#### Scenario: Mix AssemblyAI ASR with Deepgram TTS

- **WHEN** Bot 选择 AssemblyAI ASR 和 Deepgram TTS，并分别提供有效组件凭证
- **THEN** Pipeline 通过 `ASRService` 创建 AssemblyAI Adapter，同时独立创建 Deepgram TTS；任一组件不得要求另一组件使用同一 Provider

### Requirement: Fixed opening script

配置了 Opening Script 时，系统 MUST 在客户端准备完成后直接交给 TTS 播放，并把相同内容加入助手对话上下文，不得先让 LLM 改写。

#### Scenario: Client becomes ready

- **WHEN** 会话配置包含非空 Opening Script 且客户端发送 ready 事件
- **THEN** 系统播放原始 Opening Script

### Requirement: Session termination

客户端断开、空闲超时或达到最大会话时长时，系统 MUST 取消正在进行的生成和播放工作并释放会话资源。

#### Scenario: Browser disconnects during generation

- **WHEN** 浏览器在 LLM 或 TTS 仍在工作时断开
- **THEN** 系统取消对应 Pipeline Worker

### Requirement: Provider-neutral latency metrics

所有支持的 ASR MUST 使用同一 `asr_final_latency_ms` 字段和缺失原因契约；Deepgram Flux 与 ElevenLabs TTS MUST 产生相同的其余逐轮指标与计算口径。Adapter 可以使用各自 word timing/turn event 计算 ASR Final latency，但前端和历史不得增加 Provider 专属公式。

#### Scenario: ElevenLabs completes a turn

- **WHEN** ElevenLabs 依次产生 `TTSStartedFrame`、首个 `TTSAudioRawFrame` 和浏览器首次播放回调
- **THEN** 系统按与 Deepgram Flux 相同的时间点和公式保存 TTS initial、TTS TTFT、playback 与 e2e latency

#### Scenario: ElevenLabs event semantics differ

- **WHEN** ElevenLabs SDK/Pipecat service 的原始事件与 Deepgram Flux 不同
- **THEN** ElevenLabs 适配层必须归一化为公共 TTS frame 契约，不得在历史采集或前端增加 provider 专属计算分支

#### Scenario: ElevenLabs turn is interrupted or not played

- **WHEN** ElevenLabs 响应在 LLM 首 Token、TTS 首音频或浏览器播放前被打断或会话结束
- **THEN** 对应值保存为 null，并使用与 Deepgram Flux 相同的 `incomplete_reason` 规则展示具体原因

#### Scenario: Provider timing is insufficient

- **WHEN** Provider 没有足够证据计算 Final latency
- **THEN** 系统保存 null 和具体原因，不得记录 0、猜测值或用另一 Provider 的事件近似

### Requirement: Provider-specific TTS failures

系统 MUST 对 ElevenLabs 鉴权、voice/model、不足额度、限流、超时和 WebSocket 断开进行安全分类，不得泄露 API Key 或完整 provider payload。

#### Scenario: ElevenLabs rejects the voice or credential

- **WHEN** ElevenLabs WebSocket 返回鉴权或 voice/model 错误
- **THEN** 当前会话安全失败并产生可诊断错误，日志和 API 响应不包含 Key

### Requirement: Per-turn latency decomposition

系统 MUST 按轮记录 LLM 首 Token、TTS 首音频包、服务端首音频到浏览器播放及用户停说到浏览器播放的耗时，并明确各指标是否包含浏览器链路。

#### Scenario: A complete turn finishes

- **WHEN** 一轮对话依次产生 ASR final、LLM 首 Token、TTS 首音频和浏览器首次播放事件
- **THEN** 历史详情展示 `llm_first_token_ms`、`tts_first_audio_ms`、`server_to_playback_ms` 和 `turn_to_playback_ms`

#### Scenario: Browser playback event is missing

- **WHEN** 服务端已产生 TTS 音频但未收到浏览器播放回调
- **THEN** 浏览器相关指标保存为 null 并显示“被打断”或“会话结束前未播放”等缺失原因，不得记录为 0 或仅显示破折号

#### Scenario: Flux emits transcript before user-stopped frame

- **WHEN** Flux 的 `EndOfTurn` Transcript 先于 Pipeline 的 `UserStoppedSpeakingFrame` 到达
- **THEN** 系统使用 Flux word timing 与已接收音频时钟计算 ASR final latency；无法计算时保存 null 和原因，不得把负值截断为 0

#### Scenario: Previous response leaves late frames

- **WHEN** 用户打断上一轮后，上一轮残留的 TTS frame 在新用户轮次开始后到达
- **THEN** 残留 frame 不得计入新轮次，新轮次的缺失指标必须标注实际未完成阶段

### Requirement: Non-blocking history capture

文本、指标和录音持久化 MUST NOT 在核心实时 Pipeline 中执行同步阻塞 I/O。

#### Scenario: Storage becomes slow

- **WHEN** SQLite 或录音磁盘写入明显变慢
- **THEN** 系统通过异步边界或有界后台队列处理，实时语音链路不等待同步磁盘操作

### Requirement: Reasoning latency evidence

系统 MUST 按轮保存 LLM 返回的 reasoning token 数量、实际关闭策略和验证状态，用于解释首 Token 延迟；不得保存隐藏思维链正文。

#### Scenario: Provider omits reasoning usage

- **WHEN** 一轮响应没有提供 reasoning token usage
- **THEN** 历史记录保存 `reasoning_tokens=null` 和 `unverified`，不得记录为 0 或已关闭

### Requirement: Deepgram Flux voice settings

系统 MUST 在创建 Deepgram Flux streaming TTS 连接时传入当前 Bot 的 `speed` 与 `expressivity`，且不得改变现有音频格式、文本聚合、打断和时延统计契约。

#### Scenario: Start Flux with voice controls

- **WHEN** Bot 配置 `speed=1.05`、`expressivity=1` 并启动会话
- **THEN** Flux WebSocket 使用所选 voice、Speed 和 Expressivity 建立连接，其他 Pipeline 行为保持不变

### Requirement: Provider-neutral conversational speed tool

系统 MUST 在 Bot 启用通话内语速控制时向兼容 LLM 注册本地 `set_speech_speed` 工具。LLM MUST 只选择受控 action；当前数值、调整步长、范围校验、provider 调用和结果状态 MUST 由 Pipeline 确定性执行，不得将普通助手文本作为控制 JSON 解析。

#### Scenario: Caller asks the agent to speak faster

- **WHEN** 当前有效 Speed 为 `1.0`、Bot 步长为 `0.10`，且用户明确要求说快一点
- **THEN** LLM 调用 `set_speech_speed(action="faster")`，Pipeline 计算目标 `1.1` 并在成功应用后才允许 LLM 生成确认回复

#### Scenario: Caller asks repeatedly at a provider limit

- **WHEN** 当前 Speed 已达到 provider 上限且用户再次要求加快
- **THEN** Pipeline 返回 `at_limit` 且保持当前值，LLM 不得声称语速继续增加

#### Scenario: Caller resets speed

- **WHEN** LLM 调用 `normal` 或 `configured`
- **THEN** Pipeline 分别以 `1.0` 或该通话启动时的 Bot Speed 为目标，并遵循同一 provider 应用与确认流程

#### Scenario: Tool update fails

- **WHEN** provider 拒绝、超时或连接断开
- **THEN** Pipeline 清除 pending 值、保留之前的 current Speed、返回 `failed`，并确保回复不会宣称修改成功

### Requirement: Session-scoped speed state

系统 MUST 为每次通话独立维护 immutable configured Speed、已生效 current Speed 和可空 pending Speed，并串行化并发更新。临时 Speed 不得覆盖 Bot 持久配置或泄漏到其他通话。

#### Scenario: Change speed twice in one call

- **WHEN** 通话从 configured Speed `0.95` 开始，连续两次成功执行 `faster` 且步长为 `0.10`
- **THEN** current Speed 依次为 `1.05`、`1.15`，第二次基于第一次成功值计算

#### Scenario: End a modified session

- **WHEN** current Speed 与 configured Speed 不同的通话结束，随后同一 Bot 开始新通话
- **THEN** 旧会话状态被销毁，新通话仍从 Bot 保存的 configured Speed 开始

### Requirement: Provider-specific runtime speed application

系统 MUST 通过统一会话工具将 Speed 应用到当前 TTS provider，同时保留现有音频格式、文本聚合、打断和逐轮时延统计契约。

#### Scenario: Apply speed to Flux

- **WHEN** Flux 通话计算出新的合法目标 Speed
- **THEN** 适配器在当前 `/v2/speak` WebSocket 发送 `Configure`，等待有界的成功或失败结果，并从 provider 的下一个 segment 边界采用新值

#### Scenario: Apply speed to ElevenLabs non-v3

- **WHEN** ElevenLabs Flash、Turbo 或 Multilingual 通话计算出新的合法目标 Speed
- **THEN** 适配器在后续文本消息的完整 `voice_settings` 中使用新 Speed，同时保持其他 Voice settings 不变；已缓冲或已生成音频不被重写

#### Scenario: Request speed control with Eleven v3

- **WHEN** 通话使用 Eleven v3 且用户要求改变语速
- **THEN** 系统不得伪造成功或将 prompt pacing 当作数值 Speed；agent 应明确说明当前模型不支持精确通话内语速调整

#### Scenario: Custom LLM rejects tools

- **WHEN** Bot 启用该能力但 Custom OpenAI-compatible endpoint 不支持或拒绝结构化 tool calling
- **THEN** 会话以可诊断错误失败或禁用该能力并明确告知客户端，不得静默解析普通文本来执行控制

### Requirement: Conversational speed diagnostics

系统 MUST 为每次语速控制尝试记录不含敏感信息的 provider、action、旧值、目标值、最终状态和耗时；该事件不得改变既有逐轮 latency 字段或计算公式。

#### Scenario: Inspect a failed speed update

- **WHEN** provider 返回失败或更新超时
- **THEN** 日志或诊断事件能够区分 rejection、timeout、disconnect 与 unsupported，且不包含 API Key 或完整 provider payload

### Requirement: Normalized ASR turn contract

每个 Adapter MUST 把供应商事件归一化为 User Started、Interim Transcript、Final Transcript、User Stopped、Interruption 和安全 Error。系统本期 MUST 支持 `provider_native` 与 `off` 两种 Turn Detection Source；`off` MUST 表示关闭语义、声学或模型原生的智能 Turn Detection并保留 VAD/固定静音切分，不得解释为关闭自动轮次。同一会话只有一个来源可以最终提交用户 Turn，Self-developed 不在本 Change 范围。

#### Scenario: Native endpoint finalizes a turn

- **WHEN** 选定 Provider 的原生 Turn Detection 确认用户结束
- **THEN** Pipeline 只提交一个 Final 用户 Turn，随后触发一次 LLM 请求

#### Scenario: Turn Detection is Off

- **WHEN** 当前 Provider/model 的 Turn Detection Source 为 `off`
- **THEN** Adapter 必须关闭智能 Turn 判定并保留该 Provider 可证明的 VAD/固定静音边界；固定静音边界可自动触发一次完整用户 Turn，普通 ASR 分块 Final 不得被误解释为轮次结束

#### Scenario: Use Nova-3 with Turn Detection Off

- **WHEN** Deepgram Nova-3 会话启动
- **THEN** Adapter 固定使用 `off`，提交正数 `endpointing` 静音阈值并只以 `speech_final=true` 收口完整用户 Turn；普通分块 Final 不得自动触发 LLM/TTS

#### Scenario: Use Speechmatics with Turn Detection Off

- **WHEN** Speechmatics 的 Turn Detection Source 为 `off`
- **THEN** Adapter 必须提交 `end_of_utterance_mode=FIXED` 与正数 `conversation_config.end_of_utterance_silence_trigger`，并以固定静音后的 `EndOfUtterance` 收口；不得把阈值设为会关闭检测的 `0`

#### Scenario: Soniox requires native endpoint detection

- **WHEN** Soniox `stt-rt-v5` 会话启动
- **THEN** Adapter 必须启用 semantic endpoint detection，并只以 `<end>` 收口自动用户 Turn；Off 配置必须在保存或启动前被拒绝

#### Scenario: AssemblyAI requires native turn detection

- **WHEN** AssemblyAI Universal-3.5 Pro Realtime 会话启动
- **THEN** Adapter 必须使用其标点/语音上下文 End-of-Turn 与 max-silence fallback；由于 Provider API 不提供 VAD-only 模式，Off 配置必须在保存或启动前被拒绝

#### Scenario: User interrupts agent playback

- **WHEN** Provider 检测到用户在 Agent 播放期间开始说话
- **THEN** 当前播放和生成按现有 barge-in 契约取消，新用户 Turn 不得混入上一轮残留文本或音频

### Requirement: AssemblyAI conversation context

AssemblyAI 会话 MUST 在同一 WebSocket 内使用 Opening Script 初始化 Agent Context。LLM 文本 MUST 保持流式进入 TTS；Assistant Turn Aggregator MUST 在独立分支为每个 Agent Turn 发送且只发送一次 `UpdateConfiguration.agent_context`，内容仅使用本轮 Agent 回复，不得等待 TTS 音频返回或播放完成，也不得依据 Web/SIP 播放游标截取。服务端自动 carryover 只允许来自该连接的 Final 用户 Turn。

#### Scenario: First user turn follows the opening

- **WHEN** AssemblyAI Web Call 配置非空 Opening Script 并开始第一轮用户音频
- **THEN** Opening Script 已作为 `agent_context` 提供，且不会被伪装成用户转写

#### Scenario: Agent context update fails

- **WHEN** `UpdateConfiguration.agent_context` 失败但基础 WebSocket 仍可转写
- **THEN** 基础 ASR 可继续，该轮记录 `context_applied=false` 和安全原因，不得宣称 Context 已生效

#### Scenario: Context update and TTS run concurrently

- **WHEN** LLM 流式产生 Assistant 文本，并且 Aggregator 形成可提交的 Context 快照
- **THEN** 文本块继续进入 TTS，Context 更新独立发送且不得等待首包或末包 TTS 音频

#### Scenario: Agent playback is interrupted

- **WHEN** 用户在本轮 Agent 回复播放期间发起 barge-in
- **THEN** 系统仍以本轮 Agent 回复作为唯一一次 `agent_context` 更新内容，不得按实际播放前缀发送第二次修订

#### Scenario: Reconnect clears provider context

- **WHEN** AssemblyAI WebSocket 断开并建立新连接
- **THEN** 系统按当前会话可证明的 Opening/最近 Agent Turn 重新初始化，且不得假设 Provider 保留旧连接的用户历史
