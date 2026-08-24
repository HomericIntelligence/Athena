# P034 — Fail Fast

## Definition

When a required invariant, configuration, dependency, or precondition is absent or invalid, stop
the affected operation near the point of detection. Report a specific failure before invalid state
can travel farther and produce corruption, misleading output, or a harder-to-diagnose symptom.

**Aliases:** early failure, immediate visible failure, detect invalid state near its source

## Provenance

**Classification:** Established practitioner principle

Jim Shore's 2004 IEEE Software article is an influential primary exposition, not proof that the
phrase or idea originated there.

## Decision rule

If continuing cannot satisfy the operation's correctness and safety contract, fail at the earliest
boundary that can identify the real defect and preserve safe state.

## How to apply

- Validate required configuration and schemas during startup or at the relevant entry boundary.
- Check invariants before using state and report the violated condition with safe context.
- Reject malformed or impossible inputs before expensive or irreversible work.
- Prefer explicit result types, assertions for true programmer invariants, and precise error
  statuses over sentinel defaults that postpone discovery.
- Ensure early termination still releases resources and produces one actionable diagnostic.
- Test startup, boundary, and invariant failures, not only successful execution.

## Boundaries and tensions

Fail fast describes **when and where** to stop; [P035](p035-fail-secure-fail-closed.md) describes
the safe authorization or security state after uncertainty. [P036](p036-graceful-degradation.md)
permits continued reduced service only for a noncritical capability with a documented safe
fallback. A required capability must not be relabeled “optional” simply to keep a process alive.

Fail fast is not “crash the largest possible scope.” Isolate the affected operation under
[P042](p042-fault-isolation-bulkheads.md), preserve state under
[P033](p033-state-safe-failure-semantics.md), and terminate only the scope that cannot proceed
correctly.

## Examples

### Positive application

A service validates its required signing-key configuration before accepting traffic. A missing key
causes startup to fail with the configuration field named, instead of allowing requests to reach a
later ambiguous signing error.

### Misuse or counterexample

A parser replaces a missing required identifier with an empty string. Several layers later, a
database constraint fails and hides the actual input defect.

### Athena or agent workflow

An Athena skill checks for its declared hard dependency before planning external actions. If it is
unavailable and no documented fallback exists, the skill reports that prerequisite immediately
rather than inventing results or continuing toward a misleading completion claim.

## Related principles

- [P033 — State-Safe Failure Semantics](p033-state-safe-failure-semantics.md)
- [P035 — Fail Secure / Fail Closed](p035-fail-secure-fail-closed.md)
- [P036 — Graceful Degradation](p036-graceful-degradation.md)
- [P042 — Fault Isolation / Bulkheads](p042-fault-isolation-bulkheads.md)

## References

### Origin and history

- [Jim Shore, “Fail Fast,” IEEE Software (2004)](https://martinfowler.com/ieeeSoftware/failFast.pdf)
  — influential primary article defining immediate, visible failure as an aid to diagnosis.

### Current guidance

- [C++ Core Guidelines P.7](https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines#p7-catch-run-time-errors-early)
  — living language guidance to catch runtime errors early.
- [Microsoft Azure, Design for self-healing](https://learn.microsoft.com/en-us/azure/architecture/guide/design-principles/self-healing)
  — applies fast failure to persistently unhealthy remote dependencies through circuit breakers.

### Further reading

- [Microsoft Azure, Circuit Breaker pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker)
  — shows how early rejection can protect both caller and dependency during persistent failure.

[Back to the engineering principles catalog](../README.md#p034)
