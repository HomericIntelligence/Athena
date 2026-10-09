"""Contract tests for the shared issue-planning comment markers."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]
PLANNING_CONTRACT = ROOT / "docs" / "review" / "issue-planning.md"
FINALIZE_SKILL = ROOT / "skills" / "finalize-plan" / "SKILL.md"
ISSUE_EXCHANGE = ROOT / "skills" / "review-exchange" / "scripts" / "issue_exchange.py"


def load_issue_exchange() -> ModuleType:
    """Load the module that owns the marker constants the readers consume."""
    specification = importlib.util.spec_from_file_location(
        "planning_marker_issue_exchange", ISSUE_EXCHANGE
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class PlanningMarkerContractTests(unittest.TestCase):
    """Keep Athena's distributed planning instructions on one marker contract."""

    def test_finalize_skill_repeats_each_current_shared_marker(self) -> None:
        """A future docs-only edit cannot silently split Athena's marker readers."""
        exchange = load_issue_exchange()
        planning_contract = PLANNING_CONTRACT.read_text(encoding="utf-8")
        finalize_skill = FINALIZE_SKILL.read_text(encoding="utf-8")

        for marker in (exchange.PLAN_MARKER, exchange.REVIEW_MARKER):
            self.assertIn(marker, planning_contract)
            self.assertIn(marker, finalize_skill)

        # The finalize marker is a prefix plus a key=value template. Both the
        # prefix and the template now have one owner in the reader module.
        self.assertIn(exchange.FINALIZE_MARKER_TEMPLATE, planning_contract)
        self.assertIn(exchange.FINALIZE_MARKER_TEMPLATE, finalize_skill)
