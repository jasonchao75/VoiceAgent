# Delta: Call History

## ADDED Requirements

### Requirement: Provider-neutral TTS history snapshots

系统 MUST 以 provider-neutral 的统一结构持久化 Deepgram Flux 与 ElevenLabs 的 TTS provider/model/voice/text aggregation 快照、逐轮 latency 与缺失原因。历史详情的指标字段、计算口径和展示顺序不得因 TTS provider 改变。

#### Scenario: Compare Deepgram and ElevenLabs calls

- **WHEN** 用户分别查看 Deepgram Flux 与 ElevenLabs 通话历史
- **THEN** 两者展示相同的 ASR、LLM、TTS、playback、e2e 和 reasoning 指标，并明确展示各自 TTS provider/model/voice/text aggregation

#### Scenario: Explain aggregation-sensitive latency

- **WHEN** 用户查看 `tts_initial_ms` 或对比两次通话
- **THEN** 页面说明 Sentence 模式的该阶段包含首句聚合等待，并展示 text aggregation 供用户按相同口径比较

#### Scenario: A provider turn is incomplete

- **WHEN** 任一 TTS provider 的轮次被打断或未播放
- **THEN** 页面按相同规则显示缺失原因，不得只显示破折号或用 0 代替缺失事件
