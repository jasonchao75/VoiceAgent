# S2 External-Real Canary — 2026-09-24

## Authorization

- Decision: PD-084
- Confirmation: “那你搞吧。可以”
- Data: exactly five conversations from the frozen RiyadBank production source
- Recipients: Speechmatics, Soniox and ElevenLabs receive matching audio; Qwen3.8-Max receives corresponding conversation text and ASR evidence
- Cost ceiling: USD 1 total across the normal run and controlled post-send-timeout recovery check
- Stop conditions: any duplicate provider dispatch, state regression, budget breach, missing durable unknown-usage reservation, P0/P1 correctness defect, authentication failure or rate limit
- Excluded: S3, S4, E65A rerun and any unrelated customer data

## Selected conversations

| Conversation | Language | Duration | Prior coverage role |
|---|---:|---:|---|
| `1030000000079648` | Arabic | 13.92 s | short, candidate path |
| `1030000000072164` | English | 19.68 s | short, candidate path |
| `1030000000086003` | mixed | 43.32 s | mixed-language candidate path |
| `1030000000070672` | Arabic | 76.42 s | no-candidate path |
| `1030000000070676` | Arabic | 160.90 s | long, multi-Case path |

## Execution evidence

### Normal-path attempt 1 — stopped

- Subset ZIP: SHA-256 `cb17e91495303ba5e64173f7b1b046719f644d730298302cc5258504aeacb3b3`; 15 files; package audit valid with 5 matched conversations, 76 events, 36 user events and no blocking issue
- Frozen dataset: `dataset-b0f19b12c0b341c19715b9445db639ff`
- Batch: `EV-20260924-EF94`; `completed / completed / 100%`; frozen budget USD 1; recorded cost USD 0.03971245
- Active-source restoration: the original 82-conversation package was immediately re-audited and activated as `dataset-c4a33df9f45c42bdb89d1da31e923f4e`; 82/82/82 required files, 1,232 events, 560 user events and zero blocking issues
- Completed external work: one Qwen Pass 1 request; five Pass 1 conversation results; four full-context calls for each of Speechmatics, Soniox and ElevenLabs; all 13 reservations settled; no active operation, unknown-usage reservation or budget breach remained
- Stop-condition result: **TRIGGERED**. All 27 Case-ASR projections failed and all nine Cases became `excluded_insufficient_evidence`; Event Alignment and Pass 2 never started. The controlled-timeout check and S3 were not executed.
- Root cause: all four ambiguous audio-alignment fallback calls failed locally before reservation or dispatch. `_AUDIO_ALIGNMENT_FALLBACK_PROMPT` declared `{{payload}}`, while `_llm_json` rendered the template with the payload's child keys and separately sent the complete payload as the user message. Strict prompt rendering therefore raised `ValueError` for the unresolved slot before every fallback request.
- Repair: remove the duplicate/unresolved system-prompt slot and state that the user message contains the complete input JSON exactly once. A regression now proves the system prompt renders with no unresolved slot and does not embed the request payload.
- Local verification: 4 focused regressions passed; full repository suite 305 passed with the two previously disclosed dependency warnings; Ruff format/check, scoped Mypy and frontend production build passed.

Independent review, deployment and a rerun limited to the same five frozen conversations remain required before S2 can pass. The original PD-084 USD 1 ceiling applies cumulatively; USD 0.03971245 has already been consumed according to the frozen-rate ledger.
