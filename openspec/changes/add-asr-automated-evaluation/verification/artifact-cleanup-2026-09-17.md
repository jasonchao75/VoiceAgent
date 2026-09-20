# Local artifact and sensitive-output audit — 2026-09-17

Evidence level: local-static

## Preserved acceptance evidence

- Change-owned screenshots and redacted probe evidence under `verification/` remain tracked as delivery evidence.
- The one historical whole-batch probe JSON records token counts and stop reason only; it contains no API key, authorization header, transcript, or audio payload.

## Local-only data protected from commit

- `benchmarks/RiyadBankConversation/`: real uploaded Excel/MP3/WAV source package; ignored as customer data.
- `data/`: SQLite databases, including encrypted connection material; ignored.
- `outputs/`: generated evaluation workbooks and derived outputs; now ignored.
- `test-results/`, `playwright-report/`, `frontend/dist/`, dependency folders and Python caches: ignored generated artifacts.
- `*.log`, `*.wav`, `*.mp3`, and `*.pcm`: ignored logs and audio artifacts.

## Checks

- `git ls-files` contains no SQLite database, runtime log, generated test-result directory, or customer MP3/WAV artifact.
- A tracked-file scan found no private-key body or token-shaped `sk-...` credential. The only private-key phrase found is documentation explaining a placeholder header format.
- Existing local databases, recordings, logs, caches, and generated workbooks were preserved; this audit did not delete user data.

## Remaining boundary

Provider-side retention and supplier billing cannot be verified locally. They remain covered by the external-real verification items and are not claimed complete here.

## 2026-09-19 acceptance rerun

- The isolated acceptance service used `/private/tmp/voiceagent-asr-eval-gate2.rzYcNU`; the service was stopped and the directory was removed after 72 browser cases passed.
- The final post-fix rerun used `/private/tmp/voiceagent-asr-eval-gate2.fQKOtR`; it was stopped and removed after all 74 browser cases passed.
- Focused failure screenshots/traces and the generated Playwright HTML report were removed after the green rerun.
- `.env`, `benchmarks/library_ar/test-results/` and `test-results/` are ignored; no secret contents were inspected or staged.
- The configured remote is SSH (`git@github.com:jasonchao75/VoiceAgent.git`). No push or production deployment was performed during this local Gate 2 preparation.
