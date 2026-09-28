# Voice Bot Configuration and Testing Prototype

Status: application prototype approved on 2026-09-08; login prototype approved on 2026-09-10 after removing architecture-specific pipeline copy

Open `index.html` directly in a browser for the application baseline. Open `login.html` for the confirmed product-owned login direction. Together they cover the componentized Bot editor, component drawers, Chat/Web call tests, Sessions history detail and website access states.

## Confirmed product decisions

- The user-facing platform name is `VoiceAgent Demo` everywhere. Product rail supports collapsed/expanded states; account and SIP line management are deferred.
- Login is a styled `VoiceAgent Demo` page rather than a browser Basic Auth popup. It uses the same visual system, returns to the requested page, and keeps website login separate from call tokens.
- Bot settings contains only Bot name, Opening message and System prompt. ASR/LLM/TTS configuration and credentials live in non-modal right drawers.
- Component cards contain configuration facts only; unmeasured latency is not displayed.
- Top-level Advanced contains only the Bot-level LLM timeout Fallback script; Evaluation, speaking order and prompt generation are deferred.
- ASR is currently Deepgram Flux only. English/Automatic come from the backend catalog; Automatic supports optional hints for ten languages.
- Flux ASR settings are Bot-scoped. Eager EOT, Nova endpointing, smart detection and noise suppression are absent. WebCall input is fixed at mono PCM 16 kHz.
- LLM Thinking uses Provider default/Off/Minimal explicit overrides because Model is free-form. LLM Advanced also includes Max response tokens and Request timeout; Bot Advanced stores the timeout Fallback script. LLM diagnostic tests unsaved configuration and reports measured TTFT.
- TTS basic fields end at Initial speed. Advanced orders Text aggregation, conversational speed control and provider-specific tuning.
- ElevenLabs voice discovery requires its Key and supports Custom voice ID. Deepgram Flux catalog browsing does not require a Key and has no Custom voice ID.
- Voice libraries support search and metadata filters; initial avatars are derived from names.
- Chat test is text → LLM → TTS, supports Start/End and barge-in. Web call adds ASR and live captions.
- Each Agent reply owns the immediately adjacent Turn metric card. Chat omits ASR final; Web call includes it.
- Sessions is a filterable list. View opens a collapsible right detail drawer with user-uplink recording, transcript and inline metrics.
- `Simulate caller turn` and every displayed prototype latency are demonstrators only and MUST NOT ship.

## Traceability

| Prototype area | Delta requirement / scenario |
|---|---|
| `login.html` identity and form | `bot-config` / Product-owned login experience |
| Login error/expiry presentation | `bot-config` / Invalid credentials; Website login expires |
| Product rail, tabs and Bot settings | `bot-config` / Componentized Bot editor |
| ASR card and drawer | `bot-config` / ASR catalog, WebCall format, Bot-scoped Flux settings |
| LLM card, Thinking and diagnostic | `bot-config` / LLM Thinking override and connection diagnostic |
| TTS provider states and Voice Library | `bot-config` / Provider-dependent TTS configuration |
| Conversational speed controls | `bot-config` / Conversational speed-control configuration; `voice-pipeline` / runtime speed requirements |
| Chat test | `call-history` / Run and interrupt a Chat test |
| Web call captions and Turn metrics | `call-history` / Run a Web call test |
| Sessions list and View drawer | `call-history` / Sessions list and detail drawer |
| Historical user recording | `call-history` / Play retained user audio |

Behavior and data rules follow Delta Specs. Visual structure and interaction details follow this prototype after final product approval.
