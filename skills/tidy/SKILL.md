---
name: tidy
description: Safely tidy branches using required Hephaestus automation. Resolves HOMERIC_INTELLIGENCE_HEPHAESTUS_OWNER, a canonically forked repository in the current Organization when the viewer has push/maintain/admin permission, or HomericIntelligence/Hephaestus, and fails if ~/.agent_brain/automation cannot be prepared.
argument-hint: "<optional: --dry-run | --no-swarm | --trunk BRANCH | --max-concurrent N>"
allowed-tools: [Bash, Read, Agent]
---

# Tidy branches

Use this when the user asks to inspect or rebase local branches onto the repository's default trunk.

## Workflow

1. Confirm the repository and default branch. Stop if the working tree has uncommitted changes that
   would be affected.
2. Resolve Hephaestus using `HOMERIC_INTELLIGENCE_HEPHAESTUS_OWNER`, then a canonical
   `<current-owner>/Hephaestus` fork only when the current owner is an Organization and the viewer
   has push/maintain/admin permission on the current repository, then
   `HomericIntelligence/Hephaestus`. Prepare it at `$HOME/.agent_brain/automation` under
   [`docs/dependency-resolution.md`](../../docs/dependency-resolution.md). Failure is blocking.
   Report repository, SHA, and trust basis. Before using an automatic fork, reverify Organization
   ownership, viewer permission, `parent.full_name`, identity, default branch, tip SHA, and checkout.
3. Run `hephaestus-tidy` from the resolved checkout's locked environment and forward arguments
   exactly; `--dry-run` is the safe preview. Never use an unrelated executable found on `PATH`.
4. The user answers any interactive deletion prompt. Athena never answers it automatically.
5. For failed rebases, use one isolated worktree per branch. Delegate independent branches when the
   host supports subagents; otherwise process them sequentially.
6. Resolve conflicts semantically, run branch-relevant tests, and use only `--force-with-lease`
   plus `--force-if-includes` when the user has authorized a push.
7. Report rebased, already-subsumed, and still-failing branches separately.

## Invariants

- Never delete local or remote branches.
- Never remove a worktree with `--force`.
- Never touch a pre-existing worktree.
- Never enable auto-merge or push without explicit user authority.
