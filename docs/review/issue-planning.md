# Issue planning and issue review

**Why:** One current, actor-owned plan prevents a stale, foreign, or ambiguous issue comment from
driving implementation. The issue remains the requirements source; a plan proposes work but never
scopes implementation, merge, or forge mutation beyond its explicitly requested comment.

## Principle routing

For plan scope and architecture, apply [P001](../principles/README.md#p001),
[P002](../principles/README.md#p002), [P008](../principles/README.md#p008),
[P010](../principles/README.md#p010), [P012](../principles/README.md#p012),
[P015](../principles/README.md#p015), [P063](../principles/README.md#p063),
[P064](../principles/README.md#p064), and [P074](../principles/README.md#p074). For artifact identity,
publication, and cleanup, apply [P019](../principles/README.md#p019),
[P033](../principles/README.md#p033), [P044](../principles/README.md#p044),
[P059](../principles/README.md#p059), [P061](../principles/README.md#p061),
[P062](../principles/README.md#p062), [P065](../principles/README.md#p065),
[P066](../principles/README.md#p066), and [P083](../principles/README.md#p083). Plan review additionally
uses [P069](../principles/README.md#p069), [P071](../principles/README.md#p071), and
[P072](../principles/README.md#p072) for proportionate independence and evidence-based disposition.

## At a glance

| Artifact | Owner and purpose | Write boundary |
| --- | --- | --- |
| Canonical plan | One authenticated actor-owned `<!-- athena:plan-issue -->` comment. | `plan-issue` may create or update it when requested. |
| Plan review | One authenticated actor-owned `<!-- athena:issue-review -->` comment. | `issue-review` may publish it when requested and without `--report-only`. |
| Finalized epoch | One sealed `R/P/V` identity in the issue body. | `finalize-plan` may replace that body once, then remove its two sealed comments after exact readback. |
| Missing or ambiguous plan | A coverage gap or identity conflict, never a favorable plan. | Withhold the write and return the prepared artifact. |

## Canonical plan identity

Before planning, reviewing, or publishing, enumerate every current issue comment. Accept the plan
marker only when it occurs exactly once in one comment authored by the authenticated actor. Apply
the semantic-marker rule below to both the plan and review markers before any count, ownership,
absence, digest, drift, creation, update, or publication decision. A foreign marker, multiple
occurrences (including repeated markers in one comment), or unverifiable author is an ownership
conflict: do not create a second marker, adopt or overwrite foreign content, or publish from
ambiguity. Preserve issue bodies and comments from other authors and request human direction.

### Semantic-marker rule

A marker is an artifact identity only when its exact HTML comment is the complete top-level Markdown
line in a comment: `<!-- athena:plan-issue -->` for a plan or
`<!-- athena:issue-review -->` for a review. The line may end in LF or CRLF; do not trim surrounding
prose or Markdown syntax to manufacture a match. Marker text is not an artifact when it appears in
prose, inline code, a blockquote, a list item, or fenced or indented code. Two qualifying lines in
one comment remain a repeated-marker conflict, and qualifying lines in different comments remain a
multiple-comment conflict. Apply this same rule wherever either artifact identity is resolved or
published; do not let an ignored textual reference change absence, ownership, content digest, or
pre-write drift comparisons.

If the marker is absent, `plan-issue` may create one after its scope and identity checks.
`issue-review` records verified absence as a coverage gap; it must not invent a plan or normalize a
foreign or multiple marker into absence.

For a valid plan, record the resolved issue ID or URL; digest of title, body, and acceptance criteria;
authenticated actor; plan-comment ID or URL; and plan-content digest. For absence, record the issue
identity and requirements digest with verified `plan: absent`. Immediately before an update or review
publication, resolve the applicable identity again and compare every field, including absence. If
requirements or plan content changed, the marker became foreign or multiple, or identity cannot be
verified, withhold the stale write and return the prepared draft or review.

## Plan content

A canonical plan contains:

1. architecture alignment and relevant guidance or ADRs;
2. an acceptance-criterion-to-step mapping;
3. concrete module, file, interface, and ownership changes;
4. behavior-first tests and runnable validation commands;
5. applicable error, boundary, security, migration, rollout, and rollback considerations; and
6. unresolved decisions, assumptions, and dependencies.

Run `advise` before drafting. In planning mode, it may use the existing checkout as best effort
without completing upstream synchronization; report its revision and trust/freshness limits, or its
explicit no-guidance result, and continue planning. Include only current requirements: no speculative
features, unrelated refactors, or generic framework layers without a demonstrated consumer. For a
new module, abstraction, public interface, dependency, configuration path, or state owner, identify
that consumer and why reuse, deletion, consolidation, or a direct local change is not the simpler
behaviorally complete option.

## Issue review

Review the current canonical plan against the current issue. Earlier plans and reviews are bounded
context, never a replacement for current identity. Lead with architecture alignment, then verify that
every acceptance criterion has a concrete, safe implementation step, architecture boundary, and
behavior-first validation. Identify missing requirements, unsafe or out-of-scope work, incorrect paths
or boundaries, unverified assumptions, non-deterministic tests, and unresolved dependencies.

When requested, without `--report-only`, after a successful pre-publication identity comparison, and a safe
forge capability, `issue-review` publishes exactly one actor-owned structured review comment, including
when no actionable finding remains. It records reviewed plan identity or verified absence, architecture
decision, requirement coverage, findings, N/A sections, coverage gaps, concise status, and unresolved
assumptions. It is evidence only; forge labels, approvals, and human policy remain authoritative. A
stale identity or missing safe capability withholds publication and returns the prepared result.

## Bounded revision loop

When a plan changes, review the new canonical plan rather than accumulating the historical transcript.
Keep only immediately relevant prior findings and unresolved decisions needed to confirm the new plan
fixed them. A missing or malformed plan is a coverage gap, not favorable evidence. A foreign, multiple,
or unverifiable marker is an identity conflict, not a coverage gap.

## Finalized planning epochs

`finalize-plan` is the bounded terminal materialization step after one reviewed planning epoch. It
does not plan, review, implement, relabel, or change issue workflow state. The issue requirements
remain the source of intent; the actor-owned canonical plan supplies architecture and implementation
detail; the actor-owned review supplies the exact disposition and residual risk. A finalizer accepts
only exactly one current plan and review owned by the authenticated actor, bound to the same issue
requirements identity, with exact `GO` and no unresolved `critical`, `major`, or other `required`
finding.

Before drafting, record `R` (canonical digest of issue ID, title, original body, and acceptance
criteria), `P` (plan-comment ID and canonical plan-content digest), and `V` (review-comment ID and
review-content digest). The review must embed and exactly agree with the issue, `R`, plan-comment ID,
and `P`. Missing, foreign, repeated, malformed, stale, mismatched, unverified, conditional, or
NO-GO inputs fail closed. The finalizer must not create or adopt replacement comments.

The finalized issue body leads with why and original requirements; then, when useful, one compact
system-shape diagram; architecture and implementation; operations including validation, rollout,
rollback, dependencies, residual risks, and out-of-scope decisions; and provenance. It preserves
requirements and accepted plan details without inventing scope or converting a review suggestion into
a requirement. After verified publication, the plan and review comments are intermediate artifacts and
are removed; the finalized body retains their sealed provenance.

The body carries exactly one machine-readable marker:
`<!-- athena:finalize-plan R=<R> P=<P> V=<V> F=<F> -->`. `F` is computed from a
canonical body representation whose marker `F` value is the literal `<F>` placeholder, preventing
self-reference. Directly before publication, re-resolve every source identity, actor, marker, and GO
binding. A publish performs one issue-body update, followed by exact readback verification. Only then
may it delete the exact actor-owned plan and review comments recorded in `P` and `V`; re-read each
comment's ID, actor, marker, and digest before deletion. Drift prevents that deletion. A timeout,
indeterminate response, or mismatched body readback is an unknown outcome and never authorizes retry;
a deletion uncertainty leaves the finalized body in place and reports partial cleanup without retry or
compensation.

An intact marker whose `F` and source identities verify, with both sealed comments absent, makes
re-finalization idempotent: report no-change rather than duplicate content. A surviving sealed comment
is partial cleanup, not permission to repeat a deletion. A later material human edit invalidates that
epoch and starts a new requirements state, which must complete `plan-issue` and `issue-review` again.
`plan-issue` and `issue-review` must not treat generated plan text or sealed provenance as a new
requirement.
