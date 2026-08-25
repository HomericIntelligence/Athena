---
name: plan-issue
license: BSD-3-Clause
description: Draft or publish one canonical implementation plan for a GitHub or GitLab issue after architecture and knowledge review. Use when an issue needs an executable, behavior-first plan; `--draft` is read-only.
argument-hint: "[--draft] ISSUE_NUMBER_OR_URL"
allowed-tools: [Read, Bash, Grep, Glob, Agent]
---

# Plan an issue

Why: turn current issue requirements into the smallest architecture-aligned,
behavior-verifiable plan before implementation begins.

Apply the [ASD-STE100 writing policy](../../docs/technical-english.md) to this skill and to all prose
that it produces.

Use the shared [issue-planning contract](../../docs/review/issue-planning.md),
[review contract](../../docs/review/common.md),
[language routing](../../docs/review/language-routing.md), and
[behavior-first testing](../../docs/review/behavior-first-testing.md).

## Engineering principles

Apply the canonical [engineering-principles catalog](../../docs/principles/README.md) through these
planning decisions:

- [P010 Scope Fidelity](../../docs/principles/README.md#p010) and
  [P063 Requirement-to-Code Traceability](../../docs/principles/README.md#p063) map every plan step to
  the exact issue requirements and exclude unrelated work.
- [P012 Evidence Before Modification](../../docs/principles/README.md#p012) and
  [P015 Architecture Conformance](../../docs/principles/README.md#p015) require repository evidence
  and established boundaries to shape the plan before files or abstractions are proposed.
- [P001 KISS — Keep It Simple, Stupid](../../docs/principles/README.md#p001),
  [P002 YAGNI — You Ain't Gonna Need It](../../docs/principles/README.md#p002), and
  [P074 Prefer Existing Mechanisms](../../docs/principles/README.md#p074) select the smallest current,
  architecture-aligned solution using an appropriate existing mechanism where possible.
- [P008 Understand Before Subtracting](../../docs/principles/README.md#p008) requires verified purpose,
  consumers, and contracts before a plan removes or consolidates an existing mechanism.

## Scope and delivery

`--draft` is read-only. A requested plan without it may publish only the
actor-owned canonical-plan issue comment described by the issue-planning
contract; it does not expand scope to implementation, labels, assignments, commits,
pushes, pull requests, merges, or other forge mutations.

Use the forge's native issue-comment mechanism. If it cannot safely identify or
update the actor-owned plan, return a ready-to-publish draft and explain the
capability or ownership gap.

## Plan

1. Resolve one exact issue in the current repository. Read its title, body,
   labels, linked work, comments, and relevant design documents; never infer
   requirements from a similar title.
2. Invoke `advise` with the outcome, architecture, languages, risks, and test
   needs. In planning mode, use its existing-checkout best-effort result without requiring upstream
   synchronization; report its revision and trust/freshness limits, or its explicit no-guidance
   result, and continue issue planning.
3. Establish architecture under
   [P015 Architecture Conformance](../../docs/principles/README.md#p015) before proposing files or
   abstractions: repository guidance, ADRs, boundaries, dependency direction, and public interfaces.
4. Under [P012 Evidence Before Modification](../../docs/principles/README.md#p012), verify current
   code, tests, commands, dependencies, paths, and symbols.
   Treat the issue and earlier plan as leads, not ground truth.
5. Map each current acceptance criterion to a minimal architecture-respecting change and
   behavior-first validation under
   [P063 Requirement-to-Code Traceability](../../docs/principles/README.md#p063). Apply
   [P001 KISS — Keep It Simple, Stupid](../../docs/principles/README.md#p001) and
   [P002 YAGNI — You Ain't Gonna Need It](../../docs/principles/README.md#p002) when comparing
   solution size, and prefer an
   applicable existing mechanism under
   [P074 Prefer Existing Mechanisms](../../docs/principles/README.md#p074). Exclude speculative
   abstractions and unrelated cleanup. Before deleting or consolidating a mechanism, apply
   [P008 Understand Before Subtracting](../../docs/principles/README.md#p008).
6. Follow the canonical-plan content, ownership, and identity rules in the
   issue-planning contract. Preserve foreign content and return the draft on
   ambiguity rather than overwriting it.

Activate other shared profiles only when the planned surface requires them:
[P022 Test Behavior, Not Implementation](../../docs/principles/README.md#p022) for changed behavior,
[P029 Generalize Error Policy; Preserve Specific Cause](../../docs/principles/README.md#p029) for
error contracts, and [P048 Secure by Design](../../docs/principles/README.md#p048) for security or new
trust boundaries.

When the issue body carries a valid finalized-planning marker, treat its sealed
provenance and generated plan text as implementation-facing context, not new
requirements. An unchanged finalized epoch needs no new plan. A later material
issue-body edit starts a fresh requirements state and must be planned from that
edit under the issue-planning contract.

For a material architecture decision, include or cite a
[design record](../../docs/review/design-docs.md) that leads with why, then its
block diagram and high-level design before clear component details. Do not
create a durable design artifact for a simple change without a repository need.

Name only repository-discovered validation commands; never claim an unrun
command passed or create a prose-string test to make the plan look verifiable.
Immediately before publication, re-resolve the canonical identity and withhold
the update if the requirements, marker, comment, or plan content drifted.

## Failed approaches

- Planning from the issue title alone or inferring requirements from a similar issue.
- Embedding unverified assumptions instead of verifying paths, symbols, and commands against
  current repository evidence and citing `file:line`.
- Starting implementation during planning, or expanding delivery past the canonical-plan comment.
- Claiming an unrun validation command passed, or overwriting foreign plan content on ambiguity.

## Result

Return the issue, architecture decision, Mnemosyne revision or no-guidance status and relevant
guidance, plan action or draft, requirement mapping, validation plan, and every unresolved decision.
If published, return the forge URL or comment identity; otherwise state why publication was withheld.
