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
    anchors: dict[str, tuple[str, str | None, int]] = (
        delivery.anchor_proofs.expected_anchors(
            source=source,
            target=target,
            envelope=envelope,
            visible=visible,
            findings=findings,
            review_id=review_id,
            legacy_proofs=(),
        )
    )
    return anchors


def test_original_annex_is_recovered_as_factual_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, replacement: Any
) -> None:
    root, base, head = _git_source(tmp_path)
    delivery, envelope, visible, spec, target = _case(root, base, head)
    spec = dict(spec)
    spec[field] = replacement
    monkeypatch.setattr(delivery.anchor_proofs, "ORIGINAL_ANNEX_COMPATIBILITY", spec)

    with pytest.raises(ValueError):
        _expected(delivery, root, target, envelope, visible)


def test_original_annex_rejects_a_tampered_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, base, head = _git_source(tmp_path)
    delivery, envelope, visible, spec, target = _case(root, base, head)
    target = {**target, "provider": "gitlab"}
    monkeypatch.setattr(delivery.anchor_proofs, "ORIGINAL_ANNEX_COMPATIBILITY", spec)

    with pytest.raises(ValueError):
        _expected(delivery, root, target, envelope, visible)


def test_original_annex_requires_immutable_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    label: str,
    visible_mutation: Any,
    review_id: str,
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


RETAINED_REVIEW = ROOT / "tests" / "fixtures" / "pr4618-review-5822080238.md"


def test_retained_annex_pins_the_published_carrier_identities() -> None:
    delivery = load_module()
    spec = delivery.anchor_proofs.RETAINED_ANNEX_COMPATIBILITY

    assert spec["manifest_id"] == "comet-retained-anchor-annex-omitted-finding-v1"
    assert spec["repository"] == "LLM360/comet"
    assert spec["review_id"] == "5822080238"
    assert spec["base_oid"] == "b3a331d4ea38d10987e685f4987948c21ca2cf59"
    assert spec["head_oid"] == "2009b20eccb5d1c6e835442f30ceb2051564b8ca"
    assert spec["merge_base_oid"] == "04132366986da87e4f638df94ae209375dea2259"
    assert (
        spec["state_sha256"]
        == "b046c8fbb12f7e8fbe25a214b3652319cc3479574b894e6381559a5f40972979"
    )
    assert (
        spec["visible_content_sha256"]
        == "a0ae725759bfc9f36ceddf56cc0cbaa9e9d11c13942746a1e34fc11a26601536"
    )
    assert (
        spec["annex_json_sha256"]
        == "f854fdf010819ba5ad70da1c90c48e5224a5ee234ad07f14a267eae7af23fadf"
    )
    assert spec["hunks_sha256"] == {
        "author_intent": "f29e4ffa1df12c83aea4cf45b6641c51bcaf34c8ad67cd2073d9b0461845e3f5",
        "current_target": (
            "fdfe147459861a2fe538df91f8416379cb1e66937f04bba1f1618b820c9c563b"
        ),
    }


def test_retained_annex_is_recovered_from_the_exact_published_carrier(
    tmp_path: Path,
) -> None:
    delivery = load_module()
    body = RETAINED_REVIEW.read_text(encoding="utf-8")
    exchange = delivery.review_exchange
    envelope, _ = exchange.extract_carrier_pair(body)
    visible = delivery._carrier_visible(body)

    recovered = delivery.anchor_proofs._original_annex(
        visible,
        tmp_path,
        envelope["state"]["target"],
        envelope,
        "5822080238",
        delivery.anchor_proofs.RETAINED_ANNEX_COMPATIBILITY,
    )

    assert recovered is not None
    assert [entry["id"] for entry in recovered["findings"]] == [
        f"F-{index:03d}" for index in range(1, 7)
    ]
    assert {f["id"] for f in envelope["state"]["findings"]} == {
        f"F-{index:03d}" for index in range(1, 8)
    }


def _retained_case(
    root: Path,
    base: str,
    head: str,
) -> tuple[Any, dict[str, Any], str, dict[str, Any], dict[str, Any]]:
    delivery = load_module()
    exchange = delivery.review_exchange
    target = {
        "provider": "github",
        "repository": "LLM360/comet",
        "number": 4618,
        "url": "https://github.com/LLM360/comet/pull/4618",
    }
    annex = delivery.anchor_proofs.prepare_manifest(root, base, head, FINDINGS[:1])
    visible = (
        "Factual source review.\n\n"
        + delivery.anchor_proofs.MARKER
        + "\n```json\n"
        + delivery.anchor_proofs.canonical(annex)
        + "\n```\n\nThe superseding state carrier follows.\n"
    )
    event = {
        "event_type": "reviewer_assessment",
        "exchange_id": "exchange-retained",
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
        "manifest_id": "synthetic-retained-annex",
        "repository": "LLM360/comet",
        "review_id": "5822080238",
        "base_oid": base,
        "head_oid": head,
        "merge_base_oid": annex["merge_base_oid"],
        "state_sha256": envelope["state_sha256"],
        "visible_content_sha256": exchange.sha256_text(visible),
        "annex_json_sha256": hashlib.sha256(
            delivery.anchor_proofs.canonical(annex).encode("utf-8")
        ).hexdigest(),
        "hunks_sha256": annex["hunks_sha256"],
    }
    return delivery, envelope, visible, spec, target


def test_retained_annex_is_recovered_with_its_published_finding_subset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, base, head = _git_source(tmp_path)
    delivery, envelope, visible, spec, target = _retained_case(root, base, head)
    monkeypatch.setattr(delivery.anchor_proofs, "RETAINED_ANNEX_COMPATIBILITY", spec)

    result = _expected(
        delivery, root, target, envelope, visible, review_id="5822080238"
    )

    assert result == {
        "F-001": ("justfile", None, 10),
        "F-002": ("justfile", None, 80),
    }


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("repository", "LLM360/other"),
        ("review_id", "5822080239"),
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
def test_retained_annex_requires_each_pinned_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    replacement: Any,
) -> None:
    root, base, head = _git_source(tmp_path)
    delivery, envelope, visible, spec, target = _retained_case(root, base, head)
    spec = dict(spec)
    spec[field] = replacement
    monkeypatch.setattr(delivery.anchor_proofs, "RETAINED_ANNEX_COMPATIBILITY", spec)

    with pytest.raises(ValueError):
        _expected(delivery, root, target, envelope, visible, review_id="5822080238")


def _publish_module() -> Any:
    path = ROOT / "skills" / "pr-review" / "scripts" / "publish_round.py"
    name = "athena_publish_round_for_write_prevention"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("The round-publication helper cannot be loaded.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_complete_carrier_verification_accepts_valid_carrier(tmp_path: Path) -> None:
    root, base, head = _git_source(tmp_path)
    delivery, envelope, visible, _, _ = _case(root, base, head)
    publish = _publish_module()
    body = delivery.review_exchange.render_carrier(visible, envelope, "state")

    publish._verify_complete_carrier(body)


def test_complete_carrier_verification_rejects_broken_carrier(tmp_path: Path) -> None:
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
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
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
