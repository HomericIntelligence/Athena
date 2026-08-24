# P040 — Bounded Resources

## Definition

Any resource whose demand can grow must have a deliberate limit or a proven physical bound. This
includes queues, buffers, concurrency, recursion, batches, memory, disk, outstanding work, agent
iterations, token use, and tool invocations. Reaching the bound must produce controlled behavior.

**Aliases:** resource limits, finite capacity, quotas

## Provenance

**Classification:** Established reliability and security principle

Resource bounding is foundational across operating systems, queueing, and secure design. No single
origin for this language-neutral rule is asserted.

## Decision rule

For every potentially repeated or accumulated unit of work, identify the capacity owner, set a
limit based on evidence and risk, and define admission, rejection, cleanup, and recovery at that
limit.

## How to apply

- Inventory resources consumed per request, tenant, process, and dependency.
- Bound both item count and item cost where items can vary greatly in size or complexity.
- Prefer platform-provided quotas, bounded executors, and bounded queues over bespoke counters.
- Reserve capacity or separate pools for critical work so low-value demand cannot consume it all.
- Make rejection cheaper than admitted work and provide a clear overload signal.
- Monitor saturation, rejected work, queue age, and time at the limit; revisit limits as workloads
  change.
- Test the system at and beyond each important limit, including cleanup and recovery.

## Boundaries and tensions

A large finite number is not a meaningful bound if it exceeds available capacity. A small limit can
also harm correctness or availability if it ignores legitimate bursts. Use measurements and service
objectives rather than arbitrary constants.

[P041](p041-backpressure-and-load-shedding.md) defines how demand should react at capacity, while
[P042](p042-fault-isolation-bulkheads.md) prevents one consumer from exhausting unrelated capacity.
[P039](p039-bounded-waiting.md) limits resource holding time as well as resource count.

## Examples

### Positive application

A worker pool caps in-flight tasks and queue depth. When full, it rejects new work with a retryable
overload response, exposes queue-age metrics, and retains reserved capacity for health operations.

### Misuse or counterexample

An API buffers every request in an unbounded in-memory queue during a downstream outage. Memory
growth eventually crashes the process and discards the entire backlog.

### Athena or agent workflow

A swarm workflow sets explicit limits on concurrent specialists, iterations, tool calls, and token
budget. Hitting a limit returns a truthful partial or failed outcome instead of silently spawning
more work.

## Related principles

- [P039 — Bounded Waiting](p039-bounded-waiting.md)
- [P041 — Backpressure and Load Shedding](p041-backpressure-and-load-shedding.md)
- [P042 — Fault Isolation / Bulkheads](p042-fault-isolation-bulkheads.md)
- [P043 — Circuit Breakers](p043-circuit-breakers.md)

## References

### Origin and history

- No single primary origin is asserted. Operating systems and network services have long used
  quotas and capacity limits; Athena generalizes the practice to software and agentic resources.

### Current guidance

- [MITRE CWE-770, Allocation of Resources Without Limits or Throttling](https://cwe.mitre.org/data/definitions/770.html)
  — current weakness definition, consequences, and mitigations for unbounded allocation.
- [Google SRE, Addressing Cascading Failures](https://sre.google/sre-book/addressing-cascading-failures/)
  — production guidance on queue, memory, thread, CPU, and file-descriptor exhaustion.

### Further reading

- [Microsoft Azure, Throttling pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/throttling)
  — guidance for aligning limits to the resource that saturates first and controlling admission.

[Back to the engineering principles catalog](../README.md#p040)
