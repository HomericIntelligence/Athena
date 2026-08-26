# P077 — Separate Policy from Mechanism

## Definition

**Separate Policy from Mechanism** puts decisions about necessary behavior in policy. The principle
puts execution capabilities in mechanisms. A mechanism supplies stable capabilities. A policy selects
and controls those capabilities for a specified context.

**Aliases:** policy-mechanism separation and separation of policy and mechanism.

## Provenance

**Classification:** principle with source evidence.

Operating-system research used this distinction. The Hydra system put policy and mechanism in
different components for schedules, memory pages, and protection. The Hydra mechanisms let external
policies change. The principle is also applicable to applications, security, work control, storage, and
infrastructure.

## Decision rule

Give a policy boundary with a name to a rule that can change. Keep a neutral mechanism that uses each
selected policy correctly.

## How to apply

- Find decisions that can change. Put these decisions in policy interfaces.
- Give policy inputs, outputs, defaults, and failure behavior an explicit contract.
- Use a narrow interface to supply the policy. Do not put copies of policy branches in the mechanism.
- Do policy-selection tests and mechanism-correctness tests independently.
- If a policy is a security or integrity control, keep enforcement mandatory.

## Diagram

The policy selects an operation. The mechanism does only the selected operation.

```mermaid
flowchart LR
    A["Context"] --> B["Policy decision"]
    B --> C["Selected operation"]
    C --> D["Neutral mechanism"]
    D --> E["Result"]
```

## Language examples

The two examples supply a policy to a stable queue mechanism.

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

An abstraction is not necessary for each condition. Until two components use a stable policy, the
policy can stay local. A neutral mechanism must use the policy.

Some low-level policy is necessary for fairness, safety, or resource limits. Record that decision.

## Examples

**Positive:** A scheduler supplies queueing and dispatch primitives while a different strategy
selects priority and fairness rules.

**Misuse:** Authorization rules occur in transport handlers, database helpers, and user interfaces.
One role change causes edits to all three, and the edits do not agree.

**Athena/agent workflow:** A coordinator selects tasks that can operate independently in parallel. The
delegation mechanism starts, monitors, and collects workers without new scope policy.

## Related principles

- [P016 Separation of Concerns](p016-separation-of-concerns.md)
- [P018 Information Hiding](p018-information-hiding.md)
- [P019 Explicit Contracts](p019-explicit-contracts.md)
- [P078 Single Source of Truth](p078-single-source-of-truth.md)
- [P084 Prefer Local Reasoning](p084-prefer-local-reasoning.md)

## References

### Source information

- [Policy/mechanism separation in Hydra](https://doi.org/10.1145/1067629.806531)
  is the 1975 primary paper that gives the principle for schedules, memory pages, and protection.

### Applicable information

- [Linux Integrity Policy Enforcement](https://www.kernel.org/doc/html/latest/security/ipe.html)
  gives a kernel design with integrity measurement and local enforcement policies in different
  components.

### More information

- [The Protection of Information in Computer Systems](https://www.cs.virginia.edu/~evans/cs551/saltzer/)
  gives guidance on Complete Mediation, least privilege, and simple security mechanisms.

[Back to the engineering principles catalog](../README.md#p077)
