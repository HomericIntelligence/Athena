---
name: learn
description: Preserve a verified lesson in required Mnemosyne and always deliver it through a pull request. Uses Athena's canonical dependency-resolution contract and fails if ~/.agent_brain/knowledge cannot be prepared.
argument-hint: <lesson or session summary>
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent]
---

# Learn

Capture behavior-changing knowledge in Mnemosyne. This workflow always creates a branch, signed
commit, push, and pull request. It never writes directly to a default branch and never treats a
local-only edit as success.

## Prepare the knowledge repository

Prepare Mnemosyne at `$HOME/.agent_brain/knowledge` by following the canonical
[`dependency-resolution` contract](../../docs/dependency-resolution.md) exactly. Do not restate its
owner precedence, trust gates, checkout rules, or revalidation requirements in this skill. Report
the exact repository, commit SHA, and trust basis. Any resolution, authentication, checkout, update,
or revalidation failure is blocking.

## Before writing

1. Run `advise` with the proposed lesson.
2. Derive the canonical retrieval intent: the trigger/context, desired outcome,
   constraints, and failure mode another agent needs to recognize. Do not use a
   title, issue number, or session wording as the identity.
3. Search flat `skills/*.md`, excluding optional notes, for every semantic
   match. Group entries by retrieval intent rather than title, issue number, or
   wording, then inspect each same-intent candidate.
4. Search Git history for prior consolidation, provenance, and the durable
   decision rule each candidate preserves.
5. Query every open pull request in the resolved Mnemosyne repository. Enumerate its changed flat
   `skills/*.md` artifacts and inspect their changed content to derive each retrieval intent; a title
   or candidate path is only a discovery aid, never sufficient duplicate evidence. If any open pull
   request has the same or an ambiguous retrieval intent, fail closed: leave Mnemosyne unchanged and
   obtain user direction before mutation. Work atop that branch only with explicit authority; never
   create a conflicting PR.
6. Record one disposition before mutating: `amend`, `consolidate`, `create`, or
   `reject`.
   - Amend exactly one canonical entry when its retrieval intent matches and
     there is a material verified decision-rule, workflow, parameter, or
     failure-mode delta.
   - Consolidate when two or more current entries have the same retrieval
     intent: select one canonical entry, merge every non-superseded verified
     rule, and retire the duplicates in the same pull request.
   - Create only for a materially distinct intent.
   - Reject the lesson as `no learnable change` when it adds no durable,
     verified delta.

   An ambiguous candidate set, semantic overlap in an open pull request,
   unverifiable delta, or unsafe retirement is a blocking consolidation failure.
   Leave Mnemosyne unchanged, report the candidate paths and intent evidence
   gap, and obtain user direction; do not evade consolidation by creating
   another near-duplicate.
   Do not report `learn` as completed after a rejection or blocked
   consolidation.

## Canonicalization rules

Generalize a lesson into the smallest reusable decision rule that safely applies
across similar tasks. Preserve task-specific facts only when they are required
to execute or verify that rule. Do not create near-duplicates for different
repositories, issue numbers, tool output, names, timestamps, or conversational
phrasing when the trigger and desired outcome already match a canonical entry.

Before adding new guidance, consolidate every verified same-intent set into one
canonical entry. Choose the entry with the clearest reusable retrieval intent
and strongest provenance, fold all non-superseded verified deltas into it, and
retire duplicate entries in the same pull request. Preserve history in Git; do
not retain duplicate active entries merely as provenance. If a candidate has a
materially distinct rule, an active consumer that cannot be safely migrated, or
uncertain provenance, stop without mutation and request direction.

An amendment folds the new verified delta into one already-canonical entry and
removes superseded or repeated guidance. A creation names the distinct trigger
and outcome precisely enough for retrieval. A rejection leaves Mnemosyne
unchanged and reports the matching entry or the reason the evidence is not
durable.

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
or unexpected scope. When the host does not provide native isolation, retain the resolved Mnemosyne
checkout as the current working directory and invoke Athena's tested
`../git-worktrees/scripts/prepare_worktree.py` by its absolute path resolved from this skill
directory, with the exact `skill/<slug>` branch,
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
   beneath the worktree's `skills/` directory. Include a searchable intent,
   semantic version, verification level, generalized when-to-use and workflow,
   relevant failed approaches, parameters, and evidence. Omit session transcript
   detail that no active consumer needs.
4. For an amendment, update only the canonical entry, fold in the verified
   delta, and remove repeated or superseded guidance. For a consolidation,
   merge every non-superseded verified rule into the selected canonical entry,
   retire each duplicate in the same pull request, and preserve provenance in
   Git history. Do not retire a candidate until its active consumers are safely
   migrated under the authorized scope; otherwise stop without mutation.
   Optional raw evidence may be added to `.notes.md` only when a current
   consumer needs it.
5. Run the resolved Mnemosyne repository's own validation and tests.
6. Verify exactly one active entry remains for the retrieval intent and no
   duplicate intent or stale consolidated name was introduced.
7. Commit with a cryptographic signature and DCO sign-off, push the feature branch, and open a PR
   against the resolved repository's default branch. The PR body must contain `Closes #N` when a
   tracking issue exists.
8. Report the `amend`, `consolidate`, or `create` disposition, retired entries
   when applicable, PR URL, and exact validation evidence. Do not auto-merge.

If a push or PR cannot be created, preserve the isolated worktree and report the blocker. A Learn
run is successful only when it returns a PR URL. Never fall back to writing inside Athena or a
different repository.

Preserve all delegated and delivery worktrees until their unique work is integrated or explicitly
rejected. Cleanup is a separate mutation: remove only worktrees created by this Learn invocation,
only with user authority, and only after rechecking that no uncommitted or unintegrated state
remains. Otherwise report each worktree's path, owner, revision, cleanliness, and integration state
and leave it intact. Never delete branches, discard changes, force removal, or touch a pre-existing
worktree.
