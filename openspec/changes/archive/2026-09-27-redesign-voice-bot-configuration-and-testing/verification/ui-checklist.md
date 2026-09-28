# UI Verification Checklist

Status: Gate 1 approved on 2026-09-08; Gate 2 visual direction accepted on 2026-09-10; User Gate 2 accepted on 2026-09-27 with UV-001/UV-002 evidence boundaries

## Test contract

| Item | Value |
|---|---|
| Risk | High |
| Prototype | `prototypes/index.html`, `prototypes/login.html` |
| Annotations | `prototypes/ui-annotations.md` |
| State matrix | `prototypes/ui-state-matrix.md` |
| Fixture | `tests/ui/fixtures/voice-bot-editor.json` |
| Desktop viewport | 1440 × 1000, device scale 1 |
| Narrow viewport | 1024 × 1000, device scale 1 |
| Browser | Playwright Chromium 153.0.8010.12 (Playwright Chromium build 1243) |
| Locale/timezone/theme | en-US / UTC / dark |
| Motion | Disabled during capture |

## Gate 1 — specification and baseline

- [x] Product confirmed the five-area interactive prototype in `verification/gate-1-review.md`
- [x] The approved prototype is frozen as the implementation baseline
- [x] Delta Scenarios record visible controls and component ownership
- [x] State matrix and deterministic fixture define engineering coverage
- [x] Do not retroactively calibrate pixel thresholds; preserve this as accepted historical evidence boundary UV-002
- [x] Do not recreate current screenshots as an immutable historical baseline; preserve the approved HTML prototype and actual screenshots honestly under UV-002

## Gate 2 — static shell

- [x] Navigation, workspace widths and non-modal drawer geometry match baseline in the manual fixed-viewport pass
- [x] ASR field order includes read-only Audio input
- [x] ASR Advanced uses the exact control shapes: EOT slider, timeout input, Keyterms textarea, two toggles and Redact single-select
- [x] Each component drawer shows only its own credential card; persistence control never reveals another component's Key
- [x] LLM Advanced and TTS hierarchy match their annotated baselines
- [x] Desktop and narrow actual screenshots are recorded in `visual-diffs.md`
- [x] Product confirms overall layout and visual direction

## Gate 3 — behavior and states

- [x] Product-owned login, invalid/expired messages, secure Cookie, logout and return path pass
- [x] Chat/Web call Bearer metrics remain separate and never return a browser Basic Auth challenge
- [x] Login and avatar/logout controls use `VoiceAgent Demo`; historical platform names are absent from user-facing frontend
- [x] Catalog success/failure and disabled unsafe-action states pass functional checks
- [x] Automatic language/hints and credential editability states pass
- [x] LLM diagnostic succeeds with real TTFT; error contracts remain covered by backend tests
- [x] TTS provider switching, Key gating, voice picker filtering fixture and unsupported states pass
- [x] Chat lifecycle, captions and inline metrics pass; live-microphone WebCall acoustic barge-in remains explicitly excluded as UV-001 under D-001
- [x] Sessions list/detail/drawer-close and historical recording states pass; unavailable states remain backend-tested
- [x] Long voice content, keyboard focus, disabled controls, overlay overflow and narrow layout pass
- [x] Every retained scenario has an evidence disposition; missing immutable baseline/diff ratios are recorded as UV-002 rather than fabricated
- [x] API, pipeline, browser functional and accessibility evidence remain distinct from screenshots
- [x] Product gave final acceptance on 2026-09-27 under D-001

## Known differences requiring correction

| Area | Observed difference | Evidence | Status |
|---|---|---|---|
| ASR basic | Read-only Audio input was missing | User review, 2026-09-08 | Fixed; manual screenshot captured |
| ASR Advanced | Layout and control presentation differed from approved prototype | User review, 2026-09-08 | Fixed; manual screenshot captured |
| ASR credentials | Saving revealed cross-component LLM Key; card differed from prototype | User review, 2026-09-08 | Fixed; component-isolated editable card captured |
| Test pages | Formal UI retained the old Conversation shell | Agent self-check, 2026-09-08 | Fixed; Chat/WebCall shells captured |
| Voice picker | Three-column cards truncated voice metadata | Agent self-check, 2026-09-08 | Fixed; readable row list captured |
| Voice picker | Horizontal scrollbar appeared with a populated ElevenLabs catalog | User review, 2026-09-10 | Fixed; desktop and narrow Playwright overflow assertions pass |
| Production login | Chat metrics Bearer request triggered a second native Basic Auth dialog | User screenshot and code diagnosis, 2026-09-10 | Fixed locally; metrics bypass website Cookie middleware and returns no Basic challenge |
| Product identity | Historical platform naming and architecture-specific login copy would limit future pipelines | Product review, 2026-09-10 | Fixed; login and application identity use `VoiceAgent Demo`, pipeline-specific lead removed |

## Automated and BYOK results — 2026-09-10

- Playwright application suite: 14/14 passed at 1440 × 1000 and 1024 × 1000; login suite adds 4/4 passed desktop/narrow checks.
- Backend suite: 91/91 passed; Ruff, Mypy, build, safety checks and strict OpenSpec validation passed.
- Product login: sign-in, generic failure, expiry presentation, secure Cookie, immediate logout, safe local return path and no horizontal overflow covered.
- Gemini diagnostic: connected, measured TTFT 1019.5 ms; no Key value logged or captured.
- Deepgram Flux Chat: opening playback and reply succeeded; Turn 1 E2E 2241 ms with all five Chat components displayed.
- ElevenLabs Chat: opening playback and reply succeeded; Turn 1 E2E 1541.6 ms with all five Chat components displayed.
- Web call live microphone path is not executable on this host; production historical recordings and backend contracts were checked instead.

## Evidence record

For every accepted scenario record: prototype screenshot, actual screenshot, diff image, pixel ratio, viewport, browser/version, fixture revision, masks, known deviations, reviewer and decision. Existing files in `verification/screenshots/` are retained as historical implementation evidence and are not approved baselines.
