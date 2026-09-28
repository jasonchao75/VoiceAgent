# UI Verification Checklist

- Change: `add-streaming-asr-providers`
- Gate: D-019/D-020 feedback revision complete and independently verified; User Gate 2 product acceptance pending
- Browser: bundled Playwright Chromium (headless)
- Viewports: 1440×1000 and explicit 390×844; scale 1
- Fixture revision: PRD V1.0.17
- Baseline approval: Product owner / 2026-09-28 / D-014 + D-015 + D-019/D-020 amendments
- Sole active prototype SHA-256: `b6835ca7da9f0ee120081bb682a319f60be296029800c6b83e28a111b400b277`

## Engineering results

| Checkpoint | Result | Evidence |
|---|---|---|
| A — production DOM + fixture | PASS | `frontend/tests/ui/voice-bot.spec.js`; the formal `/` route uses the production drawer and deterministic Bot/history fixtures |
| B — API + persistence | PASS | Bot/API/session tests cover Provider-aware Bot credentials, legacy migration, refresh round-trip, lease secrets and safe failures |
| C — functional/accessibility/visual | PASS (local scope) | 18/18 Voice Bot Playwright cases pass against an isolated current-worktree service; desktop and 390px screenshots are stored beside this file; keyboard focus, labels and drawer overflow checks pass |

## State matrix

| Scenario | Desktop | 390px | Contract result | External-real status |
|---|---|---|---|---|
| Deepgram Flux / Nova-3 switch | PASS | PASS | Flux V2 and Nova-3 V1 fields remain isolated; Nova-3 is Off with positive endpointing | Nova-3 external-real PASS |
| Speechmatics language/domain/Advanced | PASS | PASS | Language Pack controls, domain filtering, compact refresh action, Fixed Off, sentence segmentation and punctuation states match V1.0.17 | External-real PASS |
| Soniox searchable language hints | PASS | PASS | `code (English name)` labels, code/name search, Catalog selection, add/remove and clear-to-Automatic pass | External-real PASS |
| AssemblyAI presets/context options | PASS | PASS | 18 unique `code (English name)` choices; Mode resets three values; edits show modified state; Voice Focus dependency enforced | External-real Context + Turn PASS |
| Bot-scoped credentials | PASS | PASS | Key follows Advanced; blank keeps this Bot's key; provider/component isolation is covered by API tests | All four Provider authentications PASS |
| Drawer/modal overflow | PASS | PASS | `scrollWidth <= clientWidth` for affected overlays | No open local issue |
| Keyboard/accessibility | PASS | PASS | Interactive controls have accessible names; overlay focus is contained and Escape closes | No open local issue |

## Evidence files

- `actual-gate-2-{deepgram-nova,speechmatics,soniox,assemblyai}.{desktop-chromium,narrow-chromium}.png`
- `gate3.{llm,voice-picker,sessions,advanced}.{desktop-chromium,narrow-chromium}.png`

The 2026-09-28 repository-wide UI probe stopped after four failures in unrelated Auth/Evaluation suites. The first targeted Voice Bot run also connected to a stale port-8000 process whose in-memory Catalog predated Advanced fields. The same 18 scoped cases passed against the current-worktree service on port 8011; the required 390px check is applied inside this Change's provider-state case. Port 8011 remains available for product review.
