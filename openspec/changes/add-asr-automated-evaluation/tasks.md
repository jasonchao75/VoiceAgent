# Tasks: Add ASR Automated Evaluation

## 0. User Gate 1 — specification and baseline

- [x] 0.1 Confirm `PRD.html V1.17` plus `prototypes/index.html V1.17` (SHA-256 `fd400adde2eb769570d3766dcbe5fea4d5f6ab6976565dcdfb84be2c1fec7d5e`) as the current requirement baseline
- [x] 0.2 Confirm per-conversation Excel input, suspected-rate formula, unclear exclusion, Good:Bad 1:1 sampling and no confidence threshold
- [x] 0.3 Remove obsolete PRD artifacts and retain one latest PRD and one latest prototype
- [x] 0.4 Draft proposal, three capability Delta Specs, design, tasks and UI verification materials
- [x] 0.5 Product reviews and approves this Change one-page summary and Delta Specs
- [x] 0.6 Freeze the approved prototype and record checksum, approver and date
- [x] 0.7 Create a deterministic non-secret UI fixture derived from the 56-call RiyadBank dataset
- [x] 0.8 Capture immutable desktop and narrow prototype baseline screenshots

## 1. Persistence and configuration foundations

- [x] 1.1 Add evaluation SQLite migrations and repositories for batches, snapshots, inputs, events, jobs, cases, LLM runs, reviews, reports, Benchmark samples and audit events
- [x] 1.2 Add immutable version models for tags, contexts, generic reference dictionaries, Prompt templates and pricing
- [x] 1.3 Reuse Fernet credential encryption for isolated evaluation ASR/LLM connections; verify no Key is returned or logged
- [x] 1.4 Add optimistic version checks, idempotency keys and transactional state transitions
- [x] 1.5 Add retention classes that exempt evaluation and Benchmark data from normal history cleanup

## 2. Configuration APIs and pages

- [x] 2.1 Implement global scenario-tag create/edit/version/enable/disable/delete, tombstones and reference history
- [x] 2.2 Implement versioned evaluation-context create/edit/default/enable/disable plus links to zero or more versioned generic reference dictionaries
- [x] 2.3 Implement complete two-pass Prompt read-only viewing, explicit edit entry, template restore/diff/versioning and required-contract validation
- [x] 2.4 Implement ASR Key-only and LLM Base URL + Key connection cards with safe classified tests
- [x] 2.5 Implement async ASR capability Endpoint/model/input validation and available/pending/unavailable states
- [x] 2.6 Implement model-specific ASR/LLM pricing versions and default/hard batch budget configuration without unreliable preflight estimate
- [x] 2.7 Add idempotent database seeding for the reviewed RiyadBank context, generic branch-dictionary instance and two Chinese Prompt fixtures

## 3. Import and validation

- [x] 3.1 Implement safe ZIP staging with path traversal, symlink, duplicate path, file-count and expanded-size protection
- [x] 3.2 Parse one `Dialogue Details` workbook per conversation and validate required columns, timestamps and one-role-per-row
- [x] 3.3 Match exact full-ID sets across per-conversation Excel, MP3 and WAV directories
- [x] 3.4 Probe audio content and validate codec, sample rate, channels, duration and shared timeline tolerance
- [x] 3.5 Generate downloadable issue CSV and implement scoped repair ZIP / corrected per-conversation Excel replacement
- [x] 3.6 Add tests for missing, duplicate, malformed, undecodable, time-drift and malicious archive inputs

## 4. Batch orchestrator and cost control

- [x] 4.1 Implement persisted async worker leases, finite concurrency, stage checkpoints and application-restart recovery
- [x] 4.2 Implement batch draft/validate/start/stop/pause/resume/partial-failure/review/completion state transitions
- [x] 4.3 Implement per-call explicit timeouts, provider rate limits, maximum three automatic retries and targeted manual retry
- [x] 4.4 Implement frozen price-based cost accounting and stop-before-new-call budget gate
- [x] 4.5 Verify duplicate commands, callbacks and worker recovery do not duplicate external calls, costs or downstream data

