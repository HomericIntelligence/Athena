# P075 — Make Invalid States Hard to Represent

## Definition

Use types, schemas, constructors, validation, encapsulation, and state machines so invalid
combinations of data are rejected at creation or cannot be expressed by ordinary program paths.
Core logic should receive values whose important structural invariants already hold.

**Aliases:** make illegal states unrepresentable; encode invariants in the model.

## Provenance

**Classification:** practitioner heuristic.

The aphorism has diffuse provenance across typed functional programming and domain modeling; this
page does not assign it to a single author. Algebraic data types, abstract data types, design by
contract, and schema validation supply established technical foundations.

## Decision rule

When a state combination is always invalid, model construction so normal callers cannot create it.
Use repeated runtime checks only for invariants that cannot be enforced more clearly at the boundary
or in the representation.

## How to apply

- Replace correlated booleans and nullable fields with explicit variants when states are exclusive.
- Use validated constructors or factories that return a valid value or a specific error.
- Keep fields private when unrestricted mutation could violate invariants.
- Express units, identifiers, required fields, and legal transitions in types or schemas.
- Revalidate facts that depend on external mutable state at the responsible boundary.

## Boundaries and tensions

No type system can prove every temporal, distributed, authorization, or business invariant. External
data remains untrusted and still requires [P053 boundary validation](p053-validate-at-trust-boundaries.md)
and [P076 parse-validate-operate](p076-parse-then-validate-then-operate.md). Avoid a maze of wrappers,
generics, or type-level machinery whose complexity exceeds the prevented risk. Representations must
remain readable, evolvable, and compatible with required serialization contracts.

## Examples

**Positive:** A payment state is one enum with variant-specific data, so `settled` and `failed`
cannot both be true and only legal transitions are exposed.

**Misuse:** Three booleans and two nullable timestamps encode workflow state, forcing every caller to
rediscover and check impossible combinations.

**Athena/agent workflow:** A review contract is parsed into a structure whose constructor requires a
revision, scope, and activated principle content, so the restricted reviewer never receives a
partially initialized contract.

## Related principles

- [P019 Explicit Contracts](p019-explicit-contracts.md)
- [P053 Validate at Trust Boundaries](p053-validate-at-trust-boundaries.md)
- [P076 Parse, Then Validate, Then Operate](p076-parse-then-validate-then-operate.md)
- [P079 Explicit Ownership and Lifetimes](p079-explicit-ownership-and-lifetimes.md)
- [P084 Prefer Local Reasoning](p084-prefer-local-reasoning.md)

## References

### Origin/history

- [Liskov and Zilles, "Programming with Abstract Data Types" (1974)](https://doi.org/10.1145/800233.807045)
  is a foundational primary source for using abstract types to control representation and
  operations; the later aphorism itself has no verified single origin.

### Current guidance

- [The Rust Programming Language: Defining an Enum](https://doc.rust-lang.org/book/ch06-01-defining-an-enum.html)
  shows how variants and exhaustive matching let a compiler distinguish and check valid cases.
- [Microsoft C#: Nullable reference types](https://learn.microsoft.com/en-us/dotnet/csharp/fundamentals/null-safety/nullable-reference-types)
  documents type annotations and flow analysis that detect states inconsistent with declared null
  contracts.

### Further reading

- [Meyer, "Applying Design by Contract"](https://www.kth.se/social/files/59526bfb56be5b4f17000807/meyer-92-contracts.pdf)
  develops preconditions, postconditions, and invariants as complementary runtime contract tools.

[Back to the engineering principles catalog](../README.md#p075)
