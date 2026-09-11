# Version 1 command interface

Use the [ASD-STE100 technical-English policy](../../TECHNICAL_ENGLISH.md) for prose that uses this
interface. Use the [shared review contract](../../../docs/review/common.md) for transition policy.
This reference specifies the complete version 1 input and output interface for the two installed
helpers.

## Data rules

Each JSON object has exactly the fields in this reference. Include a nullable field with the JSON
value `null`. The helpers reject an omitted field, an unknown field, a duplicate key, a duplicate
identity, a nonfinite number, and a value with the wrong JSON type.

Use UTF-8. A digest is 64 lowercase hexadecimal characters. The digest algorithm is SHA-256.
Canonical JSON has sorted object keys, no insignificant space, and no ASCII substitution for Unicode
characters. A JSON-list order is significant unless this reference identifies the list as a set.
The helper sorts each scope set and rejects duplicate values.

The maximum input size is 1 MiB. One exchange can contain a maximum of 100 findings. The maximum
carrier body size is 65,536 UTF-8 bytes for `github` and 1,000,000 UTF-8 bytes for `gitlab`.

Each command has this form:

```bash
<installed-skill>/scripts/review_exchange.py <command> <input-path-or-dash>
<installed-skill>/scripts/issue_exchange.py <command> <input-path-or-dash>
```

Use `-` to read standard input. A valid result has exit code `0`. A protocol rejection has exit code
`1` and one diagnostic on standard error. An input-read or output-write failure has exit code `2`
and one diagnostic on standard error. Except for `review_exchange.py render`, a successful command
writes one canonical JSON value and a line feed to standard output. `render` writes the exact
carrier document.

## Common records

### Target and binding records

A review target has these fields:

| Field | Type and value |
| --- | --- |
| `provider` | `github` or `gitlab` |
| `repository` | Nonempty string |
| `number` | Integer of at least 1 |
| `url` | Nonempty string |

An `artifact_binding` has these fields:

| Field | Type and value |
| --- | --- |
| `revision` | Nonempty immutable revision or comment identity |
| `sha256` | Digest of the reviewed artifact |
| `visible_content_sha256` | Digest of the exact visible carrier content |

An `authority_receipt` has these fields:

| Field | Type and value |
| --- | --- |
| `reference` | Nonempty authority-record identity |
| `sha256` | Digest of the authority record |

The common reducer validates the receipt shape and digest binding. It does not authenticate the
record. Before reduction, the surface workflow must resolve one exact live forge record, verify its
body digest and repository authority, and make sure that it authorizes the target, exchange,
applicable findings, and decision. The issue-snapshot producer must derive `is_authority` from
provider authority metadata. The issue adapter then verifies the exact comment and digest from the
normalized current snapshot. A pull-request workflow must do the equivalent verification from its
exact-head forge snapshot.

An action-bound authority record is the complete comment body. It is one canonical JSON object with
these fields:

| Field | Type and value |
| --- | --- |
| `schema_id` | `athena.review-exchange.authority` |
| `schema_version` | Integer `1` |
| `action` | `human_decision` or `reframe` |
| `target` | Exact review target |
| `exchange_id` | Exchange that receives the authorized result |
| `requirements_sha256` | Requirements digest for that exchange |
| `prior_state_sha256` | Exact state that receives a `human_decision`; `null` for `reframe` |
| `supersedes_state_sha256` | Exact superseded state digest for `reframe`; otherwise `null` |
| `decisions` | Exact human-decision list for `human_decision`; empty list for `reframe` |

For `human_decision`, `prior_state_sha256` is non-null and `supersedes_state_sha256` is `null`. For
`reframe`, `prior_state_sha256` is `null` and `supersedes_state_sha256` is non-null.

The shared parser rejects noncanonical JSON, unknown fields, and a context that does not match the
event or result state. The event verifier requires the exact decision list. The durable-state
verifier requires one exact accepted human-decision event for the receipt. It permits extra original
decisions in the record only when all decisions that the current state attributes to that receipt
remain present. A later reviewer counter removes a superseded selected-closure receipt from that
finding. The authority record digest must equal `authority_receipt.sha256`.

### Finding input

For new GitHub adoptions, use the GraphQL root comment ID. The GitHub delivery adapter can resolve
an existing canonical positive decimal `fullDatabaseId` through the same root object in a complete
snapshot. This read-only compatibility alias does not change the carrier or the generic grammar.
An ambiguous alias is invalid. The adapter retains all origin, ownership, and conversation checks.

A finding input has these fields:

| Field | Type and value |
| --- | --- |
| `id` | Consecutive `F-001` through `F-100` identity. An initial pull-request import can use `native:<root-comment-id>`. The native token contains 1 through 256 characters from `[A-Za-z0-9._~:/+=-]`. |
| `severity` | `critical`, `major`, `minor`, `nit`, or `FYI` |
| `disposition` | `required`, `suggestion`, `nit`, or `FYI` |
| `category` | `simplification` or `null` |
| `material_architecture` | Boolean |
| `location` | Nonempty exact carrier location |
| `impact` | Nonempty impact statement |
| `evidence` | Nonempty list of unique, nonempty strings |
| `closure_condition` | Nonempty string for `required`; otherwise `null` |
| `introduction` | `initial`, `introduced_by_correction`, `new_evidence`, `missed_high_risk`, `missed_security`, `missed_correctness`, or `nonblocking_follow_up` |

