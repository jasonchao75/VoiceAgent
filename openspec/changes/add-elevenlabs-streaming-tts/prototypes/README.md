# UI Prototype Baseline

Status: approved by product on 2026-09-03

Open `index.html` directly in a browser. It uses the current Platform layout and entry:

`Your bots → New bot/Edit → Pipeline → TTS provider → Voice → Choose`

## Traceability

| Prototype area | Delta requirement / scenario |
|---|---|
| Provider selector | Bot configuration persistence |
| TTS text aggregation selector | Configure TTS text aggregation; derive ElevenLabs Auto mode |
| Model and Voice tuning | Configure an ElevenLabs voice; invalid setting validation |
| Read-only Auto mode state | ElevenLabs aggregation derives Auto mode |
| Provider-aware API keys | Optional encrypted credential storage |
| Voice trigger and modal | ElevenLabs account voice discovery |
| Search and dynamic filters | Voice list succeeds; Filter Deepgram voices |
| Pagination and manual ID | Large result set; Voice list fails |
| Existing metrics panel | Provider-neutral latency requirements |

Behavior follows Delta Specs; approved visual structure and interaction follow this prototype. Implementation may replace demo data and static copy with real state, but must not simplify or materially rearrange the confirmed controls and Voice Picker. Demo voice data is illustrative and must not become a production catalog.

The prototype intentionally does not expose Vapi's caching, pronunciation dictionary, fallback voice, SSML, or legacy HTTP `optimizeStreamingLatency` controls. They are separate platform capabilities or do not map to the selected bidirectional WebSocket transport.
