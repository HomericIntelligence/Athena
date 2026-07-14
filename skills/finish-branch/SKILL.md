---
name: finish-branch
description: Finish a branch using required Hephaestus automation for repository and merge-policy discovery. Resolves HOMERIC_INTELLIGENCE_HEPHAESTUS_OWNER, a canonically forked repository in the current Organization when the viewer has push/maintain/admin permission, or HomericIntelligence/Hephaestus at ~/.agent_brain/automation and fails when unavailable.
argument-hint: "<optional: base branch name>"
allowed-tools: [Bash, Read]
---

# Finish a development branch

Use `verification` first. Do not proceed while relevant repository-defined checks fail.

## Workflow

1. Read `AGENTS.md` and [`docs/policies/development.md`](../../docs/policies/development.md).
2. Resolve Hephaestus using `HOMERIC_INTELLIGENCE_HEPHAESTUS_OWNER`, then a canonical fork in the
   current Organization only when the viewer has push/maintain/admin permission on the current
   repository, or `HomericIntelligence/Hephaestus`, in that order. Prepare it at
   `$HOME/.agent_brain/automation` under
   [`docs/dependency-resolution.md`](../../docs/dependency-resolution.md). Failure is blocking.
   Report repository, SHA, and trust basis. Before using an automatic fork, reverify Organization
   ownership, viewer permission, `parent.full_name`, identity, default branch, tip SHA, and checkout.
3. Discover the default branch and repository-defined validation commands from its task runner,
   manifests, and required workflow. Do not substitute Hephaestus-specific commands.
4. Run the relevant tests, validation, formatting, linting, and build/package checks. Report exact
   commands and results.
5. Review `git log <base>..HEAD` and both the merge-base and current-base diffs.
6. Verify every commit is cryptographically signed, has a DCO `Signed-off-by` trailer, and follows
   Conventional Commits. Fix violations before offering delivery.
7. Present three choices: create/update a pull request, preserve the branch, or discard it. Discard
   requires the user to type `discard` after seeing the exact branch, commits, and worktree affected.
8. For a PR, push only the feature branch and create a body containing `Closes #N` when a tracking
   issue exists. Do not enable auto-merge or merge without explicit user authority.
9. Remove only worktrees created for this branch and only after delivery or confirmed discard.

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
