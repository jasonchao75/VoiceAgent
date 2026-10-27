# Legacy RTP compatibility independent review

- Date: 2026-10-27
- Reviewer: independent Codex subagent `/root/legacy_rtc_review`
- Result: **PASS — scoped compatibility patch**, not full Change or device acceptance.
- Scope: uncommitted changes to `td-rtc-entry.js`, `td-rtp-candidate-worker.js`, `td-rtp-input-worker.js` and associated tests, under D-003.

## Findings

No blocking implementation defect found in this patch. The initial audio transceiver is bound before SDP; legacy readable/writable streams transfer to the same receiver worker used by ScriptTransform. Both entry points execute the same packet-order, SHA-256 payload identity, source extent and decode checks. Neither path replaces RTP/Opus with data-channel audio or enables native playback as a silent fallback.

The optional sender observer uses its separate worker. Missing capture metadata remains explicitly unavailable; it does not synthesize capture time or alter the audio frames. Receiver failure remains fatal to task playback. API selection prefers the modern transform, then the legacy receiver API, while retaining AudioDecoder as a prerequisite.

Native audio remains muted while the task renderer produces authenticated start/stop/finish receipts. The patch does not weaken receipt ordering, HTTP failure handling, or decode-output ownership checks.

## Independent checks

- Read the Change proposal, design, Delta Spec, D-001 through D-003, assumptions and open questions; no open product question.
- `node --test frontend/tests/unit/td-rtc-entry.test.js frontend/tests/unit/td-rtp-input-tap.test.js`: **14 passed**.
- `node --test frontend/tests/unit/td-playback-receipts.test.js frontend/tests/unit/td-rtp-decode-job.test.js frontend/tests/unit/td-rtp-capture.test.js`: **8 passed**.
- `python3 scripts/quality/verify_change.py fix-identifier-cumulative-rtc`: **PASS, 0 errors, 3 warnings** at review time. Warnings include the existing device/external-service exclusions, a stale compatibility issue description and two pending completion tasks. The implementing agent was asked to update the stale issue description.

## Browser evidence inspected

The implementing agent ran the formal application RTC identifier test on actual Google Chrome for Testing 138.0.7204.183, with no real provider calls. Evidence: `/tmp/voiceagent-chrome138-rtc-evidence/`.

Independent inspection of the saved evidence found 424 packet-bound and 424 decoded events; task start, finish and stop receipts all received HTTP 204. The stopped echo rendered 283400 samples. Sender capture reported `capture_time_unavailable`, preserving missing evidence instead of inventing it. The actual application test checks clear arbitration, suppression of the queued echo, muted native audio and final renderer sample counts.

These are **local-real RTC/decoder/renderer** results with **offline provider replacements**. The browser run was executed by the implementing agent; this reviewer inspected its saved output rather than claiming to have rerun the browser. At review time, its diagnostics JSON did not yet include browser-version/API fields; the implementing agent was asked to retain the separate version/API probe evidence. Modern forced-legacy and modern-native regression runs were also reported by the implementing agent, not independently repeated here.

## Limits

This review does not prove Android hardware, Honor Chrome 97, Safari, physical speaker/microphone, AEC, background transitions, weak networks or real paid provider behavior. Chrome 138 desktop is evidence for the old encoded-stream interface, not a substitute for phone acceptance. No deployment, paid call, dependency addition or production-data mutation was performed by this reviewer. No prototype or user acceptance baseline was changed.
