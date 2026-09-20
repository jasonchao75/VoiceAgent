# UI Verification Checklist — ASR Automated Evaluation

Status: User Gate 1 and Engineering Checkpoints A/B/C passed; User Gate 2 acceptance is pending

## Test contract

| Item | Value |
|---|---|
| Risk | High |
| Latest PRD | `PRD.html` V1.17 |
| Latest prototype | `prototypes/index.html` V1.17 |
| Annotations | `prototypes/ui-annotations.md` |
| State matrix | `prototypes/ui-state-matrix.md` |
| Fixture source | `benchmarks/RiyadBankConversation/` plus non-secret derived fixture |
| Desktop viewport | 1440 × 1000, scale 1 |
| Narrow viewport | 1024 × 1000, scale 1 |
| Minimum overflow viewport | 390 × 844, scale 1 |
| Locales/theme | English + Chinese / dark |
| Motion | Disabled during capture |

## User Gate 1 — specification and baseline

- [x] Input is one Excel + MP3 + WAV per full conversation ID
- [x] Good:Bad target is 1:1 and provider jobs are conversation-scoped
- [x] Suspected metric uses Bad + needs review, demonstrated as 24/441
- [x] Manual review explicitly chooses Good/Bad; unclear is reviewed and excluded
- [x] Automatic admission does not use a confidence threshold
- [x] English context residue found in product review is corrected in the prototype
- [x] Product approves proposal, Delta Specs, design and one-page review
- [x] Prototype upload fixture is corrected from single workbook to per-conversation workbooks
- [x] Approved prototype checksum and reviewer/date are recorded
- [x] Baseline screenshots are captured and protected from ordinary test overwrite

## Engineering Checkpoint A — production UI with fixtures

The historical `actual-gate-2-*` filenames are retained as evidence names. They now represent Checkpoint A and must exercise the same production route/components used by the real runtime.

- [x] Evaluation navigation, page hierarchy and batch-owned report entry match baseline
- [x] New-batch dialog explains and validates the per-conversation package contract
- [x] Stage detail distinguishes conversation ASR jobs from event Cases
- [x] Review comparison places production and proposed label adjacent
- [x] Good, Bad and unclear actions match the approved wording and required states
- [x] Report version, coverage, denominator and exclusion information are visible
- [x] Report Case audio expands inline with play/pause/resume, seekable progress and elapsed/total time; starting another stops the current player
- [x] Complete report Case details filter by scenario tag and disclose matching count / batch total without mutating the report
- [x] Every runtime report conversation ID opens the uploaded workbook timeline, highlights the target event and exposes the full-call recording
- [x] Chinese report mode translates fixed interface copy locally; real English/Arabic source text keeps the original and requests only visible text from the frozen Pass 1 model
- [x] Display translations remain browser-session cached, are marked non-evidence, and degrade to the original text without horizontal drawer overflow
- [x] AI-proposed tag name and description are displayed together; confirming creation persists both fields and batch-moves the associated Cases
- [x] Production-ASR analysis stays aggregate-only (`errors / total`) by scenario and does not duplicate Case IDs from the detail table
- [x] Candidate-tag overview cards expose `Review cases & create tag` navigation to the proposed-tag detail section
- [x] Proposed-tag details render exactly one Case per row with its production transcript and audio; group creation remains a single action
- [x] Scenario tags expose create, edit and delete actions; deletion confirmation states that referenced historical snapshots remain
- [x] Evaluation-context create/edit opens a complete form, preloads the reviewed RiyadBank data and saves an immutable next version
- [x] Context editing shows where conversation history, context, reference dictionaries, screening strategy and scenario tags come from and which values are frozen with the batch
- [x] Generic reference dictionaries expose stable keys, versioned CSV/JSON content and context linkage; RiyadBank branches are an instance rather than a platform field
- [x] Both complete Prompt editors preload the reviewed Chinese offline-flow content, default to read-only, require an explicit edit action, use `reference_dictionaries` instead of branch-specific variables, and validate required inputs, outputs and the no-confidence contract
- [x] Context list and editor can preview both variable-bearing templates and fully rendered Prompts, with clickable field mapping and complete linked-dictionary entries
- [x] Library displays both Good origins, 20 rows/page, selected/all-filtered download actions and the grouped ZIP contract
- [x] Desktop and narrow overlays have no horizontal overflow (minimum-width is covered in Checkpoint B)
- [x] Batch resources card separates ASR selection, Pass 1/Pass 2 LLMs and cost protection into distinct visual groups
- [x] Cost settings reads the server model catalog and sends explicit model tests through the existing live diagnostic API without mutating prices
- [x] A successfully tested custom Model ID is added to the persisted evaluation model catalog and becomes selectable in both new-batch LLM passes; failed or untested IDs are not added
- [x] Gemini 3.8 Flash is listed; provider-prefixed IDs are normalized; same-provider/Base URL Bot Keys can test another server-listed model without exposing the Key or mutating the Bot
- [x] All three ASR connections can be checked directly on the Resource connections page and synchronize their status with the matching async capability card
- [x] All four LLM connection cards expose an actionable live-test button and show testing, success or classified failure feedback in place
- [x] Successful ASR/LLM tests encrypt and persist the connection in SQLite; page reload and application restart restore only safe metadata and never return the Key

