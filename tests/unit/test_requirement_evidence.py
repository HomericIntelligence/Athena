"""Behavior tests for the shared requirement-to-evidence review module."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, cast

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "skills/review-exchange/scripts/requirement_evidence.py"


def load_module(module_name: str = "athena_requirement_evidence") -> Any:
    """Load the shared requirement-evidence module from its canonical path."""
    if module_name in sys.modules:
        return sys.modules[module_name]
    specification = importlib.util.spec_from_file_location(module_name, MODULE)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[module_name] = module
    specification.loader.exec_module(module)
    return module


evidence = load_module()
Error = evidence.RequirementEvidenceError


def digest(text: str) -> str:
    """Return one synthetic hexadecimal digest."""
    return cast(str, evidence.sha256_text(text))


SECTIONS: dict[str, dict[str, Any]] = {
    "S1": {"id": "S1", "paths": ["a.py"], "depends_on": []},
    "S2": {"id": "S2", "paths": ["b.py"], "depends_on": ["a.py"]},
    "S3": {"id": "S3", "paths": ["c.py"], "depends_on": []},
}
PATHS = {"a.py": digest("a-1"), "b.py": digest("b-1"), "c.py": digest("c-1")}


def inventory(section_ids: tuple[str, ...] = ("S1", "S2")) -> dict[str, Any]:
    """Return one frozen expected inventory with two requirements."""
    build = cast(Any, evidence).build_inventory
    paths = sorted({path for name in section_ids for path in SECTIONS[name]["paths"]})
    return cast(
        dict[str, Any],
        build(
            requirements_binding={
                "kind": "issue",
                "identity": "HomericIntelligence/Athena#288",
                "content_sha256": digest("requirements"),
            },
            artifact_binding={
                "kind": "commit",
                "identity": "1" * 40,
                "content_sha256": digest("artifact-1"),
            },
            scope_binding={"paths": paths, "sha256": digest("scope-1")},
            requirements=[
                {"id": "R1", "source": "issue:acceptance:1"},
                {"id": "R2", "source": "issue:acceptance:2"},
            ],
            sections=[SECTIONS[name] for name in section_ids],
        ),
    )


def rows(
    result: str = "covered",
    *,
    finding_ids: list[str] | None = None,
    evidence_refs: list[str] | None = None,
    section_ids: tuple[str, ...] = ("S1", "S2"),
) -> list[dict[str, Any]]:
    """Return one complete assessed row set for the inventory."""
    return [
        {
            "requirement": requirement,
            "section": section,
            "surface": surface,
            "result": result,
            "reason": None,
            "evidence": ["a.py:1"] if evidence_refs is None else evidence_refs,
            "finding_ids": [] if finding_ids is None else list(finding_ids),
            "dependencies": dict(PATHS),
        }
        for requirement in ("R1", "R2")
        for section in section_ids
        for surface in evidence.SURFACES
    ]


def current_sections(
    *,
    corrected_findings: list[str] | None = None,
    section_ids: tuple[str, ...] = ("S1", "S2"),
) -> list[dict[str, Any]]:
    """Return one current section dependency record."""
    return [
        {
            **SECTIONS[name],
            "dependencies": dict(PATHS),
            "corrected_findings": []
            if corrected_findings is None
            else corrected_findings,
        }
        for name in section_ids
    ]


def build_record(
    *,
    rows_value: list[dict[str, Any]] | None = None,
    artifact_binding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return one validated evidence record."""
    frozen = inventory()
    return cast(
        dict[str, Any],
        cast(Any, evidence).build_record(
            inventory=frozen,
            rows=rows_value if rows_value is not None else rows(),
            artifact_binding=artifact_binding,
        ),
    )


