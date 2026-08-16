---
name: change-review
license: BSD-3-Clause
description: Review only the working-tree, staged, or explicit-range changes for architecture alignment, behavior, language practices, and evidence. Use before committing or opening a PR; it never edits source or posts forge comments.
argument-hint: "[--worktree | --staged | --range BASE..HEAD] [PATH ...]"
allowed-tools: [Read, Bash, Grep, Glob, Agent]
---

# Change review

Why: bind the exact local change before review so findings apply to the bytes
that will be committed.

Use the shared [review contract](../../docs/review/common.md),
[language routing](../../docs/review/language-routing.md), and
[behavior-first testing](../../docs/review/behavior-first-testing.md).

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
