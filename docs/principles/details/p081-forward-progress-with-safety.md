# P081 — Forward Progress With Safety

## Definition

**Forward Progress With Safety** requires an operation either to make bounded, observable progress
toward a valid outcome or to terminate in a clear recoverable failure state. It combines safety
properties—nothing invalid happens—with liveness properties—required progress eventually happens.

**Aliases:** none in common use.

## Provenance

**Classification:** Athena synthesis.

Athena's operational wording is not a named theorem. Leslie Lamport's 1977 work established the
modern distinction between safety and liveness properties for concurrent programs. Reliability
practice adds deadlines, retry budgets, cancellation, and recovery states to make that distinction
actionable in production workflows.

## Decision rule

For every loop, wait, retry, queue, and multistep workflow, define the progress measure, the bound or
termination condition, the invariants that must remain true, and the recoverable outcome when
progress cannot continue.

## How to apply

- Make terminal success, failure, cancellation, and paused states distinguishable.
- Bound retries, waits, queues, and internal iteration.
- Detect and report stagnation rather than resetting a watchdog without real progress.
- Preserve invariants at every checkpoint and failure exit.
- Persist enough state to resume long work safely when required.
- Test deadlock, timeout, starvation, cancellation, and dependency-loss scenarios.

## Boundaries and tensions

The principle does not require every algorithm to be wait-free or every operation to have a short
fixed duration. Some safe work is slow or dependent on external events; it still needs observability,
cancellation, or an explicit resumable state. Safety may require stopping rather than forcing
progress. A timeout is a failure outcome, not evidence that an attempted side effect did not occur.

## Examples

**Positive:** A migration records each completed batch, enforces a time budget, and exits as
`paused` with a resume token while preserving schema invariants.

**Misuse:** A worker catches every error and retries forever, consuming a queue slot while callers
see neither completion nor failure.

**Athena/agent workflow:** A delegated task has a bounded iteration budget and produces success,
blocked, or failed status with evidence instead of remaining indefinitely active.

## Related principles

- [P039 Bounded Waiting](p039-bounded-waiting.md)
- [P040 Bounded Resources](p040-bounded-resources.md)
- [P046 Resumability](p046-resumability.md)
- [P047 Observability Is Part of Correctness](p047-observability-is-part-of-correctness.md)
- [P082 Design for Cancellation](p082-design-for-cancellation.md)

## References

### Origin/history

- [Proving the Correctness of Multiprocess Programs](https://doi.org/10.1109/TSE.1977.229904)
  is Lamport's 1977 primary work introducing safety and liveness as distinct correctness concerns.

### Current guidance

- [gRPC Deadlines](https://grpc.io/docs/guides/deadlines/) explains why calls need realistic
  deadlines and why servers must stop work after cancellation.
- [AWS Well-Architected: Control and limit retry calls](https://docs.aws.amazon.com/wellarchitected/latest/framework/rel_mitigate_interaction_failure_limit_retries.html)
  requires retry limits, backoff, and tested stop conditions.

### Further reading

- [Exponential Backoff and Jitter](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/)
  shows how bounded randomized retry can preserve progress without synchronized contention.

[Back to the engineering principles catalog](../README.md#p081)
