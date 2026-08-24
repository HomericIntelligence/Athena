# P069 — Independent Review for High-Risk Changes

## Definition

Security- or availability-critical changes should receive a risk-appropriate evaluation independent
of their author. The reviewer must be qualified for the affected domain and must examine the actual
change and evidence rather than merely endorsing the author's conclusion.

**Aliases:** independent technical review; qualified second review.

## Provenance

**Classification:** established practice.

Independent software inspection has a documented lineage in Michael Fagan's 1970s work at IBM.
Modern code review and secure-development guidance apply independent, domain-qualified scrutiny
proportionally to risk.

## Decision rule

Before accepting a high-risk change, obtain a review from a qualified evaluator who did not produce
the change and can challenge its assumptions, inspect its evidence, and report findings without
being required to agree with the author.

## How to apply

- Classify risk from the changed trust boundaries, data, concurrency, migration, or operations.
- Route specialized surfaces to reviewers competent in security, privacy, cryptography,
  concurrency, infrastructure, or the relevant domain.
- Give the reviewer the requirements, exact revision, complete diff, tests, and known limitations.
- Keep author and reviewer conclusions distinguishable and resolve material findings explicitly.
- Increase independence and depth as consequence and uncertainty increase.

## Boundaries and tensions

Independent does not necessarily mean human. A separate qualified agent or specialist with a fresh,
bounded review task can satisfy this principle unless repository policy requires a human, Code
Owner, regulated role, or approval count. Automated analysis can support review but rarely supplies
all contextual judgment by itself. A non-author rubber stamp is not independent review, while low-
risk routine work need not acquire heavyweight ceremony.

## Examples

**Positive:** A security specialist who did not author an authorization change reviews the exact
commit, threat boundary, negative tests, and rollout behavior before acceptance.

**Misuse:** A teammate approves cryptographic code without reading it or understanding the primitive,
solely to satisfy an approval count.

**Athena/agent workflow:** A coordinator assigns the completed high-risk diff to a separate review
agent with explicit criteria and no instruction to confirm the implementer's result, then surfaces
unresolved findings to the user.

## Related principles

- [P052 Separation of Duties](p052-separation-of-duties.md)
- [P054 Defense in Depth](p054-defense-in-depth.md)
- [P061 Separate Decision from High-Impact Execution](p061-separate-decision-from-high-impact-execution.md)
- [P065 Verify Before Claiming Completion](p065-verify-before-claiming-completion.md)

## References

### Origin/history

- [Fagan, "Design and Code Inspections to Reduce Errors in Program Development" (1976)](https://doi.org/10.1147/sj.153.0182)
  is a foundational primary account of structured, role-based software inspection.

### Current guidance

- [Google Engineering Practices: What to look for in a code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html)
  directs authors to involve qualified reviewers for complex areas such as security, privacy, and
  concurrency.
- [NIST SSDF 1.1](https://csrc.nist.gov/pubs/sp/800/218/final) includes code review and analysis
  among the practices for finding vulnerabilities before release.

### Further reading

- [OWASP Secure Code Review Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secure_Code_Review_Cheat_Sheet.html)
  explains risk-based manual review and the contextual weaknesses that automated tools can miss.

[Back to the engineering principles catalog](../README.md#p069)
