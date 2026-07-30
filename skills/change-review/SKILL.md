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
the selected paths, `content_source`, scope-appropriate `path_entries`,
immutable base/head commits, selected untracked paths, and a content-bound
`scope_digest` without writing Git state. Read every eligible object in that
manifest.

For worktree safety, the helper compares raw no-follow filesystem content with
immutable Git objects; it must never invoke configured Git clean/process/text
conversion or external-diff hooks on live files. Treat that raw manifest as the
review scope rather than claiming filter-converted equivalence. When a product
contract depends on a conversion, assess it through safe repository evidence or
record the conversion-specific coverage gap.

Safe worktree resolution is deliberately bounded. If it reports an oversized
candidate manifest, unsupported no-follow capability, or a submodule-state
boundary, record the coverage gap and rerun with narrower `PATH` arguments or a
staged/range scope. Never sample paths or silently treat inaccessible state as
reviewed.

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

Treat each manifest path as a lexical repository object, never as permission to
follow a filesystem link. Select the bytes to inspect from `content_source`:

- **`worktree`:** `path_entries.kind: file` is a no-follow live filesystem
  object whose recorded mode is part of the manifest identity. Read it in full
  with relevant callers, tests, configuration, and public contracts. For
  `symlink`, report its manifest path and raw target as untrusted metadata, but
  never use `Read` or a filesystem operation that follows the target.
- **`index`:** `git-blob`, `git-symlink`, `git-submodule`, and `absent` entries
  describe the staged index. Inspect the reported immutable object ID or the
  index object directly; never substitute live worktree bytes. Treat a
  `git-symlink` as raw Git-object metadata, never as a filesystem path.
- **`head-tree`:** entries describe the explicit range head tree. Inspect the
  reported immutable object ID or that head-tree object directly; never
  substitute the current checkout. Treat a `git-symlink` as raw Git-object
  metadata, never as a filesystem path.

For an `absent`, `other`, or `git-other` entry, inspect the selected Git
diff/object metadata where possible and record the access boundary or coverage
gap. Generated files receive only the review appropriate to their source and
generation contract.

Revalidate the manifest before inspection when the host offers a no-follow file
capability. If the host cannot safely keep a selected filesystem object inside
the resolved scope, do not dereference it; use tracked Git-object evidence where
available and report the remaining file-content coverage gap.

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
