# UI Prototype-to-Implementation Delivery

Use this workflow for every Change that adds or materially changes a page, drawer or core interaction.

## Lightweight default

Use OpenSpec annotations, a state matrix, deterministic fixtures, Playwright fixed-viewport screenshots and the Change-local UI checklist. Do not start with a hosted visual platform.

## Two user gates and three engineering checkpoints

1. **User Gate 1 — contract and baseline approval.** Approve Delta Specs, prototype, precise annotations, state matrix, deterministic fixtures and baseline candidates.
2. **Engineering Checkpoint A — production UI with fixtures.** Build the real route and components, load deterministic fixture data through an explicit adapter, and compare structure and visuals with the frozen baseline.
3. **Engineering Checkpoint B — real integration and resilience.** Keep the same UI code, connect real APIs and persistence, and verify loading, empty, failure, retry, partial, refresh and restart behavior.
4. **Engineering Checkpoint C — independent verification.** Reconcile the state matrix, functional tests, accessibility checks, visual diffs and evidence through an independent verifier.
5. **User Gate 2 — final product acceptance.** Present one consolidated result only after all three engineering checkpoints pass.

User Gate 1 freezes the product contract; User Gate 2 accepts the delivered product. The three checkpoints are engineering responsibilities, not extra user approvals. Implementation drift must be corrected by engineering instead of sending the user back through the same decision.

Checkpoint A must use the production route, components and DOM that continue into Checkpoints B and C. Only the data source may switch between deterministic fixtures and real APIs through an explicit adapter. A separate static acceptance page or duplicated component tree is prohibited because it cannot prove what the integrated product will render.

## Evidence layout

```text
verification/
├── ui-checklist.md
├── visual-diffs.md
├── baseline/<scenario>.png
├── actual/<scenario>.png
└── diff/<scenario>.png
```

Baseline updates are a review action, never a side effect of tests. Record browser, viewport, scale, font readiness, locale, timezone, fixture revision and masking rules. Use the templates in `docs/engineering/templates/ui-delivery/`.

## Risk level

- Low: targeted screenshot plus functional assertion.
- Medium: component matrix, desktop/narrow screenshots and diff.
- High: full page matrix, deterministic fixture, all fixed viewports, functional/accessibility tests and visual diff.

Screenshot comparison supplements rather than replaces functional tests, keyboard/accessibility checks and User Gate 2 product acceptance.