A `critical` finding, `major` finding, or material architecture finding has the `required`
disposition. A `minor` finding has the `required` or `suggestion` disposition. A `nit` or `FYI`
severity has its matching disposition. A native finding is an initial, required pull-request
finding. A later nonblocking finding has the `nonblocking_follow_up` basis.

### Response input

An author response has these fields:

| Field | Type and value |
| --- | --- |
| `finding_id` | Existing required-finding identity that the current transition must answer |
| `kind` | `fix`, `fix_with_tradeoff`, `contest`, or `risk_acceptance` |
| `evidence` | Nonempty list of unique, nonempty strings |
| `tradeoff` | Nonempty string for `fix_with_tradeoff` or `risk_acceptance`; otherwise `null` |

A reviewer response has these fields:

| Field | Type and value |
| --- | --- |
| `finding_id` | Prior answered required-finding identity |
| `kind` | `resolve`, `partial`, `still_present`, `withdraw`, `accept`, `counter`, `refute`, or `escalate` |
| `evidence` | Nonempty list of unique, nonempty strings |
| `closure_condition` | Revised nonempty condition for `counter`; otherwise `null` |

A human decision has these fields:

| Field | Type and value |
| --- | --- |
| `finding_id` | Active required-finding identity |
| `kind` | `accept_risk` or `select_closure` |
| `closure_condition` | New nonempty condition for `select_closure`; otherwise `null` |

### Stored state

A stored finding contains all finding-input fields and these fields:

| Field | Type and value |
| --- | --- |
| `closure_revision` | Integer of at least 0 |
| `introduced_round` | Integer from 1 through 5 |
| `state` | `open`, `answered_fix`, `answered_tradeoff`, `contested`, `partial`, `still_present`, `countered`, `resolved`, `withdrawn`, `accepted_risk`, `escalated`, or `nonblocking` |
| `author_response` | `null`, or an object with `kind`, `evidence`, `tradeoff`, and `artifact_revision` |
| `reviewer_response` | `null`, or an object with `kind`, `evidence`, `closure_condition`, and `round` |
| `authority_receipt` | `null` or an authority receipt |

The stored author and reviewer records use the response values in this reference. They omit
`finding_id`. `artifact_revision` is a nonempty string. `round` is an integer from 1 through 5.

A progress record has these fields:

| Field | Type and value |
| --- | --- |
| `round` | Consecutive integer from 1 through 5 |
| `artifact_revision` | Nonempty string |
| `scope` | Sorted, nonempty list of unique target strings |
| `scope_size` | Integer equal to the number of values in `scope` |
| `required_remaining` | Nonnegative integer |
| `accepted_event_sha256` | Digest of the accepted event |

A state record has these fields:

| Field | Type and value |
| --- | --- |
| `exchange_id` | Nonempty stable exchange identity |
| `surface` | `issue` or `pull_request` |
| `target` | Review target |
| `requirements_sha256` | Requirements digest |
| `round` | Current reviewer round, from 1 through 5 |
| `round_limit` | Integer `5` |
| `phase` | `awaiting_author`, `awaiting_reviewer`, `awaiting_evidence`, `complete`, or `decision_required` |
| `artifact_binding` | Artifact binding |
| `scope` | Sorted, nonempty list of unique target strings |
| `prior_state_sha256` | Prior state digest or `null` |
| `accepted_event_sha256` | Accepted-event digest |
| `accepted_events` | Complete normalized event ledger for the current exchange |
| `supersedes_state_sha256` | Superseded state digest or `null` |
| `supersession_authority_receipt` | Authority receipt for a reframe, or `null` when `supersedes_state_sha256` is `null` |
| `coverage_complete` | Boolean |
| `go_eligible` | Boolean. `false` is valid only for a pull-request state. |
| `progress` | One progress record for each reviewer round |
| `findings` | Ordered list of 0 through 100 stored findings |
| `verdict` | `GO`, `CONDITIONAL GO`, or `NO-GO` |
| `next_action` | `author_response`, `review_assessment`, `finalize`, `human_decision`, or `none` |

The accepted-event ledger starts with the initial reviewer assessment or reframe. It contains at
most 509 events. The helper replays the complete ledger, verifies each prior-state binding, and
requires the replayed result to equal all current state fields. The phase, verdict, next action,
findings, authority, and progress history must agree with this replay. Do not construct or edit a
state record manually. A reframe genesis event also has `superseded_exchange_ids`. This is the
complete ordered list of earlier exchange identifiers from the oldest exchange through the direct
predecessor.

### Envelopes

