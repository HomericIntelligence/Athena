# P031 — Propagate Rather Than Swallow

## Definition

A layer that cannot completely and correctly recover from a failure must return, throw, signal, or
otherwise propagate that failure to a boundary that can decide the outcome. It must not replace a
real failure with apparent success, an empty value, or unqualified continuation.

Propagation preserves the distinction between “the operation succeeded” and “the caller still has
work to do because it failed.” That distinction is part of the contract, not merely a diagnostic
detail.

**Aliases:** error propagation, no silent catch, surface unrecovered failures

## Provenance

**Classification:** Established error-handling principle

Structured exception handling has a long published history, but this exact phrase has no single
verified origin. Athena uses it as a language-neutral decision rule.

## Decision rule

Handle a failure only when the current boundary can restore its promised postconditions or produce
an explicitly documented alternative result. Otherwise, preserve the failure and send it upward.

## How to apply

- State failure behavior in return types, exceptions, result objects, exit statuses, or protocol
  responses.
- Catch only the failures for which the layer can retry, compensate, translate, or terminate with
  the necessary policy context.
- When translating an implementation-specific error, retain the original cause and add stable,
  caller-relevant context.
- Make fallback values explicit in the API. A fallback is a successful alternate outcome only when
  the contract says so and the caller can distinguish it when that distinction matters.
- Test that failed dependencies produce a failed public outcome and do not leave partial state.

## Boundaries and tensions

Propagation does not mean that every internal exception must escape unchanged. A boundary may
translate it into a stable error taxonomy, but should preserve causality under
[P032](p032-handle-once-preserve-causality.md). It also does not prohibit
[P036](p036-graceful-degradation.md): a documented, safe reduced mode can be a valid outcome.

Security-sensitive uncertainty still follows [P035](p035-fail-secure-fail-closed.md). Do not expose
secret values, credentials, or unnecessary internal detail merely to preserve a cause; retain that
information in appropriately protected diagnostics.

## Examples

### Positive application

A repository adapter cannot read a required record. It attaches the record identifier to the
storage error and returns it. The service boundary then maps that failure to its documented API
error while retaining the original cause for protected diagnostics.

### Misuse or counterexample

A configuration loader catches every parsing exception, returns an empty configuration, and lets
startup report success. The service later behaves incorrectly and the actionable parse failure is
lost.

### Athena or agent workflow

If a required validation command exits nonzero, an Athena workflow reports the failed command and
evidence. It does not declare completion because earlier checks passed or because the error can be
omitted from the summary.

## Related principles

- [P032 — Handle Once; Preserve Causality](p032-handle-once-preserve-causality.md)
- [P033 — State-Safe Failure Semantics](p033-state-safe-failure-semantics.md)
- [P034 — Fail Fast](p034-fail-fast.md)
- [P036 — Graceful Degradation](p036-graceful-degradation.md)

## References

### Origin and history

- [John B. Goodenough, “Structured Exception Handling” (1975)](https://doi.org/10.1145/512976.512997)
  — early primary treatment of detecting exception conditions and transferring control to an
  appropriate handler; it is not claimed as the origin of Athena's wording.

### Current guidance

- [The Rust Programming Language: Propagating Errors](https://doc.rust-lang.org/book/ch09-02-recoverable-errors-with-result.html#propagating-errors)
  — official language guidance showing how a callee returns an error when its caller has the
  context needed to decide what to do.
- [C++ Core Guidelines, Error Handling](https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines#S-errors)
  — living guidance that recommends a deliberate error strategy and cautions against catching in
  every function.

### Further reading

- [P029 — Generalize Error Policy; Preserve Specific Cause](../README.md#p029) — the companion
  catalog rule for translating errors without losing diagnostic specificity.

[Back to the engineering principles catalog](../README.md#p031)
