# Decision and delivery

## Why

A review verdict is evidence. It does not expand the forge scope. Bind the exact artifact before a
scoped publication. This check prevents publication to a later artifact and prevents a favorable
result from stale review state.

Use the [ASD-STE100 technical-English policy](../../TECHNICAL_ENGLISH.md) for all technical prose
and review output. Use the canonical
[bounded review exchange](../../../docs/review/common.md#bounded-review-exchange) for state and round
policy.

```text
[complete review] -> [state carrier] -> [exact readback]
                              |                |
                              |                +-> [nonterminal: exclusive NO-GO]
                              +-> [terminal GO: carrier -> thread closure -> exclusive GO]
                                                                   |
                                            [optional guarded auto-merge]
```

## Engineering principle routes

- [P037 Idempotency Before Retry](../../../docs/principles/README.md#p037) and
  [P044 Atomicity Where Possible](../../../docs/principles/README.md#p044) require one bound atomic
  review per reviewer round. They prohibit a blind retry after an uncertain write.
- [P050 Least Privilege](../../../docs/principles/README.md#p050),
  [P051 Complete Mediation](../../../docs/principles/README.md#p051),
  [P052 Separation of Duties](../../../docs/principles/README.md#p052), and
  [P058 Bounded Agent Authority](../../../docs/principles/README.md#p058) keep review, publication,
  thread closure, labels, approval, and merge as separate capabilities.
- [P061 Separate Decision from High-Impact Execution](../../../docs/principles/README.md#p061),
  [P062 Human Approval for Irreversible or High-Risk Actions](../../../docs/principles/README.md#p062),
  and [P083 Irreversible Actions Last](../../../docs/principles/README.md#p083) require an authority
  and identity check immediately before a write.
- [P065 Verify Before Claiming Completion](../../../docs/principles/README.md#p065) and
  [P068 No Validation Bypass](../../../docs/principles/README.md#p068) prohibit a favorable delivered
  result from stale, incomplete, bypassed, or unverified evidence.

## Decision

For a default or continuous-integration-free (CI-free) normal report, calculate findings and the
score. Then, reduce the reviewer event and emit one verdict. For the prevalidated profile, emit only
its structured audit. Do not emit a verdict, scorecard, carrier, or publication. GitLab can report a
verdict. This skill must not enable GitLab auto-merge.

| Verdict | Required conditions |
| --- | --- |
| **GO** | Use only for the default profile. Require grade A (93–100), architecture alignment or an evidenced intentional change, zero active findings with critical or major severity, zero active required findings, complete applicable coverage, and passing host-selected checks on the reviewed head. The exchange state must also have `phase=complete`, `verdict=GO`, `next_action=finalize`, an exact current-head artifact binding, and only terminal finding states. Keep each `accepted_risk` finding in the report with its verified authority receipt. A delivered GO also requires the verified delivery postconditions below. |
| **CONDITIONAL GO** | Use only for a clean CI-free assessment before round 5. Require architecture to pass, no active required source finding, complete applicable CI-free coverage, and a score of at least B. The state is `phase=complete`, `next_action=none`, and `go_eligible=false`. For direct normal GitHub delivery, make the NO-GO label exclusive. A coverage or evidence gap produces `NO-GO`. |
| **NO-GO** | Use it for a score below B, an active required finding, a material architecture violation, failed required validation, or an invalid or stale binding. For direct normal GitHub delivery, make the NO-GO label exclusive after verified carrier publication. |

### Merge readiness

Report forge approval and required-gate state as a separate **Merge readiness** fact when
default-profile evidence is available. GO is a review verdict. It is not an approval, merge
authorization, or claim that each branch-protection rule passed.

`--report-only` can report that evidence is GO-eligible. It must record
`delivery: withheld (read-only)` and `auto_merge: withheld (read-only)`. Without
`--enable-auto-merge-on-go`, a delivered GO records `auto_merge: withheld (not requested)`. For
CONDITIONAL GO, NO-GO, CI-free, prevalidated, and GitLab, record `auto_merge: not-eligible` with the
blocker.

## Reviewer-round carrier

Default and CI-free direct delivery publish one exact-head state carrier for each reviewer round.
A normal `--report-only` review calls the exchange helper and returns the prepared carrier and
logical batch. It does not publish, resolve a thread, or change a label. `--prevalidated` does not
call an exchange or delivery helper.

For GitHub, send exactly one atomic request to the retained target:

```text
POST /repos/{owner}/{repo}/pulls/{number}/reviews
commit_id = reviewed head OID
event     = COMMENT
body      = visible review followed by the final canonical state carrier
comments  = one entry for each new anchorable finding
```

Put only one verified changed `path`, `side`, causal `line`, and finding body in each comment entry.
Append this marker to each new inline finding:

```text
<!-- HomericIntelligence:review-finding:v1 exchange=<exchange-id> id=F-NNN -->
```

Carry reconciled earlier findings in the state ledger. Do not publish them as new inline comments.
A terminal GO round must publish its carrier even when the `comments` array is empty. Do not post a
different generic clean review.

Verify the returned review and fetched comments against the target, `COMMENT` or `COMMENTED` state,
reviewed commit, complete body carrier, and each expected path, side, line, finding ID, and body. If
verification fails or is uncertain, make no additional write. Do not retry. Do not substitute a
prose-only comment or `gh pr review --comment`.

If a bound value changes, withhold the complete set. When only the pull-request head changes, use a
separate author-response invocation to bind the new artifact before the current exchange continues.
That head refresh does not increase the reviewer-round count. A material requirements change uses
the reframe rule. It does not silently reset the exchange.

Before a human decision or requirements reframe, the pull-request surface adapter must resolve one
exact current logical state. Start with the latest accepted state carrier. Reduce each later
contiguous author-event carrier in verified provider order. Reject a stale event, fork, gap, or
ambiguous chain. Then, resolve one exact live authority record. Verify its body digest, repository
authority, target, exchange, applicable findings, and decision before you give the normalized
receipt to the reducer. The reducer validates the receipt shape and state binding. It does not
authenticate the forge record. A reframe stores the receipt in
`supersession_authority_receipt`. Before a state-dependent label or terminal delivery, resolve and
verify that receipt again. For GitHub delivery, use `review:<review-id>` or
`comment:<thread-comment-id>` as the reference. Require the exact record to have `OWNER`, `MEMBER`,
or `COLLABORATOR` author association. Also require its author to have current `ADMIN` or `MAINTAIN`
repository permission. If the adapter cannot prove both conditions, withhold the state-dependent
operation.

## Authority-transition state carrier

An invocation with an explicit `human_decision` or `reframe` event is the only owner of that
authority transition. Require the explicit event and receipt before reduction. Do not infer either
item from the retained state or the authority record. Resolve the current logical state through all
verified pending author events before you apply the transition. A human decision binds the retained
exchange, logical state, artifact revision, and artifact digest. Its state carrier has a new
visible-content digest, and its reviewer-round count does not change. A reframe binds the exact
superseded logical state, starts a new exchange at round 1, binds the new requirements and current
artifact, and stores the verified supersession receipt. Its `superseded_exchange_ids` value is the
unique, oldest-first prior genesis ancestry followed by the immediate prior exchange ID. It must not
contain the new exchange ID.

For GitHub, a human decision uses one exact-head `COMMENT` review with an empty inline-comments
array. A reframe uses the normal ordered inline finding batch for its new round-1 findings. Its batch
is empty only when it has no new anchorable finding. For a nonterminal result, publish and verify the
review before exclusive NO-GO delivery. For a terminal GO, give the same prepared body and
action-specific batch to the terminal helper. The helper is the one `COMMENT` publisher. Do not
publish the terminal carrier through the general publisher first. For GitLab, put the state note and
each new finding discussion in one atomic draft or batch. When there is no new finding discussion,
create one immutable state note through the applicable normal delivery path.

Require exact readback of the target, actor, head, body bytes, carrier digest, accepted-event digest,
authority receipt, and provider order after the exact logical predecessor. Then, apply the normal
nonterminal or terminal delivery conditions without a new reviewer assessment. On an uncertain
write or readback, stop without a retry or a second delivery path.

## Author-event carrier

The `pr-review --author-response` invocation is the only direct author-event preparation and
publication owner. A reviewer-round invocation verifies the result. It must not synthesize or
publish an author event. Before a corrective reviewer round or authority transition, reduce every
pending author-event carrier after the latest state carrier in verified provider order. Each event
must bind the logical state that its exact predecessor derives. When this chain is nonempty, its
final event must bind the current head, the complete active required-finding set, and the author's
answers. For GitHub,
publish each author event through one exact-head `COMMENT` review with an empty inline-comments
array. For GitLab, use one immutable author-event note in
[GitLab discussion delivery](#gitlab-discussion-delivery). The carrier is the response ledger.
Thread prose can give context, but it is not the author answer and cannot replace the carrier.

A normal response starts from `phase=awaiting_author`. A pull-request head refresh can also start
from `phase=awaiting_reviewer`, `phase=awaiting_evidence`, or a pre-round-5 complete
`CONDITIONAL GO`, but the revision must change. Each changed-head response covers every active
required finding. It also covers each required finding in `resolved`, `withdrawn`, or
`accepted_risk` state. It uses the same identifiers, replaces the prior answers, and clears the
prior reviewer replies. It also clears a prior accepted-risk authority receipt. A new risk request
needs a new authoritative decision for the changed head. Nonblocking findings keep their state.

The response list is empty only when there is no active or terminal required finding. A refresh
invalidates coverage and does not change the round, progress history, GO eligibility, or finding
IDs. From `awaiting_reviewer`, it stays `awaiting_reviewer`. From `awaiting_evidence` or a conditional
state, it moves to `awaiting_reviewer` when it revalidates a terminal required finding. Otherwise,
it moves to `phase=awaiting_evidence`. Each refresh has `verdict=NO-GO` and
`next_action=review_assessment`.

Verify the returned record identity, actor, current head, final author-event carrier, body digest,
and prior-state digest. For GitHub, also require `COMMENT` or `COMMENTED` state. Reject an absent,
stale, foreign, repeated, or ambiguous author event. Do not infer an answer from a commit message,
acknowledgment, thread resolution, or old prose. A normal report-only author response can prepare
this exact review; it cannot publish it.

Immediately before author-event publication, revalidate the exact target, base, current head,
reviewed scope, requirements, complete scope set, latest state review, complete pending
author-event chain, logical state, provider order, and publisher actor. For GitHub, publish one
atomic review with the current head as `commit_id`,
`COMMENT` as `event`, the exact rendered author-event carrier as `body`, and an empty `comments`
array. Read the review and target again. Require the exact body bytes, actor, target, current head,
carrier digest, prior-state digest, and publication order after the exact predecessor carrier. Also
require `COMMENT` or `COMMENTED` state for GitHub. If publication or readback fails or is uncertain,
stop without a retry or a second write. After verified readback, report the derived phase and stop.
Do not assess the implementation or increase the reviewer round in the same invocation.

## Exclusive NO-GO delivery

After exact readback of a nonterminal, CONDITIONAL GO, or NO-GO round, use the installed helper with
the retained target, immutable identities, and verified version-1 state-carrier proof:

```bash
<installed-skill>/scripts/deliver_go.py \
  --target-host github.com \
  --target-repository <owner/repository> \
  --expected-pr-url <canonical-pr-url> \
  --expected-base-oid <base-oid> \
  --expected-head-oid <head-oid> \
  --state-carrier-file <verified-non-go-carrier.json> \
  --deliver-no-go \
  <number>
```

The proof has only these fields:

- `schema_id`, with the value `athena.pr-review.no-go-proof`;
- `schema_version`, with the value `1`;
- `binding`, with the exact repository, pull-request number and URL, base object identifier, and
  head object identifier;
- `review_id`, with the published `COMMENT` review identity;
- `state`, with the complete version-1 state envelope; and
- `visible_content`, with the exact text before the state carrier; and
- `requirements_binding`, with the reviewed-scope digest, linked-requirements digest, and canonical
  sorted set of selected requirement-issue URLs.

The helper extracts the state carrier from the exact review body. It compares the extracted carrier
with `state` and `visible_content`. It must verify either the nonterminal `phase!=complete`,
`verdict=NO-GO`, and `next_action!=finalize` tuple or the terminal `phase=complete`,
`verdict=CONDITIONAL GO`, `next_action=none`, and `go_eligible=false` tuple. It also verifies the
review identity, body digest, carrier digest, reviewed head, and live requirements binding before a
label write. The state
`artifact_binding.sha256` and `requirements_sha256` values must equal their respective retained
binding digests. Require `state:implementation-no-go` to be
present and `state:implementation-go` to be absent.
`already_delivered` is an idempotent success only for that exact label state on the unchanged head.
A write or readback failure is partial. Do not claim delivery or make a blind retry.

## Verified GO delivery

A direct default-profile GitHub review owns this narrow finalization unless an enclosing coordinator
is the declared single delivery owner. This helper is the only terminal state-review publisher. Do
not publish the terminal round through the general reviewer-round path first. Complete finalization
before you expose a delivered GO. CI-free, prevalidated, report-only, and GitLab invocations do not
run this GitHub finalizer.

First, run the read-only version-1 preparation with the same target arguments:

```bash
<installed-skill>/scripts/deliver_go.py \
  --target-host github.com \
  --target-repository <owner/repository> \
  --expected-pr-url <canonical-pr-url> \
  --expected-base-oid <base-oid> \
  --expected-head-oid <head-oid> \
  --prepare-manifest \
  [--requirement-issue <canonical-issue-url> ...] \
  --schema-version 1 \
  <number>
```

The returned `athena.pr-review.closure-manifest` has only `schema_id`, `schema_version`, `binding`,
`state`, `terminal_visible_content`, `entries`, `requirements_binding`, `comments`, and
`summary_finding_ids`. The `state` field contains the complete terminal state envelope. The helper
adds one entry for each open thread. Complete these entry fields without adding a field:

- `thread_id`, `finding_id`, `finding_exchange_id`, and `finding_state_sha256`;
- `superseding_state_sha256`, `origin_comment_id`, and `origin_review_head_oid`;
- `conversation_sha256`, `finding_disposition`, and `author_event_review_id`;
- `author_answer` and `author_artifact_revision`;
- `reviewer_disposition` and `closure_evidence`; and
- `authority_receipt`.

Use `comments` for the ordered inline-comment batch in the terminal `COMMENT` review. Each entry has
only `path`, `side`, `line`, and `body`. The body ends with the exact exchange and finding marker.
The state location for an anchorable terminal-round finding has the form
`<relative-path>:<positive-line>`. Its path and line must equal the inline entry. Put each such
finding in `comments`. Put each other terminal-round finding identity in the ordered
`summary_finding_ids` list. The two lists must not overlap. Their union must equal all findings that
the terminal reviewer event introduced. Empty lists are valid when that event introduced no
finding. The manifest is canonical JSON and must not exceed the common input limit.

Do not edit `requirements_binding`. Its `reviewed_scope_sha256` is the digest of the current PR
title, body, closing references, state, draft state, and base and head names. Its
`requirements_sha256` is the aggregate `reviewed_linked_requirements` digest. Its
`requirement_issue_urls` value is the canonical sorted set of all linked requirement URLs that the
collector selected. The terminal state `artifact_binding.sha256` must equal
`reviewed_scope_sha256`. The state `requirements_sha256` must equal the retained requirements
digest.

After publication, require the fetched inline root to belong to the selected terminal review and
the exact reviewed head. Its path, side, line, body, exchange marker, and finding marker must equal
the prepared entry. The helper derives the new thread identity and closure entry from this readback;
the caller does not predict a thread identity.

Use only `resolved`, `withdrawn`, `accepted_risk`, or `nonblocking` as terminal reviewer
dispositions. An accepted risk requires the `risk_acceptance` answer and a verified authority
receipt. A corrected finding requires its author answer and corrective head. A contest requires its
bound author-event review and one valid terminal reviewer answer. The helper extracts that
author-event carrier, replays it from the exact prior state carrier, and derives the author answer
and artifact revision. The helper generates the response body. It does not accept arbitrary
version-1 response prose.

After a head change, a `resolved` or `withdrawn` closure must use the revalidated author answer and
the reviewer response from the current-head assessment. An `accepted_risk` closure must use a new
author risk request and an authority decision that binds the changed-head state. A prior-head
terminal disposition or risk receipt cannot authorize delivery.

For a current finding, set `finding_state_sha256` to the terminal state digest and set
`superseding_state_sha256` to `null`. For an open finding from the selected supersession ancestry,
bind `finding_state_sha256` to the exact source state and `superseding_state_sha256` to its direct
reframe child. Use the source exchange in `finding_exchange_id`, even when a later exchange reuses
the same `F-NNN` value. Such a historical closure uses `withdrawn`, the child's exact verified
supersession receipt, and the canonical source-state reframe evidence. Preserve source-state author
fields; when the source has no answer, keep them `null`. Do not infer an answer from prose. Omit
historical threads that were resolved before terminal publication. After terminal publication, a
resolved manifest entry is valid only as exact recovery evidence for its generated response. An
unrelated, foreign, or ambiguous open thread withholds GO.

Each generated response names the finding as `<exchange-id>/<finding-id>`. A historical response
states `withdrawn`, identifies an authoritative requirements reframe, and shows both state digests
and the authority receipt. Its final marker binds `exchange`, `id`, `source`, `superseding`,
`terminal`, and the response digest. Thus, two exchanges that both use `F-001` have distinct
closure markers.

Save the completed canonical JSON and invoke delivery:

```bash
<installed-skill>/scripts/deliver_go.py \
  --target-host github.com \
  --target-repository <owner/repository> \
  --expected-pr-url <canonical-pr-url> \
  --expected-base-oid <base-oid> \
  --expected-head-oid <head-oid> \
  --response-manifest <closure-manifest.json> \
  <number>
```

The helper uses this order:

1. Bind the canonical open, non-draft pull request and exact base and head.
2. Read all threads, complete conversations, review records, and implementation-state labels.
3. Before a mutation, validate the complete terminal state and its selected supersession ancestry,
   manifest, ownership, capabilities, composite finding identities, origin heads, answers,
   dispositions, evidence, authority receipts, and live requirements binding.
4. Publish the exact-head terminal `COMMENT` body and `comments` in one request. Verify the exact
   review and inline-comment readback. Derive closure entries for its new finding threads.
5. For each still-open Athena-owned ledger entry, publish the generated closure response and verify
   it on the unchanged head.
6. Resolve that thread only after the exact response is visible. Verify the resolution.
7. Require zero open threads. A foreign open thread withholds GO.
8. Add `state:implementation-go` and remove `state:implementation-no-go` in one target-scoped
   operation.
9. Read the pull request again. Require the unchanged head, one matching terminal ledger, zero open
   threads, the unchanged live requirements binding, and the exclusive GO label.

Recompute the retained requirements binding at preflight, immediately before each write, and after
the final readback. A scope change, closing-reference change, selected-URL change, linked-issue
content or comment change, incomplete evidence, or provider failure withholds delivery.

Resolve only Athena-owned findings whose validated closure-manifest reviewer disposition is
`resolved`, `withdrawn`, `accepted_risk`, or `nonblocking`. An unanswered contest, partial or
still-present finding, stale head, foreign open thread, missing capability, duplicate or conflicting
terminal record, or missing authority receipt withholds GO.

New GitHub adoptions use the GraphQL root comment ID in `native:<root-comment-id>`.
For an existing carrier, the delivery adapter also accepts a canonical positive decimal
`fullDatabaseId` as a read-only compatibility alias. It resolves both forms through the same root
object in one complete GitHub snapshot. A decimal alias with a changed source line requires the
exact discussion permalink, an unchanged viewer-owned root, its submitted root review, and a
successful ancestry check from the root review head to the carrier review head. Missing,
malformed, or ambiguous aliases stop delivery. The adapter preserves carrier bytes and all origin,
ownership, head, and conversation checks.

An open legacy thread without a marker is adopted as a required finding with the immutable
`native:<root-comment-id>` identity. It still requires explicit answer, disposition, and closure
evidence for a current exchange. An exact historical reframe withdrawal can keep its source author
fields `null`; it requires the exact reframe edge, authority receipt, and closure evidence. Do not
infer closure from old prose. Leave resolved legacy history unchanged. To verify an unchanged,
fully delivered legacy GO, use the explicit read-only
`--verify-legacy-go <proof.json>` operation. Its historical three-field responses are proof-only.
They cannot authorize a new response, resolution, review, or label mutation. A version-1 workflow
must not select legacy input as a fallback.

Treat an independent older-head version-1 exchange as completed history only when its terminal
state has `phase=complete`, `verdict=GO`, `next_action=finalize`, and `go_eligible=true`. It must
bind the retained requirements, and its terminal carrier must precede each carrier or authority
record in the current exchange. Its exchange identifier must not occur in the selected current or
supersession ancestry. A conditional or later-published old-head carrier cannot reset the exchange.

Treat the exact same-head terminal record, zero open threads, and exclusive GO label as
`already_delivered`. A label without the matching current-head terminal ledger is not proof. If the
terminal carrier exists after an interrupted run, validate the same manifest and resume only the
remaining generated responses, resolutions, or label operation. Do not publish the terminal carrier
again.

If a read, publication, response, resolution, label change, or readback fails or is uncertain, stop.
Do not retry blindly, unresolve a thread, or make a compensating label change. Report the known
partial state and withhold terminal GO.

If an enclosing coordinator is the single delivery owner, return the bound structured result to it.
Do not make a second write. A GitLab review can use an authenticated capability that proves
equivalent exact-head carrier, discussion-response, resolution, and exclusive-label postconditions.
If it cannot prove these conditions, return the prepared artifact and withhold favorable delivery.

## Guarded GitHub auto-merge

Enable auto-merge only when the user directly requests `--enable-auto-merge-on-go`. Apply this
option only after an exact delivered default-profile GitHub GO. Before the operation, verify the
matching current-head terminal carrier, zero open threads, exclusive GO label, and every required
repository-policy gate. This option does not permit a direct merge, retry, approval, additional label
change, bypass, or policy change.

1. Resolve the canonical host, repository, pull-request number and node ID, open non-draft state,
   base and head object identifiers, both diff lenses, scope digest, requirements digest, path
   manifest, effective pre-admission gates, required approvals, and queue route again.
2. If a value changed, a binding is absent, or a gate failed or is pending, withhold auto-merge.
3. If the author or reviewer changed, a required thread is open, carrier publication is unverified,
   or terminal evidence conflicts, withhold auto-merge.
4. Require an authenticated capability that binds the target and can enable normal auto-merge
   without an administrator bypass.
5. Use the one repository-supported method that the capability returns. Do not select, guess, or
   change the method.
6. If the repository requires a merge queue, require a separate exact-head queue-admission
   capability. Do not use normal auto-merge as a queue-admission proxy.
7. Invoke exactly one bound enable-auto-merge or queue-admission operation.
8. Do not use an ambient target, generic command-line default, direct merge, or fallback mutation.
9. Do not retry after a failed or uncertain result.
10. Fetch the pull request again. Report `enabled` or `queue-enqueued` only when the result binds the
    same target and reviewed head. Do not report the pull request as merged.

## Normal report

Return these items in order:

1. Artifact identity, forge, base, head, immutable scope, and path bindings.
2. Behind count, files reviewed, linked issue, and acceptance criteria.
3. Each unbound check as a coverage gap.
4. Architecture decision, language routes, surface routes, and not-applicable reasons.
5. Findings from `critical` through `FYI`, with disposition, identity, location, impact, evidence,
   closure condition, and proportionate remediation. Keep each accepted risk and its verified
   authority receipt in this list.
6. Exchange ID, round, required-finding progress, state digest, carrier URL, and readback evidence.
7. Six-dimension scorecard, weighted grade, and verdict.
8. Commands and their pass or fail state.
9. Coverage gaps and merge readiness.
10. Exact `delivered`, `already_delivered`, `withheld`, or `partial` state; terminal review identity;
    closure thread identities; exclusive implementation-state label; and auto-merge state.
11. Brief strengths.

## GitLab discussion delivery

Use the same reducer and carrier. Create one immutable authenticated actor-owned top-level
merge-request note for each reviewer-round or authority-transition state. Its body is the visible
review followed by the final `kind=state` carrier. Do not update or replace a carrier-bearing note.
The latest state note in the single complete, replay-valid ancestry is the canonical retained-state
note. Reduce its later author-event notes to derive the current logical state. Always publish a
terminal state, including when there is no new inline finding.

Create one separate immutable authenticated actor-owned top-level note for each
`kind=author-event` carrier. Do not update or replace it. Do not use a discussion reply as the
complete author event. It can contain only supporting context.

Before a create, enumerate all top-level notes. Reconstruct one complete state and author-event
chain in provider order. Reject a foreign or malformed carrier, a repeated event, a missing
predecessor, a fork, both carrier kinds in one note, or a retained note whose actor, ID, or body
digest changed. Revalidate the merge-request identity and exact head before each write. After the
write, read the note and merge request again. Accept the result only when the actor, note ID, exact
body, carrier digest, predecessor digest, provider order, and head all match. Retain all prior notes
so that a superseded logical state and its direct reframe child can be verified for terminal
discussion closure.

Create one actionable changed-line discussion for each new anchorable finding. Put the exact
`base_sha`, `start_sha`, `head_sha`, `old_path`, `new_path`, and `position_type=text` values in its
position. Use `new_line` for an addition, `old_line` for a deletion, and both for an unchanged line.
The discussion contains the compact finding marker. It does not contain the complete state carrier.

When a reviewer action has one or more new finding discussions, publish all discussions and the new
state note through one supported atomic draft or batch. If the host or forge cannot provide this
capability, return the prepared batch and withhold publication. Do not start a sequential fallback.
When the action has no new finding discussion, publish one immutable state or author-event note.
Stop if a bound value changes or a write or readback result is uncertain. Report the known result.
Do not retry it.

After verified non-GO state-note readback, make the NO-GO label exclusive through one authenticated,
target-scoped capability. For terminal GO, the terminal delivery owner creates the state note once,
answers and resolves only ledger-authorized discussions, and then makes the GO label exclusive. If
the host cannot prove an equivalent exact-head operation and readback, return the prepared artifact
and withhold a favorable delivered result.

Report review or discussion URLs, publication failures, residual risks, and unverified assumptions
accurately. Forge policy controls approval and merge. Review prose does not.
