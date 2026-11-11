# P061 — Separate Decision from High-Impact Execution

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- A high-impact action gets a reviewable proposal before it is executed.
- At execution time, the target, operation, parameters, identity, and revision are resolved again.
- Authorization and safeguards are checked against the current state, not only the planned state.
- Reversible work and validation finish before the high-impact step.
- State changes between the decision and the execution trigger a fresh check.
- The proposal binds to the resolved target and parameters, so the execution matches the decision.
- When an audit trail is applicable, the actor, basis, action, and result are recorded.

## Limits

No output is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the principles catalog](../README.md#p061)
