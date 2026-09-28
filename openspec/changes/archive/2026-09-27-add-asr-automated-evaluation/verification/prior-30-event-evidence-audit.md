# Prior 30-event evidence audit — 2026-09-17

Evidence level: local-derived

## Located artifact

- Local-only path: `outputs/01a09dd7-2f06-7392-ae69-ad6fd88d20db/riyadbank_p1_asr_comparison.xlsx`
- SHA-256: `3a2ed8def1bd60217a2994e88f18ef44233d8c95b735bdb7639bf6cb522e4ad0`
- File timestamp: `2026-09-13 22:33:31 PDT`
- The source workbook remains ignored and is not copied into the Change because it contains customer-derived transcripts and ASR evidence.

### Additional historical report located

- Local-only path: `outputs/01a09dd7-2f06-7392-ae69-ad6fd88d20db/riyadbank_weekly_evaluation_report.html`
- SHA-256: `b267920321fbb5da8e85810ad8b7f96aae96b1e22ee0ff82863d6117a7f1bfa6`
- File timestamp: `2026-09-13 23:27:03 PDT`
- This report records a different historical flow: 23 conversation-level experience issues, 13 P1 conversations and 12 conversations recommended for review, using Soniox, Speechmatics and Deepgram.
- It does not contain 30 event-level Pass 2 records, structured model outputs, token usage, or the claimed `20 Bad / 6 Good / 4 review` classification set.

## What the artifact proves

- `P1 Event Comparison` identifies 13 conversations, 14 issues and 30 target events.
- `Run Metadata` identifies the screening mode as `compact / P1 only`.
- The workbook contains full-history context and Soniox, Speechmatics and Deepgram ASR evidence/segments.
- The workbook explicitly says every target event must be judged independently and provider agreement is not ground truth.

## What it does not prove

- It contains no second-pass decision output, valid/invalid JSON examples, token usage, retry result or final Good/Bad/manual-review classification.
- It uses Deepgram as the third comparison provider, while the current confirmed product uses ElevenLabs.
- The additional weekly report also uses Deepgram and conversation-level aggregates; its 13/12 counts cannot be mapped to the current Case-level 20/6/4 fixture.
- It therefore cannot be used as expected output for the current Pass 2 schema or as evidence that the current three-provider workflow reproduces historical decisions.

## Delivery consequence

The historical artifact remains unavailable and must not be reconstructed. Safe regressions use the workbook only for historical input provenance/counts and the weekly report only for its explicitly recorded conversation-level 13/12 flow. The `20 Bad / 6 Good / 4 review` data remains an explicit fixture, not local-real evidence. Under PD-029, the user-initiated `EV-20260918-2655` grouped Pass 2 result is the external-real evidence for the current schema, while deterministic tests cover malformed, missing, duplicate and retry cases. This closes task 6.8 without claiming that the historical 30-event decisions were recovered.
