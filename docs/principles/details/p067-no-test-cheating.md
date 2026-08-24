# P067 — No Test Cheating

## Definition

When an implementation violates the intended contract, fix the implementation rather than weakening
the evidence. Do not delete or skip a valid test, loosen its assertions, replace meaningful behavior
with broad mocks, mark a real failure as expected, or change expected values solely to obtain green
status.

**Aliases:** preserve test integrity; no greenwashing.

## Provenance

**Classification:** Athena synthesis.

The phrase is an Athena rule, not a principle with a verified single origin. It formalizes a basic
property of useful tests: they must be capable of rejecting broken behavior and must remain aligned
with the accepted contract.

## Decision rule

When a test fails, determine whether the implementation, test, environment, or requirement is wrong.
Change the test only when evidence shows that its contract, setup, or assertion is itself incorrect
or the accepted requirement has changed—never merely because the failure blocks delivery.

## How to apply

- Reproduce the failure and confirm what behavior the test observes.
- Compare the expectation with current requirements and public contracts.
- Fix product behavior when the implementation is wrong and retain the regression test.
- Repair flaky setup, invalid fixtures, or stale expectations with an explicit rationale.
- Keep mocks narrow enough that meaningful integration and failure behavior remain exercised.

## Boundaries and tensions

Tests are fallible and are not automatically authoritative. Legitimate contract changes require test
changes; obsolete or nondeterministic tests should be repaired, not preserved ceremonially. A
narrowly documented skip can be appropriate for an unsupported environment when repository policy
allows it, but it is not evidence that the skipped behavior works. Requirement evidence under
[P072](p072-technical-evidence-over-preference.md) decides the contract.

## Examples

**Positive:** A regression test exposes a missing authorization check. The implementation is fixed,
and the test remains to fail if the vulnerability returns.

**Misuse:** A failing assertion is changed from an exact denied status to "any response" with no
requirement change, making the suite green while preserving the defect.

**Athena/agent workflow:** An agent investigates why a validator contract fails and corrects the
validator or a demonstrably wrong fixture; it does not pin different prose or delete the case to pass
`just test`.

## Related principles

- [P022 Test Behavior, Not Implementation](p022-test-behavior-not-implementation.md)
- [P026 Regression Before Repair](p026-regression-before-repair.md)
- [P064 Requirement-to-Test Traceability](p064-requirement-to-test-traceability.md)
- [P068 No Validation Bypass](p068-no-validation-bypass.md)
- [P072 Technical Evidence Over Preference](p072-technical-evidence-over-preference.md)

## References

### Origin/history

- [Google Engineering Practices: What to look for in tests](https://google.github.io/eng-practices/review/reviewer/looking-for.html#tests)
  expresses the established expectation that tests are valid, useful, and fail when code is broken;
  no single source is claimed for Athena's label.

### Current guidance

- [NIST SSDF 1.1](https://csrc.nist.gov/pubs/sp/800/218/final) treats code review, analysis, and
  executable testing as software verification controls before release.
- [Google Engineering Practices: Tests in small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html#keep-related-test-code-in-the-same-cl)
  requires logic changes to carry meaningful related tests and refactors to remain covered.

### Further reading

- [pytest documentation: How to use skip and xfail](https://docs.pytest.org/en/stable/how-to/skipping.html)
  documents legitimate, explicit uses and outcomes of non-running or expected-failure tests; these
  markers communicate a limitation rather than a pass.

[Back to the engineering principles catalog](../README.md#p067)
