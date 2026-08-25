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

`--draft` is read-only. If the request does not include `--draft`, you may publish only the
actor-owned canonical-plan issue comment in the issue-planning contract. Do not implement code,
change labels or assignments, create commits, push branches, create pull requests, merge changes,
or make other forge changes.

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
7. Report the result revision and its limits of trust and freshness. If `advise` gives an explicit
   no-guidance result, report that result.
8. Continue issue planning after you report the `advise` result.
9. Before you propose files or abstractions, establish the architecture under
   [P015 Architecture Conformance](../../docs/principles/README.md#p015) from these sources:

   - repository guidance;
   - architecture decision records;
   - boundaries;
   - dependency direction;
   - public interfaces.

10. Under [P012 Evidence Before Modification](../../docs/principles/README.md#p012), verify current
   code, tests, commands, dependencies, paths, and symbols.
11. Treat the issue and an earlier plan as sources to verify, not as verified evidence.
12. Under [P063 Requirement-to-Code Traceability](../../docs/principles/README.md#p063), map each
    current acceptance criterion to a minimum architecture-aligned change and behavior-first
    validation.
13. When you compare solution sizes, apply
    [P001 KISS — Keep It Simple, Stupid](../../docs/principles/README.md#p001) and
    [P002 YAGNI — You Ain't Gonna Need It](../../docs/principles/README.md#p002).
14. Prefer an applicable existing mechanism under
    [P074 Prefer Existing Mechanisms](../../docs/principles/README.md#p074).
15. Do not include speculative abstractions or unrelated cleanup.
16. Before you delete or consolidate a mechanism, apply
    [P008 Understand Before Subtracting](../../docs/principles/README.md#p008).
17. Follow the canonical-plan content, ownership, and identity rules in the issue-planning contract.
18. Preserve all content that another actor owns.
19. If ownership or identity is ambiguous, return the draft.
20. Do not overwrite content with ambiguous ownership or identity.

Activate these shared profiles only for the specified surface:

- For changed behavior, activate
  [P022 Test Behavior, Not Implementation](../../docs/principles/README.md#p022).
- For error contracts, activate
  [P029 Generalize Error Policy; Preserve Specific Cause](../../docs/principles/README.md#p029).
- For security or a new trust boundary, activate
  [P048 Secure by Design](../../docs/principles/README.md#p048).

If the issue body has a valid finalized-planning marker, use its sealed provenance and generated
plan text only as implementation context. Do not treat them as new requirements. If the finalized
epoch is unchanged, do not create a new plan. If a later material edit changes the issue body,
start a new requirements state. Plan from that edit under the issue-planning contract.

For a material architecture decision, include or cite a
[design record](../../docs/review/design-docs.md). Start the design record with the reason for the
decision. Then, give the block diagram and high-level design before clear component details. Do not
create a durable design artifact for a simple change unless the repository needs it.

Name only validation commands that you find in the repository. Do not claim that a command passed
if you did not run it. Do not create a prose-string test to make the plan appear verifiable.
Immediately before publication, resolve the canonical identity again. If the requirements, marker,
comment, or plan content changed, withhold the update.

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
- requirement mapping;
- validation plan;
- each unresolved decision.

If you publish the plan, return the forge URL or comment identity. If you withhold publication,
state the reason.
