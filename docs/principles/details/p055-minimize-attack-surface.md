# P055 — Minimize Attack Surface

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- Only the capabilities needed for product behavior are exposed.
- Endpoints, listeners, tools, protocols, and dependencies that no consumer uses are removed
  or disabled.
- Accepted formats, methods, destinations, identities, and permissions are narrowed.
- Privileged management surfaces are isolated from standard product interfaces.
- Attack surface is measured by capability, not by source line count.
- Surface changes are recorded during design and review.
- Necessary compatibility is kept until evidence shows removal is safe.

## Limits

No output is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the principles catalog](../README.md#p055)
