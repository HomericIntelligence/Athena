# Issue planning and issue review

**Why:** Use one current plan that the authenticated actor owns. This prevents a stale, foreign, or
ambiguous issue comment from controlling implementation. The issue remains the requirements source.
A plan proposes work. It does not authorize implementation, merge, or another forge change.

Use the [ASD-STE100 technical-English policy](../../skills/TECHNICAL_ENGLISH.md) for all technical prose and review
output.

## Principle routing

For plan scope and architecture, apply [P001](../principles/README.md#p001),
[P002](../principles/README.md#p002), [P008](../principles/README.md#p008),
[P010](../principles/README.md#p010), [P012](../principles/README.md#p012),
[P015](../principles/README.md#p015), [P063](../principles/README.md#p063),
[P064](../principles/README.md#p064), and [P074](../principles/README.md#p074).

For artifact identity, publication, and cleanup, apply [P019](../principles/README.md#p019),
[P033](../principles/README.md#p033), [P044](../principles/README.md#p044),
[P059](../principles/README.md#p059), [P061](../principles/README.md#p061),
[P062](../principles/README.md#p062), [P065](../principles/README.md#p065),
[P066](../principles/README.md#p066), and [P083](../principles/README.md#p083).

For plan review, also apply [P069](../principles/README.md#p069),
[P071](../principles/README.md#p071), and
[P072](../principles/README.md#p072) for proportionate independence and evidence-based disposition.

## At a glance

| Artifact | Owner and purpose | Write boundary |
| --- | --- | --- |
| Canonical plan | One authenticated actor-owned `<!-- athena:plan-issue -->` comment. | When requested, `plan-issue` can create or update it. |
| Plan review | One authenticated actor-owned `<!-- athena:issue-review -->` comment. | When requested without `--report-only`, `issue-review` can publish it. |
| Finalized epoch | One sealed `R`, `P`, and `V` identity in the issue body. | `finalize-plan` can replace that body once. After exact readback, it can remove its two sealed comments. |
| Missing or ambiguous plan | A coverage gap or identity conflict, never a favorable plan. | Withhold the write and return the prepared artifact. |

## Canonical plan identity

Before you plan, review, or publish, use this sequence:

1. Enumerate each current issue comment.
2. Apply the semantic-marker rule to the plan and review markers.
3. Apply this rule before a decision about count, ownership, absence, digest, drift, creation, update,
   or publication.
4. Accept the plan marker only if it occurs exactly once in one comment that the authenticated actor
   wrote.

If a marker is foreign, repeated, or has an unverifiable author, treat it as an ownership conflict.
In an ownership conflict:

- Do not create a second marker.
- Do not adopt or overwrite foreign content.
- Do not publish from ambiguous content.
- Preserve issue bodies and comments from other authors.
- Request human direction.

### Semantic-marker rule

Treat a marker as an artifact identity only when its exact Hypertext Markup Language (HTML) comment
is the complete top-level Markdown line in a comment. Use `<!-- athena:plan-issue -->` for a plan. Use
`<!-- athena:issue-review -->` for a review. Accept a line feed (LF) or carriage return and line feed
(CRLF) line ending. Do not trim surrounding prose or Markdown syntax to create a match. Do not treat
marker text as an artifact when it occurs in one of these locations:

- prose;
- inline code;
- a blockquote;
- a list item;
- fenced code; or
- indented code.

Treat two qualifying lines in one comment as a repeated-marker conflict. Treat qualifying lines in
different comments as a multiple-comment conflict. Apply this rule each time you resolve or publish
an artifact identity. Do not let an ignored text reference change absence, ownership, content digest,
or a pre-write drift comparison.

If the marker is absent, `plan-issue` can create one after its scope and identity checks. If
`issue-review` verifies that the marker is absent, record a coverage gap. Do not invent a plan. Do not
treat a foreign or multiple marker as an absent marker.

For a valid plan, record these items:

- the resolved issue identifier (ID) or uniform resource locator (URL);
- the digest of the title, body, and acceptance criteria;
- the authenticated actor;
- the plan-comment ID or URL; and
- the plan-content digest.

For an absent plan, record the issue identity and requirements digest. Also record the verified
`plan: absent` value. Immediately before an update or review publication, resolve the applicable
identity again. Compare each field, including absence. Use the failure actions below if one of these
conditions occurs:

- The requirements or plan content changed.
- The marker became foreign or multiple.
- You cannot verify the identity.

Failure actions:

1. Stop the write.
2. Return the prepared draft or review.

## Plan content

Use this content in a canonical plan:

1. Record architecture alignment and relevant guidance or ADRs.
2. Map each acceptance criterion to a step.
3. Record concrete module, file, interface, and ownership changes.
4. Specify behavior-first tests and runnable validation commands.
5. Record applicable error, boundary, security, migration, rollout, and rollback considerations.
6. Record unresolved decisions, assumptions, and dependencies.

Run `advise` before you draft the plan. In planning mode, `advise` can use the existing checkout as
best-effort evidence without upstream synchronization. Report its revision, trust limits, and freshness
limits. If it returns no guidance, report that explicit result. Continue the planning work. Include
only current requirements. Do not add speculative features, unrelated refactors, or generic framework
layers without a demonstrated consumer. If the plan adds a new module, abstraction, public interface,
dependency, configuration path, or state owner, identify its consumer. Explain why reuse, deletion,
consolidation, or a direct local change is not the simpler complete option.

## Issue review

Review the current canonical plan against the current issue. Use earlier plans and reviews only as
bounded context. Do not use them as a replacement for the current identity. First, report architecture
alignment. Then, verify that each acceptance criterion has all these items:

- a concrete and safe implementation step;
- an architecture boundary; and
- behavior-first validation.

Identify missing requirements, unsafe work, work outside the scope, incorrect paths or boundaries,
unverified assumptions, nondeterministic tests, and unresolved dependencies.

Publish exactly one actor-owned structured review comment only if all these conditions are true:

- The user requested publication.
- The invocation does not use `--report-only`.
- The pre-publication identity comparison succeeded.
- A safe forge capability is available.

Publish the comment also when no actionable finding remains. Record these items in the comment:

- the reviewed plan identity or verified absence;
- the architecture decision;
- requirement coverage;
- findings;
- not-applicable (N/A) sections;
- coverage gaps;
- a concise status; and
- unresolved assumptions.

Treat the review as evidence only. Forge labels, approvals, and human policy remain authoritative. If
the identity is stale or a safe capability is not available:

1. Do not publish.
2. Return the prepared result.

## Bounded revision loop

If a plan changes, review the new canonical plan. Do not collect the complete historical transcript.
Keep only the prior findings and unresolved decisions that you need to verify the new plan. Treat a
missing or malformed plan as a coverage gap. Do not treat it as favorable evidence. Treat a foreign,
multiple, or unverifiable marker as an identity conflict. Do not treat it as a coverage gap.

## Finalized planning epochs

After one reviewed planning epoch, use `finalize-plan` as the bounded terminal materialization step. It
does not plan, review, implement, change labels, or change the issue workflow state. The issue
requirements remain the source of intent. The actor-owned canonical plan supplies architecture and
implementation detail. The actor-owned review supplies the exact disposition and residual risk.

Accept exactly one current plan and one current review. The authenticated actor must own both
artifacts. Bind both artifacts to the same issue-requirements identity. Require an exact `GO`. Reject
an unresolved `critical`, `major`, or other `required` finding.

Before you draft the finalized body, record these values:

- `R`: the canonical digest of the issue ID, title, original body, and acceptance criteria;
- `P`: the plan-comment ID and canonical plan-content digest; and
- `V`: the review-comment ID and review-content digest.

The review must embed and exactly agree with the issue, `R`, plan-comment ID, and `P`. Reject an input
that is missing, foreign, repeated, malformed, stale, mismatched, unverified, conditional, or
`NO-GO`. Fail closed. Do not create or adopt replacement comments.

Use this order in the finalized issue body:

1. Explain why the work is necessary.
2. Give the original requirements.
3. If it is useful, give one compact system diagram.
4. Give the architecture and implementation information.
5. Give operations information about validation, rollout, rollback, dependencies, residual risks, and
   decisions outside the scope.
6. Give the provenance.

Preserve the requirements and accepted plan details. Do not create new scope. Do not make a review
suggestion a requirement. After verified publication and cleanup, keep the sealed provenance in the
finalized body.

After verified publication, treat the plan and review comments as intermediate artifacts. Remove them
only with the deletion procedure below.

Put exactly one machine-readable marker in the body:
`<!-- athena:finalize-plan R=<R> P=<P> V=<V> F=<F> -->`. Compute `F` from a
canonical body representation. In that representation, use the literal `<F>` placeholder as the
marker's `F` value. This prevents self-reference. Immediately before publication, resolve each source
identity, actor, marker, and `GO` binding again. Update the issue body exactly once. Then, read the body
again and verify its exact content. Only after successful readback, re-read the exact actor-owned plan
and review comments recorded in `P` and `V`. Verify each comment's ID, actor, marker, and digest. Only
then, delete those comments. If a value changes, do not delete the comment. If a timeout, indeterminate
response, or body readback mismatch occurs, treat the outcome as unknown. Do not retry. If a deletion
result is uncertain, leave the finalized body in place. Report partial cleanup. Do not retry or
compensate.

If an intact marker has a valid `F`, valid source identities, and no sealed comments, treat a second
finalization as idempotent. Report no-change. Do not duplicate the content. If a sealed comment remains,
report partial cleanup. Do not delete it again. If a person later makes a material edit, invalidate
that epoch. Start a new requirements state. Complete `plan-issue` and `issue-review` again. Do not let
`plan-issue` or `issue-review` treat generated plan text or sealed provenance as a new requirement.
