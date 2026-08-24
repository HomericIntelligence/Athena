# P025 — Property-Based Testing for Invariants

## Definition

Describe behavior as properties that must hold over a broad input domain, then generate many inputs
and reduce failures to small counterexamples. This is especially useful for parsers, serializers,
algorithms, transformations, protocols, and state machines.

**Aliases:** generative property testing; QuickCheck-style testing.

## Provenance

**Classification:** established testing technique.

Random testing and specification-based generation are older, but Claessen and Hughes's QuickCheck
paper (2000) established the modern library pattern of generators, properties, and shrinking.

## Decision rule

When correctness can be expressed more generally than a list of examples, encode the invariant and
generate valid and invalid inputs from the real domain while retaining reproducible failures.

## How to apply

- State a meaningful oracle: round-trip, equivalence, ordering, conservation, or state invariant.
- Build generators that represent the domain and deliberately cover difficult shapes.
- Constrain invalid combinations explicitly rather than discarding most generated inputs.
- Shrink and persist every discovered counterexample as a regression case when useful.
- Record seeds and control external state so failures can be reproduced.

## Boundaries and tensions

Generated volume cannot rescue a weak property or biased generator. Property tests complement
named examples, boundary cases, proofs, fuzzing, and integration tests; they do not replace them.
Avoid restating the implementation as the oracle, and do not treat a finite successful run as proof
over an unbounded domain.

## Examples

### Positive application

A serializer property generates valid domain values and checks that decoding an encoded value
returns an equivalent value. Any failure reports a minimized, reproducible counterexample.

### Misuse or counterexample

A sorting property asserts only that the output length equals the input length. An implementation
that returns repeated copies of one element passes despite losing data.

### Athena or agent workflow

A parser helper generates valid frontmatter mappings in varying key order and verifies that
parsing preserves the same normalized contract without reading undeclared files or network state.

## Related principles

- [P022 — Test Behavior, Not Implementation](p022-test-behavior-not-implementation.md)
- [P024 — Boundary-Value Testing](p024-boundary-value-testing.md)
- [P027 — Deterministic and Hermetic Tests](p027-deterministic-and-hermetic-tests.md)

## References

### Origin and history

- [Claessen and Hughes, "QuickCheck: A Lightweight Tool for Random Testing of Haskell Programs" (2000)](https://doi.org/10.1145/351240.351266)
  introduced the influential generator-and-property library design.

### Current guidance

- [Hypothesis documentation, API reference](https://hypothesis.readthedocs.io/en/latest/reference/api.html)
  documents current generation, targeted exploration, stateful invariants, and shrinking controls.

### Further reading

- [Google XLS, "Exhaustive QuickCheck and fuzz tests"](https://google.github.io/xls/dslx_reference/#quickcheck)
  contrasts property-based generation, exhaustive checks for small domains, and coverage-guided
  fuzzing.

[Back to the engineering principles catalog](../README.md#p025)
