---
name: repo-review
license: BSD-3-Clause
description: Review one repository instance and return actionable findings and judgement.
argument-hint: "[quick|default] [--report-only]"
allowed-tools: [Read, Bash, Grep, Glob, Agent]
---

# Repository review

Apply the [Athena technical-English policy](../TECHNICAL_ENGLISH.md) to all output.

Use this skill when asked for a high-level review of a repository or repository-like component.

## Workflow

1. State what was supplied and what was reviewed.
2. Inspect the available source, configuration, documentation, tests, history, and decisions. If a piece is unavailable, note it in the report.
3. Inspect for defects in these dimensions, to the depth that the available evidence allows:
   - architecture and boundaries;
   - source quality and changeability;
   - tests and verification;
   - security and privacy;
   - reliability and operations;
   - dependency and packaging health;
   - API/CLI and developer experience;
   - project direction and maintenance.
4. Give short findings. For each finding, state the observed problem, impact, and suggested correction.
5. Return GO when the reviewed instance supports the requested standard. Return NO-GO otherwise.
6. Report the evidence limits, not an attestation.
7. If forge action is requested and available, post the review, set the relevant latest verdict label, and request auto-merge for an implementation GO when permitted.

## Modes

`--report-only` returns the report instead of posting it. Without it, publish the report and set the selected label when authority permits. `quick` reports the highest-signal findings. `default` provides the complete review.

## Limits and privacy

Never publish credentials, private keys, personal data, tokens, secret environment variables, or equivalent secret material. Report that they exist without their values. Credential and PII protection remains a requirement. Other checks are goals.

## Output

Return the architecture decision, evidence limits, findings, verdict, and any publication or label actions.
