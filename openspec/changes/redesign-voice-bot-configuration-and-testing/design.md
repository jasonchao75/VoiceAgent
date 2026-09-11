# Design: Voice Bot Configuration and Testing Redesign

## Goals

- Separate Bot-owned settings from provider-owned ASR/LLM/TTS configuration through a component-card and right-drawer information architecture.
- Make Chat test, Web call test and Sessions use one consistent transcript and per-Turn metric presentation.
- Preserve existing LLM diagnostics and retained user-audio history inside the redesigned flows.
- Let callers change speaking speed through natural language during an active call.
- Keep the LLM responsible only for intent classification; keep numeric bounds, state transitions, provider protocol and failure handling deterministic in the Pipeline.
- Use one product-level control across supported TTS providers without hiding provider limitations.
- Make prototype fidelity measurable before product acceptance rather than relying on memory or static DOM assertions.

## Current UI delivery inventory

| Area | Current state | Gap |
|---|---|---|
| Prototype | High-fidelity HTML plus a post-load enhancement script | No machine-readable visual annotation; final DOM is difficult to compare with implementation |
| Frontend | Vanilla JavaScript + Vite; legacy form nodes are moved into the redesigned layout at runtime | Structure can look correct in source while rendered hierarchy and component ownership differ |
| Functional tests | Pytest API/pipeline tests and static frontend string assertions | No browser interaction or accessibility coverage |
| Screenshots | Manual headless screenshots stored in the Change | No paired prototype baseline, deterministic fixture, diff image or ratio |
| CI | Python checks, frontend build and Docker build | No browser installation or visual test job |
| Verification | Markdown checklist | Items can be checked without objective evidence; current ASR screenshots demonstrate this failure |

## Root causes

1. The prototype communicates visual intent, but exact dimensions, tokens, states and allowed adaptations are not recorded.
2. Prototype and implementation do not run against a shared deterministic fixture.
3. Static contract tests check that labels and IDs exist, not that the rendered hierarchy, control type, dimensions or visibility match.
4. Screenshot evidence has no paired approved baseline or automated diff, so a reviewer can mark a section complete based on presence alone.
5. There is no intermediate layout Gate; business wiring and visual correction are mixed, increasing rework.

## Options considered

| Option | Cost | Benefit | Risk |
|---|---|---|---|
| A. Documentation-only checklist | Low | Immediate discipline improvement | Still subjective; repeats the current false-positive failure mode |
| B. Lightweight Playwright workflow (recommended) | Medium | Deterministic states, fixed viewports, screenshots and diff evidence while preserving existing stack | Adds a frontend dev dependency and browser runtime after approval; small maintenance cost |
| C. Dedicated visual-regression platform | High | Hosted review UI, history and collaboration | Premature platform/CI complexity, external service cost and baseline governance overhead |

Recommendation: adopt Option B in phases. This Change first defines contracts, annotations, matrices and fixtures. After Gate 1 approval, add Playwright as a frontend dev dependency and a small screenshot harness. Do not add a SaaS platform or production dependency.

## Risk levels

| Level | Example | Required evidence |
|---|---|---|
| Low | Copy, icon or isolated color | Targeted state screenshot and functional assertion |
| Medium | Component, drawer, form grouping | Component state matrix, desktop and narrow viewport screenshots, diff |
| High | Page redesign, navigation, responsive information architecture | Full matrix, shared fixture, all fixed viewports, functional/accessibility checks and visual diff |

This Change is High risk because it changes navigation, three provider drawers, test pages and Sessions.

## Three delivery gates

1. **Gate 1 — contract and baseline:** approve Delta Specs, prototype, `ui-annotations.md`, `ui-state-matrix.md`, fixed fixture and baseline screenshots. No core UI implementation before approval.
2. **Gate 2 — static shell:** render fixture data without provider calls; compare page geometry, component hierarchy, control types and responsive direction. Business wiring remains out of scope for this review.
3. **Gate 3 — final:** cover loading/empty/error/disabled/long-content/provider states, functional tests and accessibility checks; generate actual screenshots and diffs. User acceptance remains mandatory.

## Proposed visual test design (pending approval)

- Add Playwright only as a frontend dev dependency, not a production dependency.
- Serve prototype and actual page from stable local URLs and inject `tests/ui/fixtures/voice-bot-editor.json` through a test-only route or request interception.
- Pin Chromium major version through Playwright, viewport, device scale factor, locale, timezone and color scheme. Load the repository-approved font or wait for `document.fonts.ready`.
- Disable transitions, animations, caret blinking and timestamps in screenshot mode. Mask only documented dynamic regions; credentials are always fake fixture values or empty.
- Produce `baseline/`, `actual/` and `diff/` files with the same scenario ID. A test run may write actual/diff, but never baseline.
- Initial suggested thresholds: pixel-difference ratio `0.1%` for component crops and `0.3%` for full pages, with zero tolerance for missing/extra controls, wrong control type or wrong component ownership. Thresholds are **[待确认]** after the first calibrated run.
- CI integration is a separate approval inside this Change because it downloads a browser and increases runtime. Gate 2 can first run locally.

