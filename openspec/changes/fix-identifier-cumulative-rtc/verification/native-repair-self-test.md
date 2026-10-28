# Native/incremental repair self-test — 2026-10-28

## Scope and evidence
Approved plan: repair-plan.md; D-20261028-NATIVE-PLAYBACK, FINAL-CONTENT-RESTART, IMPLEMENT-REPAIR. This report does not assert product acceptance.

- fixture: historical ASR sequence1234→12345→123453→format Final reproduced whole-source replay in legacy planner; new planner sends123453 once. Source is the documented935dbcf8 transcript sequence, not a new ASR run or corrected reference transcript.
- fixture: slow first cached-file read, append during first unit send, source formatting, true correction, pre-preparation cancellation/resume, queued cancellation/resume, active echo continuation despite new WPM ineligibility, suspended native writer cancellation before next task, Final equivalent/changed responses and tool once-only state.
- local-real: exact private15s16kHz mono PCM recording replayed completely through bundled Silero (240000 samples); SHA256891e6026f044c5e96e98b73cce37ff2dc05a10fb84770c31d6a411e38bcdf258. Full clip is not committed. Transitions and hash in /tmp/voiceagent-native-recording-replay.json. This is not ASR accuracy verification or a manually verified reference.
- local-real: formal default public RTC identifier route, website login enabled, anonymous browser, no AudioDecoder/ScriptTransform/encoded streams; native audio peak≈0.132, clear tool succeeds, server send cancellation, no task receipt/mapping requests. Desktop and narrow Chromium both pass; /tmp/voiceagent-native-identifier-browser3.log, /tmp/voiceagent-native-browser-final/.
- local-real: final-code PC microphone WebSocket path plus ordinary native RTC; real audio tone switching and hangup cleanup:2 passed, /tmp/voiceagent-native-pc-rtc-final.log. No provider request; SDK path/normalizers/scopes/transport remain production code.
- persistence: format-only Final updates effective history text and source_final, keeps submitted_text audit and same response ID; reopened SQLite store confirms one user row. Mixed identifier Final confirms existing successful contribution without replaying business tool.

## Checks
- Final backend full suite:830 passed,9 skipped,6 existing dependency deprecation warnings; /tmp/voiceagent-native-backend-release.log.
- Final targeted mixed/history/planner group:26 passed; independent reviewer also ran46 targeted tests.
- Ruff check/format pass, mypy local Python3.13 pass; default3.11 parsing blocked by locally installed numpy3.13 stubs. GitHub CI Python3.11 remains required.
- Frontend51 unit tests passed; production build passed.
- Independent final47 targeted tests PASS; final review PASS (local engineering scope), gate0errors/15warnings. No baseline/screenshot overwrite, credentials, recordings or databases committed.

## Initial failures and corrections
First full run had7 old-policy test failures, all updated to approved Final/native contracts and rechecked. First browser launch was blocked by local process permissions; rerun with local-server permission. Authenticated browser harness initially failed401 because Secure cookie was not forwarded on HTTP loopback; dedicated authenticated manager context fixed it. Next harness waited for history events during active call; history is persisted at hangup, so the final test hangs up before querying. These were test setup failures, not proven production native playback failures. Independent review found asynchronous unit ordering, cancelled-unsent restoration, active echo eligibility, history effective Final and mixed-success proof issues; all were addressed with regression tests before deployment.

## Pre-generated assets
Publication calls EchoAudioCache.manifest: validation only, no synthesis; required unit assets must be readable, hash/rate/config fingerprint/version valid and frozen in publication snapshot. Existing tests/test_echo_api.py covers missing assets, stale config and publication race. This change adds no paid runtime permission; cache-fault recovery remains the existing separately recorded exception, not a way to bypass publication. All this run's cache/ASR/Jev/LLM/TTS replacements are offline.

## Limits and retest
No paid external calls, no customer audio uploaded. Actual ASR accuracy, current Android/iOS hardware/AEC/Bluetooth/carrier network, acoustic tail duration and300ms end-to-end target are unverified. Historical candidate packet loss causes remain unknown; default production native route removes those mapping/decoder/receipt dependencies without claiming old root causes fixed. User accepted native tail/unknown listening progress and authorized deployment after self-test/review. Final user retest: hear opening; segmented digits append without whole replay; clear/interrupt leaves no long old sequence; hang up normally.

## Temporary files
Private clip remains /tmp/voiceagent-private-regression-935dbcf8/ (user-approved evidence, not Git). Test-only services/data: /tmp/voiceagent-native-repair-app and /tmp/voiceagent-native-identifier-app; logs/evidence under /tmp/voiceagent-native-*. Existing repository test-results ignored. Keep evidence; stop created services after verification.
