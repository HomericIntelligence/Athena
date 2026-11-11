# P050 — Least Privilege

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- Each actor gets only the resources and actions needed for the assigned task.
- Grants are narrow in identity, action, data, destination, and time.
- A narrower grant is preferred when it is sufficient for the task.
- Short-lived, task-scoped credentials are preferred over static shared credentials.
- Read, write, administration, approval, and delegation are separate capabilities.
- Grants expire or are removed when the task ends.
- Permissions are reviewed from time to time, including inherited and transitive access.

## Limits

No output is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the principles catalog](../README.md#p050)