## 5. Evaluation ASR adapters

- [x] 5.1 Define the common async file-ASR contract and normalized result/segment/error models
- [x] 5.2 Implement Soniox `stt-async-v5` submit/status/result/cleanup with explicit timeout
- [x] 5.3 Implement Speechmatics `melia-1` batch/multi submit/status/result/cleanup with explicit timeout
- [x] 5.4 Implement ElevenLabs `scribe_v2` webhook submission, HMAC/correlation/result handling and synchronous fallback when no public webhook is configured; retain no unsupported polling or cleanup claim
- [x] 5.5 Enforce one provider job per conversation and reuse results across all Case types (superseded by PD-035)
- [x] 5.6 Use the user-initiated `EV-20260918-2655` run as external-real RiyadBank Arabic/English/mixed evidence; reconcile formats, timestamps, provider results and retries with deterministic callback/polling/recovery/cleanup coverage in `verification/real-batch-evidence-2026-09-19.md` without making a new paid call
- [x] 5.7 Replace full-call candidate extraction with stable pure-user event clipping and one event-level transcription per selected provider
- [x] 5.8 Persist event/provider jobs, clip trace, cost and retry state; ensure Pass 2 and manual review consume only event-level results
- [x] 5.9 Add boundary, adjacent-robot exclusion, invalid-timeline, retry/idempotency and one-Case external-real provider verification coverage

## 6. Two-pass LLM and evidence alignment

- [x] 6.1 Implement the generic two-pass runtime input envelope and Pass 1 conversation renderer, including frozen context/dictionaries/strategy/tags, structured candidate/pass/data-issue validation and valid-user denominator
- [x] 6.2 Build the extra Good pool only from valid pass events in conversations containing a suspect
- [x] 6.3 Normalize ASR segments with stable local IDs based on full conversation ID
- [x] 6.4 Implement target-event alignment, merged playback ranges, context padding and exact/expanded/full/unavailable quality
- [x] 6.5 Implement Pass 2 evidence rendering and Good/Bad/manual structured-output validation
- [x] 6.6 Enforce automatic admission without confidence threshold or provider majority voting
- [x] 6.7 Implement deterministic Good balancing to final 1:1 target and disclose pool shortfall/origin
- [x] 6.8 Audit the missing prior 30-event second-pass artifact without reconstructing it, retain its P1 workbook and separate 13-P1/12-review Deepgram report only as historical provenance, and use the current `EV-20260918-2655` grouped Pass 2 result plus deterministic tests for the current schema (PD-029; `verification/prior-30-event-evidence-audit.md`)
- [x] 6.9 Implement Thinking-enabled dynamic token packing with conversation-atomic evidence, output reservation, separate Case/request counters, frozen group idempotency and failed-group-only retry

## 7. Benchmark and review domain

- [x] 7.1 Implement automatic AI-labeled Good/Bad idempotent ingestion
- [x] 7.2 Implement manual Good, manual Bad with required label, and unclear-without-Benchmark transitions
- [x] 7.3 Cut Benchmark audio only from timeline-validated pure-user WAV and preserve location/processing trace
- [x] 7.4 Implement append-only correction history for label, language, tag and source
- [x] 7.5 Implement early review completion and exclusion of unreviewed/unclear cases
- [x] 7.6 Add tests for retry/idempotency, Good/Bad decisions, unclear discard, early completion and clip failure recovery

## 8. Evaluation UI — Engineering Checkpoint A: production UI with fixtures

