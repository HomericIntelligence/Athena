"""Unit tests for scripts/validate_skills.py."""

from __future__ import annotations

import importlib.util
import io
import json
import shutil
import subprocess
import sys
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
                ".venv",
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

    def test_cli_reports_malformed_current_manifest_without_traceback(self) -> None:
        manifest = self.fixture / ".codex-plugin" / "plugin.json"
        manifest.write_text("not-json\n", encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                str(self.fixture / "scripts" / "validate_skills.py"),
                "--root",
                str(self.fixture),
            ],
            cwd=self.fixture,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(2, result.returncode)
        self.assertIn("cannot read .codex-plugin/plugin.json", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

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
        script = self.fixture / "skills" / "pr-review" / "scripts" / "resolve_pr.py"
        script.write_text(
            "#!/usr/bin/env python3\nprint('no parser')\n", encoding="utf-8"
        )

        self.assert_invalid(
            "cli", "must construct its argparse parser with argument_parser()"
        )

    def test_executable_scripts_cannot_hide_direct_argparse_behind_dead_factory_call(
        self,
    ) -> None:
        script = self.fixture / "skills" / "pr-review" / "scripts" / "resolve_pr.py"
        script.write_text(
            "#!/usr/bin/env python3\n"
            "import argparse\n"
            "from skills._cli import argument_parser\n"
            "if False:\n"
            "    argument_parser()\n"
            "parser = argparse.ArgumentParser()\n",
            encoding="utf-8",
        )

        self.assert_invalid(
            "cli", "must not construct argparse.ArgumentParser directly"
        )

    def test_executable_scripts_may_alias_the_shared_parser_factory(self) -> None:
        script = self.fixture / "skills" / "pr-review" / "scripts" / "resolve_pr.py"
        script.write_text(
            "#!/usr/bin/env python3\n"
            "from skills._cli import argument_parser as make_parser\n"
            "parser = make_parser()\n"
            "parser.parse_args()\n",
            encoding="utf-8",
        )

        self.assertEqual(validator.validate_repository(self.fixture), [])

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
                    ".venv",
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

    def test_repo_review_scorecard_rejects_section_and_weight_mismatches(self) -> None:
        criteria = (
            self.fixture / "skills" / "repo-review" / "references" / "criteria.md"
        )
        criteria.write_text(
            criteria.read_text(encoding="utf-8").replace(
                "**Reliability:**", "**Resilience:**", 1
            ),
            encoding="utf-8",
        )
        self.assert_invalid("repo-review", "weight has no matching criteria section")

        criteria.write_text(
            criteria.read_text(encoding="utf-8").replace(
                "**Resilience:**", "**Reliability:**", 1
            ),
            encoding="utf-8",
        )
        skill = self.fixture / "skills" / "repo-review" / "SKILL.md"
        skill.write_text(
            skill.read_text(encoding="utf-8").replace(
                "Reliability 10%", "Reliability 9%", 1
            ),
            encoding="utf-8",
        )
        self.assert_invalid("repo-review", "weights must total 100%")

    def test_ruleset_requires_a_current_main_merge_gate(self) -> None:
        path = self.fixture / ".github" / "rulesets" / "homeric-main-baseline.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        status_checks = next(
            rule
            for rule in document["rules"]
            if rule["type"] == "required_status_checks"
        )
        status_checks["parameters"]["strict_required_status_checks_policy"] = False
        path.write_text(json.dumps(document), encoding="utf-8")

        self.assert_invalid("ruleset", "must require checks current with main")

        status_checks["parameters"]["strict_required_status_checks_policy"] = True
        status_checks["parameters"]["required_status_checks"] = []
        path.write_text(json.dumps(document), encoding="utf-8")

        self.assert_invalid("ruleset", "must require required-checks-gate")

    def test_ruleset_requires_the_approved_staged_merge_queue_policy(self) -> None:
        path = self.fixture / ".github" / "rulesets" / "homeric-main-baseline.json"
        original = path.read_text(encoding="utf-8")
        document = json.loads(original)
        document["rules"] = [
            rule for rule in document["rules"] if rule.get("type") != "merge_queue"
        ]
        path.write_text(json.dumps(document), encoding="utf-8")

        self.assert_invalid("ruleset", "merge queue policy is missing")

        document = json.loads(original)
        merge_queue = next(
            (rule for rule in document["rules"] if rule.get("type") == "merge_queue"),
            None,
        )
        if merge_queue is None:
            merge_queue = {
                "type": "merge_queue",
                "parameters": {
                    "check_response_timeout_minutes": 60,
                    "grouping_strategy": "ALLGREEN",
                    "max_entries_to_build": 10,
                    "max_entries_to_merge": 5,
                    "merge_method": "SQUASH",
                    "min_entries_to_merge": 1,
                    "min_entries_to_merge_wait_minutes": 5,
                },
            }
            document["rules"].append(merge_queue)
        merge_queue["parameters"]["merge_method"] = "MERGE"
        path.write_text(json.dumps(document), encoding="utf-8")

        self.assert_invalid("ruleset", "merge queue policy does not match")

    def test_obsolete_distribution_path_fails(self) -> None:
        (self.fixture / "athena").mkdir()
        self.assert_invalid("layout", "obsolete distribution path exists: athena")

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