Each envelope has exactly these fields:

| Field | Type and value |
| --- | --- |
| `schema_id` | `athena.review-exchange.state` or `athena.review-exchange.author-event` |
| `schema_version` | Integer `1` |
| `state` | State record or author-event record |
| `state_sha256` | Digest of canonical JSON for `state` |

An author-event record has these fields:

| Field | Type and value |
| --- | --- |
| `event_type` | `author_response` |
| `exchange_id` | Nonempty exchange identity |
| `prior_state_sha256` | Prior state digest or `null` for the initial issue plan |
| `target` | Review target |
| `requirements_sha256` | Requirements digest |
| `artifact_binding` | Artifact binding |
| `scope` | Sorted, nonempty list of unique target strings |
| `scope_change_reason` | Nonempty string or `null` |
| `responses` | Ordered list of unique author responses |

## `review_exchange.py`

### `reduce`

The request has exactly `previous` and `event`. `previous` is `null` for an initial assessment.
Otherwise, it is a state envelope. `event` is one event from the following tables.

An initial reviewer assessment has these fields:

| Field | Type and value |
| --- | --- |
| `event_type` | `reviewer_assessment` |
| `exchange_id` | Nonempty new exchange identity |
| `prior_state_sha256` | `null` |
| `round` | Integer `1` |
| `surface` | `issue` or `pull_request` |
| `target` | Review target |
| `requirements_sha256` | Requirements digest |
| `supersedes_state_sha256` | `null` |
| `artifact_binding` | Artifact binding |
| `scope` | Nonempty list of unique target strings |
| `coverage_complete` | Boolean |
| `go_eligible` | Boolean. An issue assessment uses `true`. |
| `responses` | Empty list |
| `new_findings` | Ordered list of finding inputs |
| `stop_reason` | `null` or a stop reason from the list below |

A requirements reframe has the same fields as an initial assessment, plus the required
`authority_receipt` and `superseded_exchange_ids` fields. It has these different values:

- `event_type` is `reframe`.
- The outer request's `previous` field is the exact retained v1 state envelope. This envelope
  can be in any phase, including `complete`.
- `exchange_id` differs from the prior exchange identity.
- `prior_state_sha256` and `supersedes_state_sha256` equal the prior envelope digest.
- `requirements_sha256` differs from the prior requirements digest.
- `surface` and `target` equal the prior values.
- `authority_receipt` is the normalized receipt that authorizes the supersession.
- `superseded_exchange_ids` is a nonempty list of unique strings. It equals the prior reframe
  genesis list plus the prior exchange identifier. For the first reframe, it contains only the prior
  exchange identifier. The new exchange identifier must not occur in this list.

The result state stores this receipt in `supersession_authority_receipt`. A fresh exchange has
`supersedes_state_sha256=null` and `supersession_authority_receipt=null`. A reframe has non-null
values for both fields.

A continued author response has these fields:

| Field | Type and value |
| --- | --- |
| `event_type` | `author_response` |
| `exchange_id` | Prior exchange identity |
| `prior_state_sha256` | Prior envelope digest |
| `artifact_binding` | New author artifact binding |
| `scope` | Complete nonempty scope set |
| `scope_change_reason` | Nonempty reason when the scope differs; otherwise `null` |
| `responses` | One author response for each required finding that the transition must answer |

Normally, a continued author response applies to `awaiting_author`. For a pull request, it can also
refresh a changed head in `awaiting_reviewer`, `awaiting_evidence`, or a pre-round-5 conditional
complete state. A refresh must change `artifact_binding.revision`. A different artifact digest with
the same revision is not sufficient.

On both review surfaces, each response that changes the artifact revision or digest must answer all
active required findings and all required findings in `resolved`, `withdrawn`, or `accepted_risk`
state. It uses the same finding identifiers. A terminal-finding response replaces the prior author
answer and reviewer response. The finding returns to the answered or contested state for the new
response. For `accepted_risk`, the transition also clears the prior authority receipt. The new risk
request needs a new authoritative decision. Nonblocking findings keep their state and do not need a
response.

When a correction reopens a revalidated terminal finding without a net decrease in active required
findings, the assessment stops with `replacement_blocker`. A clean revalidation can complete. If
the active required finding count decreases, the exchange can continue.

In `awaiting_reviewer`, a refresh stays in `awaiting_reviewer`. In `awaiting_evidence` or a
conditional complete state, the result moves to `awaiting_reviewer` when it revalidates a terminal
required finding. When it has no active or terminal required finding, `responses` is empty and the
result moves to `awaiting_evidence`. Each refresh has `verdict=NO-GO`,
`next_action=review_assessment`, and `coverage_complete=false`. It keeps the reviewer round,
progress records, `go_eligible`, and finding identifiers. It appends one accepted event. Thus, the
509-event ledger limit bounds repeated refreshes.

A corrective reviewer assessment has these fields:

