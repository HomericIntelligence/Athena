# P057 — Supply-Chain Integrity

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- Build inputs and dependencies have an identified source owner and a bounded version policy.
- Standard-library capabilities are preferred before a third-party component is added.
- Inputs come from trusted sources. Ownership, maintenance, license, and security posture are
  examined.
- Project lockfiles are kept. Digests, signatures, and provenance information are used where they
  are available.
- Provenance records show where each build input came from and where it went.
- Build systems are isolated, authenticated, and given limited credentials.
- Scans for known risks are used as signals, not as proof that a component is safe.
- Update, vulnerability-response, removal, and compromise-recovery paths are planned before
  adoption.

## Limits

No output is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the principles catalog](../README.md#p057)
