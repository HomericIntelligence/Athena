# P013 — AHA (Avoid Hasty Abstractions)

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- Generalization waits until real cases show the same stable concept.
- Small duplication is preferred over a wrong abstraction.
- Cases are compared by why they change, not only by how they look.
- The shared invariant and its owner are named before extraction.
- The narrowest abstraction that serves known consumers is chosen.
- A wrong abstraction is removed rather than extended with more flags.
- Stable protocols may still justify an abstraction with few implementations.

## Limits

No result is rejected because compliance cannot be shown.

[Back to the engineering principles catalog](../README.md#p013)
