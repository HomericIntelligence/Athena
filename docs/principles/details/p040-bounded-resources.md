# P040 — Bounded Resources

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- Resources with variable demand (queues, buffers, concurrency, recursion, memory, disk, agent iterations, tokens, tool calls) carry specified limits.
- Limits come from measurements and bound both item count and total item cost.
- Platform quotas, finite executors, and finite queues are used where available. A custom counter serves where they are not.
- Reserved capacity protects critical traffic. Rejection costs less than admitted work.
- Saturation, rejection rate, queue age, and time at the limit are monitored. Limits adjust with the workload.
- Tests exercise behavior at each important limit and beyond it.

## Limits

No result is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the engineering principles catalog](../README.md#p040)
