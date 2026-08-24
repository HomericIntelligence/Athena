# P082 — Design for Cancellation

## Definition

**Design for Cancellation** means treating a caller's loss of interest as a first-class terminal
signal. Long-running, asynchronous, networked, or agentic work must define how cancellation is
requested, propagated, observed, cleaned up, and reported without corrupting state or leaking
resources.

**Aliases:** none in common use; cooperative cancellation is one implementation approach.

## Provenance

**Classification:** practitioner heuristic.

There is no verified single origin. Cooperative cancellation developed across operating systems,
concurrent programming, and distributed request APIs. Modern structured-concurrency and context
APIs make the lifetime relationship between callers and child work explicit.

## Decision rule

If work can outlive the caller's need for its result, its contract must state whether cancellation
is supported, where it takes effect, what cleanup is guaranteed, and what result the caller receives.

## How to apply

- Accept and propagate the host's cancellation or context capability.
- Check cancellation at bounded, state-safe checkpoints.
- Stop spawning downstream work after cancellation is observed.
- Release resources and join or account for child work before returning.
- Distinguish cancellation from timeout, dependency failure, and successful completion.
- Make cleanup, compensation, and retries idempotent where repeated signals are possible.
- Test races between cancellation, completion, and partial side effects.

## Boundaries and tensions

A cancellation request is not proof of rollback. An atomic or irreversible step may need to finish
before cancellation can take effect, and small cleanup regions may be shielded so invariants are
restored. Document these points instead of claiming immediate interruption. Do not swallow a
cancellation signal and return apparent success.

## Examples

**Positive:** An import stops between committed batches, closes its input, records a resume token,
and returns a distinct cancellation result.

**Misuse:** A canceled HTTP request leaves database work and spawned subprocesses running with no
remaining owner.

**Athena/agent workflow:** A coordinator propagates an interrupted task to its subagents, collects
their terminal states, and reports any side effects already completed.

## Related principles

- [P033 State-Safe Failure Semantics](p033-state-safe-failure-semantics.md)
- [P037 Idempotency Before Retry](p037-idempotency-before-retry.md)
- [P046 Resumability](p046-resumability.md)
- [P079 Explicit Ownership and Lifetimes](p079-explicit-ownership-and-lifetimes.md)
- [P083 Irreversible Actions Last](p083-irreversible-actions-last.md)

## References

### Origin/history

- No single primary source for the general pattern is established. It should not be attributed to
  one language or framework.
- [Go Concurrency Patterns: Context](https://go.dev/blog/context) documents an influential 2014
  model for propagating deadlines and cancellation through request-scoped work.

### Current guidance

- [gRPC Cancellation](https://grpc.io/docs/guides/cancellation/) defines cancellation propagation
  and makes clear that applications must stop work they started for a canceled RPC.
- [Go: Canceling in-progress operations](https://go.dev/doc/database/cancel-operations) shows
  cancellation and cleanup across database calls.

### Further reading

- [gRPC Deadlines](https://grpc.io/docs/guides/deadlines/) connects time bounds to automatic
  cancellation while assigning spawned-work cleanup to the server application.

[Back to the engineering principles catalog](../README.md#p082)
