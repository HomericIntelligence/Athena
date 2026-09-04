# Decision and delivery

## Why

A review verdict is evidence. It does not expand the forge scope. Immediately before one scoped
publication, bind the exact artifact again. This check prevents the review from adding a comment or
automation to a later artifact. It also prevents approval of a later artifact.

Use the [ASD-STE100 technical-English policy](../../TECHNICAL_ENGLISH.md) for all technical prose
and review output.

```text
[complete review] -> [verdict] -> [rebind exact artifact]
                                        |
                 [finding batch or verified GO finalization]
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

For a default or continuous-integration-free (CI-free) normal report, calculate the findings. Then,
calculate the score. Emit exactly one terminal verdict. For the prevalidated profile, emit only its structured
audit. Do not emit a verdict, scorecard, or publication. The prevalidated profile has no auto-merge
workflow. GitLab can report a verdict. This skill must not enable GitLab auto-merge.

| Verdict | Required conditions |
| --- | --- |
| **GO** | Use only for the default profile. Require grade A (93–100). Require aligned architecture or an evidenced intentional change. Require zero `required` findings. Require complete applicable source, scope, requirements, language, and validation coverage. Require all host-selected local checks to pass on the reviewed head. A delivered GO also requires the verified GO-delivery postconditions. |
| **CONDITIONAL GO** | Require architecture to pass. Require no open `required` source finding. Require a score of at least B. Use when a remediable review condition remains. Examples include incomplete source, scope, requirement, language, or validation coverage; a local validation gap; or deliberately limited CI-free evidence. State each condition. |
| **NO-GO** | Use for a score below B or a `required` finding. Also use it for a material or unexplained architecture violation or failed required local validation. Use it for an invalid, stale, or drifted identity, scope, requirement, path, or current-head binding. |

### Merge readiness

Report forge approval and required-gate state as a separate **Merge readiness** fact when default-profile
evidence is available. For example: `Blocked — one independent approval required by repository policy`.
Use GitHub `reviewDecision` and GitLab merge-request approval state as repository-policy evidence. This
state does not lower the review score or verdict. GO is a review verdict, not an approval, merge
authorization, or claim that every branch-protection rule is satisfied.

`--report-only` can report that the review evidence is GO-eligible. It must record
`delivery: withheld (read-only)` and `auto_merge: withheld (read-only)`. It must not report a
delivered GO. Without `--enable-auto-merge-on-go`, a delivered GO records
`auto_merge: withheld (not requested)`. For
`CONDITIONAL GO`, `NO-GO`, CI-free, prevalidated, and GitLab, record `auto_merge: not-eligible` with
the blocker.

## Verified GO delivery

A direct default-profile GitHub review owns this narrow finalization unless an enclosing coordinator
declares itself as the single delivery owner. Complete the finalization before you emit terminal GO.
The finalization can make only these changes:

- add one verified reviewer response to each open review thread;
- resolve each thread after its response is visible;
- add `state:implementation-go`; and
- remove `state:implementation-no-go`.

Do not create a missing label. Do not change another label. Treat the two implementation-state labels
as mutually exclusive.

Read the complete conversation for every open thread. A response must state the disposition and the
exact reviewed-head evidence that makes resolution correct. If a finding is not addressed, keep its
thread open and change the verdict to NO-GO. Do not use a general PR comment as a thread response. Do
not alter already-resolved history.

For direct GitHub delivery, invoke the installed `deliver_go.py` helper. Give it every retained target
and immutable identity value. Give it a response manifest that binds each initially open thread to its
complete conversation digest and non-empty reviewer response. The helper must do these actions:

First, use the read-only preparation mode with the same target arguments and `--prepare-manifest`.
This mode returns each open thread, its complete conversation, and its digest. Add the verified
response body to each entry. Preserve all binding, thread, and digest values. Save that JSON as the
response manifest. Then, run the delivery command:

```bash
<installed-skill>/scripts/deliver_go.py \
  --target-host github.com \
  --target-repository <owner/repository> \
  --expected-pr-url <canonical-pr-url> \
  --expected-base-oid <base-oid> \
  --expected-head-oid <head-oid> \
  --prepare-manifest \
  <number>
```

```bash
<installed-skill>/scripts/deliver_go.py \
  --target-host github.com \
  --target-repository <owner/repository> \
  --expected-pr-url <canonical-pr-url> \
  --expected-base-oid <base-oid> \
  --expected-head-oid <head-oid> \
  --responses-file <response-manifest.json> \
  <number>
