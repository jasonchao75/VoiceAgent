# Visual Diff Evidence

Captured: 2026-09-30, headless Chromium, dark color scheme, reduced motion.

Method: compare same-size RGB screenshots. `changed pixel ratio` counts pixels where at least one channel differs by more than 24/255; `mean absolute delta` is the average channel difference divided by 255. Amplified difference images use 4× contrast for review and are evidence only, not a replacement baseline.

| Scenario | Viewport | Changed pixel ratio | Mean absolute delta | Known deviation |
|---|---:|---:|---:|---|
| Admin Share active | 1440×1000 | 9.09% | 5.01% | Real fixture name/link/QR and production spacing replace prototype samples; review dock excluded |
| Mobile live | 390×760 | 6.54% | 2.39% | Production captions use real component labels and omit concept-only phone chrome |
| Mobile transcript | 390×760 | 14.70% | 4.76% | Production drawer copy/height and actual caption card differ while hierarchy and vertical-only scrolling remain |
| Mobile reconnecting | 390×844 | 10.58% | 3.05% | Production warning placement/copy differs while reconnecting state remains equivalent |

Amplified evidence:

- `admin-share.active.1440x1000.diff.png`
- `mobile-live.390x760.diff.png`
- `mobile-transcript.390x760.diff.png`
- `mobile-reconnecting.390x844.diff.png`
