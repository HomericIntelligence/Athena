# P029 — Generalize Error Policy; Preserve Specific Cause

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- A small stable taxonomy at the boundary lets callers pick a response: rejected input, unavailable, conflict.
- Vendor and transport failures are translated where the public contract lives.
- Each translation keeps the initial cause and safe structured context for diagnosis.
- Retry status and user messages stay separate from changeable exception text.
- Public results keep secrets and internal details out. Protected diagnostics keep what operators need.
- No single type appears for each event.

## Limits

No result is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the engineering principles catalog](../README.md#p029)
