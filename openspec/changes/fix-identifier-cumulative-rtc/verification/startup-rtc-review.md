# Startup RTC independent review — 2026-10-27

## Current result: PASS (final scoped recheck including active-offer cleanup)

Scope: current uncommitted startup sequencing, RTP silence/order handling, first-error preservation, safe diagnostics. Reviewer did not modify production code, invoke providers or deploy. This is not User Gate 2 or proof of a unique cause for the user's earlier production call.

## Findings

1. **Pre-offer playback failure capacity (P1):** `prepareRTCPlayback` worker can fail before an offer is activated. Its callback labels `end_reason=provider`, while the previous pending cancellation API accepted only `connection`. First-error dedup removes the later generic error that could previously mask this; all authenticated signaling failures must attempt atomic pending cancellation. Fixed: all authenticated signaling failures now try atomic pending cancellation; provider/connection variants both pass four-attempt capacity regression, with exact reason in persisted td_events and safe logs.
2. **Control channel never opens (P1):** `MappedRawAudioTrack.recv()` now waits for `ready` indefinitely. Pinned Pipecat `_start_data_channel_timeout()` only discards queued controls; it does not close the connection. An ICE-success/SCTP-never-open call can remain connecting and occupy active/provider resources until the session maximum. Fixed: ready wait imports the pinned SDK 10-second limit; expiry raises MediaStreamError and schedules an owned disconnect task outside the sender stack. Independent regression verifies timeout, peer closed, no source samples, and no self-await deadlock.
3. **Evidence precision:** Playwright's Desktop Chrome device overrides navigator.userAgent (diagnostics show Chrome153 even when a Chrome138 executable is selected). Fixed evidence now saves actual `browser.version()`; combined and first-error files report 138.0.7204.183. Keep the initial dropped-task packet experiment distinct from the explicit null-task silence evidence. Earlier production diagnostics cannot establish which exact playback reason fired.

## Independent tests executed

- `/tmp/voiceagent-r91-py311/bin/python -m pytest tests/test_td_rtp_integration.py tests/test_td_rtp_mapping.py tests/test_td_rtp_writer.py tests/test_publication.py -q`: **25 passed**.
- `node --test frontend/tests/unit/td-rtp-decode-job.test.js frontend/tests/unit/td-rtc-entry.test.js`: **17 passed**.
- `python3 scripts/quality/verify_change.py fix-identifier-cumulative-rtc`: **0 errors**, open defect/unverified/task warnings remain.

## Evidence inspected

- `/tmp/voiceagent-connect-sctp-before`: actual local RTP, 51 packets / 0 mappings, `mapping_deadline`.
- `/tmp/voiceagent-connect-silence-fixed`: no mapping failure, 420 decoded packets, three explicitly skipped silent ranges, no fabricated PCM for those ranges.
- `/tmp/voiceagent-connect-combined-final`: actual engine 138.0.7204.183, no mapping failure, three silent skips. Six renderer receipts all HTTP204: two actual task finishes (5760 samples each) and a real stop at 282792 samples. Source/collection/clear assertions remain in the production-route test.
- `/tmp/voiceagent-connect-first-error`: one HTTP204 browser failure with playback_failed / packet_deadline, persisted history reason and released resources; error copy is not overwritten by generic connect text. This injected failure is at stage=live; exact signaling phase is separately covered below.

## Limits

Local browser audio uses deterministic offline provider replacements and synthetic PCM. No physical Android, Honor Chrome97, Safari, AEC, real mobile-network or paid-provider validation. The review checks the named patch, not universal browser compatibility or final product acceptance.

## Review disposition
No remaining blocking source defect found in this patch after recheck. The result covers named local fixes and their preserved strict task identity behavior. Reproducible local defects are established; the prior production call’s exact hidden failure remains unknown. Do not mark physical-device compatibility or user acceptance complete. Open delivery-status issues should be reconciled to fixes and retained unverified scope before deployment.

## Additional review — active offer cancellation
The exact signaling replay exposed an active lease leak after offer claim. Rechecked fix: capability and session must match; cancel_session revokes the active lease under the registration lock, discards an existing binding, and a late registration rechecks the lease before starting its pipeline. Wrong token/session cannot cancel another call. If cancellation happens before capture starts, the API finishes only a still-unended history record as failed/not_started with safe reason and removes its event buffer. Existing server exception categories are not overwritten by less-specific browser errors.

Final independent command: `/tmp/voiceagent-r91-py311/bin/python -m pytest tests/test_webrtc.py tests/test_publication.py tests/test_td_rtp_integration.py -q`: **29 passed**. This includes before/after registration races, wrong credentials, no late pipeline, no-capture history finalization, and bounded control timeout cleanup.

Additional inspected evidence:
- `/tmp/voiceagent-connect-signaling-final/first-playback-failure.json`: exactly one HTTP204, stage=signaling, provider/decoder_unavailable, persisted failed history. Real engine version retained separately.
- `/tmp/voiceagent-connect-control-timeout-final/control-timeout.json`: fixed timeout path; active and pending slots return to zero and error screen becomes active. Decoder events also show a subsequent SDK restart rejected by multiple_receiver_transform; this is not evidence of successful reconnect and no success is claimed.

No remaining blocking defect found in the final reviewed delta. Gate reports zero errors; delivery-status open implementation items still need reconciliation by the implementing agent. Physical-device and original-production-cause limitations remain unchanged.
