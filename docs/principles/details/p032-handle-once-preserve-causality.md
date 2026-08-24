# P032 — Handle Once; Preserve Causality

## Definition

One responsible boundary should own the final policy for a failure. Intermediate layers may add
useful context or telemetry, but should not repeatedly catch, log, and rethrow the same incident.
Any translation must retain the causal chain, stack information, and structured context needed to
diagnose the original failure.

**Aliases:** single-owner error handling, log-or-propagate, exception chaining

## Provenance

**Classification:** Established practitioner rule

Exception chaining is standardized in several languages. The combined “handle once” rule is a
cross-language engineering synthesis rather than a uniquely attributable maxim.

## Decision rule

For each failure, identify the boundary that decides the outcome. Let other layers propagate it,
adding nonduplicative context only when they possess information the responsible boundary cannot
reconstruct.

## How to apply

- Assign final recovery, presentation, and error-level logging to a clear API, process, job, or
  workflow boundary.
- Use native cause chaining or structured error wrapping instead of replacing an error with an
  unrelated message.
- Add context such as operation, safe identifier, or dependency name once, near the layer that
  knows it.
- Correlate retry-attempt telemetry with the final outcome; do not emit every attempt as a separate
  uncorrelated incident.
- Preserve stack and cause fields in structured telemetry while redacting sensitive data.
- Test translated errors for both their stable public category and retained internal cause.

## Boundaries and tensions

“Handle once” does not forbid metrics or low-severity attempt logs at multiple layers. It forbids
multiple layers from presenting the same failure as independent final incidents. Library code may
record diagnostic events when its observability contract requires them, but ownership and
correlation must remain explicit.

The rule complements [P031](p031-propagate-rather-than-swallow.md): propagation preserves failure,
while causality-preserving handling makes the eventual outcome understandable. Security and privacy
controls can restrict what reaches a user without deleting the protected internal chain.

## Examples

### Positive application

A storage client returns a timeout with endpoint metadata. The repository wrapper chains that
error to `ArtifactLoadFailed` with an artifact identifier. The request boundary emits one
correlated error event and returns the stable public error code.

### Misuse or counterexample

Four nested functions each log the same exception at error level and rethrow a newly constructed
exception without its cause. One incident produces four alerts and the original stack disappears.

### Athena or agent workflow

A delegated reviewer reports a tool failure with its command and exit status. The coordinator adds
the affected review phase and reports that single failure to the user instead of restating it as
several unrelated agent failures.

## Related principles

- [P031 — Propagate Rather Than Swallow](p031-propagate-rather-than-swallow.md)
- [P033 — State-Safe Failure Semantics](p033-state-safe-failure-semantics.md)
- [P038 — Bounded Retry](p038-bounded-retry.md)
- [P047 — Observability Is Part of Correctness](p047-observability-is-part-of-correctness.md)

## References

### Origin and history

- [PEP 3134 — Exception Chaining and Embedded Tracebacks](https://peps.python.org/pep-3134/)
  — records the history and rationale for retaining implicit and explicit causes during exception
  translation in Python.
- [John B. Goodenough, “Structured Exception Handling” (1975)](https://doi.org/10.1145/512976.512997)
  — early primary analysis of orderly exception handling; it does not prescribe Athena's exact
  logging rule.

### Current guidance

- [OpenTelemetry semantic conventions for exceptions in logs](https://opentelemetry.io/docs/specs/semconv/exceptions/exceptions-logs/)
  — current conventions for correlated exception records, stack traces, and avoiding duplicate
  representations in instrumentation.
- [C++ Core Guidelines E.17 and E.18](https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines#e17-dont-try-to-catch-every-exception-in-every-function)
  — advises against catching at every function and minimizing explicit handlers.

### Further reading

- [P029 — Generalize Error Policy; Preserve Specific Cause](../README.md#p029) — explains stable
  boundary taxonomies and specific internal diagnostics.

[Back to the engineering principles catalog](../README.md#p032)
