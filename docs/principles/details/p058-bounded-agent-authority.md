# P058 — Bounded Agent Authority

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- An agent gets only the resources needed for its task: repositories, files, tools, commands,
  destinations, credentials, actions, iterations, time, and cost.
- The trusted task and applicable policy give the grant. Confidence, data, and model output do not
  expand it.
- The objective, authorized targets, prohibited effects, acceptance criteria, and stop condition
  are recorded.
- Read-only, path-scoped, destination-scoped, and short-lived capabilities are preferred.
- Delegation depth, tool calls, retries, wall time, tokens, cost, and concurrent work are bounded.
- Proposed actions and parameters are checked at the tool boundary.
- Capabilities are revoked at task completion.
- A missing capability is reported, not worked around.

## Limits

No output is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the principles catalog](../README.md#p058)
