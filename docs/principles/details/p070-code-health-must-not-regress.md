# P070 — Code Health Must Not Regress

## Definition

A change is not acceptable merely because its local output is correct. It must not unnecessarily
make the overall system harder to understand, maintain, test, operate, evolve, or secure. Prefer
incremental improvement over both gradual degradation and demands for unattainable perfection.

**Aliases:** leave the codebase no worse; continuous code-health improvement.

## Provenance

**Classification:** practitioner rule.

The exact formulation is closely aligned with Google's published code-review standard. Related
"leave it better" heuristics are widespread, but no exclusive historical origin is asserted.

## Decision rule

Accept an imperfect change when it makes required progress without a material net regression in
code health. Reject or revise shortcuts whose avoidable maintenance, complexity, testing,
operability, or security cost exceeds their scoped benefit.

## How to apply

- Evaluate design, complexity, tests, naming, documentation, operation, and security in context.
- Prevent small local compromises from accumulating into systemic decay.
- Distinguish blocking regressions from optional polish and label non-blocking suggestions clearly.
- Prefer small, coherent changes that are easy to review, revert, and improve further.
- Document accepted debt only when necessity, owner, risk, and follow-up trigger are concrete.

## Boundaries and tensions

This principle is not permission for unrelated cleanup, gold-plating, or blocking delivery until code
is perfect. [P010 Scope Fidelity](p010-scope-fidelity.md) still limits the change, and emergencies may
require an explicitly managed temporary compromise. Existing conventions do not justify extending a
known defect, but repository-wide remediation may belong in separate work.

## Examples

**Positive:** A small feature reuses the established interface, adds focused tests, and makes one
nearby name clearer without broad refactoring.

**Misuse:** A working shortcut duplicates security policy across a second location because updating
the canonical component would take longer.

**Athena/agent workflow:** A reviewer distinguishes a required finding that prevents contract drift
from a non-blocking preference, keeping the skill corpus maintainable without expanding the task.

## Related principles

- [P010 Scope Fidelity](p010-scope-fidelity.md)
- [P011 Minimal Coherent Change](p011-minimal-coherent-change.md)
- [P065 Verify Before Claiming Completion](p065-verify-before-claiming-completion.md)
- [P071 Consistency Over Personal Preference](p071-consistency-over-personal-preference.md)
- [P072 Technical Evidence Over Preference](p072-technical-evidence-over-preference.md)

## References

### Origin/history

- [Google Engineering Practices: The standard of code review](https://google.github.io/eng-practices/review/reviewer/standard.html)
  is the direct practitioner source for treating improving overall code health as review's primary
  purpose; broader antecedents are not assigned to one origin here.

### Current guidance

- [Google Engineering Practices: What to look for in a code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html)
  operationalizes code health across design, functionality, complexity, tests, naming, comments,
  style, and documentation.

### Further reading

- [Google Engineering Practices: Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html)
  explains how narrow changes improve review depth, design quality, rollback, and maintainability.

[Back to the engineering principles catalog](../README.md#p070)
