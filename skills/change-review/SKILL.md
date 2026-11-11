---
name: change-review
description: Review one change instance. Inspect available input, report the judgement, and proceed without requiring attestation.
allowed-tools: []
---

# Change Review

Apply the [Athena technical-English policy](../TECHNICAL_ENGLISH.md) to all output.

## Activation

Use this skill when asked for a review of a change. The review is an instance review. It does not require source ancestry, a repository, a complete issue, or a chain of authority.

## Workflow

1. Identify what the caller supplied: a diff, directory, patch, plan, issue, or description.
2. Read as much of that material as is available. If part of it is unreadable, missing, or contradictory, note that fact.
3. Look for defects that affect the change's behavior, safety, maintainability, or contract with its callers.
4. Prefer behavior over style. Note where the evidence supports the observation.
5. Judge the reviewed instance as GO or NO-GO.
6. Publish the review. Set the implementation label if this is an implementation review. Otherwise return it to the caller or the invoking system.
7. Report the review, its findings, the evidence limits, the verdict, the label if any, and any forge operation requested.

## Limits and privacy

Never publish credentials, private keys, personal data, tokens, secret environment variables, or equivalent secrets. Report that they exist without their values. Credential and PII protection remains a requirement. Other checks are goals.

## Output

Return a compact summary of:
- what was reviewed;
- what was examined;
- what could not be examined;
- material findings;
- the verdict;
- the publication or delivery result.

## Attribution

Use the [Athena engineering principles](../../docs/principles/README.md) as a broad guide, not as restrictions.
