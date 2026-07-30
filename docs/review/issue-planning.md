# Issue planning and issue review

`plan-issue` and `issue-review` share this artifact contract. The issue is the
source of requirements. A canonical plan is an implementation proposal; it is
not an authorization to implement, merge, or change forge state beyond the
explicitly requested plan comment.

## Canonical plan artifact

Use one actor-owned issue comment marked `<!-- athena:plan-issue -->` as the
canonical plan. Treat that marker as globally unique: before planning,
reviewing, or publishing, enumerate every current issue comment and accept the
marker only when it occurs exactly once in one comment authored by the
authenticated actor. A marker in a foreign comment, more than one marker
occurrence (including repeated markers in one comment), or an unverifiable
author is an ownership conflict. Do not create a second marker, adopt or
overwrite the foreign plan, or publish a review from an ambiguous marker;
return the prepared artifact and request human direction instead. Preserve
issue bodies and comments from other authors.

If the marker is absent, `plan-issue` may create one canonical comment after
its authority and identity checks. `issue-review` records verified plan absence
as a coverage gap; it must not invent a plan or normalize a foreign or multiple
marker into absence.

For a present valid plan, the canonical planning identity is the resolved forge
issue ID or URL, a digest of the title, body, and acceptance criteria used as
requirements, the authenticated actor, plan-comment ID or URL, and
plan-content digest. Resolve and record that identity before planning or
reviewing. When the marker is absent, an issue review records the issue identity
and requirements digest with the verified `plan: absent` state instead. Before
updating a plan or publishing an issue review, resolve the applicable identity
again and compare every component, including the verified absence state. If the
requirements or plan changed, a marker became foreign or multiple, or an
identity cannot be verified, withhold the write and return the prepared draft or
review as stale.

The canonical plan contains:

1. architecture alignment and relevant guidance or ADRs;
2. an acceptance-criterion-to-step mapping;
3. concrete module, file, interface, and ownership changes;
4. behavior-first tests and runnable validation commands;
5. error, boundary, security, migration, rollout, and rollback considerations
   when applicable; and
6. explicit unresolved decisions, assumptions, and dependencies.

Run `advise` before planning. It must finish its required knowledge sync before
the plan is drafted. Do not create speculative features, unrelated refactors,
or generic framework layers without a demonstrated current consumer.

## Issue review artifact

`issue-review` evaluates the current canonical plan against the current issue.
It may use earlier plan/review comments as bounded context, but it must never
mistake a historical review, conclusion, or stale plan for the current plan.
Bind the review to the canonical-plan identity and perform the pre-publication
identity comparison above when the forge makes those fields available.

The review leads with architecture alignment, then checks that every acceptance
criterion has a concrete, safe implementation and functional verification step.
It identifies missing requirements, unsafe or out-of-scope work, incorrect
paths or boundaries, unverified assumptions, non-deterministic tests, and
unresolved dependencies.

`issue-review` publishes one actor-owned issue comment marked
`<!-- athena:issue-review -->` after an explicit direct user request without
`--report-only`, a successful pre-publication identity comparison, and a forge
capability check. It publishes the structured result even when no actionable
finding remains; a verified absent plan is a published coverage gap, not a
positive assessment. Only a stale identity (including a foreign, multiple, or
otherwise ambiguous marker), or a missing safe forge capability, withholds the
comment. The comment records the reviewed plan identity or verified absence,
findings, coverage gaps, and a concise status. It is evidence only;
target-repository labels, approvals, and human policy remain authoritative.

## Bounded revision loop

When a plan is revised, review the new canonical plan rather than accumulating
the full historical transcript. Retain only the immediately relevant prior
findings and any unresolved decision needed to verify that the new plan fixed
them. A missing or malformed plan is a coverage gap, not a reason to invent a
favorable decision. A foreign, multiple, or unverifiable plan marker is an
identity conflict: reject it and withhold the write rather than treating it as a
coverage gap.