| Field | Type and value |
| --- | --- |
| `event_type` | `reviewer_assessment` |
| `exchange_id` | Prior exchange identity |
| `prior_state_sha256` | Prior envelope digest |
| `round` | Prior round plus 1 |
| `artifact_binding` | Exact author artifact revision and artifact digest, with the visible-content digest for the new reviewer carrier |
| `scope` | Exact author scope set |
| `coverage_complete` | Boolean |
| `go_eligible` | Boolean. Use `false` for a CI-free pull-request assessment. |
| `responses` | One reviewer response for each prior author answer |
| `new_findings` | Ordered list of permitted later finding inputs |
| `stop_reason` | `null` or a stop reason from the list below |

The stop reasons are `closure_conflict`, `replacement_blocker`,
`scope_growth_without_progress`, `no_consensus`, and `requirements_reframe`.
The reducer selects `scope_growth_without_progress` automatically only when one or more active
required findings remain. A clean assessment after a zero-finding artifact refresh can complete
after scope growth.

An authoritative human event has these fields:

| Field | Type and value |
| --- | --- |
| `event_type` | `human_decision` |
| `exchange_id` | Prior exchange identity |
| `prior_state_sha256` | Prior envelope digest |
| `artifact_binding` | Prior artifact revision and artifact digest, with the visible-content digest for the new carrier |
| `authority_receipt` | Authority receipt |
| `decisions` | Nonempty list of unique human decisions |

An author response or human decision inherits `go_eligible` from the prior state. Before round 5,
when a complete pull-request state has `verdict=CONDITIONAL GO`, `next_action=none`, and
`go_eligible=false`, one later reviewer assessment can set `go_eligible=true`. It must increase the
round by one. A repeated `false` value is invalid. An author refresh for a new head can instead move
this state to `awaiting_evidence`. At round 5, an ineligible assessment produces
`phase=decision_required`, `verdict=NO-GO`, and `next_action=human_decision`. A reframe remains
valid.

At round 5, `select_closure` is invalid because it would require round 6. A requirements reframe is
the only event that can change the exchange identity.

The result has these fields:

| Field | Type and value |
| --- | --- |
| `schema_id` | `athena.review-exchange.reduce-result` |
| `schema_version` | Integer `1` |
| `status` | `accepted` or `replayed` |
| `decision` | Decision record |
| `author_event` | Author-event envelope for an accepted author response; otherwise `null` |
| `envelope` | Result state envelope |

The decision record has `phase`, `reason`, `next_role`, `review_round`, `rounds_remaining`, and
`required_remaining`. `next_role` is `author`, `reviewer`, `human`, or `null`. The last three count
fields are nonnegative integers, except that `review_round` is from 1 through 5.

### `verify`

The input is one complete state or author-event envelope. The result is its normalized canonical
envelope. The command rejects a wrong digest or a state that no valid transition can produce.

### `extract`

The input is one UTF-8 Markdown carrier document, not JSON. The result is its normalized canonical
envelope. The document must contain exactly one final carrier section. It must have this form:

````text
<exact visible content>

<!-- HomericIntelligence:review-exchange:v1 kind=<state|author-event> sha256=<digest> -->
```json
<one-line canonical envelope JSON>
```
````

The marker digest, envelope digest, carrier kind, visible-content digest, and provider body limit
must agree. The marker and its JSON fence must be a top-level final section. The visible content
cannot leave a top-level fenced code block open at the carrier boundary.
The final JSON fence must end with a line feed or at the end of input.
No text, spaces, or extra blank lines can follow that fence. The reader preserves
all input bytes for digest and size checks. The renderer continues to emit a final line feed.

### `render`

The JSON request has exactly these fields:

| Field | Type and value |
| --- | --- |
| `visible_content` | Exact string before the carrier; an empty string is valid |
| `envelope` | State or author-event envelope |
| `kind` | `state` or `author-event`, as applicable to the envelope |

The output is the exact carrier document. It ends with a line feed. `visible_content` cannot contain
a review-exchange marker. Its digest must equal `artifact_binding.visible_content_sha256`.

## Pull-request terminal closure manifest

The pull-request delivery helper accepts one canonical JSON closure manifest. It has exactly these
fields:

| Field | Type and value |
| --- | --- |
| `schema_id` | `athena.pr-review.closure-manifest` |
| `schema_version` | Integer `1` |
| `binding` | Exact repository, pull-request number and URL, base object identifier, and head object identifier |
| `state` | Complete terminal pull-request state envelope |
| `terminal_visible_content` | Exact visible content before the terminal state carrier |
| `entries` | Ordered list of existing finding-thread closure entries |
| `requirements_binding` | Exact live pull-request scope and linked-requirements binding |
| `comments` | Ordered list of terminal inline finding entries |
| `summary_finding_ids` | Ordered list of terminal-round nonanchorable finding identities |

A `requirements_binding` has exactly these fields:

| Field | Type and value |
| --- | --- |
| `reviewed_scope_sha256` | Digest of the canonical live pull-request scope |
| `requirements_sha256` | Aggregate digest of the canonical linked requirements |
| `requirement_issue_urls` | Canonical sorted set of selected requirement-issue URLs |

