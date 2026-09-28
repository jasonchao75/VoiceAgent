# Prototype Precision Annotations

Status: Gate 1 candidate; requires product confirmation

## Reference environment

| Property | Baseline |
|---|---|
| Desktop viewport | 1440 × 1000 CSS px |
| Narrow viewport | 1024 × 1000 CSS px |
| Mobile exploratory viewport | 390 × 844 CSS px; adaptive, not pixel-identical |
| Scale | deviceScaleFactor 1 |
| Theme | Dark |
| Locale / timezone | en-US / UTC |
| Font | Existing product system sans stack; browser font load must complete before capture |
| Motion | Disabled for screenshots |

## Fidelity rules

- **Strict:** information hierarchy, field order and ownership, control type, visibility, selected/expanded state, drawer behavior, component dimensions at baseline desktop, colors, typography hierarchy, spacing rhythm, borders and radius.
- **Adaptive:** line wrapping, drawer/main width at narrow breakpoints, stacked controls and scroll position, provided all content and relationships remain available.
- **Data-driven:** provider/model/language/voice values and availability may follow the capability catalog, but the component shape and empty/loading/error treatment remain strict.
- **Never copied from prototype:** sample latency values, simulation-only controls, fake keys and dates.

## Shared visual tokens

| Token | Value |
|---|---|
| Page background | `#0a0d0c` |
| Panel background | `#111514` |
| Elevated control | `#171c1a` |
| Border | `#29302d` |
| Primary text | `#edf2ef` |
| Muted text | `#8f9a95` |
| Accent | `#78f0b3` |
| Standard radius | 8–10 px |
| Field height | 36–38 px |
| Drawer width | 440 px at desktop |
| Section spacing | 14–18 px |
| Label | 11–12 px / 1.3 / 600 |
| Hint | 9–10 px / 1.4 |

## ASR drawer — strict example

Order: Provider → Model → Language + read-only Audio input → Advanced → Deepgram credential card → footer actions.

- Advanced is expanded in the baseline state.
- EOT threshold is a range slider with a visible numeric output; a number input is not equivalent.
- EOT timeout is a numeric field with unit/range hint.
- Keyterms is a multiline textarea with example phrases containing spaces.
- Profanity filter and Numerals are toggle switches. Redact is a single-select.
- Audio input is visible as read-only `PCM · 16 kHz`; it must not be omitted or presented as a selectable 8 kHz option.
- The credential card contains only the Deepgram Key in the ASR drawer. Saving controls persistence only; it must not reveal LLM or TTS credentials.

## Required component states

All interactive controls require default, hover, keyboard focus, disabled and validation-error annotations. Async regions additionally require loading, empty and request-error states. Long Bot/model/voice names, 100 Keyterms and narrow drawer wrapping must not overlap, clip required actions or change component ownership.

## Login page

- Strict product name: `VoiceAgent Demo`; no historical product name may appear in title, heading, navigation or metadata.
- Desktop composition: centered shell up to 960 px, identity region and 400 px login card; narrow viewport becomes a single column.
- Login inputs and action reuse the platform field height, border, focus ring, radius and accent tokens.
- Invalid credentials use a generic inline alert without revealing which value was wrong. Expired sessions use neutral explanatory copy rather than an error-colored failure.
- Password visibility control, submit loading/disabled state, keyboard focus order and Enter submission are required.
- Login and avatar menus must satisfy the global no-horizontal-overflow redline.
