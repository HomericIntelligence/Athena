"""Behavior tests for the change-review requirement-evidence adapter."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast

import pytest

ROOT = Path(__file__).resolve().parents[2]
ADAPTER = ROOT / "skills/change-review/scripts/review_evidence.py"
SHARED = ROOT / "skills/review-exchange/scripts/requirement_evidence.py"

pytestmark = pytest.mark.nightly


def git(cwd: Path, *arguments: str) -> str:
    """Run Git in an isolated test repository."""
    result = subprocess.run(
        ["git", *arguments],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def initialize_repository(path: Path) -> None:
    """Create a repository with two modified tracked modules."""
    path.mkdir(parents=True)
    git(path, "init", "--quiet")
    git(path, "config", "user.name", "Athena Tests")
    git(path, "config", "user.email", "athena-tests@example.invalid")
    (path / "alpha.py").write_text("def alpha():\n    return 1\n", encoding="utf-8")
    (path / "beta.py").write_text("def beta():\n    return 2\n", encoding="utf-8")
    (path / "gamma.py").write_text("def gamma():\n    return 3\n", encoding="utf-8")
    git(path, "add", "alpha.py", "beta.py", "gamma.py")
    git(path, "commit", "--quiet", "-m", "test: initialize")
    (path / "alpha.py").write_text("def alpha():\n    return 11\n", encoding="utf-8")
    (path / "beta.py").write_text("def beta():\n    return 22\n", encoding="utf-8")
    (path / "gamma.py").write_text("def gamma():\n    return 33\n", encoding="utf-8")


def load_module(name: str, path: Path) -> Any:
    """Load one adapter or shared module from its canonical path."""
    if name in sys.modules:
        return sys.modules[name]
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


shared = load_module("athena_requirement_evidence", SHARED)
ASSIGNMENT = {"S1": ["alpha.py"], "S2": ["beta.py"], "S3": ["gamma.py"]}


def digest(text: str) -> str:
    """Return one synthetic hexadecimal digest."""
    return cast(str, shared.sha256_text(text))


class ChangeReviewEvidenceTests(unittest.TestCase):
    """Exercise the read-only prepare and finalize interface."""

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repository = Path(temporary.name) / "repository"
        initialize_repository(self.repository)
        original = Path.cwd()
        os.chdir(self.repository)
        self.addCleanup(os.chdir, original)
        self.adapter = self._load_adapter()

    def _load_adapter(self) -> Any:
        """Load the adapter with the shared module on its import path."""
        script_directory = str(ADAPTER.parent)
        sys.path.insert(0, script_directory)
        self.addCleanup(lambda: sys.path.remove(script_directory))
        specification = importlib.util.spec_from_file_location(
            "athena_change_review_evidence", ADAPTER
        )
        assert specification is not None
        assert specification.loader is not None
        module = importlib.util.module_from_spec(specification)
        sys.modules[specification.name] = module
        specification.loader.exec_module(module)
        return module

    def identities(self) -> dict[str, str]:
        """Return the current dependency content identities."""
        resolved = cast(dict[str, Any], self.adapter._resolve(_selectors()))
        return cast(dict[str, str], resolved["identities"])

    def request(
        self,
        *,
        assignment: dict[str, list[str]] | None = None,
        rows: list[dict[str, Any]] | None = None,
        previous: dict[str, Any] | None = None,
        previous_sha256: str | None = None,
        corrected_findings: list[str] | None = None,
        scope_paths: list[str] | None = None,
    ) -> dict[str, Any]:
        """Return one bounded adapter request for the temporary repository."""
        sections = assignment or ASSIGNMENT
        resolved = cast(dict[str, Any], self.adapter._resolve(_selectors()))
        scope_paths = list(resolved["paths"]) if scope_paths is None else scope_paths
        inventory = shared.build_inventory(
            requirements_binding={
                "kind": "task",
                "identity": "task-288",
                "content_sha256": digest("requirements"),
            },
            artifact_binding={
                "kind": "commit",
                "identity": "0" * 40,
                "content_sha256": digest("artifact-0"),
            },
            scope_binding={
                "paths": scope_paths,
                "sha256": str(resolved["scope_digest"]),
            },
            requirements=[{"id": "R1", "source": "task:acceptance:1"}],
            sections=[
                {
                    "id": name,
                    "paths": paths,
                    "depends_on": [] if name in {"S1", "S3"} else ["alpha.py"],
                }
                for name, paths in sorted(sections.items())
            ],
        )
        return {
            "scope": "worktree",
            "range": None,
            "paths": [],
            "inventory": inventory,
            "artifact_kind": "commit",
            "sections": [
                {
                    "id": name,
                    "paths": paths,
                    "depends_on": [] if name in {"S1", "S3"} else ["alpha.py"],
                }
                for name, paths in sorted(sections.items())
            ],
            "corrected_findings": []
            if corrected_findings is None
            else corrected_findings,
            "rows": rows if rows is not None else self.complete_rows(sections),
            "previous_record": previous,
            "previous_record_sha256": previous_sha256,
        }

    def complete_rows(
        self,
        assignment: dict[str, list[str]],
        *,
        result: str = "covered",
        finding_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return one complete assessed row set for the assignment."""
        return [
            {
                "requirement": "R1",
                "section": name,
                "surface": surface,
                "result": result,
                "reason": None,
                "evidence": [f"{paths[0]}:1"],
                "finding_ids": [] if finding_ids is None else list(finding_ids),
            }
            for name, paths in sorted(assignment.items())
            for surface in shared.SURFACES
        ]

    def prepare(self, request: dict[str, Any]) -> dict[str, Any]:
        """Run one preparation in the temporary repository."""
        return cast(dict[str, Any], self.adapter.prepare(self.without_rows(request)))

    @staticmethod
    def without_rows(request: dict[str, Any]) -> dict[str, Any]:
        """Return the documented preparation request, which carries no rows."""
        return {key: value for key, value in request.items() if key != "rows"}

    def finalize(
        self, preparation: dict[str, Any], rows: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Run one finalization in the temporary repository."""
        return cast(
            dict[str, Any],
            self.adapter.finalize({"preparation": preparation, "rows": rows}),
        )

    def review(self, request: dict[str, Any]) -> dict[str, Any]:
        """Prepare and finalize one complete review for the request."""
        preparation = self.prepare(request)
        return self.finalize(preparation, cast(list[Any], request["rows"]))

    def test_prepare_binds_the_current_scope_and_inventory(self) -> None:
        request = self.request()
        result = self.prepare(request)
        assert result["inventory_sha256"] == request["inventory"]["inventory_sha256"]
        assert result["scope"]["sha256"]
        assert result["artifact_binding"]["identity"] == result["head"]
        assert [item["section"] for item in result["sections_to_assess"]] == [
            "S1",
            "S2",
            "S3",
        ]
        assert {item["cause"]["kind"] for item in result["sections_to_assess"]} == {
            "first_review"
        }
        assert result["preparation_sha256"]

    def test_prepare_rejects_a_scope_that_is_not_the_frozen_scope(self) -> None:
        request = self.request(scope_paths=["alpha.py"])
        with pytest.raises(shared.RequirementEvidenceError, match="scope binding"):
            self.prepare(request)

    def test_prepare_rejects_an_unassigned_scope_path(self) -> None:
        request = self.request(
            assignment={"S1": ["alpha.py"]}, scope_paths=["alpha.py"]
        )
        with pytest.raises(shared.RequirementEvidenceError, match="scope binding"):
            self.prepare(request)

    def test_finalize_returns_the_record_findings_batch_and_map(self) -> None:
        result = self.review(self.request())
        assert result["record"]["record_sha256"] == result["record_sha256"]
        assert result["findings"] == []
        assert result["requirement_map"].splitlines()[0].startswith("| Requirement |")
        assert (
            result["record"]["artifact_binding"]["identity"]
            == result["record"]["artifact_binding"]["identity"]
        )

    def test_complete_batch_carries_every_visible_material_finding(self) -> None:
        request = self.request(
            rows=self.complete_rows(
                ASSIGNMENT, result="missing_coverage", finding_ids=["F-001"]
            ),
        )
        result = self.review(request)
        assert {finding["id"] for finding in result["findings"]} == {"F-001"}
        assert len(result["findings"]) == 3 * len(shared.SURFACES)

    def test_partial_correction_retains_unrelated_section_and_records_cause(
        self,
    ) -> None:
        first = self.review(
            self.request(
                rows=[
                    *self.complete_rows(
                        {"S1": ["alpha.py"]},
                        result="missing_coverage",
                        finding_ids=["F-001"],
                    ),
                    *self.complete_rows({"S2": ["beta.py"], "S3": ["gamma.py"]}),
                ]
            )
        )
        assert len(first["findings"]) == len(shared.SURFACES)
        record = cast(dict[str, Any], first["record"])
        (self.repository / "beta.py").write_text(
            "def beta():\n    return 222\n", encoding="utf-8"
        )
        corrected = self.request(
            rows=self.complete_rows({"S1": ["alpha.py"], "S2": ["beta.py"]}),
            previous=record,
            previous_sha256=cast(str, record["record_sha256"]),
            corrected_findings=["F-001"],
        )
        second = self.prepare(corrected)
        assert second["retained_sections"] == ["S3"]
        assert {item["section"] for item in second["sections_to_assess"]} == {
            "S1",
            "S2",
        }
        causes = {
            item["section"]: item["cause"] for item in second["sections_to_assess"]
        }
        assert causes["S1"] == {"kind": "finding_corrected", "finding_id": "F-001"}
        assert causes["S2"] == {"kind": "dependency_changed", "changed": ["beta.py"]}
        result = self.finalize(second, cast(list[Any], corrected["rows"]))
        assert result["retained_sections"] == ["S3"]
        assert result["findings"] == []
        assert result["repeat_causes"][0]["cause"]["kind"] == "finding_corrected"

    def test_a_logical_content_change_repeats_the_changed_section(self) -> None:
        first = self.review(self.request())
        record = cast(dict[str, Any], first["record"])
        (self.repository / "beta.py").write_text(
            "def beta():\n    return 222\n", encoding="utf-8"
        )
        again = self.prepare(
            self.request(
                rows=self.complete_rows(ASSIGNMENT),
                previous=record,
                previous_sha256=cast(str, record["record_sha256"]),
            )
        )
        assert again["retained_sections"] == ["S1", "S3"]
        assert [item["section"] for item in again["sections_to_assess"]] == ["S2"]
        assert again["sections_to_assess"][0]["cause"]["changed"] == ["beta.py"]
        assert again["changed_dependencies"][0]["name"] == "beta.py"

    def test_an_unchanged_repeat_retains_every_section(self) -> None:
        record = cast(dict[str, Any], self.review(self.request())["record"])
        again = self.prepare(
            self.request(
                rows=self.complete_rows(ASSIGNMENT),
                previous=record,
                previous_sha256=cast(str, record["record_sha256"]),
            )
        )
        assert again["retained_sections"] == ["S1", "S2", "S3"]
        assert again["sections_to_assess"] == []
        result = self.finalize(again, [])
        assert result["findings"] == []
        assert result["record"]["record_sha256"]

    def test_prepare_rejects_a_prior_record_without_caller_provenance(self) -> None:
        record = cast(dict[str, Any], self.review(self.request())["record"])
        forged = self.request(previous=record, previous_sha256=digest("other"))
        with pytest.raises(shared.RequirementEvidenceError, match="record digest"):
            self.prepare(forged)

    def test_invalid_previous_record_is_rejected(self) -> None:
        record = cast(dict[str, Any], self.review(self.request())["record"])
        tampered = cast(dict[str, Any], json.loads(json.dumps(record)))
        tampered["artifact_binding"]["identity"] = "9" * 40
        forged = self.request(
            previous=tampered,
            previous_sha256=cast(str, record["record_sha256"]),
        )
        with pytest.raises(shared.RequirementEvidenceError, match="record digest"):
            self.prepare(forged)

    def test_finalize_rejects_source_drift_between_preparation_and_finalization(
        self,
    ) -> None:
        request = self.request()
        preparation = self.prepare(request)
        (self.repository / "beta.py").write_text(
            "def beta():\n    return 9\n", encoding="utf-8"
        )
        with pytest.raises(
            shared.RequirementEvidenceError, match="changed after preparation"
        ):
            self.finalize(preparation, cast(list[Any], request["rows"]))

    def test_finalize_rejects_an_incomplete_assessment(self) -> None:
        request = self.request()
        preparation = self.prepare(request)
        rows = cast(list[Any], request["rows"])[:-1]
        with pytest.raises(
            shared.RequirementEvidenceError, match="missing expected cell"
        ):
            self.finalize(preparation, rows)

    def test_finalize_rejects_rows_for_another_inventory(self) -> None:
        request = self.request()
        preparation = self.prepare(request)
        rows = [
            {**row, "requirement": "R2"} for row in cast(list[Any], request["rows"])
        ]
        with pytest.raises(
            shared.RequirementEvidenceError, match="unknown requirement"
        ):
            self.finalize(preparation, rows)

    def test_finalize_rejects_a_tampered_preparation(self) -> None:
        request = self.request()
        preparation = cast(
            dict[str, Any], json.loads(json.dumps(self.prepare(request)))
        )
        preparation["retained_sections"] = ["S1"]
        with pytest.raises(shared.RequirementEvidenceError, match="preparation digest"):
            self.finalize(preparation, cast(list[Any], request["rows"]))

    def test_the_cli_returns_one_json_result_per_command(self) -> None:
        request = self.request()
        prepared = subprocess.run(
            [sys.executable, str(ADAPTER), "prepare"],
            input=json.dumps(self.without_rows(request)),
            capture_output=True,
            text=True,
            cwd=self.repository,
            check=False,
        )
        assert prepared.returncode == 0, prepared.stderr
        preparation = json.loads(prepared.stdout)
        finalized = subprocess.run(
            [sys.executable, str(ADAPTER), "finalize"],
            input=json.dumps({"preparation": preparation, "rows": request["rows"]}),
            capture_output=True,
            text=True,
            cwd=self.repository,
            check=False,
        )
        assert finalized.returncode == 0, finalized.stderr
        result = json.loads(finalized.stdout)
        assert result["record"]["record_sha256"]
        assert result["requirement_map"]

    def test_the_cli_reports_an_invalid_previous_record_without_a_completeness_claim(
        self,
    ) -> None:
        request = self.request(previous={}, previous_sha256=digest("other"))
        failed = subprocess.run(
            [sys.executable, str(ADAPTER), "prepare"],
            input=json.dumps(self.without_rows(request)),
            capture_output=True,
            text=True,
            cwd=self.repository,
            check=False,
        )
        assert failed.returncode == 1
        assert "record" in failed.stderr
        assert "coverage_complete" not in failed.stdout


def _selectors() -> dict[str, Any]:
    """Return the default worktree scope selection for the temporary repository."""
    return {"scope": "worktree", "range": None, "paths": []}


if __name__ == "__main__":
    unittest.main()
