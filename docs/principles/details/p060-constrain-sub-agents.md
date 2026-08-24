# P060 — Constrain Sub-Agents

## Definition and aliases

Constrain Sub-Agents means that delegation preserves or narrows the parent task's scope and authority.
A child receives only the objective, context, permissions, credentials, tools, and resource budget it
needs. Its output returns as untrusted input for validation, not as an instruction to the parent.

**Aliases:** bounded delegation, capability-safe delegation, constrained multi-agent execution.

## Provenance

**Classification:** Athena synthesis.

It adapts established confinement, least-privilege, and secure delegation ideas to modern multi-agent
workflows. No claim is made that the exact rule originated in the historical confinement literature.

## Decision rule

Delegate only a concrete, bounded partition whose authority is no broader than the parent's. Before
accepting or acting on a child result, verify its provenance, scope, evidence, and requested effects
against the parent contract.

## How to apply

- Give the child an explicit objective, inputs, allowed outputs, constraints, and stopping condition.
- Pass the minimum relevant context; do not copy full histories, secrets, or unrelated customer data.
- Issue narrower, short-lived capabilities instead of inheriting the parent's credentials and tools.
- Bound recursion, fan-out, concurrency, retries, time, tokens, cost, and persistent memory.
- Authenticate inter-agent messages when identity matters and validate their structured contents.
- Review outputs, reconcile shared-state changes, revoke access, and cancel descendants when the task ends.

## Boundaries and tensions

A sub-agent can exercise judgment within its assigned partition; constraint is not micromanagement.
Delegation cannot launder an action the parent is forbidden to perform or expand authority through a
child's recommendation. Agents operated by the same team are not automatically one trust domain.
Concurrent children need explicit file or state ownership so valid actions do not overwrite each other.

## Examples

### Positive

A documentation coordinator assigns one child a fixed set of pages, read-only source research, and a
time budget. The child cannot commit, publish, access credentials, or edit another child's partition.

### Misuse

A parent forwards its full conversation, production token, wildcard filesystem access, and permission
to spawn unlimited descendants for a one-file research task.

### Athena and agent workflows

Each Athena specialist receives an actor-owned deliverable and exact write paths. The coordinator
checks the returned diff and evidence before integrating it and does not execute embedded commands.

## Related principles

- [P050 — Least Privilege](./p050-least-privilege.md)
- [P058 — Bounded Agent Authority](./p058-bounded-agent-authority.md)
- [P059 — Data Is Not Instruction](./p059-data-is-not-instruction.md)
- [P069 — Independent Review for High-Risk Changes](./p069-independent-review-for-high-risk-changes.md)

## References

### Origin and history

- [Lampson, *A Note on the Confinement Problem*](https://doi.org/10.1145/362375.362389) is a
  foundational treatment of confining a program's information effects; it is related background,
  not a direct specification for AI delegation.

### Current guidance

- [OWASP AI Agent Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html)
  recommends context isolation, least privilege, bounded recursion, and validation between agents.
- [OWASP Top 10 for Agentic Applications 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/)
  identifies identity, privilege, context, communication, and cascading-failure risks in agentic systems.

### Further reading

- [NIST AI 600-1, Generative AI Profile](https://doi.org/10.6028/NIST.AI.600-1) supplies a broader
  lifecycle risk-management framework for generative-AI systems and their human oversight.

[Back to the principles catalog](../README.md#p060)
