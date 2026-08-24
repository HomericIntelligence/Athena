# P061 — Separate Decision from High-Impact Execution

## Definition

Separate deciding that a high-impact action is appropriate from the mechanism that performs it.
At the execution boundary, independently recheck authorization, scope, target, parameters, and any
required approval before causing a destructive, privileged, persistent, financial, deployment,
administrative, or externally visible effect.

**Aliases:** decision/execution separation; execution-time authorization; two-stage action.

## Provenance

**Classification:** Athena synthesis.

No single historical source for this exact formulation is established. It combines established
separation-of-duties controls, transaction-authorization practice, and current human-AI oversight
guidance. It is deliberately narrower than requiring two people for every operation.

## Decision rule

The component or agent that proposes a high-impact action must not treat that proposal as sufficient
authority to execute it. Immediately before execution, resolve the exact action and validate its
authority and safeguards against current state.

## How to apply

- Produce a reviewable action description before invoking the side effect.
- Bind validation to the resolved target, operation, parameters, identity, and current revision.
- Keep planning and dry-run phases free of the high-impact capability when practical.
- Detect changes between decision and execution; revalidate rather than relying on stale state.
- Record the actor, authorization basis, action, and result when an audit trail is appropriate.

## Boundaries and tensions

This principle does not require a second person or repeated confirmation for every reversible action.
An already-authorized, scoped operation may proceed after execution-time validation unless
[P062 Human Approval](p062-human-approval-for-irreversible-or-high-risk-actions.md) or repository
policy requires another gate. For especially sensitive workflows,
[P052 Separation of Duties](p052-separation-of-duties.md) may require distinct actors. The control
must not become a ceremonial click that presents incomplete or stale action details.

## Examples

**Positive:** A deployment planner produces an immutable release digest and target environment. The
deployment step rechecks the digest, target, caller authority, required checks, and approval before
changing production.

**Misuse:** An agent decides early in a long session to delete a resource, then executes a stored
command after the target and repository state have changed.

**Athena/agent workflow:** A skill may analyze a proposed GitHub mutation without write authority.
The executor resolves the repository and issue or pull request again and checks current authorization
immediately before making the external change.

## Related principles

- [P052 Separation of Duties](p052-separation-of-duties.md)
- [P058 Bounded Agent Authority](p058-bounded-agent-authority.md)
- [P062 Human Approval for Irreversible or High-Risk Actions](p062-human-approval-for-irreversible-or-high-risk-actions.md)
- [P083 Irreversible Actions Last](p083-irreversible-actions-last.md)

## References

### Origin/history

- [NIST SP 800-53 Rev. 5, control AC-5](https://doi.org/10.6028/NIST.SP.800-53r5) establishes
  separation of duties as a security control; it is a foundation for, but not the complete source
  of, this Athena formulation.

### Current guidance

- [OWASP Transaction Authorization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Transaction_Authorization_Cheat_Sheet.html)
  requires significant transaction data to be visible to the authorizer and protects the sequence
  between authorization and execution.
- [NIST AI RMF 1.0](https://doi.org/10.6028/NIST.AI.100-1) calls for clearly differentiated roles,
  responsibilities, and oversight in human-AI configurations.

### Further reading

- [OWASP LLM06:2025 Excessive Agency](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/)
  describes transactional safeguards and independent approval for high-impact agent actions.

[Back to the engineering principles catalog](../README.md#p061)
