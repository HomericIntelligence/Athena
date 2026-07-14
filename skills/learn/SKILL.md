---
name: learn
description: Preserve a verified lesson in the required Mnemosyne knowledge repository and always deliver it through a pull request. Resolves HOMERIC_INTELLIGENCE_MNEMOSYNE_OWNER, a canonically forked repository in the current Organization when the viewer has push/maintain/admin permission, or HomericIntelligence/Mnemosyne, and fails if ~/.agent_brain/knowledge cannot be prepared.
argument-hint: <lesson or session summary>
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob]
---

# Learn

Capture behavior-changing knowledge in Mnemosyne. This workflow always creates a branch, signed
commit, push, and pull request. It never writes directly to a default branch and never treats a
local-only edit as success.

## Resolve the knowledge repository

Use the same mandatory resolution contract as `advise`:

1. An explicit `HOMERIC_INTELLIGENCE_MNEMOSYNE_OWNER` selects
   `<owner>/Mnemosyne` and fails closed when unreadable.
2. Otherwise prefer `<current-repository-owner>/Mnemosyne` only when the owner is an Organization,
   the viewer has `WRITE` (push), `MAINTAIN`, or `ADMIN` permission on the current repository, and
   GitHub confirms `parent.full_name` is `HomericIntelligence/Mnemosyne`. Modified organization fork
   content is allowed after all gates pass.
3. Otherwise use `HomericIntelligence/Mnemosyne`.

Prepare and verify `$HOME/.agent_brain/knowledge`: clone when absent; otherwise require the expected
origin, fetch it, and fast-forward its remote default branch without overwriting local changes.
Report repository, SHA, and trust basis. For an automatically selected fork, immediately before use
repeat the owner-type, viewer-permission, canonical-parent, identity, default-branch, and tip-SHA
checks and require the checkout to match.
Authentication, detection, checkout, or update failure is fatal.

## Before writing

1. Run `advise` with the proposed lesson.
2. Search flat `skills/*.md`, excluding notes and history, for semantic overlap.
3. Search `.history` and Git history for prior consolidation.
4. Amend the canonical entry when its intent matches; create a new entry only for a distinct search
   intent. If the proposed lesson contains no material knowledge or verification change, fail with
   `no learnable change` before mutating anything. Do not report `learn` as completed.

Repository audits belong in `repo-review`; PR audits belong in `pr-review`; review depth is a mode,
not another skill.

## Isolated write contract

Never modify the shared checkout's active worktree. From its fetched default branch:

1. Derive `slug` and `name` using only lowercase ASCII letters, digits, and single hyphens. Require
   the pattern `[a-z0-9][a-z0-9-]*`; reject `/`, `..`, leading `-`, control characters, and empty
   values. Add a short collision-resistant suffix when the branch or worktree already exists.
2. Create an isolated worktree under `$HOME/.agent_brain/worktrees/knowledge-<slug>` on branch
   `skill/<slug>`. Resolve the path before creating it and require it to remain directly beneath
   `$HOME/.agent_brain/worktrees`; reject symlinked parents or destinations.
3. Write `skills/<name>.md` only after resolving the destination and proving it remains directly
   beneath the worktree's `skills/` directory. Include name, searchable description, category, date, semantic version,
   verification level, tags, when-to-use, verified workflow, failed attempts, results, parameters,
   and evidence.
4. For an amendment, append `.history` with the old/new versions and evidence. Optional raw detail
   belongs in `.notes.md`.
5. Run the resolved Mnemosyne repository's own validation and tests.
6. Verify no duplicate intent or stale consolidated name was introduced.
7. Commit with a cryptographic signature and DCO sign-off, push the feature branch, and open a PR
   against the resolved repository's default branch. The PR body must contain `Closes #N` when a
   tracking issue exists.
8. Report the PR URL and exact validation evidence. Do not auto-merge.

If a push or PR cannot be created, preserve the isolated worktree and report the blocker. A Learn
run is successful only when it returns a PR URL. Never fall back to writing inside Athena or a
different repository.
