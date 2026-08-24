# P083 — Irreversible Actions Last

## Definition

**Irreversible Actions Last** means completing validation, reversible preparation, authorization,
and evidence collection before an external side effect that cannot be reliably undone. A multistep
workflow should identify its point of no return and move that point as late as practical.

**Aliases:** none in common use.

## Provenance

**Classification:** Athena synthesis.

No verified source establishes this exact wording. It combines long-standing change-control,
transaction-authorization, staged-release, and rollback practices into one ordering rule for
software and agent workflows.

## Decision rule

Before an irreversible step, ask whether any remaining check or preparation can fail. Perform those
steps first, then revalidate mutable targets and authorization immediately before committing the
exact action.

## How to apply

- Classify steps as read-only, reversible, compensatable, or irreversible.
- Validate inputs and targets before allocating or mutating external state.
- Use previews, staging, backups, canaries, and dry runs when they provide real evidence.
- Bind approval and authorization to the final target and parameters.
- Recheck facts that may have changed during preparation.
- Make the commit step atomic or idempotent where possible.
- Record the outcome and any side effects that cannot be reversed.

## Boundaries and tensions

Some irreversible action may be the required result; the principle delays it rather than forbidding
it. Long preparation can create stale decisions, so the final gate must check mutable state again.
Compensation is not true reversal, and messages, charges, deletions, and public releases should not
be described as reversible when their effects may already have escaped. Emergency paths may be
faster, but still require the authorization defined for that path.

## Examples

**Positive:** A release builds, tests, stages, verifies the target revision, and receives bound
authorization before switching production traffic.

**Misuse:** A checkout charges a payment method before validating inventory and delivery details,
then assumes a refund will erase every consequence.

**Athena/agent workflow:** An agent resolves the repository and issue body, previews the exact
request, verifies authority, and only then creates the externally visible GitHub issue.

## Related principles

- [P021 Evolutionary and Reversible Design](p021-evolutionary-and-reversible-design.md)
- [P061 Separate Decision from High-Impact Execution](p061-separate-decision-from-high-impact-execution.md)
- [P062 Human Approval for Irreversible or High-Risk Actions](p062-human-approval-for-irreversible-or-high-risk-actions.md)
- [P076 Parse, Then Validate, Then Operate](p076-parse-then-validate-then-operate.md)
- [P082 Design for Cancellation](p082-design-for-cancellation.md)

## References

### Origin/history

- No single primary source for the general ordering rule is established; Athena uses a synthesis of
  transaction, change-control, and release-safety practice.

### Current guidance

- [OWASP Transaction Authorization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Transaction_Authorization_Cheat_Sheet.html)
  requires ordered state transitions and a final authorization gate tied to transaction execution.
- [Google SRE Workbook: Canarying Releases](https://sre.google/workbook/canarying-releases/)
  describes staged exposure and evaluation before wider deployment, with rollback retained as a
  practical safety mechanism.

### Further reading

- [NIST SP 800-53 Revision 5](https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final) includes
  configuration change control, impact analysis, authorization, testing, and documentation controls
  for governed changes.

[Back to the engineering principles catalog](../README.md#p083)
