# User Gate 1 Review — Streaming ASR Providers

Status: **PASS — confirmed by product owner on 2026-09-27 (D-014), with D-015 baseline amendment**

Frozen prototype SHA-256: `b6835ca7da9f0ee120081bb682a319f60be296029800c6b83e28a111b400b277` (D-019/D-020 User Gate 2 feedback amendment)

This gate freezes product behavior and the visual baseline before implementation. It is not final product acceptance.

## Review order

1. Review the PRD scope and exclusions.
2. Open `prototypes/index.html` and switch all four values in the Provider dropdown; under Deepgram also switch Flux/Nova-3; inspect each language control, Turn capability and Advanced group.
3. Review confirmed Context and Bot-scoped Provider credential semantics.
4. After overall confirmation, freeze one SHA-256 baseline.

## Product review board

| Area | Confirm | Status |
|---|---|---|
| Scope | Add Speechmatics, Soniox, AssemblyAI; keep Flux and add Deepgram Nova-3; no benchmark | Confirmed by D-001 and D-010 |
| Delivery sequence | PRD/prototype first; no implementation before Gate 1 | Confirmed by D-002 |
| Turn behavior | Off means VAD/fixed silence, not no boundary; Speechmatics uses Fixed + positive trigger; Nova-3 keeps positive endpointing; Soniox/AssemblyAI fixed Native | Confirmed by D-008/D-011/D-012 |
| AssemblyAI Context timing | LLM→TTS remains streaming; Context update never waits for TTS audio | Confirmed by D-004 |
| AssemblyAI Context content and cadence | Once per Agent Turn; use this Turn's Agent reply; no playback-prefix tracking | Confirmed by D-006 |
| ASR abstraction | Pipeline → ASR Service → Registry → Adapter | Confirmed by D-005 |
| Credentials | Bot-scoped component/provider keys; different Bots may use different accounts; existing drawer interaction | Amended by D-015 |
| Deepgram model split | Flux V2 and Nova-3 V1 use separate language, Turn and Advanced contracts | Confirmed by D-010 |
| AssemblyAI Mode tuning | Mode resets three official Turn preset values; users may modify the populated values; VAD threshold remains independent | Confirmed by D-013 |
| Visual baseline | Current ASR card/drawer hierarchy and provider/model-specific states, with Bot-scoped credentials | Confirmed by D-014 and amended by D-015 |

## Gate exit criteria

- No open product question remains; D-001～D-016 remain traceable.
- PRD, Delta Specs, design, tasks and prototype agree.
- `prototypes/README.md` contains one matching SHA-256, confirmation date and source.
- `python3 scripts/quality/verify_change.py add-streaming-asr-providers` has no structural/baseline error other than intentionally incomplete implementation tasks.
