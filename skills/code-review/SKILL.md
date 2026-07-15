---
name: code-review
description: Review completed implementation work for correctness, regressions, maintainability, security, and test quality before merge.
argument-hint: <what was implemented>
allowed-tools: [Read, Bash, Grep, Glob, Agent]
---

# Code review

Use this after a substantial change, complex fix, or before merge. Review technical evidence, not
the author's confidence.

## Workflow

1. Read `AGENTS.md`, the requirements, and relevant plans or issues.
2. Keep the target repository as the current working directory. Resolve `scripts/review_diff.py`
   against this installed skill directory and invoke that absolute helper path. The helper discovers
   the target branch remote and its default branch, fetches that exact base, reports the resolved
   metadata, and prints both the merge-base diff summary and complete diff. Stop if the remote or
   default branch cannot be resolved unambiguously.

3. Delegate to one independent reviewer when the host supports subagents. Do not prescribe a vendor
   model. If delegation is unavailable, review sequentially in the current agent.
4. Inspect correctness, requirement alignment, security boundaries, error handling, public API
   compatibility, tests, documentation, and unnecessary complexity.
   Apply the KISS, YAGNI, TDD, DRY, SOLID, modularity, least-astonishment, durable-artifact, and
   behavior-test rules in [`../../docs/policies/development.md`](../../docs/policies/development.md).
   Flag tests that pin prose or flaky implementation detail and artifacts that create ongoing
   manual synchronization without a demonstrated product consumer.
5. Run the repository-defined focused tests and quality gates. Never invent successful output.
6. Rank findings as critical, important, or suggestion. Include a path and line, impact, evidence,
   and concrete remediation for each finding.
7. Verify reviewer claims before changing code. Push back with evidence when a finding is incorrect.

## Output

- Scope and diff reviewed
- Strengths
- Critical findings
- Important findings
- Suggestions
- Verification commands and results
- Verdict: ready, ready after listed fixes, or not ready

Do not post review comments or mutate GitHub state unless the user explicitly requests it.
