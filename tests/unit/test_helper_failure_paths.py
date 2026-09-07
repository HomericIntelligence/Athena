"""Exercise imported helper interfaces and command failure boundaries."""

from __future__ import annotations

import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def load_helper(skill: str, name: str) -> Any:
    """Load a helper through its import interface without invoking its CLI."""
    path = ROOT / "skills" / skill / "scripts" / f"{name}.py"
    module_name = f"skills.test_{skill.replace('-', '_')}_{name}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    with (
        patch.dict(sys.modules, {module_name: module}),
        patch.object(sys, "path", [str(path.parent), *sys.path]),
    ):
        spec.loader.exec_module(module)
    return module


class HelperFailurePathTests(unittest.TestCase):
    def test_imported_selector_returns_only_main_skill_files(self) -> None:
        module = load_helper("advise", "list_retrievable_skills")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "skills").mkdir()
            for name in ("z.md", "a.md", "a.notes.md", "a.history.md"):
                (root / "skills" / name).touch()
            self.assertEqual(
                [root / "skills/a.md", root / "skills/z.md"],
                module.retrievable_skill_files(root),
            )

    def test_imported_tidy_stops_before_execution_when_revision_is_stale(self) -> None:
        module = load_helper("tidy", "run_tidy")
        with (
            patch.object(
                module.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(["git"], 1),
            ),
            patch("sys.stderr"),
            patch.object(module.os, "execvp") as execute,
        ):
            self.assertEqual(1, module.main(["/unavailable"]))
        execute.assert_not_called()

    def test_diff_command_preserves_failure_diagnostic(self) -> None:
        module = load_helper("pr-review", "diff_context")
        for diagnostic in ("specific cause", ""):
            result = subprocess.CompletedProcess(["git"], 1, "", diagnostic)
            with (
                self.subTest(diagnostic=diagnostic),
                patch.object(module, "run_command", return_value=result),
                self.assertRaises(RuntimeError) as error,
            ):
                module.git("rev-parse", "missing")
            self.assertIn(diagnostic or "rev-parse", str(error.exception))

    def test_repository_evidence_rejects_empty_revision_output(self) -> None:
        module = load_helper("systematic-debugging", "repository_evidence")
        with (
            patch.object(sys, "argv", ["helper", "pattern"]),
            patch.object(module, "run", return_value="") as run,
            patch("sys.stderr", new_callable=io.StringIO) as error,
        ):
            self.assertEqual(1, module.main())
        run.assert_called_once()
        self.assertIn("no commits", error.getvalue())

    def test_snapshot_rejects_sub_kibibyte_quota_before_side_effects(self) -> None:
        module = load_helper("pr-review", "materialize_snapshot")
        for function in (module._mount_tmpfs, module._create_quota_volume):
            with (
                self.subTest(function=function.__name__),
                patch.object(module.sys, "platform", "linux"),
                patch.object(module.shutil, "which", return_value="/bin/mount"),
                patch.object(module, "run_command") as run,
                patch.object(Path, "mkdir") as mkdir,
                self.assertRaises(RuntimeError),
            ):
                function(Path("/unavailable"), 1023)
            run.assert_not_called()
            mkdir.assert_not_called()

    def test_pr_identity_rejects_noncanonical_inputs(self) -> None:
        module = load_helper("pr-review", "pr_identity")
        for value in (None, "owner", "owner/repository/extra"):
            with self.subTest(repository=value), self.assertRaises(RuntimeError):
                module.require_github_repository(value, "repository")
        for value in (None, "GitHub.com", "example.invalid"):
            with self.subTest(host=value), self.assertRaises(RuntimeError):
                module.require_github_host(value, "host")
        for number in (True, 0, "1"):
            with self.subTest(number=number), self.assertRaises(RuntimeError):
                module.canonical_pull_request_url("owner/repository", number)

    def test_collector_rejects_incomplete_or_invalid_expected_revisions(self) -> None:
        import argparse

        module = load_helper("pr-review", "collect_evidence")
        self.assertIsNotNone(module.metadata_error([], require_immutable_identity=True))
        for base, head in (
            ("a" * 40, None),
            ("invalid", "b" * 40),
            ("a" * 40, "invalid"),
        ):
            with (
                self.subTest(base=base, head=head),
                patch("sys.stderr"),
                self.assertRaises(SystemExit) as error,
            ):
                module.expected_identity(argparse.ArgumentParser(), base, head)
            self.assertEqual(2, error.exception.code)

    def test_resolver_rejects_invalid_target_before_provider_queries(self) -> None:
        import argparse

        module = load_helper("pr-review", "resolve_pr")
        cases = (
            (None, "github.com", None),
            (None, "example.invalid", "owner/repository"),
            (
                "https://github.com/other/repository/pull/1",
                "github.com",
                "owner/repository",
            ),
        )
        for identifier, host, repository in cases:
            with (
                self.subTest(identifier=identifier, host=host),
                patch.object(module, "command") as command,
                patch("sys.stderr"),
                self.assertRaises(SystemExit) as error,
            ):
                module.target_from_arguments(
                    argparse.ArgumentParser(), identifier, host, repository
                )
            self.assertEqual(2, error.exception.code)
            command.assert_not_called()

    def test_resolver_rejects_detached_or_malformed_discovery(self) -> None:
        module = load_helper("pr-review", "resolve_pr")
        target = module.RepositoryTarget("github.com", "owner/repository")
        for branch, response, expected_calls in (
            ("", "[]", 0),
            ("feature", "{}", 1),
            ("feature", '[{"number":0}]', 1),
        ):
            with (
                self.subTest(branch=branch, response=response),
                patch.object(module, "current_branch", return_value=branch),
                patch.object(module, "command", return_value=response) as command,
                self.assertRaises((RuntimeError, TypeError)),
            ):
                module.resolve(None, target)
            self.assertEqual(expected_calls, command.call_count)

    def test_scope_rejects_invalid_paths_and_ranges_without_git(self) -> None:
        module = load_helper("change-review", "resolve_scope")
        with patch.object(module, "git_text") as git:
            for reference in ("", "--all"):
                with self.subTest(reference=reference), self.assertRaises(RuntimeError):
                    module.verified_commit(reference)
            for value in ("HEAD", "a..b..c"):
                with self.subTest(value=value), self.assertRaises(RuntimeError):
                    module.range_revisions(value, ROOT)
            for path in ("", "../file", "a/../file"):
                with self.subTest(path=path), self.assertRaises(RuntimeError):
                    module.path_components(path)
            self.assertEqual((), module.head_tree_path_entries("a" * 40, [], ROOT))
        git.assert_not_called()

    def test_scope_stream_reports_missing_output_and_command_failure(self) -> None:
        from unittest.mock import Mock

        module = load_helper("change-review", "resolve_scope")
        for stdout, status in ((None, 0), (io.BytesIO(b"content"), 1)):
            process = Mock(stdout=stdout)
            process.wait.return_value = status
            process.poll.return_value = status
            with (
                self.subTest(status=status),
                patch.object(module.subprocess, "Popen", return_value=process),
                self.assertRaises(RuntimeError),
            ):
                module.git_stream_fingerprint("diff")
            if stdout is not None:
                self.assertTrue(stdout.closed)
