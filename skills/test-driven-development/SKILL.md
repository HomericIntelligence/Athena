---
name: test-driven-development
description: Use when implementing any feature or bugfix, before writing implementation code — enforces RED-GREEN-REFACTOR cycle
argument-hint: <feature or bugfix description>
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob]
---

# Test-Driven Development (TDD)

Why: seeing a focused test fail proves it can detect the missing product
behavior; seeing it pass proves the smallest implementation satisfies it.

Use Athena's shared [behavior-first testing guidance](../../docs/review/behavior-first-testing.md)
for good-test/bad-test criteria, determinism, and false-pass checks. Test
observable product behavior and core contracts, not wording, documentation
layout, or a private implementation arrangement.

## Use and rule

Use TDD for features, bug fixes, refactoring, and behavior changes. Ask the
human partner before exempting a throwaway prototype, generated code,
configuration-only work, or documentation-only wording/layout change. In a
swarm, the test specialist completes RED before implementation begins.

```text
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
```

If you wrote in-scope implementation first, remove only that newly authored
work and start with RED. Preserve pre-existing or user-authored work and ask for
direction when provenance or scope is unclear.

## RED–GREEN–REFACTOR

1. **RED:** Write one minimal, clearly named test for one observable behavior,
   data contract, security property, or executable artifact outcome. Use real
   code unless a controlled substitute is needed at a genuine external boundary.
2. **Verify RED:** Discover the repository's focused test command and run it.
   The test must fail—not error—for the expected missing behavior. A filtered
   command must prove it selected a relevant test; C++/CMake tests must be wired
   to a real build and test target. If the test passes, it covers existing
   behavior; if it errors, fix the test setup and run it again.
3. **GREEN:** Write the simplest behaviorally complete code that passes. Do not
   add speculative features, unrelated refactors, or implementation beyond the
   test's demonstrated need.
4. **Verify GREEN:** Run the discovered relevant suite. The new and existing
   tests must pass without errors or warnings; fix code rather than weakening a
   test.
5. **REFACTOR:** After green, remove duplication, clarify names, or extract a
   helper without adding behavior. Keep tests green, then start the next RED
   cycle.

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
fresh passing relevant tests, type checks, and lint. Follow the evidence policy
before claiming success. Use `learn` for a durable testing lesson; its own
scope and delivery rules determine whether it publishes a PR.

---

_Adapted from [obra/superpowers](https://github.com/obra/superpowers) under the [MIT License](https://github.com/obra/superpowers/blob/main/LICENSE). Copyright (c) 2025 Jesse Vincent._
