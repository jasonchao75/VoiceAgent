# Tasks: Redesign Voice Bot Configuration and Testing

## 0. UI delivery gates (current status: Gate 1 and Gate 2 approved; Gate 3 engineering verification in progress)

- [x] 0.1 Inventory the current prototype, frontend stack, tests, screenshots and CI
- [x] 0.2 Document root causes and compare three delivery approaches
- [x] 0.3 Add prototype precision annotations and page-state matrix templates for this Change
- [x] 0.4 Define a deterministic, non-secret UI fixture contract and ASR drawer example
- [x] 0.5 Product confirms the interactive prototype and five-area Gate 1 scope; the prototype is the implementation baseline
- [x] 0.6 After approval only: add Playwright as a frontend dev dependency and implement local fixed-viewport functional/screenshot commands
- [ ] 0.7 Capture and approve immutable prototype baseline screenshots; record approver and checksum
- [x] 0.8 Complete static shell comparison and product visual-direction review (Gate 2)
- [ ] 0.9 Complete state coverage, functional/accessibility checks, actual/diff evidence and product acceptance (Gate 3)
- [ ] 0.10 Propose CI integration impact and obtain approval before modifying workflows

## 1. Contracts, Catalogs and Persistence

- [x] 1.1 Add/migrate Bot-scoped Flux ASR fields and remove runtime-global business configuration reads
- [x] 1.2 Extend the server-owned ASR catalog with the current Deepgram / Flux ASR / English / Automatic capability graph
- [x] 1.3 Add/migrate `tts_dynamic_speed_enabled` and `tts_speed_step`; centralize provider-specific speed validation
- [x] 1.4 Add LLM Thinking override persistence without inferring capability from free-form model IDs
- [x] 1.5 Add API validation, migration, Bot isolation and catalog-failure tests

## 2. Bot Editor Information Architecture

- [x] 2.1 Implement the collapsible VoiceAgent-only product rail and current Bot list
- [x] 2.2 Split ASR, LLM and TTS into summary cards with selected/collapse states and non-modal workspace-compressing drawers
- [x] 2.3 Keep only Bot name, Opening message and System prompt on Bot settings; remove duplicate Primary language
- [x] 2.4 Keep Advanced limited to the Bot fallback script and omit Evaluation, speaking-order selection, prompt generation, account and SIP management
- [x] 2.5 Ensure component summaries contain configuration facts only and no unmeasured latency values

## 3. ASR Drawer

- [x] 3.1 Populate provider/model/language controls from the backend catalog and implement retryable catalog failure state
- [x] 3.2 Implement Automatic language with optional multi-select hints and ten-language limitation copy
- [x] 3.3 Implement Bot-scoped EOT threshold/timeout, keyterms, profanity filter, numerals and redact
- [x] 3.4 Keep input fixed at mono Linear16 PCM 16 kHz; omit 8 kHz, Eager EOT, endpointing, smart detection and noise suppression
- [x] 3.5 Add field-level validation and plain keyterm examples without requiring URL escaping

## 4. LLM Drawer and Diagnostic

- [x] 4.1 Implement Provider default / Off / Minimal Thinking override in Advanced; do not expose Streaming
- [x] 4.2 Preserve free-form Custom OpenAI-compatible Model entry without frontend capability guessing
- [x] 4.3 Reuse the LLM diagnostic endpoint with current unsaved endpoint/model/key/Thinking values
- [x] 4.4 Display success/failure, safe diagnostic details and measured TTFT without saving the Bot
- [x] 4.5 Persist per-Bot max response tokens, request timeout and fallback script; speak the fallback on completion timeout

## 5. TTS Drawer and Voice Picker