## Complete example: ASR drawer

Scenario ID `bot-settings.asr.english.default.desktop` uses viewport `1440×1000`, fixture Bot `asr-default`, English language and no provider calls. Gate 1 baseline records drawer width, field order, read-only Audio input, EOT slider, timeout input, Keyterms textarea, three toggle/select controls and a Deepgram-only credential card. Gate 2 captures the static implementation and fails if Audio input is absent, EOT is a number field, or an LLM Key appears. Gate 3 additionally exercises Automatic language, hints, loading failure, validation errors, keyboard focus and narrow viewport. Evidence is recorded in `verification/ui-checklist.md` and `verification/visual-diffs.md`.

## Non-goals

- Evaluation, account management, SIP line management, speaking-order selection or System prompt generation.
- Introducing selectable 8 kHz WebCall input before a transport/resampling Change.
- Treating prototype-only simulation controls or sample timings as production behavior.
- Changing Flux expressivity, ElevenLabs stability, similarity, style or voice during a call.
- Persisting a caller’s temporary preference back to the Bot.
- Claiming deterministic speed control for Eleven v3 through prompt wording or audio tags.
- Implementing the control as an MCP server. It is an in-process, latency-sensitive session tool.

## Configuration

Add two Bot fields:

| Field | Type | Default | Rules |
|---|---|---:|---|
| `tts_dynamic_speed_enabled` | boolean | `false` | Existing Bots remain unchanged; the LLM tool is registered only when enabled and supported by the selected model path. |
| `tts_speed_step` | number | `0.10` | `0.05`–`0.25`, in `0.05` increments. Used for each `faster` or `slower` command. |

The saved `tts_speed` remains the session’s configured initial speed. Provider ranges are deterministic platform validation, not user-configurable limits:

| Provider/model | Range | Increment | Runtime update |
|---|---:|---:|---|
| Deepgram Flux `/v2/speak` | `0.5`–`1.5` | `0.05` | Independent `Configure` message; effective at the next provider segment boundary |
| ElevenLabs Flash/Turbo/Multilingual TTS WebSocket | `0.7`–`1.2` | `0.05` | Updated `voice_settings` on subsequent text messages |
| Eleven v3 | Unsupported | — | Feature disabled; agent must not claim it changed speed |

The wider Flux range supersedes the earlier conservative `0.85`–`1.15` product limit because the current provider contract accepts `0.5`–`1.5`. The UI should still warn that extreme values can reduce naturalness.

## LLM Tool Contract

Register one local function when the feature is enabled:

```json
{
  "name": "set_speech_speed",
  "description": "Change this agent's speaking speed for the current call when the caller explicitly asks.",
  "parameters": {
    "type": "object",
    "properties": {
      "action": {
        "type": "string",
        "enum": ["faster", "slower", "normal", "configured"]
      }
    },
    "required": ["action"],
    "additionalProperties": false
  }
}
```

- `faster` and `slower` move one configured step from the current effective speed.
- `normal` targets `1.0`.
- `configured` returns to the Bot’s saved initial speed.
- The LLM never supplies a numeric multiplier. The executor validates the enum and calculates, rounds and clamps the target.
- The tool result returns structured status (`applied`, `at_limit`, `unsupported`, or `failed`) plus old and effective speed. The LLM may acknowledge only the returned result.

## Session State and Ordering

Create a session-scoped controller owned by the active Pipeline:

| State | Meaning |
|---|---|
| `configured_speed` | Immutable initial value copied from the Bot at session creation |
| `current_speed` | Last provider-accepted/effective value |
| `pending_speed` | Target sent to the provider but not yet confirmed; otherwise `null` |

All updates pass through one asynchronous lock so overlapping tool calls cannot calculate from stale state.

1. The caller’s request reaches the LLM after ASR finalization.
2. The LLM emits `set_speech_speed` instead of a spoken response.
3. The Pipeline executor computes the target from `current_speed` and the Bot’s step.
4. The provider adapter applies the target.
5. On success, the controller commits `current_speed`, clears `pending_speed`, and returns an `applied` result to the LLM.
6. The LLM generates a short confirmation; that response is synthesized with the new speed.
7. On rejection or timeout, the controller retains the prior speed and returns `failed`; the LLM must not claim success.

The state lives only in memory and is destroyed with the session lease. It must not be written to Bot storage or reused by another call.

