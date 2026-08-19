---
name: issue-review
license: BSD-3-Clause
description: Review a GitHub or GitLab issue and its current plan-issue artifact for architecture alignment, scope, risks, and behavior-first verification. Use before implementation; `--report-only` is read-only.
argument-hint: "[--report-only] ISSUE_NUMBER_OR_URL"
allowed-tools: [Read, Bash, Grep, Glob, Agent, WebFetch]
---

# Review an issue and plan

Why: find architecture, scope, and verification gaps while changing the plan is
still cheaper than changing code.

Use the shared [issue-planning contract](../../docs/review/issue-planning.md),
[review contract](../../docs/review/common.md),
[language routing](../../docs/review/language-routing.md), and
[behavior-first testing](../../docs/review/behavior-first-testing.md).

## Scope and delivery

The issue is the requirements source; review only its current canonical plan.
Resolve plan ownership, marker, absence, and identity under the issue-planning
contract. Historical plans and reviews are bounded context, not the artifact
under review.

`--report-only` is read-only. A requested review without it may publish exactly
one actor-owned structured review comment after the required identity comparison
and forge-capability check. It does not expand scope to labels, assignment,
implementation, commit, push, pull request, merge, or issue closure.

## Review

1. Read the issue, linked work, canonical plan, repository guidance, ADRs,
   relevant code, tests, and public contracts.
2. Decide architecture first: aligned, intentional and justified change, or an
   unexplained violation. A material violation blocks a positive assessment.
3. Map every acceptance criterion to a concrete plan step, affected boundary,
   and behavior-first validation step. For a material architecture change,
   verify that the plan includes or cites a
   [design record](../../docs/review/design-docs.md).
4. Verify cited paths, symbols, commands, dependencies, assumptions, risks,
   migration, and rollback claims against current repository evidence.
5. Apply only activated language and change-surface checks, recording N/A
   sections and reasons. Confirm that relevant prior findings are resolved,
   rather than merely acknowledged.

Prioritize architecture violations, missing requirements, unsafe scope,
unresolved dependencies, untestable outcomes, invalid references,
non-deterministic tests, empty selections, and unsupported claims.

When reviewing after a finalized epoch, do not reinterpret generated plan text
or sealed provenance as new requirements. Review only a later material issue
change and its current canonical plan; an unchanged finalized epoch is not a
new review target.

Immediately before a requested publication, re-resolve the canonical planning
identity. On drift, foreign or multiple markers, verified absence changes, or
missing safe forge capability, withhold the comment and return the review as
stale. Otherwise publish exactly one actor-owned structured comment, including
a clean result or verified absent-plan coverage gap.

## Result

Return issue and plan identities, architecture decision first, requirement
mapping, severity-ranked findings, test-quality coverage, N/A sections,
residual risks, and whether the comment was published or withheld. A review
never expands scope to implementation or merge.
