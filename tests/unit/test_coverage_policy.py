"""Unit tests for per-script coverage enforcement."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import coverage_policy


class CoveragePolicyTests(unittest.TestCase):
    def test_rejects_malformed_file_records(self) -> None:
        for report, message in (
            ({}, "no file map"),
            ({"files": {1: {}}}, "invalid file record"),
            ({"files": {"tool.py": {}}}, "no percentage"),
        ):
            with (
                self.subTest(report=report),
                self.assertRaisesRegex(ValueError, message),
            ):
                coverage_policy.coverage_failures(report, 80.0)

    def test_reports_each_executable_below_threshold(self) -> None:
        report = {
            "files": {
                "scripts/good.py": {"summary": {"percent_covered": 90.0}},
                "skills/tool/scripts/bad.py": {"summary": {"percent_covered": 79.9}},
            }
        }

        self.assertEqual(
            ["skills/tool/scripts/bad.py: 79.90% < 80.00%"],
            coverage_policy.coverage_failures(report, 80.0),
        )

    def test_cli_fails_closed_for_missing_or_low_script_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            report_path = root / "coverage.json"
            report_path.write_text(
                json.dumps(
                    {
                        "files": {
                            "scripts/only.py": {"summary": {"percent_covered": 100.0}}
                        }
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
                        "files": {
                            "scripts/tool.py": {"summary": {"percent_covered": 80.0}}
                        }
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
