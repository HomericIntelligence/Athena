# P046 — Resumability

## Definition and aliases

Resumability means that an interrupted long-running operation can continue from durable, verified
progress instead of blindly repeating the whole operation. The saved state must be sufficient to
distinguish work that committed, work that did not commit, and work whose outcome is uncertain.

**Aliases:** checkpoint/restart, durable progress, restartable workflow.

## Provenance

**Classification:** established principle.

No single origin is claimed. Checkpoint and restart techniques predate modern workflow engines;
later systems generalized them from process state to durable application milestones and operation
resources.

## Decision rule

If interruption is plausible and restarting would be costly or unsafe, persist progress at valid
recovery boundaries and make continuation safe. A resume token is useful only when it identifies
compatible state and does not cause completed effects to run twice.

## How to apply

- Assign the operation a stable identity and define terminal, retryable, and indeterminate states.
- Save checkpoints only after the associated state transition is durably committed.
- Store enough version, input, and ownership metadata to reject stale or incompatible checkpoints.
- Make each resumed step idempotent, deduplicated, or reconciled against authoritative state.
- Expose progress and failure information, and define checkpoint retention and cleanup.
- Test interruption before, during, and after each externally visible effect.

## Boundaries and tensions

Resumability is not blind retry. A checkpoint can preserve corrupt or obsolete state, so validate
its integrity and compatibility before use. Very short, cheap, side-effect-free operations may be
safer to restart. Atomic transactions are preferable when one boundary can cover the operation;
distributed work may instead need compensation. Resuming must preserve current authorization and
must not reuse expired credentials or approvals.

## Examples

### Positive

A migration records the last committed batch, schema version, input digest, and operation ID. After
interruption it verifies those fields, reconciles the last batch, and continues at the next batch.

### Misuse

A worker stores only `step = 4`. It crashes after sending a payment but before advancing the step;
restart sends the payment again because the checkpoint does not describe the uncertain effect.

### Athena and agent workflows

A coordinator records completed task IDs, accepted artifact hashes, and outstanding dependencies.
After a host interruption it revalidates the checkout and resumes only unfinished tasks rather than
replaying every delegated action.

## Related principles

- [P044 — Atomicity Where Possible](./p044-atomicity-where-possible.md)
- [P045 — Compensation Where Atomicity Is Impossible](./p045-compensation-where-atomicity-is-impossible.md)
- [P047 — Observability Is Part of Correctness](./p047-observability-is-part-of-correctness.md)
- [P053 — Validate at Trust Boundaries](./p053-validate-at-trust-boundaries.md)

## References

### Origin and history

- [USENIX: *Libckpt: Transparent Checkpointing under UNIX* (1995)](https://www.usenix.org/conference/usenix-1995-technical-conference/libckpt-transparent-checkpointing-under-unix)
  documents checkpoint/restart as a way to recover long-running computation without starting over.

### Current guidance

- [Google AIP-151: Long-running operations](https://google.aip.dev/151) defines a durable operation
  resource through which clients can track progress and later retrieve a result.
- [AWS Step Functions redrive guidance](https://docs.aws.amazon.com/step-functions/latest/dg/redrive-executions.html)
  documents resuming failed workflows from unsuccessful steps while preserving successful results.

### Further reading

- [USENIX: *Transparent Checkpoint-Restart of Multiple Processes*](https://www.usenix.org/legacy/event/usenix07/tech/full_papers/laadan/laadan_html/paper.html)
  explains consistency requirements when a checkpoint spans cooperating processes and shared state.

[Back to the principles catalog](../README.md#p046)
