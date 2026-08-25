# Design-document structure

**Why:** A design is easier to review and implement when readers first understand the problem and
boundary it protects, then the system shape, and only then each component's decisions.

Use the [ASD-STE100 technical-English policy](../../skills/TECHNICAL_ENGLISH.md) for all technical prose and review
output.

## Required order

1. **Why:** State the problem, intended outcome, and protected boundary in one or two sentences.
2. **At a glance:** Name the decision, scope, non-goals, and invariants.
3. **System shape:** If relationships, ownership, or flow are clearer in a diagram, add one block
   diagram.
4. **High-level design:** Map components, interfaces, and dependency direction before implementation
   detail.
5. **Component details:** Explain each component separately: responsibility, inputs and outputs,
   state ownership, failure boundary, and verification.
6. **Operations and consequences:** Record security, rollout, rollback, migration, observability,
   alternatives, and unresolved decisions when applicable.

## Minimal template

```md
# <Decision or subsystem>

**Why:** <problem, intended outcome, and protected boundary.>

## At a glance

- Decision: <what changes>
- Scope and non-goals: <what this does and does not cover>
- Invariants: <what must remain true>

## System shape

<a block diagram only when it clarifies the design>

## High-level design

| Component | Responsibility | Interfaces and ownership |
| --- | --- | --- |
| ... | ... | ... |

## Component details

### <Component>

- Inputs and outputs:
- State and dependency direction:
- Failure boundary:
- Verification:

## Operations and consequences

## Alternatives and unresolved decisions
```

## Diagram rules

Use a diagram if it clarifies three or more relationships, a control-flow branch, or ownership. Keep
the diagram at the system boundary. Do not repeat the same diagram in component documents. Use a
table for a simple mapping. Use a sequence for a time-ordered interaction. Use prose for one local
decision.

## Safety and architecture

A design document explains a current requirement. It does not authorize implementation, external
writes, or a change to an accepted architecture decision record (ADR). Apply the
[shared review contract](common.md). Confirm architecture alignment before you inspect implementation
detail. Support a material architecture change with an evidenced design decision or ADR. Create or
change a design document only when it explains a current product decision. Do not duplicate an
existing requested scope. Do not add a document without a consumer. Do not edit an accepted ADR.
Write a superseding ADR.
