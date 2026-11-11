# P082 — Design for Cancellation

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- The author gives long or asynchronous work a cancellation contract: the signal, the propagation path, and the terminal result.
- The author checks cancellation at bounded, state-safe checkpoints.
- The author releases resources and joins child work, or records each child result, before returning.
- The author uses different results for cancellation, timeout, dependency failure, and completion.
- The author makes cleanup and compensation idempotent when signals can repeat.

## Limits

No output is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the engineering principles catalog](../README.md#p082)
