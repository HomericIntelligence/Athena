# P008 — Understand Before Subtracting

## Definition

**Understand Before Subtracting** requires evidence about why an existing mechanism exists before
removing it. History, callers, tests, contracts, deployment behavior, and architectural purpose can
reveal requirements that are not visible at the apparent deletion site.

## Provenance

**Classification:** Athena synthesis.

No single historical source is claimed. The rule combines software archaeology, information
hiding, compatibility practice, and the caution commonly expressed by Chesterton's fence: do not
remove a boundary before understanding its purpose.

## Decision rule

Delete or consolidate only after identifying the mechanism's consumers, observable behavior,
ownership, and original or current purpose, then obtaining evidence that removal preserves every
still-required contract.

## How to apply

- Search all direct and indirect consumers, including generated, configured, and external use.
- Read tests and documentation as claims, then verify them against implementation and history.
- Inspect version history and issue context for compatibility or failure lessons.
- Identify security, migration, cleanup, and operational roles that happy-path calls may not show.
- Add or strengthen behavioral evidence before deletion when coverage is insufficient.

## Boundaries and tensions

Investigation should be proportional to risk; this rule does not demand exhaustive archaeology for
an isolated, proven-unused local. History is evidence, not an instruction that obsolete design must
remain. Once purpose and consumers are understood, [P007 Subtraction Over Addition](p007-subtraction-over-addition.md)
and [P088 Delete Dead Code](p088-delete-dead-code.md) favor safe removal. Repository and task
authority still determine whether deletion is in scope.

## Examples

**Positive:** Before deleting a compatibility parser, a maintainer checks callers, release notes,
fixtures, telemetry, and supported-version policy, then removes it only after the old format is no
longer accepted.

**Misuse:** A branch is deleted as unreachable because the current unit test never selects it,
although production configuration can.

**Athena/agent workflow:** An agent reads the package builder and archive tests before proposing a
new manifest or deleting documentation that appears unreferenced from one README.

## Related principles

- [P007 Subtraction Over Addition](p007-subtraction-over-addition.md)
- [P012 Evidence Before Modification](p012-evidence-before-modification.md)
- [P014 Preserve Unrequested Behavior](p014-preserve-unrequested-behavior.md)
- [P018 Information Hiding](p018-information-hiding.md)
- [P066 Preserve Existing Work](p066-preserve-existing-work.md)
- [P088 Delete Dead Code](p088-delete-dead-code.md)

## References

### Origin/history

- [David Parnas: On the Criteria To Be Used in Decomposing Systems into Modules](https://doi.org/10.1145/361598.361623)
  explains why apparently local implementation choices can hide decisions important to consumers.
  Athena does not claim that Parnas coined this rule.

### Current guidance

- [Google Engineering Practices: Navigating a CL in review](https://google.github.io/eng-practices/review/reviewer/navigate.html)
  recommends understanding the change in context, including related files and the broader system.
- [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html) documents why removal of public
  behavior can constitute an incompatible change.

### Further reading

- [Git documentation: git-log](https://git-scm.com/docs/git-log) describes the primary tool for
  inspecting change history and locating relevant context.

[Back to the engineering principles catalog](../README.md#p008)
