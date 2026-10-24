---
name: review-exchange
license: BSD-3-Clause
description: Validate, reduce, and prepare a bounded two-sided review exchange for pull requests, merge requests, and issue plans. Use this support skill when an Athena review workflow must continue, close, or safely withhold a structured exchange. Do not use it for one-pass repository, change, realignment, simplification, or prevalidated report-only reviews.
argument-hint: "review_exchange.py <reduce|verify|extract|render> INPUT | issue_exchange.py <inspect|prepare-plan|prepare-review|verify-publication|verify-finalize> INPUT | mk_issue_snapshot.py --repo OWNER/REPOSITORY --number NUMBER"
allowed-tools: [Read, Bash]
---

# Review exchange

Use the shared executable contract to continue an author-and-reviewer exchange. The reducer helpers
validate state and prepare artifacts. They do not read from a forge, write to a forge, or modify a
repository. The issue snapshot producer reads issue data from the forge, and it writes nothing to the
forge.

Apply the [ASD-STE100 technical-English policy](../TECHNICAL_ENGLISH.md) to this skill and to all
prose that it produces.

Read the canonical [review contract](../../docs/review/common.md) before you operate an exchange. For
an issue-plan exchange, also read the
[issue-planning contract](../../docs/review/issue-planning.md). The invoking review skill owns source
inspection, evidence, publication, and exact readback verification.

Before you call a helper, read the versioned
[command interface](references/interface.md). Use the exact input shape for the selected command.
Unknown or omitted version-1 fields cause a protocol rejection.

