# P022 — Test Behavior, Not Implementation

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- Tests assert what a caller or user can observe of the contract.
- Return values, durable state, events, and documented side effects are observed.
- A refactor that keeps behavior usually leaves the tests unchanged.
- Private methods and internal call sequences are not asserted, unless they are the contract.
- Fakes and stubs control dependencies without leaking internals.
- Structural checks are kept for real constraints, such as dependency direction or security.

## Limits

No result is rejected because compliance cannot be shown.

[Back to the engineering principles catalog](../README.md#p022)
