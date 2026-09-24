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

Pending. Record the subset dataset ID and manifest, Batch ID, task/Case/group counts, provider dispatch identities, ledger/reservation reconciliation, report outcome and controlled-timeout recovery evidence here before declaring S2 complete.