For pull-request delivery, the state `artifact_binding.sha256` equals
`reviewed_scope_sha256`, and the state `requirements_sha256` equals the binding
`requirements_sha256`. The surface adapter recomputes this binding at preflight, immediately before
each write, and after final readback. A mismatch, coverage gap, or operational failure withholds the
state-dependent write or favorable result.

The terminal closure manifest requires `phase=complete`, `verdict=GO`,
`next_action=finalize`, and `go_eligible=true`. A current exact conditional state is valid evidence
only for the exclusive implementation `NO-GO` label path.

A closure entry has exactly these fields:

| Field | Type and value |
| --- | --- |
| `thread_id` | Exact review-thread identity |
| `finding_id` | Exact state finding identity |
| `finding_exchange_id` | Exchange that owns the finding identity |
| `finding_state_sha256` | Exact selected state that contains the finding |
| `superseding_state_sha256` | Exact direct reframe-child state for a historical withdrawal, or `null` for a current finding |
| `origin_comment_id` | Exact root-comment identity |
| `origin_review_head_oid` | Exact head that the root comment reviewed |
| `conversation_sha256` | Digest of the complete current thread conversation |
| `finding_disposition` | Exact state finding disposition |
| `author_event_review_id` | Exact author-event review identity, or `null` |
| `author_answer` | Exact stored author-answer kind, or `null` |
| `author_artifact_revision` | Exact stored corrective revision, or `null` |
| `reviewer_disposition` | `resolved`, `withdrawn`, `accepted_risk`, or `nonblocking` |
| `closure_evidence` | Nonempty exact state evidence list |
| `authority_receipt` | Exact stored authority receipt, or `null` |

The pair of `finding_exchange_id` and `finding_id` is unique in the manifest. A current finding uses
the terminal state digest as `finding_state_sha256` and has no superseding digest. A historical
finding uses one state from the selected terminal supersession ancestry and names its exact direct
reframe child. Its reviewer disposition is `withdrawn`. Its authority receipt equals the child's
verified supersession receipt. Its closure evidence identifies the superseded state. Preserve an
exact author answer when the selected source state has one. Otherwise, all author-answer fields are
`null`; do not infer an answer from prose. Omit an already-resolved historical thread. An unrelated,
foreign, or ambiguous open thread withholds terminal delivery.

A terminal inline finding entry has exactly these fields:

| Field | Type and value |
| --- | --- |
| `path` | Nonempty safe relative repository path |
| `side` | `LEFT` or `RIGHT` |
| `line` | Positive integer causal line |
| `body` | Nonempty finding body with one final exact exchange and finding marker |

Replay the terminal event to determine which findings it introduced. An anchorable finding has an
exact state location of `<relative-path>:<positive-line>`. Put each anchorable terminal-round
finding in `comments` with the same path and line. Put each other terminal-round finding identity in
`summary_finding_ids`. Both lists are ordered by finding identity and contain no duplicate. They do
not overlap, and their union is the exact terminal-round finding set. Both lists can be empty.

The delivery helper publishes `terminal_visible_content`, its state carrier, and the complete
`comments` list in one exact-head `COMMENT` review. Readback must bind each inline root to that
review, head, path, side, line, body, exchange, and finding. The helper derives new thread identities
after readback. It then generates the closure responses. It does not accept arbitrary closure prose.
The current forge record for each authority receipt must pass the common action-bound record check
and prove `ADMIN` or `MAINTAIN` repository permission before a state-dependent write.

## `issue_exchange.py`

### Issue snapshot

The `inspect` command takes an issue snapshot directly. Each other issue command contains a snapshot
in its request. The snapshot has these fields:

| Field | Type and value |
| --- | --- |
| `schema_id` | `athena.issue-exchange.snapshot` |
| `schema_version` | Integer `1` |
| `target` | Issue target |
| `actor` | Authenticated actor |
| `issue` | Issue record |
| `comments` | Ordered list of complete top-level issue comments |
| `comments_complete` | Exact Boolean `true` after complete provider pagination |

An issue target has `provider`, `host`, `repository`, `issue_id`, `number`, and `url`. `provider` is
`github` or `gitlab`. `number` is an integer of at least 1. Each other field is a nonempty string.
The reducer uses `provider`, `repository`, `number`, and `url` as the common review target.

An actor has `id` and `login`. `id` is a nonempty stable actor identity. `login` is a string and can
be empty. An issue record has `state`, `title`, `body`, and `acceptance_criteria`. `state` is `open`
or `closed`. `title` and `body` are strings and can be empty. Each acceptance criterion has the
nonempty string fields `id`, `text`, and `source`. Criterion identities are unique.

