# P003 — DRY

## Definition

**DRY** (*Don't Repeat Yourself*) means that each authoritative piece of knowledge should have one
canonical representation. The target is duplicated rules, schemas, calculations, and policy—not
every repeated sequence of syntax.

## Provenance

**Classification:** established principle.

Andrew Hunt and David Thomas named and defined DRY in *The Pragmatic Programmer*. Their formulation
focuses on duplicated knowledge in a system, a distinction often lost when DRY is reduced to
eliminating similar-looking code.

## Decision rule

When two representations must change together to remain correct, identify one authority and derive,
reuse, or link the others from it. Do not unify code merely because its current text looks alike.

## How to apply

- Identify the fact or rule that would become inconsistent if edited in only one place.
- Assign one owner and make consumers depend on or derive from that authority.
- Prefer links and generated views over manually synchronized copies when consumers require them.
- Keep coincidentally similar logic separate until it represents the same stable concept.
- Test the canonical behavior rather than pinning every textual rendering.

## Boundaries and tensions

Some duplication improves local reasoning or keeps unrelated domains independent. Prematurely
centralizing it can create a misleading abstraction and tighter coupling. Apply
[P013 AHA](p013-avoid-hasty-abstractions.md) before extracting shared code and
[P005 Modularity](p005-modularity.md) before sharing mutable state. DRY does not require a registry
or generator when ordinary discovery answers the question and no product consumer needs the
artifact.

## Examples

**Positive:** A schema is canonical, while API documentation and validators are derived from it or
link to it instead of restating field constraints by hand.

**Misuse:** Two domain workflows happen to contain the same three steps, so they are forced into a
generic engine even though their policies and reasons to change differ.

**Athena/agent workflow:** The principles catalog owns IDs and definitions; skills link the relevant
entries and explain only how those principles affect their workflow.

## Related principles

- [P005 Modularity](p005-modularity.md)
- [P013 AHA](p013-avoid-hasty-abstractions.md)
- [P074 Prefer Existing Mechanisms](p074-prefer-existing-mechanisms.md)
- [P078 Single Source of Truth](p078-single-source-of-truth.md)
- [P084 Prefer Local Reasoning](p084-prefer-local-reasoning.md)

## References

### Origin/history

- [The Pragmatic Programmer DRY excerpt](https://media.pragprog.com/titles/tpp20/dry.pdf) provides
  the authors' definition and examples of duplicated knowledge.
- [The Pragmatic Programmer, 20th Anniversary Edition](https://pragprog.com/titles/tpp20/the-pragmatic-programmer-20th-anniversary-edition/)
  is the publisher's current book record.

### Current guidance

- [Google Engineering Practices: What to look for in a code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html)
  treats duplication as a maintainability concern while also requiring reviewers to assess design
  and complexity.

### Further reading

- [Sandi Metz: The Wrong Abstraction](https://sandimetz.com/blog/2016/1/20/the-wrong-abstraction)
  explains why removing duplication too early can be more costly than temporarily retaining it.

[Back to the engineering principles catalog](../README.md#p003)
