---
name: brainstorm
license: BSD-3-Clause
description: Use before complex creative work to explore intent and requirements. Requires the Mnemosyne knowledge backend through advise and fails closed when it cannot be prepared.
argument-hint: <idea or feature description>
allowed-tools: [Read, Write, Bash, Grep, Glob, Agent]
---

# Brainstorming Ideas Into Designs

Help the user turn an idea into a complete design through a natural, collaborative dialogue.

Apply the [ASD-STE100 writing policy](../../docs/technical-english.md) to this skill and to all prose
that it produces.

Start by understanding the current project context, then ask questions one at a time to refine the idea. Once you understand what you're building, present the design and proceed with the requested implementation unless a requirement remains unresolved.

**DESIGN CHECKPOINT:** Present a scaled design before complex implementation. It is a shared understanding checkpoint, not a permission gate; pause only for unresolved requirements or a filesystem-destructive action.

## Engineering principles

Use Athena's [canonical engineering-principles catalog](../../docs/principles/README.md) as the
definition source. Apply these principles to this workflow:

- [P001 — KISS — Keep It Simple, Stupid](../../docs/principles/README.md#p001): scale the design to
  the demonstrated problem and choose the least complex complete approach.
- [P002 — YAGNI — You Ain't Gonna Need It](../../docs/principles/README.md#p002): exclude speculative
  capabilities, extension points, and infrastructure from the design.
- [P007 — Subtraction Over Addition](../../docs/principles/README.md#p007): test whether removal,
  consolidation, or reuse solves the need before proposing a new moving part.
- [P008 — Understand Before Subtracting](../../docs/principles/README.md#p008): inspect purpose,
  consumers, and history before recommending deletion.
- [P012 — Evidence Before Modification](../../docs/principles/README.md#p012): ground alternatives in
  repository code, contracts, tests, history, and guidance before selecting a design.
- [P015 — Architecture Conformance](../../docs/principles/README.md#p015): follow established
  boundaries and dependency direction unless the requirement deliberately changes them.
- [P071 — Consistency Over Personal Preference](../../docs/principles/README.md#p071): prefer repository
  conventions over stylistic preference when they satisfy the requirement.
- [P074 — Prefer Existing Mechanisms](../../docs/principles/README.md#p074): reuse a suitable existing
  mechanism before inventing another one.

## Failed approaches

Every feature goes through this process. "Simple" projects are where unexamined assumptions cause the most wasted work. The design can be short (a few sentences), and should make assumptions and constraints visible before implementation.

- Skipping `advise` retrieval before design proposes what already exists or was already debugged.

## Checklist

Complete in order:

1. **Run `advise`** with the feature description to check the required knowledge backend.
2. **Explore project context** — check files, docs, recent commits
3. **Ask clarifying questions** — one at a time, understand purpose/constraints/success criteria
4. **Propose 2-3 approaches** — with trade-offs and your recommendation
5. **Present design** — in sections scaled to their complexity; ask only to resolve material ambiguity
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
- Define component responsibilities and boundaries using
  [P004 — SOLID](../../docs/principles/README.md#p004),
  [P005 — Modularity](../../docs/principles/README.md#p005),
  [P016 — Separation of Concerns](../../docs/principles/README.md#p016),
  [P017 — High Cohesion, Low Coupling](../../docs/principles/README.md#p017), and
  [P018 — Information Hiding](../../docs/principles/README.md#p018).
- Make interfaces predictable by documenting observable inputs, outputs, errors, and invariants with
  [P006 — POLA — Principle of Least Astonishment](../../docs/principles/README.md#p006),
  and [P019 — Explicit Contracts](../../docs/principles/README.md#p019).
- Identify critical architecture rules that need automated enforcement under
  [P020 — Executable Architecture](../../docs/principles/README.md#p020), and stage the design as
  reversible increments with explicit migration or rollback boundaries under
  [P021 — Evolutionary and Reversible Design](../../docs/principles/README.md#p021).
- Separate decisions from machinery and identify authoritative state and cleanup through
  [P077 — Separate Policy from Mechanism](../../docs/principles/README.md#p077),
  [P078 — Single Source of Truth](../../docs/principles/README.md#p078), and
  [P079 — Explicit Ownership and Lifetimes](../../docs/principles/README.md#p079).
- Challenge additions with [P007](../../docs/principles/README.md#p007) and
  [P008](../../docs/principles/README.md#p008); remove verified dead code and obsolete scaffolding
  under [P088](../../docs/principles/README.md#p088) and
  [P089](../../docs/principles/README.md#p089), preferring
  [P090 — Prefer Negative Code](../../docs/principles/README.md#p090) only among equally correct
  designs.
- Bound the proposal to the stated goal with
  [P010 — Scope Fidelity](../../docs/principles/README.md#p010), then select the smallest complete
  evidence-backed change with [P011 — Minimal Coherent Change](../../docs/principles/README.md#p011)
  and [P012 — Evidence Before Modification](../../docs/principles/README.md#p012).
- Prefer a reusable mechanism under
  [P009 — General Mechanisms Over Special Cases](../../docs/principles/README.md#p009) only when
  current repeated cases demonstrate it; use
  [P013 — AHA — Avoid Hasty Abstractions](../../docs/principles/README.md#p013) to defer an unstable
  abstraction.
- Enumerate behavior outside the requested change and preserve it under
  [P014 — Preserve Unrequested Behavior](../../docs/principles/README.md#p014).

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
and review policy. A specification that is in scope may be written and committed without a separate
approval prompt; retain it in the conversation when a durable artifact is not needed.

**Spec Self-Review:**

1. **Placeholder scan:** Any "TBD", "TODO", incomplete sections? Fix them.
2. **Internal consistency:** Do any sections contradict each other?
3. **Scope check:** Is this focused enough for a single plan?
4. **Ambiguity check:** Can any requirement be interpreted two ways? Pick one and make it explicit.

**User Review:**
After self-review of a persisted specification, report its location and proceed with the requested
implementation unless the user requests changes:
> "Spec written and committed to `docs/specs/<filename>`. Please review and let me know if you want changes before we start planning implementation."

**Implementation:**

- Use an installed planning skill for task tracking, or write the numbered plan inline when none is
  installed.
- Invoke the `myrmidon-swarm` skill for complex multi-agent work.

## Working rules

- **One question at a time** — don't overwhelm with multiple questions
- **Apply [P002 — YAGNI — You Ain't Gonna Need It](../../docs/principles/README.md#p002)** — remove
  unnecessary features from
  all designs
- **Explore alternatives** — always propose 2-3 approaches
- **Incremental validation** — present design sections and resolve material ambiguity before moving on
- **Invoke `advise` first** — don't propose what's already been built or debugged

---

_Adapted from [obra/superpowers](https://github.com/obra/superpowers) under the [MIT License](https://github.com/obra/superpowers/blob/main/LICENSE). Copyright (c) 2025 Jesse Vincent._
