# P043 — Circuit Breakers

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- A circuit breaker watches calls to a dependency and opens after measured continuous failure.
- A recovery interval lets in a finite half-open probe set. A failed probe reopens the breaker. Enough successful probes close it.
- The breaker sits at the failure-prone dependency boundary, not around local business logic.
- Threshold, window, open time, and recovery criteria come from the dependency contract and measurements.
- The open state returns a clear failure or a specified fallback. Scope matches the failure domain.
- State transitions, rejected calls, and probe results are recorded.

## Limits

No result is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the engineering principles catalog](../README.md#p043)
