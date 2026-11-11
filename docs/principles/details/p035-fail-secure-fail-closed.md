# P035 — Fail Secure / Fail Closed

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- A protected operation proceeds after a clear permission result. Missing, invalid, stale, or indeterminate security state reads as denial.
- A policy-service timeout or error is not a permission. Denial and infrastructure failure can share one external response.
- A validation or authorization failure keeps the protected resource unchanged.
- Tests exercise missing policy, dependency timeout, corrupt credentials, exception paths, and stale state.
- Protected diagnostics distinguish denial from infrastructure failure and keep secrets out.
- A safety-critical system can prefer a different safe state when a domain hazard analysis calls for it.

## Limits

No result is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the engineering principles catalog](../README.md#p035)
