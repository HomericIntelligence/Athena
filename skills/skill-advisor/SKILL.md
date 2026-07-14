---
name: skill-advisor
description: Use when starting a task to determine which Athena procedural skill applies before work begins.
argument-hint: <task description>
allowed-tools: []
---

# Skill Advisor

Routes the current task to the appropriate Athena skill.

**Core principle:** Check for a relevant skill BEFORE beginning any substantive work. If there is even a 1% chance a skill applies, invoke it.

**Difference from `advise`:** `advise` searches the required knowledge backend for prior lessons;
this skill routes to procedural skills. Use both: knowledge first, then process.

---

## Decision Tree

```
What are you about to do?
│
├─ Implementing a new feature or fixing a bug?
│   └─ → /athena:test-driven-development (BEFORE writing any code)
│
├─ Debugging an unexpected failure, bug, or error?
│   └─ → /athena:systematic-debugging (BEFORE proposing fixes)
│
├─ About to claim work is "done", "passing", or "fixed"?
│   └─ → /athena:verification (BEFORE making any success claims)
│
├─ Starting a complex or ambiguous feature from scratch?
│   └─ → /athena:brainstorm (BEFORE writing any code or plan)
│
├─ Needing an isolated workspace for a new branch?
│   └─ → /athena:git-worktrees
│       (skip if using myrmidon-swarm — it handles isolation automatically)
│
├─ Implementation complete, ready to merge or create PR?
│   └─ → /athena:finish-branch (AFTER running /athena:verification)
│
├─ Completed a major task and want quality assurance?
│   └─ → /athena:code-review (uses an independent reviewer when available)
│
└─ Received code review feedback to act on?
    └─ → /athena:code-review (Part 2: Receiving)
```

## Skill Priority

When multiple skills could apply:

1. **Process skills first** (brainstorm, systematic-debugging) — determine HOW to approach
2. **Execution skills second** (test-driven-development, git-worktrees) — guide execution
3. **Completion skills last** (verification, finish-branch, code-review) — gate closure

Example: "Fix this bug" → systematic-debugging first, then test-driven-development for the fix.

Example: "Build new feature" → brainstorm first, then test-driven-development for implementation.

## When to Skip This Skill

- You are a subagent dispatched by myrmidon-swarm with a specific task — follow your task prompt directly
- You were explicitly told "just do X" without workflow overhead
- The task is truly trivial (typo fix, single-line rename)

## Rationalization Prevention

These thoughts mean you should still check:

| Thought | Reality |
|---------|---------|
| "This is just a simple question" | Questions can become tasks. Check. |
| "I already know the approach" | Skills evolve. Check current version. |
| "Skill is overkill for this" | Simple things become complex. Use it. |
| "I'll check after exploring" | Skills tell you HOW to explore. Check first. |

---

*Adapted from [obra/superpowers](https://github.com/obra/superpowers) under the [MIT License](https://github.com/obra/superpowers/blob/main/LICENSE). Copyright (c) 2025 Jesse Vincent.*