## Provider Mapping

### Deepgram Flux

The adapter sends `{"type":"Configure","speed":target}` on the existing WebSocket and waits, with a bounded timeout, for `ConfigureSuccess` or `ConfigureFailure`. A success acknowledges validation/receipt; audio already synthesized is unchanged and the setting applies at the next segment boundary.

### ElevenLabs non-v3

The adapter updates its session-local voice settings only after deterministic validation. Every subsequent outbound text message includes the complete effective `voice_settings`, including the new Speed and the Bot’s unchanged Stability, Similarity, Style and Speaker Boost values. Already buffered/generated audio is unchanged. Provider send/generation failure must surface as `failed` and retain or restore the last known valid local setting.

### Eleven v3

Eleven v3 does not expose the numeric Speed control used by the TTS WebSocket. Selecting v3 disables the Advanced control. The session instruction must state that precise speed changes are unavailable so the agent explains the limitation rather than claiming success. Prompt-based pacing is explicitly not treated as an equivalent fallback.

## LLM Compatibility

Pipecat supplies the function-calling event and callback plumbing, but the tool schema, executor, session controller and provider commands are application code. Native OpenAI and Gemini paths use their supported structured tool interfaces. A custom OpenAI-compatible endpoint that rejects tool definitions must fail clearly during session start or tool execution; the system must not silently fall back to parsing ordinary assistant text as JSON.

## UI and Prototype

The approved interaction is captured in `prototypes/index.html`:

- The application rail contains only VoiceAgent in this release and supports collapsed icon-only and expanded icon-plus-name states. Account and SIP line entries are reserved but absent.
- Bot settings contains the component pipeline plus Bot name, Opening message and System prompt. Provider/model parameters and credentials never appear on the main page.
- ASR, LLM and TTS open as non-modal right panels that compress the workspace. The selected card gains an active state and its directional icon communicates that a second click collapses the panel.
- Pipeline cards show persisted configuration facts only. Latency is omitted until a measured-history feature can supply it.
- The `Advanced` top-level tab contains only the Bot-level LLM timeout Fallback script. Evaluation, speaking order and prompt generation are deferred.

### TTS hierarchy and provider state

- Basic order: Provider, Model, provider credential, Voice, Initial speed.
- One Advanced section follows Initial speed. Its fixed order is Text aggregation, Conversational speed control, then provider-specific tuning.
- Provider changes replace every dependent state; ElevenLabs values must never remain visible after selecting Deepgram and vice versa.
- ElevenLabs account voice discovery is credential-gated and retains Custom voice ID. Deepgram Flux uses the public platform catalog, may be browsed before credential entry and has no Custom voice ID.
- Voice results support text and metadata filters. A deterministic A–Z initial avatar is derived from the displayed voice name; no image asset is required.
- Conversational controls include enabled state and adjustment step. Unsupported Eleven v3 disables them with explicit copy.

### LLM Thinking and diagnostic

- Custom OpenAI-compatible Model remains free-form, so the frontend cannot infer thinking support from the model string.
- Thinking Advanced offers `provider_default`, `off` and `minimal` as explicit overrides. `provider_default` omits the override; unsupported explicit values surface through the diagnostic or test path.
- Streaming remains platform-default and is not rendered as a configurable field.
- `Test LLM connection` uses current unsaved Base URL, Model, Key and Thinking values. It does not save the Bot and returns safe success/failure information plus measured TTFT.

### Test and history presentation

- `Test bot` opens dedicated Chat test and Web call test pages. Both expose Start and End lifecycle controls and play the configured Opening message.
- Chat test bypasses only ASR; LLM and TTS remain active. Sending text during Agent playback interrupts the playback and records barge-in.
- Web call shows two-sided live captions. The prototype simulation button is a demonstrator only and must be removed in production.
- A completed interaction Turn is user input followed by one Agent reply. The reply owns the metric card placed immediately beneath it; metrics are never deferred to a page-level summary.
- Chat Turn metrics contain LLM splicing, LLM TTFT, TTS initial, TTS TTFT and playback. Web call adds ASR final using the same visual order and missing-reason rules.
- Sessions remains a filterable reverse-time list. View opens a collapsible non-modal detail drawer while the list remains visible.
- Session detail uses the same bubble alignment and inline metric cards without redundant Agent/Caller labels. The retained user-uplink recording sits above the transcript with format and retention metadata; Agent TTS is not recorded and Chat test has no audio recording.

### ASR capability catalog

The Bot editor MUST NOT hardcode ASR provider, model or language choices in frontend code. Extend the existing `GET /api/catalogs` response with an `asr_providers` capability catalog. Each provider entry contains its selectable models, and each model contains the language choices it supports plus the provider request value that choice maps to.

