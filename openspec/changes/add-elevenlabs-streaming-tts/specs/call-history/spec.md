# Delta: Call History

## MODIFIED Requirements

### Requirement: Persistent call history

系统必须以 provider-neutral 的统一结构持久化 Deepgram Flux 与 ElevenLabs 的通话文本、逐轮 latency、缺失原因及 TTS provider/model/voice 快照。历史详情的指标字段、计算口径和展示顺序不得因 TTS provider 改变。

#### Scenario: Compare Deepgram and ElevenLabs calls

- **WHEN** 用户分别查看 Deepgram Flux 与 ElevenLabs 通话历史
- **THEN** 两者展示相同的 ASR、LLM、TTS、playback、e2e 和 reasoning 指标，并明确展示各自 TTS provider/model/voice

#### Scenario: A provider turn is incomplete

- **WHEN** 任一 TTS provider 的轮次被打断或未播放
- **THEN** 页面按相同规则显示缺失原因，不得只显示破折号或用 0 代替缺失事件
