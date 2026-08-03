# Design-document structure

**Why:** A design is easier to review and implement when readers first understand the problem and
boundary it protects, then the system shape, and only then each component's decisions.

## Required order

1. **Why** — state the problem, intended outcome, and protected boundary in one or two sentences.
2. **At a glance** — name the decision, scope, non-goals, and invariants.
3. **System shape** — add one block diagram only when relationships, ownership, or flow are clearer
   visually than in a table.
4. **High-level design** — map components, interfaces, and dependency direction before implementation
   detail.
5. **Component details** — explain each component separately: responsibility, inputs and outputs,
   state ownership, failure boundary, and verification.
6. **Operations and consequences** — record security, rollout, rollback, migration, observability,
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

Use a diagram to clarify three or more relationships, a control-flow branch, or ownership that would
otherwise require repeated prose. Keep it at the system boundary; do not repeat the same diagram in
component documents. Prefer a table for a simple mapping, a sequence for time-ordered interaction,
and prose for one local decision.

## Safety and architecture

A design document explains a current requirement; it does not authorize implementation, external
writes, or a change to an accepted ADR. Apply the [shared review contract](common.md): architecture
alignment precedes implementation detail, and a material architecture change needs an evidenced design
decision or ADR. Create or change one only when it explains a current product decision; do not duplicate
an existing requested scope or add a document without a consumer. Accepted ADRs are append-only; write a
superseding ADR rather than editing one.
