# P022 — Test Behavior, Not Implementation

## Definition

Assert the observable contract of the tested system. Do not assert private methods, data structures,
or interactions that the contract does not make necessary.

If a refactor preserves system behavior, the system behavior tests usually do not change.

**Aliases:** black-box-oriented testing, implementation-agnostic testing.

## Provenance

**Classification:** practitioner heuristic.

Consumer and provider contract testing is a related but different method. It is not an alias for
this heuristic.

Black-box testing began before unit test frameworks. Many test communities did not recommend tests
of implementation details. No one source gives this formulation.

## Decision rule

Assert what a caller or user can observe in the contract. When an internal interaction is part of
the contract, assert that interaction.

## How to apply

- Before you select an assertion, give a name to the scenario and specified result.
- Exercise a public or approved boundary at the smallest applicable level.
- Observe return values, durable state, emitted events, or specified side effects.
- Use fakes or stubs to control dependencies.
- Do not put call sequences that do not change contract behavior in the test.
- Keep structural tests only for specified constraints, for example dependency direction or
  security.

## Diagram

```mermaid
flowchart LR
    Contract["Consumer contract"] --> Scenario["Give scenario"]
    Scenario --> Boundary["Exercise supported boundary"]
    Boundary --> Observe["Observe result or side effect"]
    Observe --> Assert["Assert necessary behavior"]
    Refactor["Replace internal mechanics"] --> Assert
```

## Language examples

The two tests assert stable order without inspection of the sort implementation.

Python:

```python
def order_records(records: list[tuple[str, int]]) -> list[tuple[str, int]]:
    return sorted(records, key=lambda record: record[1])

def test_order_is_stable() -> None:
    records = [("first", 2), ("second", 1), ("third", 2)]
    assert order_records(records) == [("second", 1), ("first", 2), ("third", 2)]
```

Rust:

```rust
fn order_records(records: &mut Vec<(&str, u32)>) {
    records.sort_by_key(|record| record.1);
}

#[test]
fn order_is_stable() {
    let mut records = vec![("first", 2), ("second", 1), ("third", 2)];
    order_records(&mut records);
    assert_eq!(records, vec![("second", 1), ("first", 2), ("third", 2)]);
}
```

## Boundaries and tensions

A consumer contract gives observable behavior. An audit event, transaction boundary, or idempotency key
can be an observable obligation. A user can observe the result without access to that obligation.

Black-box system tests can be slow and have low diagnostic precision. Use more than one test level.
When the output format is the contract, keep assertions for the full output.

## Examples

### Positive application

A sort test supplies records and asserts specified order and stability. The test does not use sort
algorithm details or the temporary collection.

### Misuse or counterexample

A test asserts a private call sequence that is not part of the contract. A safe refactor puts two
internal steps in one step, and the test fails.

### Athena or agent workflow

A helper test asserts exit status, structured output, and file effects. It does not use private
function names or log sentences that are not part of the contract.

## Related principles

- [P023 — Parameterized / Table-Driven Testing](p023-parameterized-table-driven-testing.md)
- [P026 — Regression Before Repair](p026-regression-before-repair.md)
- [P027 — Deterministic and Hermetic Tests](p027-deterministic-and-hermetic-tests.md)

## References

### Source information

- [Fowler, "Mocks Aren't Stubs" (2007)](https://martinfowler.com/articles/mocksArentStubs.html)
  gives an analysis of state verification, interaction verification, and refactor costs from coupled
  expectations.

### Applicable information

- [Microsoft, ".NET unit testing best practices"](https://learn.microsoft.com/en-us/dotnet/core/testing/unit-testing-best-practices)
  recommends tests that use public methods only.
- [Testing Library, "Guiding Principles"](https://testing-library.com/docs/guiding-principles/)
  recommends UI tests that follow software operation, not component internals.

### More information

- [Google Engineering Practices, "What to look for in a code review"](https://google.github.io/eng-practices/review/reviewer/looking-for.html)
  tells reviewers to make sure that tests detect broken behavior and stay simple.

[Back to the engineering principles catalog](../README.md#p022)
