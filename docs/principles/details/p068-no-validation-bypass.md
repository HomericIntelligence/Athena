# P068 — No Validation Bypass

## Definition

Do not disable, evade, or misreport a type check, lint rule, compiler warning, security control, CI
gate, authorization check, or runtime validator merely because it exposes a problem. Fix the cause
or use a narrowly justified exception through the repository's authorized process.

**Aliases:** no gate bypass; preserve validation integrity.

## Provenance

**Classification:** Athena synthesis.

No single historical origin is claimed. The rule combines secure-development verification,
defense-in-depth, and protected-branch practice into a clear contribution constraint.

## Decision rule

When validation blocks a change, treat the result as evidence to investigate. Do not reduce the
control's coverage or enforcement unless the control is demonstrably wrong and an authorized,
reviewable correction or exception preserves the intended protection.

## How to apply

- Reproduce the validation result and identify the requirement the control enforces.
- Correct the implementation, configuration, dependency, or test that violates that requirement.
- If the rule is defective, change it through its normal ownership and review process.
- Keep unavoidable suppressions local, explained, reviewable, and removable when practical.
- Report checks that did not run or were skipped; never present absence of failure as success.

## Boundaries and tensions

Validation mechanisms can produce false positives, conflict with a new accepted requirement, or be
temporarily unavailable. Correcting the mechanism is not bypass when the protection remains
effective and the change follows repository policy. An emergency path is valid only when that path
already exists, preserves required safeguards, and records the exception. Administrative ability to
bypass a gate is not authorization to do so.

## Examples

**Positive:** A linter exposes an unsafe shell construction. The command is rewritten safely and the
rule remains enabled.

**Misuse:** A pull request adds a broad suppression, disables a required check, or marks it optional
because fixing the reported defect would delay merging.

**Athena/agent workflow:** When `just all` fails, the agent investigates and reports the real result;
it never uses `--no-verify`, edits expected output, or claims a narrower passing command is the full
gate.

## Related principles

- [P020 Executable Architecture](p020-executable-architecture.md)
- [P054 Defense in Depth](p054-defense-in-depth.md)
- [P065 Verify Before Claiming Completion](p065-verify-before-claiming-completion.md)
- [P067 No Test Cheating](p067-no-test-cheating.md)
- [P072 Technical Evidence Over Preference](p072-technical-evidence-over-preference.md)

## References

### Origin/history

- [NIST SP 800-218, Secure Software Development Framework 1.1](https://doi.org/10.6028/NIST.SP.800-218)
  consolidates established secure review, analysis, and testing practices; no singular origin is
  asserted for Athena's prohibition.

### Current guidance

- [GitHub: About protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
  documents enforceable review and status-check gates as well as explicit bypass controls.
- [NIST SSDF 1.1](https://csrc.nist.gov/pubs/sp/800/218/final) requires verification of human-
  readable and executable code and correction of identified vulnerabilities before release.

### Further reading

- [OWASP Application Security Verification Standard](https://owasp.org/www-project-application-security-verification-standard/)
  provides a maintained basis for security verification requirements rather than ad hoc gate
  removal.

[Back to the engineering principles catalog](../README.md#p068)
