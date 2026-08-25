---
name: change-review
license: BSD-3-Clause
description: Review only a worktree, staged, or explicit-range change for architecture, behavior, language, and evidence. Use before a commit or pull request. This skill is read-only. If the scope is ambiguous, unresolved, or out of scope, report the reason and stop.
argument-hint: "[--worktree | --staged | --range BASE..HEAD] [PATH ...]"
allowed-tools: [Read, Bash, Grep, Glob, Agent]
---

# Change review

Purpose: Bind the exact local change to the review. Findings must apply only to the selected
content.

Apply the [ASD-STE100 technical-English policy](../TECHNICAL_ENGLISH.md) to this skill and to all
prose that it produces.

Use the shared [review contract](../../docs/review/common.md),
[language routing](../../docs/review/language-routing.md), and
[behavior-first testing](../../docs/review/behavior-first-testing.md).

## Engineering principles

Apply the canonical [engineering-principles catalog](../../docs/principles/README.md) through these
review decisions:

- [P010 Scope Fidelity](../../docs/principles/README.md#p010) and
  [P066 Preserve Existing Work](../../docs/principles/README.md#p066) bind the review to the selected
  bytes without substituting another scope or disturbing unrelated work.
- [P012 Evidence Before Modification](../../docs/principles/README.md#p012),
  [P063 Requirement-to-Code Traceability](../../docs/principles/README.md#p063), and
  [P072 Technical Evidence Over Preference](../../docs/principles/README.md#p072) require each
  finding to connect inspected evidence to a requirement, contract, or demonstrated risk rather than
  reviewer taste.
- [P014 Preserve Unrequested Behavior](../../docs/principles/README.md#p014) and
  [P022 Test Behavior, Not Implementation](../../docs/principles/README.md#p022) make observable
  behavior the review target, while
  [P065 Verify Before Claiming Completion](../../docs/principles/README.md#p065) keeps validation and
  coverage claims bounded by evidence actually obtained.

This skill is read-only. It never edits source, stages files, creates Git
state, posts forge content, opens issues, or writes review notes into source.

## Bind the scope

Select exactly one scope:

- Use `--worktree` by default. It selects tracked differences from `HEAD` and non-ignored untracked
  files.
- Use `--staged` to select index changes from `HEAD`.
- Use `--range BASE..HEAD` to select the explicit Git range.

Before you inspect content, resolve the installed
[`scripts/resolve_scope.py`](scripts/resolve_scope.py) from this skill directory. Read each eligible
object in its manifest. Follow the
[scope-resolution safety contract](references/scope-resolution.md). Use path arguments only to
reduce the selected diff. Make sure that each path remains inside the repository root.

For a range, report the immutable base and head commits. For worktree or staged scope, report these
items:

- `HEAD`;
- selected paths; and
- the returned content-bound digest.

Do not create a commit, tree, stash, temporary index, or other Git state to represent a nonexistent
head. If the scope is empty, report the empty scope. Do not substitute a different range.

`--staged` and `--range` exclude untracked worktree files. State this boundary in the result. If
resolution cannot safely cover the selected scope, report the coverage gap. Reduce the paths or
select a safer scope. Do not inspect a sample of the scope.

## Review and deliver

Follow this shared review flow:

1. Establish the architecture.
2. Select only applicable surfaces and language profiles.
3. Inspect changed behavior and tests.
4. Prepare unique findings in severity order.

For each skipped check, record not applicable (`N/A`) and give the reason.

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
3. List applicable and `N/A` checks.
4. Give severity-ranked findings with the exact `path:line`, impact, evidence, and a correction that
   is proportional to the impact for each finding.
5. Give behavior-first test and validation coverage.
6. Give residual risks and unverified assumptions.

If the host supports native source annotations, use them only for changed locations. Otherwise, use
`path:line` in the console. Do not simulate annotations by editing source.

## Failed approaches

- Do not review uncommitted work as if it is committed. Do not invent a head commit to bind a range.
- Do not increase the scope beyond the requested range, paths, or selected diff. Report the boundary.
- Do not edit source, stage files, publish forge comments, or simulate native annotations to deliver
  findings.
- Do not sample a scope that you cannot cover safely. Report the coverage gap and reduce the paths.