```

Use this response-manifest shape:

```json
{
  "binding": {
    "repository": "owner/repository",
    "number": 123,
    "url": "https://github.com/owner/repository/pull/123",
    "base_oid": "<40-lowercase-hex>",
    "head_oid": "<40-lowercase-hex>"
  },
  "responses": [
    {
      "thread_id": "<review-thread-node-id>",
      "conversation_sha256": "<complete-conversation-digest>",
      "body": "Verified response with disposition and exact-head evidence."
    }
  ]
}
```

Use an empty `responses` list only when there are no open threads. The helper adds its own
deterministic delivery marker. Do not put a marker in `body`.

1. Bind the canonical open, non-draft PR and exact base and head again.
2. Enumerate all open threads and their complete conversations.
3. Reject a response manifest that has a missing, extra, duplicate, stale, or empty entry.
4. Before each response, verify the exact PR head and bound conversation.
5. Post one deterministic response and verify its receipt and visibility.
6. Resolve that thread only after the verified response is visible on the unchanged head.
7. Verify the resolution before it continues.
8. Before the label change, bind the exact open head again and require zero open threads.
9. In one target-scoped command, add `state:implementation-go` and remove
   `state:implementation-no-go`.
10. Read the PR and all threads again. Require the unchanged head, zero open threads, and exactly one
    implementation-state label: `state:implementation-go`.

If a read, response, resolution, label change, or readback fails or is indeterminate, stop. Do not
retry blindly. Do not unresolve a thread. Do not make a compensating label change. Report the known
partial state and withhold terminal GO. A later review can recognize an exact deterministic response,
but it must repeat all current-head and final-state checks.

GitHub does not provide a head-conditional thread-resolution or label mutation. Therefore, the helper
guarantees the immediate pre-write and post-write bindings. If the post-write binding detects a race,
report the external state as partial. Never report a delivered GO for that run.

If an enclosing coordinator is the declared single delivery owner, do not invoke the helper or make a
second write. Return the bound structured GO result to that coordinator. The coordinator must perform
and verify the same sequence. It must not expose terminal GO until the final postconditions pass.

`--report-only`, `--ci-free`, and `--prevalidated` never run this finalization. A GitLab review can use
an authenticated capability that proves equivalent exact-head, discussion-response, resolution, and
exclusive-label postconditions. If that capability is absent, report the eligible assessment and the
delivery blocker. Do not claim a delivered GO.

## Guarded GitHub auto-merge

Enable auto-merge only when the user directly requests `--enable-auto-merge-on-go`. Apply this option
only after an exact delivered default-profile GitHub `GO`. Before you apply it, verify each requested
comment batch and the verified GO-delivery postconditions. This option does not permit a direct merge,
retry, approval, additional label change, bypass, or policy change.

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
   - all effective pre-admission gates, including required approvals; and
   - required queue route.
2. If a value changed or a binding is missing, withhold auto-merge.
3. If a gate failed or is pending, withhold auto-merge.
4. If the author or reviewer changed, withhold auto-merge.
5. If a required thread is unresolved, withhold auto-merge.
6. If comment publication failed or is indeterminate, withhold auto-merge.
7. Require an authenticated capability that binds the canonical target and can enable normal
   auto-merge without administrator bypass.
8. Use the one repository-supported method that the capability returns.
9. Do not select the method.
10. Do not guess the method.
11. Do not change the method.
12. If the repository requires a merge queue, require a separate exact-head queue-admission capability.
13. Do not use normal auto-merge as a queue-admission proxy.
14. Invoke exactly one bound operation:

    - Enable auto-merge with the retained PR node ID and `expectedHeadOid`; or
    - Use queue admission with the same target and head.

15. Do not use ambient repository state, ambient branch state, or generic command-line interface
    (CLI) defaults.
16. Do not use a direct merge command or fallback mutation.
17. Do not retry after a failed or indeterminate result.
18. Fetch the exact PR again.
19. Report `enabled` only if auto-merge uses the same node ID, head, and supported method.
20. Report `queue-enqueued` only if its entry binds the same PR, target, and reviewed head.
21. Do not report the PR as merged.

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
9. Report coverage gaps.
10. Report merge readiness or repository-policy state.
11. Report delivery state and auto-merge state.
12. After the findings, report brief strengths.

## Finding publication

The requested review delivery boundary permits normal finding publication. Publish findings as
comments only. This section does not prohibit the separate verified GO finalization. During finding
publication, do not do any of these actions:

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
- A bound value changed.

If there are no findings, do not post a clean review. Continue to verified GO delivery only when all
GO conditions apply.

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
