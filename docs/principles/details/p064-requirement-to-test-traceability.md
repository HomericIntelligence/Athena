# P064 — Requirement-to-Test Traceability

## Definition

Each behavior change must have verification for its requirement, acceptance criterion, defect, or
invariant. Evidence can include a behavior test, property, integration check, type rule, static
analysis, build check, or another risk-appropriate method.

**Aliases:** requirements-to-verification traceability, test coverage traceability.

## Provenance

**Classification:** established principle.

Systems and safety engineering use bidirectional requirements-to-test traceability. No verified
inventor owns the practice. Athena uses "test" to include appropriate executable verification. The
evidence must exercise the changed behavior.

## Decision rule

For each behavior change, identify evidence that fails when the required behavior fails. Add absent
evidence, or justify a risk-appropriate alternative.

## How to apply

- Turn acceptance criteria and invariants into observable verification targets.
- Choose the lowest-cost test level that proves the contract.
- Add boundary integration tests when the risk requires them.
- Record the requirement for each non-obvious test or verification group.
- Check failure paths and boundaries as well as representative success cases.
- Update the requirement and its tests when the accepted contract changes.

## Diagram

```mermaid
flowchart LR
    A["Accept behavior requirement"] --> B["Define observable result"]
    B --> C["Select risk-appropriate check"]
    C --> D["Break behavior in a controlled test"]
    D --> E{"Check detects defect?"}
    E -- "No" --> F["Improve or replace check"]
    F --> D
    E -- "Yes" --> G["Record requirement link"]
```

## Language examples

The two examples link REQ-24 to a test that permits only one charge for duplicate requests.

```python
def test_req_24_duplicate_key_creates_one_charge():
    store = ChargeStore()
    charge(store, "key-1")
    charge(store, "key-1")
    assert store.count() == 1
```

```rust
#[test]
fn req_24_duplicate_key_creates_one_charge() {
    let mut store = ChargeStore::new();
    charge(&mut store, "key-1");
    charge(&mut store, "key-1");
    assert_eq!(store.count(), 1);
}
```

## Boundaries and tensions

Traceability is not line coverage or one test for each requirement sentence. It does not require a
manual matrix in every repository. Static checks can prove properties that they fully enforce.

User workflows can require end-to-end evidence. A test provides no useful evidence when a defect
cannot make the test fail. Resolve a stale requirement before you change its tests. Apply
[P067 No Test Cheating](p067-no-test-cheating.md).

## Examples

**Positive:** A requirement states that duplicate requests create one charge. Its integration test
repeats one idempotency key and verifies one stored effect.

**Misuse:** A pull request cites its total coverage percentage. No test exercises the new
authorization failure path.

**Athena/agent workflow:** A skill change maps its success and dependency-failure contracts to the
validator or behavior tests. It does not add brittle assertions for prose text.

## Related principles

- [P022 Test Behavior, Not Implementation](p022-test-behavior-not-implementation.md)
- [P026 Regression Before Repair](p026-regression-before-repair.md)
- [P028 Test Failure Paths](p028-test-failure-paths.md)
- [P063 Requirement-to-Code Traceability](p063-requirement-to-code-traceability.md)
- [P067 No Test Cheating](p067-no-test-cheating.md)

## References

### Origin/history

- [NASA SWE-072: Bidirectional Traceability Between Test Procedures and Requirements](https://swehb.nasa.gov/spaces/7150/pages/16449898/SWE-072%2B-%2BBidirectional%2BTraceability%2BBetween%2BSoftware%2BTest%2BProcedures%2Band%2BSoftware%2BRequirements)
  records the established requirements-to-test practice. This page does not claim it as the point
  of origin.

### Current guidance

- [NASA SWE-194: Delivery Requirements Verification](https://swehb.nasa.gov/spaces/SWEHBVD/pages/102695529/SWE-194%2B-%2BDelivery%2BRequirements%2BVerification)
  links delivery evidence and test results to individual requirements.
- [NIST SSDF 1.1](https://csrc.nist.gov/pubs/sp/800/218/final) defines pre-release verification
  practices for human-readable and executable code.

### Further reading

- [Google Engineering Practices: Tests in small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html#keep-related-test-code-in-the-same-cl)
  explains why behavior changes and their tests belong in the same change.

[Back to the engineering principles catalog](../README.md#p064)
