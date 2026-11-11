# P077 — Separate Policy from Mechanism

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- The author puts decisions that can change in policy interfaces with a name.
- The author keeps mechanisms neutral; they execute the selected policy correctly.
- The author gives policy inputs, outputs, defaults, and failure behavior an explicit contract.
- The author supplies policy through a narrow interface instead of copies of policy branches.
- The author tests policy selection and mechanism correctness independently.

## Limits

No output is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the engineering principles catalog](../README.md#p077)
