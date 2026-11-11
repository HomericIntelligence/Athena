# P066 — Preserve Existing Work

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- Work from other tasks is not reverted, overwritten, reformatted, regenerated, or deleted.
- Before an edit or cleanup, the working-tree, index, branch, and worktree state is examined.
- Changes are attributed from the initial state, the task scope, and the current diff.
- Only in-scope paths are edited and staged.
- When concurrent changes could conflict, an isolated branch or worktree is used.
- Conflicts and unclear ownership are reported, not resolved by deletion.
- Careful edits to a file with other work are made only after that work is identified.

## Limits

No output is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the principles catalog](../README.md#p066)
