# Voice Pipeline Specification

## Purpose

定义浏览器实时语音会话中 ASR、LLM、TTS 的核心编排行为。

## Requirements

### Requirement: Asynchronous streaming pipeline

系统 MUST 通过异步流式 Pipeline 依次处理浏览器音频输入、Deepgram Flux STT、对话上下文、OpenAI-compatible LLM、用户选择的 TTS provider 和浏览器音频输出。TTS 必须支持 Deepgram Flux 与 ElevenLabs WebSocket 双向流式服务，核心热路径不得使用同步阻塞 I/O。

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

### Requirement: Fixed opening script

配置了 Opening Script 时，系统必须在客户端准备完成后直接交给 TTS 播放，并把相同内容加入助手对话上下文，不得先让 LLM 改写。

#### Scenario: Client becomes ready

- **WHEN** 会话配置包含非空 Opening Script 且客户端发送 ready 事件
- **THEN** 系统播放原始 Opening Script

### Requirement: Session termination

客户端断开、空闲超时或达到最大会话时长时，系统必须取消正在进行的生成和播放工作并释放会话资源。

#### Scenario: Browser disconnects during generation

- **WHEN** 浏览器在 LLM 或 TTS 仍在工作时断开
- **THEN** 系统取消对应 Pipeline Worker

### Requirement: Provider-neutral latency metrics

Deepgram Flux 与 ElevenLabs MUST 产生同一组逐轮指标并使用同一计算口径：`asr_final_latency_ms`、`llm_request_splicing_ms`、`llm_first_token_ms`、`tts_initial_ms`、`tts_first_audio_ms`、`playback_ms`、`turn_to_playback_ms`、reasoning 状态及缺失原因。切换 TTS provider 不得改变字段、公式或页面展示结构。

#### Scenario: ElevenLabs completes a turn

- **WHEN** ElevenLabs 依次产生 `TTSStartedFrame`、首个 `TTSAudioRawFrame` 和浏览器首次播放回调
- **THEN** 系统按与 Deepgram Flux 相同的时间点和公式保存 TTS initial、TTS TTFT、playback 与 e2e latency

#### Scenario: ElevenLabs event semantics differ

- **WHEN** ElevenLabs SDK/Pipecat service 的原始事件与 Deepgram Flux 不同
- **THEN** ElevenLabs 适配层必须归一化为公共 TTS frame 契约，不得在历史采集或前端增加 provider 专属计算分支

#### Scenario: ElevenLabs turn is interrupted or not played

- **WHEN** ElevenLabs 响应在 LLM 首 Token、TTS 首音频或浏览器播放前被打断或会话结束
- **THEN** 对应值保存为 null，并使用与 Deepgram Flux 相同的 `incomplete_reason` 规则展示具体原因

### Requirement: Provider-specific TTS failures

系统 MUST 对 ElevenLabs 鉴权、voice/model、不足额度、限流、超时和 WebSocket 断开进行安全分类，不得泄露 API Key 或完整 provider payload。

#### Scenario: ElevenLabs rejects the voice or credential

- **WHEN** ElevenLabs WebSocket 返回鉴权或 voice/model 错误
- **THEN** 当前会话安全失败并产生可诊断错误，日志和 API 响应不包含 Key

### Requirement: Per-turn latency decomposition

系统必须按轮记录 LLM 首 Token、TTS 首音频包、服务端首音频到浏览器播放及用户停说到浏览器播放的耗时，并明确各指标是否包含浏览器链路。

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

文本、指标和录音持久化不得在核心实时 Pipeline 中执行同步阻塞 I/O。

#### Scenario: Storage becomes slow

- **WHEN** SQLite 或录音磁盘写入明显变慢
- **THEN** 系统通过异步边界或有界后台队列处理，实时语音链路不等待同步磁盘操作

### Requirement: Reasoning latency evidence

系统必须按轮保存 LLM 返回的 reasoning token 数量、实际关闭策略和验证状态，用于解释首 Token 延迟；不得保存隐藏思维链正文。

#### Scenario: Provider omits reasoning usage

- **WHEN** 一轮响应没有提供 reasoning token usage
- **THEN** 历史记录保存 `reasoning_tokens=null` 和 `unverified`，不得记录为 0 或已关闭

### Requirement: Deepgram Flux voice settings

系统 MUST 在创建 Deepgram Flux streaming TTS 连接时传入当前 Bot 的 `speed` 与 `expressivity`，且不得改变现有音频格式、文本聚合、打断和时延统计契约。

#### Scenario: Start Flux with voice controls

- **WHEN** Bot 配置 `speed=1.05`、`expressivity=1` 并启动会话
- **THEN** Flux WebSocket 使用所选 voice、Speed 和 Expressivity 建立连接，其他 Pipeline 行为保持不变
