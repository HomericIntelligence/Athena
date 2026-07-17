---
name: tidy
description: Audit and clean up Git worktrees first, then safely tidy branches using required Hephaestus automation. Uses Athena's canonical dependency-resolution contract and fails if ~/.agent_brain/automation cannot be prepared. Worktree mutation always needs separate per-gate approval.
argument-hint: "<optional: --dry-run | --no-swarm | --trunk BRANCH | --max-concurrent N>"
allowed-tools: [Bash, Read, Agent]
---

# Tidy worktrees and branches

Use this when the user asks to inspect or rebase local branches onto the repository's default trunk,
or to clean up the repository's worktrees. The skill always runs in two phases: a worktree audit and
cleanup first, then the branch tidy. A user request to "tidy" or "clean up" is not blanket authority
to commit, push, create a PR, discard files, or remove a worktree.

## Phase 1: worktree audit and cleanup

The audit is read-only: inventory and classify state, then stop for per-gate approvals.

1. Confirm the repository root and remote identity.
2. Keep the target repository as the current working directory. Resolve `scripts/audit_worktrees.py`
   against this installed skill directory and invoke that absolute helper path. Retain its JSON
   inventory containing every registered path, branch, lock reason, detached state, status, recent
   commits, and HEAD.
3. Quote each path when presenting the inventory and preserve the machine-readable evidence.
4. Determine remote/PR state with read-only Git and `gh` queries. Do not assume `origin/main`;
   discover the remote default branch.
5. Classify each worktree:

   | State | Meaning | Default action |
   | --- | --- | --- |
   | `KEEP` | Open work, open PR, detached state, or ambiguity | Report only |
   | `DIRTY` | Modified or untracked files | Report exact paths only |
   | `UNPUBLISHED` | Commits are not safely represented remotely | Report only |
   | `REMOVABLE_CANDIDATE` | Clean and independently proven represented on the default branch | Offer removal approval |

Patch-ID, tree comparison, and PR state are supporting signals. A squash merge can invalidate
patch-ID assumptions, so no single signal proves removability.

### Approval gates

After presenting the complete audit, offer each gate separately with the exact worktree, branch,
files, commits, remote, and command that would be affected. Approval for one gate does not authorize
another. Proceed to Phase 2 after the gates are resolved or declined; declined gates leave the
affected worktrees in place.

#### Gate A: salvage and commit

Require explicit approval before staging or committing. Before asking:

- Inspect every candidate diff and untracked file; never infer safety from filename alone.
- Exclude generated artifacts and credentials. Run the repository's secret scanner when available;
  if no scanner is available, report that gap and require the user to review the exact staged diff.
- Reject `.env*`, private keys, tokens, credential stores, personal data, and symlinks escaping the
  worktree.
- Stage only user-approved explicit paths, never `git add -A` or `git add .`.
- Show `git diff --cached` before committing.

Create a cryptographically signed, DCO-attested Conventional Commit using the repository's required
identity and hooks. If signing or hooks fail, stop; never fall back to an unsigned commit or
`--no-verify`.

#### Gate B: push or pull request

Require a second explicit approval after Gate A evidence. Show the exact remote, branch, commits,
and PR base. Push only the named feature branch without force. Create a PR only when separately
authorized, follow repository policy, and never enable auto-merge.

#### Gate C: worktree removal

Require a third explicit approval for each `REMOVABLE_CANDIDATE`. Immediately before removal, run
the absolute `scripts/remove_worktree.py` helper resolved against this installed skill directory,
while retaining the target repository as the current working directory, with
`PATH --expected-head AUDITED_HEAD`. It rechecks registration, current location, cleanliness, and
HEAD before removing only that approved worktree. It does not prune unrelated registrations. If
any check changed, return to audit.

Never use `--force`. A locked worktree must be re-audited; unlocking it also requires explicit
approval. Never remove the user's current worktree or a worktree created by another active process.

## Phase 2: branch tidy

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
- Never remove a worktree with `--force` or outside Gate C.
- Never touch a pre-existing worktree beyond the audited, separately approved actions.
- Never discard, reset, stash-drop, force-push, or bulk-delete worktree directories.
- Never commit or publish a file merely because an agent believes it is related.
- Never combine approvals or treat silence as consent.
- Never enable auto-merge or push without explicit user authority.
- Preserve blocked worktrees in place and report the safest next command.

## Output

First return one row per worktree with path, branch/HEAD, cleanliness, remote/PR evidence,
classification, and action taken. In the default mode every worktree action is `none (audit only)`;
for an approved mutation, record the approval gate, exact command, resulting SHA, and verification
result. Then report the branch-tidy results: rebased, already-subsumed, and still-failing branches
separately.
