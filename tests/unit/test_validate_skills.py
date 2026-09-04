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
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

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

    def assert_validation_errors(
        self,
        validate: Callable[[Path], list[Any]],
        surface: str,
        *,
        count: int = 1,
        literal: str | None = None,
    ) -> None:
        errors = validate(self.fixture)
        self.assertEqual([surface] * count, [error.surface for error in errors], errors)
        if literal is not None:
            self.assertEqual(
                1,
                sum(literal in error.reason for error in errors),
                errors,
            )

    def test_repository_is_valid(self) -> None:
        self.assertEqual(validator.validate_repository(self.fixture), [])

    def test_repository_requires_the_exact_root_claude_pointer(self) -> None:
        (self.fixture / "CLAUDE.md").write_bytes(b"@AGENTS.md")

        errors = validator.validate_repository(self.fixture)

        self.assertTrue(
            any(
                error.surface == "agent-contract" and "CLAUDE.md" in error.reason
                for error in errors
            ),
            errors,
        )

    def test_repository_requires_the_generated_principles_block(self) -> None:
        path = self.fixture / "AGENTS.md"
        text = path.read_text(encoding="utf-8")
        start_marker = (
            "<!-- BEGIN ATHENA DEVELOPMENT PRINCIPLES: agent-contract-v1.0.0 -->"
        )
        end_marker = "<!-- END ATHENA DEVELOPMENT PRINCIPLES -->"
        start = text.find(start_marker)
        end = text.find(end_marker)
        if start >= 0 and end >= start:
            text = text[:start] + text[end + len(end_marker) :]
        path.write_text(text, encoding="utf-8")

        errors = validator.validate_repository(self.fixture)

        self.assertTrue(
            any(
                error.surface == "agent-contract" and "AGENTS.md" in error.reason
                for error in errors
            ),
            errors,
        )

    def test_frontmatter_parser(self) -> None:
        self.assertEqual(
            validator._frontmatter_name("---\nname: example\n---\n"), "example"
        )
        self.assertIsNone(validator._frontmatter_name("# missing frontmatter\n"))

    def test_missing_skill_file_fails(self) -> None:
        (self.fixture / "skills" / "advise" / "SKILL.md").unlink()
        self.assert_validation_errors(
            validator._validate_skills, "skills", literal="advise"
        )

    def test_missing_skills_directory_fails(self) -> None:
        shutil.rmtree(self.fixture / "skills")
        self.assert_validation_errors(
            validator._validate_skills, "skills", literal="skills/"
        )

    def test_duplicate_skill_name_fails(self) -> None:
        skill = self.fixture / "skills" / "brainstorm" / "SKILL.md"
        original = skill.read_text(encoding="utf-8")
        skill.write_text(
            original.replace("name: brainstorm", "name: unique-name", 1),
            encoding="utf-8",
        )
        self.assert_validation_errors(
            validator._validate_skills, "skills", literal="unique-name"
        )

        skill.write_text(
            original.replace("name: brainstorm", "name: advise", 1),
            encoding="utf-8",
        )
        self.assert_validation_errors(validator._validate_skills, "skills", count=2)

    def test_malformed_manifest_fails(self) -> None:
        (self.fixture / ".codex-plugin" / "plugin.json").write_text(
            "[]", encoding="utf-8"
        )
        self.assert_validation_errors(
            validator._validate_codex,
            "codex",
            literal=".codex-plugin/plugin.json",
        )

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

        self.assertEqual(1, result.returncode)
        self.assertIn(".codex-plugin/plugin.json", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_manifest_version_mismatch_fails(self) -> None:
        manifest = self.fixture / ".claude-plugin" / "plugin.json"
        document = json.loads(manifest.read_text(encoding="utf-8"))
        document["version"] = "9.9.9"
        manifest.write_text(json.dumps(document), encoding="utf-8")
        self.assert_validation_errors(validator._validate_claude, "version")

    def test_pi_manifest_must_declare_only_the_canonical_skill_root(self) -> None:
        package = self.fixture / "package.json"
        package.write_text(
            json.dumps(
                {
                    "name": "@homericintelligence/athena",
                    "version": "0.3.0",
                    "keywords": ["pi-package"],
                    "pi": {"skills": ["./wrong"]},
                }
            ),
            encoding="utf-8",
        )

        self.assert_validation_errors(validator._validate_pi, "pi")

    def test_pi_manifest_version_must_match_the_host_manifests(self) -> None:
        package = self.fixture / "package.json"
        document = json.loads(package.read_text(encoding="utf-8"))
        document["version"] = "9.9.9"
        package.write_text(json.dumps(document), encoding="utf-8")

        self.assert_validation_errors(validator.validate_repository, "version")

    def test_opencode_package_must_be_named_for_the_plugin(self) -> None:
        manifest = self.fixture / "npm" / "athena-opencode" / "package.json"
        document = json.loads(manifest.read_text(encoding="utf-8"))
        document["name"] = "wrong"
        manifest.write_text(json.dumps(document), encoding="utf-8")

        self.assert_validation_errors(validator._validate_opencode, "opencode")

    def test_opencode_package_must_expose_the_plugin_entry(self) -> None:
        manifest = self.fixture / "npm" / "athena-opencode" / "package.json"
        document = json.loads(manifest.read_text(encoding="utf-8"))
        document["main"] = "wrong.js"
        manifest.write_text(json.dumps(document), encoding="utf-8")

        self.assert_validation_errors(validator._validate_opencode, "opencode")

    def test_opencode_package_must_declare_the_plugin_keyword(self) -> None:
        manifest = self.fixture / "npm" / "athena-opencode" / "package.json"
        document = json.loads(manifest.read_text(encoding="utf-8"))
        document["keywords"] = ["opencode"]
        manifest.write_text(json.dumps(document), encoding="utf-8")

        self.assert_validation_errors(validator._validate_opencode, "opencode")

    def test_opencode_package_must_publish_the_skill_corpus(self) -> None:
        manifest = self.fixture / "npm" / "athena-opencode" / "package.json"
        document = json.loads(manifest.read_text(encoding="utf-8"))
        document["files"] = ["plugin.js"]
        manifest.write_text(json.dumps(document), encoding="utf-8")

        self.assert_validation_errors(validator._validate_opencode, "opencode")

    def test_opencode_manifest_version_must_match_the_host_manifests(self) -> None:
        manifest = self.fixture / "npm" / "athena-opencode" / "package.json"
        document = json.loads(manifest.read_text(encoding="utf-8"))
        document["version"] = "9.9.9"
        manifest.write_text(json.dumps(document), encoding="utf-8")

        self.assert_validation_errors(validator.validate_repository, "version")

    def test_manifests_accept_full_semver(self) -> None:
        version = "2.0.0-rc.1+build.5"
        for relative in (
            ".claude-plugin/plugin.json",
            ".codex-plugin/plugin.json",
            "npm/athena-opencode/package.json",
        ):
            path = self.fixture / relative
            document = json.loads(path.read_text(encoding="utf-8"))
            document["version"] = version
            path.write_text(json.dumps(document), encoding="utf-8")
        marketplace = self.fixture / ".claude-plugin" / "marketplace.json"
        document = json.loads(marketplace.read_text(encoding="utf-8"))
        document["metadata"]["version"] = version
        marketplace.write_text(json.dumps(document), encoding="utf-8")
        package = self.fixture / "package.json"
        document = json.loads(package.read_text(encoding="utf-8"))
        document["version"] = version
        package.write_text(json.dumps(document), encoding="utf-8")

        self.assertEqual(validator.validate_repository(self.fixture), [])

    def test_independent_host_manifest_contracts_fail_closed(self) -> None:
        cases: tuple[tuple[str, Callable[[dict[str, Any]], None], str], ...] = (
            (
                ".claude-plugin/marketplace.json",
                lambda value: value.update({"plugins": []}),
                "claude",
            ),
            (
                ".claude-plugin/marketplace.json",
                lambda value: value["plugins"][0].update({"name": "wrong"}),
                "claude",
            ),
            (
                ".claude-plugin/plugin.json",
                lambda value: value.update({"skills": "./wrong/"}),
                "claude",
            ),
            (
                ".agents/plugins/marketplace.json",
                lambda value: value.update({"plugins": []}),
                "codex",
            ),
            (
                ".agents/plugins/marketplace.json",
                lambda value: value["plugins"][0].update({"source": "wrong"}),
                "codex",
            ),
            (
                ".codex-plugin/plugin.json",
                lambda value: value.update({"skills": "./wrong/"}),
                "codex",
            ),
        )
        for relative, mutate, surface in cases:
            with self.subTest(relative=relative):
                path = self.fixture / relative
                original = path.read_text(encoding="utf-8")
                value: dict[str, Any] = json.loads(original)
                mutate(value)
                path.write_text(json.dumps(value), encoding="utf-8")
                validate = {
                    "claude": validator._validate_claude,
                    "codex": validator._validate_codex,
                }[surface]
                self.assert_validation_errors(validate, surface)
                path.write_text(original, encoding="utf-8")

    def test_independent_manifests_reject_invalid_semantic_versions(self) -> None:
        cases: tuple[tuple[str, Callable[[Path], list[Any]]], ...] = (
            (".codex-plugin/plugin.json", validator._validate_codex),
            ("npm/athena-opencode/package.json", validator._validate_opencode),
        )
        for relative, validate in cases:
            with self.subTest(relative=relative):
                path = self.fixture / relative
                original = path.read_text(encoding="utf-8")
                value: dict[str, Any] = json.loads(original)
                value["version"] = "v1"
                path.write_text(json.dumps(value), encoding="utf-8")

                self.assert_validation_errors(validate, "version")
                path.write_text(original, encoding="utf-8")

    def test_private_skill_directory_fails(self) -> None:
        private = self.fixture / "skills" / "_private"
        private.mkdir()
        (private / "SKILL.md").write_text(
            "---\nname: _private\n---\n", encoding="utf-8"
        )
        self.assert_validation_errors(
            validator._validate_skills, "skills", literal="_private"
        )

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

        self.assert_validation_errors(
            validator._validate_cli_conventions,
            "cli",
            literal="skills/pr-review/scripts/resolve_pr.py",
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

        self.assert_validation_errors(
            validator._validate_cli_conventions,
            "cli",
            literal="skills/pr-review/scripts/resolve_pr.py",
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
        self.assert_validation_errors(
            validator._validate_layout_and_policy,
            "self-contained",
            literal=repository,
        )

    def test_unapproved_ecosystem_repository_is_case_insensitive(self) -> None:
        repository = "hOmErIc" + "InTeLlIgEnCe/" + "UnapprovedRepository"
        (self.fixture / "docs" / "bad.md").write_text(
            f"depends on https://github.com/{repository}", encoding="utf-8"
        )
        self.assert_validation_errors(
            validator._validate_layout_and_policy,
            "self-contained",
            literal=repository,
        )

    def test_validator_checks_its_own_file_for_ecosystem_references(self) -> None:
        path = self.fixture / "scripts" / "validate_skills.py"
        path.write_text(
            "homericintelligence" + "/" + "forbidden-" + "repository\n",
            encoding="utf-8",
        )

        errors = validator._validate_layout_and_policy(self.fixture)

        self.assertEqual(["self-contained"], [error.surface for error in errors])

    def test_distributable_coverage_prefixed_file_is_inspected(self) -> None:
        repository = "HomericIntelligence/" + "UnapprovedRepository"
        (self.fixture / "docs" / ".coverage-bypass.md").write_text(
            f"depends on {repository}", encoding="utf-8"
        )
        self.assert_validation_errors(
            validator._validate_layout_and_policy,
            "self-contained",
            literal=repository,
        )

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

            errors = validator._validate_layout_and_policy(fixture)

        self.assertEqual(
            ["self-contained"], [error.surface for error in errors], errors
        )
        self.assertEqual(
            1,
            sum(repository in error.reason for error in errors),
            errors,
        )

    def test_distributable_nested_ignored_name_is_still_inspected(self) -> None:
        repository = "HomericIntelligence/" + "UnapprovedRepository"
        directory = self.fixture / "docs" / "dist"
        directory.mkdir()
        (directory / "bad.md").write_text(f"depends on {repository}", encoding="utf-8")
        self.assert_validation_errors(
            validator._validate_layout_and_policy,
            "self-contained",
            literal=repository,
        )

    def test_project_prefix_is_rejected(self) -> None:
        forbidden = "Project" + "Example"
        (self.fixture / "docs" / "bad.md").write_text(forbidden, encoding="utf-8")
        self.assert_validation_errors(
            validator._validate_layout_and_policy,
            "self-contained",
            literal=forbidden,
        )

    def test_missing_required_policy_file_fails(self) -> None:
        (self.fixture / "docs" / "policies" / "required-checks.md").unlink()
        self.assert_validation_errors(
            validator._validate_layout_and_policy,
            "policy",
            literal="docs/policies/required-checks.md",
        )

    def test_repo_review_scorecard_rejects_section_and_weight_mismatches(self) -> None:
        criteria = self.fixture / "docs" / "review" / "repository-scorecard.md"
        criteria.write_text(
            criteria.read_text(encoding="utf-8").replace(
                "**Reliability:**", "**Resilience:**", 1
            ),
            encoding="utf-8",
        )
        self.assert_validation_errors(
            validator._validate_repo_review_scorecard,
            "repo-review",
            count=2,
        )

        criteria.write_text(
            criteria.read_text(encoding="utf-8").replace(
                "**Resilience:**", "**Reliability:**", 1
            ),
            encoding="utf-8",
        )
        skill = self.fixture / "skills" / "repo-review" / "SKILL.md"
        skill.write_text(
            skill.read_text(encoding="utf-8").replace(
                "Reliability 9%", "Reliability 8%", 1
            ),
            encoding="utf-8",
        )
        self.assert_validation_errors(
            validator._validate_repo_review_scorecard, "repo-review"
        )

    def test_ruleset_requires_a_current_main_merge_gate(self) -> None:
        path = self.fixture / ".github" / "rulesets" / "homeric-main-baseline.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        status_checks = next(
            rule
            for rule in document["rules"]
            if rule["type"] == "required_status_checks"
        )
        status_checks["parameters"]["strict_required_status_checks_policy"] = True
        path.write_text(json.dumps(document), encoding="utf-8")

        self.assert_validation_errors(validator._validate_ruleset_policy, "ruleset")

        status_checks["parameters"]["strict_required_status_checks_policy"] = False
        status_checks["parameters"]["required_status_checks"] = []
        path.write_text(json.dumps(document), encoding="utf-8")

        self.assert_validation_errors(validator._validate_ruleset_policy, "ruleset")

    def test_ruleset_requires_only_the_github_actions_aggregate_gate(self) -> None:
        path = self.fixture / ".github" / "rulesets" / "homeric-main-baseline.json"
        original = path.read_text(encoding="utf-8")
        invalid_checks = {
            "missing integration": [{"context": "required-checks-gate"}],
            "wrong integration": [
                {"context": "required-checks-gate", "integration_id": 1}
            ],
            "extra check": [
                {"context": "required-checks-gate", "integration_id": 15368},
                {"context": "smoke-test", "integration_id": 15368},
            ],
            "duplicate aggregate": [
                {"context": "required-checks-gate", "integration_id": 15368},
                {"context": "required-checks-gate", "integration_id": 15368},
            ],
            "extra field": [
                {
                    "context": "required-checks-gate",
                    "integration_id": 15368,
                    "unexpected": True,
                }
            ],
        }
        for name, checks in invalid_checks.items():
            with self.subTest(name=name):
                document = json.loads(original)
                status_checks = next(
                    rule
                    for rule in document["rules"]
                    if rule["type"] == "required_status_checks"
                )
                status_checks["parameters"]["required_status_checks"] = checks
                path.write_text(json.dumps(document), encoding="utf-8")

                self.assert_validation_errors(
                    validator._validate_ruleset_policy, "ruleset"
                )

        document = json.loads(original)
        status_checks = next(
            rule
            for rule in document["rules"]
            if rule["type"] == "required_status_checks"
        )
        document["rules"].append(json.loads(json.dumps(status_checks)))
        path.write_text(json.dumps(document), encoding="utf-8")

        self.assert_validation_errors(validator._validate_ruleset_policy, "ruleset")

    def test_ruleset_requires_squash_only_pull_request_merges(self) -> None:
        path = self.fixture / ".github" / "rulesets" / "homeric-main-baseline.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        pull_request = next(
            rule for rule in document["rules"] if rule["type"] == "pull_request"
        )
        pull_request["parameters"]["allowed_merge_methods"] = ["merge", "squash"]
        path.write_text(json.dumps(document), encoding="utf-8")

        self.assert_validation_errors(validator._validate_ruleset_policy, "ruleset")

    def test_ruleset_requires_the_approved_staged_merge_queue_policy(self) -> None:
        path = self.fixture / ".github" / "rulesets" / "homeric-main-baseline.json"
        original = path.read_text(encoding="utf-8")
        document = json.loads(original)
        document["rules"] = [
            rule for rule in document["rules"] if rule.get("type") != "merge_queue"
        ]
        path.write_text(json.dumps(document), encoding="utf-8")

        self.assert_validation_errors(validator._validate_ruleset_policy, "ruleset")

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

        self.assert_validation_errors(validator._validate_ruleset_policy, "ruleset")

    def test_obsolete_distribution_path_fails(self) -> None:
        (self.fixture / "athena").mkdir()
        self.assert_validation_errors(
            validator._validate_layout_and_policy, "layout", literal="athena"
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
        self.assertEqual(result, 1)
        self.assertTrue(errors.getvalue().strip())


if __name__ == "__main__":
    unittest.main()
