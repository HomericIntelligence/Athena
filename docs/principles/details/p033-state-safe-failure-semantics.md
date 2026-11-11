# P033 — State-Safe Failure Semantics

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- After a failure, each applicable resource and state holder stays unchanged or reaches a specified recoverable state that preserves invariants.
- Multistep mutations record invariants and failure postconditions before the first state change.
- Temporary state is prepared and published atomically where possible.
- Scoped ownership releases locks, files, connections, and temporary resources on each exit path.
- One transaction covers a transactional boundary. Systems without one record durable step data and compensation data.
- Propagation continues after a failure (see P031). Failure erasure is the separate anti-pattern.

## Limits

No result is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the engineering principles catalog](../README.md#p033)
