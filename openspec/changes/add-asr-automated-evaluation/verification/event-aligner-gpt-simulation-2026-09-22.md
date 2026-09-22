# Event Aligner GPT Simulation — 2026-09-22

## Evidence level

- Level: mock against external-real persisted inputs
- Model: independent GPT task in the current Codex session
- External calls: none to Soniox, Speechmatics, ElevenLabs, or the production LLM connections
- Code changes: none

## Contract under test

The model receives ordered worksheet events plus immutable diarized provider turns. It may select only existing provider `segment_id` values or return `missing`/`ambiguous`. It must not generate timestamps. Deterministic code validates the selected IDs and derives the final interval from the union of accepted provider turns.

## Results

| Event | ElevenLabs | Soniox | Speechmatics | Resulting union |
|---|---|---|---|---|
| `1030000000086502/R6` | `102,104,106` (`26.70–27.22s`) | `98,99,100` (`26.91–27.39s`) | `missing` | `26.70–27.39s` |
| `1030000000089001/R7` | `76,78` (`18.94–20.48s`) | `93` (`19.05–19.11s`) | `42` (`18.86–19.18s`, low-confidence lexical mismatch) | `18.86–20.48s` |
| `1030000000089001/R13` | `162,164` (`45.16–45.84s`) | `190,191` (`45.57–45.87s`) | `89` (`45.10–45.78s`) | `45.10–45.87s` |

## Findings

- The model mapped R6 without requiring the application to normalize `Two two one` and `2 2 1` into an exact text match.
- For R7, Speechmatics produced the wrong lexical text, but its user-speaker turn occupied the same ordered time slot as the two-provider mapping. The model retained it as low-confidence rather than allowing the wrong text to move the event to another utterance.
- R13 mapped cleanly across Arabic words and digit renderings.
- The cleaner architecture is a dedicated `Event Aligner`, not a second operation described as Pass 1. Complete candidate-bearing conversations are dynamically packed so the whole batch uses one request when safe and only context overflow creates the minimum additional groups. Pass 1 selects events; ASR supplies immutable turns; the aligner binds event IDs to turn IDs; deterministic code checks speaker/order/provider count and computes the union boundary.

## Limits

This simulation proves that one GPT instance can produce the expected mapping for the three reported production cases. It does not prove prompt/schema reliability across the full dataset, retry behavior, token cost, latency, or resistance to repeated/merged/missing turns. Those require deterministic fixtures and an integrated evaluation after Q-016 is confirmed.
