# P076 — Parse, Then Validate, Then Operate

## Definition

**Parse, Then Validate, Then Operate** is a boundary sequence: convert an external representation
into a well-defined internal form, validate that form against syntactic, semantic, security, and
task constraints, and only then perform work with it. Core logic should receive trusted structured
values rather than repeatedly interpreting raw input.

**Aliases:** none in common use; distinct from *Parse, Don't Validate*.

## Provenance

**Classification:** Athena synthesis.

This sequence is informed by type-oriented advice such as *Parse, Don't Validate*, but it is not
the same rule. That advice emphasizes constructing types that cannot represent invalid values.
Athena names validation separately because a value can be parseable and well typed while still
violating a domain rule, authorization decision, cross-field invariant, or current-state
precondition.

## Decision rule

Before an operation consumes boundary data, require one explicit transition from raw input to a
canonical representation and one complete validation decision. Do not start side effects while the
input is still partially parsed or only partially checked.

## How to apply

- Identify the trust boundary and the internal type accepted beyond it.
- Parse strictly; reject ambiguity instead of silently guessing.
- Normalize only transformations with one documented meaning.
- Validate ranges, relationships, invariants, authority, and current-state preconditions.
- Make operating code accept the validated form so downstream checks are not scattered.
- Preserve safe diagnostic context, but do not retain secrets or unnecessary raw input.

## Boundaries and tensions

Parsing is not sanitization, and validation is not authorization. Mutable facts may need a fresh
check immediately before use to prevent time-of-check/time-of-use defects. Validation should be
concentrated at boundaries without pretending that an untrusted value becomes permanently safe for
every future context. Prefer types that encode invariants when practical, while keeping policy
checks explicit.

## Examples

**Positive:** A deployment request is decoded into a typed target and version, checked against the
allowed environment and current release state, and only then passed to the deployer.

**Misuse:** A parser returns a partially populated object, the executor creates external resources,
and a later field check discovers that the request was invalid.

**Athena/agent workflow:** An agent parses issue fields and file paths, validates them against the
task and repository scope, and invokes tools only with the validated targets.

## Related principles

- [P053 Validate at Trust Boundaries](p053-validate-at-trust-boundaries.md)
- [P059 Data Is Not Instruction](p059-data-is-not-instruction.md)
- [P075 Make Invalid States Hard to Represent](p075-make-invalid-states-hard-to-represent.md)
- [P083 Irreversible Actions Last](p083-irreversible-actions-last.md)

## References

### Origin/history

- [Parse, Don't Validate](https://lexi-lambda.github.io/blog/2019/11/05/parse-don-t-validate/)
  presents the influential type-oriented formulation and explains why parsing into informative
  types is stronger than repeated boolean checks.

### Current guidance

- [OWASP Input Validation Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html)
  distinguishes syntactic from semantic validation and recommends validating untrusted data as
  early as possible.

### Further reading

- [OWASP REST Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html)
  connects secure parsing, strong types, content constraints, and rejection of unexpected input at
  API boundaries.

[Back to the engineering principles catalog](../README.md#p076)
