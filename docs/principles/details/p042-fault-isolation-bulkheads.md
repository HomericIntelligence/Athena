# P042 — Fault Isolation / Bulkheads

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- Failure domains partition workloads, dependencies, tenants, and resource pools. A failure in one partition stays local to it.
- Partitions use distinct concurrency pools, queues, connection pools, quotas, processes, accounts, regions, or credentials where shared exhaustion can hurt objectives.
- Health, recovery, and critical traffic keep reserved capacity in each partition.
- The data plane stays isolated from control-plane failure. One tenant leaves capacity for the others.
- Partitions are monitored independently, with an aggregate view of system health.
- Exhaustion tests in one partition check that the others keep serving.
- A logical label without a real isolated pool is the separate anti-pattern.

## Limits

No result is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the engineering principles catalog](../README.md#p042)
