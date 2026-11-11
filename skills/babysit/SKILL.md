---
name: babysit
license: BSD-3-Clause
description: Coordinate a set of long-lived agent sessions and automation loops to a completion boundary. Use this skill when the user asks you to watch, track, revive, babysit, or guide many agent sessions, when sessions or hephaestus-automation-loop runs do work that does not appear in commits or pull requests, or when supervision must continue until an external event such as a new product release. The coordinator keeps authority, instructs the owning agents, arms an event-driven monitor, answers agent questions, and escalates non-simple blockers to the user. The required session store and session-resume capabilities are host-specific; when the host does not have them, supervise loop processes by their operating-system evidence only and do each coordination step manually with the same contracts.
argument-hint: "<optional: session selector and completion boundary>"
allowed-tools: [Bash, Read]
---

# Babysit agent sessions and loops

Use this skill for the coordination of a set of agent sessions or automation loops. Examples of
triggers are requests to watch many sessions, to find why session work does not land in commits or
pull requests, or to supervise hephaestus-automation-loop runs until a release boundary.

The coordinator role keeps authority. Subordinate sessions and loops do the implementation work
inside their own scope. Use this skill to coordinate; it does not do the subordinate work itself.
Use `myrmidon-swarm` for bounded delegation of discrete work items. Use the review skills for
artifact reviews. This skill composes those skills; it does not replace them.

Apply the [ASD-STE100 technical-English policy](../TECHNICAL_ENGLISH.md) to this skill and to all
prose that it produces.

Use the [autonomous workflow policy](../../docs/policies/autonomous-workflows.md) for authority,
recovery, resources, validation, and delivery.

## Engineering principles

Use the [canonical engineering-principles catalog](../../docs/principles/README.md) for these
workflow rules:

