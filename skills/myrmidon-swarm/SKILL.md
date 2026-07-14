---
name: myrmidon-swarm
description: Coordinate a complex task through dependency-aware specialist and executor subagents, with a sequential fallback for hosts without delegation.
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

These are capability labels, not model names. Use the host's available/default model. If subagents
are unavailable, execute the same dependency graph sequentially in the current agent.

## Workflow

1. Invoke `advise` with the task description and apply relevant prior knowledge.
2. Read `AGENTS.md`, build metadata, task runners, and the files closest to the request.
3. Decompose the work. For each item record scope, tier, files, dependencies, acceptance criteria,
   verification, and whether it writes state.
4. Present the plan when user approval is required by the host or task. Otherwise begin safe,
   in-scope work.
5. Group independent items into waves. Do not let concurrent agents edit the same files.
6. Give each subagent a bounded, self-contained prompt. Require it to report unexpected scope or
   conflicts rather than expanding its assignment.
7. Review every result before integration. Diagnose failures and revise the task; never repeat an
   unchanged failed prompt.
8. Run repository-defined tests and quality gates after integration.
9. Summarize changes, verification, unresolved risks, and any learning worth submitting through
   `learn`. `learn` must request approval before cross-repository writes.

## Safety

- Keep destructive, external, publishing, and merge actions behind the user's authority.
- Preserve existing user changes and worktrees.
- Never claim a subagent ran or a check passed without evidence.
- Prefer the smallest number of agents that creates real parallel value.

## Status format

Report each work item with its tier, dependency wave, status, result, and verification. The final
summary must distinguish completed work from recommendations and unresolved blockers.
