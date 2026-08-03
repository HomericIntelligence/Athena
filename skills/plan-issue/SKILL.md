---
name: plan-issue
description: Draft or publish one canonical implementation plan for a GitHub or GitLab issue after architecture and knowledge review. Use when an issue needs an executable, behavior-first plan; `--draft` is read-only.
argument-hint: "[--draft] ISSUE_NUMBER_OR_URL"
allowed-tools: [Read, Bash, Grep, Glob, Agent]
---

# Plan an issue

Why: turn current issue requirements into the smallest architecture-aligned,
behavior-verifiable plan before implementation begins.

Use the shared [issue-planning contract](../../docs/review/issue-planning.md),
[review contract](../../docs/review/common.md),
[language routing](../../docs/review/language-routing.md), and
[behavior-first testing](../../docs/review/behavior-first-testing.md).

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
   needs. Its required knowledge synchronization must finish before planning.
3. Establish architecture before proposing files or abstractions: repository
   guidance, ADRs, boundaries, dependency direction, and public interfaces.
4. Verify current code, tests, commands, dependencies, paths, and symbols.
   Treat the issue and earlier plan as leads, not ground truth.
5. Map each current acceptance criterion to a minimal architecture-respecting
   change and behavior-first validation. Exclude speculative abstractions and
   unrelated cleanup.
6. Follow the canonical-plan content, ownership, and identity rules in the
   issue-planning contract. Preserve foreign content and return the draft on
   ambiguity rather than overwriting it.

For a material architecture decision, include or cite a
[design record](../../docs/review/design-docs.md) that leads with why, then its
block diagram and high-level design before clear component details. Do not
create a durable design artifact for a simple change without a repository need.

Name only repository-discovered validation commands; never claim an unrun
command passed or create a prose-string test to make the plan look verifiable.
Immediately before publication, re-resolve the canonical identity and withhold
the update if the requirements, marker, comment, or plan content drifted.

## Result

Return the issue, architecture decision, Mnemosyne revision and relevant
guidance, plan action or draft, requirement mapping, validation plan, and every
unresolved decision. If published, return the forge URL or comment identity;
otherwise state why publication was withheld.
