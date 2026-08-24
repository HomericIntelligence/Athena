# P007 — Subtraction Over Addition

## Definition

**Subtraction Over Addition** means checking whether removing, consolidating, or reusing an existing
mechanism can solve a problem before adding code, state, dependencies, configuration, services, or
process.

## Provenance

**Classification:** Athena synthesis supported by empirical research and established simplicity
heuristics.

The wording is Athena's. Behavioral research published by Adams and colleagues found that people
systematically overlook beneficial subtractive changes, which supports making subtraction an
explicit design prompt. The research does not prove that subtraction is always the correct
engineering choice.

## Decision rule

Before adding a moving part, evaluate at least one behaviorally complete subtractive or reuse-based
alternative. Prefer it when required behavior, safety, clarity, and compatibility remain intact.

## How to apply

- State the outcome independently from the proposed new mechanism.
- Look for obsolete branches, redundant state, duplicate authorities, and existing capabilities.
- Compare lifecycle, failure, security, and operational costs—not just implementation effort.
- Verify consumers and contracts before removing anything.
- Delete associated tests or documentation only when their behavior is truly obsolete.

## Boundaries and tensions

Subtraction is a prompt, not a presumption of safety. It must not remove an implicit requirement,
compatibility guarantee, security control, observability, or recovery path. Apply
[P008 Understand Before Subtracting](p008-understand-before-subtracting.md) and
[P014 Preserve Unrequested Behavior](p014-preserve-unrequested-behavior.md) first. A necessary new
control may increase code while reducing system risk.

## Examples

**Positive:** A new option is avoided by deleting a redundant mode and using the repository's
existing configuration authority.

**Misuse:** A security check is removed because tests still pass, without examining the trust
boundary it protects.

**Athena/agent workflow:** Before adding a documentation generator, an agent checks whether the
runtime already packages the canonical docs tree and whether ordinary links satisfy discovery.

## Related principles

- [P001 KISS](p001-kiss.md)
- [P008 Understand Before Subtracting](p008-understand-before-subtracting.md)
- [P074 Prefer Existing Mechanisms](p074-prefer-existing-mechanisms.md)
- [P088 Delete Dead Code](p088-delete-dead-code.md)
- [P089 Delete Obsolete Configuration and Dependencies](p089-delete-obsolete-configuration-and-dependencies.md)
- [P090 Prefer Negative Code](p090-prefer-negative-code.md)

## References

### Origin/history

- [Adams et al.: People systematically overlook subtractive changes](https://www.nature.com/articles/s41586-021-03380-y)
  reports controlled studies of the human tendency to seek additive solutions.
- [PEP 20 — The Zen of Python](https://peps.python.org/pep-0020/) records a related preference for
  simple over complex designs.

### Current guidance

- [Google Engineering Practices: What to look for in a code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html)
  directs reviewers to assess complexity and whether code is more complex than necessary.

### Further reading

- [Google Engineering Practices: Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html)
  explains why smaller coherent changes are easier to understand, review, and roll back.

[Back to the engineering principles catalog](../README.md#p007)
