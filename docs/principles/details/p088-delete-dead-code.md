# P088 — Delete Dead Code

## Definition

**Delete Dead Code** means removing unreachable, unused, superseded, commented-out, or obsolete
implementation after establishing that no required consumer or contract depends on it. Version
control preserves history; dormant alternatives increase maintenance cost and cognitive load.

**Aliases:** dead-code removal; obsolete-code cleanup.

## Provenance

**Classification:** practitioner heuristic.

No verified single origin exists for the rule. Compilers have long performed dead-code elimination,
while maintainers apply the broader practice to source that is technically reachable but no longer
serves a product purpose. Athena's wording adds an evidence requirement before deletion.

## Decision rule

When code has no supported runtime, build, test, migration, compatibility, or documentation
consumer, remove it and verify the affected behavior instead of retaining it as speculative backup.

## How to apply

- Search direct and indirect call sites, entry points, registrations, and generated references.
- Check reflection, dynamic loading, feature flags, serialization, and external API compatibility.
- Inspect history and tests to understand why the code exists.
- Delete associated tests and documentation that only describe the obsolete behavior.
- Keep the removal focused and reviewable.
- Run the repository's relevant static, behavioral, packaging, and integration checks.

## Boundaries and tensions

No local reference does not prove that a public API or plug-in hook is unused. Deprecation and
migration may be required before removal. Historical rationale that still constrains current code is
not dead merely because it is non-executable. Generated sources should normally be removed by
changing their canonical input, not by editing outputs independently. Scope fidelity still limits
unrelated cleanup.

## Examples

**Positive:** A retired command has no external compatibility obligation, so its handler,
registration, tests, and command-specific help are removed together and the package is rebuilt.

**Misuse:** A reviewer deletes an apparently unused callback without checking that a framework
loads it by name from configuration.

**Athena/agent workflow:** An agent verifies manifests, references, tests, and repository history
before removing an obsolete helper rather than treating a text-search miss as proof.

## Related principles

- [P007 Subtraction Over Addition](p007-subtraction-over-addition.md)
- [P008 Understand Before Subtracting](p008-understand-before-subtracting.md)
- [P014 Preserve Unrequested Behavior](p014-preserve-unrequested-behavior.md)
- [P065 Verify Before Claiming Completion](p065-verify-before-claiming-completion.md)
- [P089 Delete Obsolete Configuration and Dependencies](p089-delete-obsolete-configuration-and-dependencies.md)

## References

### Origin/history

- No primary source establishing one coinage was found. The source-level rule is best treated as a
  maintenance heuristic related to, but broader than, compiler dead-code elimination.

### Current guidance

- [Google SRE: Operational Simplicity](https://sre.google/sre-book/simplicity/) recommends routinely
  removing dead code and ensuring that operational code has an essential purpose.
- [Google Engineering Practices: What to look for in a code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html)
  asks reviewers to examine existing comments and TODOs that a change may make obsolete.

### Further reading

- [Google Engineering Practices: Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html)
  explains why self-contained deletions and small changes are easier to review and roll back.

[Back to the engineering principles catalog](../README.md#p088)
