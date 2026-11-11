# P016 — Separation of Concerns

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- Concerns with different functions or change reasons live in different components.
- Domain rules stay free of delivery details such as HTTP, CLI, and storage.
- Each shared concern has one explicit owner.
- Each concern is exercised through its own contract.
- One service, class, or file per concern is not required; cohesive small units are fine.
- Too much separation adds indirection, so splits are made only when the coordination cost is worth it.

## Limits

No result is rejected because compliance cannot be shown.

[Back to the engineering principles catalog](../README.md#p016)
