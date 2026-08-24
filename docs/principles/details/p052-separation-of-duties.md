# P052 — Separation of Duties

## Definition and aliases

Separation of Duties divides a high-impact process among independent roles, actors, conditions, or
components so that one compromised or mistaken actor cannot complete it unilaterally. Independence
must be meaningful in identity, authority, and control path.

**Aliases:** segregation of duties, dual control, two-person rule.

## Provenance

**Classification:** established governance and security-control principle. It has long-standing
organizational roots and was formalized in computer-security integrity models such as Clark-Wilson.
No claim is made that one paper originated the broader organizational practice.

## Decision rule

When one actor's error or compromise could create unacceptable impact, require another independent
condition or role before the outcome can complete. Choose the number and kind of separations from
the risk rather than applying ceremony uniformly.

## How to apply

- Identify actions whose confidentiality, integrity, safety, or availability impact warrants separation.
- Split request, approval, execution, custody, and audit roles where their independence reduces risk.
- Bind approvals to the exact operation, target, parameters, and current revision.
- Prevent one identity from silently assuming all separated roles through inherited privilege.
- Preserve an auditable record of which condition each independent actor satisfied.
- Define guarded emergency access with retrospective review instead of informal bypasses.

## Boundaries and tensions

Separation of Duties is not the same as Saltzer and Schroeder's **separation of privilege**.
Separation of Duties divides responsibilities among actors or roles; separation of privilege makes
one access depend on multiple conditions or keys. They often reinforce each other, but neither
automatically implies the other. Routine low-risk work does not need multi-party ceremony, and two
nominal roles controlled by the same credential are not independent.

## Examples

### Positive

A developer may propose a production release, but a separate release identity verifies the approved
artifact digest and deployment target before the deployment capability becomes available.

### Misuse

A system labels one account “requester” and another “approver,” while both passwords and recovery
channels are controlled by the same automation credential.

### Athena and agent workflows

A high-risk security change is implemented by one agent and reviewed by an independent reviewer with
its own evidence. The reviewer cannot silently execute deployment merely because it approved the diff.

## Related principles

- [P050 — Least Privilege](./p050-least-privilege.md)
- [P051 — Complete Mediation](./p051-complete-mediation.md)
- [P058 — Bounded Agent Authority](./p058-bounded-agent-authority.md)
- [P060 — Constrain Sub-Agents](./p060-constrain-sub-agents.md)

## References

### Origin and history

- [Clark and Wilson, *A Comparison of Commercial and Military Computer Security Policies*](https://doi.org/10.1109/SP.1987.10001)
  formalizes separation of duty in an influential integrity model.

### Current guidance

- [NIST SP 800-53 Release 5.2.0, control AC-5](https://csrc.nist.gov/Pubs/sp/800/53/r5/upd1/Final)
  requires organizations to identify separated duties and define supporting access authorizations.

### Further reading

- [Saltzer and Schroeder, *The Protection of Information in Computer Systems*](https://doi.org/10.1109/PROC.1975.9939)
  defines the distinct separation-of-privilege principle based on multiple conditions or keys.

[Back to the principles catalog](../README.md#p052)
