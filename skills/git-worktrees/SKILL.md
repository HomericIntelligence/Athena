---
name: git-worktrees
license: BSD-3-Clause
description: Use when starting feature work that needs isolation from current workspace — creates isolated git worktrees with safety verification. Fails closed, reporting and stopping without creating or deleting anything when the target directory is not ignored or a clean base commit cannot be verified.
argument-hint: <branch-name or feature description>
allowed-tools: [Bash, Read]
---

# Use Git worktrees

## Overview

Git worktrees create isolated workspaces that share one repository. They let you work on multiple
branches without switching the active branch.

Apply the [ASD-STE100 writing policy](../../docs/technical-english.md) to this skill and to all prose
that it produces.

**Working rule:** Systematic directory selection plus safety verification produces reliable
isolation.

**When NOT to use this skill manually:** The `myrmidon-swarm` skill owns worktree creation for its
background subagents. Use this skill for manual development work, not to duplicate swarm setup.

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

## Directory Selection

Follow this priority order:

### 1. Check Existing Directories

The tested `scripts/prepare_worktree.py` helper checks `.worktrees` and then `worktrees`. If both
exist, `.worktrees` wins.

### 2. Check repository guidance

Read `AGENTS.md` and its referenced repository guidance. If a preference is specified, pass it to
the helper with `--directory DIRECTORY`.

### 3. Portable default

When no repository preference exists, use the host's temporary directory from
`tempfile.gettempdir()` with `<project>-<branch>`. This is commonly `/tmp` on Unix-like hosts and
avoids polluting the project directory.

The helper computes the project name from the repository root.

## Safety Verification

### For Project-Local Directories (.worktrees or worktrees)

**MUST verify directory is ignored before creating worktree.** The helper fails closed when its
project-local directory is not ignored.

**If NOT ignored:**

1. Do not silently edit or commit `.gitignore`, and do not create the project-local worktree.
2. Prefer a safe temporary destination by passing both
   `--path <temporary-root>/<project>-<branch>` and `--path-root <temporary-root>` to the helper;
   derive `<temporary-root>` from the host and report the fallback path.
3. If repository guidance requires the project-local directory, report the unmet ignore-policy
   prerequisite and stop. Change `.gitignore` only as a separately authorized, scoped change; after
   that change is validated and committed, rerun worktree preparation.

**Why critical:** Prevents accidentally committing worktree contents to repository.

### For /tmp Locations

No `.gitignore` verification needed — outside the project entirely.

## Creation Steps

1. Resolve and record the intended base commit SHA.
2. Keep the target repository as the current working directory. Resolve `scripts/prepare_worktree.py`
   against this installed skill directory and invoke that absolute helper path with
   `BRANCH_NAME --start-point BASE_SHA --dry-run`. For a contract requiring a distinct branch and
   path, also pass exact `--path` and `--path-root` values.
3. Create it with the same arguments without `--dry-run`, optionally supplying the documented
   repository preference through `--directory`. When an unignored local directory requires the
   temporary fallback, pass the same exact `--path` and `--path-root` to both calls. Never replace
   the recorded SHA with ambient HEAD.
4. Change to the returned path and run the repository-defined bootstrap when one exists.
5. Verify a clean baseline with the repository-defined tests and report the path, start SHA, and result.

**If tests fail:** Report failures, ask whether to proceed or investigate.

**If tests pass:** Report ready.

## Cleanup

When work is done, invoke `tidy` for branch and worktree cleanup. It prepares the trusted
Hephaestus dependency and delegates directly to `hephaestus-tidy`, whose interactive workflow owns
discovery, preservation rules, deletion prompts, rebases, and cleanup safeguards. Do not duplicate
that policy or improvise deletion commands in this skill.

Preserve the worktree by default. Delivery, merge, abandonment, or a general cleanup request does
not itself authorize this skill to remove it; route any cleanup through `tidy` and leave the
decision to the Hephaestus workflow and the user's answers to its prompts.

## Quick Reference

| Situation | Action |
| ----------- | -------- |
| `.worktrees/` exists + ignored | Use it |
| Neither exists | Use the host temporary directory with `<project>-<branch>` |
| Directory not ignored | Use and report an explicit temporary path, or stop on a repository-mandated local path |
| Tests fail at baseline | Report failures + ask before proceeding |

## Failed approaches

- **Skipping ignore verification** for project-local worktrees → contents get tracked
- **Proceeding with failing baseline** → can't distinguish new bugs from pre-existing
- **Not cleaning up** → stale worktrees accumulate

## Integration

**Pairs with:**

- Invoke `tidy` for dependency-locked delegation to Hephaestus branch and worktree cleanup.
- Verify with fresh runnable evidence per the evidence-integrity policy before finishing and
  cleaning up.

---

_Adapted from [obra/superpowers](https://github.com/obra/superpowers) under the [MIT License](https://github.com/obra/superpowers/blob/main/LICENSE). Copyright (c) 2025 Jesse Vincent._
