# P026 — Regression Before Repair

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- Where safe reproduction is possible, a small automated test reproduces the reported defect before the repair.
- The test fails on the reported cause before the repair and passes after it.
- The smallest fixture that reproduces the defect carries the behavior.
- The test keeps a behavior-oriented name after the repair.
- The repaired test stays in the suite to catch recurrence.
- Where reproduction is not safe, a model-based reproduction or a containment-first plan is a reasonable stand-in.

## Limits

No result is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the engineering principles catalog](../README.md#p026)
