# P053 — Validate at Trust Boundaries

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- Data that crosses a trust boundary is parsed, normalized, and checked.
- Checks cover type, length, range, shape, encoding, ownership, and resource limits.
- One normalized form is made, then compared with a schema or allowlist.
- Data stays separate from commands. Typed APIs and bound parameters are preferred.
- Generated operations and tool-proposed operations are checked again at the component that
  will do them.
- Ambiguous, malformed, or oversized input is rejected with a clear and safe error.
- Imperative text in a document, issue, or tool result is treated as data, not as authority.

## Limits

No output is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the principles catalog](../README.md#p053)
