# P068 — No Validation Bypass

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- When a validator reports a problem, the cause is examined and fixed.
- Validators include type checks, lint rules, compiler warnings, security checks, CI gates, and
  runtime checks.
- The implementation, configuration, or dependency that violates the requirement is corrected.
- A defective rule is changed through the standard change and review process.
- A necessary suppression stays local, records its cause, and is easy to review and remove.
- A check that did not run or was skipped is reported as such.
- Evidence, not convenience, decides whether a control is incorrect.

## Limits

No output is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the principles catalog](../README.md#p068)
