---
name: learn
description: Preserve a verified, non-duplicate Mnemosyne lesson through an isolated-worktree pull request when direct write authority exists; otherwise report without mutation. Fails closed if ~/.agent_brain/knowledge cannot be prepared.
argument-hint: <lesson or session summary>
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent]
---

# Learn

Why: one general, canonical rule is more discoverable and safer than many session-specific copies.
First decide whether a durable delta exists; write only an authorized result through a reviewable PR.

## Prepare the knowledge repository

Prepare Mnemosyne at `$HOME/.agent_brain/knowledge` under the canonical
[`dependency-resolution` contract](../../docs/dependency-resolution.md). Report the resolved
repository, commit SHA, and trust basis. Any resolution, authentication, checkout, update, or
revalidation failure is blocking.

## Decide before writing

This phase is read-only.

1. Run `advise` with the proposed lesson.
2. Define retrieval intent as the trigger/context, desired outcome, constraints, and failure mode;
   never use title, issue number, or session wording as identity.
3. Search flat `skills/*.md` (not optional notes), group semantic matches by intent, and inspect each
   candidate and its Git history for provenance and prior consolidation.
4. Inspect every open PR in the resolved Mnemosyne repository: enumerate its changed flat
   `skills/*.md` artifacts and derive intent from their changed content. A title or path only finds a
   candidate; it is never sufficient duplicate evidence.
5. Record exactly one disposition before mutation:

   | Disposition | Use when | Action |
   | --- | --- | --- |
   | `amend` | One canonical entry has a material verified delta. | Update that entry only. |
   | `consolidate` | Two or more current entries share intent. | Select one canonical entry, merge non-superseded rules, and retire duplicates in the same PR. |
   | `create` | Intent is materially distinct. | Add one precisely named entry. |
   | `reject` | No durable, verified delta exists. | Report `no learnable change`; leave Mnemosyne unchanged. |
   | `blocked` | Candidates or an open PR have same or ambiguous intent, provenance is uncertain, or retirement is unsafe. | Leave Mnemosyne unchanged and request direction. |

Never evade a blocked consolidation by creating a near-duplicate. An existing matching or ambiguous
open PR is a no-mutation boundary; work on its branch only with explicit user authority and never
create a competing PR. Do not report `learn` complete after `reject` or `blocked`.

Generalize the smallest reusable decision rule. Keep task-specific facts only when another agent
needs them to execute or verify that rule. Preserve history in Git, not duplicate active entries.
Repository audits belong in `repo-review`; PR audits belong in `pr-review`; review depth is a mode.

If a lesson requires Athena implementation, complete that normal development first. Follow
[`development.md`](../../docs/policies/development.md): keep helpers in `skills/<name>/scripts/`,
add behavior-based executable tests under `tests/unit/`, and do not add inline executable Markdown,
wording tests, or non-consumed artifacts merely to support a lesson.

## Authority

Read-only discovery never authorizes mutation. Before creating a branch or worktree, editing,
committing, pushing, or opening a PR, establish authority for the resolved repository and full
delivery path. A direct user request to invoke `learn` supplies it; a recommendation or indirect
invocation does not. Without it, return the read-only disposition and proposed repository, base,
branch, files, and PR target.

## Coordinate safely

When available, partition independent discovery, overlap analysis, drafting, and verification into
bounded work items; otherwise perform them sequentially without weakening evidence. Give every
writer an isolated worktree from the same resolved default-branch SHA and non-overlapping ownership;
read-only work items never edit. The coordinator owns each canonical entry or assigns one integration
owner, rejects unrelated edits, runs focused validation after each integration and complete relevant
validation after the combined result, and alone commits, pushes, and opens the PR. Stop on ownership
overlap, base drift, or unexpected scope.

Without native isolation, retain the resolved checkout as the current directory and invoke the
installed `../git-worktrees/scripts/prepare_worktree.py` by absolute path with branch `skill/<slug>`,
`--path $HOME/.agent_brain/worktrees/knowledge-<slug>`,
`--path-root $HOME/.agent_brain/worktrees`, and `--start-point <resolved-default-SHA>`.

## Deliver an authorized change

1. Never modify the shared checkout. Derive `slug` and `name` from lowercase ASCII letters, digits,
   and single hyphens using `[a-z0-9][a-z0-9-]*`; reject empty, control, `/`, `..`, and leading `-`
   values. Add a collision-resistant suffix when needed.
2. Create branch `skill/<slug>` at `$HOME/.agent_brain/worktrees/knowledge-<slug>`; resolve the path
   first, require it directly below `$HOME/.agent_brain/worktrees`, and reject symlinked parents or
   destinations.
3. Resolve and write only `skills/<name>.md` below that worktree's `skills/` directory. Include
   searchable intent, semantic version, verification, generalized use and workflow, relevant failed
   approaches, parameters, and evidence; omit unused session transcript detail.
4. Apply the selected disposition. Amend only the canonical entry. During consolidation, migrate
   active consumers before retiring duplicates; optional `.notes.md` evidence needs a current consumer.
5. Run Mnemosyne's relevant complete validation. Verify exactly one active entry remains for the
   intent and no duplicate intent or stale consolidated name was introduced.
6. Sign and DCO-attest the commit, push the feature branch, and open a PR against the resolved default
   branch. Include `Closes #N` when a tracking issue exists; never auto-merge.
7. Report the disposition, any retired entries, PR URL, and exact validation evidence.

A write disposition succeeds only with its PR URL. If validation, push, or PR creation fails, preserve
the isolated worktree and report the blocker; never fall back to Athena, a default branch, or another
repository. Preserve delegated and delivery worktrees until their unique work is integrated or
explicitly rejected. Cleanup is separate: remove only worktrees created by this invocation, only with
user authority, only after confirming no uncommitted or unintegrated state remains. Otherwise report
each worktree's path, owner, revision, cleanliness, and integration state and leave it intact. Never
delete branches, discard changes, force removal, or touch a pre-existing worktree.
