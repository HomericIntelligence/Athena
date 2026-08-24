# P091 — Test-Driven Development

## Definition

**Test-Driven Development** (TDD) is a short development loop in which the next observable behavior
is expressed as a failing automated test, the smallest production change makes the suite pass, and
the design is improved while all tests remain green. The cycle is commonly summarized as
Red–Green–Refactor.

**Aliases:** TDD; Red–Green–Refactor cycle.

## Provenance

**Classification:** established practice and Athena-retained methodology.

Kent Beck developed the modern TDD practice in the context of Extreme Programming in the late 1990s
and documented it in *Test-Driven Development: By Example* in 2002–2003. Athena retains TDD as a
workflow principle because its ordering creates rapid behavioral and design feedback.

## Decision rule

For a behavior change, work in the smallest meaningful Red–Green–Refactor cycle: observe the new
test fail for the intended reason, make it pass with a coherent implementation, then improve the
design without changing behavior.

## How to apply

- List the next required behaviors, including important failures and boundaries.
- Select one small behavior and write a test at the appropriate observable boundary.
- Run it and confirm the failure is expected and meaningful.
- Write only enough coherent production code to make all relevant tests pass.
- Refactor tests and production code while keeping the suite green.
- Repeat, then run the repository's broader required verification.

## Boundaries and tensions

TDD is a development loop, not the whole testing strategy. [P026 Regression Before
Repair](p026-regression-before-repair.md) is specifically about reproducing a defect; TDD applies to
incremental behavior development more broadly. P022–P028 govern test quality and scope, while TDD
governs work order. Generic verification also includes builds, types, linting, integration,
security, and operational checks. A pure behavior-preserving refactor begins from a green,
adequately characterized baseline; do not manufacture a failing test merely to claim a Red step.

## Examples

**Positive:** A parser's next boundary case is specified by a behavioral test that fails with the
old result, a narrow implementation makes it pass, and duplication is removed while the suite stays
green.

**Misuse:** Implementation is completed first, then a brittle test of private call order is added
and the work is labeled TDD.

**Athena/agent workflow:** For a requested behavior change, an agent records the failing test output,
implements the minimum coherent fix, reruns the focused suite, refactors under green, and then runs
the repository gate. For a pure refactor it first establishes and reports the green baseline.

## Related principles

- [P022 Test Behavior, Not Implementation](p022-test-behavior-not-implementation.md)
- [P026 Regression Before Repair](p026-regression-before-repair.md)
- [P027 Deterministic and Hermetic Tests](p027-deterministic-and-hermetic-tests.md)
- [P064 Requirement-to-Test Traceability](p064-requirement-to-test-traceability.md)
- [P065 Verify Before Claiming Completion](p065-verify-before-claiming-completion.md)
- [P067 No Test Cheating](p067-no-test-cheating.md)

## References

### Origin/history

- [Kent Beck, *Test-Driven Development: By Example*](https://ptgmedia.pearsoncmg.com/images/9780321146533/samplepages/0321146530.pdf)
  is the publisher's sample of the foundational book and states the Red–Green–Refactor rules.
- [Martin Fowler: Test Driven Development](https://martinfowler.com/bliki/TestDrivenDevelopment.html)
  records the practice's Extreme Programming history and explains its interface-design feedback.

### Current guidance

- [The GDS Way: Test-driven development](https://gds-way.digital.cabinet-office.gov.uk/standards/test-driven-development.html)
  gives current government engineering guidance for expected-failure, green implementation, and
  refactoring cycles, including cases where other feedback mechanisms are needed.

### Further reading

- [Agile Alliance: Testing in agile software development](https://agilealliance.org/agile-qa-testing-in-agile-software-development/)
  distinguishes TDD from acceptance-test-driven and behavior-driven practices while relating all of
  them to continuous quality.

[Back to the engineering principles catalog](../README.md#p091)
