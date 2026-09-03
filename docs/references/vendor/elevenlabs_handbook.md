# ElevenLabs STT Realtime 开发者手册 / API 极速参考

> **版本**: subpackage_v1SpeechToTextRealtime.v1SpeechToTextRealtime  
> **协议类型**: AsyncAPI 2.6.0  
> **最后更新时间**: 2026-07-08  
> **规范保证**: 结构化精炼摘要位于顶部，官方原始 AsyncAPI 规范文档完全备份在底部。

---

## 1. 终点与路由 (Endpoints)

目前 ElevenLabs STT 实时服务支持以下地理区域端点，以最大化降低握手和流式传输延迟：

| 节点名称 | WebSocket 地址 (WSS) | 建议覆盖范围 |
| :--- | :--- | :--- |
| **Production (Default)** | `wss://api.elevenlabs.io/v1/speech-to-text/realtime` | 全球默认 |
| **Production US** | `wss://api.us.elevenlabs.io/v1/speech-to-text/realtime` | 北美、拉美 |
| **Production EU** | `wss://api.eu.residency.elevenlabs.io/v1/speech-to-text/realtime` | 欧洲、中东、非洲 |
| **Production India** | `wss://api.in.residency.elevenlabs.io/v1/speech-to-text/realtime` | 南亚地区 |
| **Production Singapore** | `wss://api.sg.residency.elevenlabs.io/v1/speech-to-text/realtime` | 亚太、中国、东南亚 |

---

## 2. 鉴权机制 (Authentication)

ElevenLabs WebSocket API 支持双重鉴权手段：

1. **Header 认证（推荐服务端使用）**:  
   在 HTTP 握手阶段，在 Header 中加入：
   ```http
   xi-api-key: <YOUR_ELEVENLABS_API_KEY>
   ```
2. **Query 参数认证（客户端/浏览器环境推荐）**:  
   在 URL 参数中直接拼接单次有效的 Token (可通过 `POST /v1/tokens` 接口生成)：
   ```text
   wss://api.elevenlabs.io/v1/speech-to-text/realtime?token=<SINGLE_USE_TOKEN>
   ```

---

## 3. URL 链接配置参数 (Query Parameters)

所有会话级控制和配置均在 **建立连接时通过 URL 上的 Query String 传入**，一旦连接建立，这些配置不可更改。

| 参数 | 类型 | 默认值 | 可选值及说明 |
| :--- | :--- | :--- | :--- |
| **`model_id`** | `string` | `scribe_v2_realtime` | **必填/推荐配置**。Scribe 转写模型 ID。 |
| **`audio_format`** | `string` | `pcm_16000` | 编码格式: `pcm_8000`, `pcm_16000`, `pcm_22050`, `pcm_24000`, `pcm_44100`, `pcm_48000`, `ulaw_8000` |
| **`language_code`** | `string` | (自动) | 语种代码，如 `"en"`, `"es"`, `"ar"`, `"zh"`, 符合 ISO 639-1 / 639-3。 |
| **`commit_strategy`** | `string` | `manual` | 提交并确认文本的策略：<br/>- `manual`: 需要手动在包体中发送 `commit: true`。<br/>- `vad`: 依赖服务器内置 VAD 自动断句。 |
| **`include_timestamps`**| `boolean`| `false` | 是否在 committed 消息中包含词级（Word-Level）时间戳信息。 |
| **`include_language_detection`** | `boolean` | `false` | 是否开启并在结果中返回自动语种检测结果。 |
| **`no_verbatim`** | `boolean` | `false` | 如果设为 `true`，模型会自动过滤填充词（如 uhm, ah）和语气词。 |
| **`keyterms`** | `array` | `[]` | 热词表（提升特定品牌词、人名的识别率），如 `keyterms=["RiyadBank", "Makkah"]`。 |
| **`vad_silence_threshold_secs`** | `number` | `1.5` | VAD 断句的静音阈值（秒）。 |
| **`vad_threshold`** | `number` | `0.4` | VAD 人声活动检测阈值（0.0 - 1.0），值越小越敏感。 |
| **`min_speech_duration_ms`** | `integer`| `100` | 被识别为人声的最短持续时间（毫秒）。 |
| **`min_silence_duration_ms`** | `integer`| `100` | VAD 静音的最短持续时间（毫秒），避免瞬间呼吸断开。 |
| **`enable_logging`** | `boolean` | `true` | 是否允许记录日志。企业客户传 `false` 可开启零留存（Zero Retention）保护模式。 |

