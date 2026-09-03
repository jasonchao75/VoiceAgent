# Delta: Voice Pipeline Metrics

## ADDED Requirements

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
