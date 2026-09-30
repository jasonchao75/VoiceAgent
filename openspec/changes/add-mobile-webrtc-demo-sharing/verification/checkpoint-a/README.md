# Engineering Checkpoint A Evidence

Date: 2026-09-29

## Result

- Production admin DOM: `/?share_fixture=1`, using the same Share section that later loads `/api/bots/{bot_id}/share`.
- Production mobile component: `/demo/{public_id}`; deterministic states use `demo.html?fixture=<state>` without a second static UI shell.
- Frontend build: PASS.
- Playwright fixture matrix: 22 PASS across desktop/narrow projects.
- Mobile widths: 320, 375, 390 and 430 px; document, phone shell and transcript drawer have no horizontal overflow.
- Transcript: four visible recent turns (two Agent, two You), fade hierarchy, 36 px transcript action and full scrollable drawer.
- QR: the production `qr` package encodes the exact public URL; the generated matrix decodes back to that URL, SVG renders and PNG download produces a non-empty browser download.

## Actual screenshots

- `admin-share.desktop-chromium.png`
- `admin-share.narrow-chromium.png`
- `mobile-live.desktop-chromium.png`
- `mobile-transcript.desktop-chromium.png`
- `mobile-reconnecting.desktop-chromium.png`

## Baseline comparison

- Preserved: page hierarchy, green-on-dark visual system, public profile, QR/Web Link split, four-turn faded captions, transcript drawer, call controls and reconnecting state.
- Intentional production-only differences: real Bot fixture name and locally generated URL/QR replace prototype sample values; prototype state switcher and review notes are absent.
- Frozen Gate 1 prototype files and hashes were not modified.

## Deferred to Checkpoint B/C

- Real publication API, persisted enable/disable state and published snapshot.
- Browser Small WebRTC data-message/audio exchange and real microphone permission.
- Camera scan on a physical phone and DigitalOcean ICE reachability.
