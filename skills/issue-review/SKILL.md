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

Apply the [ASD-STE100 technical-English policy](../../docs/technical-english.md) to this skill and to
all prose that it produces.

Use the shared [issue-planning contract](../../docs/review/issue-planning.md),
[review contract](../../docs/review/common.md),
[language routing](../../docs/review/language-routing.md), and
[behavior-first testing](../../docs/review/behavior-first-testing.md).

## Engineering principles

Apply the canonical [engineering-principles catalog](../../docs/principles/README.md) through these
review decisions:

- [P010 Scope Fidelity](../../docs/principles/README.md#p010) keeps the current issue and canonical
  plan as the complete review target, while
  [P066 Preserve Existing Work](../../docs/principles/README.md#p066) prevents the review from
  rewriting foreign or historical artifacts.
- [P012 Evidence Before Modification](../../docs/principles/README.md#p012),
  [P063 Requirement-to-Code Traceability](../../docs/principles/README.md#p063), and
  [P072 Technical Evidence Over Preference](../../docs/principles/README.md#p072) require every gap
  to be grounded in current requirements, repository evidence, and an affected contract.
- [P015 Architecture Conformance](../../docs/principles/README.md#p015) makes unexplained boundary
  violations blocking;
  [P071 Consistency Over Personal Preference](../../docs/principles/README.md#p071) preserves
  repository conventions unless contrary technical evidence exists; and
  [P008 Understand Before Subtracting](../../docs/principles/README.md#p008) requires evidence about
  consumers and purpose before approving deletion or consolidation.

## Scope and delivery

Use the issue as the requirements source. Review only its current canonical plan. Use the
issue-planning contract to identify the plan owner, marker, presence or absence, and identity. Use
historical plans and reviews only as background information.

If the request includes `--report-only`, this skill is read-only. Do not publish a comment. If the
request does not include this option, first compare the required identities and confirm a safe forge
capability. Then you can publish exactly one actor-owned structured review comment. Do not expand
the scope to these items:

- labels;
- assignment;
- implementation;
- commit;
- push;
- pull request;
- merge; or
- issue closure.

## Review

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

9. Confirm that each applicable prior finding is resolved. Acknowledgment alone does not resolve a
   finding.

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
Review only a later material issue change and its current canonical plan. An unchanged finalized
epoch is not a new review target.

Immediately before you publish the requested comment, resolve the canonical planning identity again.
If one of these conditions is true, withhold the comment and report the `stale` status:

- identity drift;
- a foreign marker;
- multiple markers;
- a change to verified absence; or
- no safe forge capability.

Otherwise, publish exactly one actor-owned structured comment. Include a clean result or verified
absent-plan coverage gap.

## Failed approaches

- Do not review issues or plans outside the requested scope. Do not treat historical plans as the
  artifact under review.
- Do not edit the issue, labels, or assignment. If publication is authorized, report findings only in
  the structured review comment. For `--report-only`, return the findings without publication.
- Do not invent acceptance criteria that the reporter did not state. Do not accept an unresolved
  prior finding only because someone acknowledged it.
- After drift, do not publish the comment again. Withhold it and report `stale`.

## Result

Return these items:

- issue and plan identities;
- the architecture decision first;
- the requirement map;
- severity-ranked findings;
- test-quality coverage;
- `N/A` sections;
- residual risks; and
- whether you published or withheld the comment.

Do not expand the review scope to implementation or merge.
