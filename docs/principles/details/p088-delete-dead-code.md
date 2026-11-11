# P088 — Delete Dead Code

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- The author looks for code that has no consumer in runtime, build, test, migration, or documentation.
- The author examines call sites, registrations, reflection, feature flags, and history before removal.
- The author keeps the removal in one specified scope.
- The author removes the obsolete tests and documentation with the code.
- The author runs the applicable tests after the removal.

## Limits

No output is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the engineering principles catalog](../README.md#p088)
