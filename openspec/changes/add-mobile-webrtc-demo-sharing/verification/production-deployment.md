# Production Deployment Evidence

## Deployment identity

- Date: 2026-09-30
- Evidence level: `external-real` for deployment/runtime configuration; no paid Provider call
- Deployment baseline commit: `7166ad9eabd7ab4f2053560374d4d1dc6c1f64ba`
- Accessibility repair commit: `43ee1d03bb1a636c38000d2b774b99ab594aafd5`
- Latest CI run: `36705082129` — PASS
- Latest CD run: `36705391988` — PASS
- Public origin: `https://platform.voiceagentdemo.org`

## Verified runtime facts

- Container `voiceagent-platform-voice-agent-1` is healthy and uses Docker `host` networking.
- In-container WebRTC preflight reports one configured STUN server and Linux UDP range `32768–60999`.
- UFW allows `32768–60999/udp` for IPv4 and IPv6.
- Local container health and public HTTPS `/health` both return `status=ok` with zero pending/active sessions.
- The two existing Bot records remain present; publication/credential/link tables exist.
- Evaluation verification preserves 8 batches, 12 reports, 29 reviews and 153 benchmarks.
- The unauthenticated product root redirects to the product login page; a mobile demo route serves over HTTPS; missing public metadata returns 404; the admin Bot API returns 401 without a Basic-auth challenge.
- Local desktop/narrow browser regression confirms inactive mobile screens are `aria-hidden` and inert, while the active call retains a semantic page title; 24 mobile UI checks pass.
- A post-deployment 390×844 production-browser check confirms no horizontal overflow and an accessibility tree containing only `Demo unavailable`, its safe message and `Try again`; all four inactive screens report `aria-hidden=true` and `inert=true`.

## Data-safety evidence

- D-015 backup: `/home/deploy/apps/voiceagent-platform/backups/evaluation-before-provenance-d015-20260930.db`
- Backup SHA-256: `168a355e8b129eaf5d44f1065fa88e53ffe1bb75e9a6e6fa2197b7c20a51eadb`
- Source and backup SQLite integrity checks: `ok`
- Result-table counts were unchanged before and after the metadata-only transaction.

## Evidence boundary

- DigitalOcean Cloud Firewall rules cannot be proven from the host and still require control-plane confirmation or a real ICE path.
- No published Bot can start a Provider-backed call until the user re-enters the rotated ASR/TTS/LLM keys.
- Browser offer/PATCH/data-message, real audio, iOS Safari, Android Chrome, Wi-Fi/mobile-network reachability and connection-success measurements remain unverified.
- TURN is intentionally absent under D-005.
