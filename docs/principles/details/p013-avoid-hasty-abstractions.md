# P013 — AHA

## Definition

**AHA** (*Avoid Hasty Abstractions*) says to generalize only after concrete cases reveal a stable,
shared concept. Temporary duplication can be safer than committing unrelated behavior to the wrong
abstraction.

## Provenance

**Classification:** practitioner heuristic.

Kent C. Dodds popularized the name and credits Cher Scarlett with suggesting the AHA acronym. The
substantive warning builds on Sandi Metz's account of the “wrong abstraction” and earlier guidance
against premature generalization.

## Decision rule

Extract an abstraction when multiple real consumers share the same responsibility, contract, and
reason to change. If only surface syntax matches or future consumers are hypothetical, keep the
cases explicit.

## How to apply

- Tolerate a small amount of duplication while the domain boundary becomes clear.
- Compare why cases change, not merely how their current code looks.
- Name the shared invariant and intended owner before extracting it.
- Design the narrowest abstraction required by actual consumers.
- Undo a wrong abstraction before layering flags and exceptions onto it.

## Boundaries and tensions

AHA is not permission for indefinite copy-and-paste. When duplicated knowledge must remain
synchronized, [P003 DRY](p003-dry.md) calls for one authority. The amount of evidence needed should
match the cost of later change. Stable protocols and repository-mandated boundaries may justify an
abstraction before several in-repository implementations exist.

## Examples

**Positive:** Two validation paths remain separate until a third case reveals that they enforce the
same domain invariant, after which that invariant receives one owner.

**Misuse:** Similar-looking billing and access-control workflows are put behind one configurable
engine, then accumulate switches because their policies differ.

**Athena/agent workflow:** An agent links skills to one canonical principles catalog but keeps each
skill's workflow-specific application local instead of creating a universal generated template.

## Related principles

- [P002 YAGNI](p002-yagni.md)
- [P003 DRY](p003-dry.md)
- [P004 SOLID](p004-solid.md)
- [P009 General Mechanisms Over Special Cases](p009-general-mechanisms-over-special-cases.md)
- [P084 Prefer Local Reasoning](p084-prefer-local-reasoning.md)

## References

### Origin/history

- [Kent C. Dodds: AHA Programming](https://kentcdodds.com/blog/aha-programming) introduces and
  attributes the acronym while describing the timing of abstraction.
- [Sandi Metz: The Wrong Abstraction](https://sandimetz.com/blog/2016/1/20/the-wrong-abstraction)
  provides the influential earlier account of duplication becoming cheaper than a mistaken shared
  abstraction.

### Current guidance

- [Google Engineering Practices: What to look for in a code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html)
  asks reviewers to assess design, complexity, and over-engineering against current needs.

### Further reading

- [Martin Fowler: Yagni](https://martinfowler.com/bliki/Yagni.html) explains the related economic
  case against implementing speculative flexibility.

[Back to the engineering principles catalog](../README.md#p013)
