# Issue planning and issue review

**Why:** One current, actor-owned plan prevents a stale, foreign, or ambiguous issue comment from
driving implementation. The issue remains the requirements source; a plan proposes work but never
authorizes implementation, merge, or forge mutation beyond its explicitly requested comment.

## At a glance

| Artifact | Owner and purpose | Write boundary |
| --- | --- | --- |
| Canonical plan | One authenticated actor-owned `<!-- athena:plan-issue -->` comment. | `plan-issue` may create or update it only with direct authority. |
| Plan review | One authenticated actor-owned `<!-- athena:issue-review -->` comment. | `issue-review` may publish it only with direct authority and without `--report-only`. |
| Missing or ambiguous plan | A coverage gap or identity conflict, never a favorable plan. | Withhold the write and return the prepared artifact. |

## Canonical plan identity

Before planning, reviewing, or publishing, enumerate every current issue comment. Accept the plan
marker only when it occurs exactly once in one comment authored by the authenticated actor. A foreign
marker, multiple occurrences (including repeated markers in one comment), or unverifiable author is
an ownership conflict: do not create a second marker, adopt or overwrite foreign content, or publish
from ambiguity. Preserve issue bodies and comments from other authors and request human direction.

If the marker is absent, `plan-issue` may create one after its authority and identity checks.
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

Run `advise` before drafting; its required knowledge sync must finish first. Include only current
requirements: no speculative features, unrelated refactors, or generic framework layers without a
demonstrated consumer. For a new module, abstraction, public interface, dependency, configuration path,
or state owner, identify that consumer and why reuse, deletion, consolidation, or a direct local change
is not the simpler behaviorally complete option.

## Issue review

Review the current canonical plan against the current issue. Earlier plans and reviews are bounded
context, never a replacement for current identity. Lead with architecture alignment, then verify that
every acceptance criterion has a concrete, safe implementation step, architecture boundary, and
behavior-first validation. Identify missing requirements, unsafe or out-of-scope work, incorrect paths
or boundaries, unverified assumptions, non-deterministic tests, and unresolved dependencies.

With direct authority, no `--report-only`, a successful pre-publication identity comparison, and a safe
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
