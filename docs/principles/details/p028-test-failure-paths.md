# P028 — Test Failure Paths, Not Just Success Paths

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- Failure-path tests cover malformed input, dependency failure, timeout, cancellation, resource exhaustion, cleanup, and authorization denial.
- Injected failures land at dependency boundaries and state transitions.
- After a failure, the caller-visible error contract and the durable state are both checked.
- Success behavior has its own baseline.
- Failure injection fits sandboxes, staging, and controlled substitutes, not live production operations.
- Mocked failures can differ from production behavior. Contract or integration evidence narrows the gap.

## Limits

No result is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the engineering principles catalog](../README.md#p028)
