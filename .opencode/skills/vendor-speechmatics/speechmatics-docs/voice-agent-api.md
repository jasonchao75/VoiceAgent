# Speechmatics Voice Agent API (Preview)

> 注意：这是一个处于预览版 (Early Access) 的 API，专门为了 Voice Agent (语音助手) 的场景而设计，在流式识别的基础上内置了 **Turn-Detection (语音对话轮次检测)** 和 **VAD (语音活动检测)**，使得前端和 LLM 可以更容易地知道何时该接话。

## 1. 核心信息
- **接口协议**: WebSocket 
- **Endpoint**: `wss://preview.rt.speechmatics.com/v2/agent/<profile>`
  - `<profile>` 可以是以下之一：
    - `adaptive`: 推荐给通用对话 Agent。自适应说话人的语速和停顿（处理 "嗯"、"啊" 等思考停顿）。
    - `agile`: 极速模式，基于 VAD 的静音检测。延迟最低，但可能在人自然停顿时被打断。
    - `smart`: 在 `adaptive` 的基础上加入了声学特征的机器学习预测模型。最不容易发生抢话，但延迟稍高。
    - `external`: 手动控制模式，通过发送 `ForceEndOfUtterance` 来结束一个轮次。
- **鉴权方式**: 
  - HTTP Header: `Authorization: Bearer <SPEECHMATICS_API_KEY>` 
  - 或 URL 参数: `?api_key=<SPEECHMATICS_API_KEY>`
  - 或 URL 参数 (浏览器前端使用): `?jwt=<JWT_TEMPORARY_KEY>`
- **强制配置**: `audio_format` 必须明确为 `pcm_s16le` 格式，采样率仅支持 `8000` 或 `16000`。

## 2. 关键请求与流程 (Client -> Server)

### 2.1 启动识别 `StartRecognition`
这是建立连接后的首个消息。
```json
{
  "message": "StartRecognition",
  "audio_format": {
    "type": "raw",
    "encoding": "pcm_s16le",
    "sample_rate": 8000
  },
  "transcription_config": {
    "language": "zh",
    "enable_partials": true,
    "diarization": "speaker"
  }
}
```

#### `transcription_config` 在 Voice Agent API 下支持的参数
- `language`: 必填。支持的语言代码。
- `output_locale`: 输出区域设置 (如 `en-US`)。
- `additional_vocab`: 自定义词典热词。
- `punctuation_overrides`: 标点符号规则覆盖。
- `domain`: 领域模型 (如 `medical`)。
- `enable_entities`: 实体检测格式化，默认 `false`。
- `enable_partials`: 是否发送部分转写段 (`AddPartialSegment`)，默认 `true`。
- `diarization`: 说话人分离，默认 `speaker`。设为 `none` 可关闭。
- `volume_threshold`: 处理的最小音量阈值。

#### `speaker_diarization_config` 专属配置 (需开启 `diarization: "speaker"`)
- `max_speakers`: 跟踪的最大说话人数。
- `speaker_sensitivity`: 说话人分离敏感度。
- `prefer_current_speaker`: 偏向于最近活跃的说话人。
- `known_speakers`: 预注册的说话人 ID，用于跨会话一致性识别（Speaker ID 功能）。

**绝对红线 (不支持的参数)**: 此端点明确**不支持** `translation_config` 或 `audio_events_config`，传入会导致报错拒绝。

### 2.2 发送音频
接收到服务器的 `RecognitionStarted` 后，开始不断发送二进制的 raw PCM 音频数据包。

### 2.3 其他控制指令
- `ForceEndOfUtterance`: 仅限 `external` 模式，手动触发当前轮次结束，服务端会立即返回最终结果 `AddSegment`。
- `UpdateSpeakerFocus`: 动态调整焦点说话人，可以忽略背景噪音说话人（`focus_speakers` / `ignore_speakers`）。
- `EndOfStream`: 会话结束时调用。

## 3. 关键接收事件 (Server -> Client)

Voice Agent API 与普通 Realtime API 的核心区别在于：它会将语音包装为一个一个的“轮次” (Turn)。

### 3.1 轮次开始 `StartOfTurn`
当检测到用户开始说话时触发。收到此消息时，你的 Agent 应该停止讲话（支持打断逻辑）。
```json
{
  "message": "StartOfTurn",
  "turn_id": 42
}
```

