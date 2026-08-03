# Decision and delivery

## Why

A review verdict is evidence, not a forge-scope expansion. Rebinding immediately before
one scoped publication prevents a correct review from commenting on, approving,
or automating a later artifact.

```text
[complete review] -> [verdict] -> [rebind exact artifact]
                                        |
                     [one comment-only batch, when requested]
                                        |
                [optional separate auto-merge opt-in after GO]
```

## Decision

For default and CI-free normal reports, calculate findings and score before
emitting exactly one terminal verdict. The prevalidated profile emits only its
structured audit; it has no verdict, scorecard, publication, or auto-merge
path. GitLab may report a verdict, but this skill never enables its auto-merge.

| Verdict | Required conditions |
| --- | --- |
| **GO** | Default profile; A (93–100); architecture aligned or evidenced intentional change; zero `required` findings; complete applicable source, scope, requirements, language, and validation coverage; host-selected local checks passing on the reviewed head; and exact-head provider evidence that all effective required pre-admission checks, rulesets, reviews, conversations, deployments, and integration policy gates are satisfied. For GitHub check runs, require strict evidence with `check_evidence.status: head_bound`; a coverage gap or unbound rollup cannot satisfy this condition. The PR is OPEN, non-draft, conflict-free, `behind_count == 0`, and has no existing or planned required unresolved discussion. A merge queue is a route after pre-admission gates, not proof they passed. A GO eligible for auto-merge also needs an authenticated reviewer distinct from the PR author; no approval, bypass, or policy change is implied. |
| **CONDITIONAL GO** | Architecture passes, no `required` source finding is open, and score is at least B, but a remediable condition remains: for example incomplete or unbound required-gate evidence, pending review/deployment/conversation gate, draft, behind branch, provider gap, target-policy-required optional thread, or CI-free's deliberate lack of CI evidence. State every condition; do not enable auto-merge. |
| **NO-GO** | Score below B; any `required` finding; material or unexplained architecture violation; failed, cancelled, stale, skipped, or mismatched required gate; conflict; or invalid/stale/drifted identity, scope, requirement, path, or current-head binding. Do not enable auto-merge. |

`--report-only` may report GO but records `auto_merge: withheld (read-only)`.
Without `--enable-auto-merge-on-go`, a GO records `auto_merge: withheld (not
requested)`. CONDITIONAL GO, NO-GO, CI-free, prevalidated, and GitLab records
`auto_merge: not-eligible` with the blocker.

## Guarded GitHub auto-merge

An explicit direct-user `--enable-auto-merge-on-go` request is the only
auto-merge selection. It applies only to an exact eligible default-profile
GitHub GO, after any requested comment batch is verified; it never permits a
direct merge, retry, approval, label, bypass, or policy change.

1. Re-resolve canonical host, repository, PR number and node ID, OPEN/non-draft
   state, target, base/head OIDs, both lenses, scope digest,
   linked-requirements digest, path manifest, all effective pre-admission gates,
   and required queue route. Withhold on drift, missing binding, gate failure or
   pending state, changed author/reviewer, required unresolved thread, or failed
   or indeterminate comment publication.
2. Require an authenticated capability that binds the canonical target and can
   enable normal auto-merge without administrator bypass. It returns the one
   repository-supported permitted method; never choose, guess, or change one.
   If a merge queue is required, require a separate exact-head queue-admission
   capability instead; normal auto-merge is never a queue-admission proxy.
3. Invoke exactly one bound operation: enable auto-merge with retained PR node
   ID and `expectedHeadOid`, or queue admission with the same target and head.
   Do not use ambient repository or branch state, generic CLI defaults, a direct
   merge command, fallback mutation, or retry after failure or indeterminate
   results.
4. Re-fetch the exact PR. Report `enabled` only when auto-merge is enabled for
   the same node ID, head, and supported method; report `queue-enqueued` only
   when its entry binds the same PR, target, and reviewed head. Never report the
   PR as merged.

## Normal report

Return, in order:

1. Artifact identity, forge, base/head, immutable scope and path bindings,
   behind count, files reviewed, linked issue, acceptance criteria, and each
   unbound check as a coverage gap.
2. Architecture decision, language/surface routes, and N/A reasons.
3. Findings from CRITICAL through FYI. Every finding has independent
   `required`, `suggestion`, `nit`, or `FYI` disposition; exact location;
   observed gap; impact and governing evidence; and proportionate fix.
4. Six-dimension scorecard, weighted grade, terminal verdict, commands and
   pass/fail state, coverage gaps, delivery/auto-merge state, and brief
   strengths after findings.

## Comment-only publication

The requested review delivery boundary permits normal publication. It permits comments only, never approval, request-changes, labels,
issue edits, thread resolution, rebase, push, close, merge, or a follow-up
work-item. Indirect invocation, `--report-only`, absent forge capability, no
findings, or drift returns the complete ready-to-publish batch without a write.
Do not post a clean review.

Before every requested write, re-fetch the exact open artifact and derive the
fully-qualified write target only from the retained identity. Revalidate:

| Forge/profile | Required rebind |
| --- | --- |
| Default GitHub | Exact repository/PR/base/head plus fresh strict evidence binding and matching scope, linked-requirements, and path-manifest digests. |
| CI-free GitHub | Exact repository/PR/base/head plus the final non-CI source-scope binding. Never call `collect_evidence.py` or a CI endpoint. |
| GitLab | Exact identity, scope, linked requirements, changed paths, and complete base/start/head position tuple. |

On any drift, withhold the entire set and restart the review. A general summary
is optional and may cover only architecture, scope, coverage, or another truly
cross-cutting point without a changed-line anchor. It must not repeat an inline
finding. Each independently actionable changed-line finding gets exactly one
inline comment or discussion on its one causal changed line; never combine
separate fixes, use a line range instead of a causal line, or duplicate it at
several locations.

### GitHub batch

Send exactly one atomic request to the retained target:

```text
POST /repos/{owner}/{repo}/pulls/{number}/reviews
commit_id = reviewed head OID
event     = COMMENT
body      = non-empty (neutral transport body is valid)
comments  = one entry per anchorable independent finding
```

Each comment entry contains only one verified changed `path`, `side`, causal
`line`, and finding body; `commit_id` is top-level, never per comment. Verify
the returned review and fetched comments identify the target, `COMMENT` or
`COMMENTED` event/state, reviewed commit, and every expected path, side, line,
and body anchor. On failed or indeterminate verification, make no further write
or retry. Do not substitute `gh pr review --comment`.

### GitLab discussions

Create one actionable changed-line discussion for each anchorable independent
finding. Every text position includes exact `base_sha`, `start_sha`, `head_sha`,
`old_path`, `new_path`, and `position_type=text`; use only `new_line` for an
added/right-side finding, only `old_line` for deletion/left-side, and both for
an unchanged line. Prefer an atomic draft or batch. If unavailable, rebind
before every ordered discussion; stop on drift, retain created URLs, and return
the remaining batch. Verify each returned target, tuple, paths, and line fields
exactly. If an atomic batch is required but unsupported, withhold the whole set.

Report review/discussion URLs, posting failure, residual risks, and unverified
assumptions honestly. The forge and its approval policy—not review prose—own
labels, acceptance, and merging.
