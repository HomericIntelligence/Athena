---
name: git-worktrees
license: BSD-3-Clause
description: Use for feature work that needs an isolated Git worktree. If Git does not ignore a project-local directory, use the verified temporary-directory fallback. If repository guidance requires the local directory, report the problem. In that case, stop before creation. If the helper cannot verify a clean base commit, report the problem. In that case, stop before creation. Do not delete anything.
argument-hint: <branch-name or feature description>
allowed-tools: [Bash, Read]
---

# Use Git worktrees

## Overview

Git worktrees are isolated workspaces that share one repository. You can work on multiple branches
at the same time. You do not have to switch the active branch.

Apply the [ASD-STE100 technical-English policy](../TECHNICAL_ENGLISH.md) to this skill and to all
prose that it produces.

**Rule:** Select the directory systematically. Then complete the safety checks. These actions give
reliable isolation.

**Do not use this skill for `myrmidon-swarm` worktrees.** That skill creates worktrees for its
background subagents. Use this skill for manual development work.

## Engineering principles

Use the [canonical engineering-principles catalog](../../docs/principles/README.md) through these
workflow-specific rules:

- [P010 — Scope Fidelity](../../docs/principles/README.md#p010): create only the requested isolated
  branch and worktree; leave cleanup and unrelated repository changes to their owning workflows.
- [P012 — Evidence Before Modification](../../docs/principles/README.md#p012): inspect repository
  guidance, the selected base revision, directory state, ignore rules, and baseline checks first.
- [P021 — Evolutionary and Reversible Design](../../docs/principles/README.md#p021): isolate feature
  work at an exact base so it can be reviewed, integrated, preserved, or abandoned independently.
- [P033 — State-Safe Failure Semantics](../../docs/principles/README.md#p033): fail before creation
  when validation fails and preserve any created worktree when later setup or tests fail.
- [P053 — Validate at Trust Boundaries](../../docs/principles/README.md#p053): pass branch, base, path,
  and path-root values through the tested helper's validation rather than composing raw Git commands.
- [P058 — Bounded Agent Authority](../../docs/principles/README.md#p058): bind creation to the named
  branch, exact start SHA, validated destination, and requested feature scope.
- [P065 — Verify Before Claiming Completion](../../docs/principles/README.md#p065): report the actual
  path and start SHA and run the repository-defined clean-baseline checks before declaring readiness.
- [P083 — Irreversible Actions Last](../../docs/principles/README.md#p083): complete dry-run and safety
  validation before creating the branch and worktree, and delegate later removal to `tidy`.

## Select the directory

Follow this priority order:

### 1. Check existing directories

The tested `scripts/prepare_worktree.py` helper checks `.worktrees` and then `worktrees`. If both
directories exist, the helper selects `.worktrees`.

### 2. Check repository guidance

Read `AGENTS.md` and its referenced repository guidance. If repository guidance specifies a
preference, pass it to the helper with `--directory DIRECTORY`.

### 3. Portable default

If the repository does not specify a location, use the host temporary directory from
`tempfile.gettempdir()` with `<project>-<branch>`. On Unix-like hosts, this directory is usually
`/tmp`. This location keeps the worktree outside the project directory.

The helper computes the project name from the repository root.

## Verify safety

### For project-local directories

Before you create a project-local worktree, verify that Git ignores its directory. If Git does not
ignore the directory, the helper stops before it makes a change.

#### If Git does not ignore the directory

1. Do not edit `.gitignore`.
2. Do not commit `.gitignore`.
3. Do not create the project-local worktree.
4. If repository guidance requires the project-local directory, report the ignore-policy
   prerequisite.
5. If repository guidance requires the project-local directory, stop.
6. Change `.gitignore` only in a separate authorized change.
7. After that change is validated and committed, prepare the worktree again.
8. If repository guidance does not require the project-local directory, get `<temporary-root>` from
   the host.
9. Give preference to a safe temporary destination.
10. Pass `--path <temporary-root>/<project>-<branch>` and `--path-root <temporary-root>` to the helper.
11. Report the fallback path.

This check prevents Git from tracking the worktree contents.

### For `/tmp` locations

You do not have to verify `.gitignore` for a path under `/tmp`. This path is outside the project.

## Create the worktree

1. Resolve the intended base commit SHA.
2. Record the intended base commit SHA.
3. Keep the target repository as the current working directory.
4. Resolve `scripts/prepare_worktree.py` from this installed skill directory.
5. Prepare `BRANCH_NAME --start-point BASE_SHA --dry-run` as the helper arguments.
6. If the contract requires a distinct branch and path, add exact `--path` and `--path-root` values.
7. If repository guidance specifies a directory, add it through `--directory`.
8. If an unignored local directory requires the temporary fallback, retain the exact `--path` and
   `--path-root` values.
9. For this fallback, use those values for both helper calls.
10. Invoke the helper by its absolute path with the prepared dry-run arguments.
11. Create the worktree with the same arguments without `--dry-run`.
12. Do not replace the recorded SHA with the current `HEAD`.
13. Change to the returned path.
14. If the repository defines a bootstrap, run it.
15. Use the repository tests to verify a clean baseline.
16. Report the path, start SHA, and result.

**If the tests fail:** Report the failures. Ask whether to continue or investigate.

**If the tests pass:** Report that the worktree is ready.

## Clean up

When the work is complete, invoke `tidy` for branch and worktree cleanup. `tidy` prepares the trusted
Hephaestus dependency. It delegates the work directly to `hephaestus-tidy`. The interactive workflow
controls discovery, preservation rules, deletion prompts, rebases, and cleanup safeguards. Do not
duplicate that policy. Do not write deletion commands in this skill.

Preserve the worktree by default. Delivery, merge, abandonment, or a general cleanup request does
not authorize this skill to remove the worktree. Use `tidy` for each cleanup. The Hephaestus
workflow and the user's answers to its prompts control the removal decision.

## Quick Reference

| Situation | Action |
| ----------- | -------- |
| `.worktrees/` exists and is ignored | Use it. |
| Neither exists | Use the host temporary directory with `<project>-<branch>` |
| Directory is not ignored | Use an explicit temporary path. Report the path. If the repository requires a local path, stop. |
| Tests fail at baseline | Report the failures. Ask before you continue. |

## Failed approaches

- Do not skip ignore verification for a project-local worktree. Git can track the worktree contents.
- If the baseline tests fail, do not continue unless the user explicitly tells you to continue. You
  cannot separate new defects from existing defects.
- When cleanup is authorized, use `tidy`. Do not leave stale worktrees.

## Related workflow

- Invoke `tidy` for dependency-locked delegation to Hephaestus branch and worktree cleanup.
- Before you report completion or start cleanup, get fresh runnable evidence. Follow the
  evidence-integrity policy.

---

_Adapted from [obra/superpowers](https://github.com/obra/superpowers) under the [MIT License](https://github.com/obra/superpowers/blob/main/LICENSE). Copyright (c) 2025 Jesse Vincent._
