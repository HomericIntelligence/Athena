"""Standard-library contract tests for scripts/validate_skills.py."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "validate_skills.py"
SPEC = importlib.util.spec_from_file_location("athena_validate_skills", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class DistributionTests(unittest.TestCase):
    """Exercise the live plugin distribution contract."""

    def test_repository_is_valid(self) -> None:
        self.assertEqual(validator.validate(), [])

    def test_frontmatter_parser(self) -> None:
        self.assertEqual(validator._frontmatter_name("---\nname: example\n---\n"), "example")
        self.assertIsNone(validator._frontmatter_name("# missing frontmatter\n"))

    def test_dependency_contract_sets(self) -> None:
        self.assertEqual(validator.KNOWLEDGE_SKILLS, {"advise", "learn"})
        self.assertIn("tidy", validator.AUTOMATION_SKILLS)
        self.assertIn("finish-branch", validator.AUTOMATION_SKILLS)

    def test_review_scoring_starts_at_zero(self) -> None:
        root = MODULE_PATH.parents[1]
        for skill in ("pr-review", "repo-review"):
            text = (root / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("0%", text)
            self.assertNotIn("starts at F", text)


if __name__ == "__main__":
    unittest.main()
