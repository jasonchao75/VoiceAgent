# UI Prototype-to-Implementation Delivery

Use this workflow for every Change that adds or materially changes a page, drawer or core interaction.

## Lightweight default

Use OpenSpec annotations, a state matrix, deterministic fixtures, Playwright fixed-viewport screenshots and the Change-local UI checklist. Do not start with a hosted visual platform.

## Gates

1. Gate 1: approve Delta Specs, prototype, precise annotations, state matrix, fixture and baseline candidates.
2. Gate 2: compare the static shell before full business wiring.
3. Gate 3: run functional, accessibility and visual checks across required states, then request final product acceptance.

Gate 1 is product scope approval, not final acceptance. Once the interactive prototype is approved, it becomes the frozen baseline and implementation drift must not trigger repeated product review of the same requirements. Gate 2 is owned by implementation and QA: compare the actual static page against that baseline and correct differences. Gate 3 is the product-facing final acceptance with functional and visual evidence.

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

Screenshot comparison supplements rather than replaces functional tests, keyboard/accessibility checks and product acceptance.
