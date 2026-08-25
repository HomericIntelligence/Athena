"""Behavior tests for skill-local executable helpers."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from skills._cli import argument_parser, git_read_arguments, git_read_environment

ROOT = Path(__file__).resolve().parents[2]


def executable_scripts() -> list[Path]:
    candidates = [*ROOT.glob("scripts/*.py"), *ROOT.glob("skills/*/scripts/*.py")]
    return sorted(
        path
        for path in candidates
        if path.read_text(encoding="utf-8").startswith("#!/usr/bin/env python3\n")
    )


def run_script(
    relative_path: str,
    *arguments: str,
    cwd: Path,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [str(ROOT / relative_path), *arguments]
    process_env = env.copy() if env is not None else os.environ.copy()
    if os.environ.get("ATHENA_COVERAGE") == "1":
        command = [
            sys.executable,
            "-m",
            "coverage",
            "run",
            "--branch",
            "--parallel-mode",
            str(ROOT / relative_path),
            *arguments,
        ]
        process_env["COVERAGE_FILE"] = str(ROOT / ".coverage")
    return subprocess.run(
        command,
        cwd=cwd,
        env=process_env,
        capture_output=True,
        text=True,
        check=False,
        input=input_text,
    )


def git(cwd: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=cwd, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def initialize_repository(path: Path) -> None:
    path.mkdir(parents=True)
    git(path, "init", "--quiet")
    git(path, "config", "user.name", "Athena Tests")
    git(path, "config", "user.email", "athena-tests@example.invalid")
    (path / "tracked.txt").write_text("base\n", encoding="utf-8")
    git(path, "add", "tracked.txt")
    git(path, "commit", "--quiet", "-m", "test: initialize")


class ScriptConventionTests(unittest.TestCase):
    def test_immutable_git_reads_disable_lazy_fetch_and_commit_graphs(self) -> None:
        hostile_environment = {
            "GIT_ALTERNATE_OBJECT_DIRECTORIES": "/attacker/objects",
            "GIT_COMMON_DIR": "/attacker/common",
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "core.commitGraph",
            "GIT_CONFIG_PARAMETERS": "core.commitGraph=true",
            "GIT_CONFIG_VALUE_0": "true",
            "GIT_DIR": "/attacker/.git",
            "GIT_EXTERNAL_DIFF": "/attacker/diff",
            "GIT_GRAFT_FILE": "attacker-grafts",
            "GIT_INDEX_FILE": "/attacker/index",
            "GIT_NO_LAZY_FETCH": "0",
            "GIT_OBJECT_DIRECTORY": "/attacker/objects",
            "GIT_SHALLOW_FILE": "/attacker/shallow",
            "GIT_TRACE": "/attacker/trace",
            "GIT_WORK_TREE": "/attacker/worktree",
        }
        with patch.dict(
            os.environ,
            hostile_environment,
        ):
            environment = git_read_environment()

        for key, value in hostile_environment.items():
            self.assertNotEqual(value, environment.get(key))
        self.assertEqual(os.devnull, environment["GIT_GRAFT_FILE"])
        self.assertEqual("1", environment["GIT_NO_REPLACE_OBJECTS"])
        self.assertEqual("1", environment["GIT_NO_LAZY_FETCH"])
        self.assertEqual(
            ("-c", "core.commitGraph=false", "--no-replace-objects"),
            git_read_arguments(),
        )

    def test_every_executable_reports_the_plugin_version(self) -> None:
        manifest = json.loads(
            (ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        expected_version = manifest["version"]

        for path in executable_scripts():
            with self.subTest(script=path.relative_to(ROOT)):
                result = subprocess.run(
                    [sys.executable, str(path), "--version"],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual(
                    f"{path.name} {expected_version}", result.stdout.strip()
                )

    def test_shared_version_action_is_lazy_and_reports_manifest_failures(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest = root / ".codex-plugin" / "plugin.json"
            manifest.parent.mkdir()
            with patch("skills._cli.PLUGIN_ROOT", root):
                parser = argument_parser()
                parser.parse_args([])

                for document in ("not-json\n", "[]\n"):
                    with self.subTest(document=document):
                        manifest.write_text(document, encoding="utf-8")
                        errors = io.StringIO()
                        with (
                            redirect_stderr(errors),
                            self.assertRaises(SystemExit) as exit,
                        ):
                            parser.parse_args(["--version"])
                        self.assertEqual(1, exit.exception.code)
                        self.assertIn("cannot read plugin version", errors.getvalue())

                manifest.write_text('{"version": "0.2.0"}\n', encoding="utf-8")
                output = io.StringIO()
                with redirect_stdout(output), self.assertRaises(SystemExit) as exit:
                    parser.parse_args(["--version"])
                self.assertEqual(0, exit.exception.code)
                self.assertEqual("0.2.0", output.getvalue().strip().split()[-1])

    def test_helpers_report_missing_git_or_gh_without_a_traceback(self) -> None:
        commands = (
            (
                "skills/git-worktrees/scripts/prepare_worktree.py",
                ("feature", "--start-point", "HEAD", "--dry-run"),
                "git",
            ),
            ("skills/pr-review/scripts/collect_evidence.py", ("1",), "gh"),
            (
                "skills/pr-review/scripts/diff_context.py",
                ("a" * 40, "b" * 40),
                "git",
            ),
            (
                "skills/pr-review/scripts/resolve_pr.py",
                (
                    "--target-host",
                    "github.com",
                    "--target-repository",
                    "owner/repository",
                    "1",
                ),
                "gh",
            ),
            ("skills/change-review/scripts/resolve_scope.py", ("--worktree",), "git"),
            (
                "skills/systematic-debugging/scripts/repository_evidence.py",
                ("pattern",),
                "git",
            ),
            (
                "skills/tidy/scripts/run_tidy.py",
                ("/tmp/automation",),
                "uv",
            ),
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            bin_directory = root / "bin"
            bin_directory.mkdir()
            (bin_directory / "python3").symlink_to(sys.executable)
            environment = os.environ.copy()
            environment["PATH"] = str(bin_directory)

            for path, arguments, missing_command in commands:
                with self.subTest(path=path):
                    result = run_script(path, *arguments, cwd=root, env=environment)

                    self.assertNotEqual(0, result.returncode)
                    self.assertIn(
                        f"required command unavailable: {missing_command}",
                        result.stderr,
                    )
                    self.assertNotIn("Traceback", result.stderr)


class RetrievableSkillSelectorTests(unittest.TestCase):
    def test_lists_only_flat_retrievable_main_skills(self) -> None:
        script = ROOT / "skills/advise/scripts/list_retrievable_skills.py"
        self.assertTrue(script.is_file(), f"missing executable selector: {script}")

        with tempfile.TemporaryDirectory() as temporary_directory:
            knowledge_root = Path(temporary_directory)
            skills = knowledge_root / "skills"
            skills.mkdir()
            (skills / "alpha.md").write_text("main\n", encoding="utf-8")
            (skills / "alpha.notes.md").write_text("notes\n", encoding="utf-8")
            (skills / "alpha.notes-v2.md").write_text("notes v2\n", encoding="utf-8")
            (skills / "alpha.history").write_text("history\n", encoding="utf-8")
            (skills / "alpha.history.md").write_text(
                "history markdown\n", encoding="utf-8"
            )
            (skills / "beta.md").write_text("main\n", encoding="utf-8")
            nested = skills / "nested"
            nested.mkdir()
            (nested / "gamma.md").write_text("nested\n", encoding="utf-8")

            result = run_script(
                "skills/advise/scripts/list_retrievable_skills.py",
                str(knowledge_root),
                cwd=knowledge_root,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("skills/alpha.md\nskills/beta.md\n", result.stdout)

    def test_rejects_checkout_without_a_skills_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            knowledge_root = Path(temporary_directory)
            result = run_script(
                "skills/advise/scripts/list_retrievable_skills.py",
                str(knowledge_root),
                cwd=knowledge_root,
            )

        self.assertEqual(1, result.returncode)
        self.assertIn("knowledge skills directory is unavailable", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


class FakeGitHubCliFixtureTests(unittest.TestCase):
    def run_fake_gh(
        self,
        root: Path,
        *arguments: str,
        settings: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        if settings is not None:
            environment.update(settings)
        return run_script(
            "tests/fixtures/fake_gh.py", *arguments, cwd=root, env=environment
        )

    def test_fake_gh_rejects_duplicate_repository_options(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = self.run_fake_gh(
                Path(temporary_directory),
                "pr",
                "view",
                "42",
                "--repo",
                "github.com/owner/repository",
                "--repo",
                "github.com/attacker/repository",
                "--json",
                "number",
                settings={"FAKE_GH_REQUIRE_REPOSITORY": "owner/repository"},
            )

        self.assertEqual(9, result.returncode)

    def test_fake_gh_rejects_a_repository_option_without_a_value(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = self.run_fake_gh(
                Path(temporary_directory),
                "pr",
                "view",
                "42",
                "--repo",
                "github.com/owner/repository",
                "--repo",
                settings={"FAKE_GH_REQUIRE_REPOSITORY": "owner/repository"},
            )

        self.assertEqual(9, result.returncode)

    def test_fake_gh_simulates_a_complex_pull_request_view(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            fields_file = root / "requested-fields.txt"
            result = self.run_fake_gh(
                root,
                "pr",
                "view",
                "7",
                "--repo",
                "github.com/owner/repository",
                "--json",
                "number,commits",
                settings={
                    "FAKE_GH_REQUIRE_REPOSITORY": "owner/repository",
                    "FAKE_GH_SIMULATE_COMPLEXITY_DROP": "1",
                    "FAKE_GH_VIEW_FIELDS_FILE": str(fields_file),
                    "FAKE_GH_VIEW_JSON": json.dumps({"number": 7}),
                },
            )
            requested_fields = fields_file.read_text(encoding="utf-8")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("number,commits", requested_fields)
        self.assertEqual(
            {"author": None, "number": 7, "statusCheckRollup": None, "title": None},
            {
                key: json.loads(result.stdout)[key]
                for key in ("author", "number", "statusCheckRollup", "title")
            },
        )

    def test_fake_gh_supports_configured_command_responses(self) -> None:
        default_view = {
            "author": {"login": "reviewer"},
            "baseRefName": "main",
            "baseRefOid": "a" * 40,
            "headRefName": "feature",
            "headRefOid": "b" * 40,
            "number": 7,
            "state": "OPEN",
            "statusCheckRollup": [],
            "title": "Fake pull request",
            "url": "https://github.com/owner/repository/pull/7",
        }
        candidates = [{"number": 7, "state": "OPEN"}]
        cases: tuple[tuple[tuple[str, ...], dict[str, str], int, object, str], ...] = (
            (
                ("pr", "view", "7", "--json", "number"),
                {},
                0,
                default_view,
                "",
            ),
            (
                ("pr", "view", "7"),
                {"FAKE_GH_VIEW_JSON": json.dumps(["not a mapping"])},
                0,
                json.dumps(["not a mapping"]) + "\n",
                "",
            ),
            (
                ("pr", "view", "7"),
                {"FAKE_GH_VIEW_RAW": "not JSON"},
                0,
                "not JSON\n",
                "",
            ),
            (
                ("pr", "list", "--repo", "github.com/owner/repository"),
                {
                    "FAKE_GH_CANDIDATES_JSON": json.dumps(candidates),
                    "FAKE_GH_REQUIRE_REPOSITORY": "owner/repository",
                },
                0,
                candidates,
                "",
            ),
            (
                ("pr", "list", "--repo", "github.com/attacker/repository"),
                {"FAKE_GH_REQUIRE_REPOSITORY": "owner/repository"},
                9,
                "",
                "expected an explicit retained GitHub repository\n",
            ),
            (
                ("pr", "diff"),
                {"FAKE_GH_CHANGED_FILES": "first.py\nsecond.py"},
                0,
                "first.py\nsecond.py\n",
                "",
            ),
            (
                ("pr", "diff"),
                {"FAKE_GH_DIFF_ERROR": "diff unavailable"},
                1,
                "",
                "diff unavailable\n",
            ),
            (
                ("pr", "checks"),
                {"FAKE_GH_CHECKS": '["pending"]', "FAKE_GH_CHECKS_EXIT": "8"},
                8,
                '["pending"]\n',
                "",
            ),
            (
                ("repo", "view"),
                {"FAKE_GH_REPOSITORY": "owner/alternative"},
                0,
                {"nameWithOwner": "owner/alternative"},
                "",
            ),
            (
                ("repo", "view"),
                {"FAKE_GH_FORBID_REPO_VIEW": "1"},
                10,
                "",
                "ambient repository lookup is forbidden\n",
            ),
            (
                ("api", "repos/owner/repository/pulls/7/files"),
                {
                    "FAKE_GH_FILES_JSON": json.dumps(
                        [
                            {"filename": "kept.py"},
                            {"filename": 7},
                            {"other": "ignored.py"},
                            "not an object",
                        ]
                    )
                },
                0,
                "kept.py\n",
                "",
            ),
            (
                ("api", "repos/owner/repository/pulls/7/files"),
                {"FAKE_GH_FILES_JSON": json.dumps({"filename": "ignored.py"})},
                0,
                "",
                "",
            ),
            (("unknown",), {}, 2, "", "unexpected gh invocation: ['unknown']\n"),
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            for arguments, settings, exit_code, stdout, stderr in cases:
                with self.subTest(arguments=arguments):
                    result = self.run_fake_gh(root, *arguments, settings=settings)

                    self.assertEqual(exit_code, result.returncode)
                    self.assertEqual(stderr, result.stderr)
                    if isinstance(stdout, (dict, list)):
                        self.assertEqual(stdout, json.loads(result.stdout))
                    else:
                        self.assertEqual(stdout, result.stdout)


class PullRequestScriptTests(unittest.TestCase):
    def make_fake_tools(
        self, root: Path, candidates: list[dict[str, object]]
    ) -> dict[str, str]:
        bin_dir = root / "bin"
        bin_dir.mkdir()
        (bin_dir / "gh").symlink_to(ROOT / "tests" / "fixtures" / "fake_gh.py")
        env = os.environ.copy()
        env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
        env["FAKE_GH_CANDIDATES_JSON"] = json.dumps(candidates)
        return env

    def resolve_pr(
        self,
        *arguments: str,
        cwd: Path,
        env: dict[str, str],
    ) -> subprocess.CompletedProcess[str]:
        """Resolve through the test's retained GitHub target."""
        return run_script(
            "skills/pr-review/scripts/resolve_pr.py",
            "--target-host",
            "github.com",
            "--target-repository",
            "owner/repository",
            *arguments,
            cwd=cwd,
            env=env,
        )

    def test_resolve_pr_accepts_explicit_number(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            result = self.resolve_pr(
                "42",
                cwd=root,
                env=self.make_fake_tools(root, []),
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(42, json.loads(result.stdout)["number"])

    def test_resolve_pr_emits_a_canonical_review_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            result = self.resolve_pr(
                "42",
                cwd=root,
                env=self.make_fake_tools(root, []),
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            {
                "host": "github.com",
                "kind": "github",
                "number": 42,
                "repository": "owner/repository",
                "url": "https://github.com/owner/repository/pull/42",
            },
            json.loads(result.stdout)["review_target"],
        )

    def test_resolve_pr_rejects_ambient_target_selection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            env = self.make_fake_tools(root, [])
            env["GH_HOST"] = "attacker.invalid"
            env["GH_REPO"] = "attacker/repository"
            env["FAKE_GH_REQUIRE_REPOSITORY"] = "owner/repository"
            env["FAKE_GH_FORBID_REPO_VIEW"] = "1"
            result = self.resolve_pr("42", cwd=root, env=env)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            "owner/repository", json.loads(result.stdout)["review_target"]["repository"]
        )

    def test_resolve_pr_derives_an_explicit_target_from_a_canonical_url(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            env = self.make_fake_tools(root, [])
            env["GH_HOST"] = "attacker.invalid"
            env["GH_REPO"] = "attacker/repository"
            env["FAKE_GH_REQUIRE_REPOSITORY"] = "owner/repository"
            env["FAKE_GH_FORBID_REPO_VIEW"] = "1"
            result = run_script(
                "skills/pr-review/scripts/resolve_pr.py",
                "https://github.com/owner/repository/pull/42",
                cwd=root,
                env=env,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(42, json.loads(result.stdout)["number"])

    def test_resolve_pr_rejects_a_noncanonical_direct_url_without_a_traceback(
        self,
    ) -> None:
        """Malformed direct URLs are argument errors, not uncaught exceptions."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            result = run_script(
                "skills/pr-review/scripts/resolve_pr.py",
                "https://github.com/owner/repository/pull/42/",
                cwd=root,
                env=self.make_fake_tools(root, []),
            )

        self.assertEqual(2, result.returncode)
        self.assertIn("invalid pull-request URL", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_resolve_pr_requires_a_target_for_a_numeric_identifier(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            result = run_script(
                "skills/pr-review/scripts/resolve_pr.py",
                "42",
                cwd=root,
                env=self.make_fake_tools(root, []),
            )

        self.assertEqual(2, result.returncode)
        self.assertIn("--target-host", result.stderr)

    def test_resolve_pr_rejects_a_pr_from_another_repository(self) -> None:
        """A local source review must never be bound to a foreign PR URL."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            env = self.make_fake_tools(root, [])
            env["FAKE_GH_REPOSITORY"] = "owner/current-repository"
            env["FAKE_GH_VIEW_JSON"] = json.dumps(
                {
                    "url": "https://github.com/other/foreign-repository/pull/42",
                }
            )
            result = self.resolve_pr(
                "42",
                cwd=root,
                env=env,
            )

        self.assertEqual(1, result.returncode)
        self.assertIn("does not belong to target repository", result.stderr)

    def test_resolve_pr_rejects_closed_and_invalid_explicit_prs(self) -> None:
        for payload, message in (
            ({"number": 42, "state": "CLOSED"}, "is not open"),
            ([{"number": 42}], "invalid pull-request object"),
        ):
            with self.subTest(payload=payload):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    root = Path(temporary_directory)
                    env = self.make_fake_tools(root, [])
                    env["FAKE_GH_VIEW_JSON"] = json.dumps(payload)
                    result = self.resolve_pr(
                        "42",
                        cwd=root,
                        env=env,
                    )

                self.assertEqual(1, result.returncode)
                self.assertIn(message, result.stderr)

    def test_resolve_pr_rejects_non_oid_provider_revisions(self) -> None:
        for field, value in (
            ("baseRefOid", "main"),
            ("headRefOid", "HEAD"),
            ("baseRefOid", "a" * 39),
            ("headRefOid", "B" * 40),
        ):
            with self.subTest(field=field, value=value):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    root = Path(temporary_directory)
                    env = self.make_fake_tools(root, [])
                    env["FAKE_GH_VIEW_JSON"] = json.dumps({field: value})
                    result = self.resolve_pr(
                        "42",
                        cwd=root,
                        env=env,
                    )

                self.assertEqual(1, result.returncode)
                self.assertIn("immutable PR revision", result.stderr)

    def test_resolve_pr_reports_no_candidate_and_usage_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            repository = root / "repo"
            initialize_repository(repository)
            env = self.make_fake_tools(root, [])
            missing = self.resolve_pr(cwd=repository, env=env)
            usage = self.resolve_pr(
                "1",
                "2",
                cwd=repository,
                env=env,
            )

        self.assertEqual(2, missing.returncode)
        self.assertIn("no open pull request", missing.stderr)
        self.assertEqual(2, usage.returncode)
        self.assertIn("usage:", usage.stderr)

    def test_pr_helpers_reject_option_like_identifiers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            env = self.make_fake_tools(root, [])
            resolved = self.resolve_pr("-R", cwd=root, env=env)
            collected = run_script(
                "skills/pr-review/scripts/collect_evidence.py", "-R", cwd=root, env=env
            )
            invalid_resolved = self.resolve_pr("invalid", cwd=root, env=env)
            invalid_collected = run_script(
                "skills/pr-review/scripts/collect_evidence.py",
                "invalid",
                cwd=root,
                env=env,
            )

        self.assertEqual(2, resolved.returncode)
        self.assertIn("usage:", resolved.stderr)
        self.assertEqual(2, collected.returncode)
        self.assertIn("usage:", collected.stderr)
        self.assertEqual(1, invalid_resolved.returncode)
        self.assertIn("invalid pull-request identifier", invalid_resolved.stderr)
        self.assertEqual(1, invalid_collected.returncode)
        self.assertIn("invalid pull-request identifier", invalid_collected.stderr)

    def test_resolve_pr_reports_malformed_github_output_as_operational_failure(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            env = self.make_fake_tools(root, [])
            env["FAKE_GH_VIEW_RAW"] = "not JSON"
            result = self.resolve_pr("42", cwd=root, env=env)

        self.assertEqual(1, result.returncode)
        self.assertIn("Expecting value", result.stderr)

    def test_resolve_pr_uses_the_only_open_pr_for_current_branch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            initialize_repository(root / "repo")
            git(root / "repo", "checkout", "-q", "-b", "feature/portable-base")
            candidates = [
                {
                    "number": 7,
                    "state": "OPEN",
                    "url": "https://example/7",
                    "headRefName": "feature/portable-base",
                    "baseRefName": "trunk",
                }
            ]
            result = self.resolve_pr(
                cwd=root / "repo",
                env=self.make_fake_tools(root, candidates),
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(7, json.loads(result.stdout)["number"])

    def test_resolve_pr_reports_multiple_candidates_without_guessing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            initialize_repository(root / "repo")
            candidates = [
                {"number": 1, "state": "OPEN", "url": "https://example/1"},
                {"number": 2, "state": "OPEN", "url": "https://example/2"},
            ]
            result = self.resolve_pr(
                cwd=root / "repo",
                env=self.make_fake_tools(root, candidates),
            )

        self.assertEqual(3, result.returncode)
        self.assertIn("https://example/1", result.stderr)
        self.assertIn("https://example/2", result.stderr)

    def test_diff_context_uses_supplied_base_in_both_diff_lenses(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repo"
            initialize_repository(repository)
            base = git(repository, "rev-parse", "HEAD")
            git(repository, "checkout", "-q", "-b", "feature")
            (repository / "tracked.txt").write_text("feature\n", encoding="utf-8")
            git(repository, "commit", "-qam", "test: feature")
            head = git(repository, "rev-parse", "HEAD")
            result = run_script(
                "skills/pr-review/scripts/diff_context.py", base, head, cwd=repository
            )

        self.assertEqual(0, result.returncode, result.stderr)
        context = json.loads(result.stdout)
        self.assertEqual(0, context["behind_count"])
        self.assertEqual(f"{base}...{head}", context["author_intent_range"])
        self.assertEqual(f"{base}..{head}", context["current_base_range"])

    def test_diff_context_ignores_hostile_git_location_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            repository = root / "reviewed"
            attacker = root / "attacker"
            initialize_repository(repository)
            base = git(repository, "rev-parse", "HEAD")
            (repository / "reviewed.txt").write_text("head\n", encoding="utf-8")
            git(repository, "add", "reviewed.txt")
            git(repository, "commit", "--quiet", "-m", "test: reviewed head")
            head = git(repository, "rev-parse", "HEAD")
            initialize_repository(attacker)
            environment = os.environ.copy()
            environment["GIT_DIR"] = str(attacker / ".git")
            environment["GIT_WORK_TREE"] = str(attacker)
            environment["GIT_INDEX_FILE"] = str(attacker / ".git" / "index")
            result = run_script(
                "skills/pr-review/scripts/diff_context.py",
                base,
                head,
                cwd=repository,
                env=environment,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(base, json.loads(result.stdout)["merge_base"])

    def test_diff_context_rejects_shallow_history_despite_hostile_git_context(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            shallow = root / "shallow"
            attacker = root / "attacker"
            initialize_repository(source)
            for number in range(3):
                path = source / f"commit-{number}.txt"
                path.write_text(f"{number}\n", encoding="utf-8")
                git(source, "add", path.name)
                git(source, "commit", "--quiet", "-m", f"test: commit {number}")
            clone = subprocess.run(
                [
                    "git",
                    "clone",
                    "--quiet",
                    "--no-local",
                    "--depth",
                    "2",
                    source,
                    shallow,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, clone.returncode, clone.stderr)
            self.assertEqual(
                "true", git(shallow, "rev-parse", "--is-shallow-repository")
            )
            initialize_repository(attacker)
            environment = os.environ.copy()
            environment["GIT_DIR"] = str(attacker / ".git")
            environment["GIT_WORK_TREE"] = str(attacker)
            result = run_script(
                "skills/pr-review/scripts/diff_context.py",
                git(shallow, "rev-parse", "HEAD~1"),
                git(shallow, "rev-parse", "HEAD"),
                cwd=shallow,
                env=environment,
            )

        self.assertEqual(1, result.returncode)
        self.assertIn("non-shallow", result.stderr)

    def test_diff_context_ignores_replacement_refs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repo"
            initialize_repository(repository)
            common = git(repository, "rev-parse", "HEAD")
            git(repository, "checkout", "-q", "-b", "target")
            (repository / "tracked.txt").write_text("target\n", encoding="utf-8")
            git(repository, "commit", "-qam", "test: target")
            target = git(repository, "rev-parse", "HEAD")
            git(repository, "checkout", "-q", "-b", "feature", common)
            (repository / "tracked.txt").write_text("feature\n", encoding="utf-8")
            git(repository, "commit", "-qam", "test: feature")
            feature = git(repository, "rev-parse", "HEAD")
            git(repository, "replace", feature, target)

            result = run_script(
                "skills/pr-review/scripts/diff_context.py",
                target,
                feature,
                cwd=repository,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        context = json.loads(result.stdout)
        self.assertEqual(common, context["merge_base"])
        self.assertEqual(1, context["behind_count"])

    def test_diff_context_ignores_graft_files(self) -> None:
        """A local graft must not rewrite the reviewed ancestry relation."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repo"
            initialize_repository(repository)
            common = git(repository, "rev-parse", "HEAD")
            git(repository, "checkout", "-q", "-b", "target")
            (repository / "tracked.txt").write_text("target\n", encoding="utf-8")
            git(repository, "commit", "-qam", "test: target")
            target = git(repository, "rev-parse", "HEAD")
            git(repository, "checkout", "-q", "-b", "feature", common)
            (repository / "tracked.txt").write_text("feature\n", encoding="utf-8")
            git(repository, "commit", "-qam", "test: feature")
            feature = git(repository, "rev-parse", "HEAD")
            grafts = Path(git(repository, "rev-parse", "--git-path", "info/grafts"))
            if not grafts.is_absolute():
                grafts = repository / grafts
            grafts.write_text(f"{feature} {target}\n", encoding="utf-8")

            result = run_script(
                "skills/pr-review/scripts/diff_context.py",
                target,
                feature,
                cwd=repository,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        context = json.loads(result.stdout)
        self.assertEqual(common, context["merge_base"])
        self.assertEqual(1, context["behind_count"])

    def test_diff_context_rejects_missing_arguments_and_invalid_refs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repo"
            initialize_repository(repository)
            usage = run_script(
                "skills/pr-review/scripts/diff_context.py", cwd=repository
            )
            invalid = run_script(
                "skills/pr-review/scripts/diff_context.py",
                "missing-base",
                "HEAD",
                cwd=repository,
            )

        self.assertEqual(2, usage.returncode)
        self.assertIn("usage:", usage.stderr)
        self.assertEqual(1, invalid.returncode)
        self.assertTrue(invalid.stderr.strip())

    def test_diff_context_rejects_option_like_refs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repo"
            initialize_repository(repository)
            result = run_script(
                "skills/pr-review/scripts/diff_context.py",
                "-R",
                "HEAD",
                cwd=repository,
            )

        self.assertEqual(2, result.returncode)
        self.assertIn("usage:", result.stderr)

    def test_diff_context_rejects_mutable_or_malformed_revisions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repo"
            initialize_repository(repository)
            head = git(repository, "rev-parse", "HEAD")

            for revision in (
                "HEAD",
                "main",
                head[:12],
                head.upper(),
                f"{head}^{{commit}}",
            ):
                with self.subTest(revision=revision):
                    result = run_script(
                        "skills/pr-review/scripts/diff_context.py",
                        revision,
                        head,
                        cwd=repository,
                    )

                    self.assertEqual(1, result.returncode)
                    self.assertIn("lowercase 40-hex", result.stderr)

    def test_collect_evidence_combines_pr_metadata_files_and_checks(self) -> None:
        requested_fields = ""
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            (bin_dir / "gh").symlink_to(ROOT / "tests" / "fixtures" / "fake_gh.py")
            fields_file = root / "view-fields.txt"
            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
            env["FAKE_GH_SIMULATE_COMPLEXITY_DROP"] = "1"
            env["FAKE_GH_VIEW_FIELDS_FILE"] = str(fields_file)
            env["FAKE_GH_VIEW_JSON"] = json.dumps(
                {
                    "number": 9,
                    "title": "Portable Athena",
                    "author": {"login": "reviewer"},
                    "statusCheckRollup": [{"name": "required-checks-gate"}],
                }
            )
            env["FAKE_GH_FILES_JSON"] = json.dumps(
                [{"filename": "skills/pr-review/SKILL.md"}]
            )
            env["FAKE_GH_CHECKS"] = json.dumps(
                [{"name": "required-checks-gate", "state": "SUCCESS"}]
            )
            result = run_script(
                "skills/pr-review/scripts/collect_evidence.py",
                "9",
                cwd=root,
                env=env,
            )
            requested_fields = fields_file.read_text(encoding="utf-8")

        self.assertEqual(0, result.returncode, result.stderr)
        evidence = json.loads(result.stdout)
        self.assertEqual(9, evidence["pull_request"]["number"])
        self.assertEqual("Portable Athena", evidence["pull_request"]["title"])
        self.assertEqual("reviewer", evidence["pull_request"]["author"]["login"])
        self.assertEqual(
            [{"name": "required-checks-gate"}],
            evidence["pull_request"]["statusCheckRollup"],
        )
        self.assertEqual(["skills/pr-review/SKILL.md"], evidence["changed_files"])
        self.assertEqual(evidence["changed_files"], evidence["changed_paths"])
        self.assertEqual("SUCCESS", evidence["checks"][0]["state"])
        self.assertNotIn("commits", requested_fields.split(","))
        self.assertNotIn("files", requested_fields.split(","))

    def test_collect_evidence_rejects_pr_from_another_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            env = self.make_fake_tools(root, [])
            env["FAKE_GH_VIEW_JSON"] = json.dumps(
                {
                    "number": 42,
                    "state": "OPEN",
                    "url": "https://github.com/other/repository/pull/42",
                }
            )
            result = run_script(
                "skills/pr-review/scripts/collect_evidence.py",
                "https://github.com/other/repository/pull/42",
                cwd=root,
                env=env,
            )

        self.assertEqual(1, result.returncode)
        self.assertIn("does not belong to current repository", result.stderr)

    def test_collect_evidence_reports_partial_pr_metadata_as_structured_error(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            env = self.make_fake_tools(root, [])
            env["FAKE_GH_VIEW_JSON"] = json.dumps({"number": 9, "title": None})
            result = run_script(
                "skills/pr-review/scripts/collect_evidence.py",
                "9",
                cwd=root,
                env=env,
            )

        self.assertEqual(1, result.returncode)
        self.assertEqual(
            {
                "error": "incomplete PR metadata",
                "details": (
                    "GitHub returned incomplete or invalid PR metadata fields: title"
                ),
            },
            json.loads(result.stdout),
        )

    def test_collect_evidence_preserves_pending_and_failed_checks(self) -> None:
        for exit_code, state in ((8, "PENDING"), (1, "FAILURE")):
            with self.subTest(exit_code=exit_code):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    root = Path(temporary_directory)
                    env = self.make_fake_tools(root, [])
                    env["FAKE_GH_VIEW_JSON"] = json.dumps({"number": 9})
                    env["FAKE_GH_FILES_JSON"] = "[]"
                    env["FAKE_GH_CHECKS"] = json.dumps(
                        [{"name": "gate", "state": state}]
                    )
                    env["FAKE_GH_CHECKS_EXIT"] = str(exit_code)
                    result = run_script(
                        "skills/pr-review/scripts/collect_evidence.py",
                        "9",
                        cwd=root,
                        env=env,
                    )

                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual(state, json.loads(result.stdout)["checks"][0]["state"])

    def test_collect_evidence_does_not_use_size_limited_pr_diff(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            env = self.make_fake_tools(root, [])
            env["FAKE_GH_VIEW_JSON"] = json.dumps({"number": 9})
            env["FAKE_GH_FILES_JSON"] = json.dumps([{"filename": "large/change.py"}])
            env["FAKE_GH_DIFF_ERROR"] = "PullRequest.diff too_large"
            result = run_script(
                "skills/pr-review/scripts/collect_evidence.py",
                "9",
                cwd=root,
                env=env,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            ["large/change.py"], json.loads(result.stdout)["changed_files"]
        )

    def test_collect_evidence_rejects_usage_and_invalid_check_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            env = self.make_fake_tools(root, [])
            usage = run_script(
                "skills/pr-review/scripts/collect_evidence.py", cwd=root, env=env
            )
            env["FAKE_GH_VIEW_JSON"] = json.dumps({"number": 9})
            env["FAKE_GH_CHECKS"] = json.dumps({"state": "SUCCESS"})
            invalid = run_script(
                "skills/pr-review/scripts/collect_evidence.py",
                "9",
                cwd=root,
                env=env,
            )

        self.assertEqual(2, usage.returncode)
        self.assertIn("usage:", usage.stderr)
        self.assertEqual(1, invalid.returncode)
        self.assertIn("invalid check evidence", invalid.stderr)


class ChangeReviewScriptTests(unittest.TestCase):
    def test_worktree_includes_nonignored_untracked_content_without_mutation(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repo"
            initialize_repository(repository)
            (repository / ".gitignore").write_text(".env.local\n", encoding="utf-8")
            git(repository, "add", ".gitignore")
            git(repository, "commit", "--quiet", "-m", "test: ignore local env")
            untracked = repository / "new.py"
            untracked.write_text("first\n", encoding="utf-8")
            (repository / ".env.local").write_text("secret\n", encoding="utf-8")
            head_before = git(repository, "rev-parse", "HEAD")
            status_before = git(repository, "status", "--porcelain=v1", "-uall")

            first = run_script(
                "skills/change-review/scripts/resolve_scope.py",
                "--worktree",
                cwd=repository,
            )

            self.assertEqual(0, first.returncode, first.stderr)
            first_scope = json.loads(first.stdout)
            self.assertEqual("worktree", first_scope["scope"])
            self.assertEqual(head_before, first_scope["base"])
            self.assertEqual(head_before, first_scope["head"])
            self.assertEqual([], first_scope["tracked_paths"])
            self.assertEqual(["new.py"], first_scope["untracked_paths"])
            self.assertEqual(["new.py"], first_scope["paths"])
            self.assertEqual("included", first_scope["untracked_scope"])
            self.assertNotIn(".env.local", first_scope["paths"])
            self.assertEqual(head_before, git(repository, "rev-parse", "HEAD"))
            self.assertEqual(
                status_before, git(repository, "status", "--porcelain=v1", "-uall")
            )

            untracked.write_text("second\n", encoding="utf-8")
            second = run_script(
                "skills/change-review/scripts/resolve_scope.py",
                "--worktree",
                cwd=repository,
            )

            self.assertEqual(0, second.returncode, second.stderr)
            self.assertNotEqual(
                first_scope["scope_digest"], json.loads(second.stdout)["scope_digest"]
            )

    def test_staged_and_range_scopes_exclude_untracked_worktree_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repo"
            initialize_repository(repository)
            base = git(repository, "rev-parse", "HEAD")
            (repository / "staged.txt").write_text("staged\n", encoding="utf-8")
            git(repository, "add", "staged.txt")
            (repository / "loose.py").write_text("loose\n", encoding="utf-8")

            staged = run_script(
                "skills/change-review/scripts/resolve_scope.py",
                "--staged",
                cwd=repository,
            )

            self.assertEqual(0, staged.returncode, staged.stderr)
            staged_scope = json.loads(staged.stdout)
            self.assertEqual(["staged.txt"], staged_scope["paths"])
            self.assertEqual([], staged_scope["untracked_paths"])
            self.assertEqual("excluded", staged_scope["untracked_scope"])

            git(repository, "commit", "--quiet", "-m", "test: stage file")
            head = git(repository, "rev-parse", "HEAD")
            ranged = run_script(
                "skills/change-review/scripts/resolve_scope.py",
                "--range",
                f"{base}..{head}",
                cwd=repository,
            )

            self.assertEqual(0, ranged.returncode, ranged.stderr)
            range_scope = json.loads(ranged.stdout)
            self.assertEqual("range", range_scope["scope"])
            self.assertEqual(base, range_scope["base"])
            self.assertEqual(head, range_scope["head"])
            self.assertEqual(["staged.txt"], range_scope["paths"])
            self.assertEqual([], range_scope["untracked_paths"])
            self.assertEqual("excluded", range_scope["untracked_scope"])

    def test_worktree_path_filter_empty_scope_and_outside_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            repository = root / "repo"
            initialize_repository(repository)

            empty = run_script(
                "skills/change-review/scripts/resolve_scope.py",
                "--worktree",
                cwd=repository,
            )

            self.assertEqual(0, empty.returncode, empty.stderr)
            self.assertEqual([], json.loads(empty.stdout)["paths"])

            source = repository / "src"
            source.mkdir()
            (source / "new.py").write_text("value = 1\n", encoding="utf-8")
            filtered = run_script(
                "skills/change-review/scripts/resolve_scope.py",
                "--worktree",
                "src",
                cwd=repository,
            )
            outside = run_script(
                "skills/change-review/scripts/resolve_scope.py",
                "--worktree",
                str(root / "outside.py"),
                cwd=repository,
            )

            self.assertEqual(0, filtered.returncode, filtered.stderr)
            self.assertEqual(["src/new.py"], json.loads(filtered.stdout)["paths"])
            self.assertEqual(1, outside.returncode)
            self.assertIn("outside repository", outside.stderr)

    def test_worktree_path_filter_treats_git_pathspec_magic_as_literal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repo"
            initialize_repository(repository)
            documentation = repository / "docs" / "review"
            documentation.mkdir(parents=True)
            common = documentation / "common.md"
            common.write_text("base\n", encoding="utf-8")
            git(repository, "add", "docs/review/common.md")
            git(repository, "commit", "--quiet", "-m", "test: add review docs")
            (repository / "tracked.txt").write_text("changed\n", encoding="utf-8")
            common.write_text("changed\n", encoding="utf-8")

            result = run_script(
                "skills/change-review/scripts/resolve_scope.py",
                "--worktree",
                ":(exclude)docs/review/common.md",
                cwd=repository,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual([], json.loads(result.stdout)["paths"])

    def test_worktree_path_filter_preserves_a_symlink_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repo"
            initialize_repository(repository)
            (repository / "target.txt").write_text("target\n", encoding="utf-8")
            (repository / "alternate.txt").write_text("alternate\n", encoding="utf-8")
            link = repository / "link"
            link.symlink_to("target.txt")
            git(repository, "add", "target.txt", "alternate.txt", "link")
            git(repository, "commit", "--quiet", "-m", "test: add symlink")
            link.unlink()
            link.symlink_to("alternate.txt")

            result = run_script(
                "skills/change-review/scripts/resolve_scope.py",
                "--worktree",
                "link",
                cwd=repository,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(["link"], json.loads(result.stdout)["paths"])

    def test_worktree_path_filter_is_anchored_at_the_repository_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repo"
            initialize_repository(repository)
            nested = repository / "nested"
            nested.mkdir()
            source = repository / "skills" / "change-review"
            source.mkdir(parents=True)
            (source / "changed.py").write_text("value = 1\n", encoding="utf-8")

            result = run_script(
                "skills/change-review/scripts/resolve_scope.py",
                "--worktree",
                "skills/change-review",
                cwd=nested,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(
                ["skills/change-review/changed.py"],
                json.loads(result.stdout)["paths"],
            )

    def test_staged_scope_uses_index_object_metadata_not_live_worktree_bytes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repo"
            initialize_repository(repository)
            tracked = repository / "tracked.txt"
            tracked.write_text("staged\n", encoding="utf-8")
            git(repository, "add", "tracked.txt")
            staged_object = git(repository, "rev-parse", ":tracked.txt")
            tracked.write_text("unstaged\n", encoding="utf-8")

            result = run_script(
                "skills/change-review/scripts/resolve_scope.py",
                "--staged",
                cwd=repository,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            scope = json.loads(result.stdout)
            self.assertEqual("index", scope["content_source"])
            self.assertEqual(
                [
                    {
                        "kind": "git-blob",
                        "mode": "100644",
                        "object_id": staged_object,
                        "path": "tracked.txt",
                    }
                ],
                scope["path_entries"],
            )
            self.assertEqual("unstaged\n", tracked.read_text(encoding="utf-8"))

    def test_range_scope_uses_head_tree_metadata_not_live_worktree_bytes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repo"
            initialize_repository(repository)
            base = git(repository, "rev-parse", "HEAD")
            tracked = repository / "tracked.txt"
            tracked.write_text("range\n", encoding="utf-8")
            git(repository, "commit", "--quiet", "-am", "test: range content")
            range_head = git(repository, "rev-parse", "HEAD")
            range_object = git(repository, "rev-parse", f"{range_head}:tracked.txt")
            tracked.write_text("unrelated worktree\n", encoding="utf-8")

            result = run_script(
                "skills/change-review/scripts/resolve_scope.py",
                "--range",
                f"{base}..{range_head}",
                cwd=repository,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            scope = json.loads(result.stdout)
            self.assertEqual("head-tree", scope["content_source"])
            self.assertEqual(
                [
                    {
                        "kind": "git-blob",
                        "mode": "100644",
                        "object_id": range_object,
                        "path": "tracked.txt",
                    }
                ],
                scope["path_entries"],
            )
            self.assertEqual(
                "unrelated worktree\n", tracked.read_text(encoding="utf-8")
            )

    def test_worktree_scope_disables_text_conversion_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repo"
            initialize_repository(repository)
            (repository / ".gitattributes").write_text(
                "*.probe diff=probe\n", encoding="utf-8"
            )
            changed = repository / "changed.probe"
            changed.write_text("base\n", encoding="utf-8")
            git(repository, "add", ".gitattributes", "changed.probe")
            git(repository, "commit", "--quiet", "-m", "test: configure textconv")
            sentinel = repository / "textconv-ran"
            converter = repository / "probe_textconv.py"
            converter.write_text(
                "#!/usr/bin/env python3\n"
                "from pathlib import Path\n"
                f"Path({str(sentinel)!r}).touch()\n"
                "print('converted')\n",
                encoding="utf-8",
            )
            converter.chmod(0o755)
            git(repository, "config", "diff.probe.textconv", str(converter))
            changed.write_text("changed\n", encoding="utf-8")

            result = run_script(
                "skills/change-review/scripts/resolve_scope.py",
                "--worktree",
                cwd=repository,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("changed.probe", json.loads(result.stdout)["paths"])
            self.assertFalse(sentinel.exists())

    def test_worktree_scope_does_not_refresh_the_git_index(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repo"
            initialize_repository(repository)
            tracked = repository / "tracked.txt"
            index = repository / ".git" / "index"
            before_contents = index.read_bytes()
            before_mtime = index.stat().st_mtime_ns
            tracked_stat = tracked.stat()
            os.utime(
                tracked,
                ns=(tracked_stat.st_atime_ns, tracked_stat.st_mtime_ns + 1_000_000_000),
            )

            result = run_script(
                "skills/change-review/scripts/resolve_scope.py",
                "--worktree",
                cwd=repository,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(before_contents, index.read_bytes())
            self.assertEqual(before_mtime, index.stat().st_mtime_ns)

    def test_worktree_scope_marks_symlinks_without_reading_their_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            repository = root / "repo"
            initialize_repository(repository)
            external = root / "outside-secret"
            external.write_text("first\n", encoding="utf-8")
            link = repository / "linked-secret"
            link.symlink_to(external)

            first = run_script(
                "skills/change-review/scripts/resolve_scope.py",
                "--worktree",
                cwd=repository,
            )

            self.assertEqual(0, first.returncode, first.stderr)
            first_scope = json.loads(first.stdout)
            self.assertEqual(["linked-secret"], first_scope["paths"])
            self.assertEqual(
                [
                    {
                        "kind": "symlink",
                        "path": "linked-secret",
                        "target": str(external),
                    }
                ],
                first_scope["path_entries"],
            )

            external.write_text("second\n", encoding="utf-8")
            second = run_script(
                "skills/change-review/scripts/resolve_scope.py",
                "--worktree",
                cwd=repository,
            )

            self.assertEqual(0, second.returncode, second.stderr)
            self.assertEqual(
                first_scope["scope_digest"],
                json.loads(second.stdout)["scope_digest"],
            )

    def test_worktree_scope_binds_an_untracked_regular_file_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repo"
            initialize_repository(repository)
            script = repository / "script.py"
            script.write_text("print('hello')\n", encoding="utf-8")
            script.chmod(0o644)

            first = run_script(
                "skills/change-review/scripts/resolve_scope.py",
                "--worktree",
                cwd=repository,
            )

            self.assertEqual(0, first.returncode, first.stderr)
            first_scope = json.loads(first.stdout)
            self.assertEqual(
                [{"kind": "file", "mode": "0644", "path": "script.py"}],
                first_scope["path_entries"],
            )
            script.chmod(0o755)

            second = run_script(
                "skills/change-review/scripts/resolve_scope.py",
                "--worktree",
                cwd=repository,
            )

            self.assertEqual(0, second.returncode, second.stderr)
            second_scope = json.loads(second.stdout)
            self.assertEqual(
                [{"kind": "file", "mode": "0755", "path": "script.py"}],
                second_scope["path_entries"],
            )
            self.assertNotEqual(
                first_scope["scope_digest"], second_scope["scope_digest"]
            )

    def test_worktree_scope_handles_a_file_replacing_a_tracked_directory(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repo"
            initialize_repository(repository)
            directory = repository / "directory"
            directory.mkdir()
            child = directory / "old.py"
            child.write_text("old\n", encoding="utf-8")
            git(repository, "add", "directory/old.py")
            git(repository, "commit", "--quiet", "-m", "test: add directory")
            child.unlink()
            directory.rmdir()
            directory.write_text("replacement\n", encoding="utf-8")

            result = run_script(
                "skills/change-review/scripts/resolve_scope.py",
                "--worktree",
                cwd=repository,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            scope = json.loads(result.stdout)
            self.assertEqual(["directory", "directory/old.py"], scope["paths"])
            self.assertEqual(
                [
                    {"kind": "file", "mode": "0644", "path": "directory"},
                    {"kind": "absent", "path": "directory/old.py"},
                ],
                scope["path_entries"],
            )

    def test_scope_resolution_rejects_an_unstable_capture(self) -> None:
        module_name = "test_change_review_scope_resolver"
        specification = importlib.util.spec_from_file_location(
            module_name,
            ROOT / "skills/change-review/scripts/resolve_scope.py",
        )
        assert specification is not None
        assert specification.loader is not None
        module = importlib.util.module_from_spec(specification)
        sys.modules[module_name] = module
        try:
            specification.loader.exec_module(module)
            first_capture = module.ScopeCapture(
                paths=("first.py",),
                tracked_paths=("first.py",),
                untracked_paths=(),
                path_entries=(("first.py", "file", None),),
                tracked_diff=b"first diff",
                scope_digest="first",
            )
            second_capture = module.ScopeCapture(
                paths=("second.py",),
                tracked_paths=("second.py",),
                untracked_paths=(),
                path_entries=(("second.py", "file", None),),
                tracked_diff=b"second diff",
                scope_digest="second",
            )

            with (
                patch.object(
                    module,
                    "git_text",
                    side_effect=["/temporary/repository", "a" * 40],
                ),
                patch.object(
                    module,
                    "capture_scope",
                    side_effect=[first_capture, second_capture],
                ),
                self.assertRaisesRegex(
                    RuntimeError, "change scope changed during resolution"
                ),
            ):
                module.resolve_scope("worktree", None, ())
        finally:
            sys.modules.pop(module_name, None)

    def test_worktree_and_staged_scopes_use_the_resolved_head_oid(self) -> None:
        module_name = "test_change_review_immutable_head"
        specification = importlib.util.spec_from_file_location(
            module_name,
            ROOT / "skills/change-review/scripts/resolve_scope.py",
        )
        assert specification is not None
        assert specification.loader is not None
        module = importlib.util.module_from_spec(specification)
        sys.modules[module_name] = module
        try:
            specification.loader.exec_module(module)
            head = "a" * 40
            repository_root = Path("/temporary/repository")
            worktree_capture = module.WorktreeTrackedCapture(
                paths=(),
                fingerprint=module.ContentFingerprint(0, "a" * 64),
            )
            with patch.object(
                module, "worktree_tracked_capture", return_value=worktree_capture
            ) as capture:
                module.tracked_paths("worktree", "b" * 40, head, (), repository_root)
                module.tracked_diff("worktree", "b" * 40, head, (), repository_root)

            for arguments, _ in capture.call_args_list:
                self.assertEqual(head, arguments[0])

            with (
                patch.object(module, "git_bytes", return_value=b"") as command,
                patch.object(
                    module,
                    "git_stream_fingerprint",
                    return_value=module.ContentFingerprint(0, "b" * 64),
                ) as fingerprint,
            ):
                module.tracked_paths("staged", "b" * 40, head, (), repository_root)
                module.tracked_diff("staged", "b" * 40, head, (), repository_root)

            for arguments, _ in command.call_args_list:
                self.assertIn(head, arguments)
                self.assertNotIn("HEAD", arguments)
            for arguments, _ in fingerprint.call_args_list:
                self.assertIn(head, arguments)
                self.assertNotIn("HEAD", arguments)
        finally:
            sys.modules.pop(module_name, None)

    def test_diffs_force_submodule_and_rename_visibility(self) -> None:
        module_name = "test_change_review_submodules"
        specification = importlib.util.spec_from_file_location(
            module_name,
            ROOT / "skills/change-review/scripts/resolve_scope.py",
        )
        assert specification is not None
        assert specification.loader is not None
        module = importlib.util.module_from_spec(specification)
        sys.modules[module_name] = module
        try:
            specification.loader.exec_module(module)
            repository_root = Path("/temporary/repository")
            for scope in ("staged", "range"):
                with patch.object(module, "git_bytes", return_value=b"") as command:
                    module.tracked_paths(
                        scope,
                        "b" * 40,
                        "a" * 40,
                        (),
                        repository_root,
                    )
                    with patch.object(
                        module,
                        "git_stream_fingerprint",
                        return_value=module.ContentFingerprint(0, "a" * 64),
                    ):
                        module.tracked_diff(
                            scope,
                            "b" * 40,
                            "a" * 40,
                            (),
                            repository_root,
                        )

                for arguments, _ in command.call_args_list:
                    self.assertIn("--ignore-submodules=none", arguments)
                    self.assertIn("--no-renames", arguments)
        finally:
            sys.modules.pop(module_name, None)

    def test_nofollow_inspection_does_not_depend_on_dir_fd_registry_entries(
        self,
    ) -> None:
        module_name = "test_change_review_open_dir_fd"
        specification = importlib.util.spec_from_file_location(
            module_name,
            ROOT / "skills/change-review/scripts/resolve_scope.py",
        )
        assert specification is not None
        assert specification.loader is not None
        module = importlib.util.module_from_spec(specification)
        sys.modules[module_name] = module
        try:
            specification.loader.exec_module(module)
            with tempfile.TemporaryDirectory() as temporary_directory:
                repository = Path(temporary_directory) / "repo"
                initialize_repository(repository)
                with patch.object(module.os, "supports_dir_fd", frozenset()):
                    entry = module.worktree_path_entry(repository, "tracked.txt")

            self.assertEqual("file", entry.kind)
        finally:
            sys.modules.pop(module_name, None)


class WorktreeScriptTests(unittest.TestCase):
    def test_prepare_worktree_uses_explicit_path_and_start_point(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            repository = root / "repo"
            initialize_repository(repository)
            start_point = git(repository, "rev-parse", "HEAD")
            (repository / "tracked.txt").write_text("later\n", encoding="utf-8")
            git(repository, "commit", "-qam", "test: later")
            worktree = root / "knowledge-lesson"

            result = run_script(
                "skills/git-worktrees/scripts/prepare_worktree.py",
                "skill/lesson",
                "--path",
                str(worktree),
                "--path-root",
                str(root),
                "--start-point",
                start_point,
                cwd=repository,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            evidence = json.loads(result.stdout)
            self.assertEqual(str(worktree.resolve()), evidence["path"])
            self.assertEqual(start_point, evidence["start_sha"])
            self.assertEqual(start_point, git(worktree, "rev-parse", "HEAD"))

    def test_prepare_worktree_rejects_intermediate_symlink_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            repository = root / "repo"
            initialize_repository(repository)
            real_parent = root / "real"
            real_parent.mkdir()
            symlink_parent = root / "linked"
            symlink_parent.symlink_to(real_parent, target_is_directory=True)

            result = run_script(
                "skills/git-worktrees/scripts/prepare_worktree.py",
                "feature-safe",
                "--path",
                str(symlink_parent / "feature-safe"),
                "--path-root",
                str(root),
                "--start-point",
                "HEAD",
                "--dry-run",
                cwd=repository,
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("symlink", result.stderr)

    def test_prepare_worktree_requires_trust_root_for_exact_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            repository = root / "repo"
            initialize_repository(repository)
            result = run_script(
                "skills/git-worktrees/scripts/prepare_worktree.py",
                "feature-safe",
                "--path",
                str(root / "feature-safe"),
                "--start-point",
                "HEAD",
                "--dry-run",
                cwd=repository,
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("--path-root", result.stderr)

    def test_prepare_worktree_prefers_ignored_dot_worktrees(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repo"
            initialize_repository(repository)
            (repository / ".worktrees").mkdir()
            (repository / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")
            git(repository, "add", ".gitignore")
            git(repository, "commit", "--quiet", "-m", "test: ignore worktrees")
            result = run_script(
                "skills/git-worktrees/scripts/prepare_worktree.py",
                "feature-one",
                "--start-point",
                "HEAD",
                "--dry-run",
                cwd=repository,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            str((repository / ".worktrees" / "feature-one").resolve()),
            json.loads(result.stdout)["path"],
        )

    def test_prepare_worktree_fails_when_local_directory_is_not_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repo"
            initialize_repository(repository)
            (repository / "worktrees").mkdir()
            result = run_script(
                "skills/git-worktrees/scripts/prepare_worktree.py",
                "feature-two",
                "--start-point",
                "HEAD",
                "--dry-run",
                cwd=repository,
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("not ignored", result.stderr)

    def test_prepare_worktree_rejects_symlinked_local_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            repository = root / "repo"
            initialize_repository(repository)
            external = root / "external"
            external.mkdir()
            (repository / ".worktrees").symlink_to(external, target_is_directory=True)

            result = run_script(
                "skills/git-worktrees/scripts/prepare_worktree.py",
                "feature-symlink",
                "--start-point",
                "HEAD",
                "--dry-run",
                cwd=repository,
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("symlink", result.stderr)

    def test_prepare_worktree_treats_requested_directory_as_a_base(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repo"
            initialize_repository(repository)
            base = (Path(temporary_directory) / "isolated").resolve()
            result = run_script(
                "skills/git-worktrees/scripts/prepare_worktree.py",
                "feature-three",
                "--directory",
                str(base),
                "--start-point",
                "HEAD",
                "--dry-run",
                cwd=repository,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            str((base / "feature-three").resolve()),
            json.loads(result.stdout)["path"],
        )

    def test_prepare_worktree_rejects_symlink_within_requested_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            repository = root / "repo"
            initialize_repository(repository)
            outside = root / "outside"
            outside.mkdir()
            requested = root / "requested"
            requested.mkdir()
            (requested / "linked").symlink_to(outside, target_is_directory=True)
            result = run_script(
                "skills/git-worktrees/scripts/prepare_worktree.py",
                "feature-safe",
                "--directory",
                str(requested / "linked" / "nested"),
                "--start-point",
                "HEAD",
                "--dry-run",
                cwd=repository,
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("symlink", result.stderr)

    def test_prepare_worktree_rejects_symlink_above_nonexistent_trust_root(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            repository = root / "repo"
            initialize_repository(repository)
            real_parent = root / "real"
            real_parent.mkdir()
            linked_parent = root / "linked"
            linked_parent.symlink_to(real_parent, target_is_directory=True)
            trust_root = linked_parent / "not-created"
            result = run_script(
                "skills/git-worktrees/scripts/prepare_worktree.py",
                "feature-safe",
                "--path",
                str(trust_root / "feature-safe"),
                "--path-root",
                str(trust_root),
                "--start-point",
                "HEAD",
                "--dry-run",
                cwd=repository,
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("symlink", result.stderr)

    def test_prepare_worktree_rejects_symlink_above_existing_trust_root(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            repository = root / "repo"
            initialize_repository(repository)
            real_parent = root / "real"
            trust_root = real_parent / "worktrees"
            trust_root.mkdir(parents=True)
            linked_parent = root / "linked"
            linked_parent.symlink_to(real_parent, target_is_directory=True)
            lexical_root = linked_parent / "worktrees"
            result = run_script(
                "skills/git-worktrees/scripts/prepare_worktree.py",
                "feature-safe",
                "--path",
                str(lexical_root / "feature-safe"),
                "--path-root",
                str(lexical_root),
                "--start-point",
                "HEAD",
                "--dry-run",
                cwd=repository,
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("symlink", result.stderr)

    def test_prepare_worktree_rejects_broken_symlink_ancestor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            repository = root / "repo"
            initialize_repository(repository)
            broken_parent = root / "broken"
            broken_parent.symlink_to(root / "missing", target_is_directory=True)
            trust_root = broken_parent / "not-created"
            result = run_script(
                "skills/git-worktrees/scripts/prepare_worktree.py",
                "feature-safe",
                "--path",
                str(trust_root / "feature-safe"),
                "--path-root",
                str(trust_root),
                "--start-point",
                "HEAD",
                "--dry-run",
                cwd=repository,
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("symlink", result.stderr)

    def test_prepare_worktree_rejects_directory_with_exact_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            repository = root / "repo"
            initialize_repository(repository)
            result = run_script(
                "skills/git-worktrees/scripts/prepare_worktree.py",
                "feature-safe",
                "--directory",
                str(root),
                "--path",
                str(root / "feature-safe"),
                "--path-root",
                str(root),
                "--start-point",
                "HEAD",
                "--dry-run",
                cwd=repository,
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("not allowed with argument", result.stderr)

    def test_prepare_worktree_rejects_invalid_branch_name(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repo"
            initialize_repository(repository)
            result = run_script(
                "skills/git-worktrees/scripts/prepare_worktree.py",
                "../escape",
                "--start-point",
                "HEAD",
                "--dry-run",
                cwd=repository,
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("invalid branch", result.stderr)


class TidyDelegationTests(unittest.TestCase):
    def test_tidy_delegate_preserves_process_contract(self) -> None:
        delegate = ROOT / "skills/tidy/scripts/run_tidy.py"
        self.assertTrue(delegate.is_file(), "the thin tidy delegate must exist")

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            automation_checkout = root / "trusted automation"
            automation_checkout.mkdir()
            target_repository = root / "target repository"
            target_repository.mkdir()
            bin_directory = root / "bin"
            bin_directory.mkdir()
            fake_uv = bin_directory / "uv"
            fake_uv.write_text(
                "#!/usr/bin/env python3\n"
                "import json\n"
                "import os\n"
                "import sys\n"
                "stdin = sys.stdin.read()\n"
                "print(json.dumps("
                "{'argv': sys.argv[1:], 'cwd': os.getcwd(), 'stdin': stdin}"
                "))\n"
                "print('delegated stderr', file=sys.stderr)\n"
                "raise SystemExit(37)\n",
                encoding="utf-8",
            )
            fake_uv.chmod(0o755)
            environment = os.environ.copy()
            environment["PATH"] = f"{bin_directory}{os.pathsep}{environment['PATH']}"

            result = run_script(
                "skills/tidy/scripts/run_tidy.py",
                str(automation_checkout),
                "--",
                "--dry-run",
                "value with spaces",
                "$(touch should-not-run)",
                cwd=target_repository,
                env=environment,
                input_text="interactive sentinel\n",
            )

        self.assertEqual(37, result.returncode)
        self.assertEqual("delegated stderr", result.stderr.strip())
        invocation = json.loads(result.stdout)
        self.assertEqual(str(target_repository.resolve()), invocation["cwd"])
        self.assertEqual("interactive sentinel\n", invocation["stdin"])
        self.assertEqual(
            [
                "run",
                "--project",
                str(automation_checkout),
                "--locked",
                "hephaestus-tidy",
                "--",
                "--dry-run",
                "value with spaces",
                "$(touch should-not-run)",
            ],
            invocation["argv"],
        )


class DebuggingScriptTests(unittest.TestCase):
    def test_repository_evidence_bounds_recent_diff_to_ten_commits(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repo"
            initialize_repository(repository)
            for number in range(12):
                path = repository / f"change-{number}.txt"
                path.write_text(f"change {number}\n", encoding="utf-8")
                git(repository, "add", path.name)
                git(repository, "commit", "--quiet", "-m", f"test: change {number}")

            result = run_script(
                "skills/systematic-debugging/scripts/repository_evidence.py",
                "change",
                "--source-root",
                ".",
                cwd=repository,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        evidence = json.loads(result.stdout)
        self.assertNotIn("change-0.txt", evidence["recent_diff"])
        self.assertIn("change-2.txt", evidence["recent_diff"])
        self.assertIn("change-11.txt", evidence["recent_diff"])
        self.assertIn("..HEAD", evidence["recent_range"])

    def test_repository_evidence_reports_unborn_repository_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repo"
            repository.mkdir()
            git(repository, "init", "--quiet")
            result = run_script(
                "skills/systematic-debugging/scripts/repository_evidence.py",
                "anything",
                cwd=repository,
            )

        self.assertEqual(1, result.returncode)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("HEAD", result.stderr)

    def test_repository_evidence_does_not_require_ripgrep(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            repository = root / "repo"
            initialize_repository(repository)
            bin_directory = root / "bin"
            bin_directory.mkdir()
            git_executable = shutil.which("git")
            self.assertIsNotNone(git_executable)
            (bin_directory / "git").symlink_to(str(git_executable))
            (bin_directory / "python3").symlink_to(sys.executable)
            environment = os.environ.copy()
            environment["PATH"] = str(bin_directory)

            result = run_script(
                "skills/systematic-debugging/scripts/repository_evidence.py",
                "base",
                "--source-root",
                ".",
                cwd=repository,
                env=environment,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn(
            "tracked.txt:1:base", json.loads(result.stdout)["pattern_matches"]
        )

    def test_repository_evidence_reports_recent_commits_and_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repo"
            initialize_repository(repository)
            result = run_script(
                "skills/systematic-debugging/scripts/repository_evidence.py",
                "base",
                "--source-root",
                ".",
                cwd=repository,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        evidence = json.loads(result.stdout)
        self.assertIn("test: initialize", evidence["recent_commits"])
        self.assertIn("tracked.txt", evidence["pattern_matches"])


if __name__ == "__main__":
    unittest.main()
