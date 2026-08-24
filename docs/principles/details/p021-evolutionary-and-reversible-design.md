# P021 — Evolutionary and Reversible Design

## Definition

Change systems through incremental, behavior-preserving, migration-safe steps and retain a
practical way to roll back, roll forward, or coexist during transition. Prefer learning from small
changes over committing the system to one large rewrite.

**Aliases:** evolutionary design; incremental architecture; reversible change.

## Provenance

**Classification:** Athena synthesis.

This synthesis has established practitioner roots in evolutionary design, continuous delivery,
expand-and-contract migrations, and rollback practice across several communities. No single source
defines this exact combined principle.

## Decision rule

Choose the smallest sequence of independently verifiable changes that preserves service and gives
operators a tested recovery path until the new state is proven.

## How to apply

- Split work at compatibility boundaries while keeping every merged state usable.
- Separate preparation, activation, migration, and cleanup when their risks differ.
- Use additive schema changes, dual reads or writes, feature controls, or adapters when justified.
- Define rollback or roll-forward behavior before activating a risky change.
- Remove transitional machinery after evidence shows it has no remaining consumer.

## Boundaries and tensions

Reversibility has a cost and is not absolute. Legal notifications, leaked secrets, consumed
resources, and destructive migrations may be impossible to undo. Identify such points explicitly
and move them late. Do not preserve indefinite compatibility or dual-write complexity for a cheap,
local change whose prior version can simply be restored.

## Examples

### Positive application

A schema change first adds a nullable column, then deploys compatible readers and writers,
backfills data with checkpoints, switches reads, and removes the old column only after validation.

### Misuse or counterexample

A team calls a flag-protected rewrite reversible even though enabling the flag irreversibly rewrites
all stored data into a format the old release cannot read.

### Athena or agent workflow

An agent makes a focused commit, runs the repository gate, and delays publishing or destructive
cleanup until the local artifact and exact targets are verified.

## Related principles

- [P020 — Executable Architecture](p020-executable-architecture.md)
- [P026 — Regression Before Repair](p026-regression-before-repair.md)
- [P027 — Deterministic and Hermetic Tests](p027-deterministic-and-hermetic-tests.md)

## References

### Origin and history

- [Fowler, "Original Strangler Fig Application" (2004)](https://martinfowler.com/bliki/OriginalStranglerFigApplication.html)
  describes gradual replacement around a legacy system instead of a single cutover rewrite.

### Current guidance

- [Google Engineering Practices, "Small CLs"](https://google.github.io/eng-practices/review/developer/small-cls.html)
  explains why self-contained changes are easier to review, validate, merge, and roll back.

### Further reading

- [Ford, Parsons, and Kua, *Building Evolutionary Architectures*, second-edition sample](https://www.thoughtworks.com/content/dam/thoughtworks/documents/books/bk_building_evolutionary_architectures_second_edition_free_chapter.pdf)
  frames evolutionary architecture as guided, incremental change across multiple dimensions.

[Back to the engineering principles catalog](../README.md#p021)