class TestInventory:
    """Bind an independent expected inventory."""

    def test_build_inventory_recomputes_its_own_digest(self) -> None:
        frozen = inventory()
        assert evidence.validate_inventory(frozen) == frozen
        assert frozen["inventory_sha256"] == evidence.inventory_digest(frozen)

    def test_build_inventory_rejects_an_unassigned_scope_path(self) -> None:
        with pytest.raises(Error, match="is not assigned to a section"):
            evidence.build_inventory(
                requirements_binding={
                    "kind": "issue",
                    "identity": "A#1",
                    "content_sha256": digest("requirements"),
                },
                artifact_binding={
                    "kind": "commit",
                    "identity": "1" * 40,
                    "content_sha256": digest("artifact"),
                },
                scope_binding={"paths": ["a.py", "b.py"], "sha256": digest("scope")},
                requirements=[{"id": "R1", "source": "issue:1"}],
                sections=[
                    {"id": "S1", "paths": ["a.py"], "depends_on": []},
                    {"id": "S2", "paths": [], "depends_on": []},
                ],
            )

    def test_validate_inventory_rejects_a_forged_digest(self) -> None:
        frozen = cast(dict[str, Any], dict(inventory()))
        frozen["inventory_sha256"] = digest("other")
        with pytest.raises(Error, match="inventory digest"):
            evidence.validate_inventory(frozen)

    def test_validate_inventory_rejects_a_digest_the_caller_did_not_freeze(
        self,
    ) -> None:
        frozen = inventory()
        with pytest.raises(Error, match="inventory digest"):
            evidence.validate_inventory(frozen, expected_sha256=digest("other"))

    def test_inventory_rejects_a_duplicate_requirement_identifier(self) -> None:
        with pytest.raises(Error, match="duplicate requirement identifier"):
            evidence.build_inventory(
                requirements_binding={
                    "kind": "issue",
                    "identity": "A#1",
                    "content_sha256": digest("requirements"),
                },
                artifact_binding={
                    "kind": "commit",
                    "identity": "1" * 40,
                    "content_sha256": digest("artifact"),
                },
                scope_binding={"paths": ["a.py"], "sha256": digest("scope")},
                requirements=[
                    {"id": "R1", "source": "issue:1"},
                    {"id": "R1", "source": "issue:2"},
                ],
                sections=[{"id": "S1", "paths": ["a.py"], "depends_on": []}],
            )

    def test_expected_cells_cover_every_surface_of_every_section(self) -> None:
        cells = evidence.expected_cells(inventory())
        assert len(cells) == 2 * 2 * len(evidence.SURFACES)
        assert {
            (cell["requirement"], cell["section"], cell["surface"]) for cell in cells
        } == {
            (requirement, section, surface)
            for requirement in ("R1", "R2")
            for section in ("S1", "S2")
            for surface in evidence.SURFACES
        }


