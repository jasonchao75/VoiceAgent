# Tasks: Add ElevenLabs Streaming TTS

## 1. Configuration and Credentials

- [x] 1.1 Extend provider-aware TTS config and request schemas
- [x] 1.2 Add encrypted ElevenLabs Key column with idempotent SQLite migration
- [x] 1.3 Implement provider-conditional saved/BYOK credential validation and clearing
- [x] 1.4 Add public ElevenLabs model metadata without exposing credentials

## 2. Provider Integration

- [x] 2.1 Register Pipecat `ElevenLabsTTSService` with PCM 24 kHz streaming settings
- [x] 2.2 Select the provider-specific credential in the Pipeline
- [ ] 2.3 Verify interruption, disconnect, opening script and timing frames remain provider-neutral
- [x] 2.4 Persist TTS provider/model/voice snapshots without changing latency formulas

## 3. Voice Discovery and UI

- [x] 3.1 Add timeout-bounded ElevenLabs voice-list proxy with sanitized responses/errors
- [x] 3.2 Build one provider-neutral searchable Voice Picker for Deepgram and ElevenLabs
- [x] 3.3 Support dynamic voice selection plus manual voice ID fallback
- [x] 3.4 Update session BYOK fields and provider-specific validation messages
- [x] 3.5 Derive voice filter options dynamically from provider metadata and map missing values to `Unspecified`

## 4. Verification and Delivery

- [x] 4.1 Add registry, config, API, storage migration and Pipeline tests
- [ ] 4.2 Add parity tests proving both providers produce the same metric schema and missing-reason behavior
- [ ] 4.3 Run safety, format, lint, typecheck, unit tests, frontend build and Docker build
- [ ] 4.4 Push and verify CI/CD plus public health endpoint
- [ ] 4.5 With explicit approval, run one paid ElevenLabs end-to-end smoke test
- [ ] 4.6 Verify against the prototype traceability map and UI checklist, then attach final screenshots