Each comment has `id`, `url`, `author`, and `body`. `id` and `url` are nonempty strings. A comment
author has `id`, `login`, and `is_authority`. The first two fields have the same rules as the snapshot
actor fields. `is_authority` is a Boolean. `body` is a string and can be empty. Comment identities
are unique. The snapshot producer must exhaust the provider's bounded comment pagination and then
set `comments_complete` to `true`. A missing or false value rejects the snapshot. The helper does
not infer completeness from an empty or short list. The snapshot must contain all top-level
comments that can own a canonical plan or review marker.

The current requirements digest is the digest of canonical JSON with `schema_id` set to
`athena.issue-exchange.requirements`, `schema_version` set to `1`, and the exact `target`, issue
`title`, issue `body`, and `acceptance_criteria` from the normalized snapshot.

### Issue artifact records

An issue artifact summary has `id`, `author_id`, and `body_sha256`. The first two values are nonempty
strings. `body_sha256` is the exact body digest.

A prepared comment operation has these fields:

| Field | Type and value |
| --- | --- |
| `action` | `create` or `update` |
| `artifact` | `plan` or `review` |
| `comment_id` | `null` for `create`; retained comment identity for `update` |
| `expected_body_sha256` | `null` for `create`; retained body digest for `update` |
| `body` | Exact body to publish |
| `body_sha256` | Digest of `body` |
| `operation_sha256` | Digest of canonical JSON for the other six fields |

A prepared issue-comment result has these fields:

| Field | Type and value |
| --- | --- |
| `schema_id` | `athena.issue-exchange.prepare-result` |
| `schema_version` | Integer `1` |
| `status` | `ready` or `withheld` |
| `requirements_sha256` | Current requirements digest |
| `precondition_sha256` | Digest of the exact issue-comment precondition |
| `target` | Exact issue target |
| `actor_id` | Authenticated stable actor identity |
| `peer` | Other canonical artifact summary or `null` |
| `state` | Result state record or `null` |
| `state_sha256` | Digest of `state` or `null` |
| `authority_receipt` | Reframe-plan authority receipt, or `null` for all other results |
| `next_action` | `prepare_plan`, `prepare_review`, `author_response`, `review_assessment`, `finalize`, `human_decision`, or `none` |
| `operation` | Prepared comment operation or `null` |
| `diagnostics` | List of diagnostic records |

A diagnostic record has the nonempty string fields `code` and `message`. A `ready` result has an
operation and an empty diagnostic list. A `withheld` result has no operation and has a diagnostic.

The issue-comment precondition is the digest of canonical JSON with `schema_id` set to
`athena.issue-exchange.precondition`, `schema_version` set to `1`, and these fields: exact issue
`target`, `actor_id`, `requirements_sha256`, canonical plan summary or `null`, canonical review
summary or `null`, and `authority_receipt`. The authority receipt is non-null only for a reframe-plan
operation. Thus, publication verification can detect authority-comment drift during that first
reframe phase.

### `inspect`

The input is one issue snapshot. The result has these fields:

| Field | Type and value |
| --- | --- |
| `schema_id` | `athena.issue-exchange.inspect-result` |
| `schema_version` | Integer `1` |
| `status` | `ready`, `withheld`, or `finalized` |
| `requirements_sha256` | Current requirements digest |
| `precondition_sha256` | Current issue-comment precondition digest |
| `plan` | Canonical plan summary or `null` |
| `review` | Canonical review summary or `null` |
| `envelope` | Current reduced state envelope or `null` |
| `state` | Current state record or `null` |
| `state_sha256` | Current state digest or `null` |
| `next_action` | `prepare_plan`, `prepare_review`, `finalize`, `human_decision`, or `none` |
| `diagnostics` | List of diagnostic records |

The command does not infer answers from unversioned prose. It returns `withheld` for a malformed,
duplicate, foreign, stale, or conflicting canonical artifact. A valid finalized issue returns
`finalized` and `next_action=none`.

An unchanged finalized body stays terminal. A body that keeps a finalization marker but no longer
matches its `F` digest is malformed and stays withheld. After an authoritative person replaces the
sealed body with clean requirements and removes the obsolete finalization marker, `inspect` starts a
new round-1 epoch. It does not treat the generated finalized plan or sealed provenance as new
requirements.

After a verified reframe-plan publication, the plan contains the new author-event carrier while the
review still contains the exact old retained v1 state. `inspect` recognizes only this narrow
pending-reframe pair. It requires the deterministic new exchange identity, current requirements,
same target and comment identities, empty responses, an exact prior-state binding, and one live
action-bound authority record for the reframe. It returns `ready` and
`next_action=prepare_review`, with the old envelope as the reframe context. The next `prepare-review`
request must still supply and verify that live authority receipt explicitly.

### `prepare-plan`

The request has exactly `snapshot`, `content`, and `event`. `snapshot` is an issue snapshot.
`content` is nonempty visible plan content without an Athena artifact marker. A normal plan event
has these fields:

| Field | Type and value |
| --- | --- |
| `scope` | Nonempty list of unique scope-target objects |
| `scope_change_reason` | Nonempty string when a continued plan changes scope; otherwise `null` |
| `responses` | Empty list for the initial plan; otherwise one response for each required finding that the transition must answer |

