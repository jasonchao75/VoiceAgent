# Provider Key Re-entry Checklist

## Scope

- Generated: 2026-09-30
- Evidence level: `external-real` inventory, values never read or logged
- Storage Key rotation: Completed for local and DigitalOcean environments
- DigitalOcean service restart: Healthy; both Bot records preserved
- Local database: no Bots, so no local Provider Key re-entry is required
- DigitalOcean: preserve Bot records and re-enter only the saved credentials listed below

## DigitalOcean Bots

### DeepgramFlux

- Bot ID: `eb373ea0-9052-42f4-85a8-e55e113f20af`
- ASR: Deepgram — saved key present before rotation; re-entry required
- TTS: Deepgram Flux — saved key present before rotation; re-entry required
- LLM: Custom — saved key present before rotation; re-entry required
- Status: Pending user re-entry

### Elevenlabs Turbo

- Bot ID: `e8faae75-3b83-41c5-a2bb-c06207eeb806`
- ASR: Deepgram — saved key present before rotation; re-entry required
- TTS: ElevenLabs — saved key present before rotation; re-entry required
- LLM: Google Gemini — saved key present before rotation; re-entry required
- Status: Pending user re-entry

## Safety Notes

- No API Key value is included in this file.
- Bot definitions, history, recordings, and public links are not deleted by Storage Key rotation.
- Until re-entry is complete, calls that depend on these saved credentials are expected to fail safely.
- BYOK requests provide credentials per request and are not affected by the stored-key rotation.
