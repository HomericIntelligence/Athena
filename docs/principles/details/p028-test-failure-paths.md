# P028 — Test Failure Paths, Not Just Success Paths

## Definition

Verify how a system behaves when inputs are malformed or dependencies and operations fail. Cover
realistic cancellation, timeout, partial progress, unavailability, retry, cleanup, authorization,
and resource-exhaustion conditions in addition to successful outcomes.

**Aliases:** negative testing; robustness testing; error-path testing.

## Provenance

**Classification:** established principle.

Negative and robustness testing have many roots in reliability, security, and protocol testing.
No single origin supports the full modern set of failure conditions in this principle.

## Decision rule

For every material dependency or state transition, identify plausible failures and verify the
documented result, preserved invariants, cleanup, and diagnostic evidence.

## How to apply

- Derive failures from the contract and architecture rather than chasing coverage percentage.
- Inject dependency errors, timeouts, cancellations, and partial completion deterministically.
- Assert caller-visible error semantics and the resulting durable state.
- Verify resources are released and retries or compensation stay within their budgets.
- Include authorization denial and malformed untrusted input without performing unsafe live acts.

## Boundaries and tensions

Do not trigger destructive production failures to prove a test. Use controlled substitutes,
sandboxes, fault injection, or staged environments proportionate to risk. Mocked failures can drift
from real dependency behavior, so pair them with contract or integration evidence. Avoid asserting
sensitive internal details in caller-visible errors.

## Examples

### Positive application

A file-replacement test injects a write failure after temporary output is complete and verifies the
old file remains valid, temporary resources are cleaned, and the error preserves its cause.

### Misuse or counterexample

A client has extensive success-path tests but none for a timeout after the server commits a write;
its automatic retry later duplicates the operation.

### Athena or agent workflow

A skill test simulates a missing required capability and verifies a clear safe-failure response
rather than silently skipping work or fabricating success evidence.

## Related principles

- [P022 — Test Behavior, Not Implementation](p022-test-behavior-not-implementation.md)
- [P027 — Deterministic and Hermetic Tests](p027-deterministic-and-hermetic-tests.md)
- [P030 — Handle Errors at the Nearest Responsible Boundary](p030-nearest-responsible-error-boundary.md)

## References

### Origin and history

- [NIST, "An Approach for Analyzing the Robustness of Windows NT Software" (1998)](https://csrc.nist.gov/files/pubs/conference/1998/10/08/proceedings-of-the-21st-nissc-1998/final/docs/paperf8.pdf)
  describes robustness testing with valid and invalid inputs and exception conditions.

### Current guidance

- [Google Engineering Practices, "What to look for in a code review"](https://google.github.io/eng-practices/review/reviewer/looking-for.html)
  requires useful tests that actually fail when the covered behavior is broken.
- [OWASP Web Security Testing Guide, "Testing for Error Handling"](https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/08-Testing_for_Error_Handling/README)
  provides current security-oriented tests for improper error handling and stack disclosure.

### Further reading

- [OWASP, "Business Logic Security Cheat Sheet"](https://cheatsheetseries.owasp.org/cheatsheets/Business_Logic_Security_Cheat_Sheet.html)
  adds adversarial cases for invalid ordering, repeated steps, concurrency, and rule bypass.

[Back to the engineering principles catalog](../README.md#p028)