Each scope target has `kind` and `value`. `value` is a nonempty string. `kind` is `path`, `module`,
`interface`, `workflow`, `dependency`, `migration`, or `command`. The helper normalizes it to
`<kind>:<value>` in the common state scope.

A reframe plan event has exactly these fields:

| Field | Type and value |
| --- | --- |
| `event_type` | `reframe` |
| `previous` | Exact retained v1 review-state envelope, including a `complete` review |
| `authority_receipt` | Exact live authority receipt for the requirements supersession |
| `scope` | Nonempty list of unique scope-target objects for the new requirements |

The reframe snapshot must contain the same retained plan and review comments, with changed
requirements. The helper verifies the receipt against one noncanonical comment in the normalized
current snapshot whose author has `is_authority=true`. The comment body must be an exact `reframe`
authority record for the new exchange, new requirements, current target, and old state digest. The
helper makes a new exchange identity and binds it to the prior state digest. The plan author-event
carrier does not persist the receipt. The prepared result carries the receipt only for publication
verification. `prepare-review` must receive and verify the authority receipt again.

The retained review envelope must be the current logical state of the old exchange. The plan-source
token in the retained review must bind the retained plan. If the plan contains a valid pending author
event that the review has not accepted, `prepare-plan` rejects the reframe. Complete and verify a
reviewer assessment before the requirements change. The adapter does not overwrite the sole
pending-event carrier or supersede a stale persisted state.

The result is a prepared issue-comment result. A ready initial result prepares one `create` operation
for the canonical plan comment. A ready continued result prepares one `update` operation for that
same comment. Its body has the latest author-event carrier. The helper does not prepare a plan when
the exchange awaits a reviewer, is complete, or requires a human decision, unless the request is an
authorized reframe with changed requirements.

Before a review exists, an initial plan carrier can use only the exact plan-comment identity or
`pending:<visible_content_sha256>` as its artifact revision. If the requirements change before any
review exists, `inspect` can select `prepare_plan` for a fresh initial exchange on the same plan
comment. This case has no prior review state to supersede.

### `prepare-review`

The request has exactly `snapshot`, `content`, and `event`. `snapshot` is an issue snapshot.
`content` is nonempty visible review content without an Athena artifact marker. `event` is one of
these three exact event forms.

A reviewer-assessment event has these fields:

| Field | Type and value |
| --- | --- |
| `event_type` | `reviewer_assessment` |
| `coverage_complete` | Boolean |
| `responses` | Empty for round 1; otherwise one reviewer response for each prior author answer |
| `new_findings` | Ordered list of finding inputs |
| `stop_reason` | `null` or a common stop reason |
| `legacy_import` | Boolean; use `true` only for an explicit in-place import of an active unversioned review |
| `scope` | List of scope-target objects. An empty list selects the targets from a versioned plan. A nonempty list must equal those targets. A legacy import requires a nonempty list. |

An authoritative-human event has these fields:

| Field | Type and value |
| --- | --- |
| `event_type` | `human_decision` |
| `authority_receipt` | Authority receipt |
| `decisions` | Nonempty list of unique human decisions |

The authority reference must identify one exact live noncanonical issue comment by its identity or
URL. That comment must have `is_authority=true`. Its body digest must equal
`authority_receipt.sha256`. Its body must be an exact `human_decision` authority record for the
current target, exchange, requirements, prior state, and decision list. The helper derives the
prior state and artifact binding from the canonical comments.

A reframe review event has these fields:

| Field | Type and value |
| --- | --- |
| `event_type` | `reframe` |
| `previous` | Same verified old state envelope that the reframe plan used |
| `authority_receipt` | Exact live authority receipt for the requirements supersession |
| `coverage_complete` | Boolean |
| `responses` | Empty list |
| `new_findings` | Ordered list of initial finding inputs for the new exchange |
| `stop_reason` | `null` or a common stop reason |
| `legacy_import` | Boolean `false` |
| `scope` | Nonempty list of scope-target objects that equals the reframe plan targets |

The helper verifies the exact action-bound reframe record again from the current snapshot. The
resulting state stores the verified receipt in `supersession_authority_receipt`. The issue adapter
sets `go_eligible=true` on each generated common reviewer assessment and reframe. The issue request
does not accept this field.

The result is a prepared issue-comment result. Round 1 creates the canonical review comment only
when it is absent. A continuation updates that same comment. The helper inserts this generated
top-level marker in the visible content:

```text
<!-- HomericIntelligence:reviewed-plan:v1 token=<source-token> -->
```

The source token is the digest of canonical JSON with the exact `comment_id` and `body_sha256` of
the plan. The review body then ends with the complete state carrier. A terminal review still
produces this update when it has no new finding.

### `verify-publication`

The request has exactly `prepared` and `snapshot`. `prepared` is the exact ready result from
`prepare-plan` or `prepare-review`. `snapshot` is the complete readback after the caller makes the
one prepared comment operation.

The result has these fields:

