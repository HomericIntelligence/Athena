# Publication anchors and factual source locations

A finding location records where its evidence applies. A location outside the original diff can
remain factual without creating an inline comment. This rule does not change the finding's
severity, required response, disposition, or closure authority.

## Future reviewer carriers

Before a reviewer assessment or reframe is published, prepare the source manifest with
[`anchor_proofs.py`](../scripts/anchor_proofs.py):

```text
python3 <skill>/scripts/anchor_proofs.py \
  --source <complete-immutable-source> \
  --base-oid <reviewed-base-oid> \
  --head-oid <reviewed-head-oid> \
  --findings <ordinary-findings.json>
```

The input is a JSON list of the new ordinary findings. Each item supplies `id`, `location`, and,
for a source location, an optional `side` (`RIGHT` by default, or `LEFT`). Use only the findings that
this reviewer event introduces. Native findings retain their existing native-root contract.

`RIGHT` uses the path and line in the head commit. `LEFT` uses the path and line in the
merge-base commit. For `LEFT`, the file content at the current base must be identical to its
merge-base content. If the content differs or either file is unavailable, the helper rejects the
finding before publication. It does not map line numbers between different base files. This
conservative limit also applies when a base edit is after the finding's line. A target change in
another file does not prevent a `LEFT` anchor. Do not change a factual coordinate to bypass this
limit; retain the unavailable classification until a supported source coordinate can be proved.

The helper reads Git objects. It does not execute repository code or contact the forge. It requires
the repository root, complete history, both exact commits, and one merge base. It reads both author-intent and
current-target ranges.

The helper hashes each complete patch as a stream, in batches of at most 16 MiB.
A batch boundary records progress and continues the same hash. It does not reject a larger patch.
It retains no complete patch in memory. Object reads and per-path diff reads keep their 2 MiB limit.
Diagnostic output has a 16 KiB limit. All queries share one 30-second deadline for the source operation.
A patch hash requires complete output, no stream error, and a successful Git exit before that deadline.

An incomplete or unavailable source fails. It cannot establish that a line is outside the diff.

The result has schema `athena.pr-review.anchor-manifest`, version `1`. It includes the base, head,
merge base, fixed diff policy, both diff hashes, and one ordered entry per finding. An entry is
`inline` with its exact path, side, and line, or `summary` with one of these reasons:

- `outside_bound_hunks`: the factual source line exists and is outside both original hunk sets;
- `non_source_location`: the finding has a prose location rather than a source coordinate.

Append this separate section to the visible review, before calculating its existing
`visible_content_sha256` and rendering the canonical state carrier:

````text
<!-- HomericIntelligence:review-anchors:v1 -->
```json
<the one-line canonical manifest JSON>
```
````

The annex must be the final visible section. Only ASCII spaces, tabs, carriage returns, and line
feeds can follow its closing fence in the visible content. Keep those bytes in the carrier digest.
The canonical exchange carrier follows it. The
existing carrier digest binds the annex; the exchange state schema does not change. Do not add the
annex to an author-event carrier. Before publication, retain the captured base for source
reproduction. Revalidate the exact target, head, requirements, and complete comment batch as required
by the delivery contract.

Supply `--anchor-source <complete-immutable-source>` to version-1 delivery. Verification regenerates
the manifest rather than trusting the proposed classifications. Every ordinary finding must occur
exactly once in the inline or summary set. Inline comments still require their exact marker,
review owner, head, path, side, line, and unchanged root. A missing real inline root blocks delivery.
For a terminal manifest, `comments` and `summary_finding_ids` must match the verified partition.
Append its annex to the exact generated terminal closure ledger. Do not change that ledger.

## Explicit recovery for an existing version-1 carrier

A version-1 carrier without the annex does not bind a base OID in its state fields. Do not use the
current PR diff, branch names, an unattached local file, or a new assertion as historical proof.

The explicit compatibility input is a canonical JSON list passed through
`--historical-anchor-proofs <proofs.json>`, together with `--anchor-source`. Each proof has exactly
these fields:

| Field | Required value |
| --- | --- |
| `schema_id` | `athena.pr-review.historical-anchor-proof` |
| `schema_version` | Integer `1` |
| `target` | Exact carrier provider, repository, number, and URL |
| `review_id` | Exact original published reviewer record ID |
| `state_sha256` | Exact unchanged original state digest |
| `visible_content_sha256` | Exact original visible-text digest |
| `base_oid`, `head_oid`, `merge_base_oid` | Full original Git commit IDs |
| `finding_ids` | Ordered IDs of all factual findings outside both original ranges |
| `witness` | Exact original published source-binding sentence |

The compatibility grammar supports these existing source assertions at the start of the original
visible review:

```text
Reviewed <repository-name> #<number> at `<head>`, against base/merge-base `<base>` (zero commits behind).
```

```text
Default Athena round <round> reviews <repository-name> #<number> at `<head>`, against base and merge base `<base>`.
```

The second form can follow the exact heading `## Bound corrective review` and one blank line.
Either sentence can start a longer paragraph. The round must match the original carrier state.
Repeated assertions, including a mixture of these two forms, are invalid.

All values must match the bound target and proof. The base must actually equal the only merge base.
The original statement must be unambiguous. A different historical format remains unavailable
until a separately reviewed verifier supports it. Do not rewrite a published review to match this
format. The original carrier, review actor, edit state, head, and chronology must pass their existing
checks before this proof is used.

If verified migration changes a state digest, the proof still binds the original digest.
The verifier retains the original envelope from that exact published review. After it verifies
the complete normalized chain and publication order, it uses the original envelope for source
geometry. Only the original digest of a verified published state can select a historical proof.
Do not substitute the normalized digest. Migration does not change the proof or the published
review. Duplicate or ambiguous carrier mappings remain invalid.

The verifier regenerates both original ranges and verifies that the supplied IDs are exactly the
factual summary set. Other source findings still require their original inline roots. A proof for
a state outside the selected chain, a duplicate proof, or a proof combined with an annex for the
same state is invalid. Missing objects, shallow history, wrong identities, changed carrier bytes,
and incorrect classifications prevent every delivery write.

This compatibility proof establishes publication geometry only. It does not create a
`human_decision`, authorize thread resolution, accept risk, remove a required response, or change a
verdict. The original finding stays open until the existing exchange handles it. Base advancement
cannot reclassify the original finding; current delivery identity checks remain separate.

If the original base cannot be proved, stop and retain the evidence gap. A user approval cannot
manufacture missing source evidence. An explicitly authorized reframe is a different operation with
its existing authority requirements.
