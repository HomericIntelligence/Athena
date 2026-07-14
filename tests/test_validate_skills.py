"""Standard-library contract tests for scripts/validate_skills.py."""

from __future__ import annotations

import importlib.util
import io
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "validate_skills.py"
SPEC = importlib.util.spec_from_file_location("athena_validate_skills", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class DistributionTests(unittest.TestCase):
    """Exercise positive and negative plugin-distribution contracts."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.fixture = Path(self.temporary_directory.name) / "Athena"
        shutil.copytree(
            ROOT,
            self.fixture,
            ignore=shutil.ignore_patterns(
                ".git", ".pixi", "dist", "build", "__pycache__", "*.pyc"
            ),
        )

    def assert_invalid(self, surface: str, reason: str) -> None:
        errors = validator.validate_repository(self.fixture)
        self.assertTrue(
            any(
                error.surface == surface and reason in error.reason for error in errors
            ),
            errors,
        )

    def test_repository_is_valid(self) -> None:
        self.assertEqual(validator.validate_repository(self.fixture), [])

    def test_frontmatter_parser(self) -> None:
        self.assertEqual(
            validator._frontmatter_name("---\nname: example\n---\n"), "example"
        )
        self.assertIsNone(validator._frontmatter_name("# missing frontmatter\n"))

    def test_missing_skill_file_fails(self) -> None:
        (self.fixture / "skills" / "advise" / "SKILL.md").unlink()
        self.assert_invalid("skills", "cannot read skills/advise/SKILL.md")

    def test_missing_skills_directory_fails(self) -> None:
        shutil.rmtree(self.fixture / "skills")
        self.assert_invalid("skills", "skills/ directory is missing")

    def test_duplicate_skill_name_fails(self) -> None:
        skill = self.fixture / "skills" / "brainstorm" / "SKILL.md"
        skill.write_text(
            skill.read_text(encoding="utf-8").replace(
                "name: brainstorm", "name: advise", 1
            ),
            encoding="utf-8",
        )
        self.assert_invalid("skills", "duplicate skill name: advise")

    def test_malformed_manifest_fails(self) -> None:
        (self.fixture / ".codex-plugin" / "plugin.json").write_text(
            "[]", encoding="utf-8"
        )
        self.assert_invalid("codex", "must be a JSON object")

    def test_manifest_version_mismatch_fails(self) -> None:
        manifest = self.fixture / ".claude-plugin" / "plugin.json"
        manifest.write_text(
            manifest.read_text(encoding="utf-8").replace('"0.1.0"', '"9.9.9"'),
            encoding="utf-8",
        )
        self.assert_invalid(
            "version", "Claude marketplace and manifest versions differ"
        )

    def test_dependency_substitution_fails(self) -> None:
        skill = self.fixture / "skills" / "advise" / "SKILL.md"
        skill.write_text(
            skill.read_text(encoding="utf-8").replace(
                "HomericIntelligence/Mnemosyne", "attacker/Mnemosyne"
            ),
            encoding="utf-8",
        )
        self.assert_invalid("knowledge", "HomericIntelligence/Mnemosyne")

    def test_learn_without_pr_success_contract_fails(self) -> None:
        skill = self.fixture / "skills" / "learn" / "SKILL.md"
        skill.write_text(
            skill.read_text(encoding="utf-8").replace("PR URL", "local path"),
            encoding="utf-8",
        )
        self.assert_invalid("knowledge", "PR URL")

    def test_review_without_full_coverage_fails(self) -> None:
        skill = self.fixture / "skills" / "repo-review" / "SKILL.md"
        skill.write_text(
            skill.read_text(encoding="utf-8").replace(
                "Full coverage", "Partial coverage"
            ),
            encoding="utf-8",
        )
        self.assert_invalid("review", "Full coverage")

    def test_lowercase_ecosystem_reference_fails(self) -> None:
        forbidden_name = "odys" + "seus"
        (self.fixture / "docs" / "bad.md").write_text(
            f"depends on {forbidden_name}", encoding="utf-8"
        )
        self.assert_invalid("self-contained", forbidden_name)

    def test_obsolete_distribution_path_fails(self) -> None:
        (self.fixture / "pyproject.toml").write_text(
            "[project]\nname='forbidden'\n", encoding="utf-8"
        )
        self.assert_invalid(
            "layout", "obsolete distribution path exists: pyproject.toml"
        )

    def test_review_scoring_starts_at_zero(self) -> None:
        for skill in ("pr-review", "repo-review"):
            text = (self.fixture / "skills" / skill / "SKILL.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("0%", text)
            self.assertNotIn("starts at F", text)

    def test_cli_quiet_success(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            result = validator.main(["--root", str(self.fixture), "--quiet"])
        self.assertEqual(result, 0)
        self.assertEqual(output.getvalue(), "")

    def test_cli_failure_is_actionable(self) -> None:
        shutil.rmtree(self.fixture / "skills")
        errors = io.StringIO()
        with redirect_stderr(errors):
            result = validator.main(["--root", str(self.fixture)])
        self.assertEqual(result, 2)
        self.assertIn("skills/ directory is missing", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