| Field | Type and value |
| --- | --- |
| `schema_id` | `athena.issue-exchange.publication-result` |
| `schema_version` | Integer `1` |
| `status` | `verified` or `unknown_outcome` |
| `state` | Prepared result state or `null` |
| `state_sha256` | Prepared state digest or `null` |
| `receipt` | Publication receipt or `null` |
| `diagnostics` | List of diagnostic records |

A publication receipt has these fields:

| Field | Type and value |
| --- | --- |
| `operation_sha256` | Prepared operation digest |
| `action` | Prepared `create` or `update` action |
| `artifact` | Prepared `plan` or `review` role |
| `comment_id` | Nonempty readback comment identity |
| `url` | Nonempty readback comment URL |
| `body_sha256` | Prepared and read-back body digest |
| `verified_precondition_sha256` | Prepared precondition digest |

These values bind the exact prepared operation and readback. An `unknown_outcome` result has no
receipt. It does not authorize a retry. Readback repeats canonical marker identity checks and live
action-bound authority verification. For a reframe-plan publication, it uses the ephemeral prepared
`authority_receipt` and requires `inspect` to recognize the exact live peer as the superseded state
of the pending reframe. For a review publication, it uses the receipts in the result state.

For a corrective plan publication, verification reduces the exact live retained review state with
the published author-event carrier. The derived state and digest must equal the prepared result.
Thus, a separately valid result state cannot replace the prepared continuation.

### `verify-finalize`

The command has two request forms. To prepare finalization, use exactly `snapshot` and
`candidate_body`. `snapshot` is the current issue snapshot. `candidate_body` is nonempty final plan
content without a finalization marker. To verify issue-body readback, use exactly `snapshot` and
`prepared`. `prepared` is the exact ready finalization result. The helper selects the request form by
its exact field set.

A ready or verified finalization result has these fields:

| Field | Type and value |
| --- | --- |
| `schema_id` | `athena.issue-exchange.finalize-result` |
| `schema_version` | Integer `1` |
| `status` | `ready` or `verified` |
| `requirements_sha256` | Current requirements digest |
| `requirements_context_sha256` | Digest of the target, issue state, title, and acceptance criteria |
| `target` | Exact issue target |
| `actor_id` | Authenticated stable actor identity |
| `precondition_sha256` | Exact finalization precondition digest |
| `state` | Exact terminal issue state record |
| `state_sha256` | Terminal state digest |
| `sources` | Exact `R`, `P`, and `V` source record |
| `operation` | Prepared issue-body replacement operation |
| `deletion_allowlist` | Exact plan and review comment identities |
| `remaining_comment_ids` | Empty list |
| `diagnostics` | Empty list |

`sources.R` is the requirements digest. `sources.P` and `sources.V` each have `token`, `comment_id`,
and `body_sha256`. The source token is the digest of canonical JSON with `comment_id` and
`body_sha256`.

The issue-body replacement operation has `action`, `expected_issue_body_sha256`, `body`,
`body_sha256`, `F`, and `operation_sha256`. `action` is `replace_body`. `F` binds the finalization
marker template. `operation_sha256` is the digest of canonical JSON for the other five fields.

The finalization precondition is the digest of canonical JSON with `schema_id` set to
`athena.issue-exchange.finalize-precondition`, `schema_version` set to `1`, and these fields: exact
issue `target`, `actor_id`, `requirements_sha256`, `requirements_context_sha256`, `state_sha256`,
plan summary, review summary, and `expected_issue_body_sha256`. Thus, changing the expected issue
body and recomputing only the operation digest does not make a valid prepared finalization.
`requirements_context_sha256` binds the issue workflow state through preparation and readback. The
helper permits an open or closed issue and does not change that state.

A non-ready finalization result has these fields:

| Field | Type and value |
| --- | --- |
| `schema_id` | `athena.issue-exchange.finalize-result` |
| `schema_version` | Integer `1` |
| `status` | `withheld`, `unknown_outcome`, `partial_cleanup`, or `no_change` |
| `requirements_sha256` | Requirements digest or `null` |
| `state` | `null`, except that an unknown outcome retains the prepared state |
| `state_sha256` | `null`, except that an unknown outcome retains the prepared digest |
| `sources` | `null`, except that an unknown outcome retains the prepared sources |
| `operation` | `null` |
| `deletion_allowlist` | Empty list |
| `remaining_comment_ids` | Sealed intermediate-comment identities only for `partial_cleanup`; otherwise empty |
| `diagnostics` | Nonempty list of diagnostic records |

Finalization requires a current matching requirements digest, plan source, review source, exact GO
state, complete coverage, terminal ledger, and each required authority receipt. The current plan
carrier must equal the last accepted author response in that ledger. For a round-1 GO with no author
response, it must equal the initial plan event that the first assessment binds. Finalization does
not make a review assessment. Readback verifies each live action-bound authority record again before
it returns `verified`. A verified result authorizes cleanup only for `deletion_allowlist`. After an
unknown outcome, do not retry the body replacement.
