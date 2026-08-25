---
name: change-review
license: BSD-3-Clause
description: Review only the working-tree, staged, or explicit-range changes for architecture alignment, behavior, language practices, and evidence. Use before committing or opening a PR; it never edits source or posts forge comments. An ambiguous, unresolvable, or out-of-scope change set blocks the review with a reported reason instead of being silently widened.
argument-hint: "[--worktree | --staged | --range BASE..HEAD] [PATH ...]"
allowed-tools: [Read, Bash, Grep, Glob, Agent]
---

# Change review

Why: bind the exact local change before review so findings apply to the bytes
that will be committed.

Apply the [ASD-STE100 writing policy](../../docs/technical-english.md) to this skill and to all prose
that it produces.

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

Choose exactly one scope:

- `--worktree` (default): tracked differences from `HEAD` and non-ignored
  untracked files;
- `--staged`: index changes from `HEAD`; or
- `--range BASE..HEAD`: the explicit Git range.

Resolve the installed [`scripts/resolve_scope.py`](scripts/resolve_scope.py)
from this skill directory before inspection. Read every eligible object in its
manifest and follow the [scope-resolution safety contract](references/scope-resolution.md).
Paths further restrict the selected diff and must remain inside the repository
root.

For a range, report immutable base and head commits. For worktree or staged
scope, report `HEAD`, selected paths, and the returned content-bound digest;
never create a commit, tree, stash, temporary index, or other Git state to
invent a head. Report an empty scope and never silently substitute a different
range.

`--staged` and `--range` exclude untracked worktree files. State that boundary
in the result. If resolution cannot safely cover the selected scope, report the
coverage gap and narrow the paths or choose a safer scope; never sample it.

## Review and deliver

Follow the shared review flow: establish architecture first, classify only
applicable surfaces and language profiles, inspect changed behavior and tests,
then de-duplicate severity-ranked evidence. Record each skipped check as N/A
with its reason.

Activate the shared profiles only when the selected change contains the relevant surface: use
[P001 KISS — Keep It Simple, Stupid](../../docs/principles/README.md#p001) for added complexity,
[P015 Architecture Conformance](../../docs/principles/README.md#p015) for boundary or dependency
changes, [P022 Test Behavior, Not Implementation](../../docs/principles/README.md#p022) for testable
behavior, [P029 Generalize Error Policy; Preserve Specific Cause](../../docs/principles/README.md#p029)
for error-path changes, and [P048 Secure by Design](../../docs/principles/README.md#p048) for security
or trust-boundary changes.

For a material architecture change, require a stated design decision, ADR, or
[design record](../../docs/review/design-docs.md). Missing architecture evidence
is a blocker; do not invent it.

Return in the console or host-native read-only annotation surface:

1. scope identity, base/head or manifest digest, and files read;
2. architecture decision first, then applicable and N/A checks;
3. severity-ranked findings with exact `path:line`, impact, evidence, and a
   proportionate remediation direction;
4. behavior-first testing and validation coverage; and
5. residual risks and unverified assumptions.

Use native source annotations only for changed locations when the host supports
them. Otherwise use `path:line` in the console; never simulate annotations by
editing source.

## Failed approaches

- Reviewing uncommitted work as if it were committed, or inventing a head commit to bind a range.
- Widening scope past the requested range, paths, or selected diff instead of reporting the
  boundary.
- Editing source, staging files, posting forge comments, or simulating native annotations to deliver
  findings.
- Sampling an unsafe-to-cover scope instead of reporting the coverage gap and narrowing the paths.
