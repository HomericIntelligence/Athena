---
name: systematic-debugging
license: BSD-3-Clause
description: Investigate root cause before you repair a bug or unexpected behavior. This skill requires the Mnemosyne knowledge backend through advise. Stop if the backend cannot be prepared.
argument-hint: <description of the bug or failure>
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent]
---

# Systematic debugging

## Overview

A repair without evidence wastes time and can create a new bug. A repair of only the symptom can
hide the root cause.

Apply the [ASD-STE100 technical-English policy](../TECHNICAL_ENGLISH.md) to this skill and to
all prose that it produces.

## Working rules

Find the root cause before you attempt a repair. Do not repair only the symptom. Follow each
required step in this process.

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

## Before you start

Run `advise` with the error description. If you cannot prepare the required knowledge backend,
stop. Do not skip the prior-knowledge search.

## Required sequence

Complete phase 1 before you propose a repair.

## When to use

Use this skill for all technical issues, including:

- A test fails.
- A bug occurs in production.
- The product has unexpected behavior.
- The product has a performance problem.
- A build fails.
- An integration fails.

Use this skill especially in these conditions:

- You are under time pressure.
- A repair appears obvious before an investigation.
- You already attempted multiple repairs.
- A previous repair did not work.
- You do not fully understand the issue.

## Workflow

Complete each phase before you continue to the next phase.

### Phase 1: Root cause investigation

Before you attempt a repair, complete these steps:

1. Record these items from the complete failure output:

   - each error and warning;
   - the complete stack trace;
   - line numbers;
   - file paths;
   - error codes.

2. Do not skip an error or warning. An error message can identify the cause.
3. Reproduce the failure consistently.
4. Record the exact conditions, steps, and frequency of the failure.
5. If you cannot reproduce the failure, collect more data.
6. Do not guess the cause.
7. Compare the failed state with recent repository history.
8. Inspect these possible sources of the failure:

   - `git diff`;
   - recent commits;
   - new dependencies;
   - configuration changes;
   - environment differences.

