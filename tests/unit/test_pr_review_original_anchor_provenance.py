"""Original source proofs remain bound to published bytes after state migration."""

from __future__ import annotations

import copy
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from tests.unit.test_pr_review_anchor_proofs import assert_no_write, git, legacy_case
from tests.unit.test_pr_review_anchor_proofs import source as git_source
from tests.unit.test_pr_review_go_delivery import FakeForge
from tests.unit.test_review_legacy_history import legacy_prefixes, original_document

source = git_source


def migrated_case(
    source: tuple[Path, str, str], *, compressed: bool = True
) -> tuple[Any, Any, Any, Any]:
    """Continue an unchanged legacy review and answer with a current review."""
    delivery, forge, binding, proof = legacy_case(source)
    exchange = delivery.review_exchange
    initial = proof.state_envelope
    (source[0] / "correction.txt").write_text("The proposed correction.\n")
    git(source[0], "add", "correction.txt")
    git(source[0], "commit", "-qm", "fixture correction")
    current_head = git(source[0], "rev-parse", "HEAD")
    binding = replace(binding, head_oid=current_head)
    author_visible = "Both required findings have a proposed correction."
    author = exchange.reduce_request(
        {
            "previous": initial,
            "event": {
                "event_type": "author_response",
                "exchange_id": initial["state"]["exchange_id"],
                "prior_state_sha256": initial["state_sha256"],
                "artifact_binding": {
                    **initial["state"]["artifact_binding"],
                    "revision": current_head,
                    "visible_content_sha256": exchange.sha256_text(author_visible),
                },
                "scope": initial["state"]["scope"],
                "scope_change_reason": None,
                "responses": [
                    {
                        "finding_id": finding["id"],
                        "kind": "fix",
                        "evidence": ["A correction is available for source review."],
                        "tradeoff": None,
                    }
                    for finding in initial["state"]["findings"]
                ],
            },
        }
    )
    answered = author["envelope"]
    visible = "The correction is partial. Both findings remain required."
    terminal = exchange.reduce_request(
        {
            "previous": answered,
            "event": {
                "event_type": "reviewer_assessment",
                "exchange_id": initial["state"]["exchange_id"],
                "prior_state_sha256": answered["state_sha256"],
                "round": 2,
                "artifact_binding": {
                    **answered["state"]["artifact_binding"],
                    "visible_content_sha256": exchange.sha256_text(visible),
                },
                "scope": initial["state"]["scope"],
                "coverage_complete": True,
                "responses": [
                    {
                        "finding_id": finding["id"],
                        "kind": "partial",
                        "evidence": ["The correction does not satisfy the finding."],
                        "closure_condition": None,
                    }
                    for finding in initial["state"]["findings"]
                ],
                "new_findings": [],
                "stop_reason": None,
            },
        }
    )["envelope"]
    originals, authors = legacy_prefixes(exchange, terminal)
    original = originals[initial["state_sha256"]]
    record = forge.reviews[0]

    class CurrentForge(FakeForge):
        def snapshot(self) -> Any:
            return replace(
                super().snapshot(), base_oid=source[1], head_oid=current_head
            )

    original_labels = set(forge.labels)
    forge = CurrentForge(delivery, threads=tuple(forge.threads.values()))
    forge.labels = original_labels
    forge.reviews[:] = [
        replace(
            record,
            body=original_document(
                proof.visible_content, original, compressed=compressed
            ),
        ),
        replace(
            record,
            id="legacy-author",
            head_oid=current_head,
            body=original_document(
                author_visible,
                authors[author["author_event"]["state_sha256"]],
                compressed=compressed,
            ),
            submitted_at="2026-01-01T00:01:00Z",
        ),
        replace(
            record,
            id="current-review",
            head_oid=current_head,
            body=exchange.render_carrier(visible, terminal, "state"),
            submitted_at="2026-01-01T00:02:00Z",
        ),
    ]
    historical = {
        **proof.historical_anchor_proofs[0],
        "state_sha256": original["state_sha256"],
    }
    assert historical["state_sha256"] != initial["state_sha256"]
    return (
        delivery,
        forge,
        binding,
        replace(
            proof,
            state_envelope=terminal,
            visible_content=visible,
            review_id="current-review",
            historical_anchor_proofs=(historical,),
        ),
    )


