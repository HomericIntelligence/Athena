# Requirement-to-evidence review contract

**Why:** A review that stops after its first visible defect makes the author correct one item, then
re-review, then find another item that was visible in the first pass. This contract makes one review
pass return one complete set of material findings for the bound requirements and the bound source.

This document defines the review result. It does not prescribe how an author implements a change.

## Component ownership

| Component | Owns |
| --- | --- |
| [`skills/review-exchange/scripts/requirement_evidence.py`](../../skills/review-exchange/scripts/requirement_evidence.py) | The pure expected inventory, assessed rows, findings batch, section comparison, and map rendering. |
| [`skills/change-review/scripts/review_evidence.py`](../../skills/change-review/scripts/review_evidence.py) | The read-only local adapter that prepares and finalizes one local change-review result. |
| [`skills/change-review/scripts/resolve_scope.py`](../../skills/change-review/scripts/resolve_scope.py) | Exact scope binding and dependency content identities. |
| The invoking review skill | Requirement enumeration, section assignment, and the assessed rows. |

The shared module is pure. It does not execute reviewed code, read the network, publish a review, or
grant authority.

## Independent expected inventory

Build the inventory before the reviewer submits assessed rows. The inventory is a separate input.
Never derive it from submitted rows or from findings.

| Field | Purpose |
| --- | --- |
| `requirements_binding` | Exact task or issue identity and its content digest. |
| `artifact_binding` | Exact plan, commit, index, or worktree identity. |
| `scope_binding` | Complete selected path set and its digest. |
| `requirements` | Enumerated acceptance criteria and applicable contracts, each with a stable identifier and a source reference. |
| `sections` | Review sections with their paths, declared section dependencies, and their source dependencies. |
| `expected_cells` | Every combination of requirement, section, and evidence surface. |
| `inventory_sha256` | Digest of the complete canonical inventory. |

The surfaces are `implementation`, `tests`, `documentation`, and `operations`.

Every selected scope path must be assigned to one section. An unassigned path is rejected. Each
expected cell must receive one assessed row. Mark a cell not applicable only with a reason.

Freeze `inventory_sha256` before assessment. Pass the expected inventory and the assessment as
separate arguments. An assessment cannot replace or shrink the inventory. A source or contract change
requires an explicit inventory update with the old digest, the new digest, and a change cause.

This check proves structural completeness against the independent inventory. It does not prove that
the reviewer found every requirement or that a finding is technically correct.

## Assessed rows

One row records:

| Field | Contract |
| --- | --- |
| `requirement`, `section`, `surface` | The assessed cell. It must be one expected cell. |
| `result` | `covered`, `missing_coverage`, `incorrect_implementation`, or `not_applicable`. |
| `reason` | Required only for `not_applicable`. |
| `evidence` | One or more references for an applicable cell. |
| `finding_ids` | Required for a material result, forbidden otherwise. |
| `dependencies` | The content identities of the section paths and declared section dependencies. |

Missing requirement coverage and an incorrect implementation are different results. A material result
names at least one finding. The findings batch is assembled only after every expected cell has an
assessment.

A reviewer can recommend a method. A mandatory implementation method needs a repository policy or a
documented safety or security boundary. A map row does not add an approval stage. The coverage record
is review evidence, not workflow authority.

## Selective repetition

Retain a section only when its requirements, declared section dependencies, source content, modes, and
applicable scope remain equivalent.

| Cause | Repeated section |
| --- | --- |
| `first_review` | No prior record exists. |
| `dependency_changed` | A section dependency content identity changed. |
| `finding_corrected` | The author corrected a finding that the section reported. |
| `requirements_changed` | The requirements identity changed. |
| `no_verified_dependency_evidence` | The prior record has no verified dependency identities. |

Each repeated section names its cause. A compatible base change or a signature-only rewrite preserves
applicable technical evidence when the dependencies are equivalent. The returned result binds the new
artifact identity. Technical evidence reuse never transfers approval, accepted-risk authority, a
current-head test receipt, or merge permission.

## Local change-review interface

`skills/change-review/scripts/review_evidence.py` is read-only. Both commands read bounded JSON from
standard input and return JSON on standard output. The adapter writes no record into the repository
and creates no storage or exchange authority.

| Command | Input | Output |
| --- | --- | --- |
| `prepare` | Scope selectors, the frozen expected inventory, the review section assignment, the corrected findings, and an optional prior record with the caller-retained record digest. | The current scope binding, the inventory digest, the retained sections, the sections that need assessment with a cause each, and a preparation digest. |
| `finalize` | The preparation and the assessed rows for the repeated sections. | The evidence record and its digest, the complete findings batch, the compact requirement-to-evidence map, the retained sections, and the repeat causes. |

Rules:

- A prior record needs the digest that the caller retained with its own review result. A digest
  supplied only inside the record is not provenance.
- An invalid prior record is rejected with a specific diagnostic and no completeness claim. Do not
  discard it silently.
- `finalize` resolves the current scope again. Source drift after preparation is a failure, not a
  merge.
- A retained section keeps its retained rows. Assess only the repeated sections.
- An invocation without prior evidence starts a complete review.
- The caller retains the returned record outside the reviewed source and supplies it on the next
  invocation.

## Version compatibility and rollback

A review state that carries the requirement-evidence record uses envelope version 3. Version 1 and
version 2 records keep their original digests and historical replay rules. A record without
dependency evidence cannot authorize selective reuse.

- Deploy the new reader and writer together with their surface adapters.
- If the new writer is withdrawn, preserve every version 3 record unchanged. Do not downgrade,
  delete, overwrite, or start a replacement exchange to bypass one.
- An older reader rejects version 3 as unsupported before any publication or state change. Restore a
  compatible reader to continue that exchange.
- Test rollback with a historical-reader fixture that rejects the new record and performs no write.

## Limits

Keep the existing input, finding, event, and carrier limits. If a limit prevents complete assessment
or delivery, report the gap. Never truncate a batch and claim completeness. Source, secret,
untrusted-code, and production-authority boundaries do not change.
