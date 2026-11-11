# P036 — Graceful Degradation

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- A noncritical capability can continue in reduced mode after a failure. The optional classification precedes the failure.
- The reduced mode stays correct and safe, stays visible to operators, and stays consistent with the specified contract.
- A reduced result says it is reduced. Skipped work stays marked as skipped work.
- Fallbacks stay small and bounded. Authorization, integrity, and validation stay in place.
- Failure tests exercise dependency failure and overload for the fallback path.
- Reclassifying a capability after failure to raise availability is the separate anti-pattern.

## Limits

No result is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the engineering principles catalog](../README.md#p036)
