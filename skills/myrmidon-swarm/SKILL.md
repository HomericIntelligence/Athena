---
name: myrmidon-swarm
description: Coordinate complex work through dependency-aware subagents in isolated worktrees, with a sequential fallback. Requires the Mnemosyne knowledge backend through advise and fails closed when it cannot be prepared.
argument-hint: <task description>
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent]
---

# Myrmidon swarm

Use this for a task with several independently useful workstreams. Do not use it for work that one
agent can complete more clearly.

## Capability tiers

- **Coordinator:** decomposes ambiguous or cross-cutting work and integrates results.
- **Specialist:** handles design, investigation, review, security, or non-trivial implementation.
- **Executor:** handles well-specified mechanical changes, focused tests, formatting, or docs.

These are capability labels, not model names. Use the host's available/default model and native
delegation, background execution, and worktree isolation capabilities. If any capability is absent,
preserve the same ownership and dependency graph while executing the affected items sequentially in
the coordinator.

## Isolation and ownership contract

Before dispatch, record the integration base revision and assign every work item:

- One isolated worktree based on that revision. Never let a subagent edit the coordinator's active
  worktree or reuse a worktree owned by another agent. Use the tested
  `../git-worktrees/scripts/prepare_worktree.py` helper from Athena's `git-worktrees` skill with an
  exact non-overlapping `--path`, its trusted `--path-root`, and `--start-point <integration-SHA>`
  when the host does not provide native worktree isolation.
- An explicit file and directory ownership set. Concurrent write sets must not overlap. Shared files
  belong to the coordinator or to one designated integration item after dependent work completes.
- A bounded objective, dependencies, acceptance criteria, validation commands, and mutation limits.
- A delivery format the host can integrate, such as a reviewed commit, patch, or complete read-only
  report. The coordinator remains responsible for the final result.

Read-only agents may inspect overlapping evidence, but they must not edit it. If safe isolation
cannot be established, stop delegation and use the sequential fallback.

## Workflow

1. Invoke `advise` with the task description and apply relevant prior knowledge.
2. Read `AGENTS.md`, build metadata, task runners, and the files closest to the request.
3. Decompose the work. For each item record scope, tier, files, dependencies, acceptance criteria,
   verification, and whether it writes state.
4. Present the plan when user approval is required by the host or task. Otherwise begin safe,
   in-scope work.
5. Group dependency-independent items into a wave. Start their isolated subagents as background or
   concurrent tasks when the host supports it, up to the host's safe concurrency limit. Wait for the
   complete wave before dispatching work that depends on it.
6. Give each subagent its recorded worktree, ownership set, and bounded prompt. Require it to stop
   on overlap, unexpected scope, a changed integration base, or unsafe mutation rather than
   expanding its assignment.
7. If background execution or delegation is unavailable, run the same items sequentially in the
   coordinator. Do not weaken scope, isolation, validation, or evidence requirements.
8. Review each result and its diff or evidence before integration. Reject unrelated edits and stale
   results. Integrate accepted results sequentially onto the coordinator branch, resolving shared
   integration files only after their producers finish.
9. After every integration, run focused checks for the affected boundary. After the final
   integration, run the repository-defined complete relevant validation from the combined tree.
10. Summarize changes, verification, unresolved risks, preserved worktrees, and any learning worth
    submitting through `learn`. `learn` must follow its own external-write authority checkpoint.

## Worktree disposition

Preserve every subagent worktree until its result is integrated or explicitly rejected and the
coordinator has proved that no unique work remains. Report the path, owner, branch or revision,
cleanliness, and integration state.

Cleanup is a separate mutation. Remove only worktrees created for this invocation, only after the
user grants cleanup authority, and only after rechecking for uncommitted or unintegrated state.
Without that authority, preserve the worktrees and return exact disposition information. Never
delete branches, discard changes, force removal, or touch a pre-existing worktree.

## Safety

- Keep destructive, external, publishing, and merge actions behind the user's authority.
- Preserve existing user changes and all pre-existing worktrees.
- Never claim a subagent ran or a check passed without evidence.
- Prefer the smallest number of agents that creates real parallel value.

## Status format

Report each work item with its tier, dependency wave, worktree, owned paths, execution mode
(concurrent or sequential fallback), status, result, integration revision, and verification. The
final summary must distinguish completed work from recommendations and unresolved blockers and
must list every preserved or removed worktree.
