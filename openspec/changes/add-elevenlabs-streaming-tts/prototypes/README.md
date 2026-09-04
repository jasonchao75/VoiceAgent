# UI Prototype Baseline

Status: approved by product on 2026-09-03

Open `index.html` directly in a browser. It uses the current Platform layout and entry:

`Your bots → New bot/Edit → Pipeline → TTS provider → Voice → Choose`

## Traceability

| Prototype area | Delta requirement / scenario |
|---|---|
| Provider selector | Bot configuration persistence |
| Provider-aware API keys | Optional encrypted credential storage |
| Voice trigger and modal | ElevenLabs account voice discovery |
| Search and dynamic filters | Voice list succeeds; Filter Deepgram voices |
| Pagination and manual ID | Large result set; Voice list fails |
| Existing metrics panel | Provider-neutral latency requirements |

Behavior follows Delta Specs; approved visual structure and interaction follow this prototype. Demo voice data is illustrative and must not become a production catalog.