@pytest.mark.parametrize("compressed", [False, True])
def test_original_proof_survives_verified_legacy_history_without_digest_alias(
    source: tuple[Path, str, str], compressed: bool
) -> None:
    delivery, forge, binding, proof = migrated_case(source, compressed=compressed)
    original_records = tuple(forge.reviews)
    original_proof = copy.deepcopy(proof.historical_anchor_proofs)
    original_state = copy.deepcopy(proof.state_envelope)

    assert delivery.deliver_no_go(forge, binding, proof).status == "delivered"

    assert tuple(forge.reviews) == original_records
    assert proof.historical_anchor_proofs == original_proof
    assert proof.state_envelope == original_state
    assert forge.labels == {"state:implementation-no-go"}
    assert len(forge.threads) == 1
    assert [f["id"] for f in original_state["state"]["findings"]] == [
        "F-001",
        "F-002",
    ]
    assert all(
        finding["disposition"] == "required" and finding["state"] == "partial"
        for finding in original_state["state"]["findings"]
    )


@pytest.mark.parametrize(
    "defect",
    [
        "normalized_digest_alias",
        "unrelated_proof",
        "wrong_review",
        "wrong_visible_digest",
        "wrong_head",
        "wrong_base",
        "wrong_merge_base",
        "wrong_summary_set",
        "duplicate_proof",
        "changed_body",
        "edited_review",
        "foreign_owner",
        "wrong_review_head",
        "missing_inline_root",
        "duplicate_carrier",
        "missing_author",
    ],
)
def test_migration_keeps_original_proof_and_inline_ownership_checks(
    source: tuple[Path, str, str], defect: str
) -> None:
    delivery, forge, binding, proof = migrated_case(source)
    historical = copy.deepcopy(proof.historical_anchor_proofs[0])
    proofs: tuple[dict[str, Any], ...] = (historical,)
    record = forge.reviews[0]
    if defect == "normalized_digest_alias":
        historical["state_sha256"] = delivery.review_exchange.extract_carrier(
            record.body
        )["state_sha256"]
    elif defect == "unrelated_proof":
        proofs += ({**historical, "state_sha256": "f" * 64},)
    elif defect == "wrong_review":
        historical["review_id"] = "another-review"
    elif defect == "wrong_visible_digest":
        historical["visible_content_sha256"] = "f" * 64
    elif defect in {"wrong_head", "wrong_base", "wrong_merge_base"}:
        historical[defect.removeprefix("wrong_") + "_oid"] = "f" * 40
    elif defect == "wrong_summary_set":
        historical["finding_ids"] = ["F-001", "F-002"]
    elif defect == "duplicate_proof":
        proofs += (copy.deepcopy(historical),)
    elif defect == "changed_body":
        forge.reviews[0] = replace(record, body="Changed. " + record.body)
    elif defect == "edited_review":
        forge.reviews[0] = replace(record, includes_created_edit=True)
    elif defect == "foreign_owner":
        forge.reviews[0] = replace(record, viewer_did_author=False)
    elif defect == "wrong_review_head":
        forge.reviews[0] = replace(record, head_oid="f" * 40)
    elif defect == "missing_inline_root":
        forge.threads.clear()
    elif defect == "duplicate_carrier":
        forge.reviews.append(replace(record, id="duplicate-review"))
    else:
        del forge.reviews[1]
    proof = replace(proof, historical_anchor_proofs=proofs)

    with pytest.raises(delivery.DeliveryError):
        delivery.deliver_no_go(forge, binding, proof)

    assert_no_write(forge)
