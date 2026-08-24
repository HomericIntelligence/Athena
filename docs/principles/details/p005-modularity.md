# P005 — Modularity

## Definition

**Modularity** organizes a system into cohesive components with explicit interfaces and limited
dependencies. A change inside one module should have minimal, intentional effects on unrelated
modules.

## Provenance

**Classification:** established principle.

Modular design predates modern software engineering. David Parnas's 1972 paper supplied a durable
software-specific foundation: module boundaries should hide design decisions likely to change,
rather than merely follow processing steps.

## Decision rule

Create or preserve a module boundary when it gives a coherent responsibility a clear owner, hides a
volatile decision, or contains change and failure. Do not split a system merely to increase its
module count.

## How to apply

- Group behavior and data that share policy and reasons to change.
- Expose a small contract and keep implementation choices private.
- Make dependency direction explicit and detect unwanted boundary crossings.
- Keep deployment, failure, and ownership boundaries aligned where the product needs independence.
- Test both module behavior and the contracts between modules.

## Boundaries and tensions

Physical separation alone is not modularity. Tiny packages with pervasive cross-calls, shared
mutable state, or cyclic dependencies can be less modular than a cohesive single component.
Distributed services add operational boundaries and should not be introduced solely to obtain code
organization. Balance [P003 DRY](p003-dry.md) against local ownership, and use
[P012 Evidence Before Modification](p012-evidence-before-modification.md) before moving established
boundaries.

## Examples

**Positive:** Parsing owns external syntax and returns a stable internal value, while business
policy depends on that value rather than parser internals.

**Misuse:** A small application is divided into services that must deploy together and share one
database, adding network failure without independent ownership or evolution.

**Athena/agent workflow:** Canonical skills remain in `skills/`; host manifests point to them rather
than maintaining host-specific copies that can diverge.

## Related principles

- [P004 SOLID](p004-solid.md)
- [P015 Architecture Conformance](p015-architecture-conformance.md)
- [P016 Separation of Concerns](p016-separation-of-concerns.md)
- [P017 High Cohesion, Low Coupling](p017-high-cohesion-low-coupling.md)
- [P018 Information Hiding](p018-information-hiding.md)
- [P077 Separate Policy from Mechanism](p077-separate-policy-from-mechanism.md)

## References

### Origin/history

- [David Parnas: On the Criteria To Be Used in Decomposing Systems into Modules](https://doi.org/10.1145/361598.361623)
  is the foundational paper connecting modular boundaries to hidden design decisions.

### Current guidance

- [Microsoft: Architectural principles](https://learn.microsoft.com/en-us/dotnet/architecture/modern-web-apps-azure/architectural-principles)
  describes separation of concerns and encapsulation as current architecture practices.
- [SEI: Quality Attribute Workshops](https://www.sei.cmu.edu/library/quality-attribute-workshops/)
  provides a current method for connecting architectural choices to concrete quality requirements.

### Further reading

- [Liskov and Wing: A Behavioral Notion of Subtyping](https://doi.org/10.1145/197320.197383)
  is useful when a module contract supports substitutable implementations.

[Back to the engineering principles catalog](../README.md#p005)
