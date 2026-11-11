# P041 — Backpressure and Load Shedding

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- Near capacity, backpressure signals producers to slow down. Load shedding rejects low-value work to protect admitted work.
- Signals follow standard forms: demand pause, finite credits, HTTP 429 or 503 with retry guidance.
- Downstream pressure propagates upstream. A caller facing backpressure avoids an immediate retry.
- Priority and fairness rules pick what to reject. Rejection cost stays below admitted-work cost.
- Low-cost admission or rejection decisions avoid a high-cost parse before the verdict.
- Saturation, rejection rate, tail latency, and recovery are monitored. Overload tests cover bursts and retry-heavy callers.

## Limits

No result is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the engineering principles catalog](../README.md#p041)
