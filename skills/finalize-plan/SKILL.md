---
name: finalize-plan
license: BSD-3-Clause
description: Materialize one exact, actor-owned, GO-reviewed issue-planning epoch into its implementation-facing issue body. Use after plan-issue and issue-review approve a plan; `--draft` is read-only and every missing, foreign, stale, ambiguous, or unverifiable input fails closed.
argument-hint: "[--draft] ISSUE_NUMBER_OR_URL"
allowed-tools: [Read, Bash, Grep, Glob]
---

# Finalize an approved issue plan

Why: an approved plan should be the readable implementation entry point without
turning review history, suggestions, or a generated body into new requirements.

Use the shared [issue-planning contract](../../docs/review/issue-planning.md),
[review contract](../../docs/review/common.md),
[design-document structure](../../docs/review/design-docs.md),
[language routing](../../docs/review/language-routing.md), and
[behavior-first testing](../../docs/review/behavior-first-testing.md).

## Scope and delivery

`--draft` is read-only. Without it, this skill may replace the resolved issue
body once and, only after exact body readback, delete the two sealed,
actor-owned plan and review comments. It must not update the title, labels,
assignment, milestone, project fields, state, branches, pull requests, or
repository files. The finalized body retains the required provenance after
those intermediate comments are removed.

Use the forge's native issue-body mechanism. If the host cannot authenticate the
actor, enumerate and delete exact comments, read the issue body, compare
identities, or make and read back one exact body update, return a
ready-to-publish draft and identify the capability gap. Never create, adopt,
edit, or replace plan or review comments to make finalization possible.

## Finalized planning epoch

An epoch has these sealed source identities:

- `R`: the canonical digest of the original issue requirements: exact issue ID,
  title, body, and acceptance criteria before finalization;
- `P`: one actor-owned `<!-- athena:plan-issue -->` comment ID and canonical
  plan-content digest; and
- `V`: one actor-owned `<!-- athena:issue-review -->` comment ID and
  review-content digest.

The review must embed and exactly match the same issue, `R`, plan-comment ID,
and `P`. It must have an exact `GO` disposition with no unresolved `critical`,
`major`, or other `required` finding. A conditional, partial, malformed, stale,
foreign, duplicated, absent, or unverifiable artifact is not authorization.

The rendered body records exactly one marker:
`<!-- athena:finalize-plan R=<R> P=<P> V=<V> F=<F> -->`. Define `F` by hashing
the final body after replacing that marker's `F` value with the literal
`<F>` placeholder; do not hash a marker containing its own digest. The marker
lets a host distinguish sealed source identities from the generated body and
verify later readback without recursion.

## Finalize

1. Resolve one exact issue, including node or URL, title, body, state, and
   authenticated actor. Enumerate every current comment before interpreting a
   marker.
2. Resolve exactly one actor-owned plan marker and one actor-owned review marker.
   Compute `R`, `P`, and `V`, then verify the review's embedded bindings and
   clean GO result. Any ownership, multiplicity, binding, disposition, or
   required-finding failure returns no write.
3. Build a compact, lossless synthesis. Lead with **Why** (the preserved
   original problem, outcome, and non-negotiable requirements), then include a
   compact system-shape diagram only when it makes at least three relationships,
   boundaries, or state transitions materially clearer. Follow with architecture
   breakdown, implementation plan, operations, and provenance.
4. Preserve every acceptance criterion, implementation boundary, validation,
   migration or cutover step, rollback condition, dependency, residual risk, and
   out-of-scope decision. Record review suggestions as optional residual context
   unless the reviewed canonical plan already adopted them. Do not invent files,
   commands, requirements, architecture, implementation results, or validation
   evidence; do not copy historical revision transcripts or duplicate the plan
   and review verbatim when a smaller lossless synthesis suffices.
5. Add the finalized marker and compute `F` over its non-self-referential
   canonical representation. In `--draft`, return the complete body, `R/P/V/F`,
   source links, and all withheld-write reasons without invoking a forge write.
6. Immediately before publication, resolve the issue, actor, every comment and
   marker, `R/P/V`, review disposition, and target body again. If any input
   drifted, return the ready-to-publish body as stale; do not write.
7. Publish exactly one issue-body replacement. Read the issue back immediately
   and verify the exact body, marker, `R/P/V`, and `F`. A timeout, indeterminate
   response, or mismatched readback is an unknown outcome: do not retry or make
   another mutation.
8. After successful body readback, re-read each sealed comment by its exact ID,
   actor, marker, and digest, then delete the plan comment and review comment.
   Delete no foreign, replacement, or drifted comment. A failed, timed-out, or
   indeterminate deletion is a partial-cleanup unknown outcome: do not retry,
   compensate, or remove the finalized body; report the surviving identities.

## Re-finalization and restart

If the live body exactly verifies its finalized marker and both sealed comments
are absent, re-running for that epoch returns a documented no-change result. A
surviving sealed comment is partial cleanup, not authorization to retry a prior
deletion. If the marker is absent, malformed, foreign, or its canonical `F` does
not match, the epoch is not valid evidence. A later material human edit is a new
requirements state and must pass a fresh `plan-issue` plus `issue-review` cycle
before another finalization. Do not treat generated plan text or provenance
fields as newly authored requirements.

## Behavior-first verification

Use controlled issue, comment, actor, and forge fixtures to demonstrate:

- one clean GO plan/review epoch preserves requirements and operational details;
- `--draft` returns the body without a forge mutation;
- publish performs one body update, verifies its exact readback, then deletes
  only the two sealed actor-owned comments;
- an unchanged sealed epoch is idempotent; and
- every absent, foreign, duplicate, mismatched, stale, NO-GO, required-finding,
  drift, unsupported-write, timeout, readback-mismatch, or deletion-uncertainty
  case fails before an unsafe mutation or retry.

Assert identities, ordering classes, preservation, mutation count and scope, and
failure-before-write behavior. Do not freeze editorial wording, headings,
paragraph counts, or an example issue body.

## Failed approaches

- Re-finalizing an epoch without a fresh request or a new requirements state.
- Treating generated plan text or sealed provenance fields as newly authored, executable
  requirements.
- Bypassing behavior-first verification for wording checks, or inventing files, commands, or
  validation evidence during synthesis.
- Retrying after a timeout, readback mismatch, or indeterminate deletion instead of reporting the
  unknown outcome.

## Result

Return the issue and actor identities; `R/P/V/F`; GO decision and finding
summary; requirement-preservation map; draft, no-change, published, stale,
partial-cleanup, or unknown-outcome status; body-update receipt, readback
evidence, deleted-comment receipts when present; and every unresolved capability
or residual risk.
