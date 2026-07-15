---
name: tidy
description: Safely tidy branches using required Hephaestus automation. Uses Athena's canonical dependency-resolution contract and fails if ~/.agent_brain/automation cannot be prepared.
argument-hint: "<optional: --dry-run | --no-swarm | --trunk BRANCH | --max-concurrent N>"
allowed-tools: [Bash, Read, Agent]
---

# Tidy branches

Use this when the user asks to inspect or rebase local branches onto the repository's default trunk.

## Workflow

1. Confirm the repository and default branch. Stop if the working tree has uncommitted changes that
   would be affected.
2. Prepare Hephaestus at `$HOME/.agent_brain/automation` under the canonical
   [`dependency-resolution` contract](../../docs/dependency-resolution.md). Do not restate or
   override that contract here. Report repository, SHA, and trust basis; any preparation or
   revalidation failure is blocking.
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
