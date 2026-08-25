# P063 — Requirement-to-Code Traceability

## Definition

Each substantive code or artifact change must trace to a requirement, acceptance criterion, defect,
invariant, or necessary implementation dependency. A reviewer must be able to find the reason for
the change. Ordinary work does not require a large traceability matrix.

**Aliases:** requirements traceability, change-to-requirement map, implementation provenance.

## Provenance

**Classification:** established principle.

Requirements traceability developed across systems and software engineering. No verified inventor
owns the practice. Formal standards often require bidirectional links between requirements, design,
code, and verification. Athena applies the same discipline in proportion to risk.

## Decision rule

For each substantive change, identify its accepted requirement or documented dependency. If no link
exists, remove the change, separate the work, or record the absent requirement before implementation.

## How to apply

- State the requirement and acceptance criteria before implementation.
- Keep each change narrow so its issue, plan, or pull-request rationale is clear.
- Map important design and code decisions to their requirements.
- Identify migrations, compatibility work, and other support changes as explicit dependencies.
- Update trace links when requirements or implementation ownership change.

## Diagram

```mermaid
flowchart LR
    A["Accept requirement or defect"] --> B["Define acceptance criteria"]
    B --> C["Map design decision"]
    C --> D["Map code change"]
    D --> E{"Does the trace link contain all required data?"}
    E -- "No" --> F["Remove, separate, or justify change"]
    E -- "Yes" --> G["Submit focused change"]
```

## Language examples

The two examples associate the function with REQ-17 and implement the accepted REQ-17 rule.

```python
def normalize_email(value):
    """REQ-17: Return a lowercase email address without outer spaces."""
    normalized = value.strip().lower()
    return normalized
```

```rust
/// REQ-17: Return a lowercase email address without outer spaces.
fn normalize_email(value: &str) -> String {
    value.trim().to_lowercase()
}
```

## Boundaries and tensions

Traceability proves justified intent. It does not require a comment or ticket ID on every line.
Mechanical edits, generated artifacts, and refactors can inherit the rationale of one coherent
parent change. Security or correctness work can be necessary when the initial request omits it. In
that case, record the dependency. Do not use traceability to preserve a flawed implementation or to
bypass [P072 Technical Evidence](p072-technical-evidence-over-preference.md).

## Examples

**Positive:** A schema field, migration, compatibility reader, and removal trigger all reference the
same accepted data-transition requirement.

**Misuse:** A feature pull request includes an unrelated dependency update and broad refactor. No
requirement supports either change.

**Athena/agent workflow:** A plan assigns an acceptance criterion to each implementation step. It
omits files and process artifacts that have no demonstrated product consumer.

## Related principles

- [P010 Scope Fidelity](p010-scope-fidelity.md)
- [P011 Minimal Coherent Change](p011-minimal-coherent-change.md)
- [P064 Requirement-to-Test Traceability](p064-requirement-to-test-traceability.md)
- [P072 Technical Evidence Over Preference](p072-technical-evidence-over-preference.md)

## References

### Origin/history

- [NASA SWE-064: Bidirectional Traceability Between Software Design and Software Code](https://swehb.nasa.gov/spaces/7150/pages/16450496/SWE-064%2B-%2BBidirectional%2BTraceability%2BBetween%2BSoftware%2BDesign%2Band%2BSoftware%2BCode)
  documents a mature systems-engineering treatment of code traceability. This page does not claim a
  single origin.

### Current guidance

- [NASA SWE-050: Software Requirements](https://swehb.nasa.gov/spaces/SWEHBVD/pages/102695421/SWE-050%2B-%2BSoftware%2BRequirements)
  describes requirement properties and bidirectional lifecycle traceability in the current Software
  Engineering Handbook.
- [NIST SSDF 1.1](https://csrc.nist.gov/pubs/sp/800/218/final) links secure design and code practices
  to documented security requirements and release evidence.

### Further reading

- [Google Engineering Practices: Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html)
  explains why reviewers can more easily understand one self-contained conceptual change.

[Back to the engineering principles catalog](../README.md#p063)
