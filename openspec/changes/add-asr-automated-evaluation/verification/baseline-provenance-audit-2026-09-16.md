# Prototype Baseline Provenance Audit — 2026-09-16

## Findings

| SHA-256 | Recorded location | File/version attribution | Timestamp evidence | Confirmation evidence |
|---|---|---|---|---|
| `1c5313…` | `verification/gate-1-review.md` | Described only as the earlier Gate 1 prototype | Review file says 2026-09-15 | Superseded under PD-019; matching prototype bytes are unavailable and it is not a frozen baseline |
| `1c61fb…` | Historical `prototypes/README.md` and former `prototypes/index.html` | V1.14, Prompt slots/mapping/dictionary preview | Former prototype modified 2026-09-16 00:52 local; README modified one minute later | Explicitly confirmed in PD-019, then superseded by the PD-024-authorized V1.15 baseline |
| `b3c5aea…` | Historical `prototypes/README.md` and former `prototypes/index.html` | V1.15, Benchmark type filter/edit/pagination | Updated 2026-09-17 | Explicitly authorized in PD-024, then superseded by the PD-025-authorized V1.16 grouped-Prompt baseline |

## Repository history check

- The entire `openspec/changes/add-asr-automated-evaluation/` directory is currently untracked by Git.
- No committed prototype revision exists from which the `1c5313…` bytes can be restored.
- Repository search found no other copy or reference for either checksum.
- The former V1.14 `index.html` hashed to `1c61fb…`; the current full checksum is declared only in `prototypes/README.md`.

## Conclusion

PD-019 resolved the original conflict by confirming V1.14. PD-024 authorized V1.15, and PD-025 later authorized the grouped Pass 2 Prompt update. Therefore V1.16 is now the unique frozen baseline. The `1c5313…`, `1c61fb…`, and `b3c5aea…` prefixes remain only as historical audit notes and must not be used for current visual verification.
