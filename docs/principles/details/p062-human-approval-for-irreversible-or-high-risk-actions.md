# P062 — Human Approval for Irreversible or High-Risk Actions

## Definition

Obtain explicit human approval before an otherwise unauthorized action that can delete data, alter
production, change privileges, expose secrets, communicate externally, incur substantial cost, or
create another difficult-to-reverse effect. Approval must identify the material action being
authorized, not merely express general trust in the actor or tool.

**Aliases:** human-in-the-loop approval; confirmation gate; approval-bound execution.

## Provenance

**Classification:** Athena synthesis.

The exact rule is not attributable to one origin. It adapts transaction authorization, safety
interlocks, and current guidance for limiting excessive agent autonomy to repository automation.

## Decision rule

If an action is both high-risk or difficult to reverse and is not already explicitly authorized at
the required specificity, stop before the side effect and obtain approval bound to its target,
scope, and material parameters.

## How to apply

- Classify impact using the real destination, data, privilege, cost, and reversibility.
- Show the approver the exact action and significant parameters in understandable terms.
- Ask again when the target, scope, material parameters, or risk changes after approval.
- Keep approval credentials and execution state protected from substitution or replay.
- Pair approval with technical safeguards; approval alone does not make an unsafe action safe.

## Boundaries and tensions

Do not manufacture redundant prompts. Under Athena's repository contract, scoped constructive Git,
GitHub, and Hephaestus actions already authorized by the user and task do not need a second approval
merely because they are externally visible. Destructive, privilege-changing, production, secret-
exposing, materially costly, or otherwise ungranted high-risk actions still require explicit
approval. Repository policy may impose a stricter gate. Approval never permits an action prohibited
by a higher-priority instruction or security control.

## Examples

**Positive:** Before deleting a production dataset, the system presents the resolved environment,
dataset identifier, retention consequence, and recovery status, then executes only after explicit
approval for those details.

**Misuse:** A generic onboarding checkbox stating that an agent may "manage resources" is treated as
permanent approval for any future deletion or deployment.

**Athena/agent workflow:** A direct request to file a named GitHub issue authorizes that scoped,
constructive external write. Removing a worktree containing uncommitted changes remains approval-
gated because it could destroy data.

## Related principles

- [P050 Least Privilege](p050-least-privilege.md)
- [P058 Bounded Agent Authority](p058-bounded-agent-authority.md)
- [P061 Separate Decision from High-Impact Execution](p061-separate-decision-from-high-impact-execution.md)
- [P083 Irreversible Actions Last](p083-irreversible-actions-last.md)

## References

### Origin/history

- [OWASP Transaction Authorization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Transaction_Authorization_Cheat_Sheet.html)
  documents the established practice of binding authorization to significant transaction data; it
  does not establish a single origin for the broader Athena rule.

### Current guidance

- [OWASP LLM06:2025 Excessive Agency](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/)
  recommends human approval before high-impact agent actions and limiting available extensions and
  permissions.
- [NIST AI RMF 1.0, Appendix C](https://airc.nist.gov/airmf-resources/airmf/appendices/app-c-ai-risk-management-and-human-ai-interaction/)
  explains that human roles and oversight should be defined according to system context and risk.

### Further reading

- [NIST AI RMF Core](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/) provides risk-based
  governance outcomes for assigning and differentiating oversight responsibilities.

[Back to the engineering principles catalog](../README.md#p062)