class TestAssessment:
    """Compare assessed rows with the independent inventory."""

    def test_complete_batch_accepts_every_expected_cell_once(self) -> None:
        frozen = inventory()
        validated = evidence.validate_assessment(frozen, rows())
        assert len(validated) == len(evidence.expected_cells(frozen))

    def test_complete_batch_rejects_missing_required_surface(self) -> None:
        frozen = inventory()
        incomplete = [
            row
            for row in rows()
            if not (
                row["requirement"] == "R1"
                and row["section"] == "S1"
                and row["surface"] == "documentation"
            )
        ]
        with pytest.raises(Error, match="missing expected cell"):
            evidence.validate_assessment(frozen, incomplete)

    def test_complete_batch_rejects_a_duplicate_row(self) -> None:
        frozen = inventory()
        duplicated = [*rows(), rows()[0]]
        with pytest.raises(Error, match="duplicate assessed cell"):
            evidence.validate_assessment(frozen, duplicated)

    def test_complete_batch_rejects_an_unknown_requirement(self) -> None:
        frozen = inventory()
        extra = [
            {**rows()[0], "requirement": "R9"},
            *rows()[1:],
        ]
        with pytest.raises(Error, match="unknown requirement"):
            evidence.validate_assessment(frozen, extra)

    def test_complete_batch_rejects_removed_requirement_and_rows(self) -> None:
        expected = inventory()
        submitted = cast(
            dict[str, Any],
            dict(
                evidence.build_inventory(
                    requirements_binding=expected["requirements_binding"],
                    artifact_binding=expected["artifact_binding"],
                    scope_binding=expected["scope_binding"],
                    requirements=[expected["requirements"][0]],
                    sections=expected["sections"],
                )
            ),
        )
        reduced = [row for row in rows() if row["requirement"] == "R1"]
        with pytest.raises(Error, match="does not match the expected inventory"):
            evidence.validate_assessment(
                submitted,
                reduced,
                expected_inventory=expected,
                expected_sha256=expected["inventory_sha256"],
            )

    def test_complete_batch_rejects_a_substituted_expected_inventory(self) -> None:
        expected = inventory()
        submitted = cast(dict[str, Any], dict(expected))
        submitted["expected_cells"] = submitted["expected_cells"][:-1]
        submitted["inventory_sha256"] = evidence.inventory_digest(submitted)
        with pytest.raises(Error, match="inventory digest"):
            evidence.validate_assessment(
                submitted,
                rows(),
                expected_inventory=expected,
                expected_sha256=expected["inventory_sha256"],
            )

    def test_not_applicable_requires_a_reason(self) -> None:
        frozen = inventory()
        marked = [
            {**row, "result": "not_applicable", "reason": None}
            if row["requirement"] == "R1" and row["surface"] == "documentation"
            else row
            for row in rows()
        ]
        with pytest.raises(Error, match="not applicable needs a reason"):
            evidence.validate_assessment(frozen, marked)

    def test_not_applicable_keeps_its_reason(self) -> None:
        frozen = inventory()
        marked = [
            {
                **row,
                "result": "not_applicable",
                "reason": "The section adds no documentation surface.",
                "evidence": [],
            }
            if row["requirement"] == "R1" and row["surface"] == "documentation"
            else row
            for row in rows()
        ]
        validated = evidence.validate_assessment(frozen, marked)
        marked_cell = next(
            row
            for row in validated
            if row["requirement"] == "R1" and row["surface"] == "documentation"
        )
        assert marked_cell["reason"] == "The section adds no documentation surface."

    def test_a_material_result_needs_a_finding_identifier(self) -> None:
        frozen = inventory()
        marked = [
            {**row, "result": "missing_coverage"}
            if row["requirement"] == "R1" and row["surface"] == "tests"
            else row
            for row in rows()
        ]
        with pytest.raises(Error, match="needs a finding identifier"):
            evidence.validate_assessment(frozen, marked)

    def test_missing_coverage_and_incorrect_implementation_stay_distinct(self) -> None:
        assert "missing_coverage" in evidence.RESULTS
        assert "incorrect_implementation" in evidence.RESULTS
        frozen = inventory()
        marked = [
            {
                **row,
                "result": "missing_coverage"
                if row["surface"] == "tests"
                else row["result"],
                "finding_ids": ["F-001"] if row["surface"] == "tests" else [],
            }
            if row["requirement"] == "R1"
            else row
            for row in rows()
        ]
        validated = evidence.validate_assessment(frozen, marked)
        material = evidence.assemble_findings(
            evidence.build_record(inventory=frozen, rows=validated)
        )
        assert {finding["result"] for finding in material} == {"missing_coverage"}


class TestFindingsBatch:
    """Assemble one bounded complete findings batch."""

    def test_record_requires_every_expected_cell_before_findings(self) -> None:
        frozen = inventory()
        with pytest.raises(Error, match="missing expected cell"):
            evidence.build_record(inventory=frozen, rows=rows()[:-1])

    def test_complete_batch_carries_every_material_finding(self) -> None:
        frozen = inventory()
        marked = []
        for row in rows():
            if row["surface"] == "tests" and row["requirement"] in {"R1", "R2"}:
                marked.append(
                    {
                        **row,
                        "result": (
                            "incorrect_implementation"
                            if row["requirement"] == "R1"
                            else "missing_coverage"
                        ),
                        "finding_ids": [f"F-{row['requirement']}-tests"],
                    }
                )
            else:
                marked.append(row)
        record = evidence.build_record(inventory=frozen, rows=marked)
        findings = evidence.assemble_findings(record)
        assert sorted({finding["id"] for finding in findings}) == [
            "F-R1-tests",
            "F-R2-tests",
        ]
        assert len(findings) == 4
        assert {finding["result"] for finding in findings} == {
            "missing_coverage",
            "incorrect_implementation",
        }
        assert len(findings) == 4
        assert {finding["result"] for finding in findings} == {
            "missing_coverage",
            "incorrect_implementation",
        }

    def test_record_binds_the_supplied_artifact_identity(self) -> None:
        record = build_record()
        assert record["artifact_binding"] == inventory()["artifact_binding"]

    def test_signature_only_rewrite_preserves_rows_and_binds_the_new_commit(
        self,
    ) -> None:
        prior = build_record()
        rebound = evidence.build_record(
            inventory=inventory(),
            rows=cast(list[dict[str, Any]], prior["rows"]),
            artifact_binding={
                "kind": "commit",
                "identity": "2" * 40,
                "content_sha256": digest("artifact-2"),
            },
        )
        comparison = evidence.compare_sections(prior, current_sections())
        assert comparison["retained"] == ["S1", "S2"]
        assert comparison["repeated"] == []
        assert rebound["artifact_binding"]["identity"] == "2" * 40
        assert evidence.assemble_findings(rebound) == []