- [x] 5.1 Keep provider/model/Key/Voice/Initial speed as basic fields and one ordered Advanced section after them
- [x] 5.2 Put Text aggregation first, conversational speed second and provider-specific tuning last
- [x] 5.3 Implement full ElevenLabs/Deepgram provider switching for model, credential, voice catalog, speed range and Advanced controls
- [x] 5.4 Require an ElevenLabs Key before account voice discovery; allow Deepgram catalog browsing without a Key
- [x] 5.5 Keep Custom voice ID for ElevenLabs only; add search and metadata-driven filters plus deterministic initial avatars
- [x] 5.6 Implement ElevenLabs tuning and Deepgram Flux Expressivity/model-improvement opt-out states

## 6. Conversational Speed Runtime

- [x] 6.1 Implement session-scoped configured/current/pending speed state with serialized updates
- [x] 6.2 Register and execute the provider-neutral `set_speech_speed` tool only when enabled and compatible
- [x] 6.3 Implement deterministic faster/slower/normal/configured calculations and structured results
- [x] 6.4 Implement Flux `Configure` correlation/timeout and ElevenLabs non-v3 subsequent-message settings
- [x] 6.5 Reject unsupported Eleven v3 behavior and prevent false success claims

## 7. Test Bot Experience

- [x] 7.1 Implement separate Chat test and Web call test secondary pages with Start/End lifecycle
- [x] 7.2 Make Chat test execute LLM + TTS, play Opening message and record text-send-during-playback as barge-in
- [x] 7.3 Add two-sided Web call live captions; exclude the prototype-only simulation control from production
- [x] 7.4 Render E2E and component timings immediately below each Agent reply: Chat omits ASR final, Web call includes it
- [x] 7.5 Preserve missing/incomplete metric reasons and never substitute fabricated production latency

## 8. Sessions Experience

- [x] 8.1 Keep reverse-time row list, time/type filters and per-row View action
- [x] 8.2 Open a collapsible non-modal right drawer for the selected Session without replacing the list
- [x] 8.3 Show transcript bubbles without redundant Agent/Caller labels and keep each Turn metric beneath its Agent reply
- [x] 8.4 Add retained user-uplink recording playback, format/retention metadata and unavailable/expired/failure states
- [x] 8.5 Show no recording for Chat test and never imply that Agent TTS downlink is stored

## 9. Verification and Delivery

- [ ] 9.1 Add automated UI tests for drawers, provider dependencies, credential gates, test lifecycle, barge-in and Sessions detail
- [ ] 9.2 Complete `verification/ui-checklist.md` and capture implementation screenshots against the approved prototype
- [x] 9.3 Run lint, typecheck, backend tests, frontend build, Docker build and strict OpenSpec validation
- [ ] 9.4 Run opt-in BYOK smoke tests for ASR, LLM diagnostic, both TTS providers, Chat test, Web call and history recording
- [x] 9.5 Confirm no API keys, recordings, logs, caches or prototype-only simulation behavior enter commits/production
- [ ] 9.6 Push after product approval, verify CI/CD and check production health

Gate 3 note (2026-09-10): Playwright desktop/narrow state tests pass 14/14 and actual screenshots are recorded. BYOK LLM diagnostic, Deepgram Flux Chat and ElevenLabs Chat passed. Web call remains unverified on this host because no microphone is available; immutable pixel baselines/diffs and final product acceptance remain open.

## 10. Product login and authentication separation (scope pending product confirmation)

- [x] 10.1 Product confirms shared account, idle/absolute expiry, return path, product name and avatar/logout behavior in `verification/login-flow-review.md`
- [x] 10.2 Add and approve a `VoiceAgent Demo` login-page prototype plus signed-out, invalid, expired, narrow-screen and left-rail avatar/logout states before implementation
- [x] 10.3 Replace browser Basic Auth challenges with secure Cookie-based website sessions while retaining the existing shared deployment credential source
- [x] 10.4 Keep Chat/Web call Bearer events and metrics authorization separate from the website session
- [x] 10.5 Add login/logout, expiry return-path, generic-error, retry-limiting and no-native-popup backend tests
- [x] 10.6 Add Playwright coverage for login success/failure/expiry/logout and Chat metrics after login
- [ ] 10.7 Complete fixed-viewport screenshots and Gate 2/3 evidence before production deployment
