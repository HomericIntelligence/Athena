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
[design-document structure](../../docs/review/design-docs.md),
[language routing](../../docs/review/language-routing.md), and
[behavior-first testing](../../docs/review/behavior-first-testing.md).

## Engineering principles

Use the canonical [engineering-principles catalog](../../docs/principles/README.md) to make these
finalization decisions:

- [P010 Scope Fidelity](../../docs/principles/README.md#p010): Change only the issue body for the
  verified epoch.
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

A planning epoch is one set of these sealed source identities:

- `R` is the canonical digest of the original issue requirements. It contains the exact issue ID,
  title, body, and acceptance criteria before finalization.
- `P` identifies one actor-owned `<!-- athena:plan-issue -->` comment ID and its canonical plan-content
  digest.
- `V` identifies one actor-owned `<!-- athena:issue-review -->` comment ID and its review-content
  digest.

The review must contain the same issue, `R`, plan-comment ID, and `P`. These values must match
exactly. The review must have the exact `GO` disposition. It must not have an unresolved `critical`,
`major`, or other `required` finding. Do not write if an artifact is conditional, partial,
malformed, stale, foreign, duplicated, absent, or not verifiable.

Record exactly one marker in the rendered body:
`<!-- athena:finalize-plan R=<R> P=<P> V=<V> F=<F> -->`. Before you calculate `F`, use the literal
`<F>` placeholder as the marker's `F` value. Calculate `F` from the final body. Do not calculate a
digest from a marker that contains its own digest. The marker identifies the sealed source
identities separately from the generated body. It also permits later readback verification without
recursion.

## Finalize

1. Resolve one exact issue with its node or URL, title, body, state, and authenticated actor.
2. Before you interpret a marker, enumerate each current comment.
3. Resolve exactly one actor-owned plan marker.
4. Resolve exactly one actor-owned review marker.
5. Calculate `R/P/V`.
6. Verify the review bindings and the clean `GO` result.
7. If ownership, multiplicity, binding, disposition, or required-finding verification fails, do not
   write.
8. Build a compact and lossless final body.
9. Apply [P001 KISS — Keep It Simple, Stupid](../../docs/principles/README.md#p001) only to the
   sealed content.
10. Make the presentation simple.
11. Do not remove a requirement.
12. Do not change the meaning of the approved architecture.
13. Start the final body with **Why**.
14. Preserve the original problem, outcome, and requirements that cannot change.
15. If a system diagram makes at least three relationships, boundaries, or state transitions
    clearer, include it.
16. Include the architecture description, implementation plan, operations, and provenance.
17. Preserve all items in this list:

   - acceptance criteria;
   - implementation boundaries;
   - validation;
   - migration or cutover steps;
   - rollback conditions;
   - dependencies;
   - residual risks; and
   - out-of-scope decisions.

18. Unless the reviewed canonical plan adopted a review suggestion, record the suggestion as optional
    residual context.
19. Do not invent files, commands, requirements, architecture, implementation results, or validation
    evidence.
20. If a smaller lossless result is sufficient, do not copy historical revision transcripts.
21. If a smaller lossless result is sufficient, do not duplicate the plan and review verbatim.
22. Add the finalized marker.
23. Calculate `F` from its canonical representation that does not contain its own value.
24. If the user selects `--draft`, return the complete body, `R`, `P`, `V`, `F`, and source links.
25. For `--draft`, return all reasons for withheld writes.
26. For `--draft`, do not make a forge write.
27. Immediately before publication, apply
    [P061 Separate Decision from High-Impact Execution](../../docs/principles/README.md#p061).
28. For this check, resolve the issue, actor, each comment and marker, `R`, `P`, `V`, review
    disposition, and target body again.
29. If an input changed, return the ready-to-publish body with the `stale` status.
30. After an input changes, do not write.
31. Under [P044 Atomicity Where Possible](../../docs/principles/README.md#p044), publish exactly one
    issue-body replacement.
32. Immediately read the issue again.
33. Under [P065 Verify Before Claiming Completion](../../docs/principles/README.md#p065), verify the
    exact body, marker, `R`, `P`, `V`, and `F`.
34. If a timeout, indeterminate response, or readback mismatch occurs, report `unknown-outcome`.
35. After a timeout, indeterminate response, or readback mismatch, do not retry.
36. After a timeout, indeterminate response, or readback mismatch, do not make another mutation.
37. Only after a successful body readback, use
    [P083 Irreversible Actions Last](../../docs/principles/README.md#p083) to read each sealed comment
    again.
38. Verify the exact ID, actor, marker, and digest of each sealed comment.
39. Delete the plan comment only after its exact verification.
40. Delete the review comment only after its exact verification.
41. Do not delete a foreign, replacement, or changed comment.
42. If deletion fails, times out, or has an indeterminate result, report `partial-cleanup`.
43. State that an indeterminate deletion result is unknown.
44. After a deletion failure, timeout, or indeterminate result, do not retry.
45. After a deletion failure, timeout, or indeterminate result, do not compensate.
46. After a deletion failure, timeout, or indeterminate result, do not remove the finalized body.
47. After a deletion failure, timeout, or indeterminate result, report the identities of the comments
    that remain.

If the final material contains architecture, test, error, or security decisions, preserve the
reviewed use of these principles:

- [P015 Architecture Conformance](../../docs/principles/README.md#p015);
- [P022 Test Behavior, Not Implementation](../../docs/principles/README.md#p022);
- [P029 Generalize Error Policy; Preserve Specific Cause](../../docs/principles/README.md#p029); and
- [P048 Secure by Design](../../docs/principles/README.md#p048).

Finalization does not reopen these decisions. Do not make new decisions.

## Finalize again or restart

If the live body verifies its finalized marker exactly and both sealed comments are absent, a second
run returns a documented `no-change` result. If a sealed comment remains, report
`partial-cleanup`. Its presence does not authorize another deletion attempt. If the marker is absent,
malformed, foreign, or has a canonical `F` mismatch, do not use the epoch as evidence. A later
substantive edit by a person creates a new requirements state. Before another finalization, this new
state must pass a new `plan-issue` and `issue-review` cycle. Do not treat generated plan text or
provenance fields as new requirements from a person.

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
- After a timeout or readback mismatch, do not retry. Report `unknown-outcome`.
- After an indeterminate deletion, do not retry. Report `partial-cleanup`. State that the deletion
  result is unknown.

## Result

Return these items:

- issue and actor identities;
- `R/P/V/F`;
- the `GO` decision and finding summary;
- the requirement-preservation map;
- the exact `draft`, `no-change`, `published`, `stale`, `partial-cleanup`, or `unknown-outcome`
  status;
- the body-update receipt;
- readback evidence;
- deleted-comment receipts, if present; and
- each unresolved capability or residual risk.
