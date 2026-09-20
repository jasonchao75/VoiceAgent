# External-real acceptance evidence — EV-20260918-2655

Date: 2026-09-19
Evidence level: external-real
Decision basis: PD-028 and PD-029

## Scope

This is the existing user-initiated batch selected for Engineering Checkpoints B/C. No additional provider request was made during acceptance verification. Its 24 pending manual-review items do not block product acceptance under PD-028.

## Persisted result

- Stage: `awaiting_review`; report: immutable `preliminary`.
- Source: 56 conversations and 381 valid user events.
- Pass 1: 120 candidates; Pass 2: 122 decisions.
- Final suspected result: 73 / 381 (19.2%).
- Automatic Benchmark samples: 98 (49 Good, 49 Bad).
- Manual review: 24 pending across 16 conversations.
- English batch and report views display `Riyad Bank branch routing v10`; source Arabic/English transcripts remain unchanged.

## Provider and recovery evidence

The deployed telemetry endpoint records 48 completed conversation jobs for each of Soniox, Speechmatics and ElevenLabs. These are the conversations selected for downstream evaluation ASR; no extra provider job was created for the Good balancing pool.

- Soniox: 48 completed jobs, average latency 6,987.9 ms.
- Speechmatics: 48 completed jobs, average latency 12,207.3 ms.
- ElevenLabs: 48 completed jobs, average latency 4,465.3 ms.
- Pass 1: 56 completed LLM requests, 11 retries and 12 rejected schema attempts.
- Pass 2: 5 completed grouped LLM requests, 2 retries and 3 rejected schema attempts.

The immutable report renders provider transcripts, evidence-linked event IDs, language distribution, positioning/playback states and current review status. Polling/callback parsing, retry idempotency, restart recovery and remote-cleanup behavior are additionally covered by deterministic adapter/orchestrator tests; the real telemetry does not claim a separate supplier-side cleanup receipt.

## Cost evidence

The append-only ledger records 144 ASR calls, 76 LLM attempts and a frozen-rate total of USD 2.2698320617847223. Token usage is separated into input, cached input, reasoning and output fields. The API correctly labels the value `estimated_from_frozen_supplier_rates`; it is not an actual supplier invoice.

## Local verification after the real run

- Evaluation Ruff and Mypy checks: pass.
- Evaluation backend/quality subset: 73 passed.
- Isolated production-route browser suite: 74 passed across desktop and narrow projects, including explicit 390×844 overlay checks.
- Current deployed real batch/report: inspected read-only; report entry, counts, English display name and pending-review state reconcile.

## Limits

- Actual supplier invoices were not available, so invoice reconciliation remains UV-003 / task 12.3a.
- Provider-specific token limits for every possible saved custom Model ID remain UV-002.
- No new paid request was sent to manufacture retry or failure evidence.