- [x] 8.1 Add Evaluation product rail and batch list/detail using the approved layout and fixed fixture
- [x] 8.2 Implement new-batch dialog with per-conversation package explanation, validation repair and frozen resource selection
- [x] 8.3 Implement five-stage task progress, provider status, candidate table and targeted retry controls
- [x] 8.4 Implement manual review with adjacent production/current label, equal provider candidates and explicit Good/Bad/unclear actions
- [x] 8.5 Implement report list/detail entered only from a batch, complete Case table and conversation drawer
- [x] 8.6 Implement Benchmark filters, detail, cross-page selection, sample revision and download toolbar
- [x] 8.7 Implement tags, context, full Prompt, resource connection and cost configuration pages
- [x] 8.8 Reuse the server model catalog and live LLM diagnostic endpoint; keep model verification separate from pricing
- [x] 8.9 Add Gemini 3.8 Flash and reuse a same-provider/Base URL Bot Key for a temporary server-catalog model diagnostic without exposing the Key or changing the Bot
- [x] 8.10 Add 20-row Benchmark paging, selected/all-filtered download scopes and the language/scenario-grouped ZIP contract
- [x] 8.11 Add create/edit/delete actions for data-backed scenario tags while preserving referenced historical snapshots
- [x] 8.12 Make context create/edit-version actions clickable and preload the reviewed RiyadBank context plus Chinese two-pass Prompt content in the production UI fixture mode
- [x] 8.13 Make all resource-connection test buttons interactive in place; reuse the existing live LLM diagnostic route and show card-level testing/success/failure feedback
- [x] 8.14 Add generic versioned reference-dictionary configuration, context linkage and two-pass runtime-input mapping; remove branch-specific Prompt variables
- [x] 8.15 Default both Prompt templates to read-only, add explicit edit mode, and add two-pass final-request preview from the context list and editor
- [x] 8.16 Restore explicit per-session variable slots and add clickable field-to-slot-to-rendered-Prompt mapping with complete dictionary entries
- [x] 8.17 Verify the production desktop and narrow UI against the frozen baseline with deterministic fixtures; historical product approval is retained as evidence, but this checkpoint is not a separate user Gate

## 9. Evaluation UI — Engineering Checkpoint B: real integration and resilience

- [x] 9.1 Wire loading/empty/error/paused/partial/retry/completed/partial-final states and report Case scenario-tag filtering to APIs
- [x] 9.2 Implement audio playback with inline play/pause/resume/progress controls, single-active-player behavior, event seek, authorization-checked streaming and unavailable/degraded states
- [x] 9.3 Implement English/Chinese switching; assert English mode has no Chinese UI residue while preserving source transcripts
- [x] 9.4 Add keyboard/focus/label/dialog/drawer accessibility coverage
- [x] 9.5 Assert every dialog, drawer and popover has no horizontal overflow at desktop and narrow viewports
- [x] 9.6 Implement selected-ID and frozen-filter Benchmark ZIP generation, progress, expiry and manifest failure feedback
- [x] 9.7 Deliver the Checkpoint B local runtime backed by SQLite and the persisted external-real `EV-20260918-2655` result; the prior simulated-result runtime remains withdrawn
- [x] 9.8 Persist successfully live-verified custom LLM Model IDs in the evaluation model catalog and expose them to both new-batch pass selectors without storing credentials
- [x] 9.9 Reset every New Evaluation dialog to a clean draft and downgrade historical duration/timeline findings to non-blocking reference warnings
- [x] 9.10 Persist ASR/LLM Resource Connections with Fernet encryption, real provider tests and restart-safe server metadata; remove all page-memory-only success states

## 10. Reports, metrics and observability

- [x] 10.1 Implement suspected, manually confirmed and review-coverage formulas from persisted rows
- [x] 10.2 Implement immutable preliminary and final report versions, partial coverage and frozen snapshot display
- [x] 10.3 Implement language/scenario/problem distributions, evidence-linked observations and proposed-tag batch reassignment
- [x] 10.4 Add structured counters/traces for stage latency, provider jobs, retries, schema failures, cost and queue depth without transcript/audio/Key content
- [x] 10.5 Add audit coverage for configuration, batch actions, review, early completion, playback, download and edits

## 11. Engineering Checkpoint C and User Gate 2

