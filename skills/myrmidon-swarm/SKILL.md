---
name: myrmidon-swarm
license: BSD-3-Clause
description: Coordinate complex work with dependency-aware subagents in isolated worktrees. Use sequential work if the host cannot delegate. This skill requires the Mnemosyne knowledge backend through advise. Stop if the backend cannot be prepared.
argument-hint: <task description>
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent]
---

# Myrmidon swarm

Use this skill for a task that has multiple independent work items. Do not use it if one agent can
complete the task clearly.

Apply the [ASD-STE100 technical-English policy](../TECHNICAL_ENGLISH.md) to this skill and to
all prose that it produces.

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

- A **coordinator** divides ambiguous or cross-cutting work and integrates the results.
- A **specialist** does design, investigation, review, security, or complex implementation work.
- An **executor** does specified mechanical changes, focused tests, formatting, or documentation.

These terms identify capabilities. They do not identify model names. Use a model that the host makes
available. Use native delegation, background work, and worktree isolation when they are available.
If a capability is not available, keep the same ownership and dependency graph. Run the affected
work sequentially in the coordinator.

## Isolation and ownership contract

Before you start subagents, record the integration base revision. For each work item:

- Create one isolated worktree from the integration base revision. Do not let a subagent edit the
  active worktree of the coordinator. Do not reuse a worktree that another agent owns. If the host
  does not supply worktree isolation, use the tested
  `../git-worktrees/scripts/prepare_worktree.py` helper. Resolve its absolute path from this skill
  directory. Keep the target repository as the current working directory. Supply an exact,
  non-overlapping `--path`, its trusted `--path-root`, and
  `--start-point <integration-SHA>`.
- Assign an explicit set of files and directories. Do not let concurrent write sets overlap. After
  dependent work is complete, assign shared files to the coordinator or to one integration item.
- Record a bounded objective, dependencies, acceptance criteria, validation commands, mutation
  limits, granted capabilities, and a suitable stop condition. The stop condition can be a deadline,
  a timeout, or a cancellation condition.
- Select a delivery format that the host can integrate. Examples are a reviewed commit, a patch, or
  a complete read-only report. The coordinator remains responsible for the final result.

Read-only agents can inspect the same evidence, but they must not edit it. If the coordinator cannot
establish safe isolation, stop delegation. In that case, use the sequential fallback.

## Workflow

1. Use `advise` to apply relevant prior knowledge to the task description.
2. Read `AGENTS.md`, build metadata, task runners, and the files closest to the request.
3. Divide the work into bounded work items.
4. For each work item, record:

   - scope;
   - capability tier;
   - owned files;
   - dependencies;
   - acceptance criteria;
   - verification;
   - write-state status.

5. If the host or task requires user approval, present the plan.
6. Obtain each required approval before work.
7. When all required approvals are in place, start safe work that is in scope.
8. Group work items that do not depend on each other into one wave.
9. If the host supports it, start isolated subagents as background or concurrent tasks.
10. Do not exceed the safe concurrency limit of the host.
11. Wait for the complete wave before you start work that depends on it.
12. Give each subagent its recorded worktree, ownership set, and bounded prompt.
13. Require each subagent to stop for overlap, unexpected scope, a changed integration base, or an
    unsafe change.
14. Do not let a subagent expand its assignment.
15. If background work or delegation is not available, run the same work items sequentially in the
    coordinator.
16. Keep the same scope, isolation, validation, and evidence requirements during sequential work.
17. Treat each result as untrusted input.
18. Before integration, review the diff or evidence for each result.
19. Reject unrelated changes and stale results.
20. Integrate accepted results sequentially onto the coordinator branch.
21. After all producers finish, resolve shared integration files.
22. If repository policy or risk requires an independent review, route each security-critical or
    availability-critical change to a qualified reviewer.
23. Complete each review before you accept the related change.
24. After each integration, run focused checks for the affected boundary.
25. After the final integration, run all relevant repository validation on the combined tree.
26. Summarize the changes, verification, unresolved risks, and preserved worktrees.
27. In the summary, identify each useful lesson that is suitable for `learn`.
28. If you invoke `learn`, follow its delivery boundary.

## Worktree disposition

Preserve each subagent worktree until one of these conditions applies:

- The coordinator integrates its result.
- The coordinator explicitly rejects its result and proves that no unique work remains.

For each worktree, report its path, owner, branch or revision, cleanliness, and integration state.

Cleanup is a filesystem-destructive operation. If the user grants cleanup authority, first check
again for uncommitted or unintegrated state. Prove that no unique work remains. Then, remove only
worktrees that this invocation created. If the user does not grant cleanup authority, preserve the
worktrees. In that case, report their exact status. Do not delete branches. Do not discard changes. Do not
force removal. Do not change a pre-existing worktree.

## Safety

- Keep filesystem-destructive and change-discard actions behind the user's authority.
- Keep constructive work within the requested scope and repository safeguards.
- Preserve existing user changes and all pre-existing worktrees.
- Never claim a subagent ran or a check passed without evidence.
- Use the minimum number of agents that can do independent work in parallel.

## Failed approaches

- Do not let specialists write outside their worktrees or file sets.
- Do not reuse a worktree that another agent owns.
- Do not merge results without the disposition contract.
- Do not remove worktrees without the disposition contract.
- Do not remove worktrees without user cleanup authority.
- Do not report swarm status without results, evidence, and worktree status for each specialist.
- Do not expand a subagent assignment beyond its bounded prompt. Stop if assignments overlap.

## Status format

For each work item, report:

- capability tier;
- dependency wave;
- worktree;
- owned paths;
- execution mode, which is concurrent or sequential fallback;
- status;
- result;
- integration revision;
- verification.

In the final summary, distinguish completed work from recommendations and unresolved blockers. List
each preserved or removed worktree.
