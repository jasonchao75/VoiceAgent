---
name: change-verifier
description: Independently verify an implemented OpenSpec Change against its PRD, prototype, specs, decisions, real data flow, and evidence. Use after implementation and before user acceptance; do not implement fixes while reviewing.
---

# Independent Change Verifier

1. Read the PRD, frozen prototype, Delta Specs, tasks, decision records, and evidence.
2. Run `python scripts/quality/verify_change.py <change-name>`.
3. Trace representative user paths from input to persisted output; check source truth, failures, refresh, restart, and external-service reality.
4. Keep `static`, `fixture`, `mock`, `local-real`, and `external-real` evidence distinct.
5. Compare against the frozen prototype without updating it.
6. Write `verification/independent-review.md` with `PASS`, `BLOCKED`, or `INSUFFICIENT EVIDENCE` and reproducible evidence.
7. Do not implement fixes, change requirements, lower criteria, or mark user acceptance.
8. For UI Changes, verify the declared `two-user-gates-three-engineering-checkpoints` model and prove that fixture and real-data checks exercise the same production route, components and DOM. Treat a separate static shell as a blocker.