### 3.2 轮次中间结果 `AddPartialSegment`
相当于普通流式的中间结果，但结构是 `segments` 数组。每个新的消息会替换之前的。
```json
{
  "message": "AddPartialSegment",
  "segments": [
    { "text": "你好", "is_eou": false, "speaker_id": "S1" }
  ]
}
```

### 3.3 轮次最终结果 `AddSegment`
在轮次即将结束时发送的最终稳定的句子，直接喂给你的 LLM 进行回复。
```json
{
  "message": "AddSegment",
  "segments": [
    { "text": "你好，今天天气怎么样？", "is_eou": true, "speaker_id": "S1" }
  ]
}
```

### 3.4 轮次结束 `EndOfTurn`
表示系统判断用户这一句话已经说完了（基于你选择的 profile，例如 `adaptive`），Agent 此时可以真正开始回复了。
```json
{
  "message": "EndOfTurn",
  "turn_id": 42,
  "metadata": { "start_time": 0.84, "end_time": 3.24 }
}
```

## 4. 预测与 VAD 特性

- **预测**: `adaptive` 和 `smart` 模式下，会提前发来 `EndOfTurnPrediction`，允许你提前唤醒 LLM 预热请求。`smart` 模式还会发送高置信度的 `SmartTurnResult`。
- **纯 VAD 事件**: 系统会独立抛出 `SpeechStarted` 和 `SpeechEnded` 事件来标志绝对的“有声音/没声音”物理边界（不代表语义上的完整一句话）。
- **Speaker 事件**: `SpeakerStarted` 和 `SpeakerEnded` 会带上具体的说话人标签（如 `S1`）。

---

## 5. Reference: Official API Spec
> **防幻觉红线**: 以下为官方原始 API 规范文档备份。当上方精简版参数无法满足需求或出现争议时，请**绝对以本段下方的官方原始定义为准**。

# Voice Agent API (Preview)
Early access to the Voice Agent API — a turn-based API built for voice agents
The Voice Agent API is a preview offering and should not be used for live production traffic. The system will be less stable than our production endpoints and features may change.
- There are no uptime or performance SLAs.
- There are no data residency guarantees. Data processing may occur in both US and EU regions.
- Preview features may be cancelled at any time or never be released publicly.

## Introduction
The Voice Agent API is a WebSocket API for building voice agents. Stream audio in and receive speaker-labelled, turn-based transcription back — clean, punctuated, and ready to pass directly to an LLM.

Turn detection runs server-side. Choose a profile based on your use case and the API handles when to finalise each speaker's turn.

## Profiles
Profiles are pre-configured turn detection modes. Each profile sets the right defaults for your use case.

| Profile | Turn detection | Best for |
|---|---|---|
| `adaptive` | Adapts to speaker pace and hesitation | General conversational agents |
| `agile` | VAD-based silence detection | Speed-first use cases |
| `smart` | adaptive + ML acoustic turn prediction | High-stakes conversations |
| `external` | Manual — you trigger turn end | Push-to-talk, custom VAD, LLM-driven |

### adaptive
**Endpoint**: `/v2/agent/adaptive`
Adapts to each speaker's pace over the course of a conversation. It adjusts the turn-end threshold based on speech rate and disfluencies (e.g. hesitations, filler words), waiting longer for speakers who tend to pause mid-thought.

### agile
**Endpoint**: `/v2/agent/agile`
Uses voice activity detection (VAD) to detect silence and finalise turns as quickly as possible. The lowest latency profile.

### smart
**Endpoint**: `/v2/agent/smart`
Builds on adaptive with an additional ML model that analyses acoustic cues to predict whether a speaker has genuinely finished their turn. The most conservative profile — least likely to interrupt.

### external
**Endpoint**: `/v2/agent/external`
Turn detection is fully manual. The server accumulates audio and transcript until you send a `ForceEndOfUtterance` message, at which point it finalises everything spoken up to that point and emits an `AddSegment`.

