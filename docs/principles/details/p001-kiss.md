# P001 — KISS

## Definition

**KISS** (commonly expanded as *Keep It Simple, Stupid*) is the rule that a solution should use
the least complexity needed to satisfy its demonstrated requirements. Indirection, abstraction,
configuration, concurrency, infrastructure, and process all carry costs and must earn their place.

## Provenance

**Classification:** practitioner heuristic.

The phrase is commonly associated with aircraft engineer Kelly Johnson, but a definitive
contemporaneous source for the exact wording and attribution is difficult to establish. The broader
idea long predates software. This page therefore treats KISS as a widely adopted heuristic rather
than attributing it to a single verified author.

## Decision rule

Choose the simplest design that is complete, correct, secure, and operable for the current
requirements. When proposing a more complex design, identify the concrete requirement or measured
constraint that the added mechanism satisfies.

## How to apply

- Start with the direct path from input to required outcome.
- Count concepts and operational responsibilities, not just lines of code.
- Prefer existing language and repository mechanisms over custom frameworks.
- Remove layers that merely relay data or policy without creating a useful boundary.
- Reassess simplicity after tests expose the real behavioral cases.

## Boundaries and tensions

Simple is not synonymous with short, familiar, or expedient. A compact implementation that hides
state, weakens validation, or shifts complexity to callers is not simpler as a system. KISS yields
to required compatibility, security, reliability, and explicit contracts. It works with
[P002 YAGNI](p002-yagni.md) and [P007 Subtraction Over Addition](p007-subtraction-over-addition.md),
but [P008 Understand Before Subtracting](p008-understand-before-subtracting.md) prevents careless
deletion.

## Examples

**Positive:** A command with two fixed modes uses a small explicit branch instead of a plug-in
framework whose only consumers are those modes.

**Misuse:** Removing validation and error context makes a function shorter while making every
caller reconstruct its failure semantics.

**Athena/agent workflow:** An agent proposes the narrow documentation edit and existing validation
commands that meet the task, without introducing a generator or new registry solely to manage the
edit.

## Related principles

- [P002 YAGNI](p002-yagni.md)
- [P007 Subtraction Over Addition](p007-subtraction-over-addition.md)
- [P011 Minimal Coherent Change](p011-minimal-coherent-change.md)
- [P074 Prefer Existing Mechanisms](p074-prefer-existing-mechanisms.md)
- [P090 Prefer Negative Code](p090-prefer-negative-code.md)

## References

### Origin/history

- No definitive contemporaneous source for the exact phrase or its Kelly Johnson attribution was
  established during this review; the attribution is therefore recorded as common but uncertain.
- [PEP 20 — The Zen of Python](https://peps.python.org/pep-0020/) is a primary language-design
  source for the closely related rule that simple is preferable to complex.

### Current guidance

- [Google Engineering Practices: What to look for in a code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html)
  directs reviewers to challenge unnecessary complexity and prefer understandable code.

### Further reading

- [Google Engineering Practices: Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html)
  explains how narrowly scoped changes improve review quality and reduce risk.

[Back to the engineering principles catalog](../README.md#p001)
