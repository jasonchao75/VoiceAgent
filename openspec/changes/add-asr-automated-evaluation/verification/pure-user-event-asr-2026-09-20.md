# Pure-user event ASR verification — 2026-09-20

## Authorization and scope

- Decision: PD-035
- Source: user explicitly authorized sending `1030000000082501 · R15` to Soniox, Speechmatics and ElevenLabs.
- Audio: `user_record/1030000000082501.wav`, clipped to `51.222–53.255s` (2.033s).
- Ceiling: USD 0.05 total.
- Stop rule: one dispatch per provider, no retry.

## External-real result

| Provider | Remote task | Text | Segments | Result |
|---|---:|---:|---:|---|
| Soniox | yes | 5 characters | 2 | usable |
| Speechmatics | yes | 0 characters | 0 | empty; must be treated as invalid result |
| ElevenLabs | synchronous | 7 characters | 0 | usable text without word segments |

No full-call MP3, neighboring event, transcript workbook or robot audio was sent. Raw customer text and credentials are intentionally omitted from this evidence file.

## Findings

- The generated provider input exactly matches the deterministic user-event interval.
- Short-clip providers may return valid text without word-level segments; source positioning must therefore come from the pre-dispatch event clip rather than provider segments.
- A remote job that returns empty text must be recorded as a failed provider resource, not a successful empty candidate.
