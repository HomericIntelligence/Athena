# P025 — Property-Based Testing for Invariants

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- A property states an invariant such as round-trip equivalence, order, conservation, or a state invariant.
- Generators cover the domain, including nested or constrained shapes, and keep rejected combinations in view.
- Each failure shrinks to a small counterexample.
- Counterexamples that help diagnosis enter the regression suite with recorded seeds.
- Property tests stand alongside named examples, boundary cases, fuzz tests, and integration tests.
- A run without failures is one piece of evidence. It does not close an unbounded domain.

## Limits

No result is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the engineering principles catalog](../README.md#p025)
