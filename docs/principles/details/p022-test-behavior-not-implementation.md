# P022 — Test Behavior, Not Implementation

## Definition

Assert the externally observable contract of the system under test rather than private methods,
incidental data structures, exact internal call sequences, or other replaceable mechanics. A
behavior-preserving refactor should normally leave behavioral tests unchanged.

**Aliases:** black-box-oriented testing; implementation-agnostic testing.

## Provenance

**Classification:** practitioner heuristic.

Consumer/provider contract testing is a related but distinct technique, not an alias for this
broader heuristic. Black-box testing predates modern unit-testing frameworks, while the specific
advice against implementation-coupled tests emerged from many testing communities. No single
origin for this formulation is established.

## Decision rule

Assert what a caller or user is entitled to observe; assert internal collaboration only when that
interaction is itself a required contract.

## How to apply

- Name the scenario and expected outcome before selecting an assertion.
- Exercise a public or supported boundary at the narrowest useful level.
- Observe return values, durable state, emitted events, or specified side effects.
- Use fakes or stubs to control dependencies without specifying irrelevant call sequences.
- Retain structural tests only for real constraints such as dependency direction or security.

## Boundaries and tensions

"Behavior" is relative to the consumer. Calls to an audit sink, a transaction boundary, or an
idempotency key may be observable obligations even if an end user cannot see them directly.
Black-box system tests alone can be slow and imprecise, so combine levels rather than avoiding unit
tests. Do not weaken exact output assertions when the format itself is the contract.

## Examples

### Positive application

A sorting test supplies records and asserts documented ordering and stability. It does not inspect
which sorting algorithm or temporary collection produced the result.

### Misuse or counterexample

A test mocks every collaborator and requires an exact sequence of private calls, then fails when a
refactor combines two internal steps without changing any supported behavior.

### Athena or agent workflow

A helper test asserts exit status, structured output, and filesystem effects. It does not pin log
sentences or the names of private parsing functions.

## Related principles

- [P023 — Parameterized / Table-Driven Testing](p023-parameterized-table-driven-testing.md)
- [P026 — Regression Before Repair](p026-regression-before-repair.md)
- [P027 — Deterministic and Hermetic Tests](p027-deterministic-and-hermetic-tests.md)

## References

### Origin and history

- [Fowler, "Mocks Aren't Stubs" (2007)](https://martinfowler.com/articles/mocksArentStubs.html)
  analyzes state and interaction verification and the refactoring cost of implementation-coupled
  expectations.

### Current guidance

- [Microsoft, ".NET unit testing best practices"](https://learn.microsoft.com/en-us/dotnet/core/testing/unit-testing-best-practices)
  recommends testing public behavior, keeping tests resilient, and treating private methods as
  implementation details.
- [Testing Library, "Guiding Principles"](https://testing-library.com/docs/guiding-principles/)
  grounds UI tests in how software is actually used rather than component internals.

### Further reading

- [Google Engineering Practices, "What to look for in a code review"](https://google.github.io/eng-practices/review/reviewer/looking-for.html)
  asks reviewers to confirm that tests fail for broken code and remain simple and useful.

[Back to the engineering principles catalog](../README.md#p022)
