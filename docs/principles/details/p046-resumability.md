# P046 — Resumability

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- An interrupted long operation resumes from durable, checked checkpoints covering committed, uncommitted, and uncertain work.
- The checkpoint binds operation identity, input, owner, and schema version.
- Resumed steps are idempotent, or they are deduplicated or reconciled against authoritative state.
- Checkpoint integrity and compatibility are checked before the resume.
- Progress and failure are reported. Checkpoint retention and removal rules are recorded.
- Tests cover the operation before, during, and after each external effect.

## Limits

No result is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the engineering principles catalog](../README.md#p046)
