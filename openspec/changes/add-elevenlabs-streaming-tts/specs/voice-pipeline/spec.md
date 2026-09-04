# Delta: Voice Pipeline

## MODIFIED Requirements

### Requirement: Streaming pipeline orchestration

系统必须通过异步流式 Pipeline 依次处理浏览器音频输入、Deepgram Flux STT、对话上下文、OpenAI-compatible LLM、用户选择的 TTS provider 和浏览器音频输出。TTS 必须支持 Deepgram Flux 与 ElevenLabs WebSocket 双向流式服务，核心热路径不得使用同步阻塞 I/O。

#### Scenario: ElevenLabs is selected

- **WHEN** Bot 选择 `elevenlabs`、有效 voice/model 且会话具备 ElevenLabs Key
- **THEN** LLM token 流持续送入 ElevenLabs WebSocket，返回的 24 kHz PCM chunk 持续送往浏览器，不等待完整文本或完整音频

#### Scenario: Deepgram remains selected

- **WHEN** Bot 选择 `deepgram_flux`
- **THEN** 系统继续使用现有 Flux TTS 行为，且不要求 ElevenLabs Key

#### Scenario: User interrupts ElevenLabs playback

- **WHEN** 用户在 ElevenLabs 仍生成或播放音频时开始说话
- **THEN** 当前合成和播放被取消，残留音频不得污染下一轮，后续会话保持可用

## ADDED Requirements

### Requirement: Provider-neutral latency metrics

Deepgram Flux 与 ElevenLabs 必须产生同一组逐轮指标并使用同一计算口径：`asr_final_latency_ms`、`llm_request_splicing_ms`、`llm_first_token_ms`、`tts_initial_ms`、`tts_first_audio_ms`、`playback_ms`、`turn_to_playback_ms`、reasoning 状态及缺失原因。切换 TTS provider 不得改变字段、公式或页面展示结构。

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

系统必须对 ElevenLabs 鉴权、voice/model、不足额度、限流、超时和 WebSocket 断开进行安全分类，不得泄露 API Key 或完整 provider payload。

#### Scenario: ElevenLabs rejects the voice or credential

- **WHEN** ElevenLabs WebSocket 返回鉴权或 voice/model 错误
- **THEN** 当前会话安全失败并产生可诊断错误，日志和 API 响应不包含 Key
