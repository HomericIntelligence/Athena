---
name: finish-branch
description: Finish a branch using required Hephaestus automation for repository and merge-policy discovery. Uses Athena's canonical dependency-resolution contract and fails if ~/.agent_brain/automation cannot be prepared.
argument-hint: "<optional: base branch name>"
allowed-tools: [Bash, Read]
---

# Finish a development branch

Use `verification` first. Do not proceed while relevant repository-defined checks fail.

## Workflow

1. Read `AGENTS.md` and [`docs/policies/development.md`](../../docs/policies/development.md).
2. Prepare Hephaestus at `$HOME/.agent_brain/automation` under the canonical
   [`dependency-resolution` contract](../../docs/dependency-resolution.md). Do not restate or
   override that contract here. Report repository, SHA, and trust basis; any preparation or
   revalidation failure is blocking.
3. Discover the default branch and repository-defined validation commands from its task runner,
   manifests, and required workflow. Do not substitute Hephaestus-specific commands.
4. Run the relevant tests, validation, formatting, linting, and build/package checks. Report exact
   commands and results.
5. Review `git log <base>..HEAD` and both the merge-base and current-base diffs.
6. Verify every commit is cryptographically signed, has a DCO `Signed-off-by` trailer, and follows
   Conventional Commits. Fix violations before offering delivery.
7. Present three choices: create/update a pull request, preserve the branch and worktree, or request
   a separate read-only `worktree-cleanup` audit. Do not represent a cleanup request as removal
   authority.
8. For a PR, push only the feature branch and create a body containing `Closes #N` when a tracking
   issue exists. Do not enable auto-merge or merge without explicit user authority.
9. Never remove a worktree directly. Route each candidate through `worktree-cleanup`, which requires
   a fresh audit and separate explicit Gate C approval for the exact path and audited HEAD.

## Merge-method helper

Use the resolved Hephaestus checkout's current merge-method helper when the target repository does
not provide its own. Never use an unrelated executable from `PATH` or guess an organization-wide
merge method.

## Never

- Merge directly to the protected default branch.
- Skip hooks, fabricate successful checks, or force-push without explicit authority.
- Delete a branch or worktree without the required confirmation.
- Claim completion while CI is absent, stale, skipped incorrectly, or failing.

_Adapted from obra/superpowers under the MIT License. See `skills/THIRD_PARTY_LICENSES.md`._
