---
name: git-worktrees
license: BSD-3-Clause
description: Prepare an isolated feature worktree under the primary project’s ignored .worktrees directory. Preserve existing checkouts and changes. Record baseline failures and continue authorized work.
argument-hint: <branch-name or feature description>
allowed-tools: [Bash, Read]
---

# Use Git worktrees

Use the [autonomous workflow policy](../../docs/policies/autonomous-workflows.md) for authority,
recovery, resources, validation, and delivery.

## Overview

Git worktrees are isolated workspaces that share one repository. You can work on multiple branches
at the same time. You do not have to switch the active branch.

Apply the [ASD-STE100 technical-English policy](../TECHNICAL_ENGLISH.md) to this skill and to all
prose that it produces.

**Rule:** Select the directory systematically. Then complete the safety checks. These actions give
reliable isolation.

Use this location and verification policy for manual and delegated feature worktrees.

## Engineering principles

Use the [canonical engineering-principles catalog](../../docs/principles/README.md) for these
workflow-specific rules:

- [P010 — Scope Fidelity](../../docs/principles/README.md#p010): Make only the requested isolated
  branch and worktree. Delegate cleanup and unrelated changes to the applicable workflows.
- [P012 — Evidence Before Modification](../../docs/principles/README.md#p012): Before creation,
  examine repository guidance, the selected base revision, directory state, ignore rules, and
  baseline checks.
- [P021 — Evolutionary and Reversible Design](../../docs/principles/README.md#p021): Put feature work
  in an isolated worktree at the selected base commit. Only if you have user authority and can use
  the cleanup workflow, remove the worktree.
- [P033 — State-Safe Failure Semantics](../../docs/principles/README.md#p033): If validation is not
  satisfactory, repair the setup before creation. If a test fails after creation, preserve the
  worktree, classify the failure, and continue authorized work.
- [P053 — Validate at Trust Boundaries](../../docs/principles/README.md#p053): Use the tested helper
  to validate branch, base, path, and path-root values. An equivalent fallback must verify the
  same values.
- [P058 — Bounded Agent Authority](../../docs/principles/README.md#p058): Make only the named branch
  and worktree for the requested feature. Use the selected start commit and validated destination.
- [P065 — Verify Before Claiming Completion](../../docs/principles/README.md#p065): Before you report
  that you prepared the worktree, run available repository baseline checks. Report failures, the path
  and start commit.
- [P083 — Irreversible Actions Last](../../docs/principles/README.md#p083): Before creation, complete
  the dry-run. Before creation, complete the safety validation. Use `tidy` for removal.

## Select and verify the directory

Resolve the primary project checkout through Git worktree metadata. Create new worktrees and
additional project clones below its `.worktrees/` directory. Existing checkouts elsewhere remain
valid; do not move them only to satisfy the new default.

Verify that Git ignores `.worktrees/`. If needed, add the ignore rule to Git’s local exclude file as part of the authorized
setup. Do not require a separate approval or commit before creation. Preserve other ignore rules.
Reject a destination that resolves outside the intended root or traverses a symbolic link.

Use the installed `scripts/prepare_worktree.py` helper. If it fails, attempt repair and issue
handling before an equivalent native Git fallback. Verify the branch, exact base commit,
destination, absence of a conflicting worktree, and ignore rule in that fallback. Record the
actual commands; do not claim the helper succeeded.

## Create the worktree

1. Resolve the intended base commit SHA.
2. Record the intended base commit SHA as the worktree start commit and initial local review base.
3. Keep the target repository as the current working directory.
4. Resolve `scripts/prepare_worktree.py` from this installed skill directory.
5. Prepare `BRANCH_NAME --start-point BASE_SHA --dry-run` as the helper arguments.
6. If the contract requires a distinct branch and path, add exact `--path` and `--path-root` values.
7. If repository guidance specifies a directory, add it through `--directory`.
8. Use the primary project’s ignored `.worktrees/` directory.
9. Use the same exact path and path-root values for dry-run and creation.
10. Invoke the helper by its absolute path with the prepared dry-run arguments.
11. Create the worktree with the same arguments without `--dry-run`.
12. Do not replace the recorded SHA with the current `HEAD`.
13. Change to the returned path.
14. If the repository defines a bootstrap, run it.
15. Use available repository tests to record the baseline and classify pre-existing failures.
16. Report the path, start SHA, and result.

After work starts, do not replace the initial local review base with a later remote target commit
only because the remote target branch changes. Do not rebase because the remote target branch moves
or because the branch is behind. Rebase only when required target-branch content blocks the work,
or after the work is complete when the forge reports a merge conflict that the agent must resolve.
Use the current target branch only for integration and merge-readiness checks. Let the configured
merge queue do normal target integration. If a permitted rebase or conflict resolution changes
candidate content, review that changed content.

**If the tests fail:** Record the baseline failures. Use the shared issue-handling procedure and
continue the task. Distinguish these failures from regressions introduced by the feature.

**If the tests pass:** Report that the worktree is ready.

## Clean up

When the work is complete, invoke `tidy` for branch and worktree cleanup. `tidy` prepares the trusted
Hephaestus dependency. It delegates the work directly to `hephaestus-tidy`. The interactive workflow
controls discovery, preservation rules, deletion prompts, rebases, and cleanup safeguards. Do not
duplicate that policy. Do not write deletion commands in this skill.

Preserve the worktree by default. An explicit cleanup request authorizes guarded removal of verified
merged branches and clean worktrees with no unique work. Use `tidy`. Preserve ambiguous or unique
work and report it.

## Failed approaches

- Do not create an unignored project-local worktree.
- Do not treat a pre-existing baseline failure as a whole-task blocker.
- Do not move an existing checkout solely because its location differs from the new default.
- Do not remove unique work during cleanup.

## Related workflow

- Invoke `tidy` for dependency-locked delegation to Hephaestus branch and worktree cleanup.
- Before you report completion or start cleanup, get fresh runnable evidence. Follow the
  [evidence-integrity policy](../../docs/policies/evidence-integrity.md).

---

_Adapted from [obra/superpowers](https://github.com/obra/superpowers) under the [MIT License](https://github.com/obra/superpowers/blob/main/LICENSE). Copyright (c) 2025 Jesse Vincent._
