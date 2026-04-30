import os

filepath = '/Volumes/work/OpenCode/VoiceAgent/.opencode/skills/vendor-speechmatics/speechmatics-docs/voice-agent-api.md'
with open(filepath, 'r') as f:
    lines = f.readlines()

# keep lines up to 121 (which is index 120, wait 121 lines means index 0 to 120. Line 121 is the > 防幻觉红线: ... block)
# Let's find the exact line containing "防幻觉红线"
end_idx = 0
for i, line in enumerate(lines):
    if "防幻觉红线" in line:
        end_idx = i + 1
        break

header_lines = lines[:end_idx]

content = """
```markdown
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

## Features
### Speaker Focus
Speaker focus lets you control which speakers' output your agent acts on.
- `focus_speakers`: speaker IDs to treat as active.
- `ignore_speakers`: speaker IDs to exclude entirely.
- `focus_mode`: what happens to other speakers (`retain` or `ignore`).

### Speaker ID
Speaker ID lets you recognise the same person across separate sessions. Store the `speaker_identifiers` from `SpeakersResult` and pass them into `StartRecognition` via `transcription_config.known_speakers`.
```
"""

with open(filepath, 'w') as f:
    f.writelines(header_lines)
    f.write("\n")
    f.write(content.strip())
    f.write("\n")
