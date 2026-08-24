# P041 — Backpressure and Load Shedding

## Definition

When demand approaches or exceeds capacity, protect the system with an explicit control response.
**Backpressure** signals producers to slow, pause, or reduce concurrency. **Load shedding** rejects,
drops, or degrades selected work that cannot be admitted safely. Both prevent uncontrolled queues
and resource use from turning overload into collapse.

**Aliases:** flow control, overload signaling, admission shedding

## Provenance

**Classification:** established principle.

Backpressure has established meanings in flow-control and streaming systems; load shedding has
established use in overload control. Athena combines the complementary tools but does not treat
them as synonyms.

## Decision rule

Before saturation, either make upstream demand conform to sustainable capacity or reject work
cheaply and predictably. Never accept unlimited work merely because it can be queued.

## How to apply

- Identify the actual bottleneck: concurrency, queue depth, CPU, memory, downstream quota, or
  another constrained resource.
- Expose standard overload signals, such as paused demand, bounded credits, HTTP 429 or 503, and
  safe retry guidance.
- Propagate downstream backpressure rather than hiding it behind immediate retries.
- Shed work before collapse, using explicit priority and fairness rules when requests differ in
  value or cost.
- Keep rejection cheaper than accepted work and avoid expensive parsing before admission when safe.
- Monitor saturation, shed rate, affected principals, tail latency, and recovery.
- Load-test steady overload, bursts, retrying callers, and recovery after load falls.

## Boundaries and tensions

Buffering smooths a short mismatch but is not backpressure if the buffer can grow without bound.
Apply [P040](p040-bounded-resources.md) to every queue. A retry response is useful only when callers
follow [P038](p038-bounded-retry.md); otherwise, rejection can become a retry storm.

Load shedding intentionally declines some work. [P036](p036-graceful-degradation.md) instead serves
a reduced but valid result. They can be combined, but neither may bypass security or silently alter
a required correctness contract.

## Examples

### Positive application

A service begins returning HTTP 503 with bounded retry guidance as its in-flight limit approaches.
It first sheds low-priority refresh requests, preserves reserved capacity for critical writes, and
recovers admission gradually after latency stabilizes.

### Misuse or counterexample

A consumer acknowledges messages immediately and stores them in an unbounded local list. The
producer sees no pressure, memory grows, and the process crashes with all buffered work at risk.

### Athena or agent workflow

A coordinator at its concurrency limit queues only a bounded number of independent tasks. It
defers or rejects lower-priority delegation and reports the constraint rather than spawning agents
until the host or token budget is exhausted.

## Related principles

- [P036 — Graceful Degradation](p036-graceful-degradation.md)
- [P038 — Bounded Retry](p038-bounded-retry.md)
- [P040 — Bounded Resources](p040-bounded-resources.md)
- [P042 — Fault Isolation / Bulkheads](p042-fault-isolation-bulkheads.md)

## References

### Origin and history

- [Reactive Manifesto 2.0 (2014)](https://www.reactivemanifesto.org/) — influential practitioner
  statement connecting message-driven flow control, monitored queues, and backpressure; it is not
  the origin of flow control.

### Current guidance

- [Reactive Streams 1.0.4](https://www.reactive-streams.org/) — specification and compatibility
  kit defining asynchronous stream processing with nonblocking backpressure.
- [Google SRE, Addressing Cascading Failures](https://sre.google/sre-book/addressing-cascading-failures/)
  — production guidance on load shedding, overload signals, bounded queues, and degraded results.

### Further reading

- [Microsoft Azure, Throttling pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/throttling)
  — detailed current guidance on early shedding, caller signals, fairness, and propagating
  backpressure through a call chain.

[Back to the engineering principles catalog](../README.md#p041)
