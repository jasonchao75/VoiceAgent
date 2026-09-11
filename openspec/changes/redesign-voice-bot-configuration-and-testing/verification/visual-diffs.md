# Visual Difference Register

Status: Gate 1 approved and Gate 2 visual direction accepted. Playwright actual captures now cover fixed desktop/narrow viewports; immutable pixel baseline approval and generated diff ratios remain pending.

| Scenario | Prototype baseline | Actual | Diff | Ratio | Known difference / decision | Result |
|---|---|---|---|---:|---|---|
| bot-settings.asr.english.default | Approved prototype / ASR drawer | `actual/bot-settings.asr.english.default.jpg` | Manual side-by-side | — | Audio input, Advanced control shapes and isolated editable credential card now match the approved structure | Pass (manual) |
| bot-settings.asr.automatic.hints | Approved Automatic state | `actual/bot-settings.asr.automatic.hints.jpg` | Manual side-by-side | — | Optional ten-language checkbox grid is shown only for Automatic | Pass (manual) |
| bot-settings.llm.default | Approved prototype / LLM drawer | `actual/bot-settings.llm.default.jpg` | Manual side-by-side | — | Temperature, Advanced fields, component credential and connection test order checked | Pass (manual) |
| bot-settings.tts.deepgram | Approved prototype / TTS drawer | `actual/bot-settings.tts.deepgram.jpg` | Manual side-by-side | — | Deepgram voice catalog is not Key-gated and has no Custom Voice ID | Pass (manual) |
| bot-settings.tts.eleven.no-key | Approved ElevenLabs no-Key state | `actual/bot-settings.tts.eleven.no-key.jpg` | Manual side-by-side | — | Credential precedes Voice and account voice discovery is disabled without a Key | Pass (manual) |
| bot-settings.tts.deepgram.voices | Approved voice-library state | `actual/bot-settings.tts.deepgram.voices.jpg` | Manual side-by-side | — | Search, language/gender filters, readable row list and deterministic initials checked | Pass (manual) |
| chat.idle | Approved Chat test shell | `actual/chat.idle.jpg` | Manual side-by-side | — | Page title, Start/End controls, compact status and large transcript area aligned | Pass (manual) |
| webcall.idle | Approved WebCall shell | `actual/webcall.idle.jpg` | Manual side-by-side | — | No production simulation control; page title, lifecycle controls and caption area aligned | Pass (manual) |
| sessions.list.empty | Approved Sessions list shell | `actual/sessions.list.empty.jpg` | Manual side-by-side | — | Row-list location, filters and empty state checked; populated View drawer requires fixture/data | Pass (manual shell) |
| gate3.llm | Approved LLM drawer | `actual/gate3.llm.{desktop,narrow}-chromium.png` | Automated structural comparison | — | Advanced fields, component-only credentials and overflow invariant | Pass |
| gate3.voice-picker | Approved filtered voice list | `actual/gate3.voice-picker.{desktop,narrow}-chromium.png` | Automated structural comparison | — | Deterministic two-language fixture, long copy and no horizontal overflow | Pass |
| gate3.sessions | Approved populated Sessions list | `actual/gate3.sessions.{desktop,narrow}-chromium.png` | Automated structural comparison | — | Production snapshot list, English dates and collapsible detail | Pass |
| gate3.advanced | Approved Bot-scoped Advanced | `actual/gate3.advanced.{desktop,narrow}-chromium.png` | Automated structural comparison | — | Bot selector retained and fallback belongs to selected Bot | Pass |

Baseline files may only be added or replaced by the explicit baseline-approval task. A normal test run writes only actual and diff artifacts.

## Remaining differences and unverified states

- Exact pixel ratios remain pending immutable baseline capture/approval; normal test runs do not create or update baselines.
- Chat audio and inline Turn metrics were exercised with both TTS providers. Live Web call microphone and acoustic barge-in remain unverified because this host has no microphone.
- The 1275 × 1114 screenshots are manual Gate 2 evidence, not immutable automated baselines.
