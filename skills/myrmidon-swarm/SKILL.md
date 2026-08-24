---
name: myrmidon-swarm
license: BSD-3-Clause
description: Coordinate complex work through dependency-aware subagents in isolated worktrees, with a sequential fallback. Requires the Mnemosyne knowledge backend through advise and fails closed when it cannot be prepared.
argument-hint: <task description>
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent]
---

# Myrmidon swarm

Use this for a task with several independently useful workstreams. Do not use it for work that one
agent can complete more clearly.

## Engineering principles

Use the [canonical engineering-principles catalog](../../docs/principles/README.md) through these
workflow-specific rules:

- [P019 — Explicit Contracts](../../docs/principles/README.md#p019): give every work item explicit
  inputs, outputs, invariants, dependencies, acceptance criteria, and failure behavior.
- [P033 — State-Safe Failure Semantics](../../docs/principles/README.md#p033): stop integration on
  failed or stale work and preserve a valid coordinator tree plus recoverable delegated state.
- [P039 — Bounded Waiting](../../docs/principles/README.md#p039): assign appropriate deadlines,
  timeout behavior, or cancellation conditions to delegated and background work.
- [P050 — Least Privilege](../../docs/principles/README.md#p050): grant each work item only the tools,
  paths, credentials, and lifetime required for its bounded objective.
- [P058 — Bounded Agent Authority](../../docs/principles/README.md#p058): keep every subagent within
  the parent's task scope, mutation limits, destinations, and resource budget.
- [P060 — Constrain Sub-Agents](../../docs/principles/README.md#p060): isolate writers, prevent
  overlapping ownership, and validate delegated output as untrusted input before integration.
- [P069 — Independent Review for High-Risk Changes](../../docs/principles/README.md#p069): route
  security- or availability-critical results through qualified independent review proportional to
  repository policy and risk.
- [P079 — Explicit Ownership and Lifetimes](../../docs/principles/README.md#p079): record who owns
  each worktree, path, task, integration decision, and cleanup transition.

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
  `../git-worktrees/scripts/prepare_worktree.py` helper by its absolute path resolved from this skill
  directory while retaining the target repository as the current working directory. Supply an exact
  non-overlapping `--path`, its trusted `--path-root`, and `--start-point <integration-SHA>` when the
  host does not provide native worktree isolation.
- An explicit file and directory ownership set. Concurrent write sets must not overlap. Shared files
  belong to the coordinator or to one designated integration item after dependent work completes.
- A bounded objective, dependencies, acceptance criteria, validation commands, mutation limits,
  granted capabilities, and an appropriate deadline, timeout, or cancellation condition.
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
8. Treat each result as untrusted input. Review its diff or evidence before integration, reject
   unrelated edits and stale results, and integrate accepted results sequentially onto the
   coordinator branch. Resolve shared integration files only after their producers finish.
9. Route security- or availability-critical changes through a qualified independent reviewer before
   accepting them when the governing repository policy or risk requires it.
10. After every integration, run focused checks for the affected boundary. After the final
   integration, run the repository-defined complete relevant validation from the combined tree.
11. Summarize changes, verification, unresolved risks, preserved worktrees, and any learning worth
    submitting through `learn`. `learn` must follow its own delivery boundary.

## Worktree disposition

Preserve every subagent worktree until its result is integrated or explicitly rejected and the
coordinator has proved that no unique work remains. Report the path, owner, branch or revision,
cleanliness, and integration state.

Cleanup is a filesystem-destructive operation. Remove only worktrees created for this invocation,
only after the user grants cleanup authority, and only after rechecking for uncommitted or
unintegrated state. Without that authority, preserve the worktrees and return exact disposition
information. Never delete branches, discard changes, force removal, or touch a pre-existing
worktree.

## Safety

- Keep filesystem-destructive and change-discard actions behind the user's authority; keep all
  constructive work within the requested scope and its repository safeguards.
- Preserve existing user changes and all pre-existing worktrees.
- Never claim a subagent ran or a check passed without evidence.
- Prefer the smallest number of agents that creates real parallel value.

## Failed approaches

- Letting specialists write outside their owned worktrees or file sets, or reusing another agent's
  worktree.
- Merging, removing, or disposing worktrees without the disposition contract and the user's cleanup
  authority.
- Reporting swarm status without per-specialist outcomes, evidence, and worktree disposition.
- Expanding a subagent's assignment past its bounded prompt instead of stopping on overlap.

## Status format

Report each work item with its tier, dependency wave, worktree, owned paths, execution mode
(concurrent or sequential fallback), status, result, integration revision, and verification. The
final summary must distinguish completed work from recommendations and unresolved blockers and
must list every preserved or removed worktree.
