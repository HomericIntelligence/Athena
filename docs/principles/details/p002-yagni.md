# P002 — YAGNI

## Definition

**YAGNI** (*You Aren't Going to Need It*, also rendered *You Ain't Gonna Need It*) says not to add
functionality, extension points, configuration, abstraction, or infrastructure until a concrete
requirement needs it. Implement today's verified need while leaving ordinary, evidence-backed
change possible.

## Provenance

**Classification:** established principle.

YAGNI emerged from Extreme Programming. Martin Fowler reports that the phrase arose in a
conversation between Kent Beck and Chet Hendrickson; the exact colloquial expansion varies. Its
meaning is better established than a single canonical spelling.

## Decision rule

If a proposed element serves only a hypothetical future case, omit it. Add the element when an
accepted requirement, observed repeated case, or measured constraint makes its value concrete.

## How to apply

- Separate current acceptance criteria from imagined future requests.
- Delete speculative flags, hooks, providers, compatibility paths, and configuration.
- Keep the current design easy to change through clear contracts and tests, not unused flexibility.
- Record a deferred idea only when it is useful planning information with an owner or trigger.
- Revisit the decision when evidence changes rather than predicting every future need.

## Boundaries and tensions

YAGNI does not excuse ignoring explicit nonfunctional requirements, known migrations, security
controls, or foreseeable protocol obligations already in scope. It discourages speculative
implementation, not prudent design. [P004 SOLID](p004-solid.md) and
[P005 Modularity](p005-modularity.md) may justify a boundary needed today; they do not justify an
unused framework. [P013 AHA](p013-avoid-hasty-abstractions.md) provides the corresponding rule for
abstraction timing.

## Examples

**Positive:** A service implements the one required authentication provider behind the existing
repository interface and defers a provider marketplace until another provider is approved.

**Misuse:** Refusing to parameterize a value that is already a stated deployment requirement is not
YAGNI; it leaves the requirement unmet.

**Athena/agent workflow:** A plan names only artifacts with demonstrated product consumers and does
not add a changelog, generator, registry, or compatibility layer to anticipate unknown requests.

## Related principles

- [P001 KISS](p001-kiss.md)
- [P010 Scope Fidelity](p010-scope-fidelity.md)
- [P013 AHA](p013-avoid-hasty-abstractions.md)
- [P073 Optimize Only With Evidence](p073-optimize-only-with-evidence.md)

## References

### Origin/history

- [Martin Fowler: Yagni](https://martinfowler.com/bliki/Yagni.html) traces the term to Extreme
  Programming and explains its economic rationale.
- [Extreme Programming Explained, second edition](https://www.pearson.com/en-us/subject-catalog/p/extreme-programming-explained-embrace-change/P200000000118/9780321278654)
  is the publisher's record for Kent Beck and Cynthia Andres's foundational Extreme Programming
  text.

### Current guidance

- [Google Engineering Practices: What to look for in a code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html)
  advises reviewers to reject functionality that is not currently needed.

### Further reading

- [Martin Fowler: Design Stamina Hypothesis](https://martinfowler.com/bliki/DesignStaminaHypothesis.html)
  discusses when design effort begins to repay its cost without requiring speculative features.

[Back to the engineering principles catalog](../README.md#p002)
