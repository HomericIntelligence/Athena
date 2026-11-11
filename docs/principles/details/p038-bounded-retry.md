# P038 — Bounded Retry

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- Retry covers transient failures classified by the dependency contract. A catch-all retry is the separate anti-pattern.
- A finite try count or a shared deadline bounds the budget. Nested calls share one owner for one budget.
- Concurrent callers spread retries with exponential backoff and jitter.
- Server guidance (for example, `Retry-After`) fits within the caller deadline.
- Cancellation, permanent failure, or budget exhaustion ends the cycle.
- Telemetry records try count and last outcome, correlated with the request.

## Limits

No result is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the engineering principles catalog](../README.md#p038)
