---
name: finalize-plan
license: BSD-3-Clause
description: Create an issue body after `plan-issue` and `issue-review` deliver their results. `--draft` is read-only. Preserve foreign comments. Missing cleanup capability does not block an authorized body update.
argument-hint: "[--draft] ISSUE_NUMBER_OR_URL"
allowed-tools: [Read, Bash, Grep, Glob]
---

# Finalize an issue plan

Purpose: Make the delivered plan the implementation entry point. Do not convert review history,
suggestions, or generated text into requirements.

Apply the [ASD-STE100 technical-English policy](../TECHNICAL_ENGLISH.md) to this skill and to all
prose that it produces.

Use the [autonomous workflow policy](../../docs/policies/autonomous-workflows.md) for authority,
recovery, resources, validation, and delivery.

## Engineering principles

Use the canonical [engineering-principles catalog](../../docs/principles/README.md) to make these
finalization decisions:

- [P010 Scope Fidelity](../../docs/principles/README.md#p010): Change only the issue body and, when
  cleanup is authorized, the actor-owned plan and review comments.
- [P061 Separate Decision from High-Impact Execution](../../docs/principles/README.md#p061): Before a
  write, make sure the target and your authority for the write agree with this skill's delivery
  contract.
- [P062 Human Approval for Irreversible or High-Risk Actions](../../docs/principles/README.md#p062):
  If the delivery contract gives authority for the write, continue without a second approval.
- [P063 Requirement-to-Code Traceability](../../docs/principles/README.md#p063): Map each source
  requirement to the issue body without information loss.
- [P065 Verify Before Claiming Completion](../../docs/principles/README.md#p065): Before you report
  that finalization is completed, read the issue body. Make sure that it is the intended body.
- [P044 Atomicity Where Possible](../../docs/principles/README.md#p044): Use one body update for the
  replacement.
- [P083 Irreversible Actions Last](../../docs/principles/README.md#p083): Do not remove an applicable
  comment before you verify the body update.
- [P031 Propagate Rather Than Swallow](../../docs/principles/README.md#p031): Report each partial or
  unknown outcome. Reconcile exact readback before retrying an uncertain update.

## Scope and delivery

`--draft` is read-only. If you do not use `--draft`, first revalidate the target and your authority
under [P061 Separate Decision from High-Impact Execution](../../docs/principles/README.md#p061). This skill
can then replace the resolved issue body one time. Only after the body update is read back, it can
delete actor-owned plan and review comments when cleanup is authorized. Do not update these items:

- title;
- labels;
- assignment;
- milestone;
- project fields;
- state;
- branches;
- pull requests; or
- repository files.

Use the forge's native issue-body mechanism. The host should have these capabilities:

- authenticate the actor;
- enumerate exact comments;
- delete exact owned comments, only when cleanup is available and authorized;
- read the issue body;
- make one exact body update; and
- read back that body update.

If a body-write capability is unavailable after recovery, return a ready-to-publish draft and
exact manual command. Missing comment deletion does not block the body update. Preserve foreign
comments. Do not adopt, edit, or replace plan or review comments from another actor.

## Finalize

1. Read the issue title, body, and comments. Read the plan comment and the review comment when
   they exist. Read applicable repository context. If Git or forge metadata is absent, proceed
   with the input you have; do not withhold the output because metadata is missing.
2. Report what informed the judgement: the issue, the plan comment, the review comment, and the
   repository files you read. Name what you could not inspect and why.
3. Build the candidate body. It has no finalization marker:

   - Start with **Why**.
   - Preserve the original problem, outcome, and requirements that cannot change.
   - Keep the architecture description, the implementation plan, and the operations summary.
   - If a system diagram makes at least three relationships, boundaries, or state transitions
     clearer, include it.
   - Preserve all items in this list:

     - acceptance criteria;
     - implementation boundaries;
     - validation;
     - migration or cutover steps;
     - rollback conditions;
     - dependencies;
     - residual risks; and
     - out-of-scope decisions.

   - Unless the reviewed plan adopted a review suggestion, record the suggestion as optional
     residual context.
   - Do not invent files, commands, requirements, architecture, implementation results, or
     validation evidence.
   - Do not remove a requirement. Do not change the meaning of the approved architecture.
   - If a smaller lossless result is sufficient, do not copy historical revision transcripts.
   - If a smaller lossless result is sufficient, do not duplicate the plan and review verbatim.

4. Apply [P001 KISS — Keep It Simple, Stupid](../../docs/principles/README.md#p001) to the candidate
   content. Make the presentation simple.
5. Make sure the candidate content is complete with respect to the requirements. If a requirement
   cannot be mapped, say so in the delivery instead of dropping it silently.
6. If the user selects `--draft`, return the complete prepared result and do not make a forge write.
7. Immediately before publication, apply
   [P061 Separate Decision from High-Impact Execution](../../docs/principles/README.md#p061). Read the
   issue again. If the issue or the target comment changed in a way that affects the body, refresh
   the affected content and prepare the body again.
8. Under [P044 Atomicity Where Possible](../../docs/principles/README.md#p044), publish exactly one
   issue-body replacement with the forge's issue-body mechanism, using the exact candidate bytes.
   On GitHub, use `gh issue edit <NUMBER> --repo <owner>/<repo> --body-file <BODY_FILE>`. On
   GitLab, use the equivalent `glab` mechanism.
9. Immediately read the issue body again. Report the exact readback result.
10. If the write fails or its outcome is uncertain, report the outcome honestly. Do not retry a
    body write until you read the current body and reconcile it.
11. Only after the body update is read back as intended, and only when cleanup is authorized, use
    [P083 Irreversible Actions Last](../../docs/principles/README.md#p083) to read each actor-owned
    plan and review comment again.
12. Delete a comment only if it is an actor-owned comment with its plan or review identity (for
    example `<!-- HomericIntelligence:plan-issue -->` or
    `<!-- HomericIntelligence:issue-review -->`). Skip and report any foreign, changed, or ambiguous
    comment.
13. If deletion fails, times out, or has an indeterminate result, report which comments remain.
    Preserve the finalized body. Reconcile comment state before retrying an authorized deletion.
    Missing cleanup capability leaves comments intact and does not undo the body publication.

If the final material contains architecture, test, error, or security decisions, preserve the
reviewed use of these principles:

- [P015 Architecture Conformance](../../docs/principles/README.md#p015);
- [P022 Test Behavior, Not Implementation](../../docs/principles/README.md#p022);
- [P029 Generalize Error Policy; Preserve Specific Cause](../../docs/principles/README.md#p029); and
- [P048 Secure by Design](../../docs/principles/README.md#p048).

Finalization does not reopen these decisions. Do not make new decisions.

## Finalize again or restart

If the live body already matches the prepared candidate and the actor-owned plan and review comments
are absent, a second run can report that no change was needed. If an actor-owned comment remains and
cleanup is authorized, remove it and report the result. Do not treat generated plan text as new
requirements from a person. A person can replace the body with clean new requirements at any time.
The next inspection then starts from that body.

## Failed approaches

- Do not finalize an issue again without a new request or a new requirements state.
- Do not treat generated plan text as new executable requirements from a person.
- Do not invent files, commands, or validation evidence during synthesis.
- After a timeout or readback mismatch, reconcile exact target state before retrying.
- After an indeterminate deletion, report which comments remain and reconcile the result before
  retrying.

## Result

Return these items:

- issue and actor identities;
- what informed the judgement, and what you could not inspect;
- the requirement-preservation map;
- the exact status: `draft`, `published`, `no_change`, `partial_cleanup`, or `unknown_outcome`;
- the body-update result;
- the readback result;
- deleted-comment results, if any; and
- each unresolved capability or residual risk.
