---
name: learn
description: Preserve a verified lesson in the required Mnemosyne knowledge repository and always deliver it through a pull request. Resolves HOMERIC_INTELLIGENCE_MNEMOSYNE_OWNER, a canonically forked repository in the current Organization when the viewer has push/maintain/admin permission, or HomericIntelligence/Mnemosyne, and fails if ~/.agent_brain/knowledge cannot be prepared.
argument-hint: <lesson or session summary>
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent]
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
2. Search flat `skills/*.md`, excluding optional notes, for semantic overlap.
3. Search Git history for prior consolidation and provenance.
4. Query open pull requests in the resolved Mnemosyne repository by candidate title and changed
   `skills/<name>.md` path. If one already changes the canonical entry, inspect it and either stack on
   its branch with explicit authority or stop for user direction; never create a conflicting PR.
5. Amend the canonical entry when its intent matches; create a new entry only for a distinct search
   intent. If the proposed lesson contains no material knowledge or verification change, fail with
   `no learnable change` before mutating anything. Do not report `learn` as completed.

Repository audits belong in `repo-review`; PR audits belong in `pr-review`; review depth is a mode,
not another skill.

Learn records verified knowledge; it does not embed executable Athena behavior in Mnemosyne. When a
lesson requires an Athena implementation, first make that change through normal Athena development:
put each Bash or Python helper in `skills/<name>/scripts/`, reference it from the owning `SKILL.md`,
and add executable behavior tests under `tests/unit/`. Never paste an inline Bash or Python program
into skill Markdown. Run the complete Athena gates before learning the verified result through the
mandatory Mnemosyne PR.

Athena skill guidance must follow [`../../docs/policies/development.md`](../../docs/policies/development.md).
Do not teach agents to create prose-string tests, documentation snapshots, manually maintained
changelogs, generated documentation, duplicated registries/catalogs/inventories, or unrelated files.
Tests must exercise computable behavior or executable artifact contracts and fail for the defect
they claim to detect. Apply KISS, YAGNI, TDD, DRY, SOLID, modularity, and least astonishment when
deciding whether a lesson should cause repository work at all.

## External-write authority checkpoint

Before creating a branch or worktree, editing Mnemosyne, committing, pushing, or opening the
mandatory pull request, establish explicit user authority for the resolved repository and the
complete branch, commit, push, and PR workflow. A direct user request to invoke `learn` supplies
that authority. An indirect recommendation or invocation by another skill does not: show the
repository, trust basis, base revision, proposed branch, intended files, and PR target, then obtain
explicit user approval before mutation.

Read-only resolution, search, and planning do not authorize later mutation. If authority is absent,
stop before creating mutable state and report that Learn has not run successfully. Once authorized,
the workflow may not substitute a local-only edit for its mandatory PR outcome.

## Delegation and integration

When the host supports subagents, partition independent discovery, overlap analysis, drafting, and
verification into bounded work items. Run dependency-independent items concurrently in the
background, up to the host's safe limit. If delegation or background execution is unavailable, run
the same items sequentially without weakening their evidence requirements.

Every writing subagent receives an isolated worktree based on the same resolved Mnemosyne default-
branch revision and an explicit, non-overlapping file ownership set. Each canonical knowledge entry
belongs to the coordinator or one designated integration item. Read-only agents may inspect shared
evidence but must not edit it. Stop concurrent work on any ownership overlap, changed base revision,
or unexpected scope. When the host does not provide native isolation, invoke Athena's tested
`../git-worktrees/scripts/prepare_worktree.py` with the exact `skill/<slug>` branch,
`--path $HOME/.agent_brain/worktrees/knowledge-<slug>`,
`--path-root $HOME/.agent_brain/worktrees`, and `--start-point <resolved-default-SHA>`.

The coordinator reviews each result and diff, rejects unrelated edits, and integrates accepted work
sequentially into the single delivery worktree described below. Run focused validation after each
integration and the resolved repository's complete relevant validation after the combined result.
Only the coordinator performs the authorized commit, push, and PR creation.

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
4. For an amendment, update only the canonical entry. Git and pull-request history provide
   provenance; optional raw evidence may be added to `.notes.md` only when a current consumer needs
   it.
5. Run the resolved Mnemosyne repository's own validation and tests.
6. Verify no duplicate intent or stale consolidated name was introduced.
7. Commit with a cryptographic signature and DCO sign-off, push the feature branch, and open a PR
   against the resolved repository's default branch. The PR body must contain `Closes #N` when a
   tracking issue exists.
8. Report the PR URL and exact validation evidence. Do not auto-merge.

If a push or PR cannot be created, preserve the isolated worktree and report the blocker. A Learn
run is successful only when it returns a PR URL. Never fall back to writing inside Athena or a
different repository.

Preserve all delegated and delivery worktrees until their unique work is integrated or explicitly
rejected. Cleanup is a separate mutation: remove only worktrees created by this Learn invocation,
only with user authority, and only after rechecking that no uncommitted or unintegrated state
remains. Otherwise report each worktree's path, owner, revision, cleanliness, and integration state
and leave it intact. Never delete branches, discard changes, force removal, or touch a pre-existing
worktree.