---

## 4. 上下行消息格式

### 4.1 发送：音频块数据 (Client -> Server)

客户端发送的所有消息必须符合 `InputAudioChunk` 架构，为 **JSON 字符串形式**：

```json
{
  "message_type": "input_audio_chunk",
  "audio_base_64": "UklGRiS9AgBXQVZFZm10IBAAAAABAAEA...",
  "commit": false,
  "sample_rate": 8000,
  "previous_text": "Optional context for the first chunk only"
}
```
- **`message_type`**: 固定为 `"input_audio_chunk"`。
- **`audio_base_64`**: 音频片段的 Base64 字符串形式。**严禁发送原始 Binary Bytes**。
- **`commit`**: 布尔值。对于 `manual` 模式，设为 `true` 代表提交当前累积文本；对于 `vad` 模式通常为 `false`，当会话结束时可发送 `commit: true` 进行最后的文本清空。
- **`sample_rate`**: 音频波形的实际采样率（如 `8000`）。必须跟音频文件的格式和 URL 上的 `audio_format` 匹配。
- **`previous_text`**: 极其重要的功能！可用于注入先验上下文或上一轮对话。**只能随第一个音频块一起发送一次**。

### 4.2 接收：服务端推送 (Server -> Client)

所有服务端下发消息均包含 `message_type` 字段，客户端应基于此字段分流处理。

#### 4.2.1 会话成功启动 (`session_started`)
```json
{
  "message_type": "session_started",
  "session_id": "c1f71df8-a3f2-4e67-bf0e-562725e6834d",
  "config": {
    "sample_rate": 8000,
    "audio_format": "pcm_8000",
    "language_code": "ar",
    "commit_strategy": "vad",
    "vad_silence_threshold_secs": 1.5,
    "vad_threshold": 0.4,
    "min_speech_duration_ms": 100,
    "min_silence_duration_ms": 100,
    "model_id": "scribe_v2_realtime",
    "enable_logging": true,
    "include_timestamps": false,
    "include_language_detection": false,
    "keyterms": [],
    "no_verbatim": false
  }
}
```

#### 4.2.2 实时中间临时文本 (`partial_transcript`)
不具备时间戳，文本可能会随着后续音频的读入发生调整修正。常用于低延迟界面渲染。
```json
{
  "message_type": "partial_transcript",
  "text": "Hello, how ca"
}
```

#### 4.2.3 已确认并提交的文本 (`committed_transcript`)
当 `commit_strategy` 的断句条件触发或手动 commit 时产生，此段文本已经固定。
```json
{
  "message_type": "committed_transcript",
  "text": "Hello, how can I help you today?"
}
```

#### 4.2.4 带有时间戳的已提交文本 (`committed_transcript_with_timestamps`)
如果开启了 `include_timestamps=true`，则会取代普通 committed 消息推送：
```json
{
  "message_type": "committed_transcript_with_timestamps",
  "text": "Hello, how can I help you today?",
  "language_code": "en",
  "words": [
    {
      "text": "Hello",
      "start": 0.12,
      "end": 0.45,
      "type": "word",
      "speaker_id": "speaker_0",
      "logprob": -0.05,
      "characters": ["H", "e", "l", "l", "o"]
    }
  ]
}
```

