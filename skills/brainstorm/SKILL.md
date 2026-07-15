---
name: brainstorm
description: Use before complex creative work to explore intent and requirements. Requires the Mnemosyne knowledge backend through advise and fails closed when it cannot be prepared.
argument-hint: <idea or feature description>
allowed-tools: [Read, Write, Bash, Grep, Glob, Agent]
---

# Brainstorming Ideas Into Designs

Help turn ideas into fully formed designs and specs through natural collaborative dialogue.

Start by understanding the current project context, then ask questions one at a time to refine the idea. Once you understand what you're building, present the design and get user approval.

**HARD GATE:** Do NOT write any code, scaffold any project, or take any implementation action until you have presented a design and the user has approved it. This applies to EVERY request regardless of perceived simplicity.

## Anti-Pattern: "This Is Too Simple To Need A Design"

Every feature goes through this process. "Simple" projects are where unexamined assumptions cause the most wasted work. The design can be short (a few sentences), but you MUST present it and get approval.

## Checklist

Complete in order:

1. **Run `advise`** with the feature description to check the required knowledge backend.
2. **Explore project context** — check files, docs, recent commits
3. **Ask clarifying questions** — one at a time, understand purpose/constraints/success criteria
4. **Propose 2-3 approaches** — with trade-offs and your recommendation
5. **Present design** — in sections scaled to their complexity, get user approval after each section
6. **Persist when needed** — write `docs/specs/YYYY-MM-DD-<topic>-design.md` only when complexity,
   project policy, or a current downstream consumer requires a durable specification
7. **Design self-review** — scan for placeholders, contradictions, ambiguity, and scope issues
8. **User confirms the design** — request file review only when a specification was persisted
9. **Transition to implementation** — invoke `myrmidon-swarm` for complex implementation. If an
   installed planning skill is available, it may track the approved design; otherwise write a short
   numbered implementation plan in the current conversation and proceed sequentially.

## The Process

**Understanding the idea:**

- Check out the current project state first (files, docs, `git log --oneline -10`)
- Before asking detailed questions, assess scope: if the request describes multiple independent subsystems, flag this immediately. Help the user decompose into sub-projects first.
- For appropriately-scoped projects, ask questions one at a time
- Prefer multiple choice questions when possible
- Only one question per message
- Focus on: purpose, constraints, success criteria

**Exploring approaches:**

- Propose 2-3 different approaches with trade-offs
- Lead with your recommended option and explain why
- Reference existing patterns in the target codebase

**Presenting the design:**

- Present in sections, ask after each whether it looks right
- Scale each section to its complexity
- Cover: architecture, components, data flow, error handling, testing strategy
- Follow Athena's local development principles: KISS, YAGNI, DRY, SOLID, modularity, and POLA

**Working in existing codebases:**

- Follow existing patterns in the target repository
- Invoke the `advise` skill first to check for existing implementations
- Don't propose unrelated refactoring — stay focused on the current goal

## After the Design

**Persist a spec only when required:**

For small changes, keep the approved design in the conversation and proceed. When complexity,
project policy, or a current downstream consumer requires a durable specification, save it to
`docs/specs/YYYY-MM-DD-<topic>-design.md` and commit it as
`docs(specs): add <topic> design document`.

Before writing or committing a specification, read the target repository's mutation, signing, DCO,
and review policy and establish explicit user authority for the proposed file and commit. Approval
of the design content alone does not authorize a repository mutation. Without that authority, keep
the approved design in the conversation and hand off the proposed path and commit subject.

**Spec Self-Review:**

1. **Placeholder scan:** Any "TBD", "TODO", incomplete sections? Fix them.
2. **Internal consistency:** Do any sections contradict each other?
3. **Scope check:** Is this focused enough for a single plan?
4. **Ambiguity check:** Can any requirement be interpreted two ways? Pick one and make it explicit.

**User Review Gate:**
After self-review of a persisted specification:
> "Spec written and committed to `docs/specs/<filename>`. Please review and let me know if you want changes before we start planning implementation."

Wait for approval. Only proceed once approved.

**Implementation:**

- Use an installed planning skill for task tracking, or write the numbered plan inline when none is
  installed.
- Invoke the `myrmidon-swarm` skill for complex multi-agent work.

## Key Principles

- **One question at a time** — don't overwhelm with multiple questions
- **YAGNI ruthlessly** — remove unnecessary features from all designs
- **Explore alternatives** — always propose 2-3 approaches
- **Incremental validation** — present design sections, get approval before moving on
- **Invoke `advise` first** — don't propose what's already been built or debugged

---

_Adapted from [obra/superpowers](https://github.com/obra/superpowers) under the [MIT License](https://github.com/obra/superpowers/blob/main/LICENSE). Copyright (c) 2025 Jesse Vincent._
