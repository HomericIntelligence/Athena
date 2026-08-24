# P043 — Circuit Breakers

## Definition

A circuit breaker observes calls to a dependency and, after evidence of persistent failure, opens
to reject further calls without invoking that dependency. After a controlled recovery interval it
admits a limited probe in a half-open state, closing only when recovery criteria are met.

**Aliases:** dependency circuit breaker, open/half-open/closed breaker

## Provenance

**Classification:** established principle.

Michael Nygard popularized the software pattern in *Release It!*; the electrical circuit-breaker
metaphor and related failure controls are older.

## Decision rule

When repeated calls are likely to waste caller resources, overload an unhealthy dependency, or
spread failure, stop sending them temporarily and test recovery cautiously.

## How to apply

- Place the breaker around a remote or otherwise failure-prone dependency boundary, not arbitrary
  local business logic.
- Choose failure signals, sampling window, threshold, open duration, and recovery criteria from the
  dependency contract and observed behavior.
- Keep breaker state scoped appropriately; a global breaker can unnecessarily disable healthy
  partitions, while a per-request breaker learns nothing.
- Return a distinct, immediate failure or documented fallback while open.
- Permit only bounded probes while half-open and prevent a recovery stampede.
- Emit state transitions, rejected calls, probe outcomes, and affected dependency identity.
- Test oscillation, slow calls, partial recovery, and breaker behavior with retries.

## Boundaries and tensions

A breaker is not a retry policy. [P038](p038-bounded-retry.md) addresses isolated transient errors;
the breaker protects against persistent failure. A timeout under
[P039](p039-bounded-waiting.md) still bounds each permitted call.

Opening too aggressively can turn a small fault into avoidable unavailability; opening too slowly
allows cascading failure. [P042](p042-fault-isolation-bulkheads.md) limits the blast radius even
before the breaker opens, and [P036](p036-graceful-degradation.md) governs any fallback response.

## Examples

### Positive application

A client records timeouts within a rolling window. At its tested threshold the dependency-specific
breaker opens, immediately rejects calls for a bounded interval, then permits a few probes before
restoring traffic gradually.

### Misuse or counterexample

A single validation error opens one application-wide breaker for every tenant and endpoint. Healthy
traffic is disabled even though the error was a permanent request defect, not dependency failure.

### Athena or agent workflow

If a dependency-backed tool repeatedly returns confirmed service failures, a workflow stops
invoking it after a bounded threshold and reports the unavailable capability. It does not keep
spending tool calls or claim that the skipped result succeeded.

## Related principles

- [P036 — Graceful Degradation](p036-graceful-degradation.md)
- [P038 — Bounded Retry](p038-bounded-retry.md)
- [P039 — Bounded Waiting](p039-bounded-waiting.md)
- [P042 — Fault Isolation / Bulkheads](p042-fault-isolation-bulkheads.md)

## References

### Origin and history

- [Michael T. Nygard, *Release It!*, second edition](https://pragprog.com/titles/mnee2/release-it-second-edition/)
  — influential source that popularized the circuit-breaker pattern in production software.
- [Martin Fowler, “Circuit Breaker” (2014)](https://martinfowler.com/bliki/CircuitBreaker.html)
  — practitioner explanation that explicitly credits Nygard and illustrates the state model.

### Current guidance

- [Microsoft Azure, Circuit Breaker pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker)
  — current guidance on thresholds, open and half-open states, recovery probes, and interaction with
  retry.

### Further reading

- [Google SRE, Addressing Cascading Failures](https://sre.google/sre-book/addressing-cascading-failures/)
  — operational context for why persistent calls, timeouts, and retries can spread failure.

[Back to the engineering principles catalog](../README.md#p043)
