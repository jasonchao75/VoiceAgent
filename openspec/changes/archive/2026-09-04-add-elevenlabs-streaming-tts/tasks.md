# Tasks: Add ElevenLabs Streaming TTS

## 1. Configuration and Credentials

- [x] 1.1 Extend provider-aware TTS config and request schemas
- [x] 1.2 Add encrypted ElevenLabs Key column with idempotent SQLite migration
- [x] 1.3 Implement provider-conditional saved/BYOK credential validation and clearing
- [x] 1.4 Add public ElevenLabs model metadata without exposing credentials
- [x] 1.5 Persist and validate ElevenLabs model plus voice settings with backward-compatible defaults
- [x] 1.6 Persist provider-neutral TTS text aggregation and derive provider-safe runtime settings

## 2. Provider Integration

- [x] 2.1 Register Pipecat `ElevenLabsTTSService` with PCM 24 kHz streaming settings
- [x] 2.2 Select the provider-specific credential in the Pipeline
- [x] 2.3 Verify interruption, disconnect, opening script and timing frames remain provider-neutral
- [x] 2.4 Persist TTS provider/model/voice snapshots without changing latency formulas
- [x] 2.5 Pass model-compatible voice settings and Auto mode into the WebSocket service

## 3. Voice Discovery and UI

- [x] 3.1 Add timeout-bounded ElevenLabs voice-list proxy with sanitized responses/errors
- [x] 3.2 Build one provider-neutral searchable Voice Picker for Deepgram and ElevenLabs
- [x] 3.3 Support dynamic voice selection plus manual voice ID fallback
- [x] 3.4 Update session BYOK fields and provider-specific validation messages
- [x] 3.5 Derive voice filter options dynamically from provider metadata and map missing values to `Unspecified`
- [x] 3.6 Rebuild the Bot editor strictly from the approved prototype, including field order, grouping, control types, defaults and responsive layout
- [x] 3.7 Preserve the full Voice Picker modal/card/search/filter/preview/pagination/manual-ID interaction; do not substitute a native select

## 4. Verification and Delivery

- [x] 4.1 Add registry, config, API, storage migration and Pipeline tests
- [ ] 4.2 Add parity tests proving both providers produce the same metric schema and missing-reason behavior
- [x] 4.3 Run safety, format, lint, typecheck, unit tests, frontend build and Docker build
- [ ] 4.4 Push and verify CI/CD plus public health endpoint
- [ ] 4.5 With explicit approval, run one paid ElevenLabs end-to-end smoke test
- [ ] 4.6 Verify every prototype state at desktop and narrow viewport, attach side-by-side implementation screenshots, and resolve visible/interaction differences before delivery
- [x] 4.7 Add range, persistence, factory passthrough and model regression tests for the new settings
- [ ] 4.8 Add UI regression coverage for provider/model/aggregation switching, v3 disabled states, voice search/filter/preview/select, pagination and manual-ID fallback