class TestSectionComparison:
    """Repeat only the review sections that a source change affects."""

    def test_partial_correction_retains_unrelated_sections(self) -> None:
        sections = ("S1", "S2", "S3")
        prior = evidence.build_record(
            inventory=inventory(sections),
            rows=[
                {
                    **row,
                    "result": "missing_coverage",
                    "finding_ids": ["F-002"],
                }
                if row["requirement"] == "R1"
                and row["section"] == "S1"
                and row["surface"] == "tests"
                else row
                for row in rows(section_ids=sections)
            ],
        )
        marked = [
            {
                **row,
                "finding_ids": [],
                "result": "covered",
                "reason": None,
            }
            if row["requirement"] == "R1"
            and row["section"] == "S1"
            and row["surface"] == "tests"
            else row
            for row in cast(list[dict[str, Any]], prior["rows"])
        ]
        current = [
            {**section, "corrected_findings": ["F-002"]}
            for section in current_sections(section_ids=sections)
        ]
        record = evidence.build_record(inventory=inventory(sections), rows=marked)
        comparison = evidence.compare_sections(prior, current)
        assert comparison["repeated"] == [
            {
                "section": "S1",
                "cause": {"kind": "finding_corrected", "finding_id": "F-002"},
                "changed_dependencies": [],
            }
        ]
        assert comparison["retained"] == ["S2", "S3"]
        assert evidence.assemble_findings(record) == []

    def test_compatible_base_change_retains_every_section(self) -> None:
        prior = build_record()
        rebound = cast(dict[str, Any], dict(prior))
        rebound["artifact_binding"] = {
            "kind": "commit",
            "identity": "3" * 40,
            "content_sha256": digest("artifact-3"),
        }
        comparison = evidence.compare_sections(rebound, current_sections())
        assert comparison["retained"] == ["S1", "S2"]
        assert comparison["repeated"] == []

    def test_logical_content_change_repeats_the_section_and_its_dependents(
        self,
    ) -> None:
        prior = build_record()
        changed = [
            {
                "id": "S1",
                "paths": ["a.py"],
                "depends_on": [],
                "dependencies": {
                    "a.py": digest("a-2"),
                    "b.py": digest("b-1"),
                    "c.py": digest("c-1"),
                },
                "corrected_findings": [],
            },
            {
                "id": "S2",
                "paths": ["b.py"],
                "depends_on": ["a.py"],
                "dependencies": {
                    "a.py": digest("a-2"),
                    "b.py": digest("b-1"),
                    "c.py": digest("c-1"),
                },
                "corrected_findings": [],
            },
        ]
        comparison = evidence.compare_sections(prior, changed)
        repeated = {
            item["section"]: item["cause"]["kind"] for item in comparison["repeated"]
        }
        assert repeated == {"S1": "dependency_changed", "S2": "dependency_changed"}
        assert comparison["changed_dependencies"] == [
            {"name": "a.py", "old": digest("a-1"), "new": digest("a-2")}
        ]
        assert comparison["retained"] == []

    def test_a_removed_dependency_repeats_the_section(self) -> None:
        prior = build_record()
        current = current_sections()
        current[0]["dependencies"] = {"a.py": PATHS["a.py"]}
        comparison = evidence.compare_sections(prior, current)
        repeated = {item["section"]: item for item in comparison["repeated"]}
        assert repeated["S1"]["cause"] == {
            "kind": "dependency_changed",
            "changed": ["b.py", "c.py"],
        }
        assert {
            "name": "b.py",
            "old": PATHS["b.py"],
            "new": "",
        } in repeated["S1"]["changed_dependencies"]
        assert "S1" not in comparison["retained"]

    def test_a_dependent_that_sorts_first_still_repeats_with_its_dependency(
        self,
    ) -> None:
        sections = [
            {"id": "docs", "paths": ["d.md"], "depends_on": ["s.py"]},
            {"id": "src", "paths": ["s.py"], "depends_on": []},
        ]
        before = {"d.md": digest("d-1"), "s.py": digest("s-1")}
        frozen = cast(Any, evidence).build_inventory(
            requirements_binding={
                "kind": "issue",
                "identity": "HomericIntelligence/Athena#288",
                "content_sha256": digest("requirements"),
            },
            artifact_binding={
                "kind": "commit",
                "identity": "1" * 40,
                "content_sha256": digest("artifact-1"),
            },
            scope_binding={"paths": ["d.md", "s.py"], "sha256": digest("scope-1")},
            requirements=[{"id": "R1", "source": "issue:acceptance:1"}],
            sections=sections,
        )
        prior_rows = [
            {
                "requirement": "R1",
                "section": section["id"],
                "surface": surface,
                "result": "covered",
                "reason": None,
                "evidence": ["s.py:1"],
                "finding_ids": [],
                "dependencies": {section["paths"][0]: before[section["paths"][0]]},
            }
            for section in sections
            for surface in evidence.SURFACES
        ]
        prior = cast(Any, evidence).build_record(inventory=frozen, rows=prior_rows)
        current = [
            {
                **sections[0],
                "dependencies": {"d.md": before["d.md"]},
                "corrected_findings": [],
            },
            {
                **sections[1],
                "dependencies": {"s.py": digest("s-2")},
                "corrected_findings": [],
            },
        ]
        comparison = evidence.compare_sections(prior, current)
        repeated = {item["section"]: item["cause"] for item in comparison["repeated"]}
        assert repeated == {
            "docs": {"kind": "dependency_changed", "changed": ["s.py"]},
            "src": {"kind": "dependency_changed", "changed": ["s.py"]},
        }
        assert comparison["retained"] == []

    def test_first_review_repeats_every_section(self) -> None:
        comparison = evidence.compare_sections(None, current_sections())
        assert comparison["retained"] == []
        assert {item["cause"]["kind"] for item in comparison["repeated"]} == {
            "first_review"
        }

    def test_a_prior_record_without_dependency_evidence_cannot_be_reused(self) -> None:
        legacy = build_record()
        stripped = [
            {key: value for key, value in row.items() if key != "dependencies"}
            for row in cast(list[dict[str, Any]], legacy["rows"])
        ]
        assert evidence.compare_sections({"rows": stripped}, current_sections())[
            "repeated"
        ]

    def test_a_record_for_other_requirements_cannot_be_reused(self) -> None:
        prior = build_record()
        other = cast(dict[str, Any], dict(prior))
        other["requirements_sha256"] = digest("other-requirements")
        comparison = evidence.compare_sections(other, current_sections())
        assert {item["cause"]["kind"] for item in comparison["repeated"]} == {
            "requirements_changed"
        }


