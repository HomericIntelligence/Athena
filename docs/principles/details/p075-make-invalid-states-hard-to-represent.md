# P075 — Make Invalid States Hard to Represent

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- The author represents exclusive states as variants, not correlated booleans or nullable fields.
- The author uses validated constructors that return a value that satisfies the invariant or a specified error.
- The author expresses units, identifiers, necessary fields, and legal transitions in types or schemas.
- The author keeps mutation behind operations that preserve invariants.
- The author keeps representations clear, easy to change, and compatible with necessary serialization contracts.

## Limits

No output is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the engineering principles catalog](../README.md#p075)
