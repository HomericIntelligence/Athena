"""Unit tests for scripts/validate_skills.py."""

from __future__ import annotations

import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
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
                ".git",
                ".pixi",
                "dist",
                "build",
                "__pycache__",
                "*.pyc",
                ".coverage*",
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
        document = json.loads(manifest.read_text(encoding="utf-8"))
        document["version"] = "9.9.9"
        manifest.write_text(json.dumps(document), encoding="utf-8")
        self.assert_invalid(
            "version", "Claude marketplace and manifest versions differ"
        )

    def test_manifests_accept_full_semver(self) -> None:
        version = "2.0.0-rc.1+build.5"
        for relative in (
            ".claude-plugin/plugin.json",
            ".codex-plugin/plugin.json",
        ):
            path = self.fixture / relative
            document = json.loads(path.read_text(encoding="utf-8"))
            document["version"] = version
            path.write_text(json.dumps(document), encoding="utf-8")
        marketplace = self.fixture / ".claude-plugin" / "marketplace.json"
        document = json.loads(marketplace.read_text(encoding="utf-8"))
        document["metadata"]["version"] = version
        marketplace.write_text(json.dumps(document), encoding="utf-8")

        self.assertEqual(validator.validate_repository(self.fixture), [])

    def test_independent_host_manifest_contracts_fail_closed(self) -> None:
        cases: tuple[tuple[str, Callable[[dict[str, Any]], None], str, str], ...] = (
            (
                ".claude-plugin/marketplace.json",
                lambda value: value.update({"plugins": []}),
                "claude",
                "exactly one plugin",
            ),
            (
                ".claude-plugin/marketplace.json",
                lambda value: value["plugins"][0].update({"name": "wrong"}),
                "claude",
                "must be named 'athena'",
            ),
            (
                ".claude-plugin/plugin.json",
                lambda value: value.update({"skills": "./wrong/"}),
                "claude",
                "load './skills/'",
            ),
            (
                ".agents/plugins/marketplace.json",
                lambda value: value.update({"plugins": []}),
                "codex",
                "exactly one plugin",
            ),
            (
                ".agents/plugins/marketplace.json",
                lambda value: value["plugins"][0].update({"source": "wrong"}),
                "codex",
                "local source './'",
            ),
            (
                ".codex-plugin/plugin.json",
                lambda value: value.update({"skills": "./wrong/"}),
                "codex",
                "load './skills/'",
            ),
            (
                ".codex-plugin/plugin.json",
                lambda value: value.update({"version": "v1"}),
                "version",
                "valid SemVer",
            ),
        )
        for relative, mutate, surface, reason in cases:
            with self.subTest(relative=relative, reason=reason):
                path = self.fixture / relative
                original = path.read_text(encoding="utf-8")
                value: dict[str, Any] = json.loads(original)
                mutate(value)
                path.write_text(json.dumps(value), encoding="utf-8")
                self.assert_invalid(surface, reason)
                path.write_text(original, encoding="utf-8")

    def test_private_skill_directory_fails(self) -> None:
        private = self.fixture / "skills" / "_private"
        private.mkdir()
        (private / "SKILL.md").write_text(
            "---\nname: _private\n---\n", encoding="utf-8"
        )
        self.assert_invalid("skills", "private skill directory is forbidden")

    def test_python_cache_is_not_treated_as_a_private_skill(self) -> None:
        cache = self.fixture / "skills" / "__pycache__"
        cache.mkdir(exist_ok=True)
        (cache / "cached.pyc").write_bytes(b"cache")

        self.assertEqual(validator.validate_repository(self.fixture), [])

    def test_executable_scripts_must_use_shared_argparse_convention(self) -> None:
        script = self.fixture / "skills" / "code-review" / "scripts" / "review_diff.py"
        script.write_text(
            "#!/usr/bin/env python3\nprint('no parser')\n", encoding="utf-8"
        )

        self.assert_invalid(
            "cli", "must construct its argparse parser with argument_parser()"
        )

    def test_unapproved_ecosystem_repository_fails(self) -> None:
        repository = "HomericIntelligence/" + "UnapprovedRepository"
        (self.fixture / "docs" / "bad.md").write_text(
            f"depends on {repository}", encoding="utf-8"
        )
        self.assert_invalid("self-contained", repository)

    def test_unapproved_ecosystem_repository_is_case_insensitive(self) -> None:
        repository = "hOmErIc" + "InTeLlIgEnCe/" + "UnapprovedRepository"
        (self.fixture / "docs" / "bad.md").write_text(
            f"depends on https://github.com/{repository}", encoding="utf-8"
        )
        self.assert_invalid("self-contained", repository)

    def test_distributable_coverage_prefixed_file_is_inspected(self) -> None:
        repository = "HomericIntelligence/" + "UnapprovedRepository"
        (self.fixture / "docs" / ".coverage-bypass.md").write_text(
            f"depends on {repository}", encoding="utf-8"
        )
        self.assert_invalid("self-contained", repository)

    def test_checkout_under_ignored_named_ancestor_is_still_inspected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture = Path(temporary_directory) / "build" / "Athena"
            shutil.copytree(
                ROOT,
                fixture,
                ignore=shutil.ignore_patterns(
                    ".git",
                    ".pixi",
                    "dist",
                    "build",
                    "__pycache__",
                    "*.pyc",
                    ".coverage*",
                ),
            )
            repository = "HomericIntelligence/" + "UnapprovedRepository"
            (fixture / "docs" / "bad.md").write_text(
                f"depends on {repository}", encoding="utf-8"
            )

            errors = validator.validate_repository(fixture)

        self.assertTrue(
            any(
                error.surface == "self-contained" and repository in error.reason
                for error in errors
            ),
            errors,
        )

    def test_distributable_nested_ignored_name_is_still_inspected(self) -> None:
        repository = "HomericIntelligence/" + "UnapprovedRepository"
        directory = self.fixture / "docs" / "dist"
        directory.mkdir()
        (directory / "bad.md").write_text(f"depends on {repository}", encoding="utf-8")
        self.assert_invalid("self-contained", repository)

    def test_project_prefix_is_rejected(self) -> None:
        forbidden = "Project" + "Example"
        (self.fixture / "docs" / "bad.md").write_text(forbidden, encoding="utf-8")
        self.assert_invalid("self-contained", forbidden)

    def test_missing_required_policy_file_fails(self) -> None:
        (self.fixture / "docs" / "policies" / "required-checks.md").unlink()
        self.assert_invalid(
            "policy", "required file is missing: docs/policies/required-checks.md"
        )

    def test_obsolete_distribution_path_fails(self) -> None:
        (self.fixture / "pyproject.toml").write_text(
            "[project]\nname='forbidden'\n", encoding="utf-8"
        )
        self.assert_invalid(
            "layout", "obsolete distribution path exists: pyproject.toml"
        )

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
