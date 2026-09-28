---
name: change-delivery-guard
description: Guard implementation of an OpenSpec Change by managing development questions, assumptions, evidence levels, and delivery claims. Use for every behavior-changing task with an openspec/changes entry.
---

# Change Delivery Guard

Use `AGENTS.md` as the authority.

## Workflow

1. Before implementation, read the main specs, Change files, prototype baseline, and all files under `decisions/`; then run `python3 scripts/quality/verify_change.py <change-name>`.
2. If the artifacts do not uniquely determine observable behavior, data truth, metrics, cost, latency, privacy, retention, failure handling, or Mock/degradation boundaries, add an `Open` item to `decisions/open-questions.md`, pause the affected work, and ask the user with 2-3 options plus a recommendation.
3. Record only reversible, non-product engineering choices in `decisions/assumptions.md`.
4. After a user decision, update `decision-log.md` and every affected Spec, design, task, prototype, and test before resuming.
5. Label evidence as `static`, `fixture`, `mock`, `local-real`, or `external-real`; a lower level never proves a higher one.
6. Keep only `Open` product questions in `open-questions.md`; move confirmed outcomes to `decision-log.md`, and put engineering defects in `tasks.md`.
7. Before sending real customer data or making a paid external call, record the data scope, recipient, cost ceiling, stop condition, and explicit authorization source in `verification/delivery-status.json` and `decision-log.md`.
8. Before every milestone or delivery claim, re-read the decision files and rerun the verifier. Never set product acceptance for the user.
9. When ready, hand off to the independent `change-verifier` workflow; do not self-approve.
10. As soon as implementation, debugging, testing, or review reveals a defect, mismatch, failure, risk, or unverified scope, record it in `verification/delivery-status.json` under `known_issues` or `unverified_items` before doing more work. Do not leave it only in reasoning, tool output, or an intermediate chat update.
11. Before ending any turn that performed work, review those two lists and give the user a compact four-part report: completed work, discovered issues, unverified scope, and decisions needed. Explicitly say when no new issue was found. Set `disclosed_to_user` to `true` only after the issue is included in a user-visible message.
12. Never end a working turn or claim completion while an Open item has `disclosed_to_user: false`. Disclosed Open items may remain during development, but they block final acceptance unless resolved, excluded from scope with evidence, or explicitly accepted by the user.
13. For UI Changes, use exactly two user gates and three engineering checkpoints: User Gate 1 freezes the contract and baseline; Checkpoint A compares the production UI with deterministic fixtures; Checkpoint B verifies the same UI with real APIs, persistence and failure/recovery states; Checkpoint C performs independent functional, accessibility, visual and evidence verification; User Gate 2 is final product acceptance.
14. Never build a separate static acceptance shell. Checkpoint A must use the production route, components and DOM; only an explicit data adapter may switch between fixture and real sources. Engineering checkpoints never require repeated user approval of the frozen contract.
