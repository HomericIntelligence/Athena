# P014 — Preserve Unrequested Behavior

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- Behavior the request does not touch is kept: APIs, formats, order, defaults, errors, side effects.
- When a contract is unclear, current behavior is recorded in tests before the change.
- Deliberate contract changes come with a migration or compatibility path.
- Behavior changes are reported, not hidden in implementation detail.
- Private implementation details that stay unobservable may change freely.
- Vulnerabilities and corrupting behavior are not protected by this goal.

## Limits

No result is rejected because compliance cannot be shown.

[Back to the engineering principles catalog](../README.md#p014)
