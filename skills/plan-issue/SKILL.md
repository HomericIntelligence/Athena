---
name: plan-issue
license: BSD-3-Clause
description: Draft or publish one canonical implementation plan for a GitHub or GitLab issue. Use this skill after architecture and knowledge review when an issue needs an executable, behavior-first plan. The `--draft` mode is read-only.
argument-hint: "[--draft] ISSUE_NUMBER_OR_URL"
allowed-tools: [Read, Bash, Grep, Glob, Agent]
---

# Plan an issue

Use this skill to create the smallest architecture-aligned plan for the current issue requirements.
Include behavior-first verification in the plan. Create the plan before implementation starts.

Apply the [ASD-STE100 technical-English policy](../TECHNICAL_ENGLISH.md) to this skill and to
all prose that it produces.

Use the shared [issue-planning contract](../../docs/review/issue-planning.md),
[review contract](../../docs/review/common.md),
[review-exchange mechanism](../review-exchange/SKILL.md),
[language routing](../../docs/review/language-routing.md), and
[behavior-first testing](../../docs/review/behavior-first-testing.md).

## Engineering principles

Use the canonical [engineering-principles catalog](../../docs/principles/README.md) for these
decisions:

- [P010 Scope Fidelity](../../docs/principles/README.md#p010):
  - Do not include work that is not in the issue.
- [P063 Requirement-to-Code Traceability](../../docs/principles/README.md#p063):
  - For each plan step, record a link to the applicable issue requirement.
- [P012 Evidence Before Modification](../../docs/principles/README.md#p012):
  - Before you put files or abstractions in the plan, examine repository evidence.
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

`--draft` is read-only. If the request does not include `--draft`, you may create the actor-owned
canonical-plan comment only when it is absent. Otherwise, update that exact retained comment. Never
create a second plan comment. Do not implement code. Do
not change labels or assignments. Do not create commits. Do not push branches. Do not create pull
requests. Do not merge changes. Do not make other forge changes.

Use the native issue-comment mechanism of the forge. If the forge cannot safely identify or update
the actor-owned plan, return a ready-to-publish draft. Explain the capability or ownership gap.

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
18. Follow the canonical-plan content, ownership, and identity rules in the issue-planning contract.
19. Preserve all content that another actor owns.
20. If ownership or identity is ambiguous, return the draft.
21. Do not overwrite content with ambiguous ownership or identity.

Activate these shared profiles only for the specified surface:

- For changed behavior, activate
  [P022 Test Behavior, Not Implementation](../../docs/principles/README.md#p022).
- For error contracts, activate
  [P029 Generalize Error Policy; Preserve Specific Cause](../../docs/principles/README.md#p029).
- For security or a new trust boundary, activate
  [P048 Secure by Design](../../docs/principles/README.md#p048).

If the issue body has a valid finalized-planning marker, use only its sealed provenance as
implementation context. Use the generated plan text for the same purpose. Do not treat them as new
requirements. If the finalized epoch is unchanged, do not create a new plan. A later material edit
that keeps a stale or malformed finalization marker does not authorize a new exchange. After the
sealed comments are removed, an authoritative person can replace the sealed body with clean new
requirements and remove the obsolete marker. The next inspection then starts a new round-1 epoch.
Do not use generated plan text or sealed provenance as the new requirements.

For a material architecture decision, include or cite a
[design record](../../docs/review/design-docs.md). Start the design record with the reason for the
decision. Then, give the block diagram and high-level design before clear component details. Do not
create a durable design artifact for a simple change unless the repository needs it.

Name only validation commands that you find in the repository. Do not claim that a command passed
if you did not run it. Do not create a prose-string test to make the plan appear verifiable.

## Exchange projection

1. Exhaust bounded provider pagination for issue comments. Normalize the current issue snapshot,
   set `comments_complete` to `true`, and run `issue_exchange.py inspect`.
2. For a normal plan, stop unless `next_action` is `prepare_plan`.
3. Declare the plan targets with the supported target kinds in the issue-planning contract.
4. For a continuation, answer every active required finding with `fix`, `fix_with_tradeoff`,
   `contest`, or `risk_acceptance`. When the visible plan changes, also re-answer each required
   finding in `resolved`, `withdrawn`, or `accepted_risk` state. Keep its identifier. Do not re-answer
   a nonblocking finding. A prior risk-acceptance receipt does not authorize the changed plan.
5. Give `scope_change_reason` if and only if the declared target set changes.
6. Run `issue_exchange.py prepare-plan` with the visible plan and author event.
7. For `--draft`, return the prepared result and stop.
8. Before publication, get a fresh snapshot and prepare the operation again.
9. Require the same precondition and exact operation. If they differ, withhold the update.
10. Make only the returned comment create or update operation.
11. Read the issue again and run `issue_exchange.py verify-publication`.
12. After verified publication, stop for reviewer assessment.
13. If the write or readback result is indeterminate, report `unknown_outcome`. Preserve the
    prepared operation and available receipt evidence. Do not retry.

For an explicit requirements reframe, require changed requirements, the exact retained v1 review
state, and one live repository-authoritative receipt. The state can be in any phase,
including `complete`. Call `prepare-plan` with the `reframe` event, that receipt, the old state, and
the new target set. Update the same plan comment and verify its exact readback. This step prepares
the new exchange. It does not complete the reframe or increment the old round. Stop for
`issue-review`, which must verify the same old state, receipt, and target set before it updates the
retained review comment.

The retained plan and review must identify the same current logical state before this reframe. If
the plan has a pending author event that the review has not accepted, stop. Complete and verify one
reviewer assessment before the requirements change. Do not overwrite the pending event or
supersede the older persisted review state.

Do not call this skill again while reviewer assessment, finalization, or human action is due. Do not
infer a response from old prose.

## Failed approaches

- Do not plan from the issue title alone.
- Do not infer requirements from a similar issue.
- Do not include an assumption before you verify paths, symbols, and commands in current repository
  evidence. Cite the evidence as `file:line`.
- Do not start implementation during planning.
- Do not deliver changes beyond the canonical-plan comment.
- Do not claim that a validation command passed if you did not run it.
- Do not overwrite content from another actor if ownership is ambiguous.

## Result

Return these items:

- issue identity;
- architecture decision;
- Mnemosyne revision or no-guidance status;
- applicable guidance;
- plan action or draft;
- exchange state digest and next action;
- exact operation or publication receipt;
- requirement mapping;
- validation plan;
- each unresolved decision.

If you publish the plan, return the forge URL or comment identity. If you withhold publication,
return the helper diagnostics and state the reason.