- [x] 11.1 Import and audit the 56-call RiyadBank source package; keep the prior 20 Bad / 6 Good / 4 review output only behind the explicit frozen-fixture flag
- [x] 11.2 Verify the frozen fixture numerator is 24/441, not 30/441; keep it explicitly separate from the real 56-call source/run counts (381 valid events and 120 historical candidates)
- [x] 11.3 Verify extra Good balancing uses already transcribed conversations and creates no additional provider job
- [x] 11.4 Verify one-provider failure continues with incomplete evidence; all-provider failure pauses only affected work; targeted retry preserves successes
- [x] 11.5 Verify budget stop, restart recovery, duplicate webhook and repeated ingestion are idempotent
- [x] 11.6 Run backend unit/integration tests, Ruff, Mypy, frontend build and Playwright functional/accessibility/visual checks
- [x] 11.7 Complete `verification/ui-checklist.md` with baseline/actual/diff evidence, obtain independent Checkpoint C PASS, then request User Gate 2 acceptance
- [x] 11.8 Confirm test archives, generated audio, databases, logs and provider responses are cleaned or recorded as evidence and never committed; see `verification/artifact-cleanup-2026-09-17.md`
- [x] 11.9 Inspect the SSH remote, ignored `.env`, generated test outputs and temporary files for the local Gate 2 handoff; no push or production deployment was requested in this cycle, so remote CI/deployment verification remains conditional on a future push
- [x] 11.10 Run the full local acceptance subset after real ASR/LLM execution exists; 73 backend/quality tests and 72 isolated production-route desktop/narrow browser tests pass after `EV-20260918-2655`
- [x] 11.11 Delete the superseded audit-only EV-20260916-1400 batch under PD-026 and remove its owned review, Benchmark, report, execution and cost rows while preserving shared source/configuration data and a content-free deletion tombstone (KI-051)
- [x] 11.11 Purge all simulated batch/review/Benchmark results from runtime storage, expose only parsed source facts, block only structural/unreadable source errors, and save a 56-row audit report
- [x] 11.12 Add confirmed deletion for audit-only, failed and stopped batches; reject active-batch deletion, expose staged-upload discard, keep one idempotency key per New Evaluation draft, and cover all paths with API/UI regressions (KI-052, KI-053)

## 12. Delivery-audit remediation

