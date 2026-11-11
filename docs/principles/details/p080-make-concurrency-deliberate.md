# P080 — Make Concurrency Deliberate

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- The author prefers sequential execution as the baseline.
- The author adds concurrency only for a measured latency, throughput, response, or isolation benefit.
- The author minimizes shared mutable state and prefers immutable messages or ownership transfer.
- The author sets limits for workers, queues, fan-out, and active work.
- The author propagates deadlines and cancellation through the task tree and gives one result for concurrent errors.

## Limits

No output is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the engineering principles catalog](../README.md#p080)
