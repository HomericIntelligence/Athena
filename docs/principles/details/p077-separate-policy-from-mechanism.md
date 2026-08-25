# P077 — Separate Policy from Mechanism

## Definition

**Separate Policy from Mechanism** keeps a decision about required behavior separate from the means
that execute the behavior. A mechanism supplies stable capabilities. A policy selects and limits
those capabilities for a specified context.

**Aliases:** policy-mechanism separation and separation of policy and mechanism.

## Provenance

**Classification:** established principle.

Early operating-system work developed this distinction. The Hydra system made the distinction
explicit for schedules, memory pages, and protection. Its mechanisms supported replaceable external
policies. The rule also applies to applications, security, work control, storage, and infrastructure.

## Decision rule

Give a variable rule a named policy boundary. Keep the mechanism neutral enough to apply each
supported policy correctly.

## How to apply

- Identify variable decisions separately from stable primitive operations.
- Give policy inputs, outputs, defaults, and failure behavior an explicit contract.
- Supply the policy through a narrow interface. Do not copy policy branches into the mechanism.
- Test policy choices independently from mechanism correctness.
- Keep enforcement mandatory when a policy protects security or integrity.

## Diagram

The policy selects an action. The mechanism performs only the selected action.

```mermaid
flowchart LR
    A["Context"] --> B["Policy decision"]
    B --> C["Selected action"]
    C --> D["Neutral mechanism"]
    D --> E["Result"]
```

## Language examples

The two examples pass a policy to a stable queue mechanism.

### Python

```python
def dispatch(job, priority_policy, queue) -> None:
    priority = priority_policy(job)
    entry = QueueEntry(job, priority)
    queue.push(entry)
```

### Rust

```rust
fn dispatch<P: PriorityPolicy>(job: Job, policy: &P, queue: &mut Queue) {
    let priority = policy.priority(&job);
    let entry = QueueEntry::new(job, priority);
    queue.push(entry);
}
```

## Boundaries and tensions

This principle does not require an abstraction for each condition. A stable policy can stay local
until the system has another use. A neutral mechanism must not give a bypass for required policy.
Some low-level policy is necessary for fairness, safety, or resource limits. Document that choice.

## Examples

**Positive:** A scheduler supplies queueing and dispatch primitives while a separate strategy
selects priority and fairness rules.

**Misuse:** Authorization rules appear in transport handlers, database helpers, and user interfaces.
One role change requires inconsistent edits across all three.

**Athena/agent workflow:** A coordinator decides which independent tasks may run in parallel. The
delegation mechanism starts, monitors, and collects workers without new scope policy.

## Related principles

- [P016 Separation of Concerns](p016-separation-of-concerns.md)
- [P018 Information Hiding](p018-information-hiding.md)
- [P019 Explicit Contracts](p019-explicit-contracts.md)
- [P078 Single Source of Truth](p078-single-source-of-truth.md)
- [P084 Prefer Local Reasoning](p084-prefer-local-reasoning.md)

## References

### Origin/history

- [Policy/mechanism separation in Hydra](https://doi.org/10.1145/1067629.806531)
  is the 1975 primary paper that defines the principle for schedules, memory pages, and protection.

### Current guidance

- [Linux Integrity Policy Enforcement](https://www.kernel.org/doc/html/latest/security/ipe.html)
  documents a contemporary kernel design that separates integrity measurement from local
  enforcement policies.

### Further reading

- [The Protection of Information in Computer Systems](https://www.cs.virginia.edu/~evans/cs551/saltzer/)
  supplies related foundational guidance on Complete Mediation, least privilege, and economical
  security mechanisms.

[Back to the engineering principles catalog](../README.md#p077)
