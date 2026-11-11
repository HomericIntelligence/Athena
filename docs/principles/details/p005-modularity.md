# P005 — Modularity

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- Behavior and data that share policy stay in one component.
- Each module has a small contract and hides its decisions that can change.
- A change in one module has few effects on unrelated modules.
- Dependency direction is clear, and unneeded boundary crossings are few.
- Module count is not a goal by itself.
- Small packages that share mutable state or call across every boundary are not modular in effect.

## Limits

No result is rejected because compliance cannot be shown.

[Back to the engineering principles catalog](../README.md#p005)
