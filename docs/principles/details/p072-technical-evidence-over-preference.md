# P072 — Technical Evidence Over Preference

## Definition

Resolve engineering choices using requirements, specifications, measurements, tests, profiling,
existing architecture, and established engineering principles before subjective taste. Preferences
may choose among approaches only after relevant evidence shows them to be materially equivalent.

**Aliases:** facts over opinions; evidence-based engineering judgment.

## Provenance

**Classification:** practitioner rule.

Evidence-based decision making has broad scientific and engineering roots rather than one software
origin. Google's code-review guidance states the rule directly for review disagreements; Athena
extends it across planning, implementation, validation, and review.

## Decision rule

When approaches conflict, identify the decision-relevant evidence and its quality. Choose the option
best supported by trusted requirements and technical evidence; if evidence is inconclusive and the
options are equivalent, use established convention or the responsible author's preference.

## How to apply

- State the disputed claim and the observation that would distinguish the options.
- Rank evidence by relevance, trustworthiness, reproducibility, and applicability to the workload.
- Prefer accepted requirements and specifications over anecdotes or familiarity.
- Use representative tests, benchmarks, and production data where behavior depends on environment.
- Record consequential evidence and uncertainty so future decisions can be revisited.

## Boundaries and tensions

Measurements and tests can be stale, biased, incomplete, or aimed at the wrong contract; evidence
must be evaluated, not counted. Architecture and principles guide judgment but do not override an
explicit higher-priority requirement. [P071 Consistency](p071-consistency-over-personal-preference.md)
is a useful tie-breaker only when stronger evidence does not favor a change. Lack of data is not
evidence that a risk is absent.

## Examples

**Positive:** Representative profiles identify serialization as the latency bottleneck, so the team
optimizes that path instead of adding concurrency to a component that consumes little time.

**Misuse:** A reviewer blocks a correct, conventional implementation because another syntax "feels
cleaner" and offers no contract, measurement, or design consequence.

**Athena/agent workflow:** When repository prose and executable behavior appear inconsistent, an
agent inspects history, validators, tests, and current policy before recommending which authority
should change.

## Related principles

- [P012 Evidence Before Modification](p012-evidence-before-modification.md)
- [P063 Requirement-to-Code Traceability](p063-requirement-to-code-traceability.md)
- [P065 Verify Before Claiming Completion](p065-verify-before-claiming-completion.md)
- [P071 Consistency Over Personal Preference](p071-consistency-over-personal-preference.md)
- [P073 Optimize Only With Evidence](p073-optimize-only-with-evidence.md)

## References

### Origin/history

- [Google Engineering Practices: The standard of code review](https://google.github.io/eng-practices/review/reviewer/standard.html)
  directly states that technical facts and data overrule opinions and personal preferences; it is a
  practitioner source, not a claim of first origin.

### Current guidance

- [NASA SWE-194: Delivery Requirements Verification](https://swehb.nasa.gov/spaces/SWEHBVD/pages/102695529/SWE-194%2B-%2BDelivery%2BRequirements%2BVerification)
  ties acceptance evidence to requirements, test results, and recorded verification.
- [NIST SSDF 1.1](https://csrc.nist.gov/pubs/sp/800/218/final) provides a risk-based set of secure
  development and verification practices grounded in concrete outcomes.

### Further reading

- [Athena evidence integrity policy](../../policies/evidence-integrity.md) defines how repository
  evidence claims must be bound to reproducible commands, revisions, environments, and real output.

[Back to the engineering principles catalog](../README.md#p072)
