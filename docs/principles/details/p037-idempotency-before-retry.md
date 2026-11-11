# P037 — Idempotency Before Retry

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- A side-effecting operation aims for one effect per equivalent request: an idempotency key, duplicate detection, a conditional write, or reconciliation.
- The idempotency key binds caller identity and normalized request data, recorded atomically with the effect.
- Equivalent requests return the recorded result. The same key with a different request is a conflict.
- A timeout leaves the outcome unknown. Status queries or reconciliation replace a blind retry.
- Tests cover duplicate, concurrent, late, and conflicting-key requests, and timeouts.
- A nonequivalent key reuse is reported as a conflict, not silently accepted.

## Limits

No result is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the engineering principles catalog](../README.md#p037)
