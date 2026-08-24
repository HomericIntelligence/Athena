# P055 — Minimize Attack Surface

## Definition and aliases

Minimize Attack Surface means exposing only the entry points, exit paths, protocols, identities,
permissions, tools, interpreters, dependencies, and features required by the supported behavior. Each
reachable capability is another place an attacker may influence the system or extract value.

**Aliases:** attack-surface reduction, exposure minimization, remove unnecessary entry points.

## Provenance

**Classification:** established security practice. Attack-surface analysis developed across security
engineering; Manadhata and Wing provided an influential formal metric. The broader practice has no
single uncontested origin.

## Decision rule

Before adding or retaining an externally influenceable capability, identify its required consumer and
security controls. Remove or disable it when no current requirement justifies its exposure, and
reassess the threat model whenever the surface changes.

## How to apply

- Inventory data and command paths into and out of the system, including internal privileged paths.
- Remove unused endpoints, listeners, tools, plugins, protocols, dependencies, and administrative paths.
- Narrow accepted formats, methods, destinations, identities, and permissions.
- Keep privileged management surfaces isolated from routine product interfaces.
- Track surface changes during design and code review and apply focused security testing.
- Preserve required compatibility until evidence shows removal is safe.

## Boundaries and tensions

Attack surface is not source-line count. A small interpreter or broadly privileged endpoint can expose
more capability than a large pure library. Do not remove a necessary defense merely to reduce the
component count. Saltzer and Schroeder's **economy of mechanism** recommends security mechanisms that
are small and simple enough to inspect; it supports but is not equivalent to minimizing exposed attack
paths.

## Examples

### Positive

A service removes an unused administration protocol, restricts the supported API methods, and moves
the remaining administrative endpoint behind a separate authenticated network boundary.

### Misuse

A team deletes input validation to reduce code size while retaining the public endpoint and dangerous
operation. Complexity falls, but exploitable exposure increases.

### Athena and agent workflows

A documentation task receives file-read and link-check capabilities but no arbitrary shell, messaging,
deployment, or credential tools. Capabilities are added only when the task demonstrates a need.

## Related principles

- [P048 — Secure by Design](./p048-secure-by-design.md)
- [P050 — Least Privilege](./p050-least-privilege.md)
- [P054 — Defense in Depth](./p054-defense-in-depth.md)
- [P057 — Supply-Chain Integrity](./p057-supply-chain-integrity.md)

## References

### Origin and history

- [Manadhata and Wing, *An Attack Surface Metric*](https://doi.org/10.1109/TSE.2010.60) formalizes
  attack surface in terms of a system's methods, channels, data, and associated privileges.

### Current guidance

- [OWASP Attack Surface Analysis Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Attack_Surface_Analysis_Cheat_Sheet.html)
  provides a practical process for mapping, reviewing, minimizing, and monitoring surface changes.

### Further reading

- [Saltzer and Schroeder, *The Protection of Information in Computer Systems*](https://doi.org/10.1109/PROC.1975.9939)
  defines economy of mechanism, the related but distinct requirement to keep protection design simple.

[Back to the principles catalog](../README.md#p055)
