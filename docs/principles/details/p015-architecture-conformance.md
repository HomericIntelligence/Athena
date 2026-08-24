# P015 — Architecture Conformance

## Definition

**Architecture Conformance** means following a system's established boundaries, dependency
direction, layering, ownership, naming, data flow, and extension mechanisms. A local change should
integrate with the system rather than bypassing a boundary or creating a parallel architecture for
convenience.

## Provenance

**Classification:** established architectural practice expressed as an Athena decision rule.

Architecture conformance draws on modularity, architecture evaluation, and automated dependency
checking. Athena claims no single author for the phrase or this exact formulation.

## Decision rule

Place a change in the existing responsible component and use its intended contracts. Depart from
the architecture only when evidence demonstrates that the architecture itself must change and that
broader change is explicitly in scope.

## How to apply

- Identify authoritative architecture documentation and verify it against executable structure.
- Trace dependency direction, data ownership, runtime boundaries, and extension points.
- Follow nearby patterns when they still serve the same architectural purpose.
- Evaluate a proposed exception at system scale, including deployment and failure behavior.
- Mechanically enforce important boundaries with types, tests, static checks, or CI where valuable.

## Boundaries and tensions

Conformance is not blind consistency. Outdated architecture can and should evolve through an
explicit, evidence-backed decision, but a local task does not authorize that redesign by default.
Documentation that contradicts executable behavior requires investigation rather than automatic
obedience to either source. Repository and user instructions remain the governing authority.
[P071 Consistency Over Personal Preference](p071-consistency-over-personal-preference.md) yields to
[P072 Technical Evidence Over Preference](p072-technical-evidence-over-preference.md) when change is
justified.

## Examples

**Positive:** A new persistence operation is added behind the established repository boundary, and
domain code depends on its contract rather than the database client.

**Misuse:** A feature writes directly to a shared database from the presentation layer because the
proper application service needs a small extension.

**Athena/agent workflow:** A contribution edits canonical sources under `skills/` and updates host
metadata that consumes them, rather than creating a host-specific copy of a skill.

## Related principles

- [P005 Modularity](p005-modularity.md)
- [P012 Evidence Before Modification](p012-evidence-before-modification.md)
- [P016 Separation of Concerns](p016-separation-of-concerns.md)
- [P020 Executable Architecture](p020-executable-architecture.md)
- [P071 Consistency Over Personal Preference](p071-consistency-over-personal-preference.md)
- [P077 Separate Policy from Mechanism](p077-separate-policy-from-mechanism.md)

## References

### Origin/history

- [David Parnas: On the Criteria To Be Used in Decomposing Systems into Modules](https://doi.org/10.1145/361598.361623)
  supplies foundational reasoning for architectural boundaries and hidden design decisions.

### Current guidance

- [Software Engineering Institute: Software Architecture](https://www.sei.cmu.edu/software-architecture/)
  describes current methods for analyzing and sustaining architectures against quality goals.
- [Microsoft: Validate code with layer diagrams](https://learn.microsoft.com/en-us/visualstudio/modeling/validate-code-with-layer-diagrams?view=vs-2022)
  demonstrates automated enforcement of dependency constraints in builds.

### Further reading

- [ArchUnit User Guide](https://www.archunit.org/userguide/html/000_Index.html) documents a current
  architecture-testing tool and examples of executable layer and dependency rules.

[Back to the engineering principles catalog](../README.md#p015)
