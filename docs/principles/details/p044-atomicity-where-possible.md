# P044 — Atomicity Where Possible

## Definition

When several state changes form one logical operation and can share a trustworthy transaction
boundary, make their success or failure all-or-none: either every change commits or none does. If
concurrent observers must not see intermediate state, separately choose an isolation level or atomic
publication mechanism that provides that visibility guarantee.

**Aliases:** all-or-nothing update, transactional commit, failure atomicity

## Provenance

**Classification:** established principle.

Atomic transactions predate the ACID acronym. Härder and Reuter's 1983 paper is the primary source
commonly associated with the ACID terminology, not the origin of every form of atomic update.

## Decision rule

If partial completion would violate an invariant and one supported transaction boundary can cover all
effects, use it before designing custom rollback or compensation. Specify suitable isolation or atomic
publication separately when partial visibility would violate an invariant.

## How to apply

- Identify the logical operation, affected state, invariants, and observers.
- Use the datastore, filesystem, message broker, or platform's documented transaction primitives for
  all-or-none commit.
- Select an isolation level or atomic publication primitive that meets the required visibility contract.
- Keep the transaction no broader or longer than required; avoid network calls and user waits while
  holding transactional resources.
- Validate prerequisites before the transaction and defer irreversible external effects until after
  reversible preparation.
- Treat commit acknowledgement loss as an unknown outcome that may require status lookup.
- Test failure before commit, during commit, after commit acknowledgement loss, and under the intended
  concurrent-observation and isolation conditions.

## Boundaries and tensions

Atomicity is scoped: a database transaction does not automatically include an email, remote API,
filesystem, or second datastore. Do not describe a local transaction as end-to-end atomic when
effects escape its boundary.

When one reliable boundary cannot cover the workflow, apply
[P045](p045-compensation-where-atomicity-is-impossible.md) and durable progress rather than inventing
a fragile distributed transaction. [P033](p033-state-safe-failure-semantics.md) remains the broader
post-failure requirement. Atomicity also does not imply isolation level, durability, or business
validity; those guarantees must be specified separately.

## Examples

### Positive application

A database transaction inserts an order and its line items and updates the inventory reservation, so
all changes commit or roll back together. Readers that require a stable multi-object view use an
isolation level that provides it.

### Misuse or counterexample

Code commits an order, then publishes an event, and calls the pair “atomic.” A crash between those
steps leaves committed state without its required notification.

### Athena or agent workflow

An Athena document update is assembled and validated before replacing its target. Related
repository edits are kept in one coherent patch and a failed validation is reported before any
external publication step.

## Related principles

- [P033 — State-Safe Failure Semantics](p033-state-safe-failure-semantics.md)
- [P037 — Idempotency Before Retry](p037-idempotency-before-retry.md)
- [P045 — Compensation Where Atomicity Is Impossible](p045-compensation-where-atomicity-is-impossible.md)
- [P083 — Irreversible Actions Last](../README.md#p083)

## References

### Origin and history

- [Härder and Reuter, “Principles of Transaction-Oriented Database Recovery” (1983)](https://doi.org/10.1145/289.291)
  — primary source for the ACID terminology and transaction-recovery framework.

### Current guidance

- [PostgreSQL 18, Transactions](https://www.postgresql.org/docs/18/tutorial-transactions.html)
  — current database documentation illustrating complete-or-not-at-all updates, visibility, commit,
  and rollback.

### Further reading

- [AWS Builders' Library, Making retries safe with idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)
  — explains why recording an idempotency token and its related mutation may itself require an
  atomic operation.

[Back to the engineering principles catalog](../README.md#p044)
