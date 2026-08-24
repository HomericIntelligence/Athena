# P023 — Parameterized / Table-Driven Testing

## Definition

Express one behavioral rule once and run it against multiple named cases containing inputs,
expected outcomes, and relevant context. This separates the invariant test procedure from the
examples used to exercise it.

**Aliases:** data-driven tests; test tables; parameterized tests; theories.

## Provenance

**Classification:** established principle.

Data-driven testing appeared in multiple early frameworks and language communities. The
slash-combined name reflects two common forms and has no single verified origin.

## Decision rule

When several cases differ primarily in data rather than setup or expected behavior, use one clear
test procedure with independently named cases.

## How to apply

- Give every case a diagnostic name describing its distinguishing condition.
- Store explicit expected results rather than recomputing them with production logic.
- Include representative normal, non-default, empty, missing, invalid, and boundary cases.
- Keep per-case setup and assertions small; split cases that express a different rule.
- Ensure mutable case data is isolated and a failure identifies the exact case.

## Boundaries and tensions

A large table can hide intent when cases require different workflows or many conditional fields.
Do not force integration scenarios into a common loop solely to remove lines. Parameterization
increases coverage of chosen examples but is not exhaustive and does not replace invariant-based or
boundary analysis.

## Examples

### Positive application

A parser test runs the same public operation for named cases covering a normal value, whitespace,
an empty input, malformed syntax, and the documented maximum length.

### Misuse or counterexample

A single table includes flags that choose different setup, invocation, and assertion branches. The
test loop becomes a second implementation that is harder to understand than separate tests.

### Athena or agent workflow

A validator helper uses named cases for valid frontmatter, a missing required field, an unknown
field, and malformed YAML while sharing one invocation and result-checking path.

## Related principles

- [P022 — Test Behavior, Not Implementation](p022-test-behavior-not-implementation.md)
- [P024 — Boundary-Value Testing](p024-boundary-value-testing.md)
- [P025 — Property-Based Testing for Invariants](p025-property-based-testing-for-invariants.md)

## References

### Origin and history

- [Go project, "TableDrivenTests"](https://go.dev/wiki/TableDrivenTests)
  records the established Go practice of separating reusable test logic from complete named cases.

### Current guidance

- [pytest, "How to parametrize fixtures and test functions"](https://docs.pytest.org/en/stable/how-to/parametrize.html)
  documents built-in parameter sets, generated cases, fixtures, and per-case marks.
- [JUnit User Guide, "Parameterized Classes and Tests"](https://docs.junit.org/current/writing-tests/parameterized-classes-and-tests.html)
  documents current parameter sources, argument conversion, and named invocations.

### Further reading

- [Microsoft, ".NET unit testing best practices"](https://learn.microsoft.com/en-us/dotnet/core/testing/unit-testing-best-practices)
  contrasts duplicated test logic with theory-style named input and expected-output cases.

[Back to the engineering principles catalog](../README.md#p023)
