"""Real-Git proof boundaries for factual review-summary locations."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from tests.unit.test_pr_review_go_delivery import FakeForge, load_module


def git(root: Path, *args: str) -> str:
    """Run Git only in an owned fixture repository."""
    return subprocess.run(
        ["git", "-C", str(root), "-c", "commit.gpgsign=false", *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def source(tmp_path: Path) -> tuple[Path, str, str]:
    """Make a real complete history with one changed and one untouched line."""
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.name", "Fixture")
    git(tmp_path, "config", "user.email", "fixture@example.invalid")
    lines = [f"line {n}\n" for n in range(1, 101)]
    (tmp_path / "justfile").write_text("".join(lines))
    git(tmp_path, "add", "justfile")
    git(tmp_path, "commit", "-qm", "fixture base")
    base = git(tmp_path, "rev-parse", "HEAD")
    lines[9] = "changed line\n"
    (tmp_path / "justfile").write_text("".join(lines))
    git(tmp_path, "commit", "-qam", "fixture head")
    return tmp_path, base, git(tmp_path, "rev-parse", "HEAD")


def test_left_anchor_rejects_target_insertions_that_change_its_coordinates(
    source: tuple[Path, str, str],
) -> None:
    root, merge, head = source
    git(root, "checkout", "-qb", "target", merge)
    lines = (root / "justfile").read_text().splitlines(keepends=True)
    lines[69:69] = [f"target insertion {n}\n" for n in range(20)]
    (root / "justfile").write_text("".join(lines))
    git(root, "commit", "-qam", "target-only insertions")
    base = git(root, "rev-parse", "HEAD")
    anchors = load_module().anchor_proofs

    # Merge-base line80 is untouched, but current-base line80 is an inserted line.
    assert git(root, "show", f"{merge}:justfile").splitlines()[79] == "line 80"
    assert (
        git(root, "show", f"{base}:justfile")
        .splitlines()[79]
        .startswith("target insertion")
    )
    with pytest.raises(ValueError, match="LEFT.*base.*content"):
        anchors.prepare_manifest(
            root,
            base,
            head,
            [{"id": "F-001", "location": "justfile:80", "side": "LEFT"}],
        )


@pytest.mark.parametrize("target_diverges", [False, True])
def test_left_anchor_uses_one_coordinate_when_base_path_content_is_identical(
    source: tuple[Path, str, str], target_diverges: bool
) -> None:
    root, merge, head = source
    base = merge
    if target_diverges:
        git(root, "checkout", "-qb", "target", merge)
        (root / "unrelated.txt").write_text("target-only file\n")
        git(root, "add", "unrelated.txt")
        git(root, "commit", "-qm", "target advances outside reviewed path")
        base = git(root, "rev-parse", "HEAD")
        assert base != merge
    anchors = load_module().anchor_proofs
    manifest = anchors.prepare_manifest(
        root,
        base,
        head,
        [
            {"id": "F-001", "location": "justfile:10", "side": "LEFT"},
            {"id": "F-002", "location": "justfile:80", "side": "LEFT"},
        ],
    )
    assert manifest["merge_base_oid"] == merge
    assert [entry["publication"] for entry in manifest["findings"]] == [
        "inline",
        "summary",
    ]
    assert all(entry["side"] == "LEFT" for entry in manifest["findings"])


def legacy_case(source: tuple[Path, str, str]) -> tuple[Any, Any, Any, Any]:
    """Keep an original carrier immutable while supplying explicit source proof."""
    root, base, head = source
    delivery = load_module()
    exchange = delivery.review_exchange
    target = {
        "provider": "github",
        "repository": "owner/repository",
        "number": 7,
        "url": "https://github.com/owner/repository/pull/7",
    }
    visible = (
        f"Reviewed repository #7 at `{head}`, against base/merge-base `{base}` "
        "(zero commits behind).\n\n"
        "F-002 remains required and is in the summary because its causal line predates the diff."
    )
    findings = [
        {
            "id": finding_id,
            "category": None,
            "severity": "major",
            "disposition": "required",
            "material_architecture": False,
            "location": f"justfile:{line}",
            "impact": "The result is incorrect.",
            "evidence": ["Controlled source evidence."],
            "closure_condition": "The result is correct.",
            "introduction": "initial",
        }
        for finding_id, line in (("F-001", 10), ("F-002", 80))
    ]
    envelope = exchange.reduce_request(
        {
            "previous": None,
            "event": {
                "event_type": "reviewer_assessment",
                "exchange_id": "summary-source",
                "prior_state_sha256": None,
                "round": 1,
                "surface": "pull_request",
                "target": target,
                "requirements_sha256": "d" * 64,
                "supersedes_state_sha256": None,
                "artifact_binding": {
                    "revision": head,
                    "sha256": "5" * 64,
                    "visible_content_sha256": exchange.sha256_text(visible),
                },
                "scope": ["path:justfile"],
                "coverage_complete": True,
                "go_eligible": True,
                "responses": [],
                "new_findings": findings,
                "stop_reason": None,
            },
        }
    )["envelope"]
    body = exchange.render_carrier(visible, envelope, "state")
    review_id = "original-review"
    record = delivery.ReviewRecord(
        id=review_id,
        body=body,
        head_oid=head,
        author="reviewer",
        viewer_did_author=True,
        includes_created_edit=False,
        state="COMMENTED",
        submitted_at="2026-01-01T00:00:00Z",
    )
    comment = delivery.ReviewComment(
        id="real-inline-root",
        body="Required.\n\n<!-- HomericIntelligence:review-finding:v1 exchange=summary-source id=F-001 -->",
        author="reviewer",
        viewer_did_author=True,
        review_head_oid=head,
        review_id=review_id,
        path="justfile",
        side="RIGHT",
        line=10,
        original_line=10,
        published_at="2026-01-01T00:00:00Z",
    )
    thread = delivery.ReviewThread(
        id="real-thread", is_resolved=False, comments=(comment,)
    )

    class BoundForge(FakeForge):
        def snapshot(self) -> Any:
            return replace(super().snapshot(), base_oid=base, head_oid=head)

    forge = BoundForge(delivery, threads=(thread,))
    forge.reviews = [record]
    forge.labels = {"state:implementation-go"}
    binding = delivery.ReviewBinding(
        repository=target["repository"],
        number=7,
        url=target["url"],
        base_oid=base,
        head_oid=head,
    )
    legacy = {
        "schema_id": "athena.pr-review.historical-anchor-proof",
        "schema_version": 1,
        "target": target,
        "review_id": review_id,
        "state_sha256": envelope["state_sha256"],
        "visible_content_sha256": exchange.sha256_text(visible),
        "base_oid": base,
        "head_oid": head,
        "merge_base_oid": base,
        "finding_ids": ["F-002"],
        "witness": visible.split("\n", 1)[0],
    }
    # The public proof gains runtime-only source inputs; its persisted v1 bytes stay exact.
    proof = delivery.NoGoProof(
        state_envelope=envelope,
        visible_content=visible,
        review_id=review_id,
        requirements_binding=delivery.RequirementsBinding(
            reviewed_scope_sha256="5" * 64,
            requirements_sha256="d" * 64,
            requirement_issue_urls=(),
        ),
        anchor_source=root,
        historical_anchor_proofs=(legacy,),
    )
    return delivery, forge, binding, proof


def test_legacy_factual_summary_uses_original_source_without_rewriting_carrier(
    source: tuple[Path, str, str],
) -> None:
    delivery, forge, binding, proof = legacy_case(source)
    original = forge.reviews[0].body
    original_state = json.dumps(proof.state_envelope, sort_keys=True)
    result = delivery.deliver_no_go(forge, binding, proof)
    assert result.status == "delivered"
    assert forge.reviews[0].body == original
    assert json.dumps(proof.state_envelope, sort_keys=True) == original_state
    assert len(forge.threads) == 1
    assert proof.state_envelope["state"]["findings"][1]["state"] == "open"


def test_summary_proof_cannot_hide_a_missing_real_inline_root(
    source: tuple[Path, str, str],
) -> None:
    delivery, forge, binding, proof = legacy_case(source)
    forge.threads.clear()
    with pytest.raises(delivery.DeliveryError):
        delivery.deliver_no_go(forge, binding, proof)
    assert not any(
        event.startswith(("label", "reply", "resolve")) for event in forge.events
    )


def rebind_visible(delivery: Any, forge: Any, proof: Any, visible: str) -> Any:
    """Publish controlled fixture text through the real immutable carrier encoder."""
    event = json.loads(json.dumps(proof.state_envelope["state"]["accepted_events"][0]))
    event["artifact_binding"]["visible_content_sha256"] = (
        delivery.review_exchange.sha256_text(visible)
    )
    envelope = delivery.review_exchange.reduce_request(
        {"previous": None, "event": event}
    )["envelope"]
    body = delivery.review_exchange.render_carrier(visible, envelope, "state")
    forge.reviews[0] = replace(forge.reviews[0], body=body)
    return replace(proof, visible_content=visible, state_envelope=envelope)


def future_case(
    source: tuple[Path, str, str],
) -> tuple[Any, Any, Any, Any, dict[str, Any]]:
    delivery, forge, binding, proof = legacy_case(source)
    manifest = delivery.anchor_proofs.prepare_manifest(
        source[0], source[1], source[2], proof.state_envelope["state"]["findings"]
    )
    proof = replace(proof, historical_anchor_proofs=())
    return delivery, forge, binding, proof, manifest


def with_annex(delivery: Any, forge: Any, proof: Any, manifest: dict[str, Any]) -> Any:
    visible = (
        "Factual source review.\n\n"
        + delivery.anchor_proofs.MARKER
        + "\n```json\n"
        + delivery.anchor_proofs.canonical(manifest)
        + "\n```"
    )
    return rebind_visible(delivery, forge, proof, visible)


def assert_no_write(forge: Any) -> None:
    assert not any(
        event.startswith(("label", "reply", "resolve", "terminal"))
        for event in forge.events
    )


def test_future_annex_binds_real_git_hunks_and_summary_partition(
    source: tuple[Path, str, str],
) -> None:
    delivery, forge, binding, proof, manifest = future_case(source)
    assert manifest["findings"] == [
        {
            "id": "F-001",
            "publication": "inline",
            "path": "justfile",
            "side": "RIGHT",
            "line": 10,
        },
        {
            "id": "F-002",
            "publication": "summary",
            "reason": "outside_bound_hunks",
            "path": "justfile",
            "side": "RIGHT",
            "line": 80,
        },
    ]
    patch = subprocess.run(
        [
            "git",
            "-C",
            str(source[0]),
            *delivery.anchor_proofs.DIFF_ARGS,
            source[1],
            source[2],
            "--",
        ],
        check=True,
        capture_output=True,
    ).stdout
    assert (
        manifest["hunks_sha256"]["author_intent"] == hashlib.sha256(patch).hexdigest()
    )
    proof = with_annex(delivery, forge, proof, manifest)
    result = delivery.deliver_no_go(forge, binding, proof)
    assert result.status == "delivered"
    assert len(forge.threads) == 1


def test_future_prose_summary_uses_manifest_without_synthetic_source_or_thread(
    source: tuple[Path, str, str],
) -> None:
    delivery, forge, binding, proof = legacy_case(source)
    event = json.loads(json.dumps(proof.state_envelope["state"]["accepted_events"][0]))
    event["new_findings"][1]["location"] = "review delivery workflow"
    envelope = delivery.review_exchange.reduce_request(
        {"previous": None, "event": event}
    )["envelope"]
    proof = replace(proof, state_envelope=envelope, historical_anchor_proofs=())
    manifest = delivery.anchor_proofs.prepare_manifest(
        *source, envelope["state"]["findings"]
    )
    proof = with_annex(delivery, forge, proof, manifest)
    assert delivery.deliver_no_go(forge, binding, proof).status == "delivered"
    assert manifest["findings"][1] == {
        "id": "F-002",
        "publication": "summary",
        "reason": "non_source_location",
    }
    assert len(forge.threads) == 1
    assert proof.state_envelope["state"]["findings"][1]["state"] == "open"


@pytest.mark.parametrize(
    "field",
    [
        "base_oid",
        "head_oid",
        "merge_base_oid",
        "hunk_hash",
        "classification",
        "missing_finding",
        "duplicate_finding",
        "wrong_line",
        "wrong_side",
        "unknown_field",
        "boolean_version",
    ],
)
def test_future_annex_rejects_incorrect_source_and_partition_before_write(
    source: tuple[Path, str, str], field: str
) -> None:
    delivery, forge, binding, proof, manifest = future_case(source)
    if field in {"base_oid", "head_oid", "merge_base_oid"}:
        manifest[field] = "f" * 40
    elif field == "hunk_hash":
        manifest["hunks_sha256"]["author_intent"] = "0" * 64
    elif field == "classification":
        manifest["findings"][0].update(
            publication="summary", reason="outside_bound_hunks"
        )
    elif field == "missing_finding":
        manifest["findings"].pop()
    elif field == "duplicate_finding":
        manifest["findings"].append(manifest["findings"][0])
    elif field == "wrong_line":
        manifest["findings"][1]["line"] = 81
    elif field == "wrong_side":
        manifest["findings"][0]["side"] = "LEFT"
    elif field == "unknown_field":
        manifest["waive_inline"] = True
    else:
        manifest["schema_version"] = True
    proof = with_annex(delivery, forge, proof, manifest)
    with pytest.raises(delivery.DeliveryError):
        delivery.deliver_no_go(forge, binding, proof)
    assert_no_write(forge)


@pytest.mark.parametrize(
    "field",
    [
        "target",
        "target_number_type",
        "review_id",
        "state_sha256",
        "visible_content_sha256",
        "base_oid",
        "head_oid",
        "merge_base_oid",
        "finding_ids",
        "witness",
        "extra",
        "duplicate",
    ],
)
def test_legacy_proof_rejects_wrong_original_identity_or_classification(
    source: tuple[Path, str, str], field: str
) -> None:
    delivery, forge, binding, proof = legacy_case(source)
    legacy = json.loads(json.dumps(proof.historical_anchor_proofs[0]))
    if field == "target":
        legacy["target"]["repository"] = "other/repository"
    elif field == "target_number_type":
        legacy["target"]["number"] = float(legacy["target"]["number"])
    elif field == "finding_ids":
        legacy[field] = ["F-001", "F-002"]
    elif field == "extra":
        legacy["human_decision"] = "accept"
    elif field == "duplicate":
        pass
    else:
        legacy[field] = "f" * (64 if field.endswith("sha256") else 40)
    proof = replace(
        proof,
        historical_anchor_proofs=(legacy, legacy)
        if field == "duplicate"
        else (legacy,),
    )
    with pytest.raises(delivery.DeliveryError):
        delivery.deliver_no_go(forge, binding, proof)
    assert_no_write(forge)


@pytest.mark.parametrize(
    "mutation",
    ["edited", "source_missing", "proof_absent", "shallow", "oversized_diff"],
)
def test_legacy_summary_needs_complete_unedited_source_proof(
    source: tuple[Path, str, str], mutation: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    delivery, forge, binding, proof = legacy_case(source)
    if mutation == "edited":
        forge.reviews[0] = replace(
            forge.reviews[0], last_edited_at="2026-01-01T00:01:00Z"
        )
    elif mutation == "source_missing":
        proof = replace(proof, anchor_source=None)
    elif mutation == "proof_absent":
        proof = replace(proof, historical_anchor_proofs=())
    elif mutation == "shallow":
        (source[0] / ".git" / "shallow").write_text(source[1] + "\n")
    else:
        monkeypatch.setattr(delivery.anchor_proofs, "MAX_BYTES", 32)
    with pytest.raises(delivery.DeliveryError):
        delivery.deliver_no_go(forge, binding, proof)
    assert_no_write(forge)


def test_base_advancement_cannot_reclassify_original_summary(
    source: tuple[Path, str, str],
) -> None:
    delivery, forge, binding, proof = legacy_case(source)
    # A later base changes the old summary line; the original review still means its old base.
    git(source[0], "checkout", "-qb", "later-base", source[1])
    lines = (source[0] / "justfile").read_text().splitlines(keepends=True)
    lines[79] = "later base edit\n"
    (source[0] / "justfile").write_text("".join(lines))
    git(source[0], "commit", "-qam", "advance target")
    later = git(source[0], "rev-parse", "HEAD")
    snapshot = forge.snapshot
    forge.snapshot = lambda: replace(snapshot(), base_oid=later)
    result = delivery.deliver_no_go(forge, replace(binding, base_oid=later), proof)
    assert result.status == "delivered"
    assert proof.historical_anchor_proofs[0]["base_oid"] == source[1]


@pytest.mark.parametrize("alter_ledger", [False, True])
def test_terminal_future_summary_is_published_without_synthetic_thread(
    source: tuple[Path, str, str], alter_ledger: bool
) -> None:
    delivery, forge, binding, proof, annex = future_case(source)
    event = json.loads(json.dumps(proof.state_envelope["state"]["accepted_events"][0]))
    event["new_findings"] = [event["new_findings"][1]]
    event["new_findings"][0].update(
        id="F-001", severity="minor", disposition="suggestion", closure_condition=None
    )
    annex = delivery.anchor_proofs.prepare_manifest(
        source[0], source[1], source[2], event["new_findings"]
    )
    visible = (
        delivery.terminal_visible_content(binding, ())
        + "\n\n"
        + delivery.anchor_proofs.MARKER
        + "\n```json\n"
        + delivery.anchor_proofs.canonical(annex)
        + "\n```"
    )
    if alter_ledger:
        visible = visible.replace("Closure ledger:", "Altered ledger:")
    event["artifact_binding"]["visible_content_sha256"] = (
        delivery.review_exchange.sha256_text(visible)
    )
    envelope = delivery.review_exchange.reduce_request(
        {"previous": None, "event": event}
    )["envelope"]
    manifest = delivery.ClosureManifest(
        state_envelope=envelope,
        terminal_visible_content=visible,
        entries=(),
        requirements_binding=proof.requirements_binding,
        comments=(),
        summary_finding_ids=("F-001",),
        anchor_source=source[0],
    )
    forge.reviews.clear()
    forge.threads.clear()
    forge.labels = {"state:implementation-no-go"}
    if alter_ledger:
        with pytest.raises(delivery.DeliveryError, match="closure ledger"):
            delivery.deliver_go_v1(forge, binding, manifest)
        assert_no_write(forge)
        return
    result = delivery.deliver_go_v1(forge, binding, manifest)
    assert result.status == "delivered"
    assert forge.events.count("terminal") == 1
    assert not forge.threads
    assert "HomericIntelligence:review-anchors:v1" in forge.reviews[0].body


def test_mutable_git_attributes_cannot_hide_an_inline_source_change(
    source: tuple[Path, str, str],
) -> None:
    delivery, _forge, _binding, proof = legacy_case(source)
    (source[0] / ".git" / "info" / "attributes").write_text("justfile -diff\n")
    manifest = delivery.anchor_proofs.prepare_manifest(
        source[0], source[1], source[2], proof.state_envelope["state"]["findings"]
    )
    assert manifest["findings"][0]["publication"] == "inline"


def test_legacy_original_witness_can_start_a_longer_published_paragraph(
    source: tuple[Path, str, str],
) -> None:
    delivery, forge, binding, proof = legacy_case(source)
    witness = proof.historical_anchor_proofs[0]["witness"]
    visible = proof.visible_content.replace(
        witness, witness + " Both immutable diff lenses have the same paths.", 1
    )
    updated = rebind_visible(delivery, forge, proof, visible)
    legacy = {
        **proof.historical_anchor_proofs[0],
        "state_sha256": updated.state_envelope["state_sha256"],
        "visible_content_sha256": delivery.review_exchange.sha256_text(visible),
    }
    updated = replace(updated, historical_anchor_proofs=(legacy,))
    assert delivery.deliver_no_go(forge, binding, updated).status == "delivered"


def test_source_subdirectory_cannot_hide_a_root_relative_inline_location(
    source: tuple[Path, str, str],
) -> None:
    delivery, _forge, _binding, proof = legacy_case(source)
    nested = source[0] / "nested"
    nested.mkdir()
    with pytest.raises(ValueError, match="repository root"):
        delivery.anchor_proofs.prepare_manifest(
            nested, source[1], source[2], proof.state_envelope["state"]["findings"]
        )


@pytest.mark.parametrize("separator", ["\u2028", "\r", "\v", "\f"])
def test_only_physical_git_lines_can_be_factual_locations(
    source: tuple[Path, str, str], separator: str
) -> None:
    delivery = load_module()
    (source[0] / "justfile").write_bytes(f"one{separator}two\n".encode())
    git(source[0], "commit", "-qam", "fixture physical lines")
    head = git(source[0], "rev-parse", "HEAD")
    with pytest.raises(ValueError, match="factual source location"):
        delivery.anchor_proofs.prepare_manifest(
            source[0], source[1], head, [{"id": "F-001", "location": "justfile:2"}]
        )


def test_carriage_return_in_source_is_not_a_patch_header(
    source: tuple[Path, str, str],
) -> None:
    delivery = load_module()
    lines = (source[0] / "justfile").read_bytes().split(b"\n")
    lines[9] = b"changed\r@@ -80,1 +80,1 @@"
    (source[0] / "justfile").write_bytes(b"\n".join(lines))
    git(source[0], "commit", "-qam", "fixture embedded carriage return")
    head = git(source[0], "rev-parse", "HEAD")
    manifest = delivery.anchor_proofs.prepare_manifest(
        source[0], source[1], head, [{"id": "F-001", "location": "justfile:80"}]
    )
    assert manifest["findings"][0]["publication"] == "summary"


def test_legacy_null_source_coordinate_cannot_be_reclassified_as_prose(
    source: tuple[Path, str, str],
) -> None:
    delivery, forge, binding, proof = legacy_case(source)
    event = json.loads(json.dumps(proof.state_envelope["state"]["accepted_events"][0]))
    event["new_findings"] = [event["new_findings"][0]]
    event["new_findings"][0]["location"] = "invalid\x00path:10"
    envelope = delivery.review_exchange.reduce_request(
        {"previous": None, "event": event}
    )["envelope"]
    body = delivery.review_exchange.render_carrier(
        proof.visible_content, envelope, "state"
    )
    forge.reviews[0] = replace(forge.reviews[0], body=body)
    forge.threads.clear()
    proof = replace(proof, state_envelope=envelope, historical_anchor_proofs=())
    with pytest.raises(delivery.DeliveryError):
        delivery.deliver_no_go(forge, binding, proof)
    assert_no_write(forge)


def test_manifest_cli_emits_reproducible_source_proof(
    source: tuple[Path, str, str], capsys: pytest.CaptureFixture[str]
) -> None:
    delivery = load_module()
    findings = [{"id": "F-001", "location": "justfile:80"}]
    inputs = source[0] / "findings.json"
    inputs.write_text(json.dumps(findings))
    assert (
        delivery.anchor_proofs.main(
            [
                "--source",
                str(source[0]),
                "--base-oid",
                source[1],
                "--head-oid",
                source[2],
                "--findings",
                str(inputs),
            ]
        )
        == 0
    )
    emitted = capsys.readouterr().out.strip()
    expected = delivery.anchor_proofs.prepare_manifest(*source, findings)
    assert emitted == delivery.anchor_proofs.canonical(expected)


@pytest.mark.parametrize("contents", ["{}", "null", "[1]", "not json"])
def test_manifest_cli_rejects_invalid_finding_inputs_without_proof(
    source: tuple[Path, str, str], capsys: pytest.CaptureFixture[str], contents: str
) -> None:
    delivery = load_module()
    inputs = source[0] / "findings.json"
    inputs.write_text(contents)
    with pytest.raises(SystemExit) as error:
        delivery.anchor_proofs.main(
            [
                "--source",
                str(source[0]),
                "--base-oid",
                source[1],
                "--head-oid",
                source[2],
                "--findings",
                str(inputs),
            ]
        )
    assert error.value.code == 1
    assert capsys.readouterr().out == ""