class TestRequirementMap:
    """Render one compact requirement-to-evidence map."""

    def test_requirement_map_lists_every_expected_cell(self) -> None:
        frozen = inventory()
        record = evidence.build_record(inventory=frozen, rows=rows())
        rendered = evidence.render_requirement_map(record)
        for cell in evidence.expected_cells(frozen):
            assert (
                f"| {cell['requirement']} | {cell['section']} | {cell['surface']} |"
                in rendered
            )

    def test_requirement_map_carries_results_evidence_and_findings(self) -> None:
        frozen = inventory()
        marked = [
            {
                **row,
                "result": "not_applicable",
                "reason": "No operation surface applies to a pure library change.",
                "evidence": [],
            }
            if row["requirement"] == "R2"
            and row["section"] == "S2"
            and row["surface"] == "operations"
            else (
                {
                    **row,
                    "result": "missing_coverage",
                    "finding_ids": ["F-003"],
                }
                if row["requirement"] == "R1" and row["surface"] == "implementation"
                else row
            )
            for row in rows()
        ]
        record = evidence.build_record(inventory=frozen, rows=marked)
        rendered = evidence.render_requirement_map(record)
        assert "F-003" in rendered
        assert "missing_coverage" in rendered
        assert "No operation surface applies to a pure library change." in rendered
        assert rendered.splitlines()[0].startswith(
            "| Requirement | Section | Surface |"
        )
