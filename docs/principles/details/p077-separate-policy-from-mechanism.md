# P077 — Separate Policy from Mechanism

## Definition

**Separate Policy from Mechanism** means keeping decisions about *what should happen* apart from
the machinery that determines *how it happens*. A mechanism exposes dependable capabilities; a
policy selects and constrains their use for a particular context.

**Aliases:** policy-mechanism separation; separation of policy and mechanism.

## Provenance

**Classification:** established principle.

The distinction was developed in early operating-system work and made explicit in the Hydra
system, where scheduling, paging, and protection mechanisms were designed to support replaceable
external policies. The idea now applies to application rules, security decisions, orchestration,
storage, and infrastructure as well as kernels.

## Decision rule

When a rule is expected to vary independently from the capability that enforces it, give the rule a
named policy boundary and keep the mechanism neutral enough to implement every supported policy
correctly.

## How to apply

- Identify variable decisions separately from stable primitive operations.
- Give policy inputs, outputs, defaults, and failure behavior an explicit contract.
- Inject or configure policy through a narrow interface instead of branching throughout machinery.
- Test policy choices independently from mechanism correctness.
- Keep enforcement mandatory when a policy protects security or integrity.

## Boundaries and tensions

This principle does not require an abstraction for every condition. A policy with one stable use
may remain local until variation is observed. Nor should a supposedly neutral mechanism expose a
bypass that makes required policy optional. Some low-level policy is unavoidable where fairness,
safety, or resource limits must always hold; document that choice rather than hiding it.

## Examples

**Positive:** A scheduler supplies queueing and dispatch primitives while a separate strategy
selects priority and fairness rules.

**Misuse:** Authorization rules are copied into transport handlers, database helpers, and user
interfaces, so changing a role requires inconsistent edits across all three.

**Athena/agent workflow:** A coordinator decides which independent tasks may run in parallel; the
delegation mechanism starts, monitors, and collects workers without inventing new scope policy.

## Related principles

- [P016 Separation of Concerns](p016-separation-of-concerns.md)
- [P018 Information Hiding](p018-information-hiding.md)
- [P019 Explicit Contracts](p019-explicit-contracts.md)
- [P078 Single Source of Truth](p078-single-source-of-truth.md)
- [P084 Prefer Local Reasoning](p084-prefer-local-reasoning.md)

## References

### Origin/history

- [Policy/mechanism separation in Hydra](https://doi.org/10.1145/1067629.806531)
  is the 1975 primary paper describing the principle in scheduling, paging, and protection.

### Current guidance

- [Linux Integrity Policy Enforcement](https://www.kernel.org/doc/html/latest/security/ipe.html)
  documents a contemporary kernel design in which integrity measurement and local enforcement
  policies are deliberately separated.

### Further reading

- [The Protection of Information in Computer Systems](https://www.cs.virginia.edu/~evans/cs551/saltzer/)
  supplies related foundational guidance on complete mediation, least privilege, and economical
  security mechanisms.

[Back to the engineering principles catalog](../README.md#p077)
