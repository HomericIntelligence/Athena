"""Behavior tests for the requirement-evidence model inside the review exchange."""

from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills/review-exchange/scripts/review_exchange.py"
SHARED = ROOT / "skills/review-exchange/scripts/requirement_evidence.py"
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
exchange = load(SCRIPT, "athena_review_exchange_with_evidence")


def digest(text: str) -> str:
    """Return one synthetic hexadecimal digest."""
    return cast(str, evidence.sha256_text(text))


SECTIONS = {
    "S1": {"id": "S1", "paths": ["a.py"], "depends_on": []},
    "S2": {"id": "S2", "paths": ["b.py"], "depends_on": []},
}
DEPENDENCIES = {"a.py": digest("a-1"), "b.py": digest("b-1")}


def inventory() -> dict[str, Any]:
    """Return one frozen expected inventory for the exchange tests."""
    return cast(
        dict[str, Any],
        evidence.build_inventory(
            requirements_binding={
                "kind": "issue",
                "identity": "HomericIntelligence/Athena#288",
                "content_sha256": HEX_C,
            },
            artifact_binding={
                "kind": "commit",
                "identity": "revision-1",
                "content_sha256": HEX_A,
            },
            scope_binding={"paths": ["a.py", "b.py"], "sha256": HEX_B},
            requirements=[{"id": "R1", "source": "issue:acceptance:1"}],
            sections=list(SECTIONS.values()),
        ),
    )


