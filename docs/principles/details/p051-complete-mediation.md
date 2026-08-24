# P051 — Complete Mediation

## Definition and aliases

Complete Mediation requires an authorization decision for every protected operation on the specific
target being accessed. An earlier login, screen-level check, network location, or prior successful
request does not permanently establish authority for later operations.

**Aliases:** authorize every access, per-operation authorization, continuous mediation.

## Provenance

**Classification:** established principle.

Saltzer and Schroeder named Complete Mediation as one of their secure-system design principles and
traced the suggestion to earlier work by Roger Needham.

## Decision rule

At each protected boundary, bind the current principal, operation, resource, relevant attributes,
and policy version into an authorization decision. Do not allow an alternate path to reach the
resource without the same effective check.

## How to apply

- Inventory every path to each protected resource, including batch, administrative, and recovery paths.
- Centralize policy enforcement where practical while preserving resource-specific decisions.
- Authorize the requested action on the requested object, not merely the route or object type.
- Revalidate when identity, role, tenancy, ownership, policy, or resource state may have changed.
- Design caches with explicit expiry and revocation semantics; never cache authority indefinitely.
- Test direct-object access, alternate transports, stale sessions, and policy changes.

## Boundaries and tensions

Complete Mediation concerns authorization, not repeated authentication at every function call.
Verified session identity and carefully bounded decision caching can be valid when changes and
revocation are handled. Duplicating ad hoc checks across code can create gaps; a shared enforcement
mechanism is often safer, provided no bypass path exists. Authentication alone never proves that an
identified caller may perform every action.

## Examples

### Positive

An API middleware authenticates a session, then the resource service authorizes the caller's action
against the requested tenant and object on every request, including administrative endpoints.

### Misuse

A UI hides the delete button from ordinary users, but the delete endpoint accepts any authenticated
session because login was treated as sufficient authorization.

### Athena and agent workflows

Before each write-capable tool call, the workflow checks that the requested target and operation are
inside the task's current authority. A prior approved read does not authorize a later push or deletion.

## Related principles

- [P049 — Secure by Default](./p049-secure-by-default.md)
- [P050 — Least Privilege](./p050-least-privilege.md)
- [P053 — Validate at Trust Boundaries](./p053-validate-at-trust-boundaries.md)
- [P058 — Bounded Agent Authority](./p058-bounded-agent-authority.md)

## References

### Origin and history

- [Saltzer and Schroeder, *The Protection of Information in Computer Systems*](https://doi.org/10.1109/PROC.1975.9939)
  gives the canonical formulation and discusses the risk of stale cached authority decisions.

### Current guidance

- [OWASP Authorization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html)
  requires validating permissions on every request and testing authorization logic.

### Further reading

- [NIST SP 800-53 Release 5.2.0, control AC-3](https://csrc.nist.gov/Pubs/sp/800/53/r5/upd1/Final)
  specifies policy-based enforcement for approved logical access to information and resources.

[Back to the principles catalog](../README.md#p051)
