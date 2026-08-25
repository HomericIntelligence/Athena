# Decision and delivery

## Why

A review verdict is evidence. It does not expand the forge scope. Immediately before one scoped
publication, bind the exact artifact again. This check prevents the review from adding a comment or
automation to a later artifact. It also prevents approval of a later artifact.

Use Athena's [ASD-STE100 writing policy](../../../docs/technical-english.md) for all technical prose
and review output.

```text
[complete review] -> [verdict] -> [rebind exact artifact]
                                        |
                     [one comment-only batch, when requested]
                                        |
                [optional separate auto-merge opt-in after GO]
```

## Engineering principle routes

- [P037 Idempotency Before Retry](../../../docs/principles/README.md#p037) and
  [P044 Atomicity Where Possible](../../../docs/principles/README.md#p044) require one bound atomic
  comment batch when the forge supports it. They prohibit a blind retry after a failed or indeterminate
  write.
- [P050 Least Privilege](../../../docs/principles/README.md#p050),
  [P051 Complete Mediation](../../../docs/principles/README.md#p051),
  [P052 Separation of Duties](../../../docs/principles/README.md#p052), and
  [P058 Bounded Agent Authority](../../../docs/principles/README.md#p058) keep the review, publication,
  approval, and merge capabilities separate. They limit these capabilities to the selected profile and
  requested task.
- [P061 Separate Decision from High-Impact Execution](../../../docs/principles/README.md#p061),
  [P062 Human Approval for Irreversible or High-Risk Actions](../../../docs/principles/README.md#p062),
  and [P083 Irreversible Actions Last](../../../docs/principles/README.md#p083) require a new authority
  and identity check immediately before a requested write or guarded auto-merge opt-in. If the user
  already gave specific authorization, do not request the same approval again.
- [P065 Verify Before Claiming Completion](../../../docs/principles/README.md#p065) and
  [P068 No Validation Bypass](../../../docs/principles/README.md#p068) prohibit a favorable verdict,
  successful-publication claim, or automation state from stale, incomplete, bypassed, or unverified
  evidence.

## Decision

For a default or continuous-integration-free (CI-free) normal report, calculate the findings and
score. Then, emit exactly one terminal verdict. For the prevalidated profile, emit only its structured
audit. Do not emit a verdict, scorecard, publication, or auto-merge state. GitLab can report a verdict.
This skill must not enable GitLab auto-merge.

| Verdict | Required conditions |
| --- | --- |
| **GO** | Use only for the default profile. Require grade A (93–100). Require aligned architecture or an evidenced intentional change. Require zero `required` findings. Require complete applicable source, scope, requirements, language, and validation coverage. Require all host-selected local checks to pass on the reviewed head. |
| **CONDITIONAL GO** | Require architecture to pass. Require no open `required` source finding. Require a score of at least B. Use when a remediable review condition remains. Examples include incomplete source, scope, requirement, language, or validation coverage; a local validation gap; or deliberately limited CI-free evidence. State each condition. |
| **NO-GO** | Use for a score below B, a `required` finding, a material or unexplained architecture violation, or failed required local validation. Also use it for an invalid, stale, or drifted identity, scope, requirement, path, or current-head binding. |

`--report-only` can report `GO`. It records `auto_merge: withheld (read-only)`. Without
`--enable-auto-merge-on-go`, a `GO` records `auto_merge: withheld (not requested)`. For
`CONDITIONAL GO`, `NO-GO`, CI-free, prevalidated, and GitLab, record `auto_merge: not-eligible` with
the blocker.

## Guarded GitHub auto-merge

Enable auto-merge only when the user directly requests `--enable-auto-merge-on-go`. Apply this option
only to an exact eligible default-profile GitHub `GO`. Before you apply it, verify each requested
comment batch. This option does not permit a direct merge, retry, approval, label, bypass, or policy
change.

1. Resolve these values again:
   - canonical host;
   - repository;
   - pull request (PR) number and node ID;
   - `OPEN` and non-draft state;
   - target;
   - base and head object identifiers (OIDs);
   - both lenses;
   - scope digest;
   - linked-requirements digest;
   - path manifest;
   - all effective pre-admission gates; and
   - required queue route.
2. If a value changed or a binding is missing, withhold auto-merge.
3. If a gate failed or is pending, withhold auto-merge.
4. If the author or reviewer changed, withhold auto-merge.
5. If a required thread is unresolved, withhold auto-merge.
6. If comment publication failed or is indeterminate, withhold auto-merge.
7. Require an authenticated capability that binds the canonical target and can enable normal
   auto-merge without administrator bypass.
8. Use the one repository-supported method that the capability returns.
9. Do not select, guess, or change the method.
10. If the repository requires a merge queue, require a separate exact-head queue-admission capability.
11. Do not use normal auto-merge as a queue-admission proxy.
12. Invoke exactly one bound operation: enable auto-merge with the retained PR node ID and
    `expectedHeadOid`, or use queue admission with the same target and head.
13. Do not use ambient repository state, ambient branch state, generic command-line interface (CLI)
    defaults, a direct merge command, fallback mutation, or a retry after a failed or indeterminate
    result.
14. Fetch the exact PR again.
15. Report `enabled` only if auto-merge uses the same node ID, head, and supported method.
16. Report `queue-enqueued` only if its entry binds the same PR, target, and reviewed head.
17. Do not report the PR as merged.

## Normal report

Return, in order:

1. Report the artifact identity, forge, base and head, immutable scope, and path bindings.
2. Report the behind count, files reviewed, linked issue, and acceptance criteria.
3. Report each unbound check as a coverage gap.
4. Report the architecture decision, language routes, surface routes, and not-applicable (N/A) reasons.
5. Report findings from `CRITICAL` through `FYI`.
6. For each finding, report these items:
   - independent `required`, `suggestion`, `nit`, or `FYI` disposition;
   - exact location;
   - observed gap;
   - impact and governing evidence; and
   - proportionate fix.
7. Report the six-dimension scorecard, weighted grade, and terminal verdict.
8. Report commands and their pass or fail state.
9. Report coverage gaps, delivery state, and auto-merge state.
10. After the findings, report brief strengths.

## Comment-only publication

The requested review delivery boundary permits normal publication. Publish comments only. Do not do
any of these actions:

- approve;
- request changes;
- change labels;
- edit an issue;
- resolve a thread;
- rebase;
- push;
- close;
- merge; or
- create a follow-up work item.

If any of these conditions applies, return the complete ready-to-publish batch without a write:

- The invocation is indirect.
- The invocation uses `--report-only`.
- A forge capability is absent.
- There are no findings.
- A bound value changed.

Do not post a clean review.

Before each requested write, fetch the exact open artifact again. Derive the fully qualified write
target only from the retained identity. Revalidate these values:

| Forge/profile | Required rebind |
| --- | --- |
| Default GitHub | Exact repository/PR/base/head plus fresh strict evidence binding and matching scope, linked-requirements, and path-manifest digests. |
| CI-free GitHub | Exact repository/PR/base/head plus the final non-CI source-scope binding. Never call `collect_evidence.py` or a CI endpoint. |
| GitLab | Exact identity, scope, linked requirements, changed paths, and complete base/start/head position tuple. |

If a value changes, withhold the complete set. Start a new review. Use a general summary only for
architecture, scope, coverage, or another cross-cutting point that has no changed-line anchor. Do not
repeat an inline finding in the summary. Publish each independently actionable changed-line finding
exactly once. Put it in one inline comment or discussion on its causal changed line. Do not combine
separate fixes. Do not use a line range instead of the causal line. Do not duplicate the finding at
multiple locations.

### GitHub batch

Send exactly one atomic request to the retained target:

```text
POST /repos/{owner}/{repo}/pulls/{number}/reviews
commit_id = reviewed head OID
event     = COMMENT
body      = non-empty (neutral transport body is valid)
comments  = one entry per anchorable independent finding
```

Put only one verified changed `path`, `side`, causal `line`, and finding body in each comment entry.
Put `commit_id` at the top level. Do not put it in an individual comment. Verify that the returned
review and fetched comments identify these values:

- the target;
- the `COMMENT` or `COMMENTED` event or state;
- the reviewed commit; and
- each expected path, side, line, and body anchor.

If verification fails or is indeterminate, make no additional write. Do not retry. Do not substitute
`gh pr review --comment`.

### GitLab discussions

Create one actionable changed-line discussion for each anchorable independent finding. Put these
exact values in each text position:

- `base_sha`;
- `start_sha`;
- `head_sha`;
- `old_path`;
- `new_path`; and
- `position_type=text`.

For an added or right-side finding, use only `new_line`. For a deletion or left-side finding, use only
`old_line`. For an unchanged line, use both fields. Use an atomic draft or batch when it is available.
If it is not available, bind the artifact again before each ordered discussion. If a value changes,
stop. Retain the created uniform resource locators (URLs). Return the remaining batch. Verify each
returned target, tuple, path, and line field exactly. If the workflow requires an atomic batch and the
forge does not support it, withhold the complete set.

Report review or discussion URLs, publication failures, residual risks, and unverified assumptions
accurately. The forge and its approval policy control labels, acceptance, and merge. Review prose does
not control them.
