# Independent Release Review — add-asr-automated-evaluation

- Status: **PASS**
- Date: 2026-09-20
- Scope: PD-042 final release readiness, including KI-120/121/122 and production data isolation
- Reviewer boundary: independent verification only; no business implementation was changed

## Decision

The Change is ready to enter the authorized production deployment workflow. The implementation, production route, persistence boundary and deterministic recovery tests are green. Production deployment itself has not run, so task 13.3 / UV-017 remains a mandatory deployment-time gate: the release is successful only if the deployed container proves production provenance and zero batch, report, review and Benchmark rows before the deploy script exits successfully.

This pending post-start assertion does not block initiating deployment because the workflow is fail-closed: a pre-existing non-production Evaluation database or known local batch ID is rejected before replacement; the new service uses a separately named Evaluation volume; the in-container empty-history verification runs before deployment success; and any failure triggers rollback. The authorized legacy cleanup targets only Evaluation-owned history and derived artifacts, retaining shared configuration.

## Independent evidence

### Automated gates

- Change gate: `PASS`, 0 errors, 12 disclosed warnings, 2 unchecked tasks (`12.3a` supplier invoice reconciliation and `13.3` deployment-time empty-history confirmation).
- Full backend suite: **191 passed**, 2 dependency deprecation warnings.
- Focused Evaluation/deployment/connection suite: **108 passed**, 2 dependency deprecation warnings.
- Full Evaluation browser suite: **82 passed** across desktop and narrow Chromium, including partial-result rendering, isolated empty state, translation request scoping and shared-state regressions.
- Scoped Ruff: passed.
- Mypy for `src/evaluation` and `src/api.py`: passed.
- Frontend production build: passed.
- Deployment script shell parse and production Compose configuration: passed.

### KI-120 / KI-122 — browser isolation

The previously failing empty-state, report-translation and Gemini-diagnostic scenarios now isolate their bootstrap/connection state. All 82 desktop+narrow checks pass, including the exact failed-batch partial-results scenario and minimum-width overlay checks.

### KI-121 — frozen Pass 2 recovery and report boundary

- Static trace: Pass 2 reconstructs groups from the original candidate set, reuses a stored deterministic group ID/idempotency key and skips only groups already completed.
- Regression evidence: `test_pass2_group_checkpoint_freezes_membership` and `test_pass2_retry_reuses_failed_frozen_group` pass.
- Finalization trace: persisted failed Case rows **or failed Pass 2 group rows** set the batch to `partially_failed/pass_2` and return before materialization or `freeze_preliminary_report`; therefore a failed frozen group cannot create a normal report.
- Historical `EV-20260920-9D33` remains evidence of the former defect and is not reused as proof of corrected retry behavior.

### Azure GPT / OpenRouter isolation

- Provider identities, encrypted connection rows, model catalog entries and executor routing are provider-qualified.
- Azure parses the deployment URL and uses Azure `api-key` semantics; OpenRouter uses its fixed official compatible endpoint and separate bearer credential.
- The same model ID can be registered for both providers without sharing secrets or overwriting OpenAI/GPT state; the API response does not return either key.
- Evidence level: deterministic local-real persistence/API tests and mocked provider diagnostics. No new paid Azure/OpenRouter call was authorized, so UV-019 remains disclosed and non-blocking.

### Failed-batch partial results

The API builds an ephemeral `partial_results` payload from persisted successful checkpoints without writing an immutable normal report. Backend and both browser viewports prove the non-final label, failed stage, completed/incomplete counts, ASR evidence, cost and failure detail.

### Production isolation and cleanup

- `compose.yaml` mounts `voiceagent-evaluation-production-data` at `/evaluation-data`, separate from the shared `/data` volume.
- Production storage initialization refuses a pre-existing database without immutable production provenance and marks only a fresh database.
- The deployment precheck rejects non-production provenance and the known local acceptance batch IDs.
- The post-start verifier requires production provenance and zero rows in batches, reports, reviews and benchmarks, then records `deployment.empty_history_verified=true`.
- Legacy cleanup deletes Evaluation result/audit/export/job rows and derived Evaluation artifact directories, but preserves resource connections and shared non-Evaluation configuration.
- Deployment has not executed; task 13.3 and UV-017 must remain open until the production command returns success and the empty-list marker is observed.

### PD-042 paid translation evidence

Read-only local SQLite inspection found exactly one `display_translation.requested` audit event for `EV-20260920-9D33`: Qwen `qwen-plus`, 179 texts, one attempt, no split and zero failed translations. The matching ledger row is CNY 0.008866 (3,175 input and 3,163 output tokens), within the authorized USD 0.10 ceiling.

## Non-blocking disclosed limitations

The remaining open items are already disclosed in `delivery-status.json`: repository-wide unrelated Ruff findings, dependency deprecations, Qwen structured-output/error-detail/retry-latency limitations, the unresolved Qwen native `prem` endpoint, unverified custom-model context limits, supplier-invoice reconciliation and real budget-stop proof, corrected Qwen Thinking external revalidation, and Azure/OpenRouter external-real diagnostics. None invalidates the verified release path; production deployment must still satisfy task 13.3 / UV-017.
