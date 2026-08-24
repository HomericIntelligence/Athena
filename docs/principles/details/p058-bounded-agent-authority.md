# P058 — Bounded Agent Authority

## Definition and aliases

Bounded Agent Authority gives an agent only the repositories, files, tools, commands, destinations,
credentials, actions, iterations, time, and other resources required by its task. Authority comes from
the trusted task and governing policy; confidence, retrieved text, or model output cannot enlarge it.

**Aliases:** least-authority agents, scoped agency, constrained autonomy.

## Provenance

**Classification:** Athena synthesis. It applies established least-privilege and confinement ideas to
tool-using AI agents and adds explicit bounds on autonomy, context, iteration, and resource use. No
single historical source is claimed for the combined formulation.

## Decision rule

Before enabling an agent capability, identify the exact task step that needs it and constrain its
targets, operations, duration, and budget. Deny or escalate operations outside that grant instead of
inferring permission from convenience or from content the agent inspected.

## How to apply

- State the objective, allowed targets, prohibited effects, acceptance criteria, and stopping condition.
- Prefer read-only, path-scoped, destination-scoped, and short-lived capabilities.
- Separate planning or review tools from tools that execute persistent or externally visible changes.
- Bound delegation depth, tool calls, retries, wall time, tokens, cost, and concurrent work.
- Validate proposed actions and parameters at the tool boundary against the original authority.
- Monitor use, revoke access at task completion, and report when the allowed capability is insufficient.

## Boundaries and tensions

Bounded authority does not prohibit autonomous choices inside a well-defined grant, and actions already
authorized by the user and repository contract need no invented approval ceremony. It does prohibit
using data, delegation, or an agent's own plan to create new authority. Bounds that make the stated task
impossible should fail explicitly rather than encourage hidden bypasses or broad fallback credentials.

## Examples

### Positive

A documentation agent can read the repository, edit one documentation subtree, query approved public
sources, and run documentation checks. Its write and network scopes expire with the task.

### Misuse

A review agent receives unrestricted shell, production credentials, email access, and unlimited
iterations because it might discover a future need for them.

### Athena and agent workflows

An Athena coordinator gives each specialist a bounded objective and only the context and capabilities
needed for its partition. A specialist reports a missing permission rather than expanding scope itself.

## Related principles

- [P050 — Least Privilege](./p050-least-privilege.md)
- [P059 — Data Is Not Instruction](./p059-data-is-not-instruction.md)
- [P060 — Constrain Sub-Agents](./p060-constrain-sub-agents.md)
- [P061 — Separate Decision from High-Impact Execution](./p061-separate-decision-from-high-impact-execution.md)
- [P062 — Human Approval for Irreversible or High-Risk Actions](./p062-human-approval-for-irreversible-or-high-risk-actions.md)

## References

### Origin and history

- [Saltzer and Schroeder, *The Protection of Information in Computer Systems*](https://doi.org/10.1109/PROC.1975.9939)
  supplies the least-privilege foundation; the agent-specific resource bounds are a later adaptation.

### Current guidance

- [OWASP LLM08: Excessive Agency](https://genai.owasp.org/llmrisk2023-24/llm08-excessive-agency/)
  identifies excessive functionality, permissions, and autonomy as root causes of damaging agent action.
- [OWASP AI Agent Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html)
  recommends least-privilege tools, sandboxes, action controls, and bounded resource use.

### Further reading

- [NIST AI 600-1, Generative AI Profile](https://doi.org/10.6028/NIST.AI.600-1) provides a current
  cross-sector framework for identifying and managing generative-AI risks across the lifecycle.

[Back to the principles catalog](../README.md#p058)
