# UI Verification Checklist

- Change: `add-mobile-webrtc-demo-sharing`
- Gate: User Gate 1 approved 2026-09-29; Engineering A/B and C local evidence complete; production deployment/preflight and 390×844 unavailable-state accessibility check pass; Provider key re-entry and external-real call matrix pending
- Browsers: Chromium fixture; iOS Safari/Android Chrome external-real pending
- Viewports: Admin 1440×1000, 1024×1000, 390×844; Mobile 320×700, 375×812, 390×844, 430×932
- Fixture revision: production-route fixtures in `frontend/tests/ui/`; 24 mobile desktop/narrow checks passed after accessibility-state repair, plus the previously completed Share/API matrix
- Baseline approval: D-010; frozen SHA pair recorded in `prototypes/README.md`

| Scenario | Baseline | Actual | Diff | Ratio | Functional | Accessibility | Known deviation | Decision |
|---|---|---|---|---:|---|---|---|---|
| Admin Share active | frozen | `checkpoint-a/admin-share.*`; `checkpoint-b/real-admin.*` | amplified diff | 9.09% | pass | pass | real title/URL replace sample | local pass |
| Admin Share unpublished changes | frozen | production DOM + API tests | qualitative reviewed | pending numeric | pass | pass | none | local pass |
| Admin Share disabled | candidate | production DOM + API tests | qualitative reviewed | pending numeric | pass | pass | none | local pass |
| Admin Share unpublished | candidate | production DOM + API tests | qualitative reviewed | pending numeric | pass | pass | no QR until publish | local pass |
| Mobile Ready | candidate | `checkpoint-b/real-mobile.*` | qualitative reviewed | pending numeric | pass | pass | public copy source resolved | local pass |
| Mobile Connecting/Live | candidate | `checkpoint-a/mobile-live.*` | amplified diff | 6.54% | fixture pass | pass | external-real WebRTC pending | pending external |
| Mobile weak/error/end | candidate | `checkpoint-a/mobile-reconnecting.*` + state/renegotiation tests | amplified reconnecting diff | 10.58% | local recovery pass | pass | no TURN; external ICE pending | pending external |
| Transcript drawer | candidate | `checkpoint-a/mobile-transcript.*` | amplified diff | 14.70% | pass | pass | production copy/height differ | local pass |
| Narrow overflow | candidate | desktop/narrow screenshots + 320/375/390/430 checks | qualitative reviewed | pending numeric | pass | pass | none | local pass |
