"""Unit tests for per-script coverage enforcement."""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import coverage_policy


class CoveragePolicyTests(unittest.TestCase):
    def test_rejects_malformed_file_records(self) -> None:
        reports: tuple[object, ...] = (
            {},
            {
                "meta": {"branch_coverage": True},
                "files": {
                    1: {
                        "summary": {
                            "percent_covered": 90.0,
                            "num_branches": 100,
                            "covered_branches": 100,
                            "missing_branches": 0,
                        }
                    }
                },
            },
            {"meta": {"branch_coverage": True}, "files": {"tool.py": {}}},
        )
        for report in reports:
            with (
                self.subTest(report=report),
                self.assertRaises(TypeError),
            ):
                coverage_policy.coverage_failures(report, 80.0)

    def test_reports_each_executable_below_threshold(self) -> None:
        report = {
            "meta": {"branch_coverage": True},
            "files": {
                "scripts/good.py": {
                    "summary": {
                        "percent_covered": 90.0,
                        "num_branches": 100,
                        "covered_branches": 100,
                        "missing_branches": 0,
                    }
                },
                "skills/tool/scripts/bad.py": {
                    "summary": {
                        "percent_covered": 79.9,
                        "num_branches": 100,
                        "covered_branches": 100,
                        "missing_branches": 0,
                    }
                },
            },
        }

        failures = coverage_policy.coverage_failures(report, 80.0)

        self.assertEqual(1, len(failures))
        path, separator, diagnostic = failures[0].partition(":")
        self.assertEqual("skills/tool/scripts/bad.py", path)
        self.assertEqual(":", separator)
        self.assertEqual(["79.90", "80.00"], re.findall(r"\b\d+\.\d{2}\b", diagnostic))

    def test_cli_fails_closed_for_missing_or_low_script_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            report_path = root / "coverage.json"
            report_path.write_text(
                json.dumps(
                    {
                        "meta": {"branch_coverage": True},
                        "files": {
                            "scripts/only.py": {
                                "summary": {
                                    "percent_covered": 100.0,
                                    "num_branches": 100,
                                    "covered_branches": 100,
                                    "missing_branches": 0,
                                }
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            expected = root / "expected.txt"
            expected.write_text(
                "scripts/only.py\nskills/tool/scripts/missing.py\n", encoding="utf-8"
            )

            result = coverage_policy.main(
                [
                    str(report_path),
                    "--expected-from",
                    str(expected),
                    "--minimum",
                    "80",
                ]
            )

        self.assertEqual(1, result)

    def test_combined_coverage_cannot_hide_low_branch_coverage(self) -> None:
        report = {
            "meta": {"branch_coverage": True},
            "files": {
                "tool.py": {
                    "summary": {
                        "percent_covered": 99.0,
                        "num_branches": 100,
                        "covered_branches": 79,
                        "missing_branches": 21,
                    }
                }
            },
        }
        failures = coverage_policy.coverage_failures(report, 80.0)
        self.assertEqual(1, len(failures))
        self.assertTrue(failures[0].startswith("tool.py:"))

    def test_branch_boundaries_and_branch_free_files(self) -> None:
        cases = (
            (79, 100, 99.0, 1),
            (80, 100, 99.0, 0),
            (81, 100, 99.0, 0),
            (100, 100, 79.0, 1),
            (0, 0, 100.0, 0),
            (0, 0, 79.0, 1),
            (79999, 100000, 99.0, 1),
        )
        for covered, total, percent, expected in cases:
            with self.subTest(covered=covered, total=total, percent=percent):
                report = self.branch_report(covered, total, percent)
                self.assertEqual(
                    expected, len(coverage_policy.coverage_failures(report, 80.0))
                )

    @staticmethod
    def branch_report(
        covered: int = 80, total: int = 100, percent: float = 99.0
    ) -> dict[str, object]:
        return {
            "meta": {"branch_coverage": True},
            "files": {
                "tool.py": {
                    "summary": {
                        "percent_covered": percent,
                        "num_branches": total,
                        "covered_branches": covered,
                        "missing_branches": total - covered,
                    }
                }
            },
        }

    def test_rejects_missing_or_invalid_branch_measurement(self) -> None:
        for meta in (None, {}, {"branch_coverage": False}, {"branch_coverage": 1}):
            report = self.branch_report()
            report["meta"] = meta
            with self.subTest(meta=meta), self.assertRaises((TypeError, ValueError)):
                coverage_policy.coverage_failures(report, 80.0)

    def test_rejects_malformed_summary_evidence(self) -> None:
        valid: dict[str, object] = {
            "percent_covered": 99.0,
            "num_branches": 100,
            "covered_branches": 80,
            "missing_branches": 20,
        }
        cases: list[tuple[str, object]] = [
            (field, value)
            for field in ("num_branches", "covered_branches", "missing_branches")
            for value in (None, True, -1, "100", 100.0)
        ]
        cases.extend(
            ("percent_covered", value)
            for value in (True, None, -1, 101, float("nan"), float("inf"), "90")
        )
        cases.extend(
            (("covered_branches", 101), ("missing_branches", 0), ("num_branches", 0))
        )
        for field, value in cases:
            summary = dict(valid)
            if value is None:
                del summary[field]
            else:
                summary[field] = value
            report = {
                "meta": {"branch_coverage": True},
                "files": {"tool.py": {"summary": summary}},
            }
            with (
                self.subTest(field=field, value=value),
                self.assertRaises((TypeError, ValueError)),
            ):
                coverage_policy.coverage_failures(report, 80.0)

    def test_cli_distinguishes_low_branch_coverage_from_invalid_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            report = root / "coverage.json"
            expected = root / "expected.txt"
            expected.write_text("tool.py\n", encoding="utf-8")
            for document, exit_code in (
                (self.branch_report(79), 1),
                ({"files": {}}, 2),
            ):
                report.write_text(json.dumps(document), encoding="utf-8")
                with self.subTest(exit_code=exit_code), patch("sys.stderr"):
                    self.assertEqual(
                        exit_code,
                        coverage_policy.main(
                            [str(report), "--expected-from", str(expected)]
                        ),
                    )

    def test_expected_scripts_discovers_root_and_skill_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "scripts").mkdir()
            (root / "scripts" / "__init__.py").touch()
            (root / "scripts" / "root_helper.py").touch()
            skill_scripts = root / "skills" / "tool" / "scripts"
            skill_scripts.mkdir(parents=True)
            (skill_scripts / "skill_helper.py").touch()

            scripts = coverage_policy.expected_scripts(root)

        self.assertEqual(
            {"scripts/root_helper.py", "skills/tool/scripts/skill_helper.py"},
            scripts,
        )

    def test_cli_succeeds_and_malformed_report_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            report = root / "coverage.json"
            expected = root / "expected.txt"
            expected.write_text("scripts/tool.py\n", encoding="utf-8")
            report.write_text(
                json.dumps(
                    {
                        "meta": {"branch_coverage": True},
                        "files": {
                            "scripts/tool.py": {
                                "summary": {
                                    "percent_covered": 80.0,
                                    "num_branches": 100,
                                    "covered_branches": 100,
                                    "missing_branches": 0,
                                }
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                0,
                coverage_policy.main([str(report), "--expected-from", str(expected)]),
            )
            report.write_text("not json", encoding="utf-8")
            with patch("sys.stderr"):
                self.assertEqual(2, coverage_policy.main([str(report)]))


if __name__ == "__main__":
    unittest.main()
