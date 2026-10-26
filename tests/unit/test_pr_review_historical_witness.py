"""Historical corrective-review sentences retain exact source and carrier checks."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from tests.unit.test_pr_review_anchor_proofs import (
    assert_no_write,
    git,
    legacy_case,
    rebind_visible,
)
from tests.unit.test_pr_review_anchor_proofs import (
    source as git_source,
)

source = git_source


def corrective_case(
    source: tuple[Path, str, str],
    *,
    heading: str = "## Bound corrective review\n\n",
    suffix: str = " Both original diff ranges were checked.",
) -> Any:
    """Use the published sentence structure with real fixture commit identities."""
    delivery, forge, binding, proof = legacy_case(source)
    witness = (
        f"Default Athena round 1 reviews repository #7 at `{source[2]}`, "
        f"against base and merge base `{source[1]}`."
    )
    visible = heading + witness + suffix
    return (
        delivery,
        forge,
        binding,
        bind_witness(delivery, forge, proof, visible, witness),
    )


def bind_witness(
    delivery: Any, forge: Any, proof: Any, visible: str, witness: str
) -> Any:
    """Bind test review text through the actual carrier encoder, before delivery."""
    updated = rebind_visible(delivery, forge, proof, visible)
    legacy = {
        **proof.historical_anchor_proofs[0],
        "witness": witness,
        "state_sha256": updated.state_envelope["state_sha256"],
        "visible_content_sha256": delivery.review_exchange.sha256_text(visible),
    }
    return replace(updated, historical_anchor_proofs=(legacy,))


@pytest.mark.parametrize("heading", ["", "## Bound corrective review\n\n"])
@pytest.mark.parametrize("suffix", ["", " Both original diff ranges were checked."])
def test_corrective_witness_verifies_without_changing_the_original_review(
    source: tuple[Path, str, str], heading: str, suffix: str
) -> None:
    delivery, forge, binding, proof = corrective_case(
        source, heading=heading, suffix=suffix
    )
    original_body = forge.reviews[0].body
    original_state = proof.state_envelope
    assert delivery.deliver_no_go(forge, binding, proof).status == "delivered"
    assert forge.reviews[0].body == original_body
    assert proof.state_envelope == original_state
    assert len(forge.threads) == 1
    assert proof.state_envelope["state"]["findings"][1]["state"] == "open"


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("repository #7", "foreign #7"),
        ("repository #7", "repository #8"),
        ("round 1", "round 2"),
        ("round 1", "round 01"),
        ("HEAD", "f" * 40),
        ("BASE", "e" * 40),
        ("base and merge base", "base"),
    ],
)
def test_corrective_witness_rejects_incorrect_or_missing_source_assertions(
    source: tuple[Path, str, str], old: str, new: str
) -> None:
    delivery, forge, binding, proof = corrective_case(source)
    old = {"HEAD": source[2], "BASE": source[1]}.get(old, old)
    witness = proof.historical_anchor_proofs[0]["witness"].replace(old, new)
    visible = proof.visible_content.replace(old, new)
    proof = bind_witness(delivery, forge, proof, visible, witness)
    with pytest.raises(delivery.DeliveryError):
        delivery.deliver_no_go(forge, binding, proof)
    assert_no_write(forge)


@pytest.mark.parametrize("mutation", ["duplicate", "conflicting_legacy", "not_opening"])
def test_corrective_witness_rejects_ambiguous_or_unbound_opening_text(
    source: tuple[Path, str, str], mutation: str
) -> None:
    delivery, forge, binding, proof = corrective_case(source)
    witness = proof.historical_anchor_proofs[0]["witness"]
    visible = proof.visible_content
    if mutation == "duplicate":
        visible += "\n\n" + witness
    elif mutation == "conflicting_legacy":
        visible += (
            f"\n\nReviewed repository #7 at `{source[2]}`, "
            f"against base/merge-base `{'e' * 40}` (zero commits behind)."
        )
    else:
        visible = "An unrelated statement precedes the witness.\n\n" + visible
    proof = bind_witness(delivery, forge, proof, visible, witness)
    with pytest.raises(delivery.DeliveryError):
        delivery.deliver_no_go(forge, binding, proof)
    assert_no_write(forge)


def test_corrective_witness_cannot_hide_a_missing_inline_root(
    source: tuple[Path, str, str],
) -> None:
    delivery, forge, binding, proof = corrective_case(source)
    forge.threads.clear()
    with pytest.raises(delivery.DeliveryError):
        delivery.deliver_no_go(forge, binding, proof)
    assert_no_write(forge)


def test_corrective_witness_must_match_the_actual_unique_merge_base(
    source: tuple[Path, str, str],
) -> None:
    root, base, head = source
    git(root, "checkout", "-qb", "target", base)
    (root / "unrelated.txt").write_text("base-only change\n")
    git(root, "add", "unrelated.txt")
    git(root, "commit", "-qm", "advance target")
    claimed_base = git(root, "rev-parse", "HEAD")
    delivery, forge, binding, proof = corrective_case((root, claimed_base, head))
    with pytest.raises(delivery.DeliveryError):
        delivery.deliver_no_go(forge, binding, proof)
    assert_no_write(forge)
