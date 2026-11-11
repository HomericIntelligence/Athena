# P010 — Scope Fidelity

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- Each change traces to the request, an acceptance criterion, or a needed dependency.
- Needed tests, docs, and migration work are part of the change.
- Unrelated cleanup, redesign, and upgrades are recorded for later, not folded in.
- Adjacent problems are reported, not silently fixed.
- Work with a different purpose can live in a different change.
- The smallest boundary that solves the problem is preferred.

## Limits

No result is rejected because compliance cannot be shown.

[Back to the engineering principles catalog](../README.md#p010)
