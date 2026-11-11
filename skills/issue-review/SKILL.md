---
name: issue-review
license: BSD-3-Clause
description: Use before implementation to review a GitHub or GitLab issue and its current plan. Check architecture, scope, risk, and behavior-first verification. Use `--report-only` for read-only work. Delivers the review as a comment and sets the matching state label from the verdict.
argument-hint: "[--report-only] ISSUE_NUMBER_OR_URL"
allowed-tools: [Read, Bash, Grep, Glob, Agent, WebFetch]
---

# Review an issue and plan

Purpose: Review the plan before implementation. Early review helps you find architecture, scope,
and verification gaps before code changes start. The goal is a delivered review operation: inspect
what you can, report what informed the judgement, name what you could not inspect, and set the
matching state label from the verdict.

Apply the [ASD-STE100 technical-English policy](../TECHNICAL_ENGLISH.md) to this skill and to all
prose that it produces.

Use the [autonomous workflow policy](../../docs/policies/autonomous-workflows.md) for authority,
recovery, resources, validation, and delivery.

## Engineering principles

Use the canonical [engineering-principles catalog](../../docs/principles/README.md) for these review
decisions:

- [P010 Scope Fidelity](../../docs/principles/README.md#p010): Use the current issue and current
  plan as the full review target.
- [P066 Preserve Existing Work](../../docs/principles/README.md#p066): Do not rewrite historical
  artifacts or artifacts that a different actor owns.
- [P012 Evidence Before Modification](../../docs/principles/README.md#p012): Before you accept a
  plan, examine current requirements and repository evidence. If a source is unavailable, say so
  and proceed with the input you have.
- [P063 Requirement-to-Code Traceability](../../docs/principles/README.md#p063): For each gap,
  find the related requirement or contract.
- [P072 Technical Evidence Over Preference](../../docs/principles/README.md#p072): Give technical
  evidence for each gap. Do not use personal preference as evidence.
- [P015 Architecture Conformance](../../docs/principles/README.md#p015): If a boundary violation has
  no explanation, it is a finding, not a pass.
- [P071 Consistency Over Personal Preference](../../docs/principles/README.md#p071): If technical
  evidence does not show a necessary change, obey repository conventions.
- [P008 Understand Before Subtracting](../../docs/principles/README.md#p008): Before you accept
  deletion or consolidation, examine the consumers and purpose.

## Scope and delivery

Use the issue as the requirements source. Review the current plan. Use historical plans and reviews
only as background information. If no plan is present or it is unreadable, review the issue
requirements and report that the plan could not be inspected. Do not withhold the review because
the plan or external metadata is missing.

If the request includes `--report-only`, this skill is read-only. Do not publish a comment and do
not change a label. If the request does not include this option, publish the review comment and
set the matching state label as described in Deliver. Preserve foreign comments. Do not expand the
scope to anything except the review comment and the verdict label (`state:plan-go` or
`state:plan-no-go`). Do not touch these items:

- assignment;
- implementation;
- commit;
- push;
- pull request;
- merge; or
- issue closure.

## Review

1. Read the issue, linked work, the current plan comment, repository guidance, architecture
   decision records (ADRs), applicable code, tests, and public contracts. If the plan cannot be
   read, review the issue alone and name the limit.
2. Under [P015 Architecture Conformance](../../docs/principles/README.md#p015), select one
   architecture result:

   - aligned;
   - intentional and justified change; or
   - unexplained violation.

   Report the result. A material violation is a blocking finding.
3. Under [P063 Requirement-to-Code Traceability](../../docs/principles/README.md#p063), map each
   acceptance criterion to a concrete plan step, affected boundary, and behavior-first validation
   step. Report unmapped criteria as findings.
4. If the plan contains a material architecture change, check that it includes or cites a design
   record.
5. Under [P012 Evidence Before Modification](../../docs/principles/README.md#p012), verify these
   claims against current repository evidence:

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

9. Reconcile every active prior finding before you add a new finding. Use these response rules:

   - For `fix` or `fix_with_tradeoff`, select `resolve`, `partial`, `still_present`, `withdraw`, or
     `escalate` from current evidence.
   - For `contest`, select `accept`, `counter`, `refute`, or `escalate`. A counter supplies a
     revised closure condition and new evidence. A refutation supplies new evidence.
   - For `risk_acceptance`, select `withdraw`, `still_present`, or `escalate`.

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

Do not treat generated plan text as new requirements from a person. Judge the plan against the
issue requirements as they exist now.

For each requirement you examined, map it to the proposed implementation and test steps. Mark a
mapping not applicable only with a reason. Report the material findings as one bounded batch. A
correction to one finding repeats only the affected sections, and the repeat cause names the
finding or the changed source.

## Deliver

1. Build the review comment. Include the architecture decision first, the requirement map,
   severity-ranked findings, the `N/A` sections, the residual risks, and the verdict (`GO` or
   `NO-GO`). Start the comment with the marker `<!-- HomericIntelligence:issue-review -->` so
   later rounds and readers can find it.
2. For `--report-only`, return the prepared review and stop. Do not publish and do not set a
   label.
3. Immediately before publication, read the issue again. If it changed in a way that affects the
   review, refresh the affected evidence and prepare the review again.
4. Publish the review and set the matching state label from the verdict you just delivered:
   `state:plan-go` for `GO`, `state:plan-no-go` for `NO-GO`. Use
   [`../pr-review/scripts/delivery.py`](../pr-review/scripts/delivery.py). It comments on the
   issue when the target is available, applies one target label, removes the sibling label, and
   returns the report locally otherwise. Run it as
   `python3 "<installed-pr-review-skill-directory>/scripts/delivery.py" --target <NUMBER> --kind plan --decision <GO|NO-GO> --body <REVIEW_FILE>`.
   If the helper is unavailable, publish one comment on the issue with the forge's issue-comment
   mechanism (for example `gh issue comment <NUMBER> --body-file <REVIEW_FILE>`), then
   read the issue's labels with
   `gh api repos/<owner>/<repo>/issues/<NUMBER>/labels --paginate --jq '.[].name'`,
   and set the label set with
   `gh api --method PATCH repos/<owner>/<repo>/issues/<NUMBER>/labels --input -`
   and a JSON body of the form `{"labels": ["<kept-labels>", "state:plan-go"]}` (or
   `state:plan-no-go`).
5. Read the comment and the labels back when the forge permits it. Report the exact result.
6. If the write fails or its outcome is uncertain, report the outcome honestly. Preserve the
   prepared review. Reconcile the live issue state before any retry.
7. Report what informed the judgement: the issue, its comments, the plan, the code and tests you
   read, and the guidance you used. Name what you could not inspect and why. Do not withhold
   output because external or `.git` metadata is missing. Proceed with the input you have.

## Failed approaches

- Review only the issue and its current plan. Treat historical plans and reviews as background.
- Do not edit the issue body, assignment, milestone, or labels other than the verdict label.
  For `--report-only`, return the findings without publication.
- Do not invent acceptance criteria that the reporter did not state. Do not accept an unresolved
  prior finding only because someone acknowledged it.
- Do not publish more than one delivered review per invocation.
- If the write fails or its outcome is uncertain, report the outcome; reconcile the live state
  before retrying.

## Result

Return these items:

- issue and plan identities;
- the architecture decision first;
- what informed the judgement, and what you could not inspect;
- the requirement map;
- severity-ranked findings;
- test-quality coverage;
- `N/A` sections;
- residual risks;
- the verdict (`GO` or `NO-GO`) and the delivery result: the comment identity, the label applied,
  or the reason the delivery was withheld; and
- whether you published or withheld the comment.

Do not expand the review scope to implementation or merge.
