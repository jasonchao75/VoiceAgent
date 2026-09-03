# ElevenLabs Speech-to-Text Realtime API Technical Specification

> **Source**: ElevenLabs official reference (AsyncAPI 2.6.0)  
> **Last Verified**: 2026-07-08  
> **Service Name**: Scribe (Realtime STT)

---

## 1. Connection & Endpoints

### 1.1 Regional Base URLs
Use regional URLs to reduce latency for real-time applications:
- **Global / Default**: `wss://api.elevenlabs.io/v1/speech-to-text/realtime`
- **United States**: `wss://api.us.elevenlabs.io/v1/speech-to-text/realtime`
- **Europe**: `wss://api.eu.residency.elevenlabs.io/v1/speech-to-text/realtime`
- **India**: `wss://api.in.residency.elevenlabs.io/v1/speech-to-text/realtime`
- **Singapore / Asia-Pacific**: `wss://api.sg.residency.elevenlabs.io/v1/speech-to-text/realtime`

---

## 2. URL Connection Parameters (Query Parameters)

All parameters MUST be specified as query strings when establishing the WebSocket handshake. 

| Parameter Name | Data Type | Default | Description & Allowed Values |
| :--- | :--- | :--- | :--- |
| `model_id` | `string` | `scribe_v2_realtime` | ID of the ElevenLabs transcription model. |
| `audio_format` | `string` | `pcm_16000` | Encoding format: `pcm_8000`, `pcm_16000`, `pcm_22050`, `pcm_24000`, `pcm_44100`, `pcm_48000`, `ulaw_8000`. |
| `language_code` | `string` | Null | Optional language code in ISO 639-1 or ISO 639-3 format (e.g., `"en"`, `"es"`, `"ar"`, `"zh"`). |
| `commit_strategy` | `string` | `manual` | Strategy for committing transcripts. Enum: `manual`, `vad`. |
| `include_timestamps` | `boolean` | `false` | Whether the committed transcript should return word-level timestamps. |
| `include_language_detection` | `boolean` | `false` | Whether to include automatic language detection in committed results. |
| `no_verbatim` | `boolean` | `false` | Whether to filter disfluencies and filler words (e.g., "uh", "um"). |
| `vad_silence_threshold_secs` | `number` | `1.5` | Threshold of silence in seconds to trigger VAD commit. |
| `vad_threshold` | `number` | `0.4` | Human voice activity detection sensitivity (0.0 to 1.0). Smaller is more sensitive. |
| `min_speech_duration_ms` | `integer` | `100` | Minimum speech duration required to qualify as人声 (human voice) in milliseconds. |
| `min_silence_duration_ms` | `integer` | `100` | Minimum silence duration required to trigger silence state in milliseconds. |
| `enable_logging` | `boolean` | `true` | Enterprise-only. Set to `false` to enforce Zero Retention Mode. |
| `keyterms` | `array[string]`| `[]` | List of custom words to bias the transcription model towards. |

---

## 3. Client-to-Server Messages (Publish)

Client messages sent over the WebSocket MUST be serialized JSON objects matching the `InputAudioChunk` schema.

### 3.1 `InputAudioChunk` Schema
```json
{
  "message_type": "input_audio_chunk",
  "audio_base_64": "UklGRiS9AgBXQVZFZm10IBAAAAABAAEA...",
  "commit": false,
  "sample_rate": 8000,
  "previous_text": "Optional predecessor context (First chunk ONLY)"
}
```

- **`message_type`**: Required. Must be exactly `"input_audio_chunk"`.
- **`audio_base_64`**: Required. The Base64 encoded string of the raw audio bytes (PCM or ULAW depending on your query params). Sending raw binary byte frames directly is **NOT supported** and will close the connection.
- **`commit`**: Required. Set to `true` to force-commit the current accumulation of audio. Under `commit_strategy="vad"`, this is usually set to `false`, but should be sent as `true` in an empty final chunk at the end of the session.
- **`sample_rate`**: Required. The sample rate of the audio data in Hz (e.g. `8000`).
- **`previous_text`**: Optional. Provides context to the transcriber model. **Must only be sent alongside the first audio chunk of a session.** Sending it in subsequent chunks triggers a `ScribeInputError` (message_type: `input_error`).

---

## 4. Server-to-Client Messages (Subscribe)

Every incoming message from ElevenLabs contains a `"message_type"` field. Handlers should switch logic based on this identifier.

### 4.1 Successful Setup (`session_started`)
Dispatched as soon as the handshake succeeds.
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

### 4.2 Intermediate Hypothesis (`partial_transcript`)
Sent frequently as speech is recognized. Results are subject to correction and do not have timing metadata.
```json
{
  "message_type": "partial_transcript",
  "text": "Hello, how ca"
}
```

### 4.3 Final Committed Text (`committed_transcript`)
Dispatched when VAD detects silence or the client issues a manual commit.
```json
{
  "message_type": "committed_transcript",
  "text": "Hello, how can I help you today?"
}
```

### 4.4 Word-Level Committed Text (`committed_transcript_with_timestamps`)
Sent instead of `committed_transcript` if `include_timestamps=true` was specified in the URL query.
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

### 4.5 Error Event Types
In case of errors, the connection will yield a JSON object with one of the following message types:

- **`auth_error`**: Authorization failed. Check API Key or Token validity.
- **`quota_exceeded`**: Character/Minute usage limits exceeded or subscription unpaid.
- **`commit_throttled`**: Committed chunks sent too quickly.
- **`unaccepted_terms`**: User has not accepted ElevenLabs Terms of Service.
- **`rate_limited`**: Concurrent connection limits or request rate boundaries hit.
- **`queue_overflow`**: Audio buffer overflow. Send audio pacing must strictly mimic real-time.
- **`resource_exhausted`**: Server is under too much load.
- **`session_time_limit_exceeded`**: The 30-minute session duration threshold was breached.
- **`input_error`**: Invalid message format, or `previous_text` sent on non-first chunk.
- **`chunk_size_exceeded`**: Individual payload exceeded standard packet limits.
- **`insufficient_audio_activity`**: Connection closed due to continuous absolute silence.
- **`transcriber_error`**: Internal transcription engine failure.
- **`error`**: Generic fallback error message.
