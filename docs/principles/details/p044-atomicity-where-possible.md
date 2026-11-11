# P044 — Atomicity Where Possible

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- One logical operation inside one supported transaction boundary commits all changes or no change.
- Isolation level or atomic publication is selected independently of the commit for visibility concerns.
- Transaction scope stays small. Network calls and user waits stay outside the transaction.
- Prerequisites validate before the transaction. Irreversible external effects follow reversible work.
- An unacknowledged commit resolves through a status query.
- Tests cover failures before commit, during commit, and after a lost commit acknowledgment.

## Limits

No result is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the engineering principles catalog](../README.md#p044)
