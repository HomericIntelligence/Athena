# P027 — Deterministic and Hermetic Tests

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- Each test declares or controls its inputs: time, random values, environment, files, networks, locale, order, and concurrency.
- Clocks, randomness, and external clients enter through injection.
- Tests use temporary resources with deterministic cleanup.
- Live services appear in dedicated integration or acceptance suites with controlled environments.
- Seeds and schedules are recorded, and order shuffling or parallel runs are routine.
- A fixed external service can give a deterministic yet nonhermetic test. Full isolation can also hide integration failures.

## Limits

No result is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the engineering principles catalog](../README.md#p027)