## Engineering Checkpoint B — real integration and resilience

- [x] Runtime storage contains no simulated batch, review or Benchmark result rows
- [x] Source UI reports 56/56/56 files, 853 parsed events, 0 blockers and 55 reference warnings without presenting fake conclusions
- [x] Direct report entry returns to the batch list when no real completed report exists
- [x] Conversation `1030000000091506` returns the workbook's Arabic R18 text and real MP3/WAV metadata
- [x] Evaluation start remains enabled for duration/timestamp reference warnings and is disabled only for true source-data blockers
- [x] Every New Evaluation action discards only the previous unstarted candidate, restores the active source and resets the dialog controls
- [x] Full ZIP upload is real, shows exactly three source groups, retains blocked candidates without replacing active data and activates only a fully valid package
- [x] All validation issues are visible and downloadable as CSV; repair ZIP and corrected per-conversation XLSX/MP3/WAV uploads re-run the complete audit
- [x] Historical timestamp regressions are labeled as reference warnings and do not block a conversation; true parsing/audio association failures remain blocking
- [x] ASR and LLM official-price actions call the server, update exact capability/model rows with source links, invalidate on model change and fail without overwriting existing values
- [x] Batch control, retry, budget pause and restart recovery pass in isolated backend regressions
- [x] Duplicate callback/retry does not duplicate calls, cost, reports or Benchmark samples in isolated backend regressions
- [x] One-provider failure continues with incomplete evidence; all-provider failure pauses affected work
- [x] Review Good/Bad/unclear, direct queue switching and early completion pass
- [x] Playback uses unified interval and correct source audio; degraded/unavailable states are honest
- [x] Suspected, manual-confirmed, review-coverage and Good:Bad counters reconcile with persisted rows
- [x] Preliminary/final reports are immutable and partial coverage is explicit
- [x] Benchmark search/filter/detail, selected-ID/all-filtered grouped ZIP generation and failure manifest pass
- [x] English UI contains no Chinese residue; Chinese UI preserves original transcripts
- [x] Keyboard, focus, accessible names and dialog/drawer behavior pass across desktop and narrow browser regressions
- [x] Every state-matrix row is mapped to the frozen baseline, the same production route/DOM, and named functional/accessibility evidence; representative V1.17 desktop/narrow captures are byte-identical to baseline
- [x] Engineering Checkpoint C independent review returns PASS
- [ ] Product gives User Gate 2 final acceptance

## Evidence table

