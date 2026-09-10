---
name: finalize-plan
license: BSD-3-Clause
description: Create an issue body after `plan-issue` and `issue-review` approve one exact actor-owned epoch with `GO`. `--draft` is read-only. Stop if an input is missing, foreign, stale, ambiguous, or not verifiable.
argument-hint: "[--draft] ISSUE_NUMBER_OR_URL"
allowed-tools: [Read, Bash, Grep, Glob]
---

# Finalize an approved issue plan

Purpose: Make the approved plan the implementation entry point. Do not convert review history,
suggestions, or generated text into requirements.

Apply the [ASD-STE100 technical-English policy](../TECHNICAL_ENGLISH.md) to this skill and to all
prose that it produces.

Use the shared [issue-planning contract](../../docs/review/issue-planning.md),
[review contract](../../docs/review/common.md),
[review-exchange mechanism](../review-exchange/SKILL.md),
[design-document structure](../../docs/review/design-docs.md),
[language routing](../../docs/review/language-routing.md), and
[behavior-first testing](../../docs/review/behavior-first-testing.md).

## Engineering principles

Use the canonical [engineering-principles catalog](../../docs/principles/README.md) to make these
finalization decisions:

- [P010 Scope Fidelity](../../docs/principles/README.md#p010): Change only the issue body and the two
  sealed, actor-owned comments for the verified epoch.
- [P061 Separate Decision from High-Impact Execution](../../docs/principles/README.md#p061): Before a
  write, make sure that the epoch and authority agree with this skill's delivery contract.
- [P062 Human Approval for Irreversible or High-Risk Actions](../../docs/principles/README.md#p062):
  If the delivery contract gives authority for the write, continue without a second approval.
- [P063 Requirement-to-Code Traceability](../../docs/principles/README.md#p063): Map each source
  requirement to the issue body without information loss.
- [P065 Verify Before Claiming Completion](../../docs/principles/README.md#p065): Before you report
  that finalization is completed, read the issue body. Make sure that it is the same as the approved
  body.
- [P044 Atomicity Where Possible](../../docs/principles/README.md#p044): Use one body update for the
  replacement.
- [P083 Irreversible Actions Last](../../docs/principles/README.md#p083): Do not remove an applicable
  comment before you verify the body update.
- [P031 Propagate Rather Than Swallow](../../docs/principles/README.md#p031): Report each partial or
  unknown outcome. Do not report a different outcome. Do not automatically retry the update.

## Scope and delivery

`--draft` is read-only. If you do not use `--draft`, first revalidate the authority and target under
[P061 Separate Decision from High-Impact Execution](../../docs/principles/README.md#p061). This skill
can then replace the resolved issue body one time. Only after an exact body readback, it can delete
the two sealed, actor-owned plan and review comments. Do not update these items:

- title;
- labels;
- assignment;
- milestone;
- project fields;
- state;
- branches;
- pull requests; or
- repository files.

After the skill removes the intermediate comments, the finalized body must retain the required
provenance.

Use the forge's native issue-body mechanism. The host must have these capabilities:

- authenticate the actor;
- enumerate exact comments;
- delete exact comments;
- read the issue body;
- compare identities;
- make one exact body update; and
- read back that body update.

If one capability is not available, return a ready-to-publish draft. Identify the capability gap.
Do not create plan or review comments to make finalization possible. Do not adopt plan or review
comments for this purpose. Do not edit plan or review comments for this purpose. Do not replace plan
or review comments for this purpose.

## Finalized planning epoch

Call only `issue_exchange.py verify-finalize`. Do not call `inspect`, `prepare-plan`,
`prepare-review`, or `verify-publication`. Do not perform another review. Do not parse carrier prose
or calculate `R/P/V/F` in this skill. The helper is the only parser and calculator for these values.

A planning epoch is one set of these sealed source identities:

- `R` is the canonical digest of the original issue requirements. It contains the exact issue ID,
  title, body, and acceptance criteria before finalization.
- `P` is the plan-source token over one actor-owned
  `<!-- HomericIntelligence:plan-issue -->` comment ID and its complete-body digest.
- `V` is the review-source token over one actor-owned
  `<!-- HomericIntelligence:issue-review -->` comment ID and its complete-body digest.

`P` and `V` must identify different comment IDs. Do not use one comment as both plan and review.

The review must contain the same issue, `R`, plan-comment ID, and `P`. These values must match
exactly. The review must have the exact `GO` verdict. It must not have an unresolved `critical`,
`major`, or other `required` finding. Do not write if an artifact is conditional, partial,
malformed, stale, foreign, duplicated, absent, or not verifiable.

The helper records exactly one marker in the rendered body:
`<!-- HomericIntelligence:finalize-plan R=<R> P=<P> V=<V> F=<F> -->`. It calculates `F` from the
canonical final body with the literal `<F>` placeholder. Do not add, edit, or move the returned
marker. The marker identifies the sealed source identities separately from the generated body. It
also permits later readback verification without recursion.

For migration only, resolve the exact actor-owned legacy aliases in the shared issue-planning contract.
Resolve an existing exact `<!-- athena:finalize-plan R=<R> P=<P> V=<V> F=<F> -->` body marker only as
sealed historical evidence. New finalizations must write the `HomericIntelligence` markers. Do not emit
both marker versions.

## Finalize

1. Exhaust bounded provider pagination. Resolve one exact issue snapshot with its node or URL,
   title, body, state, actor, all comments, and `comments_complete` set to `true`.
2. Build compact and lossless candidate content without a finalization marker.
3. Do not parse a plan marker, review marker, carrier, ledger, or source digest in this skill.
4. Apply [P001 KISS — Keep It Simple, Stupid](../../docs/principles/README.md#p001) only to the
   candidate content.
5. Make the presentation simple.
6. Do not remove a requirement.
7. Do not change the meaning of the approved architecture.
8. Start the candidate content with **Why**.
9. Preserve the original problem, outcome, and requirements that cannot change.
10. If a system diagram makes at least three relationships, boundaries, or state transitions
    clearer, include it.
11. Include the architecture description, implementation plan, operations, and provenance.
12. Preserve all items in this list:

   - acceptance criteria;
   - implementation boundaries;
   - validation;
   - migration or cutover steps;
   - rollback conditions;
   - dependencies;
   - residual risks; and
   - out-of-scope decisions.

13. Unless the reviewed canonical plan adopted a review suggestion, record the suggestion as optional
    residual context.
14. Do not invent files, commands, requirements, architecture, implementation results, or validation
    evidence.
15. If a smaller lossless result is sufficient, do not copy historical revision transcripts.
16. If a smaller lossless result is sufficient, do not duplicate the plan and review verbatim.
17. Call `issue_exchange.py verify-finalize` with the snapshot and candidate content.
18. Accept only a `ready` result. It must include exact `GO`, current matching `R/P/V`, a terminal
    ledger, no coverage gap, and authority receipts for accepted risks.
19. Use the returned body, marker, source values, operation, and deletion allowlist without
    modification.
20. If the user selects `--draft`, return the complete prepared result and do not make a forge write.
21. Immediately before publication, apply
    [P061 Separate Decision from High-Impact Execution](../../docs/principles/README.md#p061).
22. Get a fresh snapshot and call the same preflight form again. Require the same state,
    precondition, and operation.
23. If an input changed, return the ready-to-publish body with the `stale` status. Do not write.
24. Under [P044 Atomicity Where Possible](../../docs/principles/README.md#p044), publish exactly one
    issue-body replacement.
25. Immediately read the issue again. Call the readback form of `verify-finalize` with the snapshot
    and prepared result.
26. Continue only when the helper returns `verified`. Use only its deletion allowlist.
27. If a timeout, indeterminate response, or readback mismatch occurs, report `unknown_outcome`.
    Do not retry or make another mutation.
28. Only after verified body readback, use
    [P083 Irreversible Actions Last](../../docs/principles/README.md#p083) to read each sealed comment
    again.
29. Verify the exact ID, actor, marker, and digest of each listed comment.
30. Delete a listed comment only after its exact verification. Do not delete a foreign,
    replacement, changed, or unlisted comment.
31. If deletion fails, times out, or has an indeterminate result, report `partial_cleanup` and the
    identities of the comments that remain.
32. After a deletion failure, timeout, or indeterminate result, do not retry, compensate, or remove
    the finalized body.

If the final material contains architecture, test, error, or security decisions, preserve the
reviewed use of these principles:

- [P015 Architecture Conformance](../../docs/principles/README.md#p015);
- [P022 Test Behavior, Not Implementation](../../docs/principles/README.md#p022);
- [P029 Generalize Error Policy; Preserve Specific Cause](../../docs/principles/README.md#p029); and
- [P048 Secure by Design](../../docs/principles/README.md#p048).

Finalization does not reopen these decisions. Do not make new decisions.

## Finalize again or restart

If the live body verifies its finalized marker exactly and both sealed comments are absent, a second
run returns a documented `no_change` result. If a sealed comment remains, report
`partial_cleanup`. Its presence does not authorize another deletion attempt. If the marker is
absent, malformed, foreign, or has a canonical `F` mismatch, do not use the epoch as evidence. A
later edit that keeps a stale finalization marker does not authorize a new exchange. After the
sealed comments are removed, an authoritative person can replace the sealed body with clean new
requirements and remove the obsolete marker. The next inspection then starts a new round-1 epoch.
Do not treat generated plan text or provenance fields as new requirements from a person.

## Behavior-first verification

Use controlled issue, comment, actor, and forge fixtures to demonstrate these behaviors:

- A clean `GO` plan and review epoch preserves requirements and operational details.
- `--draft` returns the body without a forge mutation.
- Publication makes one body update. It verifies the exact readback. Then it deletes only the two
  sealed actor-owned comments.
- A sealed epoch that did not change is idempotent.
- Each absent, foreign, duplicate, mismatched, stale, `NO-GO`, required-finding, drift,
  unsupported-write, timeout, readback-mismatch, or deletion-uncertainty case stops before an unsafe
  mutation or retry.

Verify the identities and order classes. Verify content preservation and the number and scope of
mutations. Verify that failures occur before a write. Do not make tests depend on editorial wording,
headings, paragraph counts, or an example issue body.

## Failed approaches

- Do not finalize an epoch again without a new request or a new requirements state.
- Do not treat generated plan text or sealed provenance fields as new executable requirements from
  a person.
- Do not replace behavior-first verification with wording checks. Do not invent files, commands, or
  validation evidence during synthesis.
- After a timeout or readback mismatch, do not retry. Report `unknown_outcome`.
- After an indeterminate deletion, do not retry. Report `partial_cleanup`. State that the deletion
  result is unknown.

## Result

Return these items:

- issue and actor identities;
- `R/P/V/F`;
- the `GO` decision and finding summary;
- the requirement-preservation map;
- the exact `draft`, `no_change`, `published`, `stale`, `partial_cleanup`, or `unknown_outcome`
  status;
- the body-update receipt;
- readback evidence;
- deleted-comment receipts, if present; and
- each unresolved capability or residual risk.
