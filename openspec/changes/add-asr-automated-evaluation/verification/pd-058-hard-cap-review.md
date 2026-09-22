# PD-058 Two-pass hard-cap verification

Date: 2026-09-22

## Scope

- Apply one provider-independent operating envelope to Pass 1 and Pass 2 only: 131,072 total, 65,536 final-input upper bound, 32,768 combined generation ceiling, and 32,768 safety margin.
- Render business evidence once into the frozen System Prompt. The User message contains only a fixed content-free instruction or content-free retry correction.
- Keep complete historical conversation text. Limit Pass 2 full-call ASR context to each Event Aligner target turn and the immediately preceding/following turn from the same provider.
- Pre-split an oversized Pass 2 conversation by stable Case subsets; reject a still-oversized Pass 1 conversation or Pass 2 Case before provider dispatch.
- Leave Event Aligner packing unchanged. Do not resume `EV-20260922-CB26` or make a paid verification call.

## Implementation evidence

- `src/evaluation/pass2_packing.py` owns the shared envelope, canonical payload builders, final-message estimator, and deterministic grouping rules.
- `src/evaluation/executor.py` uses the shared envelope for both passes, sends system-only evidence, selects bounded full-call turns from persisted Event Aligner mappings, and plans Case subsets before dispatch.
- `src/evaluation/storage.py` appends the reviewed Pass 2 Prompt contract when the bounded-turn marker is absent.
- Preflight size failures are persisted as `preflight_input_limit`, separate from provider JSON/schema failures.

## Automated verification

- Targeted evaluation regressions: `126 passed`.
- Full repository test suite: `251 passed`, with two pre-existing dependency deprecation warnings.
- Scoped Ruff: PASS for all changed Python source/test files.
- Mypy: PASS for all 43 source files.
- Frontend production build: PASS.
- Change gate: PASS with 0 errors; remaining warnings are already disclosed historical issues or unverified external-real coverage.

The regression set includes:

- all supported providers receiving the same Pass 1/Pass 2 operating ceiling;
- the final System Prompt containing one unique evidence marker while the fixed User message contains none;
- a 34-Case / 15-conversation CB26-shaped plan with every final group below 65,536 conservative input units;
- a single large conversation splitting into stable one-Case subsets before the mocked provider boundary;
- target and direct-neighbor turn selection excluding unrelated full-call turns;
- explicit preflight failure categorization and stable retry membership without paid recursive size discovery.

## Not verified

- No paid provider request was made in this implementation cycle.
- The stopped production batch `EV-20260922-CB26` was not resumed or mutated.
- A new user-initiated production batch has not yet demonstrated the corrected policy with real provider usage and output.
