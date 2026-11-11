# P018 — Information Hiding

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- Consumers see a stable contract, not the representation behind it.
- Change points such as storage formats, vendors, and algorithms stay behind the boundary.
- Internal fields and dependency objects are not published as part of the API.
- The contract states the behavior consumers need: side effects, ownership, failure modes, consistency.
- Diagnostics can show safe facts; they do not expose mutable internals or sensitive data.
- Hiding is not secrecy for its own sake; it keeps options open when details change.

## Limits

No result is rejected because compliance cannot be shown.

[Back to the engineering principles catalog](../README.md#p018)
