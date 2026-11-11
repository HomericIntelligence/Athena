# P060 — Constrain Sub-Agents

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- Delegation keeps or narrows the parent's scope and authority.
- A child gets a specified, bounded partition of the task, with no more authority than the parent.
- The child gets the minimum necessary context, not full histories or secrets.
- The child gets narrower, short-lived capabilities, not the parent's credentials.
- The child gets only the tool subset the child task needs.
- Recursion, child count, concurrency, retries, time, tokens, and cost are bounded.
- The parent treats child output as untrusted input and checks it before acceptance.
- When the task ends, child access is revoked and descendant work is cancelled.
- Concurrent children have specified file or state ownership.

## Limits

No output is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the principles catalog](../README.md#p060)
