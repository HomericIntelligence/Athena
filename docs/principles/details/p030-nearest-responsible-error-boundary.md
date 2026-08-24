# P030 — Handle Errors at the Nearest Responsible Boundary

## Definition

Catch or consume an error only where enough policy and context exist to recover, retry, compensate,
translate, or terminate correctly. Lower layers often detect a failure but should propagate it when
they cannot decide the correct outcome.

**Aliases:** catch where you can handle; responsible error boundary.

## Provenance

**Classification:** practitioner heuristic.

Exception systems formalized stack-based handler selection, and language communities developed
similar catch-or-propagate advice. This exact "nearest responsible boundary" formulation has no
verified single origin.

## Decision rule

Handle a failure at the first boundary that can satisfy the caller's contract and restore or
preserve valid state; otherwise add safe context if needed and propagate it unchanged.

## How to apply

- Distinguish detection, cleanup, translation, recovery, and final presentation.
- Catch narrowly where the layer owns a real recovery or contract-mapping decision.
- Use deterministic cleanup constructs without pretending cleanup recovered the operation.
- Preserve the cause when translating and avoid logging the same failure at every layer.
- Put retries at the boundary that knows idempotency, deadlines, and dependency semantics.

## Boundaries and tensions

The nearest syntactic `catch` site is not necessarily responsible. Top-level boundaries may
legitimately convert an unhandled error into a process exit, protocol response, or job status.
Cleanup can occur below the handling boundary without swallowing the failure. Security policy may
require a generic public result while preserving restricted diagnostics internally.

## Examples

### Positive application

A repository propagates a database timeout. The service, which knows the operation is read-only and
has a deadline, performs one bounded retry; the API boundary then maps exhaustion to its public
unavailable response.

### Misuse or counterexample

A low-level parser catches every exception, logs it, and returns an empty object. Callers cannot
distinguish valid empty input from corruption and proceed with misleading state.

### Athena or agent workflow

A helper reports a typed capability failure. The invoking skill, which owns fallback policy,
decides whether to stop or use its documented degraded path and reports the actual result.

## Related principles

- [P028 — Test Failure Paths, Not Just Success Paths](p028-test-failure-paths.md)
- [P029 — Generalize Error Policy; Preserve Specific Cause](p029-generalize-error-policy-preserve-specific-cause.md)
- [P019 — Explicit Contracts](p019-explicit-contracts.md)

## References

### Origin and history

- [Goodenough, "Exception Handling: Issues and a Proposed Notation" (1975)](https://doi.org/10.1145/361227.361230)
  is an early systematic treatment of exception detection, handler selection, and recovery semantics.

### Current guidance

- [Microsoft, ".NET best practices for exceptions"](https://learn.microsoft.com/en-us/dotnet/standard/exceptions/best-practices-for-exceptions)
  advises catching for recovery or cleanup and propagating when the current code cannot recover.
- [Microsoft, "Exceptions and Exception Handling"](https://learn.microsoft.com/en-us/dotnet/csharp/fundamentals/exceptions/)
  states that a handler should leave the application in a known state or rethrow.

### Further reading

- [Go Blog, "Error handling and Go"](https://go.dev/blog/error-handling-and-go)
  demonstrates explicit propagation and adding caller-relevant context without hiding failure.

[Back to the engineering principles catalog](../README.md#p030)
