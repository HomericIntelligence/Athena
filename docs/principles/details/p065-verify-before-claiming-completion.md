# P065 — Verify Before Claiming Completion

## Definition

Inspect the final change and run the relevant repository-defined checks before claiming that work is
complete or correct. Report exactly what ran, against which revision and environment, what passed or
failed, and what material verification remains unavailable.

**Aliases:** evidence-backed completion; validate before declaring success.

## Provenance

**Classification:** Athena synthesis.

This formulation combines long-standing verification and validation practice with reproducible
software-delivery evidence. No single historical origin is claimed. Athena's evidence-integrity
policy makes truthful, reproducible reporting part of the rule.

## Decision rule

Do not convert expectation into a completion claim. First inspect the delivered state and obtain
fresh evidence appropriate to its risk; then scope the claim to what that evidence actually proves.

## How to apply

- Review the final diff, including generated, staged, and untracked artifacts in scope.
- Run the repository's required tests, build, type, lint, static, security, and packaging checks.
- Use the final revision and relevant environment rather than relying on stale earlier results.
- Record commands, exit status, revision, environment, and meaningful limitations.
- Report failures, skips, unavailable dependencies, and timeouts without inventing substitute
  success.

## Boundaries and tensions

Verification should be proportional: documentation, configuration, and production changes need
different evidence. Passing checks cannot prove requirements that the checks do not exercise, and
an unverified claim does not become true because a run would be expensive. When a required check
cannot run, report the gap and the command or environment that would close it. Never bypass the gate
under [P068 No Validation Bypass](p068-no-validation-bypass.md).

## Examples

**Positive:** An author inspects the final diff, runs the repository's required gate at the current
commit, and reports one unavailable platform test separately rather than saying that all tests pass.

**Misuse:** A developer changes code after a successful test run and cites the earlier run as proof
for the new revision.

**Athena/agent workflow:** Before completion, an agent runs `just all`, reports its actual status,
and names any narrower checks performed when the full gate could not finish.

## Related principles

- [P012 Evidence Before Modification](p012-evidence-before-modification.md)
- [P047 Observability Is Part of Correctness](p047-observability-is-part-of-correctness.md)
- [P064 Requirement-to-Test Traceability](p064-requirement-to-test-traceability.md)
- [P068 No Validation Bypass](p068-no-validation-bypass.md)
- [P072 Technical Evidence Over Preference](p072-technical-evidence-over-preference.md)

## References

### Origin/history

- [NIST IR 8397, Guidelines on Minimum Standards for Developer Verification of Software](https://doi.org/10.6028/NIST.IR.8397)
  records a modern consensus set of broadly applicable verification techniques; no single source is
  treated as the origin of Athena's completion rule.

### Current guidance

- [NIST SSDF 1.1](https://csrc.nist.gov/pubs/sp/800/218/final) defines review, analysis, and testing
  practices used to verify software before release.
- [Google Engineering Practices: What to look for in a code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html)
  requires reviewers to assess functionality, tests, design, and the complete changed context.

### Further reading

- [Athena evidence integrity policy](../../policies/evidence-integrity.md) defines the repository's
  reproducibility and truthful-reporting contract for completion evidence.

[Back to the engineering principles catalog](../README.md#p065)