## Session Flow
1. **Connect** to endpoint with profile via WebSocket
2. Client sends `StartRecognition`
3. Server sends `RecognitionStarted`
4. Client sends Audio frames (binary) -> Server sends `AudioAdded`
5. Events occur: `SpeechStarted`, `StartOfTurn`, `SpeakerStarted`, `AddPartialSegment` (repeating), `SpeakerMetrics` (repeating), `EndOfTurnPrediction` (adaptive, smart), `SmartTurnResult` (smart only)
6. End of turn events: `SpeechEnded`, `EndOfUtterance`, `SpeakerEnded`, `AddSegment`, `EndOfTurn`
7. Client sends `EndOfStream`
8. Server sends `EndOfTranscript`

## Configuration
Configuration is passed in `StartRecognition`.
### audio_format
Only `pcm_s16le` at 8000 or 16000 Hz is supported.

### transcription_config
| Field | Default | Notes |
|---|---|---|
| `language` | `en` | All supported languages |
| `output_locale` | — | Output locale (e.g. en-US) |
| `additional_vocab` | — | Custom vocabulary entries |
| `punctuation_overrides` | — | Custom punctuation rules |
| `domain` | — | Domain-specific model (e.g. medical) |
| `enable_entities` | `false` | Entity detection |
| `enable_partials` | `true` | Emit partial segments during speech |
| `diarization` | `speaker` | Speaker diarization; none to disable |
| `volume_threshold` | — | Minimum audio volume to process |

### transcription_config.speaker_diarization_config
Note: The following require `diarization: "speaker"` to be set.
| Field | Default | Notes |
|---|---|---|
| `max_speakers` | — | Maximum number of speakers to track |
| `speaker_sensitivity` | — | Sensitivity of speaker separation |
| `prefer_current_speaker` | — | Bias toward the most recently active speaker |
| `known_speakers` | — | Pre-enrolled speaker identifiers for cross-session recognition |

**Not supported — will be rejected if present:**
- `translation_config`
- `audio_events_config`

## API Reference - Client Messages

### StartRecognition
```json
{
  "message": "StartRecognition",
  "audio_format": { "type": "raw", "encoding": "pcm_s16le", "sample_rate": 16000 },
  "transcription_config": { "language": "en" }
}
```

### EndOfStream
```json
{ "message": "EndOfStream", "last_seq_no": 1234 }
```

### ForceEndOfUtterance
```json
{ "message": "ForceEndOfUtterance" }
```

### UpdateSpeakerFocus
```json
{
  "message": "UpdateSpeakerFocus",
  "speaker_focus": { "focus_speakers": ["S1"], "ignore_speakers": ["S3"], "focus_mode": "retain" }
}
```

### GetSpeakers
```json
{ "message": "GetSpeakers" }
```

## API Reference - Server Messages

### StartOfTurn
```json
{ "message": "StartOfTurn", "turn_id": 42 }
```

### EndOfTurn
```json
{ "message": "EndOfTurn", "turn_id": 42, "metadata": { "start_time": 0.84, "end_time": 3.24 } }
```

### AddPartialSegment
```json
{
  "message": "AddPartialSegment",
  "segments": [
    { "speaker_id": "S1", "is_active": true, "text": "Good evening", "is_eou": false }
  ]
}
```

### AddSegment
```json
{
  "message": "AddSegment",
  "segments": [
    { "speaker_id": "S1", "is_active": true, "text": "Good evening.", "is_eou": true }
  ]
}
```

### SpeakerStarted / SpeakerEnded
```json
{ "message": "SpeakerStarted", "speaker_id": "S1", "is_active": true, "time": 0.84 }
```

### SessionMetrics
```json
{ "message": "SessionMetrics", "total_time": 4.6, "total_bytes": 148480, "processing_time": 0.295 }
```

### SpeakerMetrics
```json
{
  "message": "SpeakerMetrics",
  "speakers": [ { "speaker_id": "S1", "word_count": 6, "last_heard": 2.36, "volume": 5.2 } ]
}
```

### SpeakersResult
```json
{
  "message": "SpeakersResult",
  "speakers": [ { "label": "S1", "speaker_identifiers": ["<id1>"] } ]
}
```

### EndOfTurnPrediction
```json
{ "message": "EndOfTurnPrediction", "turn_id": 2, "predicted_wait": 0.73 }
```

### SmartTurnResult
```json
{
    "message": "SmartTurnResult",
    "prediction": { "prediction": true, "probability": 0.979 }
}
```

### SpeechStarted / SpeechEnded
```json
{ "message": "SpeechStarted", "probability": 0.508 }
```
