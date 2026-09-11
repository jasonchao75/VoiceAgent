# UI State Matrix

Status: Gate 1 candidate; scenario IDs are stable screenshot/test identifiers.

| ID | Page/region | Data state | Interaction/error state | Viewport | Delta mapping | Evidence required |
|---|---|---|---|---|---|---|
| auth.login.default | Login | Signed out | Default/hover/focus | desktop+narrow | Product-owned login experience | baseline/actual/diff+a11y |
| auth.login.invalid | Login | Invalid credentials | Error | desktop+narrow | Submit invalid login credentials | baseline/actual/diff+functional+a11y |
| auth.login.expired | Login | Expired website session | Informational | desktop+narrow | Website login expires | baseline/actual/diff+functional |
| auth.avatar.logout | Product rail | Signed in | Hover/focus/touch menu | desktop+narrow | Sign out | baseline/actual/diff+functional+a11y |
| bot-settings.base.empty | Bot settings | No Bots | Empty | desktop | Componentized Bot editor | baseline/actual/diff |
| bot-settings.base.long | Bot settings | Long names/prompts | Default | desktop+narrow | Approved prototype conformance | baseline/actual/diff |
| bot-settings.asr.english.default | ASR drawer | English Flux | Expanded | desktop | Current WebCall input format; Persist Flux ASR settings | baseline/actual/diff+a11y |
| bot-settings.asr.automatic.hints | ASR drawer | Automatic + hints | Expanded | desktop | Configure Automatic language detection | baseline/actual/diff+functional |
| bot-settings.asr.catalog.loading | ASR drawer | Catalog pending | Loading | desktop | ASR options catalog | actual+functional |
| bot-settings.asr.catalog.error | ASR drawer | Catalog failed | Retry/error | desktop | Fail to load ASR capabilities | actual+functional+a11y |
| bot-settings.asr.validation | ASR Advanced | Invalid timeout/101 terms | Error | desktop | Reject unsupported ASR combinations | actual+functional+a11y |
| bot-settings.llm.default | LLM drawer | Unsaved config | Advanced expanded | desktop | LLM Thinking and diagnostic | baseline/actual/diff |
| bot-settings.llm.diagnostic | LLM drawer | Valid/invalid endpoint | Loading/success/error | desktop | Test explicit override | actual+functional+a11y |
| bot-settings.tts.eleven.no-key | TTS drawer | ElevenLabs, no Key | Disabled | desktop | Browse ElevenLabs voices | baseline/actual/diff |
| bot-settings.tts.eleven.voices | Voice picker | Loaded catalog | Search/filter/page | desktop+narrow | Filter and identify voices | baseline/actual/diff+functional |
| bot-settings.tts.deepgram | TTS drawer | Deepgram Flux | Expanded | desktop | Browse Deepgram voices | baseline/actual/diff |
| chat.active.barge-in | Chat test | Two Turns | Playing/interrupted | desktop | Interrupt Chat playback | actual+functional |
| webcall.active.captions | Web call | Two Turns | Listening/playing | desktop | Run Web call test | actual+functional |
| sessions.list.empty | Sessions | No sessions | Empty | desktop | Sessions list | baseline/actual/diff |
| sessions.detail.recording | Session drawer | Web call recording | Available | desktop+narrow | Play retained audio | baseline/actual/diff+functional |
| sessions.detail.expired | Session drawer | Expired recording | Unavailable | desktop | Recording unavailable | actual+functional |

Dynamic masking is allowed only for measured latency values, generated IDs, recording duration progress and timestamps. Labels, containers and metric ownership are never masked.
