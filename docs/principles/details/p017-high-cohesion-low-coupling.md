# P017 — High Cohesion, Low Coupling

## Definition

Place responsibilities and data that belong together in the same component, while minimizing the
number and strength of dependencies between components. Cohesion concerns internal relatedness;
coupling concerns interdependence across a boundary.

**Aliases:** strong cohesion and loose coupling; functional cohesion and weak coupling.

## Provenance

**Classification:** established design principle.

Stevens, Myers, and Constantine formalized coupling and cohesion in structured design in the
1970s. The compact maxim used here is later practitioner language rather than a quotation
attributable to one source.

## Decision rule

Group things that change for the same reason, and communicate across groups through the smallest
stable contract that preserves required behavior.

## How to apply

- Use change history and domain ownership, not directory aesthetics, to find cohesive boundaries.
- Keep invariants with the state they govern.
- Pass only the data or capability a collaborator needs; avoid shared mutable globals.
- Watch for changes that repeatedly cross many modules, dependency cycles, and wide interfaces.
- Measure coupling when useful, but confirm the result with semantic and domain understanding.

## Boundaries and tensions

Zero coupling is neither possible nor desirable in a working system. Event buses, generic data
maps, and duplicated state can hide rather than remove coupling. Maximizing cohesion can also make
a component too large if "related" is defined loosely. Prefer explicit, necessary dependencies
over implicit coordination and balance independence against transactional consistency.

## Examples

### Positive application

A pricing component owns discount rules and the inputs needed to evaluate them. Checkout depends
on its narrow quote contract, not its tables, cache, or rule-selection internals.

### Misuse or counterexample

Two services exchange a dozen events and share a database, but are described as loosely coupled
because they do not call each other synchronously.

### Athena or agent workflow

A skill-local helper performs one parsing job and exposes a stable CLI. The skill does not reach
into helper internals, and unrelated skills do not import its private implementation.

## Related principles

- [P016 — Separation of Concerns](p016-separation-of-concerns.md)
- [P018 — Information Hiding](p018-information-hiding.md)
- [P019 — Explicit Contracts](p019-explicit-contracts.md)

## References

### Origin and history

- [Stevens, Myers, and Constantine, "Structured Design" (1974)](https://doi.org/10.1147/sj.132.0115)
  introduced a systematic treatment of module coupling and cohesion.

### Current guidance

- [Microsoft Azure Architecture Center, "Design for evolution"](https://learn.microsoft.com/en-us/azure/architecture/guide/design-principles/design-for-evolution)
  connects high cohesion and loose coupling to independently changeable services.

### Further reading

- [SEI, "Modifiability Tactics" (2007)](https://www.sei.cmu.edu/documents/778/2007_005_001_14858.pdf)
  analyzes modifiability in terms of responsibility, coupling, cohesion, and change propagation.

[Back to the engineering principles catalog](../README.md#p017)
