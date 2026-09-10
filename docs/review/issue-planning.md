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
| Canonical plan | One authenticated actor-owned `<!-- HomericIntelligence:plan-issue -->` comment. It owns the latest author-event carrier. | When requested, `plan-issue` can create it when absent or update that same comment. |
| Plan review | One authenticated actor-owned `<!-- HomericIntelligence:issue-review -->` comment. It owns the complete current state carrier. | When requested without `--report-only`, `issue-review` can create it when absent or update that same comment. |
| Finalized epoch | One sealed `R`, `P`, and `V` identity in the issue body. | `finalize-plan` can replace that body once. After exact readback, it can remove its two sealed comments. |
| Missing or ambiguous plan | A coverage gap or identity conflict, never a favorable plan. | Withhold the write and return the prepared artifact. |

Author and reviewer are logical roles. The same authenticated actor can perform both roles. The two
carriers stay in the two comments above. They do not authorize a third comment.

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

### Shared marker migration

New planning artifacts use the `HomericIntelligence` markers in the table above. During migration,
resolve one existing actor-owned artifact through exactly one marker from its role's alias set:

| Role | Current marker | Read-only legacy aliases |
| --- | --- | --- |
| Plan | `<!-- HomericIntelligence:plan-issue -->` | `<!-- hephaestus-plan:canonical -->`, `<!-- athena:plan-issue -->` |
| Review | `<!-- HomericIntelligence:issue-review -->` | `<!-- hephaestus-plan-review:canonical -->`, `<!-- athena:issue-review -->` |

Count all aliases for one role together. More than one qualifying alias in one comment or across
comments is an identity conflict, even when the aliases differ. An unambiguous actor-owned legacy
artifact can be updated in place, but its replacement must use only the current marker. Do not
publish a legacy marker. Do not put current and legacy aliases in the same comment.

A single actor-owned current or legacy marker without a carrier is an active unversioned artifact.
Only an explicit `legacy_import` in `issue_exchange.py prepare-review` can adopt an active
unversioned plan or review. It must make a new version-1 round-1 assessment. When the review comment
exists, update that comment. Do not infer a finding, author answer, closure, or `GO` from legacy
prose. An invalid or unsupported carrier is malformed. It is not a legacy artifact. A version-1
round-1 `GO` can bind an unchanged unversioned plan. Preserve a valid finalized legacy epoch without
modification.

A comment with a qualifying plan marker and a qualifying review marker is an identity conflict. Do
not select, update, delete, or finalize that comment.

### Semantic-marker rule

Treat a marker as an artifact identity only when its exact Hypertext Markup Language (HTML) comment
is the complete top-level Markdown line in a comment. Use
`<!-- HomericIntelligence:plan-issue -->` for a plan. Use
`<!-- HomericIntelligence:issue-review -->` for a review. The marker can occur after a heading, prose,
or blank line when it remains a complete top-level Markdown line. Accept a line feed (LF) or carriage
return and line feed (CRLF) line ending. Do not trim, normalize, or move surrounding prose or Markdown
syntax to create a match. Do not treat marker text as an artifact when it occurs in one of these
locations:

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
- the SHA-256 digest of the exact visible plan bytes before the carrier;
- the SHA-256 digest of the complete comment body; and
- the plan-source token that hashes the comment ID and complete-body digest.

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

## Executable carriers

Use [`issue_exchange.py`](../../skills/review-exchange/SKILL.md) as the only issue-exchange parser and
state-transition mechanism. Normalize one current issue snapshot and run `inspect`. Use its
`state_sha256` and `next_action` to select the next permitted operation. Do not edit or reinterpret a
carrier.

The snapshot producer must exhaust the provider's bounded comment pagination. It must include all
top-level comments and set `comments_complete` to `true`. If the host cannot prove complete comment
coverage, withhold plan preparation, review preparation, publication verification, and
finalization.

The plan comment contains visible plan content and exactly one final `author-event` carrier. The
review comment contains visible review content and exactly one final `state` carrier. The visible
review content binds the current plan-source token. A wrong-kind, foreign, repeated, malformed,
stale, or mismatched carrier withholds the operation and routes the exchange to the reported next
action.

For each plan or review publication:

1. Run `inspect` and the applicable `prepare-plan` or `prepare-review` command.
2. For a read-only invocation, return the prepared result and stop.
3. Before a write, get a fresh normalized snapshot and prepare the operation again.
4. Require the same precondition and exact operation.
5. Make only the returned `create` or `update` operation.
6. Read the issue again and run `verify-publication`.
7. If the result is `verified`, stop for the next action.
8. If the write or readback result is indeterminate, report `unknown_outcome`. Do not retry.

Preserve the prepared operation and available receipt evidence for an `unknown_outcome`. Do not
invoke the other logical role recursively.

## Plan content

Use this content in a canonical plan:

1. Record architecture alignment and relevant guidance or ADRs.
2. Map each acceptance criterion to a step.
3. Record concrete module, file, interface, and ownership changes.
4. Specify behavior-first tests and runnable validation commands.
5. Record applicable error, boundary, security, migration, rollout, and rollback considerations.
6. Record unresolved decisions, assumptions, and dependencies.

Declare each plan target as one `kind:value` item. The supported kinds are `path`, `module`,
`interface`, `workflow`, `dependency`, `migration`, and `command`. This canonical set defines the
scope for the exchange. Plan byte count does not define scope. On a continuation, give a
`scope_change_reason` if and only if this set changes.

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

Create or update exactly one actor-owned structured review comment only if all these conditions are
true:

- The user requested publication.
- The invocation does not use `--report-only`.
- The pre-publication identity comparison succeeded.
- A safe forge capability is available.

