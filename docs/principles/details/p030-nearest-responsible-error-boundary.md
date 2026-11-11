# P030 — Handle Errors at the Nearest Responsible Boundary

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- Each failure is handled where policy and context suffice for recovery, retry, compensation, translation, or termination.
- Lower layers detect, add safe context, and propagate.
- Cleanup constructs are deterministic. Cleanup is a distinct operation from recovery.
- Retry policy lives where idempotency, deadlines, and dependency semantics are known.
- A top-level boundary can turn an unhandled failure into a process exit, a protocol response, or a job status.
- Security policy can call for a generic public result with restricted internal diagnostics.

## Limits

No result is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the engineering principles catalog](../README.md#p030)
