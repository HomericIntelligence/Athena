# P011 — Minimal Coherent Change

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- One change has one purpose, stated in a sentence.
- All parts needed for that purpose are included: behavior, tests, docs, migration.
- Cleanup and refactors unrelated to the purpose go in a different change.
- Commits keep the tree working and are easy to review one by one.
- Minimal does not mean missing needed parts; a tiny patch that breaks migration is not minimal.
- The diff is reviewed for hunks that serve no purpose.

## Limits

No result is rejected because compliance cannot be shown.

[Back to the engineering principles catalog](../README.md#p011)
