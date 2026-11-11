# P039 — Bounded Waiting

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- External waits (operations, locks, queues, processes, asynchronous results, delegated tasks) carry a deadline, a timeout, or a cancellation signal.
- Budgets come from service objectives and measured latency. Very short timeouts cause spurious failure.
- Downstream calls inherit the end-to-end deadline and the cancellation signal.
- A timeout bounds the caller wait, not the callee execution. Retrying side-effecting work pairs with idempotency or reconciliation.
- Locks, slots, and temporary resources release on each terminal path.
- Success, cancellation, timeout, and failure stay distinct outcomes.

## Limits

No result is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the engineering principles catalog](../README.md#p039)
