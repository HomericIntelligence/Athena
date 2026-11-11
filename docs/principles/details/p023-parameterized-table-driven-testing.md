# P023 — Parameterized / Table-Driven Testing

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- One behavior rule lives in one test procedure.
- Named cases carry inputs and expected results through that procedure.
- Each case has a name that says what it covers.
- Usual, empty, missing, rejected, and boundary cases are all welcome.
- Expected results are written out, not computed with production logic.
- Cases with different workflows get their own tests instead of a crowded table.
- Parameterized cases add coverage; they do not replace property tests or boundary analysis.

## Limits

No result is rejected because compliance cannot be shown.

[Back to the engineering principles catalog](../README.md#p023)