- [x] 12.1 Reconcile the PRD header, Gate review records and task status so they describe one truthful delivery phase
- [x] 12.2 Replace the stale provider-not-run historical `gate-3-local-review.md`; it must not be used as current runtime or Checkpoint B/C evidence
- [x] 12.3 Implement separate ASR and LLM ledgers with captured usage, retries, cache/reasoning/output tokens and frozen-rate estimates per PD-013
- [ ] 12.3a Reconcile captured usage and frozen-rate estimates against an actual supplier bill after a user-initiated external run
- [x] 12.4 Reconcile runtime Prompt envelopes with the frozen variable-slot and final-request-preview contract; static preview alone is insufficient
- [x] 12.5 Complete Pass 1 strategy/priority validation, candidate deduplication and truthful progress denominators
- [x] 12.6 Complete Pass 2 evidence-location, bilingual proposed-tag and full-schema admission validation
- [x] 12.7 Implement and verify Speechmatics remote cleanup rather than claiming submit/status/result as the complete adapter lifecycle
- [x] 12.8 Replace the fixture report with immutable preliminary/final report APIs and real runtime rendering matching the frozen baseline; the user-initiated EV-20260918-2655 run now provides valid preliminary-report evidence.
- [x] 12.9 Remove Chinese generated issue/question fields from English manual review and add source-transcript-aware i18n regression coverage
- [x] 12.10 Audit the first real whole-batch probe, record its authorization/scope/parameters/cost/invalid result and prohibit reuse of that authorization
- [x] 12.11 Reconcile the frozen single-Case Pass 2 output schema with confirmed dynamic multi-Case token packing, including `request_group_id`, `results[]` and `positioning_quality`, under PD-025
- [x] 12.12 Enforce the historical PD-010 isolation for EV-20260916-1400, then delete it under PD-026; exclude its report, metrics, reviews and Benchmark samples from formal product totals and Checkpoint B/C evidence
- [x] 12.13 Link every frozen preliminary report to its owning batch immediately, repair existing unlinked reports on startup, and verify the report entry on the real EV-20260918-2655 batch (KI-054)
- [x] 12.14 Canonicalize frozen tag aliases in new reports and merge aliases in immutable historical report presentation so one logical tag renders once (KI-055)
- [x] 12.15 Separate first-pass candidate, final suspected and Benchmark totals in batch/report presentation, and reconcile the real batch summary from its immutable report (KI-056)
- [x] 12.16 Populate the dashboard suspected-error metric from the latest valid formal report instead of continuing to say evaluation has not run (KI-057)
- [x] 12.17 Render an explicit not-run placeholder for failed batches without a suspected numerator instead of exposing `null` as data (KI-058)
- [x] 12.18 Persist and render a safe actionable failure category/message/stage/retryability contract for future failures; retain no invented reason for the already deleted `EV-20260918-4966` (KI-060)
- [x] 12.19 Distinguish active and inactive product-rail entries on both VoiceAgent and Evaluation routes, with semantic current-page state and a browser regression (KI-066)
- [x] 12.20 Remove remaining English interface copy from Chinese mode and, under PD-030, display an on-demand Pass 1 LLM Chinese comparison without changing source transcripts or treating translations as evidence (KI-068)
- [x] 12.21 Connect every real report conversation ID to the API-backed conversation-history drawer and full-call audio player already required by the frozen prototype (KI-069)
- [x] 12.22 Constrain both LLM passes and proposed tags to neutral ASR-quality dimensions; normal user behavior, flow completion and bot behavior cannot independently become ASR errors or global tag proposals (PD-031, KI-077)
- [x] 12.23 Restore the frozen report baseline: aggregate production-ASR X-of-Y results without Case IDs, candidate-tag navigation actions in the overview, and one proposed Case per detail row (KI-079, KI-080, KI-081)
- [x] 12.31 Remove the duplicate completed-batch report action, expose persisted event-level ASR text/audio independently of Pass 2 citations, keep failed Pass 2 groups retryable without freezing a normal report, and omit Qwen JSON Mode when Thinking is enabled (KI-109, KI-110)
- [x] 12.32 Treat `completed_partial` as the terminal completed state it is and allow its confirmed transactional deletion through the existing product/API path (KI-113)
- [x] 12.24 Extend display-only Chinese comparison to all visible Arabic evidence in the current manual-review task and Benchmark current page/detail, grouped by batch and cached per browser session (PD-032)
- [x] 12.25 Retry malformed display-translation output once, then fall back to stable groups of at most four texts with bounded retries and budget short-circuiting (PD-033, KI-090)
- [x] 12.26 Disable DeepSeek Thinking only for display translation and preserve successful chunk translations when later chunks fail, with per-text UI fallback and non-regression tests (PD-034, KI-093)
- [x] 12.27 Allow explicitly confirmed deletion of awaiting-review and completed non-running batches, then delete all local Evaluation test history while preserving shared source data and configuration (PD-037, KI-104)
- [x] 12.28 Reject batch creation when either selected LLM lacks a frozen price; terminate all-Pass-1-failed and valid zero-candidate worksets truthfully; delete EV-20260920-7878 without rerunning it (PD-038, KI-105)
- [x] 12.29 Keep batch-creation errors visible and focusable inside the New Evaluation dialog instead of relying on a transient Toast (KI-106)
- [x] 12.33 Add isolated Azure GPT and OpenRouter evaluation connections, provider-qualified model selection, encrypted persistence, diagnostics and executor routing without changing existing LLM resources (PD-041, KI-117)
- [x] 12.34 Expose persisted successful checkpoints for failed/partially-failed batches as clearly labeled non-final partial results, including stage coverage, ASR evidence, completed Pass 2 results, cost and failure detail (PD-041)
- [x] 12.35 Add backend and dual-viewport UI regressions for Azure/OpenRouter isolation, duplicate model IDs, secret redaction, price gating and partial-result recovery (PD-041)
- [x] 12.36 Canonicalize saved, selected and execution-time frozen LLM pricing aliases so a saved DeepSeek `deepseek-v4-flash` rate is accepted through New Evaluation and paid execution, including compatibility for existing price versions (KI-128)
- [x] 12.37 Diagnose production failed evaluations that never materialize Cases, preserving partial successful checkpoints and separating zero-candidate success from execution failure (KI-129)
- [x] 12.38 Diagnose and reconcile Cost Settings live diagnostics versus batch execution for `Gemini/gemini-3.8-flash` (KI-130)
- [x] 12.39 Implement Pass 1 conversation-atomic dynamic token packing, grouped Prompt/output validation, frozen group checkpoints, failed-group-only retry and deterministic regressions (PD-045)
- [x] 12.40 Make Gemini/Qwen structured-output retries corrective rather than identical, remove hidden SDK retry multiplication, and retain per-conversation/per-Case checkpoints (KI-131)
- [x] 12.41 Support the saved Qwen China native DashScope `/api/v1` endpoint, route `qwen3.8-max` through its native generation contract, retain compatible-mode support, and expose the model in Cost Settings/New Evaluation (PD-046, KI-118)
- [x] 12.42 Correct pure-user clip alignment when workbook `time (s)` values represent utterance completion/recording events rather than speech onset, fail closed on ambiguous boundaries, and add one reusable full-call context ASR job per conversation/provider without allowing it to become an event candidate (PD-048, PD-049, KI-149)
- [x] 12.43 Add confirmed single-sample Benchmark deletion from list/detail, removing only its record, revisions and managed derived WAV while preserving upstream evidence and a content-free audit tombstone (PD-050)
- [x] 12.44 Replace percentage-only retry feedback with persisted stage/group success, failure, pending and attempt counts; do not count failed work as successful progress or let a later subset overwrite whole-stage totals (KI-152)
- [x] 12.45 Defer additional-Good balancing until every suspect Pass 2 group succeeds, so retrying a partially failed suspect set cannot expand the visible Case total (KI-153)
- [x] 12.46 Make Pass 2 timeout/schema retries change the failing condition through safe regrouping or bounded fallback, instead of replaying the same oversized group up to six cumulative attempts (KI-154)
- [x] 12.48 Replace Excel-anchor speech-island selection with full-call diarization/text/order alignment, require two-provider time consensus, validate/refine only on the pure-user track, and fail closed on missing/conflicting evidence (PD-053, KI-156)
- [ ] 12.47 Distinguish queued versus in-flight Pass 2 groups and expose last activity/elapsed time, so a multi-minute provider request cannot appear frozen as generic pending work (KI-155)
- [x] 12.49 Materialize completed Pass 2 decisions into Manual Review and Benchmark Library even when sibling Cases remain failed, while keeping the batch retryable and the report explicitly non-final (KI-161)
- [x] 12.50 Use accepted provider-turn unions as final short-utterance clip boundaries, forbid user-track contraction, and add production-derived R7/R13 regressions (PD-056, KI-162)
- [x] 12.51 Implement dynamically packed Event Aligner groups over complete conversation units, validate only real turn IDs and customer-speaker ownership, isolate invalid event mappings from valid siblings, preserve actionable clip failure reasons, and add production-derived R6/R7/R13 regressions (PD-056, KI-163, KI-164, KI-165, KI-166)
- [x] 12.52 Apply the repository Ruff formatter to the five Event Aligner source/test files rejected by CI, rerun the full release checks, and republish without changing behavior (KI-167)
- [x] 12.53 Diagnose production deployment run 35700335615, record the exact failure boundary, apply only an in-scope safe correction if required, and reverify deployment plus public health (KI-168)
- [x] 12.54 Build one canonical final-message path for Pass 1 and Pass 2: render runtime variables once into the System Prompt and send only a fixed content-free User instruction; remove nested/top-level/User-message evidence duplication (PD-058, KI-169)
- [x] 12.55 Enforce the provider-independent 128K operating envelope for both passes using the exact final serialized request: input <= 64K, reasoning plus visible output <= 32K, safety >= 32K, further reduced by the frozen model's verified limits (PD-058)
- [x] 12.56 Bound Pass 2 full-call evidence to each Case's Event Aligner-selected provider turns plus the immediate preceding/following provider turns, while retaining the complete historical conversation text and event-level retranscriptions (PD-058)
- [x] 12.57 Pre-plan oversized Pass 2 conversations into stable Case subsets and fail a still-oversized single Case before dispatch; keep Pass 1 conversations indivisible and fail a still-oversized single conversation before dispatch (PD-058)
- [x] 12.58 Add deterministic CB26-scale regressions for final-wire de-duplication, conservative preflight accounting, both-pass cap enforcement, Case-complete grouping, restart idempotency and no paid size-discovery retry; make no real external call (PD-058, KI-169)
- [x] 12.59 Reconcile the size/schema failure categories and persisted diagnostics so an operator can distinguish preflight-cap rejection from provider JSON/ID-contract failure without logging customer evidence (PD-058, KI-169)
- [x] 12.60 Correct the shared Pass 2 generation budget across Gemini, DeepSeek, Qwen, GPT/Azure and OpenRouter so visible JSON is reserved first and Thinking uses only the remaining 32K allowance (PD-059, KI-170)
- [x] 12.61 Give single-Case local input/output planning failures dedicated preflight categories and preserve the last meaningful stage, progress, checkpoints and cost when a guarded run becomes partially failed (PD-059, KI-170)
- [x] 12.62 Persist and display safe ASR failure diagnostics with provider, full-call/event scope, attempts, retryability, controlled category and actionable reason, excluding raw responses and customer evidence (PD-059)
- [x] 12.63 Add cross-provider budget, truthful-progress and ASR-redaction regressions; complete independent verification and deploy without automatically retrying CB26 or 7D19 or making paid calls (PD-059)
- [ ] 12.64 Respect the persisted retryable contract when building a retry-failed plan; skip non-retryable provider results and deterministic alignment/preflight failures, and present the eligible retry scope before any paid dispatch (KI-171)
- [ ] 12.65 Account for the longest corrective retry instruction during Pass 1 packing, or deterministically re-plan a failed near-cap group before retry, so a schema correction cannot turn a previously dispatched group into a permanent local input-cap failure (KI-172)
- [x] 12.66 Add a version-checked, idempotent no-provider command that freezes paused/partially-failed batches with a preliminary report as `final_partial`/`completed_partial`, preserving successes and excluding incomplete work (PD-060, KI-173)
- [x] 12.67 Add the “Use current results” batch action and confirmation copy by reusing the frozen dialog pattern, with API/UI regressions for preservation, exclusion, no provider dispatch and invalid states (PD-060)
- [x] 12.68 Complete independent verification and deploy PD-060 while preserving production data and without operating 7D19 or making paid provider calls