| Scenario | Baseline | Actual | Diff | Ratio | Functional | Accessibility | Known deviation | Decision |
|---|---|---|---|---:|---|---|---|---|
| Batch list · desktop | `baseline/prototype-desktop.png` | `actual-gate-2-desktop.png` | byte-identical SHA-256 `3b9970c4…` | 0 changed bytes | passed | passed | none | pending product approval |
| Batch list · narrow | `baseline/prototype-narrow.png` | `actual-gate-2-narrow.png` | byte-identical SHA-256 `058ef053…` | 0 changed bytes | passed | passed | none | pending product approval |
| New batch · resources · desktop | approved prototype V1.2 | `actual-gate-2-new-run-resources-desktop.png` | same runtime structure | — | passed | passed | none | pending product approval |
| New batch · resources · narrow | approved prototype V1.2 | `actual-gate-2-new-run-resources-narrow.png` | same runtime structure | — | passed | passed | none | pending product approval |
| Complete report · desktop | approved prototype report | `actual-gate-2-report-desktop.png` | same runtime structure | — | passed | passed | Full report extends vertically as designed | pending product approval |
| Report Case audio · desktop | approved prototype V1.3 | `actual-gate-2-report-inline-audio-desktop.png` | targeted | — | real WAV play/pause/resume/progress passed on current 8000 deployment | pause/resume/progress names checked | Cases without a verified recording mapping explicitly show unavailable | pending product approval |
| Report Case filter · desktop | approved prototype V1.4 | `actual-gate-2-report-case-filter-desktop.png` | targeted | — | passed | combobox name and visible-row count checked | Static fixture only | pending product approval |
| Report AI tag creation · desktop | approved prototype V1.5 | browser-verified implementation | targeted | — | passed | bilingual name and description checked | Fixture and real-API persistence paths both pass | pending product approval |
| LLM model validation and catalog admission | approved prototype V1.7 | browser-verified implementation | desktop + narrow | — | successful custom-model diagnostic adds the model to both new-batch selectors; unverified endpoint rejection covered by backend test | button name, diagnostic feedback, SQLite catalog reload and two-pass selection checked | Real provider charge still requires an explicit click; automated tests intercept the provider response | pending product approval |
| Resource connection tests | approved prototype V1.11 | browser-verified 8000 deployment | targeted | — | real test-and-save, encrypted SQLite persistence, reload and restart coverage passed across two viewports | progress, success, classified failure, missing-Key focus and no-Key response checked | Existing transient page values cannot be recovered; each connection requires one final successful test after upgrade | pending product approval |
| Context and reference dictionaries | approved prototype V1.12 | browser-verified implementation | targeted | — | passed across two viewports | input-source map, linked dictionary, stable key and version-save controls checked | Fixture and real-API persistence paths both pass | pending product approval |
| Prompt protection and request preview | approved prototype V1.16 | browser-verified implementation | targeted | — | passed across two viewports | read-only default, explicit edit, variable slots, field mapping, complete dictionary entries, grouped Pass 2 `request_group_id`/`results[]`/`positioning_quality`, current draft values and dialog overflow | Current real batch supplies the frozen grouped result evidence | pending product approval |
| Review / dialog / report / Benchmark / configuration | approved prototype | browser-verified implementation | targeted | — | 74/74 Evaluation browser cases passed across desktop and narrow projects, including explicit 390×844 overlay checks | names, keyboard dismissal, focus restoration, context fields, prompt editing, request previews, encrypted connection reload, model-catalog admission and decision states checked | Fixture and real local API tests use one production route/DOM | pending product approval |
| Superseded Gate 3 simulation | approved Gate 2 shell | retained historical `actual-gate-3-*` screenshots | not applicable | — | withdrawn; simulated rows are no longer served by runtime APIs | not acceptance evidence | screenshots are historical only | rejected |
| Real source import and audit | approved upload contract | `docs/reports/evaluation/riyadbank-source-audit-2026-09-16.md` | source contract | — | 56 Excel/MP3/WAV sets parsed; 0 blockers, 55 reference warnings, no result rows | empty/result-unavailable states checked | providers not run | ingestion ready |
| Dataset upload and repair | approved upload contract | browser-verified 8000 deployment | targeted | — | complete ZIP, clean-dialog reset, blocked candidate, issue CSV, repair overlay, safe activation and invalid-archive rejection passed | visible file inputs, keyboard dropzone and desktop/narrow overflow checked | Missing/corrupt/unparseable source data still blocks; historical duration/timestamp defects warn only | upload accepted |
| External-real batch and report | approved report/review contract | `EV-20260918-2655` / `real-batch-evidence-2026-09-19.md` | read-only production inspection | — | three provider results, two-pass retries, immutable preliminary report and Benchmark totals reconcile | English name, report entry, source transcripts and review state checked | 24 pending reviews are non-blocking under PD-028 | Checkpoint B evidence accepted by PD-029 |
| Pass 2 failure report recovery | approved single-report action and complete Case evidence | rebuilt localhost `EV-20260920-566C` immutable R2 | targeted live-data repair | — | batch row exposes one report action plus retry; report exposes persisted ASR text and event audio for 73 Cases without inventing Pass 2 decisions | failure label, distinct action names, table headings and audio controls checked in the in-app browser | real Qwen retry remains UV-018 | implementation verified; product acceptance pending |
| Report source drawer and Chinese comparison | approved prototype drawer / PD-030 | browser-verified implementation on isolated current-source service | mock provider response; real source API shape | — | 34/34 runtime cases passed across desktop and narrow projects; source drawer, full-call URL, Arabic original, Chinese comparison and one-call session cache checked | semantic tab, dialog focus and keyboard-ready timeline checked | no real LLM call; translation quality/provider availability remains UV-014 | ready for independent re-review |
| Manual review and Benchmark Arabic comparison | PD-032 | rebuilt localhost:8000 production route | mock provider response | — | desktop/narrow checks confirm current-task Arabic evidence, current-page batch grouping, detail history and session-cache reuse | original Arabic remains readable and narrow viewport passes | no real LLM call; translation quality/provider availability remains UV-014 | ready for independent re-review |
