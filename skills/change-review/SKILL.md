---
name: change-review
license: BSD-3-Clause
description: Review only a worktree, staged, or explicit-range change for architecture, behavior, language, and evidence. Use before a commit or pull request. This skill is read-only. Resolve scope from task and branch evidence. Report unsupported scope as a coverage gap and deliver supported findings.
argument-hint: "[--worktree | --staged | --range BASE..HEAD] [PATH ...]"
allowed-tools: [Read, Bash, Grep, Glob, Agent]
---

# Change review

Purpose: Bind the exact local change to the review. Findings must apply only to the selected
content.

Apply the [ASD-STE100 technical-English policy](../TECHNICAL_ENGLISH.md) to this skill and to all
prose that it produces.

Use the shared [review contract](../../docs/review/common.md),
[requirement-to-evidence contract](../../docs/review/requirement-evidence.md),
[language routing](../../docs/review/language-routing.md), and
[behavior-first testing](../../docs/review/behavior-first-testing.md).

Use the [autonomous workflow policy](../../docs/policies/autonomous-workflows.md) for authority,
recovery, resources, validation, and delivery.

## Engineering principles

Use the canonical [engineering-principles catalog](../../docs/principles/README.md) to make these
review decisions:

- [P010 Scope Fidelity](../../docs/principles/README.md#p010): Examine only the selected bytes. Do not
  use a different scope.
- [P066 Preserve Existing Work](../../docs/principles/README.md#p066): Do not change work outside the
  selected scope.
- [P012 Evidence Before Modification](../../docs/principles/README.md#p012): Before you report a
  finding, examine the applicable evidence.
- [P063 Requirement-to-Code Traceability](../../docs/principles/README.md#p063): For each finding,
  find the applicable requirement or contract.
- [P072 Technical Evidence Over Preference](../../docs/principles/README.md#p072): Give evidence that
  you examined for each finding. Find the risk that this evidence shows. Do not use reviewer
  preference as evidence.
- [P014 Preserve Unrequested Behavior](../../docs/principles/README.md#p014): Do not recommend a
  behavior change that the request does not include.
- [P022 Test Behavior, Not Implementation](../../docs/principles/README.md#p022): Examine observable
  behavior. Do not make tests of private implementation details necessary.
- [P065 Verify Before Claiming Completion](../../docs/principles/README.md#p065): Make validation and
  coverage claims only from evidence that you examined.

This skill is read-only. Do not edit source. Do not stage files. Do not make Git state.

Do not post forge content. Do not open issues. Do not write review notes into source.

## Bind the scope

Select exactly one scope:

- Use `--worktree` by default. It selects tracked differences from `HEAD` and non-ignored untracked
  files.
- Use `--staged` to select index changes from `HEAD`.
- Use `--range BASE..HEAD` to select the explicit Git range.

For feature work, `BASE` is the recorded worktree start commit and initial review base. Do not
replace it with the latest remote target commit only because that branch changes. Movement of the
remote target branch does not invalidate a review of unchanged candidate content. Do not require a
rebase because the branch is behind. Repeat the review only if the selected content or its
requirements change, including after a permitted rebase or conflict resolution.

Before you inspect content, resolve the installed
[`scripts/resolve_scope.py`](scripts/resolve_scope.py) from this skill directory. Read each eligible
object in its manifest. For large scopes, use `--batch-size 1000` and inspect every JSONL batch.
Require the terminal complete record before claiming full coverage. Retain each manifest and
compare it during final revalidation. Follow the
[scope-resolution safety contract](references/scope-resolution.md). Use path arguments only to
reduce the selected diff. Make sure that each path remains inside the repository root.

When you must decide whether a changed test enforces a product contract through a fixed source-line
position, a stored citation offset, or the source-file length, run the installed
[`scripts/classify_test_design.py`](scripts/classify_test_design.py) on that test file. It prints one
JSON verdict with the reasons and the remediation. Follow the
[behavior-first testing contract](../../docs/review/behavior-first-testing.md). Do not request
citation-offset maintenance when the verdict is `reject`.

For a range, report the immutable base and head commits. For worktree or staged scope, report these
items:

- `HEAD`;
- selected paths; and
- the returned content-bound digest.

Do not create a commit, tree, stash, temporary index, or other Git state to represent a nonexistent
head. If the scope is empty, report the empty scope. Do not substitute a different range.

`--staged` and `--range` exclude untracked worktree files. State this boundary in the result. If
resolution cannot cover the selected scope in one operation, use batches and record progress.
If a source remains unavailable, report the exact coverage gap and supported findings.
Do not silently narrow the requested scope or claim complete coverage from a sample.

## Map the requirements to evidence

Before the verdict, build one independent expected inventory for the bound requirements and the
bound scope. Follow the [requirement-to-evidence contract](../../docs/review/requirement-evidence.md).
Freeze its digest before assessment. Assign every selected path to one review section. Assess each
expected cell as covered, missing requirement coverage, an incorrect implementation, or not
applicable with a reason.

Use the installed [`scripts/review_evidence.py`](scripts/review_evidence.py) adapter. It is
read-only.

- Run `prepare` with the scope selectors, the frozen inventory, the section assignment, the corrected
  findings, and an optional prior record with the record digest that you retained.
- Run `finalize` with the preparation and the assessed rows for the repeated sections.

The adapter returns the retained sections, the sections that need assessment with a cause each, the
evidence record, the complete findings batch, and the compact requirement-to-evidence map. Retain the
record outside the reviewed source and supply it on the next invocation. The adapter writes no record
into the repository and creates no exchange authority.

An invalid prior record is a specific diagnostic and no completeness claim. Source drift between
`prepare` and `finalize` is a failure, not a merge.

## Review and deliver

Follow this shared review flow:

1. Establish the architecture.
2. Select only applicable surfaces and language profiles.
3. Inspect changed behavior and tests.
4. Prepare unique findings in severity order.

For each skipped check, record not applicable (`N/A`). Give the reason for that status.

Activate a shared profile only if the selected change contains its surface:

- Use [P001 KISS — Keep It Simple, Stupid](../../docs/principles/README.md#p001) for added complexity.
- Use [P015 Architecture Conformance](../../docs/principles/README.md#p015) for boundary or dependency
  changes.
- Use [P022 Test Behavior, Not Implementation](../../docs/principles/README.md#p022) for testable
  behavior.
- Use
  [P029 Generalize Error Policy; Preserve Specific Cause](../../docs/principles/README.md#p029) for
  error-path changes.
- Use [P048 Secure by Design](../../docs/principles/README.md#p048) for security or trust-boundary
  changes.

For a material architecture change, require a stated design decision, architecture decision record
(ADR), or [design record](../../docs/review/design-docs.md). If architecture evidence is missing,
report a blocking finding. Do not invent evidence.

Include these items in the console or host-native read-only annotation surface:

1. Identify the scope, base and head or manifest digest, and files read.
2. Give the architecture decision first.
3. List applicable and `N/A` source-review criteria.
4. Give severity-ranked findings with the exact `path:line`, impact, and evidence.
5. For each finding, give a correction that is proportional to the impact.
6. Give changed-test source coverage and source-coverage limits.
7. Give the compact requirement-to-evidence map and the cause for each repeated section.
8. Give residual risks and unverified assumptions.

If the host supports native source annotations, use them only for changed locations. Otherwise, use
`path:line` in the console. Do not simulate annotations by editing source.

## Failed approaches

- Do not review uncommitted work as if it is committed. Do not invent a head commit to bind a range.
- Do not increase the scope beyond the requested range, paths, or selected diff. Report the boundary.
- Do not edit source. Do not stage files. Do not publish forge comments. Do not simulate native
  annotations to deliver findings.
- Cover the requested scope in batches. Report remaining gaps without discarding supported findings.
