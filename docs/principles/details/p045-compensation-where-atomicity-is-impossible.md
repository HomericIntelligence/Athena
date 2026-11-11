# P045 — Compensation Where Atomicity Is Impossible

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- A workflow spanning systems or safe transactions records each completed step with its recovery data.
- Forward steps are idempotent. Compensation steps are safe, resumable, and idempotent.
- Business invariants set the compensation sequence. Many workflows use the reverse order.
- Irreversible points are known. Irreversible steps come after validation and reversible work.
- An unclear or failing compensation escalates with state context and a supported manual procedure.
- The post-compensation state is a specified business-equivalent state. A refund does not erase history.

## Limits

No result is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the engineering principles catalog](../README.md#p045)
