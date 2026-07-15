"""Behavior tests for skill-local executable helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


def run_script(
    relative_path: str,
    *arguments: str,
    cwd: Path,
    env: dict[str, str] | None = None,
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

    def test_resolve_pr_accepts_explicit_number(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            result = run_script(
                "skills/pr-review/scripts/resolve_pr.py",
                "42",
                cwd=root,
                env=self.make_fake_tools(root, []),
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(42, json.loads(result.stdout)["number"])

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
                    result = run_script(
                        "skills/pr-review/scripts/resolve_pr.py",
                        "42",
                        cwd=root,
                        env=env,
                    )

                self.assertEqual(1, result.returncode)
                self.assertIn(message, result.stderr)

    def test_resolve_pr_reports_no_candidate_and_usage_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            repository = root / "repo"
            initialize_repository(repository)
            env = self.make_fake_tools(root, [])
            missing = run_script(
                "skills/pr-review/scripts/resolve_pr.py", cwd=repository, env=env
            )
            usage = run_script(
                "skills/pr-review/scripts/resolve_pr.py",
                "1",
                "2",
                cwd=repository,
                env=env,
            )

        self.assertEqual(2, missing.returncode)
        self.assertIn("no open pull request", missing.stderr)
        self.assertEqual(64, usage.returncode)
        self.assertIn("usage:", usage.stderr)

    def test_pr_helpers_reject_option_like_identifiers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            env = self.make_fake_tools(root, [])
            resolved = run_script(
                "skills/pr-review/scripts/resolve_pr.py", "-R", cwd=root, env=env
            )
            collected = run_script(
                "skills/pr-review/scripts/collect_evidence.py", "-R", cwd=root, env=env
            )

        self.assertEqual(1, resolved.returncode)
        self.assertIn("invalid pull-request identifier", resolved.stderr)
        self.assertEqual(1, collected.returncode)
        self.assertIn("invalid pull-request identifier", collected.stderr)

    def test_resolve_pr_reports_malformed_github_output_as_operational_failure(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            env = self.make_fake_tools(root, [])
            env["FAKE_GH_VIEW_RAW"] = "not JSON"
            result = run_script(
                "skills/pr-review/scripts/resolve_pr.py", "42", cwd=root, env=env
            )

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
            result = run_script(
                "skills/pr-review/scripts/resolve_pr.py",
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
            result = run_script(
                "skills/pr-review/scripts/resolve_pr.py",
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

        self.assertEqual(64, usage.returncode)
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

        self.assertEqual(1, result.returncode)
        self.assertIn("must not begin with '-'", result.stderr)

    def test_collect_evidence_combines_pr_metadata_files_and_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            (bin_dir / "gh").symlink_to(ROOT / "tests" / "fixtures" / "fake_gh.py")
            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
            env["FAKE_GH_VIEW_JSON"] = json.dumps(
                {"number": 9, "title": "Portable Athena"}
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

        self.assertEqual(0, result.returncode, result.stderr)
        evidence = json.loads(result.stdout)
        self.assertEqual(9, evidence["pull_request"]["number"])
        self.assertEqual(["skills/pr-review/SKILL.md"], evidence["changed_files"])
        self.assertEqual("SUCCESS", evidence["checks"][0]["state"])

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

        self.assertEqual(64, usage.returncode)
        self.assertIn("usage:", usage.stderr)
        self.assertEqual(1, invalid.returncode)
        self.assertIn("invalid check evidence", invalid.stderr)


class CodeReviewScriptTests(unittest.TestCase):
    def test_review_diff_discovers_non_origin_trunk_base(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            source.mkdir()
            git(source, "init", "--quiet", "--initial-branch=trunk")
            git(source, "config", "user.name", "Athena Tests")
            git(source, "config", "user.email", "athena-tests@example.invalid")
            (source / "tracked.txt").write_text("base\n", encoding="utf-8")
            git(source, "add", "tracked.txt")
            git(source, "commit", "--quiet", "-m", "test: initialize")
            remote = root / "remote.git"
            subprocess.run(
                ["git", "clone", "--quiet", "--bare", str(source), str(remote)],
                check=True,
            )
            git(source, "remote", "add", "upstream", str(remote))
            git(source, "fetch", "--quiet", "upstream")
            git(source, "checkout", "--quiet", "-b", "feature")

            result = run_script(
                "skills/code-review/scripts/review_diff.py",
                "--metadata-only",
                cwd=source,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        metadata = json.loads(result.stdout)
        self.assertEqual("upstream", metadata["remote"])
        self.assertEqual("trunk", metadata["default_branch"])

    def test_review_diff_prints_full_diff_and_fails_without_a_remote(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            source.mkdir()
            git(source, "init", "--quiet", "--initial-branch=main")
            git(source, "config", "user.name", "Athena Tests")
            git(source, "config", "user.email", "athena-tests@example.invalid")
            (source / "tracked.txt").write_text("base\n", encoding="utf-8")
            git(source, "add", "tracked.txt")
            git(source, "commit", "--quiet", "-m", "test: initialize")
            no_remote = run_script(
                "skills/code-review/scripts/review_diff.py",
                "--metadata-only",
                cwd=source,
            )

            remote = root / "remote.git"
            subprocess.run(
                ["git", "clone", "--quiet", "--bare", str(source), str(remote)],
                check=True,
            )
            git(source, "remote", "add", "origin", str(remote))
            git(source, "fetch", "--quiet", "origin")
            git(source, "checkout", "--quiet", "-b", "feature")
            (source / "tracked.txt").write_text("feature\n", encoding="utf-8")
            git(source, "commit", "-qam", "test: feature")
            full = run_script("skills/code-review/scripts/review_diff.py", cwd=source)

        self.assertEqual(1, no_remote.returncode)
        self.assertIn("cannot choose a review remote", no_remote.stderr)
        self.assertEqual(0, full.returncode, full.stderr)
        self.assertIn('"remote": "origin"', full.stdout)
        self.assertIn("tracked.txt", full.stdout)


class WorktreeScriptTests(unittest.TestCase):
    def test_prepare_worktree_uses_explicit_path_and_start_point(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
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
            base = Path(temporary_directory) / "isolated"
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

    def test_remove_worktree_rejects_dirty_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repo"
            initialize_repository(repository)
            worktree = Path(temporary_directory) / "feature"
            git(repository, "worktree", "add", "-q", "-b", "feature", str(worktree))
            expected_head = git(worktree, "rev-parse", "HEAD")
            (worktree / "dirty.txt").write_text("dirty\n", encoding="utf-8")
            result = run_script(
                "skills/worktree-cleanup/scripts/remove_worktree.py",
                str(worktree),
                "--expected-head",
                expected_head,
                cwd=repository,
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("not clean", result.stderr)

    def test_remove_worktree_requires_audited_head(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repo"
            initialize_repository(repository)
            worktree = Path(temporary_directory) / "feature"
            git(repository, "worktree", "add", "-q", "-b", "feature", str(worktree))

            result = run_script(
                "skills/worktree-cleanup/scripts/remove_worktree.py",
                str(worktree),
                cwd=repository,
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("expected-head", result.stderr)

    def test_remove_worktree_rejects_unregistered_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repo"
            initialize_repository(repository)
            unregistered = Path(temporary_directory) / "unregistered"
            unregistered.mkdir()
            result = run_script(
                "skills/worktree-cleanup/scripts/remove_worktree.py",
                str(unregistered),
                "--expected-head",
                git(repository, "rev-parse", "HEAD"),
                cwd=repository,
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("not a registered worktree", result.stderr)

    def test_remove_worktree_rejects_changed_head(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repo"
            initialize_repository(repository)
            worktree = Path(temporary_directory) / "feature"
            git(repository, "worktree", "add", "-q", "-b", "feature", str(worktree))
            audited_head = git(worktree, "rev-parse", "HEAD")
            (worktree / "tracked.txt").write_text("changed\n", encoding="utf-8")
            git(worktree, "commit", "-qam", "test: move head")
            result = run_script(
                "skills/worktree-cleanup/scripts/remove_worktree.py",
                str(worktree),
                "--expected-head",
                audited_head,
                cwd=repository,
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("HEAD changed", result.stderr)

    def test_remove_worktree_does_not_prune_unrelated_registration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            repository = root / "repo"
            initialize_repository(repository)
            approved = root / "approved"
            stale = root / "stale"
            git(repository, "worktree", "add", "-q", "-b", "approved", str(approved))
            git(repository, "worktree", "add", "-q", "-b", "stale", str(stale))
            shutil.rmtree(stale)
            result = run_script(
                "skills/worktree-cleanup/scripts/remove_worktree.py",
                str(approved),
                "--expected-head",
                git(approved, "rev-parse", "HEAD"),
                cwd=repository,
            )
            registrations = git(repository, "worktree", "list", "--porcelain")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn(str(stale), registrations)

    def test_remove_worktree_removes_clean_worktree_at_expected_head(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repo"
            initialize_repository(repository)
            worktree = Path(temporary_directory) / "feature"
            git(repository, "worktree", "add", "-q", "-b", "feature", str(worktree))
            expected_head = git(worktree, "rev-parse", "HEAD")
            result = run_script(
                "skills/worktree-cleanup/scripts/remove_worktree.py",
                str(worktree),
                "--expected-head",
                expected_head,
                cwd=repository,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse(worktree.exists())

    def test_audit_worktrees_emits_computable_status(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repo"
            initialize_repository(repository)
            result = run_script(
                "skills/worktree-cleanup/scripts/audit_worktrees.py", cwd=repository
            )

        self.assertEqual(0, result.returncode, result.stderr)
        records = json.loads(result.stdout)
        self.assertEqual(1, len(records))
        self.assertEqual(str(repository.resolve()), records[0]["path"])
        self.assertTrue(records[0]["clean"])


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
