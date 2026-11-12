"""Behavior tests for the change-review scope resolver.

The tests run against temporary local repositories. They assert observable
behavior and exit codes. They do not assert generated prose.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from typing import Any, cast
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "skills" / "change-review" / "scripts" / "resolve_scope.py"


def load_module() -> ModuleType:
    name = "test_resolve_scope"
    spec = importlib.util.spec_from_file_location(name, MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("The resolver helper cannot load.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@contextmanager
def temp_directory() -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as directory:
        yield Path(directory).resolve()


def init_repo(path: Path) -> Path:
    subprocess.run(
        ["git", "init", "-b", "main", str(path)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "test@example.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "Test Actor"],
        check=True,
        capture_output=True,
    )
    return path


def git_in(repo: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def commit_all(repo: Path, message: str) -> str:
    subprocess.run(
        ["git", "-C", str(repo), "add", "."], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-s", "-q", "-m", message],
        check=True,
        capture_output=True,
    )
    return git_in(repo, "rev-parse", "HEAD")


def seeded_repo(root: Path) -> Path:
    repo = init_repo(root / "repo")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("print('alpha')\n", encoding="utf-8")
    commit_all(repo, "initial")
    return repo


def run_main(module: ModuleType, repo: Path, argv: list[str]) -> tuple[int, str, str]:
    import io

    stdout = io.StringIO()
    stderr = io.StringIO()
    cwd = os.getcwd()
    os.chdir(repo)
    try:
        with (
            patch.object(sys, "argv", argv),
            patch.object(sys, "stdout", stdout),
            patch.object(sys, "stderr", stderr),
        ):
            rc = module.main()
    finally:
        os.chdir(cwd)
    return rc, stdout.getvalue(), stderr.getvalue()


class HelperFunctionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = cast(Any, load_module())

    def test_content_fingerprint_hashes_streamed_bytes(self) -> None:
        fingerprint = self.module.content_fingerprint(iter([b"ab", b"c"]))
        self.assertEqual(3, fingerprint.length)
        self.assertEqual(hashlib.sha256(b"abc").hexdigest(), fingerprint.digest)

    def test_git_command_builds_expected_argv(self) -> None:
        without_root = self.module.git_command(["ls-files"], None)
        self.assertNotIn("-C", without_root)
        self.assertIn("ls-files", without_root)
        with_root = self.module.git_command(["ls-files"], Path("/repo"))
        self.assertIn("-C", with_root)
        self.assertIn("/repo", with_root)

    def test_path_list_sorts_and_splits_nul_records(self) -> None:
        self.assertEqual(
            ["a", "b"],
            self.module.path_list(b"b\0a\0"),
        )

    def test_nul_records_skips_empty_records(self) -> None:
        self.assertEqual([b"a", b"b"], self.module.nul_records(b"a\0\0b\0"))

    def test_git_object_kind_classifies_git_object_types(self) -> None:
        self.assertEqual("git-symlink", self.module.git_object_kind("120000", "blob"))
        self.assertEqual(
            "git-submodule", self.module.git_object_kind("160000", "commit")
        )
        self.assertEqual(
            "git-submodule", self.module.git_object_kind("040000", "commit")
        )
        self.assertEqual("git-blob", self.module.git_object_kind("100644", "blob"))
        self.assertEqual("git-other", self.module.git_object_kind("100644", "tree"))

    def test_path_components_rejects_invalid_relative_paths(self) -> None:
        self.assertEqual(("a", "b"), self.module.path_components("a/b"))
        with self.assertRaises(RuntimeError):
            self.module.path_components("a/../b")
        with self.assertRaises(RuntimeError):
            self.module.path_components("")

    def test_normalized_paths_sorts_deduplicates_and_rejects_outside(self) -> None:
        with temp_directory() as directory:
            root = Path(directory)
            (root / "b.txt").write_text("b\n", encoding="utf-8")
            (root / "a.txt").write_text("a\n", encoding="utf-8")
            normalized = self.module.normalized_paths(root, ["b.txt", "a.txt", "b.txt"])
            self.assertEqual(["a.txt", "b.txt"], normalized)
            with self.assertRaises(RuntimeError):
                self.module.normalized_paths(root, ["../outside.txt"])

    def test_verified_commit_rejects_option_like_references(self) -> None:
        with self.assertRaises(RuntimeError):
            self.module.verified_commit("-badref")

    def test_range_revisions_requires_exactly_one_separator(self) -> None:
        with self.assertRaises(RuntimeError):
            self.module.range_revisions("a..b..c", Path("."))

    def test_git_blob_object_id_matches_git_hash_object(self) -> None:
        with temp_directory() as directory:
            repo = seeded_repo(directory)
            contents = b"alpha-blob\n"
            object_id = self.module.git_blob_object_id(contents, "sha1")
            completed = subprocess.run(
                ["git", "-C", str(repo), "hash-object", "--stdin"],
                input=contents,
                check=True,
                capture_output=True,
                text=False,
            )
            self.assertEqual(completed.stdout.strip().decode("ascii"), object_id)

    def test_git_object_format_matches_git_rev_parse(self) -> None:
        with temp_directory() as directory:
            repo = seeded_repo(directory)
            self.assertEqual(
                git_in(repo, "rev-parse", "--show-object-format"),
                self.module.git_object_format(repo),
            )

    def test_git_mode_for_worktree_file_maps_executable_bit(self) -> None:
        entry = self.module.PathEntry("p", "file", mode="100644")
        self.assertEqual("100644", self.module.git_mode_for_worktree_file(entry))
        executable = self.module.PathEntry("p", "file", mode="100755")
        self.assertEqual("100755", self.module.git_mode_for_worktree_file(executable))

    def test_dependency_content_identities_changes_with_content(self) -> None:
        with temp_directory() as directory:
            repo = seeded_repo(directory)
            result = self.module.dependency_content_identities(
                "worktree",
                (self.module.PathEntry("seed.txt", "file", mode="100644"),),
                repo,
            )
            self.assertIn("seed.txt", result)

    def test_entry_documents_includes_set_fields(self) -> None:
        entries = (
            self.module.PathEntry(
                "p",
                "file",
                target=None,
                object_id="abc",
                mode="100644",
            ),
        )
        documents = self.module.entry_documents(entries)
        self.assertEqual(
            [{"kind": "file", "mode": "100644", "object_id": "abc", "path": "p"}],
            documents,
        )


class WorktreeScopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = cast(Any, load_module())

    def test_worktree_scope_reports_modified_and_untracked_paths(self) -> None:
        with temp_directory() as directory:
            repo = seeded_repo(directory)
            (repo / "src" / "app.py").write_text("print('beta')\n", encoding="utf-8")
            (repo / "untracked.txt").write_text("new\n", encoding="utf-8")
            rc, out, err = run_main(
                self.module,
                repo,
                ["resolve_scope.py", "--worktree", "--"],
            )
            self.assertEqual(0, rc, err)
            data = json.loads(out)
            self.assertEqual("worktree", data["scope"])
            self.assertIn("src/app.py", data["paths"])
            self.assertIn("untracked.txt", data["untracked_paths"])
            self.assertIn("scope_digest", data)
            self.assertEqual("worktree", data["content_source"])

    def test_staged_scope_reports_staged_paths(self) -> None:
        with temp_directory() as directory:
            repo = seeded_repo(directory)
            (repo / "src" / "app.py").write_text("print('beta')\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(repo), "add", "."],
                check=True,
                capture_output=True,
            )
            rc, out, err = run_main(
                self.module,
                repo,
                ["resolve_scope.py", "--staged"],
            )
            self.assertEqual(0, rc, err)
            data = json.loads(out)
            self.assertEqual("staged", data["scope"])
            self.assertIn("src/app.py", data["paths"])
            self.assertEqual("index", data["content_source"])

    def test_range_scope_reports_range_paths(self) -> None:
        with temp_directory() as directory:
            repo = seeded_repo(directory)
            base = git_in(repo, "rev-parse", "HEAD")
            (repo / "src" / "app.py").write_text("print('beta')\n", encoding="utf-8")
            head = commit_all(repo, "change")
            rc, out, err = run_main(
                self.module,
                repo,
                ["resolve_scope.py", "--range", f"{base}..{head}"],
            )
            self.assertEqual(0, rc, err)
            data = json.loads(out)
            self.assertEqual(base, data["base"])
            self.assertEqual(head, data["head"])
            self.assertIn("src/app.py", data["paths"])
            self.assertEqual("head-tree", data["content_source"])

    def test_worktree_scope_includes_symlink_changes(self) -> None:
        with temp_directory() as directory:
            repo = seeded_repo(directory)
            (repo / "link.txt").symlink_to("seed.txt")
            commit_all(repo, "add symlink")
            (repo / "link.txt").unlink()
            (repo / "link.txt").symlink_to("src/app.py")
            rc, out, err = run_main(
                self.module,
                repo,
                ["resolve_scope.py", "--worktree"],
            )
            self.assertEqual(0, rc, err)
            data = json.loads(out)
            self.assertIn("link.txt", data["paths"])

    def test_batched_worktree_resolution_reports_batches(self) -> None:
        with temp_directory() as directory:
            repo = seeded_repo(directory)
            (repo / "src" / "app.py").write_text("print('beta')\n", encoding="utf-8")
            (repo / "untracked.txt").write_text("new\n", encoding="utf-8")
            rc, out, err = run_main(
                self.module,
                repo,
                ["resolve_scope.py", "--worktree", "--batch-size", "2"],
            )
            self.assertEqual(0, rc, err)
            lines = [line for line in out.splitlines() if line.strip()]
            self.assertTrue(lines)
            final = json.loads(lines[-1])
            self.assertTrue(final["complete"])
            self.assertGreaterEqual(final["batches"], 2)

    def test_main_rejects_invalid_batch_size(self) -> None:
        with temp_directory() as directory:
            repo = seeded_repo(directory)
            rc, _out, err = run_main(
                self.module,
                repo,
                ["resolve_scope.py", "--worktree", "--batch-size", "0"],
            )
            self.assertEqual(1, rc)
            self.assertTrue(err.strip())

    def test_main_rejects_range_with_multiple_separators(self) -> None:
        with temp_directory() as directory:
            repo = seeded_repo(directory)
            rc, _out, err = run_main(
                self.module,
                repo,
                ["resolve_scope.py", "--range", "a..b..c"],
            )
            self.assertEqual(1, rc)
            self.assertTrue(err.strip())

    def test_main_rejects_paths_outside_repository(self) -> None:
        with temp_directory() as directory:
            repo = seeded_repo(directory)
            rc, _out, err = run_main(
                self.module,
                repo,
                ["resolve_scope.py", "--worktree", "/definitely/outside/file.txt"],
            )
            self.assertEqual(1, rc)
            self.assertIn("outside the repository", err)

    def test_main_reports_git_failure_outside_repository(self) -> None:
        with temp_directory() as directory:
            rc, _out, err = run_main(
                self.module,
                directory,
                ["resolve_scope.py", "--staged"],
            )
            self.assertEqual(1, rc)
            self.assertTrue(err.strip())


if __name__ == "__main__":
    unittest.main()


class ErrorPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = cast(Any, load_module())

    def test_git_stream_fingerprint_rejects_failing_git_command(self) -> None:
        with temp_directory() as directory:
            repo = seeded_repo(directory)
            with self.assertRaises(RuntimeError):
                self.module.git_stream_fingerprint(
                    "diff",
                    "--bad-revision-9f8e7d^..HEAD",
                    repository_root=repo,
                )

    def test_git_stream_fingerprint_reports_missing_git(self) -> None:
        original = self.module.subprocess.Popen
        self.module.subprocess.Popen = None

        def fake_popen(*args: Any, **kwargs: Any) -> Any:
            raise FileNotFoundError("git")

        self.module.subprocess.Popen = fake_popen
        try:
            with self.assertRaisesRegex(RuntimeError, "not available"):
                self.module.git_stream_fingerprint(
                    "diff", "HEAD", repository_root=Path(".")
                )
        finally:
            self.module.subprocess.Popen = original

    def test_consume_git_nul_records_rejects_failing_git_command(self) -> None:
        with temp_directory() as directory:
            repo = seeded_repo(directory)
            with self.assertRaises(RuntimeError):
                self.module.consume_git_nul_records(
                    ["not-a-git-subcommand-9f8e7d"], repo, lambda record: None
                )

    def test_worktree_path_entry_reports_absent_for_missing_parent(self) -> None:
        with temp_directory() as directory:
            repo = seeded_repo(directory)
            entry = self.module.worktree_path_entry(repo, "missing-dir/file.txt")
            self.assertEqual("absent", entry.kind)

    def test_worktree_path_entry_reports_other_for_directories(self) -> None:
        with temp_directory() as directory:
            repo = seeded_repo(directory)
            entry = self.module.worktree_path_entry(repo, "src")
            self.assertEqual("other", entry.kind)

    def test_index_entry_map_rejects_malformed_records(self) -> None:
        original = self.module.git_bytes
        self.module.git_bytes = lambda *a, **k: b"not-a-valid-index-record\0"
        try:
            with self.assertRaises(RuntimeError):
                self.module.index_entry_map([Path("file.txt")], Path("."))
        finally:
            self.module.git_bytes = original

    def test_index_entry_map_rejects_unmerged_index_entries(self) -> None:
        original = self.module.git_bytes
        self.module.git_bytes = lambda *a, **k: b"100644 abc123 1\tfile.txt\0"
        try:
            with self.assertRaisesRegex(RuntimeError, "unmerged"):
                self.module.index_entry_map([Path("file.txt")], Path("."))
        finally:
            self.module.git_bytes = original

    def test_parse_head_tree_record_rejects_malformed_records(self) -> None:
        with self.assertRaises(RuntimeError):
            self.module.parse_head_tree_record(b"no-header-path\0")

    def test_head_tree_path_entries_returns_empty_for_no_paths(self) -> None:
        self.assertEqual((), self.module.head_tree_path_entries("HEAD", (), Path(".")))

    def test_parse_tagged_index_record_rejects_malformed_records(self) -> None:
        with self.assertRaises(RuntimeError):
            self.module.parse_tagged_index_record(b"garbage\0")

    def test_parse_tagged_index_record_rejects_unmerged_entries(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "unmerged"):
            self.module.parse_tagged_index_record(b"M 100644 abc123 1\tfile.txt\0")

    def test_worktree_metadata_consumes_skip_worktree_index_records(self) -> None:
        original = self.module.consume_git_nul_records
        with temp_directory() as directory:
            repo = seeded_repo(directory)

            def fake_consume(
                arguments: list[str],
                repository_root: Path,
                consume: Any,
            ) -> None:
                if arguments[0] == "ls-tree":
                    consume(b"100644 blob abc123\ttracked.txt")
                elif arguments[0].startswith("ls-files"):
                    consume(b"S 100644 def456 0\tskipped.txt")

            self.module.consume_git_nul_records = fake_consume
            try:
                metadata = self.module.worktree_metadata("HEAD", (), repo)
            finally:
                self.module.consume_git_nul_records = original
            self.assertIn("skipped.txt", metadata.skip_worktree_paths)

    def test_worktree_metadata_rejects_staged_change_outside_candidates(self) -> None:
        original = self.module.consume_git_nul_records
        with temp_directory() as directory:
            repo = seeded_repo(directory)

            def fake_consume(
                arguments: list[str],
                repository_root: Path,
                consume: Any,
            ) -> None:
                if arguments[0] == "ls-tree":
                    consume(b"100644 blob abc123\ttracked.txt")
                elif arguments[0].startswith("ls-files"):
                    consume(b"M 100644 def456 0\ttracked.txt")
                elif "diff" in arguments:
                    consume(b"untracked-change.txt")

            self.module.consume_git_nul_records = fake_consume
            try:
                with self.assertRaisesRegex(RuntimeError, "does not contain"):
                    self.module.worktree_metadata("HEAD", (), repo)
            finally:
                self.module.consume_git_nul_records = original

    def test_git_object_format_rejects_unknown_hash_format(self) -> None:
        original = self.module.git_text
        self.module.git_text = lambda *a, **k: "definitely-not-a-hash-9f8e7d"
        try:
            with self.assertRaises(RuntimeError):
                self.module.git_object_format(Path("."))
        finally:
            self.module.git_text = original

    def test_read_regular_file_snapshot_rejects_non_regular_files(self) -> None:
        with temp_directory() as directory:
            repo = seeded_repo(directory)
            with self.assertRaisesRegex(RuntimeError, "not a regular file"):
                self.module.read_regular_file_snapshot_without_following(repo, "src")

    def test_worktree_matches_entry_compares_symlink_entries(self) -> None:
        snapshot = self.module.WorktreePathSnapshot(
            entry=self.module.PathEntry("link.txt", "symlink", target="seed.txt"),
            object_id="abc123",
        )
        tree = self.module.PathEntry(
            "link.txt", "git-symlink", object_id="abc123", mode="120000"
        )
        self.assertTrue(self.module.worktree_matches_entry(snapshot, tree))
        other = self.module.PathEntry(
            "link.txt", "git-symlink", object_id="def456", mode="120000"
        )
        self.assertFalse(self.module.worktree_matches_entry(snapshot, other))

    def test_worktree_matches_entry_accepts_absent_for_missing_tree(self) -> None:
        snapshot = self.module.WorktreePathSnapshot(
            entry=self.module.PathEntry("file.txt", "absent"),
        )
        self.assertTrue(self.module.worktree_matches_entry(snapshot, None))

    def test_dependency_identities_cover_manifest_edge_cases(self) -> None:
        with temp_directory() as directory:
            repo = seeded_repo(directory)
            staged = self.module.dependency_content_identities(
                "staged",
                (
                    self.module.PathEntry(
                        "seed.txt", "git-blob", object_id="abc123", mode="100644"
                    ),
                ),
                repo,
            )
            self.assertIn("seed.txt", staged)
            absent = self.module.dependency_content_identities(
                "staged",
                (self.module.PathEntry("gone.txt", "absent"),),
                repo,
            )
            self.assertIn("gone.txt", absent)
            self.assertNotEqual(staged["seed.txt"], absent["gone.txt"])

    def test_range_scope_batched_resolution_reports_complete(self) -> None:
        with temp_directory() as directory:
            repo = seeded_repo(directory)
            base = git_in(repo, "rev-parse", "HEAD")
            (repo / "src" / "app.py").write_text("print('beta')\n", encoding="utf-8")
            head = commit_all(repo, "change")
            rc, out, err = run_main(
                self.module,
                repo,
                [
                    "resolve_scope.py",
                    "--range",
                    f"{base}..{head}",
                    "--batch-size",
                    "1",
                ],
            )
            self.assertEqual(0, rc, err)
            lines = [line for line in out.splitlines() if line.strip()]
            final = json.loads(lines[-1])
            self.assertTrue(final["complete"])
            self.assertGreaterEqual(final["batches"], 1)
