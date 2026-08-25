---
name: test-driven-development
license: BSD-3-Clause
description: Use when implementing any feature or bugfix, before writing implementation code — enforces RED-GREEN-REFACTOR cycle. Refuses to write production code without a verified failing test; a test that errors instead of failing for the expected missing behavior blocks GREEN until fixed.
argument-hint: <feature or bugfix description>
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob]
---

# Test-Driven Development (TDD)

Why: seeing a focused test fail proves it can detect the missing product
behavior; seeing it pass proves the smallest implementation satisfies it.

Apply the [ASD-STE100 writing policy](../../docs/technical-english.md) to this skill and to all prose
that it produces.

Use Athena's shared [behavior-first testing guidance](../../docs/review/behavior-first-testing.md)
for good-test/bad-test criteria, determinism, and false-pass checks. Test
observable product behavior and core contracts, not wording, documentation
layout, or a private implementation arrangement.

## Engineering principles

Use Athena's [canonical engineering-principles catalog](../../docs/principles/README.md) as the
definition source. Apply these principles to this workflow:

- [P022 — Test Behavior, Not Implementation](../../docs/principles/README.md#p022): drive and protect
  observable contracts rather than private implementation arrangements.
- [P023 — Parameterized / Table-Driven Testing](../../docs/principles/README.md#p023): express repeated
  cases through named data when one behavioral rule covers them.
- [P024 — Boundary-Value Testing](../../docs/principles/README.md#p024): include values around limits
  and transitions when the behavior has boundaries.
- [P025 — Property-Based Testing for Invariants](../../docs/principles/README.md#p025): use generated
  input families when an invariant is stronger than a small example set.
- [P026 — Regression Before Repair](../../docs/principles/README.md#p026): reproduce a defect with a
  focused failing test before repairing it when practical.
- [P027 — Deterministic and Hermetic Tests](../../docs/principles/README.md#p027): control ambient
  inputs and external boundaries so RED and GREEN are repeatable.
- [P028 — Test Failure Paths, Not Just Success Paths](../../docs/principles/README.md#p028): cover
  invalid input, dependency failure, cancellation, and cleanup where the contract requires them.
- [P091 — Test-Driven Development](../../docs/principles/README.md#p091): for behavior changes, prove
  missing behavior with RED, implement the smallest GREEN, then improve structure while green.

## Working rules

Use TDD for features, bug fixes, and behavior changes. For a pure behavior-preserving refactor,
first establish a verified green characterization baseline and enter at REFACTOR; do not manufacture
a RED result. If the work introduces or changes observable behavior, begin with RED. Ask the human
partner before exempting a throwaway prototype, generated code, configuration-only work, or
documentation-only wording/layout change. In a swarm, the test specialist completes the applicable
RED or green characterization baseline before implementation begins.

```text
BEHAVIOR CHANGES START WITH A FOCUSED FAILING TEST
PURE REFACTORING STARTS FROM A VERIFIED GREEN BASELINE
```

If you wrote in-scope behavior-changing implementation first, remove only that newly authored work
and start with RED. If a pure refactor began without a verified baseline, stop and establish one
before continuing. Preserve pre-existing or user-authored work and ask for direction when provenance
or scope is unclear.

## RED–GREEN–REFACTOR

For a behavior-preserving refactor, verify the existing characterization suite, enter at step 5,
and return to RED if the intended work changes the observable contract.

1. **RED:** Write one minimal, clearly named test for one observable behavior,
   data contract, security property, or executable artifact outcome under
   [P022](../../docs/principles/README.md#p022). Use real code unless a controlled substitute is
   needed at a genuine external boundary. Apply [P023](../../docs/principles/README.md#p023),
   [P024](../../docs/principles/README.md#p024),
   [P025](../../docs/principles/README.md#p025), and
   [P028](../../docs/principles/README.md#p028) when the behavior calls for them.
2. **Verify RED:** Discover the repository's focused test command and run it.
   The test must fail—not error—for the expected missing behavior. A filtered
   command must prove it selected a relevant test; C++/CMake tests must be wired
   to a real build and test target. If the test passes, it covers existing
   behavior; if it errors, fix the test setup and run it again. Keep the test
   deterministic and isolated under [P027](../../docs/principles/README.md#p027).
3. **GREEN:** Write the simplest behaviorally complete code that passes, following
   [P001 — KISS — Keep It Simple, Stupid](../../docs/principles/README.md#p001) and preferring
   [P090 — Prefer Negative Code](../../docs/principles/README.md#p090) only among equally correct
   solutions. Do not add speculative features, unrelated refactors, or implementation beyond the
   test's demonstrated need.
4. **Verify GREEN:** Run the discovered relevant suite. The new and existing
   tests must pass without errors or warnings; fix code rather than weakening a
   test.
5. **REFACTOR:** After green, improve structure without adding behavior. Remove genuine knowledge
   duplication under [P003 — DRY — Don't Repeat Yourself](../../docs/principles/README.md#p003)
   without violating
   [P013 — AHA — Avoid Hasty Abstractions](../../docs/principles/README.md#p013); protect
   [P070 — Code Health Must Not Regress](../../docs/principles/README.md#p070),
   [P084 — Prefer Local Reasoning](../../docs/principles/README.md#p084), and
   [P086 — Readability Counts](../../docs/principles/README.md#p086). Prefer deletion under
   [P090](../../docs/principles/README.md#p090) only when behavior and clarity remain intact. Keep
   tests green, then start the next RED cycle.

For documentation-only changes, use existing Markdown, link, and executable
example validation. Do not create production code or a text-assertion harness
to manufacture a RED phase.

## Evidence before completion

Discover commands from `AGENTS.md`, task runners, manifests, lockfiles, and
required CI; prefer repository-native entry points. Record focused and relevant
suite, coverage, type, and lint commands when applicable. If they conflict or
no safe command is discoverable, ask the user rather than borrow another
repository's command.

Before completion, confirm proportionate coverage for every changed observable
behavior and bug regression; controlled time, services, randomness, state, and
mocks where the product requires them; non-empty focused test selection; and
fresh passing relevant tests, type checks, and lint. Follow the
[evidence-integrity policy](../../docs/policies/evidence-integrity.md) before claiming success. Use
`learn` for a durable testing lesson; its own scope and delivery rules determine whether it
publishes a PR.

## Failed approaches

- Writing production code before RED, or keeping in-scope implementation written ahead of the test.
- Accepting an erroring test as RED instead of fixing the setup and re-running until it fails for
  the expected missing behavior.
- Weakening a test to reach GREEN instead of fixing the code.
- Adding speculative features or unrelated refactors beyond what a demonstrated test need requires.

---

_Adapted from [obra/superpowers](https://github.com/obra/superpowers) under the [MIT License](https://github.com/obra/superpowers/blob/main/LICENSE). Copyright (c) 2025 Jesse Vincent._