On the first round, create the canonical review comment only when it is absent. On each continuation,
revalidate identity and update that same comment. Do not create a second review marker. Publish the
comment also when no actionable finding remains. Record these items in the visible content:

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

## Bounded review exchange

Use the [bounded exchange](common.md#bounded-review-exchange) for each issue-plan review. Keep the
current plan and review comments as the only durable exchange artifacts. The plan writes an author
event. The review writes complete current state. Each later turn updates the same comment for its
role.

The author must answer every active required finding. The reviewer must reconcile every prior
finding before it adds a finding. One reviewer assessment increments the round count. An author
response does not. After round 5, an unresolved exchange requires a human decision. Do not make a
sixth reviewer assessment.

Each role must stop when `inspect.next_action` names the other role, finalization, or a human
decision. A verified plan update stops for reviewer assessment. A verified review update stops for
an author response, finalization, or a human decision. Do not call the other skill automatically.

An authoritative decision uses `prepare-review` with a `human_decision` event. The authority receipt
must resolve to one exact live noncanonical issue comment whose normalized author has repository
authority. The helper binds the decision to the current state and finding. It does not increase the
review round. A risk decision can accept only a recorded `risk_acceptance` request. A closure
selection can change only an active closure condition, and it cannot start round 6.

A requirements reframe is a two-step exchange on the retained comments. First, `plan-issue` uses
`prepare-plan` with a `reframe` event, the exact old retained v1 state, a live authority
receipt, and the new declared targets. It updates the same plan comment. After exact readback,
`issue-review` uses `prepare-review` with the same old state, authority receipt, and targets. It
updates the same review comment with round 1 of the new exchange. The new state stores
`supersession_authority_receipt`, cites the old state digest, and starts with a new exchange and
requirements identity. Revalidate the receipt in both preparation steps, after publication, during
inspection, and before finalization. If either write has an uncertain result, stop. Do not create a
replacement comment or continue the second step. A reframe can supersede any retained v1
phase, including `complete`. Normal events cannot continue a complete exchange.

For legacy adoption, give the helper only the exact current unversioned plan and optional review in
the normalized snapshot. Do not infer state from edit history or other prose. Treat a missing or
malformed plan as a coverage gap. Treat a foreign, multiple, ambiguous, or unverifiable marker as an
identity conflict and request a human decision.

## Finalized planning epochs

After one reviewed planning epoch, use `finalize-plan` as the bounded terminal materialization step. It
does not plan, review, implement, change labels, or change the issue workflow state. The issue
requirements remain the source of intent. The actor-owned canonical plan supplies architecture and
implementation detail. The actor-owned review supplies the exact verdict and residual risk.

Use only `issue_exchange.py verify-finalize` to parse terminal state and calculate or verify
`R/P/V/F`. Finalization does not run `inspect`, `prepare-plan`, `prepare-review`, or
`verify-publication`. It does not perform another review.

Accept exactly one current plan and one current review. The authenticated actor must own both
artifacts. The plan and review must be different comments. `P` and `V` must identify different
comment IDs. Bind both artifacts to the same issue-requirements identity. Require an exact `GO`.
Reject an unresolved `critical`, `major`, or other `required` finding.

Before you draft the finalized body, record these values:

- `R`: the canonical digest of the issue ID, title, original body, and acceptance criteria;
- `P`: the SHA-256 plan-source token over the plan-comment ID and its complete-body digest; and
- `V`: the SHA-256 review-source token over the review-comment ID and its complete-body digest.

The review must bind the issue, `R`, plan-comment ID, exact visible-plan digest, and `P`. The current
plan author-event must equal the last accepted author response in the terminal ledger. For a
round-1 `GO`, it must equal the initial plan event that the first assessment binds. Reject an input
that is missing, foreign, repeated, malformed, stale, mismatched, unverified, conditional, or
`NO-GO`. Fail closed. Do not create or adopt replacement comments.

Give `verify-finalize` candidate content without a finalization marker. Accept only a `ready` result
with current matching `R/P/V`, exact `GO`, a terminal ledger, complete coverage, and authority
receipts for each accepted risk. Use the returned body and operation without modification.

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
`<!-- HomericIntelligence:finalize-plan R=<R> P=<P> V=<V> F=<F> -->`. Compute `F` from a
canonical body representation. In that representation, use the literal `<F>` placeholder as the
marker's `F` value. This prevents self-reference. Immediately before publication, resolve each source
identity, actor, marker, and `GO` binding again. Update the issue body exactly once. Then, read the body
again and call the readback form of `verify-finalize` with the snapshot and prepared result. Only a
`verified` result supplies a deletion allowlist. Only after successful readback, re-read the exact actor-owned plan
and review comments recorded in `P` and `V`. Verify each comment's ID, actor, marker, and digest. Only
then, delete only the listed comments. If a value changes, do not delete the comment. If a timeout, indeterminate
response, or body readback mismatch occurs, treat the outcome as unknown. Do not retry. If a deletion
result is uncertain, leave the finalized body in place. Report partial cleanup. Do not retry or
compensate.

For read-only migration, an exact legacy
`<!-- athena:finalize-plan R=<R> P=<P> V=<V> F=<F> -->` marker identifies an existing sealed epoch.
New finalizations write only the `HomericIntelligence` marker. Do not write both marker versions in one
body.

If an intact marker has a valid `F`, valid source identities, and no sealed comments, treat a second
finalization as idempotent. Report `no_change`. Do not duplicate the content. If a sealed comment
remains, report `partial_cleanup`. Do not delete it again. A later material edit does not by itself
authorize a new exchange when it keeps a stale finalization marker. After cleanup, an authoritative
person can replace the sealed body with clean new requirements and remove the obsolete marker. The
next inspection then starts a new round-1 epoch. Do not treat generated plan text or sealed
provenance as a new requirement.
