---
name: realign
license: BSD-3-Clause
description: Bring a plan back into line with the repository architecture. Use this skill when a plan, an issue, or a change conflicts with the architecture documents. Rewrite the plan to fit, or report the architecture conflict.
argument-hint: "ISSUE_NUMBER_OR_URL"
allowed-tools: [Read, Bash, Grep, Glob, Edit, Write]
---

# Realign a plan with the architecture

Use this skill when work and the architecture disagree. The goal is one plan that the architecture
supports, so implementation can go on.

Apply the [ASD-STE100 technical-English policy](../TECHNICAL_ENGLISH.md) to this skill and to
all prose that it produces.

## Workflow

1. Read the issue and the current plan.
2. Read the architecture sources of the repository: `docs/architecture*`, ADRs, and the design
   documents that the plan touches. Read the code that the plan changes.
3. List each place where the plan conflicts with the architecture: a boundary the plan crosses, a
   dependency direction it reverses, or a mechanism it duplicates.
4. For each conflict, choose one:
   - **Rewrite the plan.** Change the approach so it follows the architecture and still meets the
     issue's requirements. This is the usual choice.
   - **Flag the architecture.** If the issue's requirement cannot be met inside the architecture,
     say which document is in the way and what change it needs. Do not change the architecture in
     silence.
5. Output the full revised plan, starting with `# Implementation Plan`. End it with a short list
   of what changed and why. If you flagged the architecture, put the conflict first.

## Rules

- Keep the plan inside the issue. Do not add work for its own sake.
- Prefer the existing mechanism over a new one.
- Name real files and symbols. Check that they exist.
- Do not block on a conflict that you can resolve by rewriting the plan.
