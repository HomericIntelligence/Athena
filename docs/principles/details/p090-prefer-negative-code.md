# P090 — Prefer Negative Code

## Definition

**Prefer Negative Code** means that when two implementations provide the same correct behavior,
prefer the one with less code, mutable state, configuration, dependency surface, and conceptual
machinery. The objective is fewer things that can be wrong, not fewer characters.

**Aliases:** negative code; subtractive implementation.

## Provenance

**Classification:** practitioner heuristic.

The term is popularly associated with Andy Hertzfeld's account of Bill Atkinson reporting
"-2000" lines after simplifying QuickDraw. That retrospective story is an anecdote about a poor
productivity metric, not empirical proof that deleting lines automatically improves software.
Athena uses the label for evidence-backed simplification.

## Decision rule

After establishing behavioral equivalence and required quality properties, choose the design with
the smaller total maintenance and operational surface. Count concepts and obligations, not raw
lines.

## How to apply

- Remove obsolete branches, intermediaries, state, and configuration.
- Derive data instead of synchronizing independent copies.
- Replace custom machinery with an appropriate existing mechanism.
- Consolidate observed common behavior without inventing a premature abstraction.
- Compare readability, performance, security, operability, and compatibility before and after.
- Protect simplification with behavioral tests and final-diff verification.

## Boundaries and tensions

Code golf, compressed expressions, and hidden conventions can reduce lines while increasing risk.
Generated code and declarative configuration make line counts especially misleading. A useful
abstraction can remove code yet add a harder concept; duplication may be safer than the wrong
abstraction. Required validation, diagnostics, compatibility, and explicit contracts must not be
cut merely to produce a negative line count.

## Examples

**Positive:** A data-driven transition table replaces repeated special-case branches while
preserving named states, validation, and error behavior.

**Misuse:** Several readable checks are compressed into a cryptic expression that is shorter but
harder to review and diagnose.

**Athena/agent workflow:** An agent removes a redundant document registry after confirming the
package already discovers the canonical documentation tree, retaining only the consumer-backed
check.

## Related principles

- [P001 KISS](p001-kiss.md)
- [P007 Subtraction Over Addition](p007-subtraction-over-addition.md)
- [P013 AHA](p013-avoid-hasty-abstractions.md)
- [P074 Prefer Existing Mechanisms](p074-prefer-existing-mechanisms.md)
- [P086 Readability Counts](p086-readability-counts.md)
- [P088 Delete Dead Code](p088-delete-dead-code.md)

## References

### Origin/history

- [Folklore.org: -2000 Lines Of Code](https://www.folklore.org/Negative_2000_Lines_Of_Code.html)
  is Andy Hertzfeld's retrospective account of the Bill Atkinson story; it is historical anecdote,
  not controlled evidence for a code-quality metric.

### Current guidance

- [Google SRE: Operational Simplicity](https://sre.google/sre-book/simplicity/) distinguishes
  essential from accidental complexity and recommends removing code that does not serve business
  goals.
- [Google SRE: Regaining Simplicity](https://sre.google/workbook/simplicity/) treats simplification
  as engineering work that reduces cognitive and operational load.

### Further reading

- [People systematically overlook subtractive changes](https://www.nature.com/articles/s41586-021-03380-y)
  reports experimental evidence for a general human bias toward additive solutions; it supports
  considering subtraction, not judging software by line count.

[Back to the engineering principles catalog](../README.md#p090)
