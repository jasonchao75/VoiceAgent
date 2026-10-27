# Pending release independent review

Status: PASS (D-002 local pending-release repair scope, 2026-10-27)

Scope: D-002 pending session cancellation and bounded pre-connect error reporting. No provider calls, production operations or implementation edits by reviewer.

## Finding and repair

- `failCall()` now awaits `reportSessionEvent()` before `releaseClient()` for **all** failure paths. A hung telemetry fetch therefore delays audio/worker/microphone cleanup for its full 3-second deadline, including an already live call. The current main voice-pipeline spec says failure telemetry cannot block media cleanup. Start error reporting and media cleanup independently, preserving the captured session credential for the report; the UI may await the bounded report after cleanup if needed. Verify a stalled events request does not keep media resources running.

The parent repaired this by starting the report promise, releasing the client, then awaiting only the UI transition. Independent VM execution of the actual current `failCall` function confirms `cleanup` happens while reporting remains unresolved, and `error-ui` appears after the report resolves. The original blocker is resolved.

## Evidence

- Independent `tests/test_session.py tests/test_publication.py`: 19 passed.
- Independent Node `frontend/tests/unit/td-rtc-entry.test.js`: 8 passed.
- Independent RTC backend regression (`test_webrtc`, `test_webrtc_deploy`, `test_td_webrtc_cancel`): 16 passed.
- Direct imported `prepareRTCPlayback`: separate missing ScriptTransform and missing AudioDecoder cases both throw `playback_unsupported` before allocating AudioContext.
- Independent current-function VM probe: with stalled reporting, media cleanup occurs first; error UI waits for bounded reporting.
- Static: cancel_pending and claim share the same lock; mismatched session/token cannot cancel another pending call; active sessions are not removed by this new method; credentials are cleared before the slot is reused.
- Gate: 0 errors, 5 warnings (existing compatibility/production issues and incomplete tasks).

## Limits

This repair does not implement the old encoded-stream API or support the user’s Chrome-97-identifying Honor browser. No physical phone or paid providers tested. The reported compatibility defect must remain disclosed; a passing cancellation test is not a successful call.

The PASS is restricted to pending-release/authentication/error-category/local cleanup behavior. Formal browser-path evidence from the parent can supplement this report; this reviewer has not claimed to run a real Honor browser or production session.

## Pre-peer microphone follow-up

The parent’s real-browser test discovered the locked SmallWebRTC SDK `stop()` returns immediately when `pc` is absent, before `mediaManager.disconnect()`. Thus `initDevices()` can leave acquired microphone tracks live after a capability failure. Static inspection independently confirms that early-return order.

The parent added pre-peer-only media-manager cleanup to `releaseClient()`. Independent execution of the current actual function verifies: (1) no peer calls media-manager disconnect, (2) an existing peer retains the SDK cleanup path without a duplicate media-manager call, (3) a thrown task-player close still proceeds through remote-audio cleanup, SDK disconnect and pre-peer device cleanup, and (4) client/transport references and audio srcObject are cleared. No blocker found in this focused follow-up.

The parent is rerunning `td-rtc-preconnect.spec.js`, which holds the real error-response request and requires every actual fake-microphone track to reach `ended` within 1500ms, before permitting that response to complete. The parent reports that browser test now passes; this reviewer’s direct evidence above remains VM/static, not physical microphone evidence.

## Final D-002 conclusion

**PASS: pending-slot cancellation, authenticated cleanup, error recording and compatibility investigation only.** The old Honor browser remains unsupported by the current task player; this conclusion does not claim playback compatibility has been repaired.

Final evidence provided by the parent (not misrepresented as independently executed here): full pytest **793 passed / 9 skipped**, Node **28 passed**, `td-rtc-preconnect.spec.js` **1 passed**. The preconnect scenario disables ScriptTransform, runs four real local API allocations and failures with 204 error responses, verifies failed histories and zero pending sessions, and confirms fake microphone tracks end before a held error HTTP response is released. The normal `td-rtc-identifier-entry.spec.js` regression also passes once.

The reviewer independently inspected the normal RTC evidence in `/tmp/voiceagent-preconnect-normal-rtc`: completed history, two prepared echo tasks, six renderer receipt HTTP responses all 204, including an actual task-stopped receipt. Final gate: **0 errors / 2 warnings**; remaining warnings correctly retain old-browser incompatibility and real-device/vendor validation limits. No physical microphone, paid model call, deployment, or new transport architecture was performed by this reviewer.
