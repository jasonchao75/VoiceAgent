# Independent backend review

Status: PASS — backend repair scope (2026-10-27; final production/device acceptance remains separate)

Scope: `TranscriptLedger` local source ownership and `CustomTDCoordinator` cumulative revision routing. No production changes or external model calls were made by this reviewer.

## Evidence

- `fixture`: `/tmp/voiceagent-r91-py311/bin/python -m pytest tests/test_td_runtime.py tests/test_td_review_regressions.py -q` — 59 passed.
- `static`: inspected proposal, design, Delta Spec, decisions, source ledger, coordinator, identifier collection/rules/output and current main voice-pipeline Spec.
- Gate: `python3 scripts/quality/verify_change.py fix-identifier-cumulative-rtc` — PASS, 0 errors, 2 warnings (4 tasks unchecked; live verification pending).
- Additional offline reproduction: `/tmp/identifier_review_probe.py` (temporary, no secrets, no external requests).

## Findings discovered and subsequently fixed

1. **Cumulative continuation bypasses the new pause before echo.** After local `12` is processed, `speech_started()` followed by same-source `123` invokes `identifier_output` from `_revise_retained_local()` while `_speaking=True`. The newly added digit is therefore eligible for playback before the required pause. Revision observation must invalidate stale pending playback immediately, but scheduling expanded-source audio must wait for current speech to stop and pause policy to pass. The reproduction logs `('123', True, 'incomplete')` twice (Partial and Final); output-level text dedup prevents identical audio replay, but does not restore the pause.
2. **Incomplete/overflow protection is lost after cumulative continuation.** `speech_started()` clears `_rule_evaluation`; retained incomplete revisions are hidden by `ledger.view()` and never restored to the candidate. After stop at 2400ms, advancing to 10400ms produces no incomplete reminder, with `_rule_evaluation=None`. The new test checks value and no disconnect at 6500ms, but not timeout/overflow behavior. Restore evaluation/candidate ownership for the latest unsubmitted cumulative contribution and cover both reminder paths.

## Limits

Formal RTC wiring is reviewed separately. Real phone, AEC, weak network, and paid vendor calls were not exercised. These tests do not establish production end-to-end success.

## First repair retest

The first two findings were reproduced and then retested after coordinator changes: no echo callback while `_speaking=True`, and the incomplete reminder is emitted at 10400ms. However, a third regression blocks approval:

3. **Same-range late corrections can lose their echo permanently.** With `collection=None` (pure echo enabled, completeness disabled), local `12` is processed and its candidate is cleared. A same-range Final `13` now updates value but follows the new observe-only retained revision branch. No candidate remains to dispatch the correction at `advance()`. `/tmp/identifier_review_same_range.py` returns only `('12', False, 'local')` in callbacks with collection value `13`. Distinguish an expanded source requiring a new pause from a same-range correction whose original pause already passed, and preserve the prior correction contract.


## Final repair retest

All four reproduced backend findings are resolved in the reviewed working tree:

- Cumulative continuation waits for speech stop/pause; initial Partial `12` still dispatches locally before Final.
- Incomplete timeout after resumed cumulative input emits its reminder.
- Same-range late correction with completeness disabled dispatches `13` after previously dispatching `12`.
- A fourth issue discovered during repair (pending pure correction leaking into the next ordinary turn) is fixed: after correcting to `13`, a new-source `hello` submits only `hello`, and collection remains `13`.

Final targeted suite: **89 passed** (`test_td_runtime`, `test_td_source_frames`, `test_td_review_regressions`, `test_td_identifier`, `test_td_identifier_output`). Repeated offline probes confirm:

- `/tmp/identifier_review_probe.py`: no continuation echo while speaking; incomplete reminder emitted.
- `/tmp/identifier_review_same_range.py`: callbacks `12`, then corrected `13`.
- `/tmp/identifier_review_next_turn.py`: commits `[hello]`, collection `13`.
- `/tmp/identifier_review_fences.py`: local source expansion works; after `freeze_submission`, a merged word crossing the submitted boundary remains rejected.
- `/tmp/identifier_review_clear.py`: cleared old source cannot repopulate collection or dispatch another echo.

The final gate returns PASS with warnings while the primary agent is still updating issue/task records and the separate RTC review is in progress. This backend PASS is not whole-Change acceptance, production rollout proof, or real-device validation. The reviewer changed only this report, not implementation or product requirements. Temporary probes contain synthetic data only and are not intended for Git submission.