## 13. Production deployment boundary (authorized by PD-042)

- [x] 13.1 Provision an independently named production data volume without copying local SQLite, uploads, recordings, clips, reports or cost rows
- [x] 13.2 Add a pre-deployment check that rejects local acceptance volumes or known local test batch IDs
- [x] 13.3 Verify the fresh production batch, report, review and Benchmark lists contain no local test history before opening access
- [x] 13.4 Publish the independently verified KI-128 hotfix without clearing existing production Evaluation data, then verify CI/CD, health and deployed commit (PD-044)
- [x] 13.5 Publish the independently verified grouped LLM and Qwen native/compatible reliability release, preserve production Evaluation data, and verify CI/CD, health and deployed commit (PD-047)
- [x] 13.6 Publish the independently verified audio-alignment/full-context and single-Benchmark deletion release, preserve production Evaluation data, and verify CI/CD, health and deployed commit (PD-051)
- [x] 13.7 Publish the independently verified adaptive Pass 2 retry and truthful-progress release, preserve production Evaluation data and failed checkpoints, and verify CI/CD plus public health without triggering a paid batch retry (PD-052)
- [x] 13.8 Publish KI-161 after the PD-053 release completes, then backfill EV-20260921-BA92's completed decisions without external calls and verify 18 reviews, 20 Benchmarks, 6 retained failures and no frozen report (PD-055)
