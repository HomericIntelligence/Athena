# P065 — Verify Before Claiming Completion

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- Before a completion claim, the change is examined and the repository's applicable checks are
  run.
- Reports give the exact commands, revision, environment, and results.
- Claims are limited to facts the evidence shows.
- Failures, skips, unavailable dependencies, and timeouts are reported accurately.
- Stale results are not cited as proof for a new revision.
- A check that did not run is reported as not run, not as a pass.
- Verification gaps are named, along with the command or environment that can close them.

## Limits

No output is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the principles catalog](../README.md#p065)
