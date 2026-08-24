# P063 — Requirement-to-Code Traceability

## Definition

Every substantive code or artifact change should have a defensible path to a requirement,
acceptance criterion, defect, invariant, or necessary implementation dependency. Traceability makes
the reason for a change discoverable without requiring a heavyweight matrix for ordinary work.

**Aliases:** requirements traceability; change-to-requirement mapping; implementation provenance.

## Provenance

**Classification:** established principle.

Requirements traceability developed across systems and software engineering rather than from one
verified inventor. Formal standards often require bidirectional links among requirements, design,
code, and verification. Athena applies the same discipline proportionally to everyday changes.

## Decision rule

If a reviewer cannot explain why a substantive changed element is necessary for the accepted task
or a documented dependency of that task, remove it, split it into separately authorized work, or
record the missing requirement before proceeding.

## How to apply

- State the requirement and acceptance criteria before implementation.
- Keep each change focused enough that its issue, plan, or pull-request rationale is unambiguous.
- Map important design and code decisions to the requirement they satisfy.
- Identify supporting changes, such as migrations or compatibility work, as explicit dependencies.
- Update trace links when requirements or implementation ownership change.

## Boundaries and tensions

Traceability is about justified intent, not a comment or ticket ID on every line. Mechanical edits,
generated artifacts, and refactors can inherit the rationale of their coherent parent change.
Security and correctness work may be necessary even when an initial request omitted it; make that
dependency explicit rather than pretending it is unrelated. Traceability must not be used to freeze
a flawed implementation or bypass [P072 Technical Evidence](p072-technical-evidence-over-preference.md).

## Examples

**Positive:** A schema field, migration, compatibility reader, and removal trigger all point to the
same accepted data-transition requirement.

**Misuse:** A feature pull request includes an unrelated dependency upgrade and broad refactor with
no requirement explaining either change.

**Athena/agent workflow:** A plan gives every implementation step an acceptance criterion and omits
files or process artifacts that have no demonstrated product consumer.

## Related principles

- [P010 Scope Fidelity](p010-scope-fidelity.md)
- [P011 Minimal Coherent Change](p011-minimal-coherent-change.md)
- [P064 Requirement-to-Test Traceability](p064-requirement-to-test-traceability.md)
- [P072 Technical Evidence Over Preference](p072-technical-evidence-over-preference.md)

## References

### Origin/history

- [NASA SWE-064: Bidirectional Traceability Between Software Design and Software Code](https://swehb.nasa.gov/spaces/7150/pages/16450496/SWE-064%2B-%2BBidirectional%2BTraceability%2BBetween%2BSoftware%2BDesign%2Band%2BSoftware%2BCode)
  documents a mature requirements-engineering treatment of code traceability; no singular origin is
  claimed here.

### Current guidance

- [NASA SWE-050: Software Requirements](https://swehb.nasa.gov/spaces/SWEHBVD/pages/102695421/SWE-050%2B-%2BSoftware%2BRequirements)
  describes requirements characteristics and bidirectional lifecycle traceability in the current
  Software Engineering Handbook.
- [NIST SSDF 1.1](https://csrc.nist.gov/pubs/sp/800/218/final) connects secure design and code
  practices to documented security requirements and release evidence.

### Further reading

- [Google Engineering Practices: Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html)
  explains why one self-contained conceptual change is easier to understand and review.

[Back to the engineering principles catalog](../README.md#p063)
