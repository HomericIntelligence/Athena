# P034 — Fail Fast

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- A missing or incorrect invariant, configuration, dependency, or precondition stops the operation near detection.
- Configuration and schemas get checked at startup or at the entry boundary.
- Invariants are examined before state use. The violated condition is recorded with safe context.
- Malformed input is rejected before irreversible or expensive work.
- Failure output names the defect and how to correct it. Termination releases resources.
- Tests cover startup, boundary, and invariant failures, not just correct execution.

## Limits

No result is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the engineering principles catalog](../README.md#p034)
