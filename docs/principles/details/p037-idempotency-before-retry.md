# P037 — Idempotency Before Retry

## Definition

An operation that may run more than once must either produce the same intended effect after repeated
equivalent requests or use an equivalent protection such as an idempotency key, deduplication,
conditional write, or reconciliation. A timeout is an unknown outcome, not evidence that the first
attempt made no state change.

**Aliases:** retry safety, idempotent operation, duplicate suppression

## Provenance

**Classification:** established principle.

Idempotence originates in mathematics and has long been used in protocol design. Athena makes its
ordering relative to retry explicit; no single source is claimed for that phrase.

## Decision rule

Do not enable automatic retry for an operation with side effects until duplicate execution is safe
or uniquely detectable and recoverable.

## How to apply

- Classify the operation's effect and define what “the same request” means semantically.
- Prefer naturally idempotent state-setting operations where the domain allows them.
- For create, charge, send, or publish operations, accept a caller-generated idempotency key bound
  to the authenticated caller and normalized request intent.
- Persist the key and state mutation atomically when possible, including a stable replay response.
- Define key scope, retention, conflict behavior, and handling of late or concurrent duplicates.
- If idempotency is impossible, disable blind retry and provide status lookup or reconciliation.
- Test duplicate, concurrent, timed-out, late-arriving, and same-key/different-intent requests.

## Boundaries and tensions

Idempotency makes duplication safer; it does not make unbounded attempts acceptable. Apply
[P038](p038-bounded-retry.md) and [P039](p039-bounded-waiting.md) as separate controls.

Recording the idempotency key before the mutation, or vice versa, can itself create partial state.
Use [P044](p044-atomicity-where-possible.md) when they share a transaction, or reconciliation and
[P045](p045-compensation-where-atomicity-is-impossible.md) when they do not. A reused key with a
different intent is a conflict, not a replay.

## Examples

### Positive application

A create-job API accepts a client request ID. The server atomically records the normalized payload,
job identifier, and response. Repeated equivalent calls return the same job; a changed payload with
the same key is rejected.

### Misuse or counterexample

A client retries `charge-card` after every timeout without a request key. The first attempt may have
succeeded, so the retry can charge the customer twice.

### Athena or agent workflow

Before retrying an issue-creation request after a lost response, an Athena workflow searches for the
exact planned title and marker or uses the host's idempotency mechanism. It does not assume the issue
was never created.

## Related principles

- [P033 — State-Safe Failure Semantics](p033-state-safe-failure-semantics.md)
- [P038 — Bounded Retry](p038-bounded-retry.md)
- [P039 — Bounded Waiting](p039-bounded-waiting.md)
- [P044 — Atomicity Where Possible](p044-atomicity-where-possible.md)
- [P045 — Compensation Where Atomicity Is Impossible](p045-compensation-where-atomicity-is-impossible.md)

## References

### Origin and history

- [RFC 2068, HTTP/1.1 section 9.1.2 (1997)](https://www.rfc-editor.org/rfc/rfc2068.html#section-9.1.2)
  — an early HTTP standards-track definition of idempotent methods and repeated-request effects;
  idempotence itself predates HTTP.

### Current guidance

- [RFC 9110 section 9.2.2, Idempotent Methods](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2)
  — current HTTP semantics governing when clients can safely repeat requests automatically.
- [AWS Builders' Library, Making retries safe with idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)
  — practitioner guidance on client request identifiers, semantic equivalence, late arrivals, and
  atomic idempotency records.

### Further reading

- [Microsoft Azure, Retry pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/retry)
  — explains why a response failure can occur after successful processing and why retry policy must
  consider idempotency.

[Back to the engineering principles catalog](../README.md#p037)