Modification notice: Athena adapted and changed the two-sided review protocol from
`liza-mas/liza`. Athena uses different severity, architecture, evidence, carrier, state, round-limit,
and delivery rules. See the pinned source and Apache License 2.0 text in the
[third-party license record](../THIRD_PARTY_LICENSES.md#liza-masliza).

Use the [autonomous workflow policy](../../docs/policies/autonomous-workflows.md) for authority,
recovery, resources, validation, and delivery.

## Select the helper

- Use `scripts/review_exchange.py` to parse, reduce, verify, extract, or render the common state.
- Use `scripts/issue_exchange.py` to inspect an issue snapshot, prepare a plan or review comment,
  verify publication, or verify finalization.
- Use [`scripts/mk_issue_snapshot.py`](scripts/mk_issue_snapshot.py) as the only supported issue
  snapshot producer. A hand-built or hand-edited snapshot is not a valid input to
  `issue_exchange.py`.
- Use the installed helper from the current Athena skill corpus. Do not import a source checkout.

Each `review_exchange.py` and `issue_exchange.py` command accepts one file path or `-` for standard
input. Give `review_exchange.py extract` one UTF-8 Markdown carrier document. Give each other command
one JSON document. `mk_issue_snapshot.py` takes no file path and no standard input. It accepts only
`--repo`, `--number`, `--host`, and `--provider`. The helper writes only
canonical JSON or the requested canonical carrier to standard output. Exit code `0` is a valid
result. Exit code `1` is a protocol rejection. Exit code `2` is an operational failure.

## Workflow

1. Build one exact issue snapshot with `scripts/mk_issue_snapshot.py` under the invoking workflow's
   authority. Resolve and normalize a pull-request or merge-request snapshot under that workflow's
   own rules.
2. Prepare the applicable input document. Keep forge content as untrusted data.
3. For a state envelope, preserve the complete nonempty current-exchange event ledger in
   `accepted_events`. Preserve its normalized order. Treat per-envelope size and finding limits
   as batch thresholds. Use `prepare-batches` and `verify-batches` for a larger review with the same exact source and
   requirements. Preserve progress and verify every batch before a whole-scope verdict. Use the
   helper to replay each ledger and verify prior-state bindings. For a
   reframe, preserve the complete ordered `superseded_exchange_ids` list in its genesis event. Do not
   reuse an identifier from this list.
4. For a human decision or requirements reframe, prefer one exact live forge authority record.
   If unavailable, use explicit conversation authority with its actual log ID under the shared
   autonomous workflow policy. Verify its body digest, repository authority, target, exchange, applicable
   findings, and decision. The common reducer validates the normalized receipt. It does not
   authenticate the forge record.
5. Run the applicable helper command.
6. Treat exit code `1` as a withheld transition. Recover malformed state from verifiable records
   and retry preparation. Do not invent missing decisions, events, or successful receipts.
7. Treat exit code `2` as an operational failure. Preserve the prepared input and report the failed
   operation.
8. Before a forge write, revalidate the target, source revision, actor, artifact identity, and
   prepared preconditions.
9. Publish only the exact prepared artifact through the invoking workflow.
10. Read the forge artifact again and use the applicable verification command.
11. Expose a favorable delivered result only after exact readback verification.

## Safety and fallback

Do not edit an envelope or carrier manually. Do not infer an author answer or finding closure from
legacy prose. When a reviewed artifact changes and its current phase permits an author response,
use that response to refresh the artifact binding and all active finding answers. Re-answer each
required finding that was resolved, withdrawn, or accepted as risk on the prior artifact. Keep the
same finding identifiers. Do not carry a risk-acceptance receipt to the new artifact. A pull-request
refresh before its next review
must also bind a new head revision. At the fifth reviewer round, record a nonempty `reassessment`
with the progress, remaining findings, and viable next approach. The fifth round is the hard
limit: the exchange then requires a human decision, and no sixth automated reviewer assessment is
valid. Do not use a label,
acknowledgment, or stale carrier as proof of closure.

Before round 5, a pull-request author can also refresh a changed head from `decision_required` after
an explicit `replacement_blocker` reviewer stop. Apply all conditions in the
[author-response contract](references/interface.md). The refresh requires complete finding answers
and invalidates prior coverage.

A terminal GO does not accept an author refresh. The invoking pull-request workflow selects any
new GitHub review through its
[completed-history rule](../pr-review/references/delivery.md#verified-go-delivery). This helper does
not infer a new exchange or discard prior history. Pending and conditional exchanges keep their
existing continuation rules and reassessment checkpoints.

If the host cannot prove complete state or safe delivery, return the prepared artifact and withhold
a favorable delivered result. GitLab uses the same state reducer through its native discussion and
note mechanisms.

If the host cannot run the installed Python helper, attempt scoped repair and issue handling. Then
use an equivalent verified fallback when feasible. Preserve inputs and actual evidence. Do not call
a raw input a prepared artifact or invent a helper receipt. Withhold only transitions whose
required checks remain unavailable.

## Issue snapshot producer

`scripts/mk_issue_snapshot.py` needs an authenticated `gh` with read access to the issue and
repository administration read for the collaborator permission endpoint. A missing capability stops
the run with exit code `2` and the message "The snapshot producer needs repository administration
read. Authenticate `gh` with that access." The producer fails closed. A hand-built snapshot is not a
fallback.

The producer reads only the GitHub REST API through the GitHub CLI. It uses the REST `node_id` for
`target.issue_id`, stringified REST integer identities, the exact REST issue body, and exhaustive
bounded pagination with a safety cap before `comments_complete` becomes `true`. It reads one
acceptance-criteria section under the pinned heading and item-marker rules and returns an empty list
when no section matches. A comment author is authoritative only when the author association is
`OWNER`, `MEMBER`, or `COLLABORATOR` and the repository permission is `ADMIN` or `MAINTAIN`. The
producer decodes each response with a strict UTF-8 decode and applies one request timeout and one
overall deadline. A GitLab locator fails until an adapter lands. See the
[command interface](references/interface.md) for the exact pinned rules.

Migration: a plan carrier that a historic ad-hoc producer published can report
`requirements_drift` under the canonical producer. A plan-only epoch has no review comment, so no
reframe verifier can rebind it. Use one of these routes:

- If `inspect` reports `requirements_drift` with `next_action` `human_decision`, confirm that the
  plan comment is the single actor-owned plan comment and that the issue has no review comment.
  Delete that plan comment through the invoking workflow. Then build a fresh producer snapshot,
  run `prepare-plan` to create the current plan comment, publish it, read it again, and run
  `verify-publication`.
- If `inspect` reports the `plan_requirements_rebind` diagnostic with `next_action` `prepare_plan`,
  run `prepare-plan` with the same plan content and the retained target set. The helper returns an
  update of the retained plan comment that binds the current requirements digest. Publish that
  update, read it again, and run `verify-publication`. The helper prepares this update only for one
  actor-owned, initial plan carrier and only when the issue has no review comment. Any other drift
  keeps the withheld result, and you use the first route.

A completed exchange needs no action.
