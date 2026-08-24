# P073 — Optimize Only With Evidence

## Definition

Do not add caching, concurrency, batching, specialized data structures, low-level tuning, or
architectural complexity without evidence that the relevant performance or resource constraint
matters. Measure a representative baseline, locate the bottleneck, optimize it, and verify both the
gain and preserved correctness.

**Aliases:** measure before optimizing; evidence-driven optimization.

## Provenance

**Classification:** established principle.

Donald Knuth's 1974 discussion popularized caution about premature optimization, but neither the
general discipline nor Athena's exact wording belongs to one author. Modern profiling and
performance frameworks operationalize the rule with representative measurements.

## Decision rule

Introduce optimization complexity only when an accepted requirement or credible measurement shows
a meaningful constraint, and when before-and-after evidence demonstrates that the proposed change
improves that constraint without unacceptable regressions.

## How to apply

- Define the performance objective, workload, environment, and acceptable trade-offs.
- Establish a reproducible baseline using representative data and end-to-end metrics.
- Profile to find the dominant cost rather than guessing from code appearance.
- Change one attributable factor when practical and compare repeated measurements.
- Retain regression protection or monitoring for the optimized behavior.

## Boundaries and tensions

Evidence can be an explicit latency, memory, cost, or capacity requirement; teams need not wait for a
production incident. Known algorithmic hazards and hard real-time constraints may justify early
design work, but the assumptions must be concrete and testable. Microbenchmarks that ignore the real
workload can mislead. An optimization that breaks correctness, security, readability, or
operability is not an improvement merely because one metric rises.

## Examples

**Positive:** A representative profile shows repeated parsing dominates request latency. A bounded
cache reduces that cost, and load tests confirm latency, memory, and correctness at the target scale.

**Misuse:** Concurrency, caching, and a new service are added because they might make a low-volume
tool faster, with no requirement, baseline, profile, or post-change measurement.

**Athena/agent workflow:** An agent proposes parallel subagents only when tasks are independent and
the coordination cost is justified, rather than treating maximum concurrency as inherently faster.

## Related principles

- [P001 KISS](p001-kiss.md)
- [P002 YAGNI](p002-yagni.md)
- [P012 Evidence Before Modification](p012-evidence-before-modification.md)
- [P072 Technical Evidence Over Preference](p072-technical-evidence-over-preference.md)
- [P080 Make Concurrency Deliberate](p080-make-concurrency-deliberate.md)

## References

### Origin/history

- [Knuth, "Structured Programming with go to Statements" (1974)](https://doi.org/10.1145/356635.356640)
  is a primary source for the influential discussion of premature optimization and critical code
  paths; it is not presented as the sole origin of performance measurement.

### Current guidance

- [Go diagnostics documentation](https://go.dev/doc/diagnostics) explains profiling and tracing as
  tools for locating expensive code and evaluating performance behavior.
- [AWS Well-Architected Performance Efficiency Pillar](https://docs.aws.amazon.com/wellarchitected/latest/performance-efficiency-pillar/welcome.html)
  requires performance indicators, monitoring, load testing, and regular measurement-driven review.

### Further reading

- [Go profile-guided optimization](https://go.dev/doc/pgo) explains why representative production
  profiles are preferred and why narrow microbenchmarks may produce misleading optimization input.

[Back to the engineering principles catalog](../README.md#p073)
