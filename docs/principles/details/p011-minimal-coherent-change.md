# P011 — Minimal Coherent Change

## Definition

A **Minimal Coherent Change** is the smallest self-contained change that completely satisfies one
purpose, including the tests, documentation, migration, and safety work required by that purpose.
Its parts belong together and unrelated work is excluded.

## Provenance

**Classification:** Athena synthesis.

The name is Athena's. It combines longstanding incremental-development and code-review guidance:
small changes are easier to understand, but a change must still be complete enough to evaluate and
operate safely.

## Decision rule

Choose the narrowest boundary that leaves the requested behavior correct and verifiable. Split work
when parts have independent purposes; keep parts together when separating them would create an
invalid, untestable, or misleading intermediate state.

## How to apply

- State the change's single conceptual purpose.
- Include all necessary behavior, tests, contract updates, and migration handling.
- Separate opportunistic cleanup, formatting, dependency updates, and unrelated refactors.
- Order commits so each is reviewable and preserves repository invariants when practical.
- Inspect the final diff for files or hunks that do not serve the stated purpose.

## Boundaries and tensions

Minimal does not mean fewest lines or an incomplete patch. A one-line schema change without its
migration and verification may be smaller but not coherent. Conversely, “while here” cleanup does
not become necessary merely because it touches the same file. [P010 Scope Fidelity](p010-scope-fidelity.md)
limits purpose; [P014 Preserve Unrequested Behavior](p014-preserve-unrequested-behavior.md) and
[P021 Evolutionary and Reversible Design](p021-evolutionary-and-reversible-design.md) constrain how
the change is delivered.

## Examples

**Positive:** A configuration rename includes compatible parsing, migration documentation, and
tests in one change while leaving unrelated configuration cleanup for later.

**Misuse:** A bug fix is split so the first commit deliberately breaks the build and the second
restores it, making neither commit independently reviewable.

**Athena/agent workflow:** An agent edits only the canonical skills and shared docs needed for one
issue, then runs the repository's existing validation without sweeping unrelated files into the
diff.

## Related principles

- [P001 KISS](p001-kiss.md)
- [P010 Scope Fidelity](p010-scope-fidelity.md)
- [P014 Preserve Unrequested Behavior](p014-preserve-unrequested-behavior.md)
- [P021 Evolutionary and Reversible Design](p021-evolutionary-and-reversible-design.md)
- [P063 Requirement-to-Code Traceability](p063-requirement-to-code-traceability.md)
- [P065 Verify Before Claiming Completion](p065-verify-before-claiming-completion.md)

## References

### Origin/history

- [Manifesto for Agile Software Development: Principles](https://agilemanifesto.org/principles.html)
  is a primary historical source for incremental delivery and simplicity; it does not define
  Athena's exact term.

### Current guidance

- [Google Engineering Practices: Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html)
  explains why a small, self-contained change should address one issue and include associated tests.
- [Athena development and delivery policy](../../policies/development.md) defines the repository's
  binding coherent-change and artifact requirements.

### Further reading

- [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/) provides a current
  convention for communicating the purpose and compatibility effect of a commit.

[Back to the engineering principles catalog](../README.md#p011)
