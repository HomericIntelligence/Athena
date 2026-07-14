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
    return subprocess.run(
        [str(ROOT / relative_path), *arguments],
        cwd=cwd,
        env=env,
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
            env["FAKE_GH_CHANGED_FILES"] = "skills/pr-review/SKILL.md"
            env["FAKE_GH_CHECKS"] = "required-checks-gate pass"
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
        self.assertIn("required-checks-gate pass", evidence["checks"])


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


class WorktreeScriptTests(unittest.TestCase):
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
                "--dry-run",
                cwd=repository,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            str((base / "feature-three").resolve()),
            json.loads(result.stdout)["path"],
        )

    def test_prepare_worktree_rejects_invalid_branch_name(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repo"
            initialize_repository(repository)
            result = run_script(
                "skills/git-worktrees/scripts/prepare_worktree.py",
                "../escape",
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
