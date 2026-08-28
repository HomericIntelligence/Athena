---
name: brainstorm
license: BSD-3-Clause
description: Use before complex creative work. Examine intent and requirements. Stop if `advise` cannot prepare Mnemosyne.
argument-hint: <idea or feature description>
allowed-tools: [Read, Write, Bash, Grep, Glob, Agent]
---

# Develop designs from ideas

Develop a complete design and specification through a dialog with the user.

Apply the [ASD-STE100 technical-English policy](../TECHNICAL_ENGLISH.md) to this skill and to all
prose that it produces.

First, inspect the current project. Ask one question in each message to clarify the idea. When the
requirements are clear, present the design. Continue with the requested implementation unless a
requirement remains unresolved.

**DESIGN CHECKPOINT:** Before a complex implementation, present a design that has sufficient detail
for the scope. Use this checkpoint to confirm shared understanding. It is not a permission gate.
Stop only for an unresolved requirement or a filesystem-destructive action.

## Engineering principles

Use Athena's [canonical engineering-principles catalog](../../docs/principles/README.md) as the
definition source. Use these principles to make workflow decisions:

- [P001 — KISS — Keep It Simple, Stupid](../../docs/principles/README.md#p001): Make the design
  sufficient for the problem that the evidence shows. Select the minimum solution that obeys
  all requirements.
- [P002 — YAGNI — You Ain't Gonna Need It](../../docs/principles/README.md#p002): Do not include a
  capability, extension point, or infrastructure that has no specified current requirement.
- [P007 — Subtraction Over Addition](../../docs/principles/README.md#p007): Before you recommend a new
  component, find if removal, consolidation, or an existing mechanism can give the necessary
  result.
- [P008 — Understand Before Subtracting](../../docs/principles/README.md#p008): Before you recommend
  deletion, examine the purpose, consumers, and history of the applicable component.
- [P012 — Evidence Before Modification](../../docs/principles/README.md#p012): Before you select a
  design, use repository code, contracts, tests, history, and guidance as evidence.
- [P015 — Architecture Conformance](../../docs/principles/README.md#p015): If the requirement does
  not change the architecture, obey the established boundaries and dependency direction.
- [P071 — Consistency Over Personal Preference](../../docs/principles/README.md#p071): If repository
  conventions obey the requirement, use them. Do not select a different style because of
  personal preference.
- [P074 — Prefer Existing Mechanisms](../../docs/principles/README.md#p074): Before you make a
  mechanism, find an applicable existing mechanism. If it obeys the requirement, use it.

## Failed approaches

Use this process for each feature. A short design can be sufficient for a simple change. Before
implementation, the design must show its assumptions and constraints.

- Do not skip `advise` retrieval. Without this retrieval, the design can duplicate an existing
  solution or repeat a problem that prior guidance already resolved.

## Checklist

Complete in order:

1. **Advise retrieval.** Run `advise` with the feature description to check the required knowledge
   backend.
2. **Project evidence.** Read applicable files, documents, and recent commits.
3. **Clarification.** Ask one question in each message to identify the purpose, constraints, and
   success criteria.
4. **Approach options.** Propose two or three approaches.
5. **Trade-offs.** State the trade-offs for each approach.
6. **Recommendation.** Identify your recommended approach.
7. **Design presentation.** Present sections that have sufficient detail for their complexity.
8. **Material ambiguity.** Ask a question only to resolve a material ambiguity.
9. **Durable specification.** Write `docs/specs/YYYY-MM-DD-<topic>-design.md` only if complexity,
   project policy, or a current downstream consumer requires it.
10. **Design review.** Check the design for placeholders, contradictions, ambiguities, and scope
    errors.
11. **Saved path.** If you saved a specification, report its path.
12. **User review.** Ask the user to review a saved specification.
13. **Continuation.** Do not stop unless a requirement remains unresolved.
14. **Implementation.** Start the requested implementation.
15. **Complex work.** For a complex implementation, invoke `myrmidon-swarm`.
16. **Planning skill.** If an installed planning skill is available, use it to track the design.
17. **Planning fallback.** Otherwise, write a short numbered plan in the current conversation.
18. **Sequential work.** Complete the fallback plan in sequence.

## Process

### Understand the idea

- First, inspect the current project files, documents, and `git log --oneline -10`.
- Before you ask detailed questions, assess the scope.
- If the request contains multiple independent subsystems, tell the user immediately. Help the user
  divide the request into subprojects.
- If the project has a suitable scope, ask questions one at a time.
- Use multiple-choice questions when possible.
- Ask only one question in each message.
- Ask about the purpose, constraints, and success criteria.

### Compare approaches

- Propose two or three different approaches with trade-offs.
- Put your recommended option first. Explain the reason for the recommendation.
- Refer to existing patterns in the target codebase.
- For each approach that adds code or structure, name one credible subtractive or reuse
  alternative first.
- If no subtractive or reuse alternative can meet the requirement, say why with evidence.

### Present the design

- Present the design in sections. Ask after each section if it is correct.
- Give each section sufficient detail for its complexity.
- Include architecture, components, data flow, error handling, and the test strategy.
- Use these principles to define component responsibilities and boundaries:
  [P004 — SOLID](../../docs/principles/README.md#p004),
  [P005 — Modularity](../../docs/principles/README.md#p005),
  [P016 — Separation of Concerns](../../docs/principles/README.md#p016),
  [P017 — High Cohesion, Low Coupling](../../docs/principles/README.md#p017), and
  [P018 — Information Hiding](../../docs/principles/README.md#p018).
- Use [P006 — POLA — Principle of Least Astonishment](../../docs/principles/README.md#p006) and
  [P019 — Explicit Contracts](../../docs/principles/README.md#p019) to make interfaces predictable.
  Document observable inputs, outputs, errors, and invariants.
- Use [P020 — Executable Architecture](../../docs/principles/README.md#p020) to identify critical
  architecture rules that need automated enforcement. Use
  [P021 — Evolutionary and Reversible Design](../../docs/principles/README.md#p021) to divide the
  design into reversible increments. Specify the migration and rollback boundaries.
- Use [P077 — Separate Policy from Mechanism](../../docs/principles/README.md#p077) to separate
  decisions from machinery. Use
  [P078 — Single Source of Truth](../../docs/principles/README.md#p078) to identify the authoritative
  state. Use [P079 — Explicit Ownership and Lifetimes](../../docs/principles/README.md#p079) to
  identify ownership and cleanup.
- Use [P007](../../docs/principles/README.md#p007) and
  [P008](../../docs/principles/README.md#p008) to question additions. Use
  [P088](../../docs/principles/README.md#p088) and
  [P089](../../docs/principles/README.md#p089) to remove verified dead code and obsolete scaffolding.
  If designs are equally correct, give preference to
  [P090 — Prefer Negative Code](../../docs/principles/README.md#p090).
- Use [P010 — Scope Fidelity](../../docs/principles/README.md#p010) to keep the proposal in the stated
  goal. Then use [P011 — Minimal Coherent Change](../../docs/principles/README.md#p011) and
  [P012 — Evidence Before Modification](../../docs/principles/README.md#p012) to select the smallest
  complete change that the evidence supports.
- Use [P009 — General Mechanisms Over Special Cases](../../docs/principles/README.md#p009) only if
  current repeated cases show the need for a reusable mechanism. Use
  [P013 — AHA — Avoid Hasty Abstractions](../../docs/principles/README.md#p013) to delay an unstable
  abstraction.
- Identify behavior that is outside the requested change. Preserve it under
  [P014 — Preserve Unrequested Behavior](../../docs/principles/README.md#p014).

### Work in existing codebases

- Follow existing patterns in the target repository.
- Invoke `advise` first to check for existing implementations.
- Do not propose unrelated refactoring. Keep the work in the current goal.

## After the design

### Save a specification only when necessary

For a small change, keep the design in the conversation. Then, continue with the requested
implementation. If complexity, project policy, or a current downstream consumer requires a durable
specification, save it to
`docs/specs/YYYY-MM-DD-<topic>-design.md`. Use this commit message:
`docs(specs): add <topic> design document`.

Before you write or commit a specification, read the target repository policies for mutation,
signing, the Developer Certificate of Origin (DCO), and review. If the specification is in scope,
you can write it without a separate approval prompt. After you write an in-scope specification, you
can commit it without a separate approval prompt. If a durable artifact is not necessary, keep the
specification in the conversation.

### Review the specification

1. **Find placeholders.** Search for `TBD`, `TODO`, and incomplete sections.
2. **Correct placeholders.** Correct each item that the search finds.
3. **Check consistency.** Correct each conflict between sections.
4. **Check the scope.** Make sure that one plan can contain the work.
5. **Select one meaning.** If a requirement has two possible meanings, select one meaning.
6. **State the meaning.** State the selected meaning clearly.

### Report the specification

After you review a saved specification, report its location. Continue with the requested
implementation unless the user requests changes. Use this message:

> I wrote and committed the specification at `docs/specs/<filename>`. Review it and tell me if you
> want changes.

### Implement the design

- If a planning skill is installed, use it to track the task. Otherwise, write the numbered plan in
  the conversation.
- For complex multi-agent work, invoke `myrmidon-swarm`.

## Rules

- **Ask one question at a time.** Do not put multiple questions in one message.
- **Apply [P002 — YAGNI — You Ain't Gonna Need It](../../docs/principles/README.md#p002).** Remove
  unnecessary features from all designs.
- **Compare alternatives.** Always propose two or three approaches.
- **Validate in increments.** Present the design in sections. Resolve material ambiguity before you
  continue.
- **Invoke `advise` first.** Do not duplicate an existing solution. Do not repeat a problem that prior
  guidance already resolved.

---

_Adapted from [obra/superpowers](https://github.com/obra/superpowers) under the [MIT License](https://github.com/obra/superpowers/blob/main/LICENSE). Copyright (c) 2025 Jesse Vincent._