9. If the system has multiple components, isolate the failed boundary.
10. Before you propose a repair, add only the minimum non-sensitive diagnostic instrumentation that
   [P047 — Observability Is Part of Correctness](../../docs/principles/README.md#p047) requires.
11. At each component boundary:

    - log the input data;
    - log the output data;
    - verify the transfer of environment and configuration data;
    - examine the state at each layer.

12. Run the instrumented reproduction one time to collect evidence.
13. Use the evidence to identify the failed component.
14. Investigate that component.
15. If an incorrect value is deep in the call stack, trace the value back to its source.
16. Identify where the incorrect value starts and which caller supplied it.
17. Continue the trace until you find the source.
18. Repair the source.
19. Do not repair only the symptom.

### Phase 2: Pattern analysis

Identify the pattern before you make a repair:

1. Find correct examples of similar code in the same repository.
2. Read each applicable reference implementation completely.
3. Do not read only a sample.
4. List each difference between the correct code and the code that fails.
5. Identify all dependencies and all configuration and environment assumptions.

### Phase 3: Hypothesis and test

Use this method to test a hypothesis:

1. State one hypothesis: `The root cause is X because Y.`
2. Make the minimum possible change to test the hypothesis.
3. Change only one variable in each test.
4. If the result supports the hypothesis, continue to phase 4.
5. If the result does not support the hypothesis, state a new hypothesis.
6. If you do not understand X, state `I do not understand X.`
7. Do not claim that you understand X.

### Phase 4: Implementation

Repair the root cause.

Do not repair only the symptom.

1. Use the `test-driven-development` skill to create a regression test.
2. Under [P026 — Regression Before Repair](../../docs/principles/README.md#p026), create the test
   before the repair.
3. Under [P022](../../docs/principles/README.md#p022), make the test assert observable behavior.
4. Under [P028](../../docs/principles/README.md#p028), make the test cover the applicable failure
   path.
5. Implement one repair that corrects the root cause.
6. Under [P065](../../docs/principles/README.md#p065), run this validation:

   - Rerun the reproduction.
   - Run the applicable test suite.
7. Under [P027](../../docs/principles/README.md#p027), keep the test deterministic and isolated.
8. Under [P067](../../docs/principles/README.md#p067) and
   [P068](../../docs/principles/README.md#p068), do not weaken tests or bypass validation.

If the repair changes failure behavior, complete these steps:

1. Under [P029](../../docs/principles/README.md#p029), generalize the policy and preserve the cause.
2. Handle the failure at the
   [nearest responsible boundary](../../docs/principles/README.md#p030).
3. [Propagate unrecovered failures](../../docs/principles/README.md#p031).
4. [Handle the failure once without losing causality](../../docs/principles/README.md#p032).
5. Under [P033](../../docs/principles/README.md#p033), preserve valid state.
6. Select [fail-fast](../../docs/principles/README.md#p034),
   [fail-closed](../../docs/principles/README.md#p035), or
   [graceful degradation](../../docs/principles/README.md#p036).
7. Base this selection on the correctness and security importance of the failed capability.

If the repair does not correct the issue, complete these steps:

1. Stop the current repair attempt.
2. Count the failed repair attempts.
3. If fewer than three repairs failed, return to phase 1 with the new information.
4. After three failed repairs, start an architecture review.

### After three failed repairs

Repeated failed repairs can show an incorrect model, a missing dependency, or an architecture
problem. They require a new assessment. They do not prove that the architecture is incorrect.

Review the evidence for these conditions:

- Each repair reveals new shared state, coupling, or a problem in another component.
- A repair requires a large refactor.
- Each repair creates a new symptom in another component.

Before another repair attempt, discuss the collected evidence with the user. If the evidence shows
an incorrect hypothesis, return to phase 1. Propose an architecture change only if the evidence
supports it.

## Stop conditions

Stop and return to phase 1 if one of these conditions applies:

- You plan a temporary repair before an investigation.
- You plan to change X only to see the result.
- You plan to make multiple changes before a test.
- You select a probable cause without evidence.
- You do not understand the issue but plan a repair.
- You plan another repair after two failed repairs.
- Each repair reveals a new problem in a different component.

## Failed approaches

- Do not omit this process for a simple issue. A simple issue also has a root cause.
- Do not omit this process during an emergency. Systematic debugging is faster than repairs without
  evidence.
- Do not attempt a repair before the investigation. The first repair can affect the next evidence.
- Do not make multiple repairs at the same time. You cannot identify which repair changed the
  result, and the repairs can cause new bugs.
- After three failed repairs, do not make another repair from a guess. Start an architecture review.

## Repository command discovery

Before you run a check, find the target repository commands in `AGENTS.md`, task runners, manifests,
lockfiles, and continuous integration (CI) configuration. Prefer the command that required CI uses.
If the sources conflict or you cannot find a safe command, ask the user. Do not use Athena commands
as a substitute.

Keep the target repository as the current working directory. Resolve
`scripts/repository_evidence.py` against this installed skill directory. Invoke that absolute helper
path with `PATTERN --source-root SOURCE_ROOT`. The helper collects the latest ten commits, a diff
bounded to that revision window, and matching source locations as JSON. Run the discovered
repository-focused test and type-check commands through the host execution tool. Keep their complete
output as evidence.

## After resolution

Before you state that the bug is fixed, verify the result with fresh runnable evidence under the
[evidence-integrity policy](../../docs/policies/evidence-integrity.md). Rerun the original
reproduction and the repository-defined checks.

If the session produces durable debugging knowledge, offer to invoke `learn`. An indirect `learn`
invocation is read-only and does not increase the requested scope. If the user requests durable
learning, use the delivery boundary of `learn`. Useful lessons include these items:

- the root-cause category and symptoms;
- the diagnostic steps that revealed the cause;
- the repair pattern; and
- each architecture issue that the investigation found.

This record prevents another agent from repeating the same debugging session.

---

_Adapted from [obra/superpowers](https://github.com/obra/superpowers) under the [MIT License](https://github.com/obra/superpowers/blob/main/LICENSE). Copyright (c) 2025 Jesse Vincent._
