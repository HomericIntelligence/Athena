# P014 — Preserve Unrequested Behavior

## Definition

**Preserve Unrequested Behavior** means retaining existing public APIs, schemas, file formats,
persistence, command behavior, ordering, security properties, side effects, and failure contracts
unless the accepted requirement explicitly changes them.

## Provenance

**Classification:** Athena synthesis grounded in compatibility practice.

The exact wording is Athena's. Backward-compatibility policies, semantic versioning, and regression
testing provide established foundations, but no single source defines the full principle for every
kind of software change.

## Decision rule

Treat externally observable behavior outside the requested change as an invariant. Alter it only
when the requirement, a mandatory security correction, or an approved compatibility plan provides
specific authority and migration handling.

## How to apply

- Inventory public and operational behavior touched by the change.
- Characterize existing behavior with tests when its contract is unclear.
- Preserve defaults, ordering, errors, formats, and side effects not named in the requirement.
- Provide compatibility or migration paths for intentionally changed contracts when required.
- Call out unavoidable collateral behavior changes instead of hiding them in implementation detail.

## Boundaries and tensions

This principle does not preserve vulnerabilities, data corruption, or behavior explicitly declared
unsupported. Repository policy and authorized requirements may demand a breaking change. It also
does not require reproducing private implementation details when observable behavior remains the
same. [P010 Scope Fidelity](p010-scope-fidelity.md) limits the change, while
[P021 Evolutionary and Reversible Design](p021-evolutionary-and-reversible-design.md) guides an
authorized transition.

## Examples

**Positive:** A parser fix accepts a newly required input while preserving existing serialized
output, error categories, and ordering for all other inputs.

**Misuse:** A documentation task silently changes a CLI default because the new value seems more
convenient.

**Athena/agent workflow:** Updating skill guidance preserves frontmatter triggers, capability
fallbacks, and host-neutral behavior unless the issue explicitly changes them.

## Related principles

- [P006 Principle of Least Astonishment](p006-principle-of-least-astonishment.md)
- [P010 Scope Fidelity](p010-scope-fidelity.md)
- [P011 Minimal Coherent Change](p011-minimal-coherent-change.md)
- [P021 Evolutionary and Reversible Design](p021-evolutionary-and-reversible-design.md)
- [P022 Test Behavior, Not Implementation](p022-test-behavior-not-implementation.md)
- [P066 Preserve Existing Work](p066-preserve-existing-work.md)

## References

### Origin/history

- [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html) formalizes compatibility effects
  for public APIs; it is a versioning standard, not the origin of Athena's broader rule.

### Current guidance

- [The Go 1 Compatibility Promise](https://go.dev/doc/go1compat) is a concrete language project's
  current policy for preserving behavior and documenting permitted exceptions.
- [Google Engineering Practices: What to look for in a code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html)
  requires reviewers to consider user effects, compatibility, and tests.

### Further reading

- [Martin Fowler: Is High Quality Software Worth the Cost?](https://martinfowler.com/articles/is-quality-worth-cost.html)
  discusses the long-term value of internal quality while distinguishing it from externally visible
  functionality.

[Back to the engineering principles catalog](../README.md#p014)
