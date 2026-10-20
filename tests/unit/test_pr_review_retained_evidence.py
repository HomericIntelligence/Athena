"""Behavior tests for retained requirement evidence in pull-request delivery."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
DELIVER = ROOT / "skills" / "pr-review" / "scripts" / "deliver_go.py"
EXCHANGE = ROOT / "skills" / "review-exchange" / "scripts" / "review_exchange.py"
SHARED = ROOT / "skills" / "review-exchange" / "scripts" / "requirement_evidence.py"
HEX_A = "a" * 64
HEX_B = "b" * 64
HEX_C = "c" * 64


def load(path: Path, name: str) -> Any:
    """Load one helper module from its canonical path."""
    if name in sys.modules:
        return sys.modules[name]
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


evidence = load(SHARED, "athena_requirement_evidence")
exchange = load(EXCHANGE, "athena_pr_review_exchange")
deliver: ModuleType = load(DELIVER, "athena_pr_deliver_go_retained_evidence")
SECTIONS = [
    {"id": "S1", "paths": ["a.py"], "depends_on": []},
    {"id": "S2", "paths": ["b.py"], "depends_on": []},
]
DEPENDENCIES = {
    "a.py": evidence.sha256_text("a-1"),
    "b.py": evidence.sha256_text("b-1"),
}


def digest(text: str) -> str:
    """Return one synthetic hexadecimal digest."""
    return cast(str, evidence.sha256_text(text))


def inventory(*, requirements_sha256: str = HEX_C, revision: str = "revision-1") -> Any:
    """Return one frozen expected inventory."""
    return evidence.build_inventory(
        requirements_binding={
            "kind": "issue",
            "identity": "HomericIntelligence/Athena#288",
            "content_sha256": requirements_sha256,
        },
        artifact_binding={
            "kind": "commit",
            "identity": revision,
            "content_sha256": digest(revision),
        },
        scope_binding={"paths": ["a.py", "b.py"], "sha256": HEX_B},
        requirements=[{"id": "R1", "source": "issue:acceptance:1"}],
        sections=SECTIONS,
    )


def rows() -> list[dict[str, Any]]:
    """Return one complete assessed row set."""
    return [
        {
            "requirement": "R1",
            "section": section["id"],
            "surface": surface,
            "result": "covered",
            "reason": None,
            "evidence": [f"{section['id']}.py:1"],
            "finding_ids": [],
            "dependencies": dict(DEPENDENCIES),
        }
        for section in SECTIONS
        for surface in evidence.SURFACES
    ]


def state_envelope(
    *, requirements_sha256: str = HEX_C, revision: str = "revision-1"
) -> Any:
    """Return one review state envelope with a retained evidence record."""
    record = evidence.build_record(
        inventory=inventory(requirements_sha256=requirements_sha256, revision=revision),
        rows=rows(),
    )
    event = {
        "event_type": "reviewer_assessment",
        "exchange_id": "exchange-7",
        "prior_state_sha256": None,
        "round": 1,
        "surface": "pull_request",
        "target": {
            "provider": "github",
            "repository": "owner/repository",
            "number": 7,
            "url": "https://github.com/owner/repository/pull/7",
        },
        "requirements_sha256": requirements_sha256,
        "supersedes_state_sha256": None,
        "artifact_binding": {
            "revision": revision,
            "sha256": HEX_B,
            "visible_content_sha256": HEX_A,
        },
        "scope": ["path:a.py", "path:b.py"],
        "coverage_complete": True,
        "responses": [],
        "new_findings": [],
        "stop_reason": None,
        "requirement_evidence": record,
    }
    return exchange.reduce_request({"previous": None, "event": event})["envelope"]


def legacy_envelope() -> Any:
    """Return one review state envelope without requirement evidence."""
    event = {
        "event_type": "reviewer_assessment",
        "exchange_id": "exchange-8",
        "prior_state_sha256": None,
        "round": 1,
        "surface": "pull_request",
        "target": {
            "provider": "github",
            "repository": "owner/repository",
            "number": 7,
            "url": "https://github.com/owner/repository/pull/7",
        },
        "requirements_sha256": HEX_C,
        "supersedes_state_sha256": None,
        "artifact_binding": {
            "revision": "revision-1",
            "sha256": HEX_B,
            "visible_content_sha256": HEX_A,
        },
        "scope": ["path:a.py", "path:b.py"],
        "coverage_complete": True,
        "responses": [],
        "new_findings": [],
        "stop_reason": None,
    }
    return exchange.reduce_request({"previous": None, "event": event})["envelope"]


class TestRetainedEvidence:
    """Verify retained technical evidence against the current requirements."""

    def test_signature_only_rewrite_preserves_applicable_technical_evidence(
        self,
    ) -> None:
        envelope = state_envelope()
        retained = deliver.retained_requirement_evidence(
            envelope, requirements_sha256=HEX_C, artifact_revision="revision-2"
        )
        assert retained["retained"] is True
        assert retained["assessed_artifact_revision"] == "revision-1"
        assert retained["current_artifact_revision"] == "revision-2"

    def test_signature_only_rewrite_does_not_reuse_stale_requirements(self) -> None:
        envelope = state_envelope()
        try:
            deliver.retained_requirement_evidence(
                envelope,
                requirements_sha256=digest("other"),
                artifact_revision="revision-1",
            )
        except deliver.DeliveryError as error:
            assert "current requirements" in str(error)
        else:
            raise AssertionError("Stale requirements were accepted.")

    def test_a_state_without_evidence_retains_nothing(self) -> None:
        retained = deliver.retained_requirement_evidence(
            legacy_envelope(), requirements_sha256=HEX_C, artifact_revision="revision-1"
        )
        assert retained["retained"] is False
        assert retained["record_sha256"] is None

    def test_retained_evidence_does_not_authorize_a_stale_state(self) -> None:
        envelope = state_envelope()
        state = envelope["state"]
        assert state["artifact_binding"]["revision"] == "revision-1"
        assert state["requirements_sha256"] == HEX_C

    def test_an_invalid_state_is_rejected(self) -> None:
        try:
            deliver.retained_requirement_evidence(
                {"schema_id": "athena.review-exchange.state", "schema_version": 3},
                requirements_sha256=HEX_C,
                artifact_revision="revision-1",
            )
        except deliver.DeliveryError as error:
            assert "invalid" in str(error)
        else:
            raise AssertionError("An invalid envelope was accepted.")
