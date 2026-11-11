# P032 — Handle Once; Preserve Causality

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- One boundary owns outcome policy for each failure. Other layers add context or telemetry, and each failure is recorded as one incident.
- Native cause links or structured wrappers carry the chain. A new message keeps its relation to the cause.
- Context that exists at one layer (an operation, an identifier, a dependency name) is added at that layer.
- Retry telemetry correlates with the last outcome; each try does not become a separate incident.
- Stack and cause fields live in structured telemetry with sensitive data removed.
- Translated errors carry both the stable public category and the internal cause.

## Limits

No result is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the engineering principles catalog](../README.md#p032)
