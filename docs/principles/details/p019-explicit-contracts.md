# P019 — Explicit Contracts

## Definition

State the obligations and guarantees at a boundary wherever ambiguity can cause defects. A useful
contract covers relevant inputs, outputs, preconditions, postconditions, invariants, units,
ownership, mutability, side effects, concurrency expectations, and failure behavior.

**Aliases:** interface contract; behavioral contract.

## Provenance

**Classification:** Athena synthesis with established foundations.

Bertrand Meyer's Design by Contract is a related formal foundation, not an exact alias: it
formalized preconditions, postconditions, and invariants. This principle deliberately extends that
vocabulary to operational and ownership properties used in modern systems.

## Decision rule

If two parties could make different reasonable assumptions about a boundary, encode or document
the assumption as part of the contract before relying on it.

## How to apply

- Define accepted and rejected inputs, including units, ranges, nullability, and encoding.
- Specify observable outputs, side effects, ordering, consistency, and error taxonomy.
- Express contracts in types, schemas, assertions, tests, or protocol definitions when practical.
- Name the owner and lifetime of mutable data and resources.
- Version externally consumed contracts and treat semantic changes as compatibility decisions.

## Boundaries and tensions

Not every internal helper needs exhaustive prose. Contracts should be proportional to ambiguity,
risk, and number of consumers. A schema cannot express every semantic promise, and generated
documentation does not replace executable verification. Do not expose volatile implementation
details merely to make a contract appear complete.

## Examples

### Positive application

A batch API states that sizes are bytes, rejects negative values, preserves input order, returns a
typed partial-failure result, and does not mutate caller-owned data.

### Misuse or counterexample

An endpoint publishes a JSON shape but omits whether retries can duplicate writes. The documented
syntax is explicit while the behavior callers need remains ambiguous.

### Athena or agent workflow

A skill defines required inputs, permitted capabilities, success evidence, and safe failure output
so a host can invoke it without guessing hidden preconditions.

## Related principles

- [P018 — Information Hiding](p018-information-hiding.md)
- [P020 — Executable Architecture](p020-executable-architecture.md)
- [P029 — Generalize Error Policy; Preserve Specific Cause](p029-generalize-error-policy-preserve-specific-cause.md)

## References

### Origin and history

- [Meyer, "Applying Design by Contract" (1992)](https://doi.org/10.1109/2.161279)
  presents software reliability through explicit client and supplier obligations.

### Current guidance

- [JSON Schema specification, Draft 2020-12](https://json-schema.org/specification)
  provides a current, machine-readable vocabulary for JSON structure and validation.
- [OpenAPI Specification v3.2.0](https://spec.openapis.org/oas/v3.2.0.html)
  defines versioned contracts for HTTP operations, parameters, request bodies, responses, and
  schemas.

### Further reading

- [RFC 9457, "Problem Details for HTTP APIs" (2023)](https://www.rfc-editor.org/rfc/rfc9457.html)
  demonstrates a stable error contract with general problem types and occurrence-specific detail.

[Back to the engineering principles catalog](../README.md#p019)
