"""The original anchor-annex compatibility path for the one retained malformed carrier."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.unit.test_pr_review_anchor_proofs import git
from tests.unit.test_pr_review_go_delivery import load_module

ROOT = Path(__file__).resolve().parents[2]
FINDINGS = [
    {
        "id": f"F-{index:03d}",
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
    for index, line in ((1, 10), (2, 80))
]


def _git_source(root: Path) -> tuple[Path, str, str]:
    git(root, "init", "-q")
    git(root, "config", "user.name", "Fixture")
    git(root, "config", "user.email", "fixture@example.invalid")
    lines = [f"line {n}\n" for n in range(1, 101)]
    (root / "justfile").write_text("".join(lines), encoding="utf-8")
    git(root, "add", "justfile")
    git(root, "commit", "-qm", "fixture base")
    base = git(root, "rev-parse", "HEAD")
    lines[9] = "changed line\n"
    (root / "justfile").write_text("".join(lines), encoding="utf-8")
    git(root, "add", "justfile")
    git(root, "commit", "-qm", "fixture head")
    head = git(root, "rev-parse", "HEAD")
    return root, base, head


def _case(
    root: Path,
    base: str,
    head: str,
    *,
    suffix: str = "suffix",
    repository: str = "owner/repository",
    number: int = 7,
) -> tuple[Any, dict[str, Any], str, dict[str, Any], dict[str, Any]]:
    delivery = load_module()
    exchange = delivery.review_exchange
    target = {
        "provider": "github",
        "repository": repository,
        "number": number,
        "url": f"https://github.com/{repository}/pull/{number}",
    }
    manifest = delivery.anchor_proofs.prepare_manifest(root, base, head, [])
    visible = (
        "Factual source review.\n\n"
        + delivery.anchor_proofs.MARKER
        + "\n```json\n"
        + delivery.anchor_proofs.canonical(manifest)
        + "\n```\n\n"
        + suffix
    )
    event = {
        "event_type": "reviewer_assessment",
        "exchange_id": "exchange-recovery",
        "prior_state_sha256": None,
        "round": 1,
        "surface": "pull_request",
        "target": target,
        "requirements_sha256": "1" * 64,
        "supersedes_state_sha256": None,
        "artifact_binding": {
            "revision": head,
            "sha256": "3" * 64,
            "visible_content_sha256": exchange.sha256_text(visible),
        },
        "scope": ["path:justfile"],
        "coverage_complete": True,
        "responses": [],
        "new_findings": FINDINGS,
        "stop_reason": "requirements_reframe",
    }
    envelope = exchange.reduce_request({"previous": None, "event": event})["envelope"]
    spec = {
        "manifest_id": "synthetic-original-annex",
        "repository": repository,
        "review_id": "9001",
        "base_oid": base,
        "head_oid": head,
        "merge_base_oid": manifest["merge_base_oid"],
        "state_sha256": envelope["state_sha256"],
        "visible_content_sha256": exchange.sha256_text(visible),
        "annex_json_sha256": hashlib.sha256(
            delivery.anchor_proofs.canonical(manifest).encode("utf-8")
        ).hexdigest(),
        "hunks_sha256": manifest["hunks_sha256"],
    }
    return delivery, envelope, visible, spec, target


def _expected(
    delivery: Any,
    source: Path,
    target: dict[str, Any],
    envelope: dict[str, Any],
    visible: str,
    *,
    review_id: str = "9001",
    findings: Any = FINDINGS,
) -> dict[str, tuple[str, str | None, int]]:
    return delivery.anchor_proofs.expected_anchors(
        source=source,
        target=target,
        envelope=envelope,
        visible=visible,
        findings=findings,
        review_id=review_id,
        legacy_proofs=(),
    )


def test_original_annex_is_recovered_as_factual_fallback(tmp_path, monkeypatch) -> None:
    root, base, head = _git_source(tmp_path)
    delivery, envelope, visible, spec, target = _case(root, base, head)
    monkeypatch.setattr(delivery.anchor_proofs, "ORIGINAL_ANNEX_COMPATIBILITY", spec)

    with pytest.raises(ValueError, match="not the final visible section"):
        delivery.anchor_proofs.visible_manifest(visible)

    result = _expected(delivery, root, target, envelope, visible)

    assert result == {
        "F-001": ("justfile", None, 10),
        "F-002": ("justfile", None, 80),
    }


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("repository", "owner/other"),
        ("review_id", "9002"),
        ("base_oid", "0" * 40),
        ("head_oid", "0" * 40),
        ("merge_base_oid", "0" * 40),
        ("state_sha256", "0" * 64),
        ("visible_content_sha256", "0" * 64),
        ("annex_json_sha256", "0" * 64),
        (
            "hunks_sha256",
            {"author_intent": "0" * 64, "current_target": "0" * 64},
        ),
    ],
)
def test_original_annex_requires_each_pinned_identity(
    tmp_path, monkeypatch, field: str, replacement: Any
) -> None:
    root, base, head = _git_source(tmp_path)
    delivery, envelope, visible, spec, target = _case(root, base, head)
    spec = dict(spec)
    spec[field] = replacement
    monkeypatch.setattr(delivery.anchor_proofs, "ORIGINAL_ANNEX_COMPATIBILITY", spec)

    with pytest.raises(ValueError):
        _expected(delivery, root, target, envelope, visible)


def test_original_annex_rejects_a_tampered_state(tmp_path, monkeypatch) -> None:
    root, base, head = _git_source(tmp_path)
    delivery, envelope, visible, spec, target = _case(root, base, head)
    exchange = delivery.review_exchange
    state = json.loads(json.dumps(envelope["state"]))
    state["findings"][0]["state"] = "resolved"
    envelope = {
        **envelope,
        "state": state,
        "state_sha256": exchange.sha256_json(state),
    }
    monkeypatch.setattr(delivery.anchor_proofs, "ORIGINAL_ANNEX_COMPATIBILITY", spec)

    with pytest.raises(ValueError):
        _expected(delivery, root, target, envelope, visible)


def test_original_annex_rejects_a_different_target_provider(
    tmp_path, monkeypatch
) -> None:
    root, base, head = _git_source(tmp_path)
    delivery, envelope, visible, spec, target = _case(root, base, head)
    target = {**target, "provider": "gitlab"}
    monkeypatch.setattr(delivery.anchor_proofs, "ORIGINAL_ANNEX_COMPATIBILITY", spec)

    with pytest.raises(ValueError):
        _expected(delivery, root, target, envelope, visible)


def test_original_annex_requires_immutable_source(tmp_path, monkeypatch) -> None:
    root, base, head = _git_source(tmp_path)
    delivery, envelope, visible, spec, target = _case(root, base, head)
    monkeypatch.setattr(delivery.anchor_proofs, "ORIGINAL_ANNEX_COMPATIBILITY", spec)

    with pytest.raises(ValueError):
        _expected(delivery, None, target, envelope, visible)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("label", "visible_mutation", "review_id"),
    [
        ("line feed suffix", lambda visible: visible + "\n\nSuffix text.", "9001"),
        ("extra blank lines", lambda visible: visible + "\n\n\n\n", "9001"),
        (
            "suffix after closing fence",
            lambda visible: visible.replace("\n```\n\nsuffix", "\n```\nsuffix"),
            "9001",
        ),
        ("carriage return", lambda visible: visible.replace("\n", "\r\n"), "9001"),
        ("leading spaces", lambda visible: "  " + visible, "9001"),
        ("second malformed carrier", lambda visible: visible, "9002"),
    ],
)
def test_non_matching_carriers_with_source_corruption_raise(
    tmp_path, monkeypatch, label: str, visible_mutation: Any, review_id: str
) -> None:
    root, base, head = _git_source(tmp_path)
    delivery, envelope, visible, spec, target = _case(root, base, head)
    monkeypatch.setattr(delivery.anchor_proofs, "ORIGINAL_ANNEX_COMPATIBILITY", spec)

    with pytest.raises(ValueError):
        _expected(
            delivery,
            root,
            target,
            envelope,
            visible_mutation(visible),
            review_id=review_id,
        )


def _publish_module():
    path = ROOT / "skills" / "pr-review" / "scripts" / "publish_round.py"
    name = "athena_publish_round_for_write_prevention"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("The round-publication helper cannot be loaded.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_complete_carrier_verification_accepts_valid_carrier(tmp_path) -> None:
    root, base, head = _git_source(tmp_path)
    delivery, envelope, visible, _, _ = _case(root, base, head)
    publish = _publish_module()
    body = delivery.review_exchange.render_carrier(visible, envelope, "state")

    publish._verify_complete_carrier(body)


def test_complete_carrier_verification_rejects_broken_carrier(tmp_path) -> None:
    publish = _publish_module()
    broken = (
        "Factual source review.\n\n"
        + "<!-- HomericIntelligence:review-anchors:v1 -->\n"
        + "```json\n"
        + "{not complete json]\n"
        + "```\n"
    )

    with pytest.raises(publish.deliver_go.DeliveryError) as raised:
        publish._verify_complete_carrier(broken)

    assert "not publishable" in str(raised.value)


def test_main_refuses_to_call_the_forge_for_invalid_visible(
    tmp_path, monkeypatch, capsys
) -> None:
    root, base, head = _git_source(tmp_path)
    delivery, envelope, visible, _, _ = _case(root, base, head)
    publish = _publish_module()

    class Recorder:
        constructed = 0

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            Recorder.constructed += 1

    monkeypatch.setattr(publish.deliver_go, "GitHubForge", Recorder)
    carrier = tmp_path / "carrier.md"
    visible_broken = visible + "\n\n" + delivery.anchor_proofs.MARKER
    event = json.loads(json.dumps(envelope["state"]["accepted_events"][0]))
    event["artifact_binding"]["visible_content_sha256"] = (
        delivery.review_exchange.sha256_text(visible_broken)
    )
    broken_envelope = delivery.review_exchange.reduce_request(
        {"previous": None, "event": event}
    )["envelope"]
    carrier.write_text(
        delivery.review_exchange.render_carrier(
            visible_broken, broken_envelope, "state"
        ),
        encoding="utf-8",
    )
    batch = tmp_path / "batch.json"
    batch.write_text(
        delivery.review_exchange.canonical_json(
            {
                "schema_id": "athena.review-exchange.finding-batch",
                "schema_version": 1,
                "exchange_id": broken_envelope["state"]["exchange_id"],
                "comments": [],
            }
        ),
        encoding="utf-8",
    )

    status = publish.main(
        [
            "--target-repository",
            "owner/repository",
            "--expected-pr-url",
            "https://github.com/owner/repository/pull/7",
            "--base-oid",
            base,
            "--head-oid",
            head,
            "--state-carrier-file",
            str(carrier),
            "--batch-file",
            str(batch),
            "7",
        ]
    )

    assert status == 1
    assert Recorder.constructed == 0
    assert "anchor" in capsys.readouterr().err.lower()
