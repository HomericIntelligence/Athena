---
name: test-driven-development
license: BSD-3-Clause
description: Use this skill before you write implementation code for a feature or bug fix. Follow the RED-GREEN-REFACTOR cycle. Do not write production code until a verified test fails for the expected missing behavior. If the test has an error, correct the test before GREEN.
argument-hint: <feature or bugfix description>
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob]
---

# Test-driven development (TDD)

A focused test that fails proves that it can detect the missing product behavior. A passing test
proves that the smallest implementation satisfies the test.

Apply the [ASD-STE100 technical-English policy](../TECHNICAL_ENGLISH.md) to this skill and to
all prose that it produces.

Use Athena's shared [behavior-first testing guidance](../../docs/review/behavior-first-testing.md)
for test criteria, determinism, and false-pass checks. Test observable product behavior and core
contracts. Do not test wording, documentation layout, or a private implementation arrangement.

## Engineering principles

Use Athena's [canonical engineering-principles catalog](../../docs/principles/README.md) for the
principle definitions. Use these principles in this workflow:

- [P022 — Test Behavior, Not Implementation](../../docs/principles/README.md#p022): Write tests for
  observable contracts. Do not write tests for a private implementation.
- [P023 — Parameterized / Table-Driven Testing](../../docs/principles/README.md#p023): If one rule is
  applicable to two or more test cases, use named data in a parameterized or table-driven test.
- [P024 — Boundary-Value Testing](../../docs/principles/README.md#p024): If the behavior has
  boundaries, include values near its limits and state changes.
- [P025 — Property-Based Testing for Invariants](../../docs/principles/README.md#p025): If a small
  example set is not sufficient for an invariant, use generated input families.
- [P026 — Regression Before Repair](../../docs/principles/README.md#p026): If it is possible, before
  you repair the defect, add one test that fails only because of the defect.
- [P027 — Deterministic and Hermetic Tests](../../docs/principles/README.md#p027): Set environment
  inputs to specified values. Control external boundaries. Make sure that each test gives the same
  result each time.
- [P028 — Test Failure Paths, Not Just Success Paths](../../docs/principles/README.md#p028): If the
  contract includes failure paths, include invalid input, dependency failure, cancellation, and
  cleanup.
- [P091 — Test-Driven Development](../../docs/principles/README.md#p091): For a behavior change, first
  add a test that shows the missing behavior (`RED`). Then, make the minimum code change that makes
  the test pass (`GREEN`). After `GREEN`, make the structure better without a behavior change
  (`REFACTOR`).

## Working rules

Use TDD for features, bug fixes, and behavior changes. For a pure refactor that preserves behavior,
first establish a verified green characterization baseline. Then, start at REFACTOR. Do not create
an artificial RED result.

If the work introduces or changes observable behavior, start with RED. Before you exempt a
throwaway prototype, generated code, configuration-only work, or documentation-only change, ask the
human partner. In a swarm, the test specialist must complete the applicable RED or green
characterization baseline before implementation starts.

```text
START A BEHAVIOR CHANGE WITH A FOCUSED FAILING TEST
START A PURE REFACTOR FROM A VERIFIED GREEN BASELINE
```

If you wrote an in-scope implementation that changes behavior before RED, remove only the work that
you added. Then, start with RED. If a pure refactor started without a verified baseline, stop.
Establish a verified baseline before you continue. Preserve existing work and work that the user
authored. If the source or scope of the work is not clear, ask for direction.

## RED-GREEN-REFACTOR

For a refactor that preserves behavior, verify the existing characterization suite. Then, start at
step 5. If the intended work changes the observable contract, return to RED.

1. **RED:** Write one minimum, clearly named test under
   [P022](../../docs/principles/README.md#p022).

   - The test must cover one observable behavior, data contract, security property, or executable
     artifact result.
   - Use real code unless a real external boundary requires a controlled substitute.
   - If the behavior requires them, apply [P023](../../docs/principles/README.md#p023),
     [P024](../../docs/principles/README.md#p024),
     [P025](../../docs/principles/README.md#p025), and
     [P028](../../docs/principles/README.md#p028).

2. **Verify RED:** Verify the RED result with the focused test command for the repository.

   - Before you run the command, find it in the repository.
   - Run the focused test command.
   - The test must fail for the expected missing behavior.
   - The test must not stop because of a test error.
   - For a filtered command, use the output to prove that the command selected an applicable test.
   - Connect each C++/CMake test source to a real build target and test target.
   - If the test passes, it covers existing behavior.
   - If the test has an error, correct the test setup. Then, run the test again.
   - Under [P027](../../docs/principles/README.md#p027), keep the test deterministic and isolated.

3. **GREEN:** Write the simplest behaviorally complete code that passes the behavior test.

   - Follow [P001 — KISS — Keep It Simple, Stupid](../../docs/principles/README.md#p001).
   - Prefer [P090 — Prefer Negative Code](../../docs/principles/README.md#p090) only if the candidate
     solutions are equally correct.
   - Do not add speculative features, unrelated refactors, or implementation beyond the need that
     the test shows.

4. **Verify GREEN:** Run the applicable test suite that you found in the repository.

   - The new and existing tests must pass without errors or warnings.
   - Correct the code. Do not weaken a test.

5. **REFACTOR:** After GREEN, improve the structure without new behavior.

   - Remove actual knowledge duplication under
     [P003 — DRY — Don't Repeat Yourself](../../docs/principles/README.md#p003).
   - Do not violate [P013 — AHA — Avoid Hasty Abstractions](../../docs/principles/README.md#p013).
   - Protect [P070 — Code Health Must Not Regress](../../docs/principles/README.md#p070),
     [P084 — Prefer Local Reasoning](../../docs/principles/README.md#p084), and
     [P086 — Readability Counts](../../docs/principles/README.md#p086).
   - Prefer deletion under [P090](../../docs/principles/README.md#p090) only if behavior and clarity
     do not change.
   - Keep the tests green.
   - Start the next RED cycle.

For a documentation-only change, use existing Markdown, link, and executable-example validation.
Do not create production code. Do not create a text-assertion harness to produce an artificial RED
phase.

## Evidence before completion

Find commands in `AGENTS.md`, task runners, manifests, lockfiles, and required continuous
integration (CI) configuration. Prefer repository-native entry points. When applicable, record the
focused-test, applicable-suite, coverage, type-check, and lint commands. If the sources conflict or
you cannot find a safe command, ask the user. Do not use a command from another repository.

Before completion, confirm these conditions:

- Each changed observable behavior and bug regression has proportionate test coverage.
- The tests control time, services, randomness, state, and mocks when the product requires this
  control.
- Focused test selection is not empty.
- Fresh applicable tests, type checks, and lint checks pass.

Before you claim success, follow the
[evidence-integrity policy](../../docs/policies/evidence-integrity.md). For a durable testing lesson,
use `learn`. The scope and delivery rules of `learn` determine if it publishes a pull request.

## Failed approaches

- Do not write production code before RED.
- Do not keep in-scope implementation that you wrote before the test.
- Do not accept a test error as RED. Correct the setup. Then, run the test until it fails for the
  expected missing behavior.
- Do not weaken a test to reach GREEN. Correct the code.
- Do not add speculative features or unrelated refactors beyond the need that the test shows.

---

_Adapted from [obra/superpowers](https://github.com/obra/superpowers) under the [MIT License](https://github.com/obra/superpowers/blob/main/LICENSE). Copyright (c) 2025 Jesse Vincent._
