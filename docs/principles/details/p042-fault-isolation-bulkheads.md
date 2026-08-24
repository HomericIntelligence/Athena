# P042 — Fault Isolation / Bulkheads

## Definition

Partition workloads, dependencies, tenants, and resource pools so failure or exhaustion in one
partition cannot consume the capacity or corrupt the state required by unrelated partitions.
Isolation turns a system-wide failure into a bounded local failure.

**Aliases:** bulkhead pattern, failure domains, cell-based isolation, blast-radius containment

## Provenance

**Classification:** established principle.

The name is a nautical analogy. Michael Nygard's *Release It!* popularized the bulkhead pattern in
modern software; the underlying practice of fault isolation is older.

## Decision rule

Whenever components have different failure risks, criticality, owners, or consumers, decide whether
they need independent capacity and state boundaries before allowing them to share resources.

## How to apply

- Define failure domains from business criticality and real dependency paths, not merely deployment
  topology.
- Separate concurrency pools, queues, connection pools, quotas, processes, accounts, regions, or
  credentials where shared exhaustion would violate objectives.
- Reserve enough capacity for health, recovery, and critical traffic in each relevant partition.
- Keep control-plane failure from consuming the data plane and prevent one tenant from becoming a
  noisy neighbor.
- Monitor each partition independently and retain an aggregate view of system health.
- Test exhaustion and failure inside one partition and verify that unrelated partitions continue.

## Boundaries and tensions

Isolation costs capacity, operational complexity, and sometimes utilization efficiency. Do not
create a partition without a concrete failure mode or service objective. A logical label is not a
bulkhead if all partitions still share the same unbounded queue, connection pool, or credential.

[P040](p040-bounded-resources.md) bounds each pool, [P041](p041-backpressure-and-load-shedding.md)
controls admission at capacity, and [P043](p043-circuit-breakers.md) stops calls into a failing
dependency. These controls reinforce rather than replace one another.

## Examples

### Positive application

Calls to three downstream services use separate connection and concurrency pools. When one service
hangs, it exhausts only its own pool; health checks and calls to the other services remain available.

### Misuse or counterexample

Nominally independent tenants share one executor and unbounded queue. One tenant submits expensive
work and starves every other tenant, so the labels provide no fault isolation.

### Athena or agent workflow

Independent subagents receive bounded task scopes and do not share writable targets without
coordination. One stalled or failed specialist does not consume every delegation slot or corrupt
another specialist's output.

## Related principles

- [P036 — Graceful Degradation](p036-graceful-degradation.md)
- [P040 — Bounded Resources](p040-bounded-resources.md)
- [P041 — Backpressure and Load Shedding](p041-backpressure-and-load-shedding.md)
- [P043 — Circuit Breakers](p043-circuit-breakers.md)

## References

### Origin and history

- [Michael T. Nygard, *Release It!*, second edition](https://pragprog.com/titles/mnee2/release-it-second-edition/)
  — influential source that popularized bulkheads and other stability patterns in software; the
  physical bulkhead analogy predates computing.

### Current guidance

- [Microsoft Azure, Bulkhead pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/bulkhead)
  — current guidance on partitioning service instances and resource pools to isolate cascading
  failures.

### Further reading

- [Microsoft Azure Well-Architected reliability patterns](https://learn.microsoft.com/en-us/azure/well-architected/reliability/design-patterns)
  — places bulkheads alongside throttling, retry, and circuit breakers as complementary reliability
  controls.

[Back to the engineering principles catalog](../README.md#p042)
