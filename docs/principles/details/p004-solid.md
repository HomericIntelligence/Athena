# P004 — SOLID

## Definition

**SOLID** is a family of five object-oriented design principles: Single Responsibility,
Open/Closed, Liskov Substitution, Interface Segregation, and Dependency Inversion. Applied
judiciously, they keep responsibilities focused and dependencies aligned with stable behavioral
contracts. They are design lenses, not a requirement to introduce classes or interfaces.

## Provenance

**Classification:** established principle family.

Robert C. Martin assembled and published the five principles around 2000; the memorable SOLID
acronym is commonly credited to Michael Feathers. Open/Closed originated with Bertrand Meyer, and
Liskov Substitution has a formal basis in work by Barbara Liskov and Jeannette Wing.

## Decision rule

Use the applicable SOLID principle when it makes a demonstrated responsibility, variation point,
or substitution contract clearer. Do not add abstraction merely to make a design appear SOLID.

## The five principles

### Single Responsibility Principle (SRP)

A module or component should have one primary responsibility and one coherent reason to change.
Responsibility is about ownership of policy, not function count or physical file size.

### Open/Closed Principle (OCP)

A stable component should permit required variation through an intentional extension mechanism
without repeated modification of its core policy. It does not require predicting or abstracting
unknown variations.

### Liskov Substitution Principle (LSP)

A subtype or implementation must preserve the observable behavioral contract of the abstraction it
replaces, including valid inputs, promised outputs, invariants, and failure semantics.

### Interface Segregation Principle (ISP)

Clients should depend only on capabilities they actually use. Prefer cohesive, role-oriented
interfaces to broad interfaces that force consumers to accept irrelevant methods or permissions.

### Dependency Inversion Principle (DIP)

High-level policy should not depend directly on volatile low-level details; both should depend on a
stable contract owned at the appropriate boundary. Dependency injection is one technique, not the
principle itself.

## How to apply

- Identify real actors, policy owners, and reasons to change before splitting responsibilities.
- Introduce an extension seam only for an observed or required variation.
- Specify behavioral contracts before claiming implementations are substitutable.
- Give consumers the narrowest coherent capability surface.
- Direct dependencies toward stable policy while keeping wiring explicit.

## Boundaries and tensions

SOLID emerged from object-oriented design and must be translated carefully to functional,
data-oriented, or procedural systems. Excess interfaces, tiny classes, and dependency-injection
machinery can violate [P001 KISS](p001-kiss.md), [P002 YAGNI](p002-yagni.md), and
[P013 AHA](p013-avoid-hasty-abstractions.md). Existing architecture and repository contracts take
precedence over a stylistic reinterpretation of SOLID.

## Examples

**Positive:** Business policy depends on a narrow storage capability, while production and test
adapters both preserve the same error and transaction contract.

**Misuse:** Every function receives a one-method interface even though there is one stable
implementation and no required substitution, producing indirection without a design benefit.

**Athena/agent workflow:** A skill owns its workflow policy, delegates execution through an
explicit capability boundary, and documents the behavior expected when that capability is absent.

## Related principles

- [P005 Modularity](p005-modularity.md)
- [P013 AHA](p013-avoid-hasty-abstractions.md)
- [P016 Separation of Concerns](p016-separation-of-concerns.md)
- [P017 High Cohesion, Low Coupling](p017-high-cohesion-low-coupling.md)
- [P018 Information Hiding](p018-information-hiding.md)
- [P019 Explicit Contracts](p019-explicit-contracts.md)

## References

### Origin/history

- [Robert C. Martin: Design Principles and Design Patterns](https://objectmentor.com/resources/articles/Principles_and_Patterns.pdf)
  presents the five principles before the SOLID acronym became commonplace.
- [Bertrand Meyer: Object-Oriented Software Construction](https://bertrandmeyer.com/OOSC2/)
  is the author's page for the work that introduced the Open/Closed Principle.
- [Liskov and Wing: A Behavioral Notion of Subtyping](https://doi.org/10.1145/197320.197383)
  gives the formal behavioral foundation for substitution.

### Current guidance

- [Microsoft: Architectural principles](https://learn.microsoft.com/en-us/dotnet/architecture/modern-web-apps-azure/architectural-principles)
  applies separation of concerns, explicit dependencies, single responsibility, and dependency
  inversion in current application architecture guidance.

### Further reading

- [Bertrand Meyer: Applying Design by Contract](https://www.kth.se/social/files/59526bfb56be5b4f17000807/meyer-92-contracts.pdf)
  develops the precondition, postcondition, and invariant model useful for reasoning about LSP.

[Back to the engineering principles catalog](../README.md#p004)
