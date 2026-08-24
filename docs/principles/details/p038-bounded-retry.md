# P038 — Bounded Retry

## Definition

Retry only a failure classified as transient, and stop after an explicit attempt, elapsed-time, or
shared deadline budget. Space attempts to avoid synchronizing callers and respect authoritative
server guidance. A retry policy must not turn a small failure into unlimited delay or amplified
load.

**Aliases:** retry budget, limited retry, backoff and jitter

## Provenance

**Classification:** Established distributed-systems practice

Finite retry and randomized backoff evolved across networking and production systems. No single
origin is asserted for Athena's combined rule.

## Decision rule

Retry only when another attempt is both safe and reasonably likely to succeed within the caller's
remaining budget; otherwise return the failure.

## How to apply

- Define retryable error categories from the dependency contract, not from a broad catch-all.
- Establish one owner and one total retry budget across nested layers.
- Use a finite attempt count or deadline, exponential backoff, and jitter where many callers can
  synchronize.
- Honor protocol signals such as `Retry-After` without exceeding the caller's deadline.
- Require [P037](p037-idempotency-before-retry.md) for side-effecting operations.
- Stop on cancellation, nontransient failure, exhausted budget, or insufficient remaining time.
- Emit attempt count and final outcome as correlated telemetry; test the policy under overload.

## Boundaries and tensions

A circuit breaker under [P043](p043-circuit-breakers.md) protects against persistent dependency
failure; retry addresses isolated transient failure. Combining them requires clear ordering and
budgets. Retrying at every stack layer multiplies attempts and violates single-owner error policy.

Immediate retry can be appropriate for a rare connection race, but repeated immediate retries
create synchronized load. Backoff must not exceed [P039](p039-bounded-waiting.md), and a queue of
pending retries remains subject to [P040](p040-bounded-resources.md).

## Examples

### Positive application

An idempotent read receives a documented transient status. The client makes at most three attempts
within the request deadline, applies jittered exponential backoff, honors `Retry-After`, and then
returns the final failure.

### Misuse or counterexample

An SDK retries five times, its service wrapper retries the SDK call five times, and a job worker
retries the wrapper indefinitely. One request becomes an uncontrolled retry storm.

### Athena or agent workflow

A coordinator retries a transient subagent transport failure only within its stated iteration and
time budget. A validation failure or permission denial is reported immediately rather than retried.

## Related principles

- [P037 — Idempotency Before Retry](p037-idempotency-before-retry.md)
- [P039 — Bounded Waiting](p039-bounded-waiting.md)
- [P040 — Bounded Resources](p040-bounded-resources.md)
- [P043 — Circuit Breakers](p043-circuit-breakers.md)

## References

### Origin and history

- [Marc Brooker, “Exponential Backoff and Jitter” (2015)](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/)
  — influential practitioner analysis of synchronized contention and randomized backoff; it is not
  claimed as the origin of retry limits.

### Current guidance

- [AWS Builders' Library, Timeouts, retries, and backoff with jitter](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/)
  — production guidance on timeouts, retry multiplication, token budgets, backoff, and jitter.
- [Microsoft Azure Well-Architected Framework, transient faults](https://learn.microsoft.com/en-us/azure/well-architected/design-guides/handle-transient-faults)
  — current guidance requiring finite retries and randomized exponential backoff.

### Further reading

- [Google SRE, Addressing Cascading Failures](https://sre.google/sre-book/addressing-cascading-failures/)
  — explains how retries amplify overload and contribute to cascading failure.

[Back to the engineering principles catalog](../README.md#p038)
