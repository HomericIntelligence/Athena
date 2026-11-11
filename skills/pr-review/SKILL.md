---
name: pr-review
description: Review one implementation instance. Post the review, set the latest implementation verdict label, and preserve secret and PII protection.
allowed-tools: []
---

# Pull Request Review

Apply the [Athena technical-English policy](../TECHNICAL_ENGLISH.md) to all output.

## Activation

Use this skill when asked to review an implementation, an issue, or a pull request. The review is an instance review. It does not attest to history, source ancestry, publisher authority, dependency trust, requirement identity, or future changes. No missing evidence is a reason to withhold the review.

## Inputs

Use the artifact that is available:
- a pull-request or issue number or URL, when one is known;
- a directory, patch, source tree, issue body, plan, or pasted text;
- links visible in the request, when the caller provides them.

No particular structure, `.git` directory, or metadata file is required.

## Independence and coordinated reviews

A review is independent only when it runs in a fresh context that did not author or author-respond to the reviewed artifact. One authenticated account can produce many independent reviews, because independence comes from the review context, not from the account.

A coordinator may dispatch N independent reviews for one artifact. Each review can return its own report and judgement. An unresolved disagreement or partial review set cannot become a consensus GO.

Exactly one delivery owner acts for each artifact. A delegated review can report findings and never publishes. The coordinator publishes, sets the verdict label, and may request auto-merge after an implementation GO.

A context that already reviewed the artifact is not independent for a later round on that artifact. A later round uses a fresh context.

## Workflow

1. **Identify the reviewed instance.** Say what the review covers and what the caller supplied. If an identifier is unavailable, say so and review what is present.
2. **Inspect the available material.** Read the source or text as far as it is readable. Note unreadable, truncated, missing, translated, generated, or contradictory material.
3. **Examine the behavior.** Prefer behavior tests, call sites, and contracts over private implementation structure. A side effect that did not run is still worth naming.
4. **Find defects.** Group concrete defects by effect on a user, an operator, an agent, or the artifact contract. When a defect is inferred but not observed, say so.
5. **Judge this instance.** State one verdict: GO or NO-GO. A GO means this one reviewed instance satisfies the caller's requested standard. It does not certify repository policy or future changes.
6. **Post the review.** Prefer one exact Markdown comment containing:
   - the reviewed instance;
   - what was examined;
   - what could not be examined;
   - findings;
   - the verdict.
7. **Apply the verdict label.** Use the most recent review to set exactly one:
   - `state:implementation-go` for GO;
   - `state:implementation-no-go` for NO-GO.
   Remove the sibling label in the same operation if both are present.
8. **Request auto-merge if permitted.** For an implementation GO, call `gh pr merge --auto --squash` against the pull request when the forge exposes that capability. A denied or unavailable request is reported, not treated as a failed review.
9. **Return the result.** State the comment location, the applied label, the auto-merge state, and any unexamined evidence.

## Delivery

For a batch of coordinated reviews, use [`scripts/independence.py`](scripts/independence.py) to classify whether the reports are independent and whether the batch reaches GO. Independence belongs to the review context, not the authenticated account. A report made with fresh context that did not author or author-respond is independent.

Use [`scripts/delivery.py`](scripts/delivery.py) to publish the report and apply the selected label. It may:
- comment on a pull request or issue when the target is available;
- otherwise return the report locally;
- apply one target label and remove the sibling label;
- request auto-merge after an implementation GO.

No program in this skill proves a review, authorizes a merge, or rejects a review because the evidence is incomplete.

## Security and privacy

Never publish credentials, private keys, personal data, access tokens, secret environment variables, or equivalent secret material. Report their presence without printing their values. Credential and PII protection remains a requirement. All other checks in this skill are goals to attain rather than gates to pass.

## Result contract

Return a compact report with the reviewed instance, findings, verdict, visible evidence or limits, comment location (or local output), label result, and auto-merge state.

## Attribution

Use the [Athena engineering principles](../../docs/principles/README.md) as a broad guide, not as a gate.
