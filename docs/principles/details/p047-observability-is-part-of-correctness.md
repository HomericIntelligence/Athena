# P047 — Observability Is Part of Correctness

## Definition and aliases

Observability is the ability to infer a running system's state and explain its outcomes from emitted
signals such as structured logs, metrics, and traces. It is part of correctness when operators need
that evidence to detect failure, distinguish partial success, and restore service safely.

**Aliases:** operational diagnosability, production visibility, telemetry-by-design.

## Provenance

**Classification:** Athena synthesis.

This synthesis is grounded in established observability practice. Distributed tracing and production
monitoring have long histories, but the exact statement that observability is part of correctness is
a normative engineering rule rather than a uniquely attributable maxim.

## Decision rule

For behavior that matters in operation, emit enough correlated and non-sensitive evidence to answer
what happened, where, when, to which operation, and why. If an important failure cannot be detected
or diagnosed within the required response window, the operational contract is incomplete.

## How to apply

- Define signals from user-visible outcomes and operational questions, not from data availability.
- Correlate work across boundaries with stable request, trace, or operation identifiers.
- Record structured status, reason, duration, and dependency context at the responsible boundary.
- Use metrics for trends and alerting, traces for causal paths, and logs for discrete evidence.
- Set retention, sampling, cardinality, access, and redaction policies before production use.
- Test telemetry for important success, failure, cancellation, and partial-progress paths.

## Boundaries and tensions

Telemetry does not make incorrect behavior correct, and volume is not observability. Excessive or
high-cardinality signals can obscure incidents and exhaust resources. Logs are a data store and an
attack surface: never emit secrets merely to improve diagnosis. Correlation should use safe opaque
identifiers rather than raw customer content. Sampling must retain the evidence needed for critical
security and failure events.

## Examples

### Positive

A multi-service request carries one trace ID. Each boundary records a structured outcome and latency,
while dashboards alert on user-visible errors and traces reveal the failing dependency.

### Misuse

A service writes free-form debug messages containing access tokens but has no request correlation,
outcome metric, or alert. It produces data while remaining unsafe and difficult to diagnose.

### Athena and agent workflows

A delegated task reports its task ID, bounded outcome, validation evidence, and exact failure reason.
It omits credentials and unrelated file content, letting the coordinator distinguish completion from
timeout or partial execution.

## Related principles

- [P046 — Resumability](./p046-resumability.md)
- [P053 — Validate at Trust Boundaries](./p053-validate-at-trust-boundaries.md)
- [P056 — Secrets Stay Out of Code and Context](./p056-secrets-stay-out-of-code-and-context.md)

## References

### Origin and history

- [Google Research: *Dapper, a Large-Scale Distributed Systems Tracing Infrastructure*](https://research.google/pubs/dapper-a-large-scale-distributed-systems-tracing-infrastructure/)
  documents an influential production tracing design and its diagnostic goals.

### Current guidance

- [OpenTelemetry observability primer](https://opentelemetry.io/docs/concepts/observability-primer/)
  describes logs, metrics, traces, correlation, and their relationship to service reliability.
- [OpenTelemetry Specification 1.60.0](https://opentelemetry.io/docs/specs/otel/) is the current
  vendor-neutral instrumentation and telemetry specification at the time of writing.

### Further reading

- [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)
  covers event design, sanitization, sensitive-data exclusion, and protection of collected logs.

[Back to the principles catalog](../README.md#p047)
