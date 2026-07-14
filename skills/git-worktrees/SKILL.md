---
name: git-worktrees
description: Use when starting feature work that needs isolation from current workspace — creates isolated git worktrees with safety verification
argument-hint: <branch-name or feature description>
allowed-tools: [Bash, Read]
---

# Using Git Worktrees

## Overview

Git worktrees create isolated workspaces sharing the same repository, allowing work on multiple branches simultaneously without switching.

**Core principle:** Systematic directory selection + safety verification = reliable isolation.

**When NOT to use this skill manually:** The `myrmidon-swarm` skill owns worktree creation for its
background subagents. Use this skill for manual development work, not to duplicate swarm setup.

## Directory Selection

Follow this priority order:

### 1. Check Existing Directories

The tested `scripts/prepare_worktree.py` helper checks `.worktrees` and then `worktrees`. If both
exist, `.worktrees` wins.

### 2. Check repository guidance

Read `AGENTS.md` and its referenced repository guidance. If a preference is specified, pass it to
the helper with `--directory DIRECTORY`.

### 3. Portable default

When no repository preference exists, use `/tmp/<project>-<branch>`. This avoids polluting the
project directory.

The helper computes the project name from the repository root.

## Safety Verification

### For Project-Local Directories (.worktrees or worktrees)

**MUST verify directory is ignored before creating worktree.** The helper fails closed when its
project-local directory is not ignored.

**If NOT ignored:**

1. Add `.worktrees/` to `.gitignore`
2. Commit the change
3. Then proceed with worktree creation

**Why critical:** Prevents accidentally committing worktree contents to repository.

### For /tmp Locations

No `.gitignore` verification needed — outside the project entirely.

## Creation Steps

1. Preview selection and validation with `scripts/prepare_worktree.py BRANCH_NAME --dry-run` from
   this skill directory.
2. Create it with `scripts/prepare_worktree.py BRANCH_NAME`, optionally supplying the documented
   repository preference through `--directory`.
3. Change to the returned path and run the repository-defined bootstrap when one exists.
4. Verify a clean baseline with the repository-defined tests and report the path and result.

**If tests fail:** Report failures, ask whether to proceed or investigate.

**If tests pass:** Report ready.

## Cleanup

When work is done, invoke `finish-branch` or use the separately approved removal flow in
`worktree-cleanup`; do not improvise deletion commands.

**For Options merge/discard:** Clean up immediately.
**For Option keep/PR open:** Preserve the worktree.

## Quick Reference

| Situation | Action |
|-----------|--------|
| `.worktrees/` exists + ignored | Use it |
| Neither exists | Use `/tmp/<project>-<branch>` |
| Directory not ignored | Add to `.gitignore` + commit first |
| Tests fail at baseline | Report failures + ask before proceeding |

## Common Mistakes

- **Skipping ignore verification** for project-local worktrees → contents get tracked
- **Proceeding with failing baseline** → can't distinguish new bugs from pre-existing
- **Not cleaning up** → stale worktrees accumulate

## Integration

**Pairs with:**

- Invoke `finish-branch` for cleanup after work is complete.
- Invoke `verification` before finishing and cleaning up.

---

_Adapted from [obra/superpowers](https://github.com/obra/superpowers) under the [MIT License](https://github.com/obra/superpowers/blob/main/LICENSE). Copyright (c) 2025 Jesse Vincent._