#### 4.2.5 异常与错误定义
所有错误类事件均拥有独立的 `message_type`。关键类型如下：
- **`auth_error`**: 鉴权 API Key 无效或 Token 过期。
- **`quota_exceeded`**: 账号配额或余额耗尽。
- **`commit_throttled`**: 客户端发送 commit 过于频繁被拦截限流。
- **`session_time_limit_exceeded`**: 会话达到单次最大时间上限。
- **`chunk_size_exceeded`**: 单次音频包过大（超出限制）。
- **`error`**: 通用系统未知异常。

---

## 5. 官方 AsyncAPI 2.6.0 规范原文备份 (兜底事实锚点 ⚓)

```yaml
asyncapi: 2.6.0
info:
  title: V 1 Speech To Text Realtime
  version: subpackage_v1SpeechToTextRealtime.v1SpeechToTextRealtime
  description: >
    Realtime speech-to-text transcription service. This WebSocket API enables
    streaming audio input and receiving transcription results.


    ## Event Flow

    - Audio chunks are sent as `input_audio_chunk` messages

    - Transcription results are streamed back in various formats (partial,
    committed, with timestamps)

    - Supports manual commit or VAD-based automatic commit strategies


    Authentication is done either by providing a valid API key in the
    `xi-api-key` header or by providing a valid token in the `token` query
    parameter. Tokens can be generated from the [single use token
    endpoint](/docs/api-reference/tokens/create). Use tokens if you want to
    transcribe audio from the client side.
channels:
  /v1/speech-to-text/realtime:
    description: >
      Realtime speech-to-text transcription service. This WebSocket API enables
      streaming audio input and receiving transcription results.


      ## Event Flow

      - Audio chunks are sent as `input_audio_chunk` messages

      - Transcription results are streamed back in various formats (partial,
      committed, with timestamps)

      - Supports manual commit or VAD-based automatic commit strategies


      Authentication is done either by providing a valid API key in the
      `xi-api-key` header or by providing a valid token in the `token` query
      parameter. Tokens can be generated from the [single use token
      endpoint](/docs/api-reference/tokens/create). Use tokens if you want to
      transcribe audio from the client side.
    bindings:
      ws:
        query:
          type: object
          properties:
            model_id:
              type: string
            token:
              type: string
            include_timestamps:
              type: boolean
              default: false
            include_language_detection:
              type: boolean
              default: false
            audio_format:
              $ref: '#/components/schemas//v1/speech-to-text/realtime_audio_format'
              default: pcm_16000
            language_code:
              type: string
            commit_strategy:
              $ref: '#/components/schemas//v1/speech-to-text/realtime_commit_strategy'
              default: manual
            keyterms:
              type: array
              items:
                type: string
            no_verbatim:
              type: boolean
              default: false
            vad_silence_threshold_secs:
              type: number
              format: double
              default: 1.5
            vad_threshold:
              type: number
              format: double
              default: 0.4
            min_speech_duration_ms:
              type: integer
              default: 100
            min_silence_duration_ms:
              type: integer
              default: 100
            enable_logging:
              type: boolean
              default: true
        headers:
          type: object
          properties:
            xi-api-key:
              type: string
    publish:
      operationId: subpackage_v1SpeechToTextRealtime.v1SpeechToTextRealtime-publish
      summary: subscribe
      description: Receive transcription results from the WebSocket
      message:
        name: subscribe
        title: subscribe
        description: Receive transcription results from the WebSocket
        payload:
          $ref: '#/components/schemas/V1SpeechToTextRealtimeSubscribe'
    subscribe:
      operationId: subpackage_v1SpeechToTextRealtime.v1SpeechToTextRealtime-subscribe
      summary: publish
      description: Send audio data to the WebSocket
      message:
        name: publish
        title: publish
        description: Send audio data to the WebSocket
        payload:
          $ref: '#/components/schemas/V1SpeechToTextRealtimePublish'
servers:
  Production:
    url: wss://api.elevenlabs.io/
    x-default: true
    protocol: wss
  Production US:
    url: wss://api.us.elevenlabs.io/
    protocol: wss
  Production EU:
    url: wss://api.eu.residency.elevenlabs.io/
    protocol: wss
  Production India:
    url: wss://api.in.residency.elevenlabs.io/
    protocol: wss
  Production Singapore:
    url: wss://api.sg.residency.elevenlabs.io/
    protocol: wss
components:
  schemas:
    /v1/speech-to-text/realtime_audio_format:
      type: string
      enum:
        - pcm_8000
        - pcm_16000
        - pcm_22050
        - pcm_24000
        - pcm_44100
        - pcm_48000
        - ulaw_8000
      default: pcm_16000
      description: Audio encoding format for speech-to-text.
      title: /v1/speech-to-text/realtime_audio_format
    /v1/speech-to-text/realtime_commit_strategy:
      type: string
      enum:
        - manual
        - vad
      default: manual
      description: Strategy for committing transcriptions.
      title: /v1/speech-to-text/realtime_commit_strategy
    AudioFormatEnum:
      type: string
      enum:
        - pcm_8000
        - pcm_16000
        - pcm_22050
        - pcm_24000
        - pcm_44100
        - pcm_48000
        - ulaw_8000
      default: pcm_16000
      description: Audio encoding format for speech-to-text.
      title: AudioFormatEnum
    MessagesSessionStartedConfigCommitStrategy:
      type: string
      enum:
        - manual
        - vad
      description: Strategy for committing transcriptions.
      title: MessagesSessionStartedConfigCommitStrategy
    MessagesSessionStartedConfig:
      type: object
      properties:
        sample_rate:
          type: integer
          description: Sample rate of the audio in Hz.
        audio_format:
          $ref: '#/components/schemas/AudioFormatEnum'
          default: pcm_16000
        language_code:
          type: string
          description: Language code in ISO 639-1 or ISO 639-3 format.
        commit_strategy:
          $ref: '#/components/schemas/MessagesSessionStartedConfigCommitStrategy'
          description: Strategy for committing transcriptions.
        vad_silence_threshold_secs:
          type: number
          format: double
          description: Silence threshold in seconds.
        vad_threshold:
          type: number
          format: double
          description: Threshold for voice activity detection.
        min_speech_duration_ms:
          type: integer
          description: Minimum speech duration in milliseconds.
        min_silence_duration_ms:
          type: integer
          description: Minimum silence duration in milliseconds.
        model_id:
          type: string
          description: ID of the model to use for transcription.
        enable_logging:
          type: boolean
          description: >-
            When enable_logging is set to false zero retention mode will be used
            for the request. This will mean history features are unavailable for
            this request. Zero retention mode may only be used by enterprise
            customers.
        include_timestamps:
          type: boolean
          description: >-
            Whether the session will include word-level timestamps in the
            committed transcript.
        include_language_detection:
          type: boolean
          description: >-
            Whether the session will include language detection in the committed
            transcript.
        keyterms:
          type: array
          items:
            type: string
          description: List of keyterms the model is biased towards.
        no_verbatim:
          type: boolean
          description: >-
            Whether filler words and disfluencies are removed from the
            transcript.
      description: Configuration for the transcription session.
      title: MessagesSessionStartedConfig
    SessionStarted:
      type: object
      properties:
        message_type:
          type: string
          enum:
            - session_started
          description: The message type identifier.
        session_id:
          type: string
          description: Unique identifier for the session.
        config:
          $ref: '#/components/schemas/MessagesSessionStartedConfig'
          description: Configuration for the transcription session.
      required:
        - message_type
        - session_id
        - config
      description: Payload sent when the transcription session is successfully started.
      title: SessionStarted
    PartialTranscript:
      type: object
      properties:
        message_type:
          type: string
          enum:
            - partial_transcript
          description: The message type identifier.
        text:
          type: string
          description: Partial transcription text.
      required:
        - message_type
        - text
      description: Payload for partial transcription results that may change.
      title: PartialTranscript
    CommittedTranscript:
      type: object
      properties:
        message_type:
          type: string
          enum:
            - committed_transcript
          description: The message type identifier.
        text:
          type: string
          description: Committed transcription text.
      required:
        - message_type
        - text
      description: Payload for committed transcription results.
      title: CommittedTranscript
    TranscriptionWordType:
      type: string
      enum:
        - word
        - spacing
      description: The type of word.
      title: TranscriptionWordType
    TranscriptionWord:
      type: object
      properties:
        text:
          type: string
          description: The transcribed word.
        start:
          type: number
          format: double
          description: Start time in seconds.
        end:
          type: number
          format: double
          description: End time in seconds.
        type:
          $ref: '#/components/schemas/TranscriptionWordType'
          description: The type of word.
        speaker_id:
          type: string
          description: The ID of the speaker if available.
        logprob:
          type: number
          format: double
          description: Confidence score for this word.
        characters:
          type: array
          items:
            type: string
          description: The characters in the word.
      description: Word-level transcription data with timing information.
      title: TranscriptionWord
    CommittedTranscriptWithTimestamps:
      type: object
      properties:
        message_type:
          type: string
          enum:
            - committed_transcript_with_timestamps
          description: The message type identifier.
        text:
          type: string
          description: Committed transcription text.
        language_code:
          type:
            - string
            - 'null'
          description: Detected or specified language code.
        words:
          type:
            - array
            - 'null'
          items:
            $ref: '#/components/schemas/TranscriptionWord'
          description: Word-level information with timestamps.
      required:
        - message_type
        - text
      description: Payload for committed transcription results with word-level timestamps.
      title: CommittedTranscriptWithTimestamps
    ScribeError:
      type: object
      properties:
        message_type:
          type: string
          enum:
            - error
          description: The message type identifier.
        error:
          type: string
          description: Error message describing what went wrong.
      required:
        - message_type
        - error
      description: Payload for error events during transcription.
      title: ScribeError
    ScribeAuthError:
      type: object
      properties:
        message_type:
          type: string
          enum:
            - auth_error
          description: The message type identifier.
        error:
          type: string
          description: Authentication error details.
      required:
        - message_type
        - error
      description: Payload for authentication errors.
      title: ScribeAuthError
    ScribeQuotaExceededError:
      type: object
      properties:
        message_type:
          type: string
          enum:
            - quota_exceeded
          description: The message type identifier.
        error:
          type: string
          description: Quota exceeded error details.
      required:
        - message_type
        - error
      description: Payload for quota exceeded errors.
      title: ScribeQuotaExceededError
    ScribeThrottledError:
      type: object
      properties:
        message_type:
          type: string
          enum:
            - commit_throttled
          description: The message type identifier.
        error:
          type: string
          description: Throttled error details.
      required:
        - message_type
        - error
      description: Payload for throttled errors.
      title: ScribeThrottledError
    ScribeUnacceptedTermsError:
      type: object
      properties:
        message_type:
          type: string
          enum:
            - unaccepted_terms
          description: The message type identifier.
        error:
          type: string
          description: Unaccepted terms error details.
      required:
        - message_type
        - error
      description: Payload for unaccepted terms errors.
      title: ScribeUnacceptedTermsError
    ScribeRateLimitedError:
      type: object
      properties:
        message_type:
          type: string
          enum:
            - rate_limited
          description: The message type identifier.
        error:
          type: string
          description: Rate limited error details.
      required:
        - message_type
        - error
      description: Payload for rate limited errors.
      title: ScribeRateLimitedError
    ScribeQueueOverflowError:
      type: object
      properties:
        message_type:
          type: string
          enum:
            - queue_overflow
          description: The message type identifier.
        error:
          type: string
          description: Queue overflow error details.
      required:
        - message_type
        - error
      description: Payload for queue overflow errors.
      title: ScribeQueueOverflowError
    ScribeResourceExhaustedError:
      type: object
      properties:
        message_type:
          type: string
          enum:
            - resource_exhausted
          description: The message type identifier.
        error:
          type: string
          description: Resource exhausted error details.
      required:
        - message_type
        - error
      description: Payload for resource exhausted errors.
      title: ScribeResourceExhaustedError
    ScribeSessionTimeLimitExceededError:
      type: object
      properties:
        message_type:
          type: string
          enum:
            - session_time_limit_exceeded
          description: The message type identifier.
        error:
          type: string
          description: Session time limit exceeded error details.
      required:
        - message_type
        - error
      description: Payload for session time limit exceeded errors.
      title: ScribeSessionTimeLimitExceededError
    ScribeInputError:
      type: object
      properties:
        message_type:
          type: string
          enum:
            - input_error
          description: The message type identifier.
        error:
          type: string
          description: Input error details.
      required:
        - message_type
        - error
      description: Payload for input errors.
      title: ScribeInputError
    ScribeChunkSizeExceededError:
      type: object
      properties:
        message_type:
          type: string
          enum:
            - chunk_size_exceeded
          description: The message type identifier.
        error:
          type: string
          description: Chunk size exceeded error details.
      required:
        - message_type
        - error
      description: Payload for chunk size exceeded errors.
      title: ScribeChunkSizeExceededError
    ScribeInsufficientAudioActivityError:
      type: object
      properties:
        message_type:
          type: string
          enum:
            - insufficient_audio_activity
          description: The message type identifier.
        error:
          type: string
          description: Insufficient audio activity error details.
      required:
        - message_type
        - error
      description: Payload for insufficient audio activity errors.
      title: ScribeInsufficientAudioActivityError
    ScribeTranscriberError:
      type: object
      properties:
        message_type:
          type: string
          enum:
            - transcriber_error
          description: The message type identifier.
        error:
          type: string
          description: Transcriber error details.
      required:
        - message_type
        - error
      description: Payload for transcriber errors.
      title: ScribeTranscriberError
    V1SpeechToTextRealtimeSubscribe:
      oneOf:
        - $ref: '#/components/schemas/SessionStarted'
        - $ref: '#/components/schemas/PartialTranscript'
        - $ref: '#/components/schemas/CommittedTranscript'
        - $ref: '#/components/schemas/CommittedTranscriptWithTimestamps'
        - $ref: '#/components/schemas/ScribeError'
        - $ref: '#/components/schemas/ScribeAuthError'
        - $ref: '#/components/schemas/ScribeQuotaExceededError'
        - $ref: '#/components/schemas/ScribeThrottledError'
        - $ref: '#/components/schemas/ScribeUnacceptedTermsError'
        - $ref: '#/components/schemas/ScribeRateLimitedError'
        - $ref: '#/components/schemas/ScribeQueueOverflowError'
        - $ref: '#/components/schemas/ScribeResourceExhaustedError'
        - $ref: '#/components/schemas/ScribeSessionTimeLimitExceededError'
        - $ref: '#/components/schemas/ScribeInputError'
        - $ref: '#/components/schemas/ScribeChunkSizeExceededError'
        - $ref: '#/components/schemas/ScribeInsufficientAudioActivityError'
        - $ref: '#/components/schemas/ScribeTranscriberError'
      title: V1SpeechToTextRealtimeSubscribe
    InputAudioChunk:
      type: object
      properties:
        message_type:
          type: string
          enum:
            - input_audio_chunk
          description: The message type identifier.
        audio_base_64:
          type: string
          format: base64
          description: Base64-encoded audio data.
        commit:
          type: boolean
          description: Whether to commit the transcription after this chunk.
        sample_rate:
          type: integer
          description: Sample rate of the audio in Hz.
        previous_text:
          type: string
          description: >-
            Send text context to the model. Can only be sent alongside the first
            audio chunk. If sent in a subsequent chunk, an error will be
            returned.
      required:
        - message_type
        - audio_base_64
        - commit
        - sample_rate
      description: Payload for sending audio chunks from client to server.
      title: InputAudioChunk
    V1SpeechToTextRealtimePublish:
      oneOf:
        - $ref: '#/components/schemas/InputAudioChunk'
      title: V1SpeechToTextRealtimePublish
```
