# P074 — Prefer Existing Mechanisms

## Definition

Before creating a utility, abstraction, parser, serializer, retry framework, cache, synchronization
primitive, security mechanism, dependency, or service, determine whether the repository, language,
framework, platform, or standard library already supplies an appropriate mechanism.

**Aliases:** reuse before build; avoid reinventing the wheel.

## Provenance

**Classification:** practitioner heuristic.

Reuse of established components is a long-standing software practice with no verified single origin.
This formulation prioritizes local and standard mechanisms while still requiring a fitness and
security assessment rather than assuming that all reuse is beneficial.

## Decision rule

Adopt an existing mechanism when it satisfies the demonstrated contract, is supported in the target
environment, and has a lower total correctness, security, maintenance, and operational cost than a
new one. Build only the missing capability, not a competing framework by default.

## How to apply

- Search repository code, documentation, dependency manifests, and architecture decisions first.
- Check the language and framework standard facilities next.
- Compare semantics, failure behavior, maintenance, provenance, licensing, and migration cost.
- Extend the existing owner through its intended seam when the gap is small and coherent.
- Document why a new mechanism is necessary when available options do not meet the contract.

## Boundaries and tensions

Existing does not mean correct, secure, maintained, or suitable. Do not contort a mechanism beyond
its contract, depend on private internals, or retain a known vulnerability solely to avoid new code.
Adding a third-party dependency can enlarge supply-chain and attack surface, so a small local
implementation may sometimes be safer. Reuse must also preserve local reasoning and explicit
ownership.

## Examples

**Positive:** A command uses the standard library's mature URL parser and the repository's existing
error envelope instead of creating two slightly different replacements.

**Misuse:** A custom retry loop is added even though the repository client already owns bounded
retry, causing nested attempts and inconsistent backoff.

**Athena/agent workflow:** An author invokes a tested skill-local helper and its documented CLI rather
than embedding a second parser as a Markdown code block.

## Related principles

- [P003 DRY](p003-dry.md)
- [P013 AHA](p013-avoid-hasty-abstractions.md)
- [P057 Supply-Chain Integrity](p057-supply-chain-integrity.md)
- [P078 Single Source of Truth](p078-single-source-of-truth.md)
- [P084 Prefer Local Reasoning](p084-prefer-local-reasoning.md)

## References

### Origin/history

- [Python tutorial: Batteries included](https://docs.python.org/3/tutorial/stdlib.html#batteries-included)
  documents one influential language philosophy of shipping robust common mechanisms; no claim is
  made that it originated the broader reuse heuristic.

### Current guidance

- [Google Engineering Practices: What to look for in a code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html)
  asks whether a change belongs in the codebase or a library and whether it integrates with the
  existing system.
- [NIST SSDF 1.1](https://csrc.nist.gov/pubs/sp/800/218/final) requires organizations to manage and
  protect both internally developed and third-party software components.

### Further reading

- [Google Engineering Practices: Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html)
  explains why unused APIs and unrelated framework work should not accompany a focused change.

[Back to the engineering principles catalog](../README.md#p074)
