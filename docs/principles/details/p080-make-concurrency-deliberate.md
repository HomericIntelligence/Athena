# P080 — Make Concurrency Deliberate

## Definition

**Make Concurrency Deliberate** means introducing parallel or asynchronous execution only for a
demonstrated requirement and defining its complete coordination model. Shared state,
synchronization, ordering, cancellation, deadlines, error aggregation, and capacity limits are
parts of the design, not implementation afterthoughts.

**Aliases:** none in common use.

## Provenance

**Classification:** established principle family.

No single source coined this wording. It reflects decades of work on processes, synchronization,
message passing, structured concurrency, and language memory models. These traditions consistently
show that concurrency changes the correctness model and requires explicit reasoning.

## Decision rule

Default to sequential execution unless concurrency supplies a concrete latency, throughput,
responsiveness, or isolation benefit. When it does, choose a model whose safety and termination
properties can be stated and tested.

## How to apply

- Name the expected benefit and measure whether it is material.
- Minimize shared mutable state; prefer immutable messages or ownership transfer.
- Specify ordering guarantees, synchronization, and permitted interleavings.
- Bound workers, queues, fan-out, and outstanding work.
- Propagate deadlines and cancellation through the task tree.
- Define how partial failures and multiple concurrent errors combine.
- Use race detection, stress tests, and deterministic model tests where appropriate.

## Boundaries and tensions

Sequential code is not automatically race-free when callers or external systems invoke it
concurrently. Some domains are inherently concurrent, so the principle asks for a deliberate model,
not avoidance. Concurrency justified by measurement may still be rejected when its operational and
correctness costs exceed the benefit. Do not let an asynchronous API force unrelated layers into
unnecessary concurrency.

## Examples

**Positive:** Independent reads run in a bounded task group with a shared deadline, no shared
mutation, and deterministic result ordering.

**Misuse:** A loop launches one worker per input without a limit; failures are logged and dropped,
and the caller cannot cancel the work.

**Athena/agent workflow:** A coordinator delegates only independent subtasks, gives each worker
bounded scope, and reconciles all results before applying shared conclusions.

## Related principles

- [P039 Bounded Waiting](p039-bounded-waiting.md)
- [P040 Bounded Resources](p040-bounded-resources.md)
- [P042 Fault Isolation / Bulkheads](p042-fault-isolation-bulkheads.md)
- [P079 Explicit Ownership and Lifetimes](p079-explicit-ownership-and-lifetimes.md)
- [P082 Design for Cancellation](p082-design-for-cancellation.md)

## References

### Origin/history

- [Communicating Sequential Processes](https://doi.org/10.1145/359576.359585) is C. A. R. Hoare's
  1978 primary paper describing a process-and-message model that avoids implicit shared-state
  coordination.

### Current guidance

- [Google Engineering Practices: What to look for in a code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html)
  calls out concurrency as a complexity and correctness area requiring especially careful review.
- [The Rust Programming Language: Fearless Concurrency](https://doc.rust-lang.org/book/ch16-00-concurrency.html)
  demonstrates using ownership and types to make concurrency errors harder to express.

### Further reading

- [Go Concurrency Patterns: Context](https://go.dev/blog/context) explains explicit propagation of
  deadlines and cancellation across concurrent request work.

[Back to the engineering principles catalog](../README.md#p080)