def rows(
    *,
    section: str = "S1",
    result: str = "covered",
    finding_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Return one complete assessed row set for one section."""
    return [
        {
            "requirement": "R1",
            "section": section,
            "surface": surface,
            "result": result,
            "reason": None,
            "evidence": [f"{section}.py:1"],
            "finding_ids": [] if finding_ids is None else list(finding_ids),
            "dependencies": dict(DEPENDENCIES),
        }
        for surface in evidence.SURFACES
    ]


def record(
    *,
    first: list[dict[str, Any]] | None = None,
    second: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return one validated evidence record for the exchange tests."""
    return cast(
        dict[str, Any],
        evidence.build_record(
            inventory=inventory(),
            rows=[
                *(first if first is not None else rows()),
                *(second if second is not None else rows(section="S2")),
            ],
        ),
    )


def artifact(revision: str = "revision-1") -> dict[str, str]:
    """Return one artifact binding for the exchange tests."""
    return {
        "revision": revision,
        "sha256": HEX_B,
        "visible_content_sha256": HEX_A,
    }


def target() -> dict[str, Any]:
    """Return one review target for the exchange tests."""
    return {
        "provider": "github",
        "repository": "owner/repository",
        "number": 7,
        "url": "https://github.com/owner/repository/pull/7",
    }


def finding(finding_id: str = "F-001", **overrides: Any) -> dict[str, Any]:
    """Return one review finding for the exchange tests."""
    result = {
        "id": finding_id,
        "severity": "major",
        "disposition": "required",
        "category": None,
        "material_architecture": False,
        "location": "src/example.py:7",
        "impact": "The result can be incorrect.",
        "evidence": ["The failing case returns 0."],
        "closure_condition": "The failing case returns 1.",
        "introduction": "initial",
    }
    result.update(overrides)
    return result


def initial_event(
    *, findings: list[dict[str, Any]], requirement_evidence: Any
) -> dict[str, Any]:
    """Return one initial reviewer assessment for the exchange tests."""
    return {
        "event_type": "reviewer_assessment",
        "exchange_id": "exchange-7",
        "prior_state_sha256": None,
        "round": 1,
        "surface": "pull_request",
        "target": target(),
        "requirements_sha256": HEX_C,
        "supersedes_state_sha256": None,
        "artifact_binding": artifact(),
        "scope": ["path:a.py", "path:b.py"],
        "coverage_complete": False,
        "responses": [],
        "new_findings": findings,
        "stop_reason": None,
        "requirement_evidence": requirement_evidence,
    }


def reduce(
    event: dict[str, Any], previous: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Apply one event to an optional prior state envelope."""
    return cast(
        dict[str, Any],
        exchange.reduce_request({"previous": previous, "event": event}),
    )


class RequirementEvidenceExchangeTests(unittest.TestCase):
    """Bind the complete findings batch and selective repetition."""

    def test_complete_batch_keeps_every_visible_material_finding(self) -> None:
        complete = record(
            first=rows(result="missing_coverage", finding_ids=["F-001"]),
            second=rows(
                section="S2", result="incorrect_implementation", finding_ids=["F-002"]
            ),
        )
        result = reduce(
            initial_event(
                findings=[finding("F-001"), finding("F-002")],
                requirement_evidence=complete,
            )
        )
        state = cast(dict[str, Any], result["envelope"]["state"])
        assert (
            state["requirement_evidence"]["record_sha256"] == complete["record_sha256"]
        )
        assert result["envelope"]["schema_version"] == 3

    def test_complete_batch_rejects_a_partial_findings_list(self) -> None:
        complete = record(
            first=rows(result="missing_coverage", finding_ids=["F-001"]),
            second=rows(
                section="S2", result="incorrect_implementation", finding_ids=["F-002"]
            ),
        )
        with self.assertRaises(exchange.ProtocolError) as context:
            reduce(
                initial_event(
                    findings=[finding("F-001")], requirement_evidence=complete
                )
            )
        assert "omits material findings" in str(context.exception)

    def test_complete_batch_rejects_evidence_for_other_requirements(self) -> None:
        other = cast(
            dict[str, Any],
            evidence.build_inventory(
                requirements_binding={
                    "kind": "issue",
                    "identity": "HomericIntelligence/Athena#288",
                    "content_sha256": digest("other"),
                },
                artifact_binding={
                    "kind": "commit",
                    "identity": "revision-1",
                    "content_sha256": HEX_A,
                },
                scope_binding={"paths": ["a.py", "b.py"], "sha256": HEX_B},
                requirements=[{"id": "R1", "source": "issue:acceptance:1"}],
                sections=list(SECTIONS.values()),
            ),
        )
        foreign = evidence.build_record(
            inventory=other, rows=[*rows(), *rows(section="S2")]
        )
        with self.assertRaises(exchange.ProtocolError) as context:
            reduce(initial_event(findings=[], requirement_evidence=foreign))
        assert "bound requirements" in str(context.exception)

    def test_an_incomplete_assessment_cannot_enter_the_exchange(self) -> None:
        with self.assertRaises(exchange.ProtocolError):
            reduce(
                initial_event(
                    findings=[finding()],
                    requirement_evidence={
                        "schema_id": "athena.review-exchange.requirement-evidence",
                        "schema_version": 1,
                    },
                )
            )

    def test_partial_correction_retains_unchanged_review_sections(self) -> None:
        complete = record(first=rows(result="missing_coverage", finding_ids=["F-001"]))
        state = cast(
            dict[str, Any],
            reduce(initial_event(findings=[finding()], requirement_evidence=complete))[
                "envelope"
            ],
        )
        answer = exchange._continued_author_event(
            {
                "event_type": "author_response",
                "exchange_id": "exchange-7",
                "prior_state_sha256": state["state_sha256"],
                "artifact_binding": artifact("revision-2"),
                "scope": ["path:a.py", "path:b.py"],
                "scope_change_reason": None,
                "responses": [
                    {
                        "finding_id": "F-001",
                        "kind": "fix",
                        "evidence": ["The correction is in revision-2."],
                        "tradeoff": None,
                    }
                ],
                "coverage_changes": {
                    "inventory_sha256": complete["inventory_sha256"],
                    "retained_sections": ["S2"],
                    "repeated_sections": ["S1"],
                    "changed_dependencies": ["a.py"],
                },
            }
        )
        repeated = reduce(cast(dict[str, Any], answer), state)
        next_state = cast(dict[str, Any], repeated["envelope"]["state"])
        assert next_state["coverage_complete"] is False
        stored = cast(dict[str, Any], next_state["accepted_events"][-1])
        assert stored["coverage_changes"]["retained_sections"] == ["S2"]

    def test_partial_correction_repeats_the_review_when_no_section_is_retained(
        self,
    ) -> None:
        complete = record(first=rows(result="missing_coverage", finding_ids=["F-001"]))
        state = cast(
            dict[str, Any],
            reduce(initial_event(findings=[finding()], requirement_evidence=complete))[
                "envelope"
            ],
        )
        answer = exchange._continued_author_event(
            {
                "event_type": "author_response",
                "exchange_id": "exchange-7",
                "prior_state_sha256": state["state_sha256"],
                "artifact_binding": artifact("revision-2"),
                "scope": ["path:a.py", "path:b.py"],
                "scope_change_reason": None,
                "responses": [
                    {
                        "finding_id": "F-001",
                        "kind": "fix",
                        "evidence": ["The correction is in revision-2."],
                        "tradeoff": None,
                    }
                ],
                "coverage_changes": {
                    "inventory_sha256": complete["inventory_sha256"],
                    "retained_sections": [],
                    "repeated_sections": ["S1", "S2"],
                    "changed_dependencies": ["a.py", "b.py"],
                },
            }
        )
        next_state = cast(
            dict[str, Any], reduce(cast(dict[str, Any], answer), state)["envelope"]
        )
        assert next_state["state"]["coverage_complete"] is False

    def test_partial_correction_rejects_coverage_changes_for_another_inventory(
        self,
    ) -> None:
        complete = record()
        state = cast(
            dict[str, Any],
            reduce(initial_event(findings=[finding()], requirement_evidence=complete))[
                "envelope"
            ],
        )
        answer = exchange._continued_author_event(
            {
                "event_type": "author_response",
                "exchange_id": "exchange-7",
                "prior_state_sha256": state["state_sha256"],
                "artifact_binding": artifact("revision-2"),
                "scope": ["path:a.py", "path:b.py"],
                "scope_change_reason": None,
                "responses": [
                    {
                        "finding_id": "F-001",
                        "kind": "fix",
                        "evidence": ["The correction is in revision-2."],
                        "tradeoff": None,
                    }
                ],
                "coverage_changes": {
                    "inventory_sha256": digest("other"),
                    "retained_sections": ["S2"],
                    "repeated_sections": ["S1"],
                    "changed_dependencies": ["a.py"],
                },
            }
        )
        with self.assertRaises(exchange.ProtocolError) as context:
            reduce(cast(dict[str, Any], answer), state)
        assert "retained requirement evidence inventory" in str(context.exception)

    def test_signature_only_rewrite_binds_the_new_commit(self) -> None:
        complete = record()
        state = cast(
            dict[str, Any],
            reduce(initial_event(findings=[finding()], requirement_evidence=complete))[
                "envelope"
            ],
        )
        rebound = evidence.build_record(
            inventory=inventory(),
            rows=cast(list[dict[str, Any]], complete["rows"]),
            artifact_binding={
                "kind": "commit",
                "identity": "revision-2",
                "content_sha256": digest("revision-2"),
            },
        )
        comparison = cast(Any, evidence).compare_sections(
            complete,
            [
                {
                    **SECTIONS[name],
                    "dependencies": dict(DEPENDENCIES),
                    "corrected_findings": [],
                }
                for name in sorted(SECTIONS)
            ],
        )
        assert comparison["retained"] == ["S1", "S2"]
        assert rebound["artifact_binding"]["identity"] == "revision-2"
        assert state["state"]["artifact_binding"]["revision"] == "revision-1"

    def test_an_older_reader_rejects_the_new_envelope_without_a_write(self) -> None:
        complete = record()
        state = cast(
            dict[str, Any],
            reduce(initial_event(findings=[finding()], requirement_evidence=complete))[
                "envelope"
            ],
        )
        assert state["schema_version"] == 3
        historical = {
            "schema_id": state["schema_id"],
            "schema_version": 2,
            "state": {
                key: value
                for key, value in state["state"].items()
                if key != "requirement_evidence"
            },
            "state_sha256": exchange.sha256_json(
                {
                    key: value
                    for key, value in state["state"].items()
                    if key != "requirement_evidence"
                }
            ),
        }
        with self.assertRaises(exchange.ProtocolError):
            exchange.verify_envelope(historical)
        # The current reader still accepts the original record without any write.
        assert exchange.verify_envelope(state)["state_sha256"] == state["state_sha256"]

    def test_an_old_record_without_dependency_evidence_cannot_be_reused(self) -> None:
        legacy = copy.deepcopy(record())
        for row in legacy["rows"]:
            del row["dependencies"]
        current = [
            {
                **SECTIONS[name],
                "dependencies": dict(DEPENDENCIES),
                "corrected_findings": [],
            }
            for name in sorted(SECTIONS)
        ]
        comparison = cast(Any, evidence).compare_sections(legacy, current)
        assert comparison["retained"] == []
        assert {item["cause"]["kind"] for item in comparison["repeated"]} == {
            "no_verified_dependency_evidence"
        }


if __name__ == "__main__":
    unittest.main()
