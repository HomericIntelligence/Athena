# P062 — Human Approval for Irreversible or High-Risk Actions

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- Irreversible or high-risk effects are recognized before they happen: data loss, production
  changes, privilege changes, secret exposure, external communication, and high cost.
- When current authority does not include the action, action-bound human approval is usually
  sought first.
- The approver sees the specific action, target, and important parameters in clear terms.
- Approval binds to the target, scope, and material parameters. Changes call for a fresh
  approval.
- Approval pairs with technical safeguards. Approval alone does not make a risky action safe.
- Constructive, scoped work the user already authorized does not need a new prompt.
- Approval credentials and execution state are protected from substitution and replay.

## Limits

No output is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the principles catalog](../README.md#p062)
