# P024 — Boundary-Value Testing

## Definition

Exercise values at and immediately around transitions, limits, and equivalence-partition edges
because defects commonly appear where behavior changes. Relevant cases include below, at, and
above a threshold as well as zero, one, empty, full, minimum, maximum, overflow, and invalid states.

**Aliases:** boundary value analysis; limit testing; edge testing.

## Provenance

**Classification:** established testing technique.

Boundary value analysis is long-standing in software-testing literature and certification
syllabi. Its precise first use is not reliably attributable to one author, so Athena makes no
origin claim.

## Decision rule

For every input partition or state transition with a meaningful edge, select cases on both sides
and at the edge, including representations that can overflow or become empty.

## How to apply

- Derive boundaries from contracts, types, protocols, resource limits, and state transitions.
- Test the last accepted, first rejected, and exact transition values where representable.
- Include combinations of adjacent boundaries when their interaction is plausible.
- Verify both returned behavior and state preservation on rejection.
- Use generated or combinatorial methods when the boundary space is too large for examples alone.

## Boundaries and tensions

Boundary tests are only as good as the partitions chosen. They do not replace representative
interior cases, semantic invariants, failure injection, or security abuse cases. Avoid blindly
testing `n - 1`, `n`, and `n + 1` when the domain is continuous, wrapped, encoded, or otherwise
requires a different notion of adjacency.

## Examples

### Positive application

For a batch limit of 100 items, tests cover 0, 1, 99, 100, and 101 items and verify that rejection
of 101 leaves no partial write.

### Misuse or counterexample

A test covers the maximum integer but ignores that the API limit is measured after UTF-8 encoding,
where character count and byte count diverge.

### Athena or agent workflow

A bounded-iteration workflow tests zero allowed iterations, one iteration, the configured maximum,
and an attempt beyond the maximum, including a clear terminal failure.

## Related principles

- [P023 — Parameterized / Table-Driven Testing](p023-parameterized-table-driven-testing.md)
- [P025 — Property-Based Testing for Invariants](p025-property-based-testing-for-invariants.md)
- [P028 — Test Failure Paths, Not Just Success Paths](p028-test-failure-paths.md)

## References

### Origin and history

- [NIST, "Fault Classes and Error Detection in Specification Based Testing" (1998)](https://www.nist.gov/publications/fault-classes-and-error-detection-specification-based-testing)
  examines how specification-derived conditions must be covered to expose particular fault classes.

### Current guidance

- [ISTQB Certified Tester Foundation Level Syllabus v4.0.1](https://istqb.org/wp-content/uploads/2024/11/ISTQB_CTFL_Syllabus_v4.0.1.pdf)
  defines two-value and three-value boundary value analysis around equivalence partitions.

### Further reading

- [NIST, "Software Fault Complexity and Implications for Software Testing"](https://www.nist.gov/publications/software-fault-complexity-and-implications-software-testing)
  provides empirical motivation for systematically covering interactions among a small number of
  conditions.

[Back to the engineering principles catalog](../README.md#p024)
