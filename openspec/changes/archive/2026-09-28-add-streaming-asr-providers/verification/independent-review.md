# Independent Change Review

- Change: `add-streaming-asr-providers`
- Review date: 2026-09-28
- Reviewer role: independent Change Verifier
- Result: **PASS**
- User Gate 2: **Feedback revision ready to resubmit; product acceptance remains pending**

## Conclusion

The current implementation and evidence satisfy the frozen product contract, including the confirmed D-019/D-020 User Gate 2 feedback amendment. The Change gate has zero errors; its sole warning is the intentionally pending task to record this independent revalidation. No product acceptance was marked by this review.

The previous external-real gap is closed. Under the product owner's bounded D-017/D-018 authorization, the production registry/adapters processed synthetic mono 16-bit 16 kHz PCM through Speechmatics Enhanced, Soniox `stt-rt-v5`, Deepgram Nova-3, and AssemblyAI Universal-3.5 Pro. Each successful probe produced Final text and exactly one downstream Turn; AssemblyAI also sent a live Agent Context update on the active connection and recorded `context_applied=true`. This independent review did not initiate any additional external or billable call.

The review reproduced KI-063 (New Bot summary rendered `undefined`) and KI-064 (the recorded D-020 scope had overreached the user's request by adding AssemblyAI search). Both are resolved: New Bot now renders `Deepgram · Automatic`; Soniox retains code/name search, while AssemblyAI displays 18 unique code/name labels and still submits raw codes. KI-065 is also resolved by removing the unrequested prototype interaction and restoring the product-owner-confirmed file byte-for-byte. Delivery status contains no Open known issue, unverified item, or undisclosed item.

## Gate model and baseline

- User Gate 1 is traceable to D-014 plus D-015; D-019/D-020 are explicit product-owner feedback amendments during User Gate 2.
- The sole frozen prototype is `prototypes/index.html`, SHA-256 `b6835ca7da9f0ee120081bb682a319f60be296029800c6b83e28a111b400b277`; the independent hash matches. The briefly generated unconfirmed replacement checksum was withdrawn rather than silently adopted.
- PRD V1.0.17 is the current behavior specification. D-019 adds a compact secondary account-Catalog refresh control with hover/loading/disabled states. D-020 adds `code (English name)` labels for Soniox and AssemblyAI while preserving raw-code submission; it does not add a new AssemblyAI search requirement.
- Checkpoint A uses the formal `/` route, production drawer/components, and the same DOM used by API-backed verification. No separate static product shell was found.
- Checkpoint B is proven for strict Catalog validation, Bot/component/provider credential isolation, encrypted SQLite persistence, account Catalog refresh/invalidation, restart recovery, session snapshots, safe failures, and history persistence.
- Checkpoint C is proven by local regression, isolated desktop/narrow UI execution, and the authorized four-target external-real evidence.
- User Gate 2 remains a product-owner action and is not implied by this `PASS`.

## Evidence classification

| Evidence class | Result | Representative evidence |
|---|---|---|
| Static | PASS | PRD V1.0.17, Delta Specs, design, tasks, D-001–D-020, strict provider models, public `ASRService`, timeout/error paths, and history schema were traced. |
| Fixture | PASS | The restored frozen prototype and formal UI fixture cover every provider/model branch, D-019 refresh states, and D-020 labels through the production route and DOM. |
| Mock | PASS | Provider request mapping, Speechmatics sentence/Turn separation and wire omission, Nova-3 `speech_final`, AssemblyAI context success/failure/timeout, Catalog validation, key isolation, and restart paths are covered without network access. |
| Local-real | PASS | Real FastAPI route, encrypted SQLite storage, migrations/restart, session resolution, frontend build, and bundled Chromium were exercised locally. |
| External-real | PASS | Four authorized production-adapter streams used synthetic 16 kHz PCM and real provider credentials within the recorded duration/retry/cost boundaries. |

## External-real authorization and results

Authorization is traceable to D-017 and D-018: only locally synthesized audio, at most 60 submitted seconds per Provider, USD 1 total, and at most five targeted retries after local diagnosis. The evidence records 11.501 seconds maximum potentially billable Speechmatics audio, 5.035 seconds Soniox, 8.220 seconds Nova-3, and a 6-second AssemblyAI session; the public-list estimate is below USD 0.004. No customer audio, Bot data, credential, or raw upstream response is retained.

| Provider/model | External-real result |
|---|---|
| Speechmatics Enhanced | 5.035 s submitted; 6 interim; 2 sentence Finals; 1 downstream Turn; 1257.8 ms first result; 3927.4 ms first-audio-to-Turn. |
| Soniox `stt-rt-v5` | 5.035 s submitted; 18 interim; 1 Final; 1 downstream Turn; 742.9 ms first result; 3886.0 ms first-audio-to-Turn. |
| Deepgram Nova-3 | 8.220 s Arabic `ar-SA`; positive `endpointing=300`; 3 interim; 1 Final; 1 `speech_final`-derived Turn; 1377.8/7517.6 ms. |
| AssemblyAI U3.5 Pro | 5.035 s submitted; 3 interim; 1 Final; 1 downstream Turn; live context send succeeded (`context_applied=true`); 1127.8/3674.5 ms. |

The permanent summary in `external-real-asr-2026-09-28.md` matched the secret-free normalized result files still present at review time under `/private/tmp/voiceagent-asr-gate2-20260928/`. The synthetic fixture hashes also match the evidence document. This review inspected those artifacts but did not replay the paid calls.

## Representative data-flow and failure review

1. Bot input is rendered from the server-owned Catalog, validated again server-side, encrypted per Bot/component/provider, persisted to SQLite, and returned without plaintext or ciphertext.
2. Speechmatics/Soniox account Catalogs are fetched only with a saved matching Provider key, normalized with an explicit timeout, persisted with the Bot, restored after restart, and enforced on both save and session start. Replacing/clearing the ASR key removes the old account Catalog; switching Bots rebuilds the frontend view from the immutable base Catalog.
3. Web Call resolves ASR/TTS/LLM credentials independently, freezes a non-secret session snapshot, and constructs ASR through `ASRService` and the Provider Registry. Chat Test bypasses ASR; missing/mismatched Web Call credentials fail safely.
4. Provider events are normalized before the common Pipeline. Ordinary Nova-3 final chunks do not end a Turn; only `speech_final` does. Speechmatics `AddSegment` accumulates text and `EndOfTurn` alone closes the user Turn. Soniox `<end>` and AssemblyAI native EOT remain their single Turn authorities.
5. AssemblyAI Agent Context is dispatched independently of TTS with a bounded send timeout and a stable Turn index. Context outcome and safe failure reason persist with provider/model/language and the `off|agent|full` context mode across restart.
6. Disconnects, stale Catalog values, invalid provider fields, provider errors, context socket failures, and timeouts do not leak credentials or silently switch Provider.
7. The server Catalog owns Soniox/AssemblyAI English labels. Soniox account discovery preserves Provider names with a safe code-table fallback; browser filtering matches Soniox code or name. AssemblyAI selection remains a Catalog picker whose hidden option and submitted value stay the original code.

## Independent commands and results

- `python3 scripts/quality/verify_change.py add-streaming-asr-providers` — PASS, 0 errors; one warning for the single expected pending independent-revalidation task.
- `.venv/bin/pytest -q` — 348 passed; three upstream deprecation warnings.
- `.venv/bin/ruff check src tests scripts/quality` — PASS.
- `.venv/bin/mypy --python-version 3.13 src` — PASS, 47 source files.
- `npm run build` in `frontend/` — PASS.
- `npx playwright test tests/ui/voice-bot.spec.js` against an isolated current-worktree service and temporary database — 18/18 PASS. Both projects cover New Bot summary, enabled refresh hover/loading/recovery, disabled refresh, Soniox English-name/code filtering, AssemblyAI unique code/name labels with raw `ar` submission, and overflow; the provider-state case explicitly uses 390×844.

## Residual notes

- Actual provider billing was not queried; submitted duration and conservative public-list estimates remain far below the authorized ceiling.
- The locked Speechmatics/Pipecat path emits a deprecation warning for `operating_point`; D-016 forbids a Pipecat upgrade in this Change, and the live stream plus local regression prove current behavior. This is dependency-upgrade debt, not an Open acceptance defect.
- Repository-wide Auth/Evaluation Playwright failures are outside this Change's Voice Bot route and are separately recorded; the complete scoped 18-case production-route matrix passes.
