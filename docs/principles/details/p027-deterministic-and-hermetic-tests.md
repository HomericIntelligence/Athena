# P027 — Deterministic and Hermetic Tests

## Definition

Make tests repeatable by controlling their inputs and isolating them from undeclared external
influences such as time, randomness, environment variables, filesystem state, networks, locale,
concurrency, and shared services. Tests should be independent of execution order.

**Aliases:** isolated tests; reproducible tests; hermetic testing.

## Provenance

**Classification:** established modern testing principle.

Determinism and test isolation have long histories, while "hermetic" became common in large
build-and-test systems. No single origin for the combined formulation is established.

## Decision rule

A test must declare or control every input that can affect its result and must neither depend on nor
leak mutable state across executions.

## How to apply

- Inject clocks, random generators, environment access, and external clients where needed.
- Use per-test temporary resources and deterministic cleanup.
- Replace live networks with controlled local substitutes except in explicitly scoped integration
  or acceptance suites.
- Record seeds and schedules for generated or concurrent tests, then preserve counterexamples.
- Run tests alone, in different orders, and in parallel where the harness supports it.

## Boundaries and tensions

Deterministic and hermetic are related but distinct: a test can be deterministic while depending on
a fixed external service, or hermetic while using uncontrolled randomness. Full isolation can hide
real integration failures, so maintain explicitly labeled non-hermetic suites with controlled
environments. Retries may diagnose flakiness but must not redefine an unreliable test as passing.

## Examples

### Positive application

A cache-expiry test receives a fake clock and a fresh temporary directory. It advances time
explicitly and produces the same result regardless of machine timezone or test order.

### Misuse or counterexample

A test calls a public web service and retries until it passes. Availability, remote data, DNS, and
rate limits now decide whether an unchanged revision is green.

### Athena or agent workflow

A repository validator test builds an isolated fixture tree, supplies every environment value, and
invokes the helper without using a user's checkout or network credentials.

## Related principles

- [P022 — Test Behavior, Not Implementation](p022-test-behavior-not-implementation.md)
- [P025 — Property-Based Testing for Invariants](p025-property-based-testing-for-invariants.md)
- [P028 — Test Failure Paths, Not Just Success Paths](p028-test-failure-paths.md)

## References

### Origin and history

- [Google Testing Blog, "Hermetic Servers" (2012)](https://testing.googleblog.com/2012/10/hermetic-servers.html)
  explains isolation from live network dependencies in end-to-end testing.

### Current guidance

- [Bazel, "Hermeticity"](https://bazel.build/basics/hermeticity)
  documents declared inputs, fixed environment properties, and isolation for deterministic build
  and test results.
- [Microsoft, ".NET unit testing best practices"](https://learn.microsoft.com/en-us/dotnet/core/testing/unit-testing-best-practices)
  identifies isolation and repeatability as core test characteristics.

### Further reading

- [Google Testing Blog, "Flaky Tests at Google and How We Mitigate Them" (2016)](https://testing.googleblog.com/2016/05/flaky-tests-at-google-and-how-we.html)
  reports causes and operational costs of nondeterministic test results.

[Back to the engineering principles catalog](../README.md#p027)
