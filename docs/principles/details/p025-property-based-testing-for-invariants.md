# P025 — Property-Based Testing for Invariants

## Definition

Use properties that must hold across many input values. Generate many inputs and
reduce each failure to a small counterexample.

This method can help parsers, serializers, algorithms, transformations, protocols, and state
machines.

**Aliases:** generative property testing, QuickCheck-style testing.

## Provenance

**Classification:** established principle.

QuickCheck followed random tests and specification-based generators. The 2000 paper by Claessen and
Hughes gave the library pattern of generators, properties, and shrinking.

## Decision rule

When an invariant gives correctness rules for more inputs than example cases, encode the invariant.
Generate accepted and rejected inputs from the domain. Preserve reproducible failures.

## How to apply

- Give a property such as round-trip equivalence, order, conservation, or a state
  invariant.
- Make generators that represent the domain and include shapes with nested or constrained data.
- Give rejected combinations. Do not discard most generated inputs.
- Reduce each failure to a small counterexample. Add each counterexample that helps diagnosis to the
  regression suite.
- Record seeds and control external state so each failure is reproducible.

## Diagram

```mermaid
flowchart LR
    Property["Invariant"] --> Generator["Generate domain inputs"]
    Generator --> Evaluate["Verify property"]
    Evaluate --> Result{"Property holds?"}
    Result -->|Yes| Budget{"All budgeted cases have results?"}
    Budget -->|No| Generator
    Budget -->|Yes| Success["Complete run"]
    Result -->|No| Reduce["Reduce counterexample"]
    Reduce --> Preserve["Preserve reproducible case"]
```

## Language examples

The two examples generate integer sequences and verify the same reverse round-trip property.

Python:

```python
from hypothesis import given
from hypothesis import strategies as st

@given(st.lists(st.integers()))
def test_reverse_round_trip(value: list[int]) -> None:
    encoded = list(reversed(value))
    assert list(reversed(encoded)) == value
```

Rust:

```rust
use proptest::prelude::*;

proptest! {
    #[test]
    fn reverse_round_trip(value in proptest::collection::vec(any::<i32>(), 0..100)) {
        let encoded: Vec<_> = value.iter().rev().copied().collect();
        let decoded: Vec<_> = encoded.iter().rev().copied().collect();
        prop_assert_eq!(decoded, value);
    }
}
```

## Boundaries and tensions

High case volume cannot correct a weak property or biased generator. Use property tests with named
examples, boundary cases, proofs, fuzz tests, and integration tests.

Do not copy the implementation into the oracle. A finite run without failures does not verify a
property in an unbounded domain.

## Examples

### Positive application

A serializer property generates accepted domain values. It verifies that decode after encode returns
an equivalent value. Each failure has a small, reproducible counterexample.

### Misuse or counterexample

A sort property verifies only output length. An implementation can return copies of one element and
pass this weak property.

### Athena or agent workflow

A parser helper generates accepted frontmatter maps with different key orders. The property verifies
the same normalized contract without undeclared file or network access.

## Related principles

- [P022 — Test Behavior, Not Implementation](p022-test-behavior-not-implementation.md)
- [P024 — Boundary-Value Testing](p024-boundary-value-testing.md)
- [P027 — Deterministic and Hermetic Tests](p027-deterministic-and-hermetic-tests.md)

## References

### Source information

- [Claessen and Hughes, "QuickCheck: A Lightweight Tool for Random Testing of Haskell Programs" (2000)](https://doi.org/10.1145/351240.351266)
  gave the generator and property library design that many tools use.

### Applicable information

- [Hypothesis documentation, API reference](https://hypothesis.readthedocs.io/en/latest/reference/api.html)
  gives generation, targeted exploration, stateful invariants, and shrinking controls.

### More information

- [Google XLS, "Exhaustive QuickCheck and fuzz tests"](https://google.github.io/xls/dslx_reference/#quickcheck)
  shows the differences between property generation, exhaustive checks for small domains, and
  coverage-guided fuzz tests.

[Back to the engineering principles catalog](../README.md#p025)
