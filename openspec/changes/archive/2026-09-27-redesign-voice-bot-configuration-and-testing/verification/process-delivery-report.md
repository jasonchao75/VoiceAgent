# UI Delivery Process Report

## New versus old

| Topic | Previous | New | Change type |
|---|---|---|---|
| Requirements | Long specs reviewed ad hoc | One-page area review backed by Delta Specs | Simplified product review |
| Prototype annotation | Visual intent implicit in HTML | Viewport, tokens, strict/adaptive regions documented | Added and moved earlier |
| Development timing | Implementation could begin before a measurable baseline | Gate 1 freezes the approved prototype before implementation | Development gate added |
| State coverage | Happy path and reviewer-discovered gaps | Stable state matrix covers data, interaction and errors | Added |
| Visual checks | Manual spot checks near completion | Gate 2 requires baseline/actual/diff per scenario | Moved earlier; automation designed, not implemented |
| Acceptance | Product finds layout and behavior defects together | Gate 1 scope, Gate 2 engineering comparison, Gate 3 final product acceptance | Staged |
| Evidence | Screenshots without baseline status | Change-local baseline/actual/diff/checklist and known differences | Added |
| Reuse | Change-specific habits | Repository rules, guide and templates selected by risk | Added |

## Why and trade-offs

The frozen prototype and Gate 2 comparison expose wrong controls, missing fields and ownership leaks before business wiring, reducing late concentrated rework. Stable scenario IDs and paired evidence make regressions and root causes easier to locate. The cost is maintaining annotations, fixtures and baselines and running more checks; low-risk copy-only changes may use a targeted screenshot, while high-risk page redesigns use the full matrix. Pixel comparison does not replace functional or accessibility testing.

## Required product participation

| Stage | Previous approximate effort | New approximate effort | Product decision |
|---|---:|---:|---|
| Requirements/prototype | Repeated ad-hoc reviews | One structured review, about 15–30 minutes | Confirm prototype and strict/adaptive boundaries |
| Static shell | Often mixed into final review | One direction checkpoint, about 5–15 minutes | Confirm overall visual direction only when engineering evidence is ready |
| Final acceptance | One large review plus rework loops | One focused acceptance, about 15–30 minutes | Accept behavior and disclosed differences |

Product does not capture screenshots, inspect pixels, traverse every state or assemble evidence. This Change's prototype was confirmed on 2026-09-08, so Gate 1 is complete; current implementation drift belongs to Gate 2.

## Delivery status

### Implemented

- Current Change: updated `proposal.md`, Delta Spec, `design.md`, `tasks.md`, prototype annotations, state matrix and verification checklist.
- Current-specific review/evidence structure: `verification/gate-1-review.md`, `visual-diffs.md`, and baseline/actual/diff directories.
- Repository reuse: root `AGENTS.md`, `docs/engineering/ui-prototype-delivery.md`, four UI delivery templates and deterministic fixture `tests/ui/fixtures/voice-bot-editor.json`.
- API Key contract: component Key fields are editable by default; persistence only controls encrypted storage; component credentials remain isolated.

### Designed only

- Playwright fixed-viewport capture, baseline checksum enforcement, diff generation and threshold calculation.
- Proposed initial thresholds: 0.1% component crop and 0.3% full page, subject to calibration from the first comparison.
- Optional CI visual job. CI changes require separate approval.

### Not yet verified

- Gate 2 engineering self-check is complete at 1275 × 1114; product visual-direction confirmation is still pending.
- Manual actual screenshots exist for ASR, LLM, both TTS dependency states, voice selection, Chat, WebCall and Sessions empty state. Automated baseline and diff images have not been generated.
- Active audio/LLM sessions, inline Turn metrics, barge-in, populated Session drawer/recording and the narrow viewport remain unverified.
- No Playwright dependency, screenshot command or CI workflow has been added.

## Run and evidence locations

- Current available validation: `openspec validate redesign-voice-bot-configuration-and-testing --strict` and JSON parsing of `tests/ui/fixtures/voice-bot-editor.json`.
- Prototype: `prototypes/index.html`.
- Future screenshot evidence must remain under `verification/baseline/`, `verification/actual/` and `verification/diff/`; tests must never update baselines silently.
