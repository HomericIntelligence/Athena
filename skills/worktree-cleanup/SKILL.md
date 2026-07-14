---
name: worktree-cleanup
description: Audit every Git worktree without mutation by default, then offer separately approved salvage, publication, and removal actions. Never deletes branches.
argument-hint: "[--dry-run]"
allowed-tools: [Bash, Read]
---

# Worktree cleanup

Audit all worktrees registered to the current repository. The default invocation is read-only:
inventory and classify state, then stop. A user request to “clean up” is not blanket authority to
commit, push, create a PR, discard files, or remove a worktree.

## Read-only audit

1. Confirm the repository root and remote identity.
2. Run `scripts/audit_worktrees.py` from this skill directory. Retain its JSON inventory containing
   every registered path, branch, lock reason, detached state, status, recent commits, and HEAD.
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

## Approval gates

After presenting the complete audit, offer each gate separately with the exact worktree, branch,
files, commits, remote, and command that would be affected. Approval for one gate does not authorize
another.

### Gate A: salvage and commit

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

### Gate B: push or pull request

Require a second explicit approval after Gate A evidence. Show the exact remote, branch, commits,
and PR base. Push only the named feature branch without force. Create a PR only when separately
authorized, follow repository policy, and never enable auto-merge.

### Gate C: worktree removal

Require a third explicit approval for each `REMOVABLE_CANDIDATE`. Immediately before removal, run
`scripts/remove_worktree.py PATH --expected-head AUDITED_HEAD` from this skill directory. The
tested helper rechecks registration, current location, cleanliness, and HEAD before removing and
pruning. If any check changed, return to audit.

Never use `--force`. A locked worktree must be re-audited; unlocking it also requires explicit
approval. Never remove the user's current worktree or a worktree created by another active process.

## Invariants

- Never delete local or remote branches; invoke the `tidy` skill for its separate branch workflow.
- Never discard, reset, stash-drop, force-push, or bulk-delete worktree directories.
- Never commit or publish a file merely because an agent believes it is related.
- Never combine approvals or treat silence as consent.
- Preserve blocked worktrees in place and report the safest next command.

## Output

Return one row per worktree with path, branch/HEAD, cleanliness, remote/PR evidence, classification,
and action taken. In the default mode every action is `none (audit only)`. For an approved mutation,
record the approval gate, exact command, resulting SHA, and verification result.
