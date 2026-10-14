#!/usr/bin/env python3
"""Publish one validated non-terminal reviewer round batch for GitHub."""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

sys.path.insert(0, str(Path(__file__).resolve().parent))

import anchor_proofs
import deliver_go

if TYPE_CHECKING:
    from skills._cli import argument_parser
else:
    argument_parser = deliver_go.argument_parser

RESULT_SCHEMA_ID = "athena.pr-review.round-publication"


def _carrier_body(
    path: Path, binding: deliver_go.ReviewBinding
) -> tuple[str, dict[str, Any]]:
    """Return the verified reviewer state carrier body and its envelope."""
    try:
        body = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise deliver_go.DeliveryError(
            f"The reviewer state carrier cannot be read: {error}"
        ) from error
    exchange = deliver_go.review_exchange
    try:
        envelope = exchange.extract_carrier(body)
    except exchange.ProtocolError as error:
        raise deliver_go.DeliveryError(
            f"The reviewer state carrier is invalid: {error}"
        ) from error
    state = envelope["state"]
    if (
        envelope["schema_id"] != exchange.STATE_SCHEMA_ID
        or state["artifact_binding"]["revision"] != binding.head_oid
        or state["target"]["number"] != binding.number
        or state["target"]["repository"] != binding.repository
    ):
        raise deliver_go.DeliveryError(
            "The reviewer state carrier is not bound to the requested pull request."
        )
    return body, envelope


def _batch_comments(path: Path, exchange_id: str) -> tuple[dict[str, Any], ...]:
    """Verify one inline batch against the shared marker and bound rules."""
    exchange = deliver_go.review_exchange
    document = deliver_go._read_json_document(
        path, "reviewer round finding batch", canonical=False
    )
    try:
        result = exchange.verify_finding_batch(document)
    except exchange.ProtocolError as error:
        raise deliver_go.DeliveryError(str(error)) from error
    if result["exchange_id"] != exchange_id:
        raise deliver_go.DeliveryError(
            "The reviewer round finding batch has a different exchange ID."
        )
    if not isinstance(document, dict) or not isinstance(document.get("comments"), list):
        raise deliver_go.DeliveryError(
            "The reviewer round finding batch has no comment list."
        )
    comments = tuple(cast(dict[str, Any], comment) for comment in document["comments"])
    if len(comments) != result["comment_count"]:
        raise deliver_go.DeliveryError(
            "The reviewer round finding batch changed during verification."
        )
    return comments


def _verify_anchor_annex(
    visible: str, anchor_source: Path | None, binding: deliver_go.ReviewBinding
) -> None:
    """Require the publication anchor annex to bind the current base and head."""
    try:
        annex = anchor_proofs.visible_manifest(visible)
    except ValueError as error:
        raise deliver_go.DeliveryError(str(error)) from error
    if annex is None:
        if anchor_source is not None:
            raise deliver_go.DeliveryError(
                "The reviewer state carrier has no publication anchor annex."
            )
        return
    if annex["head_oid"] != binding.head_oid or annex["base_oid"] != binding.base_oid:
        raise deliver_go.DeliveryError(
            "The publication anchor annex is not bound to the reviewed identity."
        )


def _readback_anchor(comment: Mapping[str, Any]) -> tuple[str, str, int, str]:
    """Return one comparable anchor identity for one inline finding."""
    path = comment.get("path")
    side = comment.get("side")
    line = comment.get("line")
    body = comment.get("body")
    if (
        not isinstance(path, str)
        or not isinstance(side, str)
        or type(line) is not int
        or not isinstance(body, str)
        or side not in {"LEFT", "RIGHT"}
        or line < 1
    ):
        raise deliver_go.DeliveryError(
            "The reviewer round finding batch has an invalid inline comment."
        )
    return path, side, line, body


def _verify_readback(
    forge: deliver_go.GitHubForge,
    binding: deliver_go.ReviewBinding,
    body: str,
    review_id: str,
    comments: tuple[dict[str, Any], ...],
) -> None:
    """Verify the published round against the exact provider readback."""
    snapshot = forge.snapshot()
    deliver_go._require_binding(snapshot, binding)
    reviews = [review for review in snapshot.reviews if review.id == review_id]
    if len(reviews) != 1:
        raise deliver_go.DeliveryError(
            "The published reviewer round has no unique readback record."
        )
    review = reviews[0]
    if (
        review.head_oid != binding.head_oid
        or not review.viewer_did_author
        or review.includes_created_edit
        or review.last_edited_at is not None
        or review.state not in {"COMMENT", "COMMENTED"}
        or review.body != body
    ):
        raise deliver_go.DeliveryError(
            "The published reviewer round changed during readback."
        )
    expected = {_readback_anchor(comment) for comment in comments}
    actual: set[tuple[str, str, int, str]] = set()
    for thread in snapshot.threads:
        if not thread.comments:
            continue
        root = thread.comments[0]
        if root.review_id != review_id:
            continue
        if root.side not in {"LEFT", "RIGHT"} or type(root.line) is not int:
            raise deliver_go.DeliveryError(
                "A published inline finding has an invalid readback anchor."
            )
        if deliver_go._finding_marker(root) is None:
            raise deliver_go.DeliveryError(
                "A published inline finding has no exact exchange finding marker."
            )
        actual.add((str(root.path), root.side, root.line, root.body))
    if actual != expected:
        raise deliver_go.DeliveryError(
            "The published reviewer round does not own its exact inline batch."
        )


def publish_round(
    forge: deliver_go.GitHubForge,
    binding: deliver_go.ReviewBinding,
    body: str,
    envelope: Mapping[str, Any],
    comments: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    """Publish one validated round batch and return its canonical result document."""
    review_id = forge.publish_round_batch(body, binding.head_oid, comments)
    _verify_readback(forge, binding, body, review_id, comments)
    exchange = deliver_go.review_exchange
    return {
        "schema_id": RESULT_SCHEMA_ID,
        "schema_version": 1,
        "status": "published",
        "review_id": review_id,
        "head_oid": binding.head_oid,
        "exchange_id": envelope["state"]["exchange_id"],
        "state_sha256": envelope["state_sha256"],
        "comment_count": len(comments),
        "bodies_sha256": exchange.sha256_json(
            [comment["body"] for comment in comments]
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Validate one round batch before the single atomic forge write."""
    parser = argument_parser(description=__doc__)
    parser.add_argument("--target-repository", required=True)
    parser.add_argument("--target-host", default=deliver_go.GITHUB_HOST)
    parser.add_argument("pull_request")
    parser.add_argument("--expected-pr-url", required=True)
    parser.add_argument(
        "--base-oid", "--expected-base-oid", dest="base_oid", required=True
    )
    parser.add_argument(
        "--head-oid", "--expected-head-oid", dest="head_oid", required=True
    )
    parser.add_argument("--state-carrier-file", type=Path, required=True)
    parser.add_argument("--batch-file", type=Path, required=True)
    parser.add_argument("--anchor-source", type=Path)
    args = parser.parse_args(argv)
    try:
        binding = deliver_go._binding_from_args(args)
        body, envelope = _carrier_body(args.state_carrier_file, binding)
        comments = _batch_comments(
            args.batch_file, cast(str, envelope["state"]["exchange_id"])
        )
        _verify_anchor_annex(
            deliver_go._carrier_visible(body), args.anchor_source, binding
        )
        forge = deliver_go.GitHubForge(binding, args.target_host)
        result = publish_round(forge, binding, body, envelope, comments)
    except (deliver_go.DeliveryError, RuntimeError, TypeError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    print(deliver_go.review_exchange.canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
