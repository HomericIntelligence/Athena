# P018 — Information Hiding

## Definition

Expose a stable contract while concealing implementation decisions that are likely to change.
Consumers should know what a component guarantees, not the representation, algorithm, dependency,
or operational detail used to provide it.

**Aliases:** encapsulation of design decisions; implementation hiding.

## Provenance

**Classification:** established principle.

David Parnas articulated information hiding as a module decomposition criterion in 1972.
Encapsulation is closely related, but language-level access control alone does not ensure that
volatile decisions are actually hidden.

## Decision rule

For every boundary, expose only what consumers need to rely on and keep volatile choices behind
that boundary.

## How to apply

- Identify likely change points such as storage formats, vendors, algorithms, and cache policy.
- Publish operations and semantic guarantees instead of internal fields or dependency objects.
- Keep private representations inaccessible through reflection, shared tables, or mutable aliases.
- Change implementations behind contract tests before changing a public contract.
- Document intentional escape hatches and their compatibility cost.

## Boundaries and tensions

Information hiding must not hide behavior that callers need for correctness, including side
effects, ownership, latency, failure modes, and consistency guarantees. It also does not justify a
speculative abstraction for every possible implementation. Observability may expose safe
diagnostic facts without exposing mutable internals or sensitive data.

## Examples

### Positive application

A repository exposes `save` and `load` semantics while owning its schema and migration details.
Callers do not construct its SQL or depend on table names.

### Misuse or counterexample

A wrapper marks fields private but returns its mutable internal collection directly. The syntax
suggests encapsulation while consumers still depend on and can corrupt the representation.

### Athena or agent workflow

A skill invokes a documented helper command and interprets its exit contract. It does not import
private helper modules or depend on incidental log wording.

## Related principles

- [P016 — Separation of Concerns](p016-separation-of-concerns.md)
- [P017 — High Cohesion, Low Coupling](p017-high-cohesion-low-coupling.md)
- [P019 — Explicit Contracts](p019-explicit-contracts.md)

## References

### Origin and history

- [Parnas, "On the Criteria To Be Used in Decomposing Systems into Modules" (1972)](https://doi.org/10.1145/361598.361623)
  argues for modules organized around hidden design decisions rather than processing steps.

### Current guidance

- [Oracle, "Strong Encapsulation in the JDK"](https://docs.oracle.com/en/java/javase/25/migrate/migrating-jdk-8-later-jdk-releases.html)
  documents a concrete platform boundary that protects unsupported internals from consumers.

### Further reading

- [SEI, "Software Architecture"](https://www.sei.cmu.edu/software-architecture/)
  describes architecture as explicit structural decisions and emphasizes conformance during
  evolution.

[Back to the engineering principles catalog](../README.md#p018)
