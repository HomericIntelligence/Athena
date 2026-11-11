# P047 — Observability Is Part of Correctness

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- Important operations emit correlated, non-sensitive signals: logs, metrics, and traces.
- Signals show the event, place, time, operation, and cause.
- Signals are selected from user outcomes and operational questions, not only from available
  data.
- Stable request, trace, or operation identifiers connect work across boundaries.
- Metrics show trends, traces show causal paths, and logs record discrete evidence.
- Operators can find an important failure and its cause in a reasonable time.
- Secrets and raw customer content do not go into telemetry.

## Limits

No output is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the principles catalog](../README.md#p047)
