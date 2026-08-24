# P045 — Compensation Where Atomicity Is Impossible

## Definition

When a logical operation spans independent systems or lasts too long for one atomic transaction,
record each completed step and its recovery meaning. If forward progress becomes impossible, run
domain-specific compensating actions to reach a documented valid state. Make both forward and
compensating steps idempotent and resumable, and identify effects that cannot be undone.

**Aliases:** compensating transaction, saga recovery, semantic undo

## Provenance

**Classification:** established principle.

Garcia-Molina and Salem introduced sagas for long-lived transactions in 1987. Compensation also
appears in broader workflow practice; not every compensating workflow is a formal saga.

## Decision rule

Use a real atomic boundary when one safely covers the operation. Otherwise, design durable forward,
compensation, reconciliation, and manual-recovery paths before executing the first side effect.

## How to apply

- Model the workflow as named steps with durable status, correlation, and ownership.
- Define each step's success evidence, idempotency key, compensating action, and retry policy.
- Record enough context before or with each effect to recover after a crash or lost response.
- Order compensation according to business invariants; reverse order is common but not universal.
- Make compensation itself resumable, observable, and safe to repeat.
- Mark points of no return and place irreversible actions after validation and reversible work.
- Escalate ambiguous or failed compensation with exact state and a supported manual procedure.

## Boundaries and tensions

Compensation is not byte-for-byte rollback. Concurrent work may make restoration of the original
state invalid; the correct result is a defined business-equivalent state. A refund, for example,
does not erase the historical charge.

Do not use compensation when [P044](p044-atomicity-where-possible.md) can provide a simpler reliable
transaction. Conversely, do not claim atomicity across independent effects. Each retry must satisfy
[P037](p037-idempotency-before-retry.md), and the workflow's intermediate states must satisfy
[P033](p033-state-safe-failure-semantics.md).

## Examples

### Positive application

A travel workflow records flight and hotel reservations as separate durable steps. If the hotel
cannot be booked and no approved alternative exists, it issues idempotent cancellation commands for
the completed reservations and records each compensation outcome for resumption.

### Misuse or counterexample

A workflow calls three services and, after the third fails, issues best-effort “undo” calls from
memory. A process crash loses which steps succeeded, and repeated undo can create new side effects.

### Athena or agent workflow

Before a multistep externally visible workflow, Athena records which actions are reversible and
which need explicit approval. If a later action fails, it reports completed effects and uses only
predefined, authorized compensation; it does not improvise destructive cleanup.

## Related principles

- [P033 — State-Safe Failure Semantics](p033-state-safe-failure-semantics.md)
- [P037 — Idempotency Before Retry](p037-idempotency-before-retry.md)
- [P044 — Atomicity Where Possible](p044-atomicity-where-possible.md)
- [P046 — Resumability](p046-resumability.md)

## References

### Origin and history

- [Garcia-Molina and Salem, “Sagas” (1987)](https://doi.org/10.1145/38714.38742)
  — primary paper defining a long-lived transaction as a sequence whose partial execution is
  amended with compensating transactions.

### Current guidance

- [Microsoft Azure, Compensating Transaction pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/compensating-transaction)
  — current guidance on durable progress, application-specific undo, idempotent compensation,
  concurrency, and points of no return.
- [AWS Prescriptive Guidance, Saga patterns](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/saga-patterns.html)
  — current guidance on forward recovery, backward recovery, choreography, and orchestration.

### Further reading

- [Microsoft Azure, Design for self-healing](https://learn.microsoft.com/en-us/azure/architecture/guide/design-principles/self-healing)
  — relates compensation to checkpoints, recovery, and resumable long-running work.

[Back to the engineering principles catalog](../README.md#p045)
