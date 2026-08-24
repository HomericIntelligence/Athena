# P050 — Least Privilege

## Definition and aliases

Least Privilege grants each user, process, service, tool, or agent only the resources and actions
needed for its current responsibility, for no longer than needed. Scope includes identities,
credentials, files, network destinations, APIs, commands, data fields, and execution duration.

**Aliases:** principle of least privilege, minimal privilege, least authority.

## Provenance

**Classification:** established security principle. Saltzer and Schroeder's 1975 formulation is a
canonical primary source, although related need-to-know and capability ideas appeared earlier.

## Decision rule

For every grant, ask whether the task can succeed with a narrower resource, action, identity, or
lifetime. Grant the narrowest sufficient capability, verify it at use time, and remove it when the
task ends.

## How to apply

- Derive permissions from documented responsibilities and exact operations, not job titles alone.
- Separate read, write, administer, approve, and delegate capabilities.
- Prefer task-scoped, short-lived credentials over shared or long-lived credentials.
- Restrict filesystem roots, network destinations, tool sets, and data fields independently.
- Review effective permissions, including inherited roles and transitive service access.
- Make denial explicit when narrower authority cannot complete the requested operation.

## Boundaries and tensions

Least privilege means sufficient but minimal authority, not zero authority. Excessive restriction can
produce unsafe workarounds, so denials should identify the missing capability. It limits what one
actor can do; Separation of Duties limits which combinations of actors or conditions can authorize a
high-impact outcome. A trusted identity still needs a narrowly authorized request.

## Examples

### Positive

A reporting job receives a short-lived credential that can read only the required view for one
tenant. It cannot modify data, enumerate unrelated tables, or assume an administrator role.

### Misuse

A deployment helper receives permanent organization-owner credentials because future commands are
unknown, even though its present task only reads one repository's release metadata.

### Athena and agent workflows

A review agent receives a read-only checkout and validation commands. It is not given deployment,
messaging, credential, or repository-write tools that the review contract does not require.

## Related principles

- [P051 — Complete Mediation](./p051-complete-mediation.md)
- [P052 — Separation of Duties](./p052-separation-of-duties.md)
- [P058 — Bounded Agent Authority](./p058-bounded-agent-authority.md)
- [P060 — Constrain Sub-Agents](./p060-constrain-sub-agents.md)

## References

### Origin and history

- [Saltzer and Schroeder, *The Protection of Information in Computer Systems*](https://doi.org/10.1109/PROC.1975.9939)
  states that programs and users should operate with the least privileges necessary for the job.

### Current guidance

- [NIST SP 800-53 Release 5.2.0, control AC-6](https://csrc.nist.gov/Pubs/sp/800/53/r5/upd1/Final)
  applies least privilege to users and processes and covers privileged functions and accounts.

### Further reading

- [OWASP Authorization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html)
  translates least privilege into practical authorization design and verification guidance.

[Back to the principles catalog](../README.md#p050)
