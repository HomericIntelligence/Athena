# P033 — State-Safe Failure Semantics

## Definition

After an operation fails, every affected resource and state holder must either be unchanged or be
in a documented, valid, recoverable state. The failure path restores invariants, releases resources
deterministically, and does not let later work proceed on state of unknown validity.

This is a postcondition for failure, not a promise that all work can always be rolled back.

**Aliases:** exception safety, valid-state guarantee

## Provenance

**Classification:** Athena synthesis.

Exception-safety guarantees and transaction theory provide established forms of this idea. The
broader language-neutral formulation has no single verified origin.

## Decision rule

Before adding a mutation, define the valid states observable after each failure point. If a partial
effect cannot be prevented, make it explicit, durable, detectable, and recoverable.

## How to apply

- Write invariants and failure postconditions before implementing a multistep mutation.
- Validate inputs and prerequisites before changing state.
- Stage output in temporary state and publish it only after all required work succeeds.
- Use scoped resource ownership so locks, files, connections, and temporary resources are released
  on every exit path.
- Use a transaction for changes that share a transactional boundary; otherwise record durable
  progress and compensation metadata.
- Inject failures between steps and verify the resulting state, cleanup, and recovery path.

## Boundaries and tensions

Failure atomicity is a stronger related guarantee, not an alias: it requires a failed operation to
leave the original state unchanged, while state-safe failure semantics also permit a documented,
valid, recoverable state.

[P044](p044-atomicity-where-possible.md) is the preferred mechanism when one transaction can cover
the logical operation. [P045](p045-compensation-where-atomicity-is-impossible.md) applies when
effects span independent systems or include long-running work. Compensation may reach a valid
business state without recreating the exact previous bytes.

[P034](p034-fail-fast.md) stops unsafe continuation, but termination alone is insufficient if it
leaks resources or leaves an ambiguous partial effect. Conversely, preserving state does not
justify suppressing the failure under [P031](p031-propagate-rather-than-swallow.md).

## Examples

### Positive application

A file generator writes and validates a temporary file, flushes it, and atomically renames it over
the destination. If generation fails, it removes the temporary file and leaves the previous
artifact intact.

### Misuse or counterexample

A migration updates half of a table, catches a later error, and returns success. Neither a rollback
nor a durable checkpoint identifies which rows were changed.

### Athena or agent workflow

An Athena workflow gathers and validates a complete proposed issue body before creating the issue.
If creation fails, it reports failure; it does not claim success or make unrelated follow-up edits
to compensate informally.

## Related principles

- [P031 — Propagate Rather Than Swallow](p031-propagate-rather-than-swallow.md)
- [P034 — Fail Fast](p034-fail-fast.md)
- [P044 — Atomicity Where Possible](p044-atomicity-where-possible.md)
- [P045 — Compensation Where Atomicity Is Impossible](p045-compensation-where-atomicity-is-impossible.md)

## References

### Origin and history

- [Härder and Reuter, “Principles of Transaction-Oriented Database Recovery” (1983)](https://doi.org/10.1145/289.291)
  — foundational treatment of transaction recovery and the ACID terminology used for
  all-or-nothing state changes.
- [Boost, Exception Safety](https://www.boost.org/doc/user-guide/exception-safety.html) — records
  the basic and strong exception-safety guarantees associated with valid state and rollback-like
  behavior; these guarantees are narrower than Athena's system-level rule.

### Current guidance

- [C++ Core Guidelines E.4 and E.6](https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines#e4-design-your-error-handling-strategy-around-invariants)
  — living guidance to design error handling around invariants and use automatic resource
  management to prevent leaks.
- [Microsoft Azure, Compensating Transaction pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/compensating-transaction)
  — current guidance for maintaining recoverability when a multistep operation cannot be atomic.

### Further reading

- [PostgreSQL 18 transaction tutorial](https://www.postgresql.org/docs/18/tutorial-transactions.html)
  — a concrete explanation of all-or-nothing transaction behavior and rollback.

[Back to the engineering principles catalog](../README.md#p033)
