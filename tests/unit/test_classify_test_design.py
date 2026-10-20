"""Behavior tests for the review check that rejects fixed-source-line tests."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
CLASSIFIER = ROOT / "skills/change-review/scripts/classify_test_design.py"
FIXTURES = ROOT / "tests/fixtures/review"
OFFSET_MAINTENANCE = (
    "update the line",
    "update the offset",
    "update the citation",
    "maintain the offset",
    "adjust the line",
)


def load_classifier(module_name: str) -> Any:
    """Load the classifier module in the current process."""
    specification = importlib.util.spec_from_file_location(module_name, CLASSIFIER)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[module_name] = module
    specification.loader.exec_module(module)
    return module


CLASSIFIER_MODULE = load_classifier("athena_classify_test_design")
REJECTED_FIXTURES = (
    "fixed_offset_citation.txt",
    "fixed_offset_extraction.txt",
    "equivalent_text_search.txt",
)


def run_classifier(*arguments: str) -> subprocess.CompletedProcess[str]:
    """Run the classifier through its real command-line interface."""
    return subprocess.run(
        [sys.executable, str(CLASSIFIER), *arguments],
        capture_output=True,
        text=True,
        check=False,
    )


def classify(path: Path) -> dict[str, Any]:
    """Return the JSON verdict for one test file."""
    result = run_classifier(str(path))
    assert result.returncode == 0, result.stderr
    verdict: dict[str, Any] = json.loads(result.stdout)
    return verdict


def test_fixed_offset_citation_is_rejected() -> None:
    """A citation that must stay within the source file length is not behavior."""
    verdict = classify(FIXTURES / "fixed_offset_citation.txt")
    assert verdict["verdict"] == "reject"
    assert any("citation-offset" in reason for reason in verdict["reasons"])
    assert any("source-file-length" in reason for reason in verdict["reasons"])


def test_fixed_offset_extraction_is_rejected() -> None:
    """Source text selected through a stored line number is not behavior."""
    verdict = classify(FIXTURES / "fixed_offset_extraction.txt")
    assert verdict["verdict"] == "reject"
    assert any("fixed-source-position" in reason for reason in verdict["reasons"])


def test_equivalent_text_search_is_rejected() -> None:
    """A source-text search does not replace the rejected fixed-offset test."""
    verdict = classify(FIXTURES / "equivalent_text_search.txt")
    assert verdict["verdict"] == "reject"
    assert any(
        "equivalent-source-text-search" in reason for reason in verdict["reasons"]
    )


def test_rejection_remediation_offers_behavior_level_or_removal() -> None:
    """Every rejection offers a behavior-level test or removal of the invalid test."""
    for fixture in REJECTED_FIXTURES:
        verdict = classify(FIXTURES / fixture)
        remediation = str(verdict["remediation"])
        assert "observable" in remediation, fixture
        assert "remove the test" in remediation, fixture


def test_rejection_remediation_does_not_request_offset_maintenance() -> None:
    """No rejection asks an author to update a citation offset after an edit."""
    for fixture in REJECTED_FIXTURES:
        remediation = classify(FIXTURES / fixture)["remediation"].casefold()
        for phrase in OFFSET_MAINTENANCE:
            assert phrase not in remediation, f"{fixture}: {phrase}"


def test_behavior_level_inventory_is_accepted() -> None:
    """A test of the observable contract is accepted."""
    verdict = classify(FIXTURES / "behavior_level_inventory.txt")
    assert verdict["verdict"] == "accept"
    assert verdict["reasons"] == []
    assert verdict["remediation"] == ""


def test_parser_diagnostic_is_accepted() -> None:
    """A line number that is the product contract stays accepted."""
    verdict = classify(FIXTURES / "parser_diagnostic.txt")
    assert verdict["verdict"] == "accept"
    assert verdict["reasons"] == []


@pytest.mark.parametrize(
    "relative_path",
    [
        "tests/unit/test_python_syntax_floor.py",
        "tests/unit/test_precommit_single_source.py",
        "tests/unit/test_semver.py",
        "tests/unit/test_change_review_scope_hardening.py",
        "scripts/policies/agent_contract.py",
    ],
)
def test_repository_tests_are_not_rejected(relative_path: str) -> None:
    """Existing layout and convention tests must stay accepted."""
    verdict = classify(ROOT / relative_path)
    assert verdict["verdict"] == "accept", verdict["reasons"]


def test_missing_file_reports_a_concise_failure() -> None:
    """An unreadable input produces a nonzero exit code and no JSON verdict."""
    result = run_classifier(str(FIXTURES / "does_not_exist.txt"))
    assert result.returncode == 1
    assert result.stdout == ""
    assert "does_not_exist.txt" in result.stderr
    assert "Traceback" not in result.stderr


def test_every_fixture_produces_one_verdict_document() -> None:
    """Each fixture produces one JSON document with the complete verdict contract."""
    for fixture in sorted(FIXTURES.glob("*.txt")):
        verdict = classify(fixture)
        assert sorted(verdict) == ["reasons", "remediation", "verdict"], fixture
        assert verdict["verdict"] in {"accept", "reject"}, fixture
        assert isinstance(verdict["reasons"], list), fixture


@pytest.mark.parametrize("fixture", REJECTED_FIXTURES)
def test_in_process_verdict_matches_the_command_line(fixture: str) -> None:
    """The classifier module and its command line give the same verdict."""
    text = (FIXTURES / fixture).read_text(encoding="utf-8")
    in_process = CLASSIFIER_MODULE.classify_text(text)
    assert in_process == classify(FIXTURES / fixture)


def test_line_counter_iteration_is_not_a_fixed_position() -> None:
    """Indexing a source collection with a loop counter is not a stored position."""
    text = (
        "def test_lines() -> None:\n"
        "    lines = read_lines()\n"
        "    for index, line in enumerate(lines):\n"
        "        assert line == lines[index]\n"
    )
    verdict = CLASSIFIER_MODULE.classify_text(text)
    assert verdict["verdict"] == "accept", verdict["reasons"]


def test_source_length_without_a_line_contract_is_not_a_finding() -> None:
    """A counted source collection without a line-number contract stays accepted."""
    text = (
        "def test_files() -> None:\n"
        "    names = sorted(path.name for path in ROOT.iterdir())\n"
        "    assert len(names) > 2\n"
    )
    verdict = CLASSIFIER_MODULE.classify_text(text)
    assert verdict["verdict"] == "accept", verdict["reasons"]


def test_boundary_index_and_fixture_write_are_not_stored_positions() -> None:
    """A first-line, last-line, or fixture-write line is not a stored position."""
    text = (
        "def test_fixture() -> None:\n"
        '    lines = (root / "justfile").read_text(encoding="utf-8").splitlines()\n'
        '    lines[9] = "changed\\n"\n'
        '    assert lines[0] == "# first"\n'
        '    assert lines[-1] == "# last"\n'
    )
    verdict = CLASSIFIER_MODULE.classify_text(text)
    assert verdict["verdict"] == "accept", verdict["reasons"]


def test_main_prints_one_verdict_document(tmp_path: Path) -> None:
    """The command prints one verdict document for a readable test file."""
    sample = tmp_path / "test_sample.py"
    sample.write_text("def test_mode() -> None:\n    assert mode()\n", encoding="utf-8")
    assert CLASSIFIER_MODULE.main([str(sample)]) == 0


def test_main_reports_an_unreadable_input(tmp_path: Path) -> None:
    """The command reports an unreadable input without a JSON verdict."""
    missing = tmp_path / "missing.py"
    assert CLASSIFIER_MODULE.main([str(missing)]) == 1
