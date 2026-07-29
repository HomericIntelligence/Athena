---
name: issue-review
description: Review a GitHub or GitLab issue and its current plan-issue artifact for architecture alignment, scope, risks, and behavior-first verification. Use before implementation; `--report-only` is read-only.
argument-hint: "[--report-only] ISSUE_NUMBER_OR_URL"
allowed-tools: [Read, Bash, Grep, Glob, Agent, WebFetch]
---

# Review an issue and plan

Use the shared [issue-planning contract](../../docs/review/issue-planning.md),
[review contract](../../docs/review/common.md),
[language routing](../../docs/review/language-routing.md), and
[behavior-first testing](../../docs/review/behavior-first-testing.md).

## Authority and artifact identity

`--report-only` is read-only. An explicit direct user request without it
authorizes exactly one actor-owned structured review comment on the resolved
issue. It does not authorize labels, assignments, implementation, commits,
pushes, pull requests, merges, or issue closure. An invocation from another
skill does not confer forge-write authority.

Resolve the issue and the exact current canonical plan using the marker and
ownership rules in the issue-planning contract. The issue is the requirements
source. The current canonical plan is the only plan artifact under review;
historical plans and reviews are bounded context only. If the plan is missing,
ambiguous, or foreign-owned in a way that prevents identity verification, record
the coverage gap and do not invent a favorable decision.

## Required workflow

1. Read the issue, its linked work, current canonical plan, repository guidance,
   relevant ADRs, current code, tests, and public contracts.
2. Establish the architecture decision first: aligned, intentional and justified
   change, or unexplained violation. A material architecture violation blocks a
   positive planning assessment.
3. Verify that every acceptance criterion maps to a concrete plan step,
   architecture boundary, and behavior-first validation step.
4. Check cited files, functions, commands, dependencies, risks, migration or
   rollback paths, and stated assumptions against current repository evidence.
5. Apply only the language and change-surface checks that the plan activates.
   Record N/A sections with reasons.
6. Confirm prior relevant review findings were actually resolved in the current
   plan, rather than merely acknowledged.
7. Immediately before publication, resolve the canonical planning identity
   again and compare the issue ID or URL, requirements digest, actor, comment
   ID or URL, and plan-content digest with the reviewed identity. If any
   component changed or is ambiguous, withhold the comment and return the
   prepared review as stale.

## Findings

Prioritize architecture violations, missing requirements, unsafe scope,
unresolved dependencies, untestable outcomes, invalid paths or symbols,
non-deterministic tests, empty-selection verification, and unsupported claims.
Every finding follows the shared severity and evidence contract.

When publishing, create one structured comment using the actor-owned review
marker only after the pre-publication identity comparison succeeds. Include the
reviewed plan identity, architecture decision, requirement coverage, findings,
N/A sections, and unresolved assumptions. Review prose is evidence only; forge
policy and human review remain authoritative.

## Output

Return the issue and plan identities, architecture decision first, requirements
mapping, severity-ranked findings, test-quality coverage, N/A sections, and
whether the review comment was published or withheld. If no finding remains,
name residual risks and unverified assumptions rather than claiming authority
to implement or merge.
