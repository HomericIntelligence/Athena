# P048 — Secure by Design

## Definition and aliases

Secure by Design makes security a requirement of architecture, implementation, delivery, and
operation from the beginning. New trust boundaries, data flows, privileges, dependencies, and
execution capabilities are designed against plausible threats rather than hardened only at release.

**Aliases:** security by design, built-in security, shift security left and throughout.

## Provenance

**Classification:** established principle.

Security design principles have deep roots, while the modern *Secure by Design* formulation has
been consolidated in software lifecycle guidance from standards bodies and public security agencies.

## Decision rule

Before adding or changing a trust-relevant capability, identify its assets, actors, boundaries,
threats, failure modes, and required controls. Put protections in the architecture and acceptance
criteria while the design can still change cheaply.

## How to apply

- Classify protected assets and draw each new or changed trust boundary and data flow.
- Threat-model entry points, identities, privileges, dependencies, and abuse cases.
- Choose safe contracts, isolation, validation, and authorization before implementation details.
- Include security tests, evidence, monitoring, update paths, and incident response in delivery.
- Revisit the model when permissions, integrations, dependencies, or operating assumptions change.
- Make the product owner accountable for security outcomes instead of transferring all risk to users.

## Boundaries and tensions

Secure by Design is not a demand for maximum controls everywhere. Controls should match assets,
threats, and impact, and should remain usable. Compliance evidence is not a substitute for threat
analysis. Late penetration testing remains useful, but it cannot cheaply repair a fundamentally
unsafe trust model. This principle shapes the lifecycle; Secure by Default governs the initial
product configuration.

## Examples

### Positive

A new webhook integration defines authenticated senders, replay resistance, payload limits, secret
rotation, failure handling, and audit events before the endpoint and queue are implemented.

### Misuse

A team ships an administrative API with broad credentials and plans to add authorization and audit
logging after customers begin using it.

### Athena and agent workflows

Before enabling a new tool, an Athena workflow defines what data crosses into the tool, which calls
are allowed, what authority it receives, how outputs are validated, and how failures are reported.

## Related principles

- [P049 — Secure by Default](./p049-secure-by-default.md)
- [P050 — Least Privilege](./p050-least-privilege.md)
- [P053 — Validate at Trust Boundaries](./p053-validate-at-trust-boundaries.md)
- [P054 — Defense in Depth](./p054-defense-in-depth.md)

## References

### Origin and history

- [Saltzer and Schroeder, *The Protection of Information in Computer Systems*](https://doi.org/10.1109/PROC.1975.9939)
  is a foundational primary source for enduring secure-system design principles; it does not claim
  the later *Secure by Design* label.

### Current guidance

- [CISA, *Shifting the Balance of Cybersecurity Risk*](https://www.cisa.gov/sites/default/files/2023-06/principles_approaches_for_security-by-design-default_508c.pdf)
  defines coordinated Secure by Design and Secure by Default expectations for software producers.
- [NIST SP 800-218, SSDF Version 1.1](https://doi.org/10.6028/NIST.SP.800-218) integrates secure
  practices throughout the software development lifecycle.

### Further reading

- [CISA Secure by Demand Guide](https://www.cisa.gov/sites/default/files/2024-08/SecureByDemandGuide_080624_508c.pdf)
  gives software customers complementary questions for evaluating producer security practices.

[Back to the principles catalog](../README.md#p048)
