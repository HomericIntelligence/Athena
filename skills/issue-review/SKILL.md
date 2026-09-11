---
name: issue-review
license: BSD-3-Clause
description: Use before implementation to review a GitHub or GitLab issue and its current `plan-issue` artifact. Check architecture, scope, risk, and behavior-first verification. Use `--report-only` for read-only work.
argument-hint: "[--report-only] ISSUE_NUMBER_OR_URL"
allowed-tools: [Read, Bash, Grep, Glob, Agent, WebFetch]
---

# Review an issue and plan

Purpose: Review the plan before implementation. Early review helps you find architecture, scope,
and verification gaps before code changes start.

Apply the [ASD-STE100 technical-English policy](../TECHNICAL_ENGLISH.md) to this skill and to all
prose that it produces.

Use the shared [issue-planning contract](../../docs/review/issue-planning.md),
[review contract](../../docs/review/common.md),
[review-exchange mechanism](../review-exchange/SKILL.md),
[language routing](../../docs/review/language-routing.md), and
[behavior-first testing](../../docs/review/behavior-first-testing.md).

## Engineering principles

Use the canonical [engineering-principles catalog](../../docs/principles/README.md) for these review
decisions:

- [P010 Scope Fidelity](../../docs/principles/README.md#p010): Use the current issue and canonical
  plan as the full review target.
- [P066 Preserve Existing Work](../../docs/principles/README.md#p066): Do not rewrite historical
  artifacts or artifacts that a different actor owns.
- [P012 Evidence Before Modification](../../docs/principles/README.md#p012): Before you accept a
  plan, examine current requirements and repository evidence.
- [P063 Requirement-to-Code Traceability](../../docs/principles/README.md#p063): For each gap,
  find the related requirement or contract.
- [P072 Technical Evidence Over Preference](../../docs/principles/README.md#p072): Give technical
  evidence for each gap. Do not use personal preference as evidence.
- [P015 Architecture Conformance](../../docs/principles/README.md#p015): If a boundary violation has
  no explanation, do not accept the plan.
- [P071 Consistency Over Personal Preference](../../docs/principles/README.md#p071): If technical
  evidence does not show a necessary change, obey repository conventions.
- [P008 Understand Before Subtracting](../../docs/principles/README.md#p008): Before you accept
  deletion or consolidation, examine the consumers and purpose.

## Scope and delivery

Use the issue as the requirements source. Review only its current canonical plan. Use the
issue-planning contract to identify the plan owner, marker, presence or absence, and identity. Use
historical plans and reviews only as background information. For explicit legacy adoption, give the
helper the exact current unversioned plan and optional review in the normalized snapshot. Do not
interpret edit history or other prose as current requirements or proof of closure.

If the request includes `--report-only`, this skill is read-only. Do not publish a comment. If the
request does not include this option, first compare the required identities. Then, confirm a safe
forge capability. Create the canonical review comment only when it is absent. Each later reviewer
round updates that exact actor-owned comment. Never create a second review marker. Do not
expand the scope to these items:

- labels;
- assignment;
- implementation;
- commit;
- push;
- pull request;
- merge; or
- issue closure.

## Review

Before the substantive review, exhaust bounded provider pagination for issue comments. Normalize
the issue snapshot, set `comments_complete` to `true`, and run `issue_exchange.py inspect`.
Withhold on an absent plan or an identity error. Use the inspect result and the caller's explicit
event to select exactly one path. Evaluate these paths in order:

- For the verified `pending_reframe` diagnostic with `next_action=prepare_review`, require an
  explicit `reframe` event and go directly to the reframe transition below.
- For a verified pending-reframe result with any other or no event, stop and report the event
  mismatch. Do not do a substantive reviewer assessment.
- For an explicit `human_decision` event when `next_action` is `prepare_plan`, `prepare_review`, or
  `human_decision`, go directly to the human-decision transition below. Do not do a substantive
  reviewer assessment. The reducer rejects a decision that is not valid for the retained finding
  state.
- For any other `next_action=prepare_review` result without an authority event, do the substantive
  review below.
- For each other result, stop and report the current state. Do not prepare or publish a comment.

Reject an event that does not match the selected path. Do not infer an authority event or decision
from the retained state, an authority comment, or other prose. For an active unversioned plan or
review, set `legacy_import` only when the issue-planning contract permits explicit round-1 adoption.

1. Read the issue, linked work, canonical plan, repository guidance, architecture decision records
   (ADRs), applicable code, tests, and public contracts.
2. Under [P015 Architecture Conformance](../../docs/principles/README.md#p015), select one architecture
   result:

   - aligned;
   - intentional and justified change; or
   - unexplained violation.

   A material violation prevents a positive assessment.
3. Under [P063 Requirement-to-Code Traceability](../../docs/principles/README.md#p063), map each
   acceptance criterion to a concrete plan step, affected boundary, and behavior-first validation
   step.
4. If the plan contains a material architecture change, verify that it includes or cites a
   [design record](../../docs/review/design-docs.md).
5. Under [P012 Evidence Before Modification](../../docs/principles/README.md#p012), verify these claims
   against current repository evidence:

   - paths;
   - symbols;
   - commands;
   - dependencies;
   - assumptions;
   - risks;
   - migration; and
   - rollback.

6. Apply only the language and change-surface checks that the review scope activates.
7. Record each not applicable (`N/A`) section and its reason.
8. Activate these principle checks only for their specified surfaces:

   - Use [P001 KISS — Keep It Simple, Stupid](../../docs/principles/README.md#p001) for added
     complexity.
   - Use [P022 Test Behavior, Not Implementation](../../docs/principles/README.md#p022) for testable
     behavior.
   - Use
     [P029 Generalize Error Policy; Preserve Specific Cause](../../docs/principles/README.md#p029) for
     error paths.
   - Use [P048 Secure by Design](../../docs/principles/README.md#p048) for security or new trust
     boundaries.

9. Reconcile every active prior finding before you add a finding. This set includes each stable
   finding identifier that `plan-issue` revalidated after an artifact change. Use these response
   rules:

   - For `fix` or `fix_with_tradeoff`, select `resolve`, `partial`, `still_present`, `withdraw`, or
     `escalate` from current evidence.
   - For `contest`, select `accept`, `counter`, `refute`, or `escalate`. A counter supplies a revised
     closure condition and new evidence. A refutation supplies new evidence.
   - For `risk_acceptance`, select `withdraw`, `still_present`, or `escalate`. Only an authoritative
     `accept_risk` decision produces `accepted_risk`.

   Acknowledgment alone does not resolve a finding.

Give priority to these findings:

- architecture violations;
- missing requirements;
- unsafe scope;
- unresolved dependencies;
- outcomes that cannot be tested;
- invalid references;
- nondeterministic tests;
- empty selections; and
- unsupported claims.

After a finalized epoch, do not treat generated plan text or sealed provenance as new requirements.
An unchanged finalized epoch is not a new review target. A stale or malformed finalization marker
must withhold the review. Review a later material issue change only after an authoritative person
replaces the sealed body with clean requirements, removes the obsolete marker, and publishes its
new canonical plan.

Build one reviewer event with complete coverage status, responses for every active prior required
finding, new findings, an applicable stop reason, and the declared scope. Supply scope for a first or
legacy round. Preserve it on later rounds.

Run `issue_exchange.py prepare-review`. For `--report-only`, return the prepared result and stop.
Immediately before publication, get a fresh snapshot and prepare the operation again. Require the
same precondition and exact create or update operation. If one of these conditions is true, withhold
the comment:

- identity drift;
- a foreign marker;
- multiple markers;
- a change to verified absence; or
- no safe forge capability.

If the prepared identity changed before the write, report `stale`. For a foreign or multiple marker,
or for a missing safe forge capability, report `withheld`.

Otherwise, publish only the exact prepared comment operation. Read the issue again and run
`issue_exchange.py verify-publication`. After a verified result, stop for an author response,
finalization, or a human decision. If the write or readback result is indeterminate, report
`unknown_outcome`. Preserve the prepared operation and available receipt evidence. Do not retry.
Do not invoke `issue-review` recursively. The reducer selects the verdict and prevents a sixth
reviewer assessment.

### Authority transitions

Use these paths only when the action dispatch selects them. The selected authority transition owns
the one retained-review update and its readback. It must not also prepare a reviewer-assessment
event.

For a human decision, accept only an explicit `human_decision` event that the reducer permits for
the retained nonterminal state. This includes an accepted recorded-risk request before the state
has `next_action=human_decision`. Normalize the authority from forge-owned permission data. Require
its receipt to match one exact live noncanonical issue comment. Use `prepare-review` to bind the
decision to the current state and finding. This event does not increment the reviewer round. It can
accept only a recorded risk request or select one active closure condition. It cannot select a
closure that needs round 6.

Before a requirements reframe, require the retained plan and review to identify the same current
logical state. If the plan has a pending author event that the review has not accepted, complete and
verify one reviewer assessment before the requirements change. Do not overwrite the pending author
event or supersede the older persisted review state.

For the second step of an explicit requirements reframe, require the reframed plan, the same exact
old retained v1 state, the same live authority receipt, and the same declared target set that
`plan-issue` used. Call `prepare-review` with the `reframe` event. Update the retained review comment
with round 1 of the new exchange. The new state must store the `supersession_authority_receipt` and
superseded state digest. Do not create a new review comment or carry old finding identities into the
new exchange.

For either authority transition, `--report-only` returns the prepared update and stops. Otherwise,
get a fresh snapshot and run `prepare-review` again. Require the same precondition and exact retained
comment update. Publish only that update and run `verify-publication` against an exact readback. If
the write or readback is uncertain, report `unknown_outcome` and stop without a retry.

## Failed approaches

- Do not review issues or plans outside the requested scope. Do not treat historical plans as the
  artifact under review.
- Do not edit the issue, labels, or assignment. If publication is authorized, report findings only in
  the structured review comment. For `--report-only`, return the findings without publication.
- Do not invent acceptance criteria that the reporter did not state. Do not accept an unresolved
  prior finding only because someone acknowledged it.
- After drift, do not publish the comment again. Withhold it. Report `stale`.

## Result

Return these items:

- issue and plan identities;
- the architecture decision first;
- the requirement map;
- severity-ranked findings;
- test-quality coverage;
- `N/A` sections;
- residual risks;
- exchange round, state digest, verdict, and next action;
- publication receipt or helper diagnostics; and
- whether you published or withheld the comment.

Do not expand the review scope to implementation or merge.
