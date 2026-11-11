# P081 — Forward Progress With Safety

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- The author gives loops, waits, retries, queues, and multistep workflows a progress measure and a bound.
- The author uses different outcomes for terminal success, failure, cancellation, and paused states.
- The author keeps invariants at checkpoints and failure exits.
- The author monitors progress and records stagnation instead of resetting a watchdog without progress.
- The author records enough state to resume long work safely.

## Limits

No output is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the engineering principles catalog](../README.md#p081)
