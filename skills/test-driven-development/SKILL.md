---
name: test-driven-development
description: Use when implementing any feature or bugfix, before writing implementation code — enforces RED-GREEN-REFACTOR cycle
argument-hint: <feature or bugfix description>
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob]
---

# Test-Driven Development (TDD)

## Overview

Write the test first. Watch it fail. Write minimal code to pass.

**Core principle:** If you didn't watch the test fail, you don't know if it tests the right thing.

**Violating the letter of the rules is violating the spirit of the rules.**

## When to Use

**Always:**

- New features
- Bug fixes
- Refactoring
- Behavior changes

**Exceptions (ask your human partner):**

- Throwaway prototypes
- Generated code
- Configuration files
- Documentation-only wording and layout changes

**Integration with myrmidon-swarm:** apply this cycle to each test sub-task. A specialist writes
failing tests before an executor writes implementation.

Thinking "skip TDD just this once"? Stop. That's rationalization.

## The Iron Law

```text
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
```

Write code before the test? Delete it. Start over.

**No exceptions:**

- Don't keep it as "reference"
- Don't "adapt" it while writing tests
- Don't look at it
- Delete means delete

Implement fresh from tests. Period.

## Red-Green-Refactor

### RED — Write Failing Test

Write one minimal test showing what should happen.

**Requirements:**

- One behavior per test
- Clear descriptive name
- Test real code (no mocks unless unavoidable)
- Assert a computable product outcome, data contract, security property, or executable artifact
  structure; never freeze documentation prose, headings, counts, or paragraph presence

### Verify RED — Watch It Fail

**MANDATORY. Never skip.**

Discover the target repository's focused test command from its guidance, task runner, manifests,
lockfiles, and required CI, then run `<repository-focused-test-command>`.

Confirm:

- Test fails (not errors)
- Failure message is expected
- Fails because feature is missing (not typos)

**Test passes?** You're testing existing behavior. Fix the test.

**Test errors?** Fix the error, re-run until it fails correctly.

Do not invent production code or a test harness to force a RED phase for documentation-only work.
Use existing markdown lint and link validation for syntax and navigation. A link checker may prove a
target resolves; a text assertion must not dictate what the documentation says.

### GREEN — Minimal Code

Write the simplest code to pass the test. No more.

Don't add features, refactor other code, or "improve" beyond what the test demands.

### Verify GREEN — Watch It Pass

**MANDATORY.**

Run the repository's discovered full relevant suite: `<repository-test-command>`.

Confirm:

- The new test passes
- All other tests still pass
- No errors or warnings

**Test fails?** Fix code, not test.

**Other tests fail?** Fix now before continuing.

### REFACTOR — Clean Up

After green only:

- Remove duplication
- Improve names
- Extract helpers

Keep tests green throughout. Don't add behavior.

### Repeat

Next failing test for next behavior.

## Repository tooling

Discover commands from `AGENTS.md`, task runners, manifests, lockfiles, and required CI. Prefer the
same entry points CI uses. Record the focused test, relevant suite, coverage, typing, and lint
commands when applicable. If repository sources conflict or no safe command is discoverable, ask
the user; never substitute Athena's Pixi/Pytest commands into an unrelated target.

## Good Tests

| Quality | Good | Bad |
| --------- | ------ | ----- |
| **Minimal** | One thing. "and" in name? Split it. | `test('validates email and domain and whitespace')` |
| **Clear** | Name describes behavior | `test_1` |
| **Shows intent** | Demonstrates desired API | Obscures what code should do |

## Common Rationalizations — All Wrong

| Excuse | Reality |
| -------- | --------- |
| "Too simple to test" | Simple code breaks. Test takes 30 seconds. |
| "I'll test after" | Tests passing immediately prove nothing. |
| "Tests after achieve same goals" | Tests-after = "what does this do?" Tests-first = "what should this do?" |
| "Already manually tested" | Ad-hoc ≠ systematic. No record, can't re-run. |
| "Deleting X hours is wasteful" | Sunk cost fallacy. Keeping unverified code is technical debt. |
| "Keep as reference, write tests first" | You'll adapt it. That's testing after. Delete means delete. |
| "Need to explore first" | Fine. Throw away exploration, start with TDD. |

## Red Flags — STOP and Start Over

- Code written before test
- Test passes immediately without implementation
- Can't explain why test failed
- "Tests added later"
- Rationalizing "just this once"

**All of these mean: Delete code. Start over with TDD.**

## Verification Checklist

Before marking work complete:

- [ ] Every new function/method has a test
- [ ] No test pins documentation wording or another non-behavioral string
- [ ] Watched each test fail before implementing
- [ ] Each test failed for the expected reason
- [ ] Wrote minimal code to pass each test
- [ ] All relevant tests pass with the repository's discovered test command
- [ ] The repository-defined type check passes
- [ ] The repository-defined linter passes

Can't check all boxes? You skipped TDD. Start over.

## After Completion

Invoke the `verification` skill before claiming work complete.
Run `learn` when the session produced a durable testing lesson; it must publish through a PR.

---

_Adapted from [obra/superpowers](https://github.com/obra/superpowers) under the [MIT License](https://github.com/obra/superpowers/blob/main/LICENSE). Copyright (c) 2025 Jesse Vincent._
