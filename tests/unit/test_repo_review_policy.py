"""Unit tests for scripts/policies/repo_review.py."""

from __future__ import annotations

import unittest
from pathlib import Path

from scripts.policies.repo_review import evaluate_scorecard

ROOT = Path(__file__).resolve().parents[2]
CRITERIA_PATH = ROOT / "docs" / "review" / "repository-scorecard.md"
SKILL_PATH = ROOT / "skills" / "repo-review" / "SKILL.md"


def _criteria() -> str:
    return CRITERIA_PATH.read_text(encoding="utf-8")


def _skill() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


class EvaluateScorecardTests(unittest.TestCase):
    """Exercise the scorecard criteria and weight contracts."""

    def test_tracked_scorecard_has_no_violation(self) -> None:
        self.assertEqual(evaluate_scorecard(_criteria(), _skill()), [])

    def test_criteria_section_contract(self) -> None:
        cases: tuple[tuple[str, str, str], ...] = (
            ("non-contiguous", _criteria().replace("2. **", "3. **", 1), "uniquely"),
            ("duplicate", _criteria().replace("2. **", "1. **", 1), "uniquely"),
        )
        for name, criteria, literal in cases:
            with self.subTest(name=name):
                errors = evaluate_scorecard(criteria, _skill())
                self.assertEqual(1, len(errors), errors)
                self.assertIn(literal, errors[0])

    def test_missing_weights_line(self) -> None:
        skill = _skill().replace("Weights: ", "Weight: ", 1)
        self.assertEqual(
            evaluate_scorecard(_criteria(), skill),
            ["The scorecard weights are missing."],
        )

    def test_weight_contract(self) -> None:
        cases: tuple[tuple[str, str, str], ...] = (
            ("wrong count", _skill().replace("Reliability 9%", "", 1), "one weight"),
            (
                "unknown weight",
                _skill().replace("Reliability 9%", "Zzz 9%", 1),
                "no matching criteria section",
            ),
            (
                "unweighted section",
                _skill().replace("Reliability 9%", "", 1),
                "does not assign a weight",
            ),
            (
                "wrong total",
                _skill().replace("Reliability 9%", "Reliability 8%", 1),
                "must total 100 percent",
            ),
        )
        for name, skill, literal in cases:
            with self.subTest(name=name):
                errors = evaluate_scorecard(_criteria(), skill)
                self.assertTrue(errors, errors)
                self.assertTrue(any(literal in error for error in errors), errors)
