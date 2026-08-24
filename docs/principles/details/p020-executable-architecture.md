# P020 — Executable Architecture

## Definition

Encode important architectural constraints in mechanisms that can evaluate the implementation,
such as tests, type systems, schemas, static analysis, dependency rules, CI policy, or runtime
guards. Documentation explains intent; executable checks detect drift.

**Aliases:** architecture fitness functions; architecture tests; automated architecture
governance.

## Provenance

**Classification:** practitioner heuristic.

This practitioner architectural technique has no single verified origin. Ford, Parsons, and Kua
popularized architectural fitness functions as part of evolutionary architecture; many earlier
tools enforced dependency and conformance rules.

## Decision rule

When violating an architectural rule would create material risk and the rule is mechanically
observable, add the smallest reliable check at the closest practical feedback boundary.

## How to apply

- Choose a few consequential qualities or dependency rules, not every architectural preference.
- Select the cheapest faithful mechanism: compiler, linter, unit test, integration check, or CI.
- Make failure output identify the violated rule and the offending dependency or artifact.
- Keep the check in the same change as the rule it protects.
- Review checks when the architecture intentionally evolves; update rule and implementation
  together.

## Boundaries and tensions

Not every architectural property is computable. A proxy metric can be gamed or reject sound
designs, so human review remains necessary for semantics and trade-offs. Avoid prose-string tests,
snapshot inventories, and brittle dependency rules that freeze incidental layout instead of a
consumer-relevant boundary.

## Examples

### Positive application

A dependency test rejects imports from the domain layer into transport adapters and reports the
exact edge. The architecture document explains why the direction matters.

### Misuse or counterexample

A test asserts that a document contains a particular heading, claiming this enforces modularity.
It freezes wording without checking any architectural behavior.

### Athena or agent workflow

Athena's validator discovers canonical skill entrypoints and rejects host-specific skill mirrors.
The repository policy explains the boundary; the check prevents distribution drift.

## Related principles

- [P019 — Explicit Contracts](p019-explicit-contracts.md)
- [P021 — Evolutionary and Reversible Design](p021-evolutionary-and-reversible-design.md)
- [P027 — Deterministic and Hermetic Tests](p027-deterministic-and-hermetic-tests.md)

## References

### Origin and history

- [Ford, Parsons, and Kua, *Building Evolutionary Architectures*, second-edition sample](https://www.thoughtworks.com/content/dam/thoughtworks/documents/books/bk_building_evolutionary_architectures_second_edition_free_chapter.pdf)
  explains fitness functions as objective checks that guide architectural change.

### Current guidance

- [ArchUnit User Guide](https://www.archunit.org/userguide/html/000_Index.html)
  documents executable dependency, layer, cycle, and custom architecture rules for Java systems.
- [SEI, "Software Architecture"](https://www.sei.cmu.edu/software-architecture/)
  describes conformance analysis and repeated fitness evaluation as architecture practices.

### Further reading

- [Thoughtworks, *Building Evolutionary Architectures* sample chapter](https://www.thoughtworks.com/content/dam/thoughtworks/documents/books/bk_building_evolutionary_architectures_en.pdf)
  surveys automated and manual fitness functions and their trade-offs.

[Back to the engineering principles catalog](../README.md#p020)
