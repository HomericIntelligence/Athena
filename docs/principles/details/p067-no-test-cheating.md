# P067 — No Test Cheating

This principle is a goal for engineering work. It does not authorize or block an action.

## What it looks like

- When a test fails, the implementation, the test, the environment, and the requirement are
  examined before any change is made.
- The implementation is fixed when it violates its contract. The regression test stays.
- A test is changed only when evidence shows an error in the test contract or expectation, or the
  accepted requirement changed.
- Assertions are not loosened just to make a failing test pass.
- Tests are not deleted or skipped to hide a defect.
- Evidence decides whether the implementation or the test is wrong, not the delivery schedule.
- Mocks stay narrow and are used to exercise integration and failure behavior.

## Limits

No output is rejected because compliance cannot be shown. Credential and PII protection still applies.

[Back to the principles catalog](../README.md#p067)
