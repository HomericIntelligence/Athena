# P006 — Principle of Least Astonishment

## Definition

The **Principle of Least Astonishment** (**POLA**, also called the principle of least surprise)
requires interfaces, defaults, state changes, and failures to behave as their intended users would
reasonably predict from the surrounding system and stated contract.

## Provenance

**Classification:** established practitioner heuristic.

The phrase has circulated through programming-language and interface design for decades, but no
single origin is reliably established. POLA is also contextual: what surprises one audience may be
normal to another, so repository precedent and explicit user research are stronger evidence than a
designer's intuition alone.

## Decision rule

When several correct designs are available, choose the one most consistent with the public
contract, local conventions, and users' established mental model. Make necessary deviations
explicit and migration-safe.

## How to apply

- Identify the actual audience and the conventions it already relies on.
- Make names, defaults, units, mutability, side effects, and errors consistent across the surface.
- Use explicit confirmation or naming for destructive and unusually expensive behavior.
- Preserve ordinary expectations across related CLI, API, and configuration operations.
- Test defaults and failure behavior as part of the public contract.

## Boundaries and tensions

POLA is not a vote for familiar but unsafe behavior. Security, correctness, accessibility, and an
explicit specification can require a deliberate break from precedent. In that case, communicate
the difference and provide a migration where appropriate. [P014 Preserve Unrequested Behavior](p014-preserve-unrequested-behavior.md)
protects established contracts, while [P019 Explicit Contracts](p019-explicit-contracts.md) reduces
ambiguity where expectations differ.

## Examples

**Positive:** A `--dry-run` flag performs no external writes and reports exactly what a normal run
would attempt.

**Misuse:** A command named `list` silently repairs and deletes stale resources because cleanup is
convenient during enumeration.

**Athena/agent workflow:** A skill treats missing required capabilities through its documented
fallback instead of silently switching to a workflow with broader authority.

## Related principles

- [P014 Preserve Unrequested Behavior](p014-preserve-unrequested-behavior.md)
- [P019 Explicit Contracts](p019-explicit-contracts.md)
- [P049 Secure by Default](p049-secure-by-default.md)
- [P071 Consistency Over Personal Preference](p071-consistency-over-personal-preference.md)
- [P085 Explicit Is Better Than Implicit](p085-explicit-is-better-than-implicit.md)

## References

### Origin/history

- [The Open Group Base Specifications, Utility Syntax Guidelines](https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/V1_chap12.html)
  document longstanding consistency rules for command interfaces; they illustrate POLA without
  claiming to originate the phrase.

### Current guidance

- [Google Cloud API Design Guide](https://cloud.google.com/apis/design) treats consistency and
  predictable resource-oriented conventions as core API design goals.
- [Google API Improvement Proposals: General principles](https://google.aip.dev/general) defines
  conventions intended to keep related APIs coherent.

### Further reading

- [PEP 20 — The Zen of Python](https://peps.python.org/pep-0020/) provides a compact example of how
  a language community records expectations about explicit and unsurprising design.

[Back to the engineering principles catalog](../README.md#p006)
