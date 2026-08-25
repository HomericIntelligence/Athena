---
name: systematic-debugging
license: BSD-3-Clause
description: Investigate root cause before fixing bugs or unexpected behavior. Requires the Mnemosyne knowledge backend through advise and fails closed when it cannot be prepared.
argument-hint: <description of the bug or failure>
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent]
---

# Systematic Debugging

## Overview

Random fixes waste time and create new bugs. Quick patches mask underlying issues.

Apply the [ASD-STE100 writing policy](../../docs/technical-english.md) to this skill and to all prose
that it produces.

## Working rules

Always find the root cause before attempting fixes. Symptom fixes are failure.

**Violating the letter of this process is violating the spirit of debugging.**

## Engineering principles

Use Athena's [canonical engineering-principles catalog](../../docs/principles/README.md) as the
definition source. Apply these principles to this workflow:

- [P012 — Evidence Before Modification](../../docs/principles/README.md#p012): inspect symptoms,
  changes, contracts, and repository guidance before choosing a repair.
- [P015 — Architecture Conformance](../../docs/principles/README.md#p015): compare the failure path
  with established boundaries before changing the architecture.
- [P022 — Test Behavior, Not Implementation](../../docs/principles/README.md#p022): reproduce and
  protect the observable contract rather than a private arrangement.
- [P029 — Generalize Error Policy; Preserve Specific Cause](../../docs/principles/README.md#p029):
  retain the original cause while applying stable boundary-level error behavior.
- [P031 — Propagate Rather Than Swallow](../../docs/principles/README.md#p031): preserve failures when
  the current layer cannot recover completely.
- [P047 — Observability Is Part of Correctness](../../docs/principles/README.md#p047): gather the
  minimum correlated, structured, non-sensitive evidence needed to locate the fault.
- [P065 — Verify Before Claiming Completion](../../docs/principles/README.md#p065): rerun the original
  reproduction and applicable repository checks before reporting resolution.
- [P072 — Technical Evidence Over Preference](../../docs/principles/README.md#p072): accept or reject
  hypotheses using observed evidence rather than intuition.

## Before Starting

Run `advise` with the error description. Failure to prepare the required knowledge backend is a
blocking error, not permission to skip prior-knowledge search.

## The Iron Law

```text
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

If you haven't completed Phase 1, you cannot propose fixes.

## When to Use

Use for ANY technical issue:

- Test failures
- Bugs in production
- Unexpected behavior
- Performance problems
- Build failures
- Integration issues

**Use this ESPECIALLY when:**

- Under time pressure (emergencies make guessing tempting)
- "Just one quick fix" seems obvious
- You've already tried multiple fixes
- Previous fix didn't work
- You don't fully understand the issue

## The Four Phases

You MUST complete each phase before proceeding to the next.

### Phase 1: Root Cause Investigation

**BEFORE attempting ANY fix:**

1. **Read error messages carefully:** capture the complete failure output.
   - Don't skip past errors or warnings
   - They often contain the exact solution
   - Read stack traces completely
   - Note line numbers, file paths, error codes

2. **Reproduce consistently:** record the exact conditions and steps.
   - Can you trigger it reliably?
   - What are the exact steps?
   - Does it happen every time?
   - If not reproducible → gather more data, don't guess

3. **Check recent changes:** compare the failing state with recent repository history.
   - What changed that could cause this?
   - `git diff`, recent commits
   - New dependencies, config changes
   - Environmental differences

4. **Gather evidence in multi-component systems:** isolate the failing boundary.

   **WHEN system has multiple components:**

   **BEFORE proposing fixes, add only the non-sensitive diagnostic instrumentation required by
   [P047 — Observability Is Part of Correctness](../../docs/principles/README.md#p047):**

   ```text
   For EACH component boundary:
     - Log what data enters component
     - Log what data exits component
     - Verify environment/config propagation
     - Check state at each layer

   Run once to gather evidence showing WHERE it breaks
   THEN analyze evidence to identify failing component
   THEN investigate that specific component
   ```

5. **Trace data flow:** follow the bad value back to its source.

   When error is deep in call stack:
   - Where does the bad value originate?
   - What called this with the bad value?
   - Keep tracing up until you find the source
   - Fix at source, not at symptom

### Phase 2: Pattern Analysis

**Find the pattern before fixing:**

1. Find working examples of similar code in the same codebase
2. Read reference implementations completely — don't skim
3. List every difference between working and broken code
4. Identify all dependencies, config, environment assumptions

### Phase 3: Hypothesis and Testing

**Scientific method:**

1. **Form single hypothesis**: "I think X is the root cause because Y"
2. **Test minimally**: Make the SMALLEST possible change to test the hypothesis
3. **One variable at a time**: Don't fix multiple things at once
4. **Verify before continuing**: If it worked → Phase 4. Didn't work → new hypothesis
5. **When stuck**: Say "I don't understand X" — don't pretend to know

### Phase 4: Implementation

**Fix the root cause, not the symptom:**

1. **Create a regression test** using the `test-driven-development` skill. Follow
   [P026 — Regression Before Repair](../../docs/principles/README.md#p026), assert observable behavior
   under [P022](../../docs/principles/README.md#p022), and cover the relevant failure path under
   [P028](../../docs/principles/README.md#p028).
2. **Implement single fix** addressing the root cause
3. **Verify the fix** under [P065](../../docs/principles/README.md#p065): rerun the reproduction and
   relevant suite, preserve determinism and isolation under
   [P027](../../docs/principles/README.md#p027), and do not weaken tests or bypass validation under
   [P067](../../docs/principles/README.md#p067) and
   [P068](../../docs/principles/README.md#p068).

   When the repair changes failure behavior, choose the responsible boundary deliberately:
   generalize policy while preserving cause under [P029](../../docs/principles/README.md#p029), handle
   at the [nearest responsible boundary](../../docs/principles/README.md#p030),
   [propagate unrecovered failures](../../docs/principles/README.md#p031), and
   [handle once without losing causality](../../docs/principles/README.md#p032). Preserve valid state
   under [P033](../../docs/principles/README.md#p033), then choose
   [fail-fast](../../docs/principles/README.md#p034),
   [fail-closed](../../docs/principles/README.md#p035), or
   [graceful degradation](../../docs/principles/README.md#p036) according to the failed capability's
   correctness and security criticality.

4. **If fix doesn't work:**
   - STOP
   - Count: How many fixes have you tried?
   - If < 3: Return to Phase 1 with new information
   - **If ≥ 3:** STOP and trigger an architecture review

5. **If 3+ fixes failed — Review Architecture:**

   Repeated failed fixes can indicate a mistaken model, a missed dependency, or an architectural
   problem. They trigger reassessment; they do not prove the architecture is wrong. Review:
   - Each fix reveals new shared state/coupling/problem elsewhere
   - Fixes require massive refactoring to implement
   - Each fix creates new symptoms elsewhere

   STOP and discuss the accumulated evidence with the user before another repair attempt. Revisit
   Phase 1 when the evidence points to a bad hypothesis; propose an architectural change only when
   the evidence supports it.

## Red Flags — STOP and Follow Process

- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- "Add multiple changes, run tests"
- "It's probably X, let me fix that"
- "I don't fully understand but this might work"
- "One more fix attempt" (when already tried 2+)
- Each fix reveals a new problem in a different place

**ALL of these mean: STOP. Return to Phase 1.**

## Failed approaches

| Excuse | Reality |
| -------- | --------- |
| "Issue is simple, don't need process" | Simple issues have root causes too. |
| "Emergency, no time for process" | Systematic debugging is FASTER than guess-and-check. |
| "Just try this first, then investigate" | First fix sets the pattern. Do it right from the start. |
| "Multiple fixes at once saves time" | Can't isolate what worked. Causes new bugs. |
| "One more fix attempt" (after 2+ failures) | Three failed fixes trigger architecture review; they do not justify another guess. |

## Repository command discovery

Before running a check, discover the target repository's commands from `AGENTS.md`, task runners,
manifests, lockfiles, and CI. Prefer the command used by required CI. If sources conflict or no safe
command is discoverable, ask the user rather than substituting Athena's own tooling.

Keep the target repository as the current working directory. Resolve
`scripts/repository_evidence.py` against this installed skill directory and invoke that absolute
helper path with `PATTERN --source-root SOURCE_ROOT` to collect the latest ten commits, a diff
bounded to that revision window, and matching source locations as JSON. Run the
discovered repository-focused test and type-check commands directly through the host execution
tool, retaining their complete output as evidence.

## After Resolution

Verify with fresh runnable evidence per the
[evidence-integrity policy](../../docs/policies/evidence-integrity.md) before claiming the bug is
fixed; rerun the failing reproduction and the repository-defined checks.

Offer to invoke `learn` when the session produced durable debugging knowledge. An indirect Learn
invocation remains read-only and does not expand the requested scope; use Learn's delivery boundary
when durable learning is requested. Useful lessons include:

- Root cause category and symptoms
- What diagnostic steps revealed it
- The fix pattern
- Any architectural issues uncovered

This prevents the same debugging session from being repeated by another agent.

---

_Adapted from [obra/superpowers](https://github.com/obra/superpowers) under the [MIT License](https://github.com/obra/superpowers/blob/main/LICENSE). Copyright (c) 2025 Jesse Vincent._
