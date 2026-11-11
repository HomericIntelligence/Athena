# P079 — Explicit Ownership and Lifetimes

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- The author records the owner and the lifetime of each resource before acquisition.
- The author makes ownership transfer and cleanup clear in types, names, or interface contracts.
- The author connects child tasks to a parent scope when no durable owner accepts them.
- The author gives shutdown order and wait behavior for concurrent work.
- The author tests failure exits as well as the standard release path.

## Limits

No output is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the engineering principles catalog](../README.md#p079)
