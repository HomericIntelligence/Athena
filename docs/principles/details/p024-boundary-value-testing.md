# P024 — Boundary-Value Testing

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- Tests exercise values less than, at, and more than each important limit.
- The suite includes zero, one, empty, full, minimum, maximum, overflow, and rejected states where the domain has them.
- Teams find edges from contracts, types, protocols, resource limits, and state transitions.
- Adjacent boundary combinations appear when evidence shows interactions.
- Rejection tests also check the returned behavior and the preserved state.
- Adjacency follows the domain. Wrapped or encoded domains change what sits next to an edge.

## Limits

No result is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the engineering principles catalog](../README.md#p024)