For the current release the catalog exposes only:

| Provider | Product model label | Language choice | Provider model mapping |
|---|---|---|---|
| Deepgram | Flux ASR | English | `flux-general-en` |
| Deepgram | Flux ASR | Automatic | `flux-general-multi` |

The frontend fetches the catalog when the Bot editor loads, then rebuilds the model and language controls whenever the upstream selection changes. Saved values MUST be validated against the same server-side catalog so stale or fabricated combinations cannot be submitted. If catalog loading fails, the dependent controls remain disabled and show a retryable error; they MUST NOT fall back to invented options.

ASR model/language capability is the single source of truth for recognition language. The main Bot identity section MUST NOT expose a separate `Primary language` field.

“Automatically pull” means the frontend pulls provider capabilities from the VoiceAgent backend catalog rather than embedding vendor values. The backend catalog remains the controlled compatibility boundary and can later be populated or refreshed from a vendor-supported discovery API where one exists.

### Bot-scoped Flux ASR configuration

Flux ASR settings belong to each Bot and MUST be copied into the session lease when a call starts. The Pipeline MUST NOT read these values from the global `RuntimeConfig.asr`. Existing Bots migrate to provider defaults.

| Bot field | Rule | Runtime behavior |
|---|---|---|
| `asr_model` | `flux-general-en` or `flux-general-multi` | Connection-time |
| `asr_language_hints` | Optional unique subset of `en, es, fr, de, hi, ru, pt, ja, it, nl`; only with multilingual model | Connection-time; Configure-capable |
| `asr_eot_threshold` | `0.5..1.0`, default `0.7` | Connection-time; Configure-capable |
| `asr_eot_timeout_ms` | `500..60000`, default `5000` | Connection-time; Configure-capable |
| `asr_keyterms` | Up to 100 plain terms or phrases; no weights | Connection-time; Configure replaces the full list |
| `asr_profanity_filter` | Boolean, default false | Connection-time only |
| `asr_numerals` | Boolean, default false | Connection-time only |
| `asr_redact` | Null, `numbers`, or `aggressive_numbers` | Connection-time only |

When Automatic is selected, the UI switches to `flux-general-multi`, states that Flux recognizes only the ten catalog languages, and reveals an optional multi-select for language hints. No selection means automatic detection across those ten languages.

Users enter keyterms as unescaped text, one term or phrase per line (for example `Riyad Bank` or `customer service`). They MUST NOT enter `%20`. The adapter URL-encodes connection query parameters, while mid-stream Configure sends the same values as a JSON string array.

### Eager EOT behavior in current Pipecat

Pipecat 1.8.1 does not perform speculative LLM execution. `EagerEndOfTurn` becomes an `InterimTranscriptionFrame`, while `TurnResumed` only invokes an event callback. The current context aggregator therefore waits for the finalized `EndOfTurn` transcript before invoking the LLM, and there is no in-flight LLM/TTS cancellation or retry caused by `TurnResumed`.

Implementing “start LLM on Eager EOT, cancel on TurnResumed, restart after final EndOfTurn” requires an application-owned speculative-response gate, generation identity, cancellation propagation and context rollback. Eager EOT configuration is therefore not exposed or persisted in this Change and remains disabled; it requires a later dedicated Change.

### Browser audio input

The current WebCall pipeline accepts only mono Linear16 PCM at 16 kHz. This is enforced by `AudioConfig.input_sample_rate: Literal[16000]` and used by the browser transport, recorder and Flux STT service. Therefore the current prototype exposes `PCM · 16 kHz` as read-only capability information; 8 kHz input is outside this Change and requires a separate transport/resampling Change before it can become selectable.

## Failure, Metrics and Safety

- Provider updates use explicit timeouts and never block the realtime event loop.
- Invalid tool arguments, provider rejection, timeout and unsupported models produce safe structured results without API keys or raw provider payloads.
- Emit a non-secret session event containing provider, action, old speed, target speed, final status and duration. It is diagnostic metadata, not a new latency KPI and does not alter existing turn calculations.
- Barge-in continues to cancel queued playback before the command turn; previously generated audio is never retroactively modified.

## Verification Strategy

- Unit-test target calculation, rounding, clamping, reset actions and concurrent serialization.
- Adapter-test Flux success/failure/timeout and ElevenLabs subsequent-message settings without live paid calls.
- Pipeline-test tool ordering so confirmation text reaches TTS only after a successful update.
- Compatibility-test feature-disabled, Eleven v3 and unsupported custom LLM paths.
- UI-test persistence, provider/model switching, disabled states and prototype screenshot parity.
- Run an opt-in live smoke test for each provider with BYOK credentials before production approval.
