# P054 — Defense in Depth

## Definition and aliases

Defense in Depth uses multiple independent preventive, detective, limiting, and recovery controls so
that failure of one mechanism does not immediately compromise the protected asset. Layers should
cover different failure modes rather than repeat one assumption.

**Aliases:** layered defense, layered security, multiple independent controls.

## Provenance

**Classification:** established principle.

The phrase has older military usage and diffuse computing history; no single software origin is
asserted. NIST and related standards now provide formal information-security definitions.

## Decision rule

For an important threat, identify the primary control and ask what prevents, detects, contains, and
recovers from its failure. Add another layer only when its different boundary or mechanism materially
reduces residual risk.

## How to apply

- Start with assets, threats, and trust boundaries rather than a generic control checklist.
- Combine controls at distinct layers, such as identity, application, data, runtime, and network.
- Avoid shared credentials, configuration, or libraries that make nominally separate layers fail together.
- Include detection and recovery instead of relying only on prevention.
- Test bypass of each layer and verify that remaining controls limit the result.
- Record ownership and maintenance for every control so stale layers do not create false assurance.

## Boundaries and tensions

More controls are not automatically better. Redundant mechanisms increase complexity and attack
surface when they do not provide independent protection. Defense in Depth does not excuse a weak
primary control, and monitoring without response is not containment. Use the least set of layers that
addresses the demonstrated threat model and remains operable.

## Examples

### Positive

A sensitive write requires service authorization, tenant-scoped database policy, an append-only audit
event, and encrypted backups. A missed route check still meets an independent data-layer barrier.

### Misuse

Three gateways apply the same copied allowlist and share one administrator credential. One bad rule or
credential compromise bypasses every nominal layer while tripling maintenance burden.

### Athena and agent workflows

A write-capable agent is limited by task instructions, tool allowlists, filesystem sandboxing,
parameter validation, and a final approval gate for ungranted irreversible actions.

## Related principles

- [P048 — Secure by Design](./p048-secure-by-design.md)
- [P050 — Least Privilege](./p050-least-privilege.md)
- [P053 — Validate at Trust Boundaries](./p053-validate-at-trust-boundaries.md)
- [P055 — Minimize Attack Surface](./p055-minimize-attack-surface.md)

## References

### Origin and history

- The term's computing history is diffuse and inherits older layered-defense usage; this page does
  not assign it to one inventor or paper.

### Current guidance

- [NIST CSRC definition of defense in depth](https://csrc.nist.gov/glossary/term/defense_in_depth)
  traces current definitions to NIST, CNSSI, and ISA/IEC security guidance.
- [NIST SP 800-53 Release 5.2.0](https://csrc.nist.gov/Pubs/sp/800/53/r5/upd1/Final) provides a
  current catalog of complementary organizational, technical, and operational security controls.

### Further reading

- [OWASP Secure Cloud Architecture Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secure_Cloud_Architecture_Cheat_Sheet.html)
  shows how trust boundaries and multiple control layers interact in application architecture.

[Back to the principles catalog](../README.md#p054)
