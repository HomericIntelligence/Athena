"""Contract tests for the shared issue-planning comment markers."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLANNING_CONTRACT = ROOT / "docs" / "review" / "issue-planning.md"
FINALIZE_SKILL = ROOT / "skills" / "finalize-plan" / "SKILL.md"

CURRENT_MARKERS = (
    "<!-- HomericIntelligence:plan-issue -->",
    "<!-- HomericIntelligence:issue-review -->",
    "<!-- HomericIntelligence:finalize-plan R=<R> P=<P> V=<V> F=<F> -->",
)


class PlanningMarkerContractTests(unittest.TestCase):
    """Keep Athena's distributed planning instructions on one marker contract."""

    def test_finalize_skill_repeats_each_current_shared_marker(self) -> None:
        """A future docs-only edit cannot silently split Athena's marker readers."""
        planning_contract = PLANNING_CONTRACT.read_text(encoding="utf-8")
        finalize_skill = FINALIZE_SKILL.read_text(encoding="utf-8")

        for marker in CURRENT_MARKERS:
            self.assertIn(marker, planning_contract)
            self.assertIn(marker, finalize_skill)
