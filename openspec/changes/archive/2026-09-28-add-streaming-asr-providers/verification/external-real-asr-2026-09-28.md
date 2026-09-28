# External-real ASR evidence — 2026-09-28

## Authorization and safety boundary

- Decisions: D-017 and D-018.
- Data: locally synthesized speech only; no customer audio, Bot data, credentials, or raw provider responses were persisted.
- Limit: one target call per Provider, at most 60 submitted seconds per Provider, USD 1 total; up to five targeted retries after local diagnosis.
- Harness: `scripts/quality/verify_streaming_asr_external.py`, which uses `create_default_asr_registry()` and the production adapters. It requires the recorded authorization ID, refuses evidence overwrite, validates mono 16-bit 16 kHz PCM, and records only normalized evidence.

## Synthetic fixtures

| Fixture | Content | Source seconds | SHA-256 |
|---|---|---:|---|
| English continuous | Local macOS synthetic voice, no >=120 ms internal silence | 3.035 | `8b70d8c25e58232942043d3f54bcf3fe6e29f6b9a2c4611db9b0b5793d80a444` |
| Arabic | Local macOS synthetic Arabic voice | 6.220 | `0f07642d8031592de2cbfe8a91420609c125a67ba4b2a16185c1e72bb2b2d24d` |

Each successful stream appended 2.000 seconds of silence to exercise the configured Provider endpoint. After the independent verifier matched all fixture hashes and normalized results to this permanent summary, the temporary audio and JSON files under `/private/tmp/voiceagent-asr-gate2-20260928/` were deleted.

## Results

| Provider/model | Language/config | Submitted | Interim | Final text segments | Downstream Turns | First result | First audio → Turn | Result |
|---|---|---:|---:|---:|---:|---:|---:|---|
| Speechmatics Enhanced | `en`, Smart Turn, sentence emission | 5.035 s | 6 | 2 | 1 | 1257.8 ms | 3927.4 ms | PASS |
| Soniox `stt-rt-v5` | `en`, Provider endpoint detection | 5.035 s | 18 | 1 | 1 | 742.9 ms | 3886.0 ms | PASS |
| Deepgram Nova-3 | `ar-SA`, `endpointing=300`, `speech_final` mapping | 8.220 s | 3 | 1 | 1 | 1377.8 ms | 7517.6 ms | PASS |
| AssemblyAI Universal-3.5 Pro | `en`, live Agent Context update | 5.035 s | 3 | 1 | 1 | 1127.8 ms | 3674.5 ms | PASS (`context_applied=true`) |

The latency column starts at first audio, so it includes the spoken fixture duration. Approximate post-source-audio endpoint intervals were 892.4 ms (Speechmatics), 851.0 ms (Soniox), and 1297.6 ms (Nova-3).

## Targeted failures and fixes

1. Speechmatics attempt 1 stopped before audio on TLS trust-root failure (KI-048). The registry now pins the locked certifi CA bundle.
2. Speechmatics retry 1 reached the service but the server rejected literal `permitted_marks="all"` (KI-050). The product keeps that UI sentinel, while the adapter omits the wire field for “all”.
3. Speechmatics retry 2 used a synthetic clip with prosodic pauses and produced five provider Turns. The verifier initially displayed ten due to bidirectional broadcast counting (KI-051). The verifier now counts downstream only and requires exactly one Turn; retry 3 with continuous synthetic speech passed with two sentence Finals and one Turn Final.
4. Soniox attempt 1 stopped before audio on the same TLS trust-root issue (KI-053). Its targeted retry passed after the registry-level fix.
5. Speechmatics Voice first attempted runtime model downloads (KI-049). The adapter now reuses Pipecat's bundled compatible Silero and Smart Turn ONNX assets; a no-download regression initializes both locally.

## Cost control

Maximum successfully submitted or potentially billable audio observed is 11.501 seconds for Speechmatics, 5.035 seconds for Soniox, 8.220 seconds for Deepgram, and a 6-second billed WebSocket session for AssemblyAI. Using public list rates observed on 2026-09-28 (Speechmatics Realtime Enhanced USD 0.43/hour, Soniox realtime approximately USD 0.12/hour, Deepgram Nova-3 monolingual USD 0.29/hour, AssemblyAI Universal-3.5 Pro Realtime USD 0.45/hour), the estimated cumulative cost is below USD 0.004. Actual account billing was not queried; this estimate is far below the authorized USD 1 ceiling.

- Speechmatics pricing: https://www.speechmatics.com/pricing
- Soniox pricing: https://soniox.com/pricing
- Deepgram pricing: https://deepgram.com/enterprise-accelerator-program
- AssemblyAI pricing: https://www.assemblyai.com/docs/getting-started/models

## Remaining proof

- Re-run the complete local regression and Change gate after this evidence update.
- Obtain an independent Change Verifier `PASS` before submitting User Gate 2.
