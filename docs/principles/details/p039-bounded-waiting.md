# P039 — Bounded Waiting

## Definition

Any wait for an external operation, lock, queue, process, asynchronous result, or delegated task
must have termination behavior appropriate to its risk: a deadline, timeout, cancellation signal,
or another demonstrable bound. The caller must be able to distinguish completion, cancellation,
timeout, and failure.

**Aliases:** deadlines, timeouts, finite blocking, wait budget

## Provenance

**Classification:** Established reliability practice

Timeouts and deadlines are longstanding concurrency and distributed-systems mechanisms. This broad
formulation has no single verified origin.

## Decision rule

If completion depends on another actor or contested resource, define how long the caller is willing
to wait and what safe outcome follows when that budget expires.

## How to apply

- Prefer an end-to-end deadline that downstream calls inherit over unrelated per-hop timeouts.
- Derive budgets from service objectives, measured latency, operation value, and cleanup cost.
- Propagate cancellation and remaining time to child operations.
- On timeout, stop or detach work only according to an explicit ownership contract; a caller timeout
  does not prove that remote side effects stopped.
- Release locks, slots, and temporary resources on every terminal path.
- Test deadline expiry, cancellation races, slow dependencies, and work that completes just before
  or after the boundary.

## Boundaries and tensions

A timeout bounds the caller's wait, not necessarily the callee's execution. Side-effecting work may
need [P037](p037-idempotency-before-retry.md), status reconciliation, or compensation before a retry.

Timeouts that are unrealistically short create self-inflicted failure; missing timeouts permit
resource leaks and cascades. Use evidence to set the budget, and combine it with
[P040](p040-bounded-resources.md) so many individually bounded waits cannot exhaust the system.

## Examples

### Positive application

An incoming request carries a two-second deadline. Each downstream call receives the remaining
budget, stops spawned work on cancellation, and returns a distinct deadline-exceeded result.

### Misuse or counterexample

A worker calls an external process with no timeout and holds a concurrency slot forever when that
process hangs. The bounded queue eventually stops making progress.

### Athena or agent workflow

A coordinator gives delegated research a stated deadline and checks the resulting status. On
timeout it reports incomplete evidence and terminates or safely abandons the task according to the
host contract; it does not wait indefinitely or invent a result.

## Related principles

- [P037 — Idempotency Before Retry](p037-idempotency-before-retry.md)
- [P038 — Bounded Retry](p038-bounded-retry.md)
- [P040 — Bounded Resources](p040-bounded-resources.md)
- [P043 — Circuit Breakers](p043-circuit-breakers.md)

## References

### Origin and history

- No single origin is asserted. Deadline and timeout mechanisms predate contemporary RPC systems
  and appear across operating-system, concurrency, and networking literature.

### Current guidance

- [gRPC, Deadlines](https://grpc.io/docs/guides/deadlines/) — official guidance to set realistic
  deadlines, propagate them, and stop server work after expiry.
- [gRPC, Cancellation](https://grpc.io/docs/guides/cancellation/) — official guidance for signaling
  lost interest and propagating cancellation through an RPC call graph.

### Further reading

- [Google SRE, Addressing Cascading Failures](https://sre.google/sre-book/addressing-cascading-failures/)
  — connects expired client deadlines, wasted server work, resource exhaustion, and cascades.

[Back to the engineering principles catalog](../README.md#p039)
