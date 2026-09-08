"""Exercise imported helper interfaces and command failure boundaries."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path
from typing import Any
from unittest.mock import call, patch

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

    def test_collector_rejects_checks_for_a_different_head(self) -> None:
        collector = load_helper("pr-review", "collect_evidence")
        head_oid = "b" * 40
        cases = {
            "stale": ["a" * 40],
            "mixed": [head_oid, "a" * 40],
        }
        for name, check_heads in cases.items():
            response = json.dumps(
                {
                    "total_count": len(check_heads),
                    "check_runs": [
                        {
                            "conclusion": "success",
                            "head_sha": check_head,
                            "id": index,
                            "name": f"check-{index}",
                            "status": "completed",
                        }
                        for index, check_head in enumerate(check_heads, start=1)
                    ],
                }
            ).encode()
            with (
                self.subTest(name=name),
                patch.object(collector, "bounded_gh_output", return_value=response),
                self.assertRaises(collector.CheckEvidenceCoverageGap),
            ):
                collector.head_bound_check_runs("owner/repository", head_oid)

    def test_collector_binds_both_immutable_path_lenses(self) -> None:
        collector = load_helper("pr-review", "collect_evidence")
        base_oid = "a" * 40
        head_oid = "b" * 40
        merge_base = "c" * 40
        with (
            patch.object(collector, "require_complete_git_history"),
            patch.object(collector, "git_bytes", return_value=b""),
            patch.object(
                collector,
                "require_unambiguous_git_merge_base",
                return_value=merge_base,
            ),
            patch.object(
                collector,
                "immutable_range_paths",
                side_effect=[
                    [b"author-intent.txt"],
                    [b"current-target.txt"],
                ],
            ) as range_paths,
        ):
            manifest = collector.immutable_changed_paths(base_oid, head_oid)

        self.assertEqual(("author-intent.txt", "current-target.txt"), manifest.paths)
        self.assertEqual(
            sha256(b"author-intent.txt\0current-target.txt\0").hexdigest(),
            manifest.sha256,
        )
        self.assertEqual(
            [
                call(merge_base, head_oid, cwd=None),
                call(base_oid, head_oid, cwd=None),
            ],
            range_paths.call_args_list,
        )

    def test_scope_git_reads_disable_local_execution_and_replacements(self) -> None:
        resolver = load_helper("change-review", "resolve_scope")
        command = resolver.git_command(("status", "--short"), ROOT)
        environment = resolver.git_read_environment()

        self.assertEqual("git", command[0])
        self.assertIn("core.fsmonitor=false", command)
        self.assertIn("--no-replace-objects", command)
        self.assertEqual("0", environment["GIT_TERMINAL_PROMPT"])
        self.assertEqual("1", environment["GIT_NO_LAZY_FETCH"])
        self.assertEqual(os.devnull, environment["GIT_CONFIG_GLOBAL"])

    def test_scope_rejects_capture_or_head_races(self) -> None:
        resolver = load_helper("change-review", "resolve_scope")
        head_oid = "a" * 40
        with (
            patch.object(resolver, "git_text", return_value=str(ROOT)),
            patch.object(resolver, "verified_commit", return_value=head_oid),
            patch.object(resolver, "capture_scope", side_effect=[object(), object()]),
            self.assertRaisesRegex(RuntimeError, "scope changed"),
        ):
            resolver.resolve_scope("worktree", None, ())

        capture = object()
        with (
            patch.object(resolver, "git_text", return_value=str(ROOT)),
            patch.object(
                resolver,
                "verified_commit",
                side_effect=[head_oid, "b" * 40],
            ),
            patch.object(resolver, "capture_scope", return_value=capture),
            self.assertRaisesRegex(RuntimeError, "HEAD changed"),
        ):
            resolver.resolve_scope("worktree", None, ())

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO support is required")
    def test_scope_bounds_candidates_and_rejects_special_files(self) -> None:
        resolver = load_helper("change-review", "resolve_scope")
        candidates: set[str] = set()
        with patch.object(resolver, "MAX_WORKTREE_CANDIDATES", 1):
            resolver.add_worktree_candidate(candidates, "first.txt")
            with self.assertRaisesRegex(RuntimeError, "candidate limit"):
                resolver.add_worktree_candidate(candidates, "second.txt")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            os.mkfifo(root / "special")
            with self.assertRaisesRegex(RuntimeError, "changed during scope"):
                resolver.untracked_content(root, "special")

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
