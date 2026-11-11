# P078 — Single Source of Truth

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- The author gives each authoritative mutable fact one declared owner and one write path.
- The author derives views, caches, and replicas from the authoritative representation.
- The author records freshness limits and reconciliation rules for asynchronous boundaries.
- The author uses an explicit operation to move authority, so two writers do not silently diverge.
- The author looks for differences when authors can change copies independently.

## Limits

No output is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the engineering principles catalog](../README.md#p078)
