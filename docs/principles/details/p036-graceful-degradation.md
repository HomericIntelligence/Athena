# P036 — Graceful Degradation

## Definition

When a noncritical feature or dependency fails, a system may continue with explicitly reduced
functionality if the reduced mode remains correct, secure, observable, and consistent with its
documented contract. The system must not present missing required work as a successful full result.

**Aliases:** degraded mode, partial service, fallback capability

## Provenance

**Classification:** Established reliability principle

The concept developed across fault-tolerant and distributed systems; no single origin for this
exact software rule is reliably established.

## Decision rule

Degrade only when the failed capability was classified as optional in advance and a tested fallback
can preserve every required invariant. Otherwise, fail the affected operation clearly.

## How to apply

- Classify capabilities as required, optional, or safety/security critical before an incident.
- Define the reduced output, user-visible indication, entry trigger, recovery trigger, and maximum
  duration of degraded mode.
- Prefer simple fallbacks with bounded cost, such as omitting recommendations while preserving the
  primary transaction.
- Keep authorization, integrity, and required validation in force; a fallback must not bypass them.
- Emit metrics and structured events when degraded mode starts, persists, and ends.
- Exercise the fallback under realistic dependency failure and overload conditions.

## Boundaries and tensions

[P034](p034-fail-fast.md) governs a failed **required** capability or violated invariant.
[P035](p035-fail-secure-fail-closed.md) governs uncertain security decisions. Graceful degradation
cannot redefine either category after failure just to improve availability.

Degradation also differs from swallowing an error. The caller or operator must be able to determine
that reduced service was delivered when that fact affects meaning, remediation, or service level.
Complex fallback paths can create more failure modes than they prevent, so their value must justify
their maintenance and testing cost.

## Examples

### Positive application

A storefront's recommendation service is unavailable. Product search and checkout continue, the
recommendation panel is omitted, and telemetry marks the dependency and duration of reduced mode.

### Misuse or counterexample

A payment API times out while charging a card, then returns “order completed” without reconciling
whether the charge occurred. Required transactional uncertainty is disguised as degradation.

### Athena or agent workflow

If optional web research is unavailable, a planning skill may continue from verified repository
evidence and clearly state the research limitation. It may not fabricate citations or omit a
required hard-dependency check.

## Related principles

- [P031 — Propagate Rather Than Swallow](p031-propagate-rather-than-swallow.md)
- [P034 — Fail Fast](p034-fail-fast.md)
- [P035 — Fail Secure / Fail Closed](p035-fail-secure-fail-closed.md)
- [P042 — Fault Isolation / Bulkheads](p042-fault-isolation-bulkheads.md)

## References

### Origin and history

- No single primary source is asserted for the general software phrase. It draws on longstanding
  fault-tolerance work and should not be attributed to a particular vendor or cloud platform.

### Current guidance

- [Microsoft Azure Well-Architected Framework, self-preservation](https://learn.microsoft.com/en-us/azure/well-architected/reliability/self-preservation)
  — current guidance for designing, triggering, communicating, and recovering from an explicit
  graceful-degradation mode.
- [Google SRE, Addressing Cascading Failures](https://sre.google/sre-book/addressing-cascading-failures/)
  — production guidance on serving degraded results under overload while testing and monitoring
  the rarely used path.

### Further reading

- [Microsoft Azure, Throttling pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/throttling)
  — relates degradation to capacity controls, load shedding, and service-level objectives.

[Back to the engineering principles catalog](../README.md#p036)
