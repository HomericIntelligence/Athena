# P016 — Separation of Concerns

## Definition

Separate aspects of a system that serve different purposes or obey different policies so each can
be understood and changed without unnecessarily entangling the others. Typical concerns include
domain rules, persistence, transport, presentation, security policy, and orchestration.

**Aliases:** concern separation; separation of responsibilities.

## Provenance

**Classification:** established principle.

Edsger W. Dijkstra used the phrase "separation of concerns" in EWD447 (1974). Earlier
modular-design work addressed related ideas, so the broader practice does not have a single origin.

## Decision rule

When two responsibilities have different reasons, rates, or authorities for change, give them an
explicit boundary unless doing so would add more coordination cost than it removes.

## How to apply

- Identify the policies represented in a workflow before choosing files, layers, or services.
- Keep domain decisions independent from delivery mechanisms such as HTTP, CLI, or storage.
- Put cross-cutting concerns behind explicit facilities rather than scattering ad hoc handling.
- Test each concern through its contract and add integration tests where the boundaries meet.
- Revisit the split when a change repeatedly requires coordinated edits across the boundary.

## Boundaries and tensions

Separation is conceptual, not a demand for a service, class, or file per concern. A small cohesive
function can legitimately combine mechanics that always change together. Excessive separation can
create indirection, distributed state, and harder local reasoning. Balance this principle with
[P017](p017-high-cohesion-low-coupling.md) and preserve one owner for shared policy.

## Examples

### Positive application

An order module decides whether a refund is allowed. An adapter translates that decision into an
HTTP response, and a repository records it. The refund rule can be tested without a web server or
database.

### Misuse or counterexample

Splitting a ten-line validation operation across a policy object, coordinator, factory, and remote
service creates boundaries with no independent responsibility or change pattern.

### Athena or agent workflow

A review skill owns review policy, while a helper script owns deterministic parsing. The skill does
not embed a second parser, and the parser does not decide whether a finding is acceptable.

## Related principles

- [P017 — High Cohesion, Low Coupling](p017-high-cohesion-low-coupling.md)
- [P018 — Information Hiding](p018-information-hiding.md)
- [P019 — Explicit Contracts](p019-explicit-contracts.md)

## References

### Origin and history

- [Dijkstra, "On the role of scientific thought" (EWD447, 1974)](https://www.cs.utexas.edu/~EWD/transcriptions/EWD04xx/EWD447.html)
  explains separation of concerns as studying one aspect consistently without denying the others.

### Current guidance

- [Microsoft Azure Architecture Center, "Design for evolution"](https://learn.microsoft.com/en-us/azure/architecture/guide/design-principles/design-for-evolution)
  recommends separating cross-cutting concerns and designing cohesive, loosely coupled services.

### Further reading

- [Parnas, "On the Criteria To Be Used in Decomposing Systems into Modules" (1972)](https://doi.org/10.1145/361598.361623)
  gives a complementary account of decomposition around design decisions likely to change.

[Back to the engineering principles catalog](../README.md#p016)