- [P012 — Evidence Before Modification](../../docs/principles/README.md#p012): Inventory and
  classify each session and each loop before you send any instruction.
- [P019 — Explicit Contracts](../../docs/principles/README.md#p019): Give each subordinate agent a
  bounded instruction. Give the monitor an explicit event list and exit rule.
- [P033 — State-Safe Failure Semantics](../../docs/principles/README.md#p033): When a monitor or a
  managed lane ends, keep the tracker and the durable state necessary to continue or escalate.
- [P035 — Fail Secure / Fail Closed](../../docs/principles/README.md#p035): Prefer to withhold
  instructions for a session whose ownership, liveness, or scope is not established. Where the
  state cannot be established, report the gap.
- [P036 — Graceful Degradation](../../docs/principles/README.md#p036): If the session store, a log,
  or local guidance is missing or stale, report the limit and continue with the evidence that is
  available.
- [P039 — Bounded Waiting](../../docs/principles/README.md#p039): Give the monitor a bounded cycle
  and a maximum lifetime. A watcher has an end rule.
- [P046 — Resumability](../../docs/principles/README.md#p046): Record coordinator state in a
  durable tracker so an interrupted coordination session can resume.
- [P047 — Observability Is Part of Correctness](../../docs/principles/README.md#p047): Keep a
  heartbeat, run logs, and per-session evidence for each reported state.
- [P050 — Least Privilege](../../docs/principles/README.md#p050): Do reconnaissance read-only.
  Give subordinate agents only the scope, paths, and authority that their task needs.
- [P058 — Bounded Agent Authority](../../docs/principles/README.md#p058): Keep each instruction
  inside the scope that the user assigned. An instruction does not expand its own scope.

## Roles

- **Coordinator**: this agent. Manages the set. Does not implement subordinate work.
- **Subordinate session**: an existing agent session that owns a task, a lane, or a loop.
- **Loop process**: an operating-system process such as a `hephaestus-automation-loop` run that a
  subordinate session launched.
- **Completion boundary**: the recorded end condition of the supervision, for example a merge, a
  wave completion, or the next release of a product version.

## Procedure

### 1. Inventory and classify (read-only)

1. Resolve the agent session store. For OpenCode, resolve the store path with
   `opencode debug paths db` (it applies XDG redirects, the `OPENCODE_DB` override, and the
   release channel). When resolution is not available, use `~/.local/share/opencode/opencode.db`
   and record the fallback. Read the store with `sqlite3 -readonly` and `SELECT` statements.
   List the requested sessions from `session_v2` (identifier, title, directory, parent, idle
   outcome, update times). When the host has no session store or session-resume capability, skip
   store-based steps and classify from process, log, git, and forge evidence only.
2. Classify each session against live evidence: running processes (`ps`, `pgrep`), loop logs, git
   worktrees and branches, pull requests, issues, and release state. A session is one of `live`,
   `idle`, `failed`, or `parked`.
3. Use parallel read-only subagents for deep analysis when the set is large. Give each subagent an
   explicit contract per `myrmidon-swarm`: inputs, read-only limits, output fields, and a deadline.
   Read-only analysis needs no worktree.
4. Record each session's task, state, artifacts, the cause that its work has no commit or pull
   request, and the next action. Typical causes are dead loop lanes, uncommitted deltas in
   detached-HEAD worktrees, infrastructure preemption, planning-only deliverables, and work still
   in flight.

### 2. Confirm the operating policy with the user

Confirm with the user before you act on live infrastructure or on subordinate agents:

- whether the coordinator instructs the owning agents (default) or does the work itself;
- which lanes to revive, and the permission for each non-default host action in those lanes;
- the exact completion boundary of the supervision;
- which decisions stay with the user. Escalate a decision to the user when it changes a protected
  host or checkout state, or when it selects between product-level alternatives.

### 3. Protect uncommitted deltas

1. For each session or subagent whose work exists only as working-tree changes, instruct its agent
   to create a branch, make signed commits, and open a pull request. Use a draft pull request when
   the work is not complete.
2. This protection runs before long waits. A detached-HEAD worktree delta is one cleanup away from
  loss; a draft pull request is reviewable and safe.

### 4. Instruct subordinate sessions

1. Resume each targeted session by its identifier with a bounded instruction, for example with
   `opencode run -s <session-id> --auto "<instruction text>"`. The `--auto` grant approves each
   permission that is not explicitly denied, so bind it: prefer `--auto` when the user confirmed
   the instruction policy in step 2. Without that confirmation, prefer to run the resume without
   `--auto` so the session's own permission rules gate each action. Aim to give each instruction:
   - scoped to that session's ownership set, with explicit isolation guards against other live
     lanes (named directories, intake clones, or running loops);
   - explicit about the required artifacts and the delivery path of every pull request: the
     `pr-review` skill to an implementation GO, the required CI checks green, then automerge;
   - ended by the stop-and-report rule: if a step has no simple fix, the agent stops and states
     the blocker plainly in its final message. The agent does not guess.
2. Stagger launches. Log each run to a file for audit.
3. Prefer not to resume sessions whose liveness or ownership is not established (P035). Where
   the gap is temporary, wait for the inventory evidence and report it.

### 5. Arm the event-driven monitor

Run ONE background monitor process. The monitor exits on the FIRST actionable event and prints the
event and its immediate evidence. The coordinator then reacts and re-arms the monitor. An
event-driven monitor replaces repeated manual polls.

Monitor these event types as applicable:

- **loop-process exit**: detect by an exact `pgrep -f` pattern that matches the loop's own command
  line; on exit, print the last lines of the loop log;
- **session idle transition**: detect from the session store when an idle outcome appears after
  the instruction time and the session has no updates for an idle floor (about 10 minutes); print
  the outcome and the session's last message;
- **external completion boundary**: check on a slow cycle (for example hourly) for the boundary
  condition such as a new release tag; print the boundary evidence.

Monitor rules (P033, P035):

- Prefer to kill orchestration processes by recorded PID. Avoid `pkill -f` on a scripted path; a
  probe whose own command line contains the same pattern kills itself.
- Give the monitor a bounded cycle and a maximum lifetime, after which it exits and the
  coordinator re-arms it.
- Write a heartbeat to a log file. Prefer the log file over the monitor's primary output; that
  output is event evidence.

### 6. Manage until the boundary

1. Answer subordinate-agent questions from the recorded evidence and the shared tracker. Keep
   answers inside the question's scope.
2. When a monitor event arrives: harvest the evidence, update the tracker, apply the recorded next
   action for that session (harvest a finished lane, supply an answer, or re-instruct), and
   re-arm the monitor for the remaining targets.
3. Escalate to the user when a subordinate agent reports a blocker that has no simple fix, when
   different owned lanes collide on one resource, or when the completion boundary requires a user
   decision.
4. When the completion boundary is reached, aim to verify it with the available evidence before you
   report completion. Report the verification result, or report that the evidence is missing.

## Tracker

Keep one durable tracker file outside the managed repositories (for example in the approved
scratch area). For each managed item record: owner session, task, state, artifacts with links, the
gap, the next action, and the monitor of record. Update the tracker at each event. The goal tools
hold the coordinator's plan; the tracker file holds the working state.

## Failed approaches

- Resume or instruct a session after the inventory establishes its task, state, and ownership.
  A cold instruction duplicates or collides with in-flight work.
- Give each lane its isolated projects directory, and check liveness before a lane becomes active.
  Many sessions writing in one intake or checkout collide.
- Commit to a branch and open a draft pull request before you wait for tests or decisions. Large
  uncommitted changes in detached-HEAD worktrees are easy to lose.
- Arm the bounded monitor instead of busy-waiting on subprocesses with repeated sleeps and output
  reads; continue on its events.
- Kill recorded PIDs for cleanup. `pkill -f` on supervisor script paths can kill the wrong process.
- Record the first cause and escalate it instead of silently absorbing a subordinate failure with
  no simple fix.
- Describe monitor or session state as healthy when time-stamped heartbeat or log evidence
  supports it. Otherwise report the limit.

## Status format

For each coordination cycle, report: the tracked set counts by state; each monitor event since the
last report with its evidence; instructions sent and their run logs; user escalations with the
plain blocker; and the completion-boundary state with verification evidence.
