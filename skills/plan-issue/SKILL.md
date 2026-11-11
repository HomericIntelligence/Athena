---
name: plan-issue
license: BSD-3-Clause
description: Draft or publish one implementation plan for a GitHub or GitLab issue. Use this skill after architecture and knowledge review when an issue needs an executable, behavior-first plan. The `--draft` mode is read-only.
argument-hint: "[--draft] ISSUE_NUMBER_OR_URL"
allowed-tools: [Read, Bash, Grep, Glob, Agent]
---

# Plan an issue

Use this skill to create the smallest architecture-aligned plan for the current issue requirements.
Include behavior-first verification in the plan. Create the plan before implementation starts.

Apply the [ASD-STE100 technical-English policy](../TECHNICAL_ENGLISH.md) to this skill and to
all prose that it produces.

Use the [autonomous workflow policy](../../docs/policies/autonomous-workflows.md) for authority,
recovery, resources, validation, and delivery.

## Engineering principles

Use the canonical [engineering-principles catalog](../../docs/principles/README.md) for these
decisions:

- [P010 Scope Fidelity](../../docs/principles/README.md#p010):
  - Do not include work that is not in the issue.
- [P063 Requirement-to-Code Traceability](../../docs/principles/README.md#p063):
  - For each plan step, record a link to the applicable issue requirement.
- [P012 Evidence Before Modification](../../docs/principles/README.md#p012):
  - Before you put files or abstractions in the plan, examine repository evidence. If a source is
    unavailable, say so and proceed with the input you have.
- [P015 Architecture Conformance](../../docs/principles/README.md#p015):
  - When you make the plan, obey established architecture boundaries and dependency directions.
- [P001 KISS — Keep It Simple, Stupid](../../docs/principles/README.md#p001):
  - Select the minimum solution that obeys all current requirements.
- [P002 YAGNI — You Ain't Gonna Need It](../../docs/principles/README.md#p002):
  - If a capability has no specified current requirement, do not add it.
- [P074 Prefer Existing Mechanisms](../../docs/principles/README.md#p074):
  - If an applicable existing mechanism is available, use it.
- [P008 Understand Before Subtracting](../../docs/principles/README.md#p008):
  - Before you plan a removal or consolidation, examine the mechanism's purpose, consumers, and
    contracts.

## Scope and delivery

`--draft` is read-only. If the request does not include `--draft`, you may publish the plan as
one comment on the issue. Create the actor-owned plan comment when it is absent. Update that same
comment on a later round when it exists and you own it. Preserve foreign comments. Do not
implement code. Do not change labels or assignments. Do not create commits. Do not push branches.
Do not create pull requests. Do not merge changes. Do not make other forge changes.

## Plan

1. Resolve exactly one issue in the current repository.
2. Read these sources for the issue:

   - title;
   - body;
   - labels;
   - linked work;
   - comments;
   - applicable design documents.

3. Do not infer requirements from an issue that has a similar title.
4. Invoke `advise` with the outcome, architecture, languages, risks, and test needs.
5. In planning mode, use the best available result from the existing checkout.
6. Do not require upstream synchronization for the planning-mode result.
7. Report the result revision and its limits of trust and freshness.
8. If `advise` gives an explicit no-guidance result, report that result.
9. Continue issue planning after you report the `advise` result.
10. Before you propose files or abstractions, establish the architecture under
    [P015 Architecture Conformance](../../docs/principles/README.md#p015) from these sources:

    - repository guidance;
    - architecture decision records;
    - boundaries;
    - dependency direction;
    - public interfaces.

11. Under [P012 Evidence Before Modification](../../docs/principles/README.md#p012), verify current
    code, tests, commands, dependencies, paths, and symbols.
12. Treat the issue and an earlier plan as sources to verify, not as verified evidence.
13. Under [P063 Requirement-to-Code Traceability](../../docs/principles/README.md#p063), map each
    current acceptance criterion to a minimum architecture-aligned change and behavior-first
    validation.
14. When you compare solution sizes, apply
    [P001 KISS — Keep It Simple, Stupid](../../docs/principles/README.md#p001) and
    [P002 YAGNI — You Ain't Gonna Need It](../../docs/principles/README.md#p002).
15. Prefer an applicable existing mechanism under
    [P074 Prefer Existing Mechanisms](../../docs/principles/README.md#p074).
16. Do not include speculative abstractions or unrelated cleanup.
17. Before you delete or consolidate a mechanism, apply
    [P008 Understand Before Subtracting](../../docs/principles/README.md#p008).
18. Make the plan content simple. Start with the problem and the desired outcome. Preserve each
    issue requirement. Do not remove a requirement. Do not invent files, commands, requirements,
    architecture, or validation evidence.
19. Preserve all content that another actor owns.
20. If ownership is ambiguous, return the draft and name the ambiguity. Do not overwrite content
    with ambiguous ownership.

Activate these shared profiles only for the specified surface:

- For changed behavior, activate
  [P022 Test Behavior, Not Implementation](../../docs/principles/README.md#p022).
- For error contracts, activate
  [P029 Generalize Error Policy; Preserve Specific Cause](../../docs/principles/README.md#p029).
- For security or a new trust boundary, activate
  [P048 Secure by Design](../../docs/principles/README.md#p048).

Do not treat generated plan text as new requirements from a person.

Do not bind plan validity to a moving remote target branch. Before implementation, the plan can name
the commit from which the worktree must start. After work starts, use the recorded worktree start
commit as the initial local review base. Do not update the plan or require a rebase only because the
remote target branch changes. If a permitted rebase or conflict resolution changes candidate
content, update the affected review evidence.

For a material architecture decision, include or cite a design record. Start the design record with
the reason for the decision. Then, give the block diagram and high-level design before clear
component details. Do not create a durable design artifact for a simple change unless the
repository needs it.

Name only validation commands that you find in the repository. Do not claim that a command passed
if you did not run it. Do not create a prose-string test to make the plan appear verifiable.

## Publish

1. Draft the plan comment. Include the marker `<!-- HomericIntelligence:plan-issue -->` as its
   first line so later runs can find it. If the issue already carries a plan comment from you
   (for example one with that marker), update it with the same content. If you cannot tell who
   owns the existing plan comment, return the draft and say why.
2. For `--draft`, return the prepared plan and stop.
3. Immediately before publication, read the issue and the target comment again. If either changed
   in a way that affects the plan, refresh the affected content and prepare again.
4. Publish with the forge's issue-comment mechanism, using the exact prepared bytes. Prefer a
   file-based body over inline text. On GitHub, use
   `gh issue comment <ISSUE_NUMBER> --body-file <PLAN_FILE>` to create a new comment, or
   `gh api --method PATCH repos/<owner>/<repo>/issues/comments/<COMMENT_ID> -F body=@<PLAN_FILE>`
   to update an existing one. On GitLab, use the equivalent `glab` mechanism.
5. Read the comment back when the forge permits it. Report the exact result.
6. If the write fails or its outcome is uncertain, report the outcome honestly. Preserve the
   prepared document. Do not retry a body write until you read the current comment and reconcile
   it.
7. Report what informed the judgement: the issue, its comments, the code and tests you read, and
   the guidance you used. Name what you could not inspect and why. Do not withhold output because
   external or `.git` metadata is missing. Proceed with the input you have.
8. After a successful publication, continue with reviewer assessment within task authority.

Invoke the workflow for the next transition within task authority. Ask only when an actual human
decision remains unresolved. Do not infer a response or approval from old prose.

## Failed approaches

- Do not plan from the issue title alone.
- Do not infer requirements from a similar issue.
- Verify paths, symbols, and commands against current repository evidence before you rely on them.
  Cite the evidence as `file:line`.
- Do not start implementation during planning.
- Do not deliver changes beyond the plan comment.
- Do not claim that a validation command passed if you did not run it.
- Do not overwrite content owned by another actor. If ownership is ambiguous, return the draft.
- Do not treat generated plan text as new requirements from a person.

## Result

Return these items:

- issue identity;
- architecture decision;
- Mnemosyne revision or no-guidance status;
- applicable guidance;
- plan action or draft;
- what informed the judgement, and what you could not inspect;
- requirement mapping;
- validation plan;
- publication result: the forge URL or comment identity, or the reason the publication was
  withheld and the exact state you could verify; and
- each unresolved decision.
