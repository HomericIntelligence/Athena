# P069 — Independent Review for High-Risk Changes

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- High-risk changes benefit from a reviewer who did not author the change.
- The reviewer has experience in the affected domain, for example security, privacy,
  cryptography, concurrency, or infrastructure.
- The reviewer examines the specified change, its assumptions, and its evidence.
- The reviewer receives the requirements, the revision, the full diff, the tests, and the known
  limitations.
- The review depth matches the risk. Low-risk work uses lighter review.
- Material findings are recorded and resolved visibly.
- Automated analysis supports the review but does not replace domain judgment.
- A non-author who approves without analysis is not an independent review.

## Limits

No output is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the principles catalog](../README.md#p069)
