# P064 — Requirement-to-Test Traceability

## Definition

Every changed behavior should have verification that demonstrates the corresponding requirement,
acceptance criterion, defect, or invariant. The evidence may be a behavioral test, property,
integration check, type rule, static analysis, build check, or another risk-appropriate method.

**Aliases:** requirements-to-verification traceability; test coverage traceability.

## Provenance

**Classification:** established principle.

Bidirectional requirements-to-test traceability is established in systems and safety engineering;
no single inventor is claimed. Athena broadens "test" to appropriate executable verification while
preserving the requirement that evidence actually exercises the changed behavior.

## Decision rule

For each changed behavior, identify evidence that would fail or otherwise become unsatisfied if the
required behavior were broken. If no such evidence exists, add it or explicitly justify the
risk-appropriate alternative.

## How to apply

- Turn acceptance criteria and invariants into observable verification targets.
- Choose the lowest-cost test level that proves the contract, then add boundary integration where
  the risk requires it.
- Record which requirement each non-obvious test or verification group covers.
- Check failure paths and boundaries, not only representative success cases.
- Update both sides when a requirement legitimately changes.

## Boundaries and tensions

Traceability is not equivalent to line coverage, one test per requirement sentence, or a manually
maintained matrix for every repository. Static checks can be sufficient for properties they fully
enforce, while user workflows may require end-to-end evidence. A passing test is not evidence if it
cannot fail when the implementation is broken. Do not distort tests to preserve a stale contract;
resolve the requirement first and apply [P067 No Test Cheating](p067-no-test-cheating.md).

## Examples

**Positive:** A requirement that duplicate requests create one charge maps to an integration test
that repeats the same idempotency key and verifies a single persisted effect.

**Misuse:** A pull request cites overall coverage percentage but has no test that exercises its new
authorization failure path.

**Athena/agent workflow:** A skill change maps its success and dependency-failure contracts to the
existing validator or behavior tests, without adding brittle assertions over prose wording.

## Related principles

- [P022 Test Behavior, Not Implementation](p022-test-behavior-not-implementation.md)
- [P026 Regression Before Repair](p026-regression-before-repair.md)
- [P028 Test Failure Paths](p028-test-failure-paths.md)
- [P063 Requirement-to-Code Traceability](p063-requirement-to-code-traceability.md)
- [P067 No Test Cheating](p067-no-test-cheating.md)

## References

### Origin/history

- [NASA SWE-072: Bidirectional Traceability Between Test Procedures and Requirements](https://swehb.nasa.gov/spaces/7150/pages/16449898/SWE-072%2B-%2BBidirectional%2BTraceability%2BBetween%2BSoftware%2BTest%2BProcedures%2Band%2BSoftware%2BRequirements)
  records the established requirements-to-test practice; this page does not claim it as the point
  of origin.

### Current guidance

- [NASA SWE-194: Delivery Requirements Verification](https://swehb.nasa.gov/spaces/SWEHBVD/pages/102695529/SWE-194%2B-%2BDelivery%2BRequirements%2BVerification)
  connects delivery evidence and test results back to individual requirements.
- [NIST SSDF 1.1](https://csrc.nist.gov/pubs/sp/800/218/final) defines verification practices for
  human-readable and executable code before release.

### Further reading

- [Google Engineering Practices: Tests in small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html#keep-related-test-code-in-the-same-cl)
  explains why behavior changes and their related tests should normally travel together.

[Back to the engineering principles catalog](../README.md#p064)
