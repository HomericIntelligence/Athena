# Issue planning and issue review

`plan-issue` and `issue-review` share this artifact contract. The issue is the
source of requirements. A canonical plan is an implementation proposal; it is
not an authorization to implement, merge, or change forge state beyond the
explicitly requested plan comment.

## Canonical plan artifact

Use one actor-owned issue comment marked `<!-- athena:plan-issue -->` as the
canonical plan. Before updating it, verify that the marker is in exactly one
comment authored by the authenticated actor. Preserve issue bodies and comments
from other authors. If the marker is absent, create one canonical comment. If
the marker is ambiguous, stop and ask for direction rather than overwriting a
plan.

The canonical planning identity is the resolved forge issue ID or URL, a digest
of the title, body, and acceptance criteria used as requirements, the
authenticated actor, plan-comment ID or URL, and plan-content digest. Resolve
and record that identity before planning or reviewing. Immediately before
updating the plan or publishing an issue review, resolve it again and compare
every component. If the requirements or plan changed, became ambiguous, or
cannot be verified, withhold the write and return the prepared draft or review
as stale.

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
`<!-- athena:issue-review -->` only after an explicit direct user request
without `--report-only` and a successful pre-publication identity comparison.
The comment records the reviewed plan identity, findings, coverage gaps, and a
concise status. It is evidence only; target-repository labels, approvals, and
human policy remain authoritative.

## Bounded revision loop

When a plan is revised, review the new canonical plan rather than accumulating
the full historical transcript. Retain only the immediately relevant prior
findings and any unresolved decision needed to verify that the new plan fixed
them. A missing, malformed, or ambiguous plan is a coverage gap, not a reason to
invent a favorable decision.
