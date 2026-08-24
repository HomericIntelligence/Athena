# P009 — General Mechanisms Over Special Cases

## Definition

**General Mechanisms Over Special Cases** favors one coherent rule, algorithm, data model, or error
path that naturally covers observed cases instead of accumulating case-specific branches. A
general mechanism captures a real invariant; it is not speculative extensibility.

## Provenance

**Classification:** established practitioner heuristic.

The idea appears throughout mathematics, language design, and software engineering rather than
having one verified origin. PEP 20 provides a prominent software formulation: special cases should
not defeat otherwise sound rules.

## Decision rule

When multiple cases share the same demonstrated rule, encode that rule once and treat variation as
data or a contract. Retain a special case when it reflects a genuinely different requirement.

## How to apply

- Write down the invariant shared by the cases before choosing an abstraction.
- Separate essential policy differences from incidental input differences.
- Prefer a table, normalized representation, or stable protocol to scattered branches.
- Exercise normal, boundary, and exceptional cases against the common rule.
- Keep explicit exceptions when collapsing them would obscure a distinct contract.

## Boundaries and tensions

Generalization has a carrying cost. Two examples may be coincidence rather than evidence of a
stable concept, so [P013 AHA](p013-avoid-hasty-abstractions.md) and [P002 YAGNI](p002-yagni.md)
constrain this principle. A clear explicit branch can be preferable to a universal engine with
hidden policy. General mechanisms must also preserve the specific causes of failures rather than
flattening useful diagnostics.

## Examples

**Positive:** Several command variants share one parser and validation pipeline, with their valid
options expressed as data.

**Misuse:** Unrelated deployment workflows are forced into a configurable state-machine framework
because both currently have three steps.

**Athena/agent workflow:** Review skills use one shared finding contract and add surface-specific
criteria, rather than implementing unrelated verdict formats for each review type.

## Related principles

- [P002 YAGNI](p002-yagni.md)
- [P003 DRY](p003-dry.md)
- [P013 AHA](p013-avoid-hasty-abstractions.md)
- [P029 Generalize Error Policy; Preserve Specific Cause](p029-generalize-error-policy-preserve-specific-cause.md)
- [P075 Make Invalid States Hard to Represent](p075-make-invalid-states-hard-to-represent.md)

## References

### Origin/history

- [PEP 20 — The Zen of Python](https://peps.python.org/pep-0020/) is a primary language-design
  statement balancing general rules, practicality, readability, and explicitness.

### Current guidance

- [Google Engineering Practices: What to look for in a code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html)
  asks reviewers to assess design, functionality, complexity, and whether code is over-engineered.

### Further reading

- [Sandi Metz: The Wrong Abstraction](https://sandimetz.com/blog/2016/1/20/the-wrong-abstraction)
  supplies the key counterpoint: a mistaken generalization can be harder to unwind than duplication.

[Back to the engineering principles catalog](../README.md#p009)
