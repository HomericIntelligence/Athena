# P084 — Prefer Local Reasoning

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- The author keeps each invariant near the code that enforces it.
- The author supplies important dependencies through explicit narrow interfaces.
- The author minimizes global state, hidden callbacks, reflection, and nonlocal effects.
- The author keeps state transitions clear and near the operations that start them.
- The author makes nonlocal invariants explicit and recorded.

## Limits

No output is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the engineering principles catalog](../README.md#p084)
