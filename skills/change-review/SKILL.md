---
name: change-review
description: Review only the working-tree, staged, or explicit-range changes for architecture alignment, behavior, language practices, and evidence. Use before committing or opening a PR; it never edits source or posts forge comments.
argument-hint: "[--worktree | --staged | --range BASE..HEAD] [PATH ...]"
allowed-tools: [Read, Bash, Grep, Glob, Agent]
---

# Change review

Review local changes with the shared
[review contract](../../docs/review/common.md),
[language routing](../../docs/review/language-routing.md), and
[behavior-first testing](../../docs/review/behavior-first-testing.md).

This skill is read-only. It never edits source, stages files, creates a commit,
posts a forge comment, opens an issue, or inserts review notes into source.

## Resolve the scope

Use exactly one scope:

- `--worktree` (default): all tracked differences relative to `HEAD` plus every
  non-ignored untracked file;
- `--staged`: index changes relative to `HEAD`; or
- `--range BASE..HEAD`: the explicit Git range.

Before inspection, resolve the installed
[`scripts/resolve_scope.py`](scripts/resolve_scope.py) helper against this skill
directory and invoke it with the selected scope and optional paths. It returns
the selected paths, immutable base/head commits, selected untracked paths, and
a content-bound `scope_digest` without writing Git state. Read every path in
that manifest.

Paths further restrict the selected diff; reject a path outside the repository
root. For `--range`, report the immutable base and head commits. For
`--worktree` or `--staged`, report `HEAD`, the selected paths, and the returned
non-mutating digest. Do not create a commit, tree object, stash, temporary
index, or other Git state merely to fabricate a staged or working-tree head
identity. Report an empty scope and do not silently fall back from a requested
range to a different one.

`--staged` and `--range` deliberately exclude untracked worktree files. State
that `untracked_scope` boundary in the report; never imply that those files were
reviewed. The default worktree scope must include raw untracked file content in
its digest, not only their paths.

Read every selected changed file in full, including relevant callers, tests,
configuration, and public contracts. Generated files receive only the review
appropriate to their source and generation contract.

## Required review flow

1. Read repository guidance and establish architecture alignment before any
   implementation-level assessment.
2. Classify the changed surfaces and choose only applicable checks from the
   shared contract. Record each skipped section as N/A with its reason.
3. Apply the selected language and toolchain profile.
4. Trace changed behavior through happy, error, boundary, state, concurrency,
   security, and external-write paths when applicable.
5. Evaluate changed tests using the behavior-first contract. Flag prose,
   implementation-detail, flaky, empty-selection, or mock-only tests.
6. De-duplicate evidence-backed findings and order them by severity.

For an architecture change, require a stated design decision or ADR. If it does
not exist, report the missing decision as a blocker rather than inventing one.

## Output

Return, in the current console or host-native source-annotation surface:

1. resolved scope, base/head, and files read;
   for a mutable worktree or index, include the selected-diff/manifest digest
   instead of an invented head commit;
2. architecture-alignment decision first;
3. applicable checks and N/A sections with reasons;
4. severity-ranked findings with exact `path:line`, impact, evidence, and a
   proportionate remediation direction;
5. behavior-first testing and validation coverage; and
6. residual risks or unverified assumptions.

When the host supports source annotations, emit native read-only annotations
that point to the changed source location. Otherwise use `path:line` in the
console. Do not write comments into source files to simulate annotations.
