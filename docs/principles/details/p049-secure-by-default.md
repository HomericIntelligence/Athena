# P049 — Secure by Default

## Definition and aliases

Secure by Default means the product's initial configuration and easiest supported path provide
appropriate protection without requiring the user to discover and enable essential controls.
Weakening that protection requires a deliberate, visible choice.

**Aliases:** safe defaults, security out of the box, default-deny configuration.

## Provenance

**Classification:** established principle.

Its historical roots include fail-safe defaults; the broader product-level formulation is now
explicit in CISA's Secure by Default guidance. These related formulations should not be treated as
identical.

## Decision rule

Choose defaults that minimize likely harm for an ordinary installation, including authentication,
authorization, network exposure, data protection, and telemetry. An insecure compatibility mode may
exist only when justified, clearly labeled, and deliberately enabled.

## How to apply

- Require explicit grants instead of shipping broad access and asking users to remove it.
- Disable unnecessary endpoints, accounts, tools, and network listeners initially.
- Use secure protocol, cryptographic, privacy, and update settings by default.
- Make dangerous configuration changes visible, auditable, and reversible where practical.
- Test a clean installation and common quick-start path, not only a hardened expert deployment.
- Provide migration guidance when strengthening defaults for existing installations.

## Boundaries and tensions

A default must be usable for its intended context; a setting that everyone immediately disables is
not effective security. Existing deployments may have compatibility constraints, but those do not
justify insecure defaults for new deployments. Secure by Default concerns starting configuration;
Fail Closed concerns what happens when a runtime security decision cannot be completed reliably.

## Examples

### Positive

A service listens only on loopback, requires authentication, generates no shared default password,
and exposes administrative access only after an operator deliberately configures it.

### Misuse

A dashboard binds publicly with anonymous administrator access because its hardening guide explains
how to enable authentication later.

### Athena and agent workflows

A newly available tool starts read-only and repository-scoped. Write access is enabled only for a
task that already grants it; installation alone does not expand the agent's authority.

## Related principles

- [P048 — Secure by Design](./p048-secure-by-design.md)
- [P050 — Least Privilege](./p050-least-privilege.md)
- [P051 — Complete Mediation](./p051-complete-mediation.md)
- [P054 — Defense in Depth](./p054-defense-in-depth.md)

## References

### Origin and history

- [Saltzer and Schroeder, *The Protection of Information in Computer Systems*](https://doi.org/10.1109/PROC.1975.9939)
  describes fail-safe defaults: base access decisions on permission rather than exclusion. That is
  an important ancestor, not the complete modern product-configuration principle.

### Current guidance

- [CISA, *Shifting the Balance of Cybersecurity Risk*](https://www.cisa.gov/sites/default/files/2023-06/principles_approaches_for_security-by-design-default_508c.pdf)
  treats security as part of the product's default experience and places responsibility on producers.

### Further reading

- [OWASP Authorization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html)
  applies deny-by-default behavior to authorization policy and explains how to test it.

[Back to the principles catalog](../README.md#p049)
