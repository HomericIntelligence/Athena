---
name: plan-issue
description: Draft or publish one canonical implementation plan for a GitHub or GitLab issue after architecture and knowledge review. Use when an issue needs an executable, behavior-first plan; `--draft` is read-only.
argument-hint: "[--draft] ISSUE_NUMBER_OR_URL"
allowed-tools: [Read, Bash, Grep, Glob, Agent]
---

# Plan an issue

Use the shared [issue-planning contract](../../docs/review/issue-planning.md),
[review contract](../../docs/review/common.md),
[language routing](../../docs/review/language-routing.md), and
[behavior-first testing](../../docs/review/behavior-first-testing.md).

## Authority and forge compatibility

`--draft` is read-only and returns a proposed canonical plan. A direct
invocation without `--draft` authorizes exactly the documented canonical-plan
comment action for the resolved issue. It does not authorize implementation,
labels, assignment, commits, pushes, pull requests, merges, or any other forge
mutation. An invocation from another skill does not confer this authority.

Use the forge's native issue API when available: GitHub issue comments or GitLab
work-item notes. If it cannot safely identify or update the actor-owned
canonical plan, stop with a ready-to-publish draft and explain the capability or
ownership gap.

## Required workflow

1. Resolve exactly one issue URL or number in the current repository. Read its
   title, body, labels, linked issues, existing comments, and relevant design
   documents. Do not guess from a similar title.
2. Invoke `advise` with the issue's outcome, architecture, languages, risks,
   and test needs. Its knowledge synchronization must succeed before planning.
3. Apply the architecture gate from the shared review contract. Identify the
   relevant guidance, ADRs, module boundaries, dependency direction, and public
   interfaces before proposing files or abstractions.
4. Discover current code, tests, commands, dependency constraints, and existing
   work. Verify cited paths and symbols against the repository rather than using
   stale issue line numbers or a prior plan as ground truth.
5. Produce one canonical plan that maps every acceptance criterion to concrete
   architecture-respecting changes and functional verification. Include only
   current requirements; reject speculative abstractions and unrelated cleanup.
6. Apply the canonical-plan ownership and marker rules in the issue-planning
   contract. Preserve all foreign issue content. On ambiguity, return the draft
   and stop rather than overwriting a plan.

## Plan content

The canonical plan contains:

- architecture alignment and affected boundaries;
- a requirement-to-step table;
- concrete files, modules, interfaces, state owners, and dependency direction;
- behavior-first tests, error and boundary cases, and runnable validation
  commands discovered from the repository;
- migration, rollout, rollback, security, and operational steps when applicable;
- dependencies, assumptions, and explicit unresolved decisions; and
- a concise scope boundary that names intentionally excluded follow-up work.

Do not assert that a command passed while planning. A plan may name a command,
but only an executed command is evidence. Do not create a prose-string test or
documentation snapshot just to make the plan appear verifiable.

## Output

Report the resolved issue, architecture decision, Mnemosyne revision and
relevant guidance, canonical-plan action or draft, requirement mapping,
validation plan, and every unresolved decision. If the plan was published,
return its forge URL or comment identity; otherwise state why it was not.
