# P051 — Complete Mediation

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- Each protected operation gets its own authorization decision.
- A login or a session check does not give permanent authority for later operations.
- Decisions bind the principal, the action, the target, and the current policy state.
- All paths to a resource use the same authorization check, including batch and recovery paths.
- Authorization is checked again when identity, role, tenancy, or ownership can change.
- Decision caches have a specified expiration and revocation policy.
- Resource-specific decisions stay with the resource, even when a central mechanism exists.

## Limits

No output is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the principles catalog](../README.md#p051)
