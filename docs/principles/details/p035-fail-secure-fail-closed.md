# P035 — Fail Secure / Fail Closed

## Definition

When authentication, authorization, validation, or security-policy evaluation cannot establish
that an operation is allowed, leave the system in the secure state: deny the capability, preserve
confidentiality and integrity, and report the failure. Absence, timeout, parse failure, or exception
must not silently become permission.

**Aliases:** fail-safe defaults, deny by default on security failure

## Provenance

**Classification:** Established security design principle

Saltzer and Schroeder documented “fail-safe defaults” in 1975. “Fail closed” and “fail secure” are
later common formulations and can mean different things in safety engineering.

## Decision rule

Grant a protected operation only from an explicit, successfully evaluated authorization result.
Treat missing, invalid, stale, or indeterminate security state as denial unless a higher trusted
contract defines a different safe state.

## How to apply

- Initialize authorization decisions to denial and transition to allow only after every required
  check succeeds.
- Make policy-service timeout and error states distinct from an affirmative decision, even if they
  share the same external denial response.
- Keep a protected resource unchanged when request validation or authorization fails.
- Test missing policy, dependency timeout, corrupt credentials, exception paths, and stale state.
- Emit protected diagnostics that distinguish denial from infrastructure failure without leaking
  secrets or sensitive policy detail.
- Restore service deliberately after the security dependency is healthy; do not auto-bypass it.

## Boundaries and tensions

Fail closed is a security choice, not a blanket availability rule. For a non-security-critical
feature, [P036](p036-graceful-degradation.md) may preserve useful service. Safety-critical systems
can also require a physically safe state different from “deny”; their domain-specific hazard
analysis governs.

[P034](p034-fail-fast.md) says to surface invalid security state near its source. This principle
says the resulting capability remains denied. [P033](p033-state-safe-failure-semantics.md) still
requires cleanup and a valid post-failure state.

## Examples

### Positive application

An authorization service times out. The API returns an unavailable or denied outcome, leaves the
record unchanged, and records a protected correlation identifier for operators.

### Misuse or counterexample

Code initializes `is_admin` to true, attempts a role lookup, and catches lookup errors without
changing the value. A failed security control grants the highest privilege.

### Athena or agent workflow

An agent cannot verify whether a destructive command is authorized for the exact target. It stops
and requests direction; uncertainty does not become permission to run the command.

## Related principles

- [P033 — State-Safe Failure Semantics](p033-state-safe-failure-semantics.md)
- [P034 — Fail Fast](p034-fail-fast.md)
- [P036 — Graceful Degradation](p036-graceful-degradation.md)
- [P053 — Validate at Trust Boundaries](../README.md#p053)

## References

### Origin and history

- [Saltzer and Schroeder, “The Protection of Information in Computer Systems” (1975)](https://doi.org/10.1109/PROC.1975.9939)
  — primary source for the fail-safe-defaults design principle: base access decisions on explicit
  permission rather than exclusion.

### Current guidance

- [OWASP, Fail Securely](https://owasp.org/www-community/Fail_securely) — current application
  guidance that security-control exceptions should follow the disallow path.
- [OWASP Developer Guide](https://owasp.org/www-project-developer-guide/assets/exports/OWASP_Developer_Guide.pdf)
  — current broader secure-development guidance that treats secure failure defaults as part of
  application design.

### Further reading

- [NIST SP 800-53 Rev. 5, AC-3 Access Enforcement](https://doi.org/10.6028/NIST.SP.800-53r5)
  — authoritative control catalog for enforcing approved authorizations on system access.

[Back to the engineering principles catalog](../README.md#p035)
