# P026 — Regression Before Repair

## Definition

When practical, reproduce a reported defect with a failing automated test before changing the
implementation. Confirm that the test fails for the reported reason, passes after the repair, and
remains in the suite to detect recurrence.

**Aliases:** bug-reproduction test; failing regression test; characterization before fix.

## Provenance

**Classification:** established practitioner technique.

Regression testing is older than automated unit-test frameworks, and test-first bug repair appears
throughout TDD and maintenance practice. This exact formulation has no uniquely verified origin.

## Decision rule

Before repairing a reproducible defect, capture its smallest supported behavioral manifestation in
a test that demonstrably fails against the unfixed revision.

## How to apply

- Reproduce the symptom in the closest reliable test layer.
- Run the new test before implementation work and inspect why it fails.
- Minimize the fixture without removing the condition that triggers the defect.
- Repair the root cause, then run the focused test and relevant surrounding suite.
- Keep the test named for behavior so it remains useful after implementation changes.

## Boundaries and tensions

"When practical" matters. Production containment, destructive failures, nondeterministic races,
and unavailable dependencies may require immediate safe mitigation or a model-based reproduction.
Do not write a test that merely duplicates the buggy implementation or pin an accidental symptom.
A passing test added after the fix is weaker evidence because its pre-fix sensitivity was not
observed.

## Examples

### Positive application

A parser crash report includes one malformed input. A focused public-API test first reproduces the
exception, then passes when the parser returns the documented structured error.

### Misuse or counterexample

A test is added after the code change and passes on both the repaired and original revisions. It
records an example but provides no evidence that it detects the regression.

### Athena or agent workflow

An agent records the focused failing command and output, makes the minimal repair, reruns that test,
then runs the repository-defined gate before claiming completion.

## Related principles

- [P021 — Evolutionary and Reversible Design](p021-evolutionary-and-reversible-design.md)
- [P022 — Test Behavior, Not Implementation](p022-test-behavior-not-implementation.md)
- [P027 — Deterministic and Hermetic Tests](p027-deterministic-and-hermetic-tests.md)
- [P091 — Test-Driven Development](p091-test-driven-development.md)

## References

### Origin and history

- [Beck, *Test-Driven Development: By Example* (2002)](https://www.pearson.com/en-us/subject-catalog/p/Beck-Test-Driven-Development-By-Example/P200000009421/9780321146533)
  established a widely used test-first cycle that also informs defect repair.

### Current guidance

- [Google Engineering Practices, "Small CLs"](https://google.github.io/eng-practices/review/developer/small-cls.html)
  recommends adding missing behavioral coverage before a refactor and keeping related tests with
  behavior changes.

### Further reading

- [Microsoft, ".NET unit testing best practices"](https://learn.microsoft.com/en-us/dotnet/core/testing/unit-testing-best-practices)
  explains regression protection and the characteristics of repeatable, self-checking tests.

[Back to the engineering principles catalog](../README.md#p026)
