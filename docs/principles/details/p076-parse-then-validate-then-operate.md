# P076 — Parse, Then Validate, Then Operate

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- The author changes boundary data into one specified internal structure.
- The author validates ranges, relationships, invariants, authority, and state preconditions before side effects.
- Core logic receives the validated structure and does not interpret the raw input again.
- The author normalizes only transformations with one specified meaning.
- The author keeps secrets and unnecessary raw input out of diagnostics.

## Limits

No output is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the engineering principles catalog](../README.md#p076)
