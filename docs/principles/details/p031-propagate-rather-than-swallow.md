# P031 — Propagate Rather Than Swallow

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- A layer that cannot satisfy its postconditions propagates the failure with its cause.
- Success and failure stay distinct in return types, exceptions, result objects, exit codes, or protocol responses.
- Fallback values live in the contract as specified alternative outcomes.
- Translation keeps the causal chain and adds stable context that helps the caller.
- After an unrecovered failure, neither a success result nor a silent empty value appears.
- Security uncertainty points toward denial (see P035). Caller-visible results keep internal details out.

## Limits

No result is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the engineering principles catalog](../README.md#p031)
