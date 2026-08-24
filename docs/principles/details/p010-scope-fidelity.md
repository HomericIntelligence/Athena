# P010 — Scope Fidelity

## Definition

**Scope Fidelity** means implementing the stated requirement and only the changes necessary to
satisfy it. Adjacent features, broad cleanup, dependency upgrades, redesign, and speculative
improvements remain outside the change unless separately authorized.

## Provenance

**Classification:** Athena synthesis.

The wording is Athena's. It combines established change-management, iterative-development, and
review practices. Athena claims no single historical origin for the rule.

## Decision rule

Every substantive changed artifact must trace to a requirement, acceptance criterion, defect,
invariant, or necessary implementation dependency. If it cannot, exclude it or obtain explicit
scope expansion.

## How to apply

- Restate the requested outcome, constraints, and acceptance criteria before editing.
- Distinguish required enabling work from merely convenient cleanup.
- Keep a visible mapping from changed behavior to task justification.
- Report discovered adjacent problems without silently solving them.
- Split independent work into a separate issue or change when practical.

## Boundaries and tensions

Scope fidelity does not mean making an incomplete patch. Required tests, documentation, migration,
security controls, and compatibility handling are part of a complete solution. Conversely,
labeling an unrelated refactor as a prerequisite does not make it necessary. Repository safety and
quality rules remain mandatory even when the prompt omits them. Use
[P011 Minimal Coherent Change](p011-minimal-coherent-change.md) to determine a complete boundary.

## Examples

**Positive:** A parser bug fix changes the parser, adds a regression test, and updates its public
behavior note without reformatting neighboring modules.

**Misuse:** While correcting one flag, a contributor renames the entire command family and upgrades
unrelated dependencies.

**Athena/agent workflow:** An agent records unrelated findings for follow-up and keeps the current
diff tied to the user's request and repository-required evidence.

## Related principles

- [P002 YAGNI](p002-yagni.md)
- [P011 Minimal Coherent Change](p011-minimal-coherent-change.md)
- [P012 Evidence Before Modification](p012-evidence-before-modification.md)
- [P014 Preserve Unrequested Behavior](p014-preserve-unrequested-behavior.md)
- [P063 Requirement-to-Code Traceability](p063-requirement-to-code-traceability.md)
- [P066 Preserve Existing Work](p066-preserve-existing-work.md)

## References

### Origin/history

- [Manifesto for Agile Software Development: Principles](https://agilemanifesto.org/principles.html)
  provides historical primary statements about early, continuous, and simple delivery; it does not
  use Athena's term “scope fidelity.”

### Current guidance

- [Athena development and delivery policy](../../policies/development.md) defines the repository's
  binding scope, artifact, and validation rules.
- [Google Engineering Practices: Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html)
  explains why one self-contained change should address one issue.

### Further reading

- [Google Engineering Practices: The standard of code review](https://google.github.io/eng-practices/review/reviewer/standard.html)
  frames review decisions around improving code health without demanding unrelated perfection.

[Back to the engineering principles catalog](../README.md#p010)
