# P073 — Optimize Only With Evidence

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- The author specifies the performance objective, workload, environment, and permitted trade-offs first.
- The author measures a representative baseline before adding caches, concurrency, or new data structures.
- The author uses a profile to find the dominant cost.
- The author checks that the optimization keeps correctness, security, and clarity.
- The author keeps an improvement easy to verify after the change.

## Limits

No output is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the engineering principles catalog](../README.md#p073)
