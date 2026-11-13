"""Behavior tests for the packaged Athena helper entry points.

These tests exercise the command-line boundary of the scripts. They use
behavioral checks and temporary repositories. They do not assert generated
prose.
"""

from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
MODULES = {
    "cli": ROOT / "skills" / "_cli.py",
    "advise": ROOT / "skills" / "advise" / "scripts" / "list_retrievable_skills.py",
    "repository_evidence": (
        ROOT / "skills" / "systematic-debugging" / "scripts" / "repository_evidence.py"
    ),
    "run_tidy": ROOT / "skills" / "tidy" / "scripts" / "run_tidy.py",
    "prepare_worktree": (
        ROOT / "skills" / "git-worktrees" / "scripts" / "prepare_worktree.py"
    ),
}


@contextlib.contextmanager
def temp_directory() -> Iterator[Path]:
    """Yield a symlink-free temporary directory path."""
    with tempfile.TemporaryDirectory() as directory:
        yield Path(directory).resolve()


def load_module(path: Path) -> ModuleType:
    name = f"test_entrypoints_{path.stem}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"The helper cannot load: '{path}'.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def standalone_import(path: Path) -> ModuleType:
    """Import the helper as an installed package-less script."""
    name = f"installed_{path.stem}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"The helper cannot load: '{path}'.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def init_repo(path: Path) -> Path:
    subprocess.run(
        ["git", "init", "-b", "main", str(path)],
        check=True,
        capture_output=True,
        text=True,
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


def commit_all(path: Path, message: str) -> None:
    subprocess.run(
        ["git", "-C", str(path), "add", "."],
        check=True,
        capture_output=True,
    )
    completed = subprocess.run(
        ["git", "-C", str(path), "commit", "-s", "-m", message],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"git commit failed: {completed.stderr}{completed.stdout}")


class StandaloneImportTests(unittest.TestCase):
    def test_each_helper_loads_without_package_binding(self) -> None:
        for name, path in MODULES.items():
            with self.subTest(helper=name):
                module = standalone_import(path)
                attribute = "argument_parser" if name == "cli" else "main"
                self.assertTrue(
                    callable(getattr(module, attribute, None)),
                    f"{name} is missing {attribute}",
                )


class SkillCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = cast(Any, load_module(MODULES["cli"]))

    def test_run_command_rejects_empty_command(self) -> None:
        with self.assertRaises(RuntimeError):
            self.module.run_command([])

    def test_run_command_reports_missing_command(self) -> None:
        with self.assertRaises(RuntimeError):
            self.module.run_command(["definitely-not-a-real-command-xyz-9f8e7d"])

    def test_run_command_executes_with_default_check_false(self) -> None:
        result = self.module.run_command(
            ["git", "--version"], capture_output=True, text=True
        )
        self.assertEqual(0, result.returncode)

    def test_git_read_environment_strips_git_and_pins_safety_keys(self) -> None:
        import os

        original = dict(os.environ)
        os.environ["GIT_DIR"] = "/tmp/redirected"
        os.environ["ATHENA_KEEP_ME"] = "yes"
        try:
            env = self.module.git_read_environment()
        finally:
            os.environ.clear()
            os.environ.update(original)
        self.assertNotIn("GIT_DIR", env)
        self.assertEqual("yes", env.get("ATHENA_KEEP_ME"))
        self.assertEqual("1", env["GIT_CONFIG_NOSYSTEM"])
        self.assertEqual("1", env["GIT_NO_REPLACE_OBJECTS"])
        self.assertEqual("0", env["GIT_TERMINAL_PROMPT"])

    def test_git_read_arguments_disable_replacement_objects(self) -> None:
        self.assertIn("--no-replace-objects", self.module.git_read_arguments())

    def test_require_complete_git_history_rejects_failed_probe(self) -> None:
        def fake_run(*args: Any, **kwargs: Any) -> Any:
            return type("R", (), {"returncode": 1, "stdout": "", "stderr": "boom\n"})()

        original = self.module.run_command
        self.module.run_command = cast(Any, fake_run)
        try:
            with self.assertRaisesRegex(RuntimeError, "boom"):
                self.module.require_complete_git_history()
        finally:
            self.module.run_command = original

    def test_require_complete_git_history_rejects_shallow_repository(self) -> None:
        def fake_run(*args: Any, **kwargs: Any) -> Any:
            return type("R", (), {"returncode": 0, "stdout": "true\n", "stderr": ""})()

        original = self.module.run_command
        self.module.run_command = cast(Any, fake_run)
        try:
            with self.assertRaisesRegex(RuntimeError, "non-shallow"):
                self.module.require_complete_git_history()
        finally:
            self.module.run_command = original

    def test_require_complete_git_history_accepts_complete_history(self) -> None:
        def fake_run(*args: Any, **kwargs: Any) -> Any:
            return type("R", (), {"returncode": 0, "stdout": "false\n", "stderr": ""})()

        original = self.module.run_command
        self.module.run_command = cast(Any, fake_run)
        try:
            self.module.require_complete_git_history()
        finally:
            self.module.run_command = original

    def test_require_unambiguous_git_merge_base_rejects_failure(self) -> None:
        def fake_run(*args: Any, **kwargs: Any) -> Any:
            return type("R", (), {"returncode": 1, "stdout": "", "stderr": "boom\n"})()

        original = self.module.run_command
        self.module.run_command = cast(Any, fake_run)
        try:
            with self.assertRaisesRegex(RuntimeError, "boom"):
                self.module.require_unambiguous_git_merge_base("base", "head")
        finally:
            self.module.run_command = original

    def test_require_unambiguous_git_merge_base_rejects_ambiguity(self) -> None:
        def fake_run(*args: Any, **kwargs: Any) -> Any:
            return type(
                "R",
                (),
                {"returncode": 0, "stdout": "aaa\nbbb\n", "stderr": ""},
            )()

        original = self.module.run_command
        self.module.run_command = cast(Any, fake_run)
        try:
            with self.assertRaisesRegex(RuntimeError, "one unambiguous merge base"):
                self.module.require_unambiguous_git_merge_base("base", "head")
        finally:
            self.module.run_command = original

    def test_require_unambiguous_git_merge_base_returns_single_base(self) -> None:
        def fake_run(*args: Any, **kwargs: Any) -> Any:
            return type(
                "R",
                (),
                {"returncode": 0, "stdout": "abc123\n", "stderr": ""},
            )()

        original = self.module.run_command
        self.module.run_command = cast(Any, fake_run)
        try:
            self.assertEqual(
                "abc123", self.module.require_unambiguous_git_merge_base("a", "b")
            )
        finally:
            self.module.run_command = original

    def _make_corpus(self, root: Path, version: str | None = "9.9.9") -> Path:
        corpus = root / "corpus"
        (corpus / "scripts").mkdir(parents=True)
        (corpus / "_cli.py").write_text("# anchor\n", encoding="utf-8")
        if version is not None:
            manifest = corpus / "_plugin.json"
            manifest.write_text(
                json.dumps({"version": version}) if version else "{}",
                encoding="utf-8",
            )
        return corpus / "scripts" / "helper.py"

    def test_corpus_root_finds_anchor(self) -> None:
        with temp_directory() as directory:
            member = self._make_corpus(Path(directory))
            self.assertEqual(
                member.parents[1].resolve(), self.module.corpus_root(member)
            )

    def test_corpus_root_returns_none_without_anchor(self) -> None:
        with temp_directory() as directory:
            candidate = Path(directory) / "nowhere" / "helper.py"
            candidate.parent.mkdir()
            self.assertIsNone(self.module.corpus_root(candidate))

    def test_corpus_version_reads_manifest(self) -> None:
        with temp_directory() as directory:
            member = self._make_corpus(Path(directory), "1.2.3")
            self.assertEqual("1.2.3", self.module.corpus_version(member))

    def test_corpus_version_returns_none_for_missing_or_invalid_version(self) -> None:
        with temp_directory() as directory:
            root = Path(directory)
            member = self._make_corpus(root, version=None)
            self.assertIsNone(self.module.corpus_version(member))
        with temp_directory() as directory:
            root = Path(directory)
            member = self._make_corpus(root, version="")
            self.assertIsNone(self.module.corpus_version(member))

    def test_corpus_version_returns_none_for_malformed_manifest(self) -> None:
        with temp_directory() as directory:
            member = self._make_corpus(Path(directory))
            (member.parents[1] / "_plugin.json").write_text(
                "not json\n", encoding="utf-8"
            )
            self.assertIsNone(self.module.corpus_version(member))

    def test_corpus_relative_path_uses_corpus_root(self) -> None:
        with temp_directory() as directory:
            member = self._make_corpus(Path(directory))
            self.assertEqual(
                "scripts/helper.py", self.module.corpus_relative_path(member)
            )

    def test_corpus_relative_path_falls_back_to_file_name(self) -> None:
        with temp_directory() as directory:
            candidate = Path(directory) / "solo.py"
            candidate.write_text("", encoding="utf-8")
            self.assertEqual("solo.py", self.module.corpus_relative_path(candidate))

    def test_corpus_manifest_prefers_skills_sibling_plugin_manifest(self) -> None:
        with temp_directory() as directory:
            skills_root = Path(directory) / "skills"
            skills_root.mkdir()
            (skills_root / "_cli.py").write_text("", encoding="utf-8")
            member = skills_root / "helper.py"
            self.assertEqual(
                self.module.PLUGIN_ROOT / ".codex-plugin" / "plugin.json",
                self.module.corpus_manifest(member),
            )

    def test_plugin_version_reads_repository_manifest(self) -> None:
        self.assertRegex(
            self.module.plugin_version(),
            r"^[0-9]+\.[0-9]+\.[0-9]+([-.][0-9A-Za-z.-]+)?$",
        )

    def test_version_action_prints_version_and_exits_zero(self) -> None:
        import io
        import sys as system

        parser = self.module.argument_parser(description="test")
        buffer = io.StringIO()
        original = system.stdout
        system.stdout = buffer
        try:
            with self.assertRaises(SystemExit) as raised:
                parser.parse_args(["--version"])
        finally:
            system.stdout = original
        self.assertEqual(0, raised.exception.code)
        self.assertIn(self.module.plugin_version(), buffer.getvalue())

    def test_version_action_reports_unreadable_version(self) -> None:
        def boom() -> str:
            raise TypeError("no version")

        original = self.module.plugin_version
        self.module.plugin_version = cast(Any, boom)
        parser = self.module.argument_parser(description="test")
        try:
            with self.assertRaises(SystemExit) as raised:
                parser.parse_args(["--version"])
        finally:
            self.module.plugin_version = original
        self.assertEqual(1, raised.exception.code)

    def test_interpreter_floor_blocks_old_python(self) -> None:
        import sys as system

        original = system.version_info
        system.version_info = cast(Any, (3, 10, 0))
        try:
            with self.assertRaises(SystemExit) as raised:
                self.module.argument_parser(description="test")
        finally:
            system.version_info = original
        self.assertEqual(2, raised.exception.code)

    def test_interpreter_floor_allows_current_python(self) -> None:
        parser = self.module.argument_parser(description="test")
        self.assertIsNotNone(parser)


class ListRetrievableSkillsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = cast(Any, load_module(MODULES["advise"]))

    def _knowledge_root(self, root: Path) -> Path:
        skills = root / "skills"
        skills.mkdir()
        (skills / "advise.md").write_text("main\n", encoding="utf-8")
        (skills / "advise.notes.md").write_text("companion\n", encoding="utf-8")
        (skills / "advise.notes-2.md").write_text("companion\n", encoding="utf-8")
        (skills / "advise.history-2026.md").write_text("history\n", encoding="utf-8")
        (skills / "advise.history.md").write_text("history\n", encoding="utf-8")
        return root

    def test_retrievable_skill_files_excludes_companion_files(self) -> None:
        with temp_directory() as directory:
            root = self._knowledge_root(Path(directory))
            paths = self.module.retrievable_skill_files(root)
            self.assertEqual(["advise.md"], [path.name for path in paths])

    def test_retrievable_skill_files_rejects_missing_skills_directory(self) -> None:
        with (
            temp_directory() as directory,
            self.assertRaisesRegex(RuntimeError, "not available"),
        ):
            self.module.retrievable_skill_files(Path(directory))

    def test_main_reports_missing_skills_directory(self) -> None:
        import io
        import sys as system
        from unittest.mock import patch

        with temp_directory() as directory:
            argv = ["list_retrievable_skills.py", str(directory)]
            buffer = io.StringIO()
            with (
                patch.object(system, "argv", argv),
                patch.object(system, "stderr", buffer),
            ):
                self.assertEqual(1, self.module.main())
            self.assertIn("not available", buffer.getvalue())

    def test_main_lists_relative_skill_paths(self) -> None:
        import io
        import sys as system
        from unittest.mock import patch

        with temp_directory() as directory:
            root = self._knowledge_root(Path(directory))
            argv = ["list_retrievable_skills.py", str(root)]
            buffer = io.StringIO()
            with (
                patch.object(system, "argv", argv),
                patch.object(system, "stdout", buffer),
            ):
                self.assertEqual(0, self.module.main())
            self.assertEqual("skills/advise.md\n", buffer.getvalue())


class RepositoryEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = cast(Any, load_module(MODULES["repository_evidence"]))

    def test_run_returns_stdout_for_accepted_command(self) -> None:
        self.assertIn("git version", self.module.run("git", "--version"))

    def test_run_raises_for_rejected_command(self) -> None:
        with self.assertRaises(RuntimeError):
            self.module.run("definitely-not-a-real-command-xyz-9f8e7d")

    def test_run_uses_custom_accepted_codes(self) -> None:
        self.assertIn("", self.module.run("git", "--version", accepted_codes=(0, 1)))

    def test_main_prints_evidence_for_a_repo(self) -> None:
        import io
        import json as json_module
        import sys as system
        from unittest.mock import patch

        with temp_directory() as directory:
            repo = init_repo(Path(directory) / "repo")
            (repo / "sample.py").write_text("pattern here\n", encoding="utf-8")
            commit_all(repo, "initial")
            argv = [
                "repository_evidence.py",
                "pattern",
                "--source-root",
                str(repo),
            ]
            buffer = io.StringIO()
            cwd = os.getcwd()
            os.chdir(repo)
            try:
                with (
                    patch.object(system, "argv", argv),
                    patch.object(system, "stdout", buffer),
                ):
                    rc = self.module.main()
            finally:
                os.chdir(cwd)
            self.assertEqual(0, rc)
            data = json_module.loads(buffer.getvalue())
            self.assertIn("pattern_matches", data)
            self.assertIn("recent_commits", data)
            self.assertIn("recent_range", data)

    def test_main_reports_repository_failure(self) -> None:
        import io
        import sys as system
        from unittest.mock import patch

        with temp_directory() as directory:
            argv = [
                "repository_evidence.py",
                "pattern",
                "--source-root",
                str(directory),
            ]
            buffer = io.StringIO()
            cwd = os.getcwd()
            os.chdir(directory)
            try:
                with (
                    patch.object(system, "argv", argv),
                    patch.object(system, "stderr", buffer),
                ):
                    rc = self.module.main()
            finally:
                os.chdir(cwd)
            self.assertEqual(1, rc)
            self.assertTrue(buffer.getvalue().strip())


class RunTidyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = cast(Any, load_module(MODULES["run_tidy"]))

    def test_revision_validation_accepts_current_checkout(self) -> None:
        completed = type("R", (), {"returncode": 0})()

        def fake_run(*args: Any, **kwargs: Any) -> Any:
            return completed

        original = self.module.subprocess.run
        self.module.subprocess.run = cast(Any, fake_run)
        try:
            self.assertEqual(
                0,
                self.module._validate_hephaestus_revision(Path("/checkout")),
            )
        finally:
            self.module.subprocess.run = original

    def test_revision_validation_rejects_stale_checkout(self) -> None:
        import io
        import sys as system
        from unittest.mock import patch

        completed = type("R", (), {"returncode": 1})()

        def fake_run(*args: Any, **kwargs: Any) -> Any:
            return completed

        buffer = io.StringIO()
        original = self.module.subprocess.run
        self.module.subprocess.run = cast(Any, fake_run)
        try:
            with patch.object(system, "stderr", buffer):
                self.assertEqual(
                    1,
                    self.module._validate_hephaestus_revision(Path("/checkout")),
                )
        finally:
            self.module.subprocess.run = original
        self.assertIn("stale", buffer.getvalue())

    def test_revision_validation_reports_missing_git(self) -> None:
        def fake_run(*args: Any, **kwargs: Any) -> Any:
            raise FileNotFoundError("git")

        original = self.module.subprocess.run
        self.module.subprocess.run = cast(Any, fake_run)
        try:
            self.assertEqual(
                127,
                self.module._validate_hephaestus_revision(Path("/checkout")),
            )
        finally:
            self.module.subprocess.run = original

    def test_main_passes_through_arguments_to_tidy(self) -> None:
        recorded: dict[str, Any] = {}

        def fake_execvp(command: str, arguments: list[str]) -> None:
            recorded["command"] = command
            recorded["arguments"] = arguments

        original_validate = self.module._validate_hephaestus_revision
        original_execvp = self.module.os.execvp
        self.module._validate_hephaestus_revision = cast(Any, lambda checkout: 0)
        self.module.os.execvp = cast(Any, fake_execvp)
        try:
            with self.assertRaises(RuntimeError):
                self.module.main(["/checkout", "arg-one"])
        finally:
            self.module._validate_hephaestus_revision = original_validate
            self.module.os.execvp = original_execvp
        self.assertEqual("uv", recorded["command"])
        self.assertIn("arg-one", recorded["arguments"])

    def test_main_reports_missing_uv(self) -> None:
        def fake_execvp(command: str, arguments: list[str]) -> None:
            raise FileNotFoundError("uv")

        original_validate = self.module._validate_hephaestus_revision
        original_execvp = self.module.os.execvp
        self.module._validate_hephaestus_revision = cast(Any, lambda checkout: 0)
        self.module.os.execvp = cast(Any, fake_execvp)
        try:
            self.assertEqual(127, self.module.main(["/checkout", "arg-one"]))
        finally:
            self.module._validate_hephaestus_revision = original_validate
            self.module.os.execvp = original_execvp

    def test_main_propagates_validation_failure(self) -> None:
        original_validate = self.module._validate_hephaestus_revision
        self.module._validate_hephaestus_revision = cast(Any, lambda checkout: 1)
        try:
            self.assertEqual(1, self.module.main(["/checkout"]))
        finally:
            self.module._validate_hephaestus_revision = original_validate


class PrepareWorktreeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = cast(Any, load_module(MODULES["prepare_worktree"]))

    def test_git_raises_on_failure_when_check_is_enabled(self) -> None:
        with (
            temp_directory() as directory,
            self.assertRaisesRegex(RuntimeError, "not a git command"),
        ):
            self.module.git(Path(directory), "not-a-git-subcommand-9f8e7d")

    def test_git_returns_result_when_check_is_disabled(self) -> None:
        with temp_directory() as directory:
            result = self.module.git(
                Path(directory), "not-a-git-subcommand-9f8e7d", check=False
            )
            self.assertNotEqual(0, result.returncode)

    def test_reject_symlinks_below_accepts_plain_paths(self) -> None:
        with temp_directory() as directory:
            root = Path(directory)
            self.module.reject_symlinks_below(root, root / "a" / "b")

    def test_reject_symlinks_below_rejects_paths_outside_root(self) -> None:
        with temp_directory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(RuntimeError, "outside the trusted root"):
                self.module.reject_symlinks_below(root, root.parent / "elsewhere")

    def test_reject_symlinks_below_rejects_symlink_components(self) -> None:
        with temp_directory() as directory:
            root = Path(directory)
            target = root / "target"
            target.mkdir()
            link = root / "link"
            link.symlink_to(target)
            with self.assertRaisesRegex(RuntimeError, "symbolic link"):
                self.module.reject_symlinks_below(root, link / "child")

    def test_select_path_directory_option(self) -> None:
        with temp_directory() as directory:
            root = init_repo(Path(directory) / "repo")
            path, local = self.module.select_path(
                root, "branch-a", Path("wt"), None, None
            )
            self.assertEqual(root / "wt" / "branch-a", path)
            self.assertTrue(local)

    def test_select_path_exact_relative_option(self) -> None:
        with temp_directory() as directory:
            root = init_repo(Path(directory) / "repo")
            path, local = self.module.select_path(
                root, "branch-a", None, Path("wt") / "exact", None
            )
            self.assertEqual((root / "wt" / "exact").resolve(), path)
            self.assertTrue(local)

    def test_select_path_requires_symlink_free_root(self) -> None:
        with temp_directory() as directory:
            root = init_repo(Path(directory) / "repo")
            outside = Path(directory) / "outside"
            outside.mkdir()
            with self.assertRaisesRegex(RuntimeError, "outside the trusted root"):
                self.module.select_path(
                    root,
                    "branch-a",
                    None,
                    Path("outside") / "exact",
                    outside,
                )

    def test_select_path_defaults_to_project_worktrees(self) -> None:
        with temp_directory() as directory:
            root = init_repo(Path(directory) / "repo")
            (root / "seed.txt").write_text("seed\n", encoding="utf-8")
            commit_all(root, "initial")
            path, local = self.module.select_path(root, "branch-a", None, None, None)
            self.assertEqual((root / ".worktrees" / "branch-a").resolve(), path)
            self.assertTrue(local)

    def test_primary_project_root_returns_repo(self) -> None:
        with temp_directory() as directory:
            root = init_repo(Path(directory) / "repo")
            self.assertEqual(root.resolve(), self.module.primary_project_root(root))

    def test_ensure_ignored_writes_exclude_for_project_worktrees(self) -> None:
        with temp_directory() as directory:
            root = init_repo(Path(directory) / "repo")
            worktree = root / ".worktrees" / "probe"
            self.module.ensure_ignored(root, worktree)
            self.module.verify_ignored(root, worktree)

    def test_ensure_ignored_uses_existing_ignore_rule(self) -> None:
        with temp_directory() as directory:
            root = init_repo(Path(directory) / "repo")
            (root / ".gitignore").write_text("otherdir/\n", encoding="utf-8")
            path = root / "otherdir" / "child"
            self.module.ensure_ignored(root, path)

    def test_ensure_ignored_requires_ignore_rule_for_external_directory(self) -> None:
        with temp_directory() as directory:
            root = init_repo(Path(directory) / "repo")
            path = root / "unignored" / "child"
            with self.assertRaisesRegex(RuntimeError, "did not confirm"):
                self.module.ensure_ignored(root, path)

    def test_verify_ignored_returns_for_paths_outside_root(self) -> None:
        with temp_directory() as directory:
            root = init_repo(Path(directory) / "repo")
            self.module.verify_ignored(root, Path("/definitely/outside/path"))

    def test_main_dry_run_reports_plan(self) -> None:
        import io
        import json as json_module
        import sys as system
        from unittest.mock import patch

        with temp_directory() as directory:
            root = init_repo(Path(directory) / "repo")
            (root / "seed.txt").write_text("seed\n", encoding="utf-8")
            commit_all(root, "initial")
            argv = [
                "prepare_worktree.py",
                "my-branch",
                "--start-point",
                "main",
                "--dry-run",
            ]
            buffer = io.StringIO()
            cwd = os.getcwd()
            os.chdir(root)
            try:
                with (
                    patch.object(system, "argv", argv),
                    patch.object(system, "stdout", buffer),
                ):
                    rc = self.module.main()
            finally:
                os.chdir(cwd)
            self.assertEqual(0, rc)
            data = json_module.loads(buffer.getvalue())
            self.assertFalse(data["created"])
            self.assertEqual("my-branch", data["branch"])

    def test_main_rejects_invalid_branch_name(self) -> None:
        import io
        import sys as system
        from unittest.mock import patch

        with temp_directory() as directory:
            root = init_repo(Path(directory) / "repo")
            (root / "seed.txt").write_text("seed\n", encoding="utf-8")
            commit_all(root, "initial")
            argv = [
                "prepare_worktree.py",
                "invalid..branch",
                "--start-point",
                "main",
                "--dry-run",
            ]
            buffer = io.StringIO()
            cwd = os.getcwd()
            os.chdir(root)
            try:
                with (
                    patch.object(system, "argv", argv),
                    patch.object(system, "stderr", buffer),
                ):
                    rc = self.module.main()
            finally:
                os.chdir(cwd)
            self.assertEqual(1, rc)

    def test_main_requires_path_and_path_root_together(self) -> None:
        import io
        import sys as system
        from unittest.mock import patch

        with temp_directory() as directory:
            root = init_repo(Path(directory) / "repo")
            (root / "seed.txt").write_text("seed\n", encoding="utf-8")
            commit_all(root, "initial")
            argv = [
                "prepare_worktree.py",
                "my-branch",
                "--start-point",
                "main",
                "--path",
                "wt/exact",
                "--dry-run",
            ]
            buffer = io.StringIO()
            cwd = os.getcwd()
            os.chdir(root)
            try:
                with (
                    patch.object(system, "argv", argv),
                    patch.object(system, "stderr", buffer),
                ):
                    rc = self.module.main()
            finally:
                os.chdir(cwd)
            self.assertEqual(1, rc)
            self.assertIn("--path-root", buffer.getvalue())

    def test_main_creates_worktree(self) -> None:
        import json as json_module
        import sys as system
        from unittest.mock import patch

        with temp_directory() as directory:
            root = init_repo(Path(directory) / "repo")
            (root / "seed.txt").write_text("seed\n", encoding="utf-8")
            commit_all(root, "initial")
            target = root / ".worktrees" / "exact"
            argv = [
                "prepare_worktree.py",
                "my-branch",
                "--start-point",
                "main",
                "--path",
                str(target),
                "--path-root",
                str(root),
            ]
            buffer_path = Path(directory) / "out.json"
            cwd = os.getcwd()
            os.chdir(root)
            try:
                from contextlib import redirect_stdout

                with (
                    open(buffer_path, "w", encoding="utf-8") as handle,
                    redirect_stdout(handle),
                    patch.object(system, "argv", argv),
                ):
                    rc = self.module.main()
            finally:
                os.chdir(cwd)
            self.assertEqual(0, rc)
            data = json_module.loads(buffer_path.read_text(encoding="utf-8"))
            self.assertTrue(data["created"])
            self.assertTrue(Path(data["path"]).exists())
            self.assertIn("my-branch", data["branch"])


if __name__ == "__main__":
    unittest.main()
