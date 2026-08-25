"""Behavior tests for change-review scope hardening."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import tracemalloc
import unittest
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
RESOLVER = ROOT / "skills/change-review/scripts/resolve_scope.py"


def git(cwd: Path, *arguments: str) -> str:
    """Run Git in an isolated test repository."""
    result = subprocess.run(
        ["git", *arguments],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def initialize_repository(path: Path) -> None:
    """Create a minimal repository with one tracked file."""
    path.mkdir(parents=True)
    git(path, "init", "--quiet")
    git(path, "config", "user.name", "Athena Tests")
    git(path, "config", "user.email", "athena-tests@example.invalid")
    (path / "tracked.txt").write_text("base\n", encoding="utf-8")
    git(path, "add", "tracked.txt")
    git(path, "commit", "--quiet", "-m", "test: initialize")


def load_resolver(module_name: str) -> Any:
    """Load a fresh resolver module so tests can patch its OS boundary."""
    specification = importlib.util.spec_from_file_location(module_name, RESOLVER)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[module_name] = module
    specification.loader.exec_module(module)
    return module


class ChangeReviewScopeHardeningTests(unittest.TestCase):
    """Exercise safety boundaries without pinning implementation prose."""

    def test_scope_resolution_never_runs_configured_fsmonitor(self) -> None:
        """A repository monitor must not execute while resolving a scope."""
        for scope in ("worktree", "staged"):
            with self.subTest(scope=scope), tempfile.TemporaryDirectory() as temp:
                repository = Path(temp) / "repo"
                initialize_repository(repository)
                tracked = repository / "tracked.txt"
                tracked.write_text(f"{scope} change\n", encoding="utf-8")
                if scope == "staged":
                    git(repository, "add", tracked.name)

                sentinel = repository / f"{scope}-fsmonitor-ran"
                monitor = repository / "fsmonitor.py"
                monitor.write_text(
                    "#!/usr/bin/env python3\n"
                    "from pathlib import Path\n"
                    f"Path({str(sentinel)!r}).touch()\n",
                    encoding="utf-8",
                )
                monitor.chmod(0o755)
                git(repository, "config", "core.fsmonitor", str(monitor))

                result = subprocess.run(
                    [sys.executable, str(RESOLVER), f"--{scope}"],
                    cwd=repository,
                    capture_output=True,
                    text=True,
                    check=False,
                )

                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn(tracked.name, json.loads(result.stdout)["paths"])
                self.assertFalse(sentinel.exists())

    def test_worktree_scope_never_runs_configured_filter_commands(self) -> None:
        for filter_key in ("clean", "process"):
            with (
                self.subTest(filter_key=filter_key),
                tempfile.TemporaryDirectory() as temp,
            ):
                repository = Path(temp) / "repo"
                initialize_repository(repository)
                (repository / ".gitattributes").write_text(
                    "*.probe filter=probe\n", encoding="utf-8"
                )
                probe = repository / "tracked.probe"
                probe.write_text("base\n", encoding="utf-8")
                git(repository, "add", ".gitattributes", probe.name)
                git(repository, "commit", "--quiet", "-m", "test: configure filter")

                sentinel = repository / f"{filter_key}-ran"
                filter_script = repository / f"{filter_key}_filter.py"
                filter_program = (
                    "sys.stdout.buffer.write(sys.stdin.buffer.read())\n"
                    if filter_key == "clean"
                    else ""
                )
                filter_script.write_text(
                    "#!/usr/bin/env python3\n"
                    "from pathlib import Path\n"
                    "import sys\n"
                    f"Path({str(sentinel)!r}).touch()\n"
                    f"{filter_program}",
                    encoding="utf-8",
                )
                filter_script.chmod(0o755)
                git(
                    repository,
                    "config",
                    f"filter.probe.{filter_key}",
                    str(filter_script),
                )
                probe.write_text("changed\n", encoding="utf-8")

                result = subprocess.run(
                    [sys.executable, str(RESOLVER), "--worktree"],
                    cwd=repository,
                    capture_output=True,
                    text=True,
                    check=False,
                )

                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn(probe.name, json.loads(result.stdout)["paths"])
                self.assertFalse(sentinel.exists())

    def test_range_scope_ignores_replacement_refs(self) -> None:
        """An immutable range must use the named commit objects, not replacements."""
        with tempfile.TemporaryDirectory() as temp:
            repository = Path(temp) / "repo"
            initialize_repository(repository)
            base = git(repository, "rev-parse", "HEAD")
            changed = repository / "replacement.txt"
            changed.write_text("head-only\n", encoding="utf-8")
            git(repository, "add", changed.name)
            git(repository, "commit", "--quiet", "-m", "test: replacement target")
            head = git(repository, "rev-parse", "HEAD")
            git(repository, "replace", head, base)

            result = subprocess.run(
                [sys.executable, str(RESOLVER), "--range", f"{base}..{head}"],
                cwd=repository,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual([changed.name], json.loads(result.stdout)["paths"])

            worktree = subprocess.run(
                [sys.executable, str(RESOLVER), "--worktree"],
                cwd=repository,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(0, worktree.returncode, worktree.stderr)
            self.assertEqual([], json.loads(worktree.stdout)["paths"])

    def test_worktree_scope_preserves_trailing_whitespace_in_repository_root(
        self,
    ) -> None:
        """The resolver must not retarget a checkout whose name ends in whitespace."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sibling = root / "repo"
            initialize_repository(sibling)
            git(sibling, "commit", "--allow-empty", "--quiet", "-m", "test: diverge")
            for suffix in (" ", "\t", "\n"):
                with self.subTest(suffix=repr(suffix)):
                    repository = root / f"repo{suffix}"
                    initialize_repository(repository)
                    tracked = repository / "tracked.txt"
                    tracked.write_text("changed\n", encoding="utf-8")
                    expected_head = git(repository, "rev-parse", "HEAD")

                    result = subprocess.run(
                        [sys.executable, str(RESOLVER), "--worktree"],
                        cwd=repository,
                        capture_output=True,
                        text=True,
                        check=False,
                    )

                    self.assertEqual(0, result.returncode, result.stderr)
                    scope = json.loads(result.stdout)
                    self.assertEqual(expected_head, scope["head"])
                    self.assertEqual([tracked.name], scope["tracked_paths"])

    def test_worktree_scope_rejects_index_changes_missing_from_live_bytes(
        self,
    ) -> None:
        """A default review cannot silently omit a staged change it cannot inspect."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for operation in ("modify", "add", "delete"):
                with self.subTest(operation=operation):
                    repository = root / operation
                    initialize_repository(repository)
                    tracked = repository / "tracked.txt"
                    if operation == "modify":
                        tracked.write_text("staged\n", encoding="utf-8")
                        git(repository, "add", tracked.name)
                        tracked.write_text("base\n", encoding="utf-8")
                    elif operation == "add":
                        added = repository / "staged.txt"
                        added.write_text("staged\n", encoding="utf-8")
                        git(repository, "add", added.name)
                        added.unlink()
                    else:
                        git(
                            repository,
                            "update-index",
                            "--force-remove",
                            tracked.name,
                        )

                    result = subprocess.run(
                        [sys.executable, str(RESOLVER), "--worktree"],
                        cwd=repository,
                        capture_output=True,
                        text=True,
                        check=False,
                    )

                    self.assertEqual(1, result.returncode)

    def test_worktree_scope_reviews_intent_to_add_as_live_addition(self) -> None:
        """Intent-to-add records have no staged content to compare against live bytes."""
        with tempfile.TemporaryDirectory() as temp:
            repository = Path(temp) / "repo"
            initialize_repository(repository)
            pending = repository / "pending.py"
            pending.write_text("value = 1\n", encoding="utf-8")
            git(repository, "add", "--intent-to-add", pending.name)

            result = subprocess.run(
                [sys.executable, str(RESOLVER), "--worktree"],
                cwd=repository,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            scope = json.loads(result.stdout)
            self.assertEqual([pending.name], scope["paths"])
            self.assertEqual([pending.name], scope["tracked_paths"])
            self.assertEqual([], scope["untracked_paths"])
            self.assertEqual(
                [{"kind": "file", "mode": "0644", "path": pending.name}],
                scope["path_entries"],
            )

    @unittest.skipUnless(
        hasattr(os, "O_NONBLOCK") and hasattr(os, "O_NOFOLLOW"),
        "requires no-follow regular-file inspection support",
    )
    def test_worktree_scope_uses_descriptor_mode_after_metadata_race(self) -> None:
        """An executable-bit change cannot be omitted after a stale pre-open stat."""
        module_name = "test_change_review_verified_descriptor_mode"
        module = load_resolver(module_name)
        try:
            with tempfile.TemporaryDirectory() as temp:
                repository = Path(temp) / "repo"
                initialize_repository(repository)
                tracked = repository / "tracked.txt"
                tracked.chmod(0o755)
                head = git(repository, "rev-parse", "HEAD")
                original_entry = module.worktree_path_entry

                def stale_entry(repository_root: Path, relative_path: str) -> Any:
                    if relative_path == tracked.name:
                        return module.PathEntry(relative_path, "file", mode="0644")
                    return original_entry(repository_root, relative_path)

                with patch.object(
                    module, "worktree_path_entry", side_effect=stale_entry
                ):
                    capture = module.worktree_tracked_capture(head, (), repository)

                self.assertEqual((tracked.name,), capture.paths)
        finally:
            sys.modules.pop(module_name, None)

    def test_worktree_scope_reviews_smudged_bytes_as_raw_changes(self) -> None:
        """A clean-filter-equivalent byte stream remains reviewable raw source."""
        with tempfile.TemporaryDirectory() as temp:
            repository = Path(temp) / "repo"
            initialize_repository(repository)
            (repository / ".gitattributes").write_text(
                "*.probe filter=probe\n", encoding="utf-8"
            )
            probe = repository / "smudged.probe"
            probe.write_text("canonical\n", encoding="utf-8")
            git(repository, "add", ".gitattributes", probe.name)
            git(repository, "commit", "--quiet", "-m", "test: add filter source")

            sentinel = repository / "clean-filter-ran"
            filter_script = repository / "clean_filter.py"
            filter_script.write_text(
                "#!/usr/bin/env python3\n"
                "from pathlib import Path\n"
                "import sys\n"
                f"Path({str(sentinel)!r}).touch()\n"
                "sys.stdout.write('canonical\\n')\n",
                encoding="utf-8",
            )
            filter_script.chmod(0o755)
            git(repository, "config", "filter.probe.clean", str(filter_script))
            probe.write_text("smudged\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(RESOLVER), "--worktree"],
                cwd=repository,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn(probe.name, json.loads(result.stdout)["paths"])
            self.assertFalse(sentinel.exists())

    def test_worktree_scope_omits_absent_skip_worktree_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repository = Path(temp) / "repo"
            initialize_repository(repository)
            sparse = repository / "sparse-only.txt"
            sparse.write_text("sparse\n", encoding="utf-8")
            git(repository, "add", sparse.name)
            git(repository, "commit", "--quiet", "-m", "test: add sparse path")
            git(repository, "update-index", "--skip-worktree", sparse.name)
            sparse.unlink()

            result = subprocess.run(
                [sys.executable, str(RESOLVER), "--worktree"],
                cwd=repository,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertNotIn(sparse.name, json.loads(result.stdout)["paths"])

    def test_worktree_scope_rejects_unverifiable_submodule_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repository = Path(temp) / "repo"
            initialize_repository(repository)
            submodule_path = "vendor/module"
            gitlink = "a" * 40
            git(
                repository,
                "update-index",
                "--add",
                "--cacheinfo",
                f"160000,{gitlink},{submodule_path}",
            )
            git(repository, "commit", "--quiet", "-m", "test: add gitlink")
            (repository / submodule_path).mkdir(parents=True)

            result = subprocess.run(
                [sys.executable, str(RESOLVER), "--worktree"],
                cwd=repository,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(1, result.returncode)
            self.assertIn(submodule_path, result.stderr)
            self.assertIn("submodule", result.stderr)

    def test_worktree_scope_rejects_head_move_after_stable_captures(self) -> None:
        """Equal captures cannot validate a worktree whose HEAD moved between them."""
        module_name = "test_change_review_head_rebind"
        module = load_resolver(module_name)
        original_cwd = Path.cwd()
        try:
            with tempfile.TemporaryDirectory() as temp:
                repository = Path(temp) / "repo"
                initialize_repository(repository)
                original_head = git(repository, "rev-parse", "HEAD")
                git(
                    repository,
                    "commit",
                    "--allow-empty",
                    "--quiet",
                    "-m",
                    "test: move head",
                )

                original_capture = module.capture_scope
                captures = 0

                def capture_then_move_head(*arguments: object) -> object:
                    nonlocal captures
                    capture = original_capture(*arguments)
                    captures += 1
                    if captures == 1:
                        git(repository, "checkout", "--quiet", original_head)
                    return capture

                os.chdir(repository)
                with (
                    patch.object(
                        module, "capture_scope", side_effect=capture_then_move_head
                    ),
                    self.assertRaisesRegex(
                RuntimeError, "HEAD changed during resolution"
                    ),
                ):
                    module.resolve_scope("worktree", None, ())
                self.assertEqual(2, captures)
        finally:
            os.chdir(original_cwd)
            sys.modules.pop(module_name, None)

    def test_worktree_scope_fails_closed_at_the_candidate_cap(self) -> None:
        module_name = "test_change_review_candidate_cap"
        module = load_resolver(module_name)
        try:
            self.assertTrue(hasattr(module, "MAX_WORKTREE_CANDIDATES"))
            with tempfile.TemporaryDirectory() as temp:
                repository = Path(temp) / "repo"
                initialize_repository(repository)
                (repository / "second.txt").write_text("second\n", encoding="utf-8")
                git(repository, "add", "second.txt")
                git(repository, "commit", "--quiet", "-m", "test: add second path")
                head = git(repository, "rev-parse", "HEAD")

                with (
                    patch.object(module, "MAX_WORKTREE_CANDIDATES", 1),
                    self.assertRaisesRegex(RuntimeError, "candidate limit"),
                ):
                    module.worktree_tracked_capture(head, (), repository)
        finally:
            sys.modules.pop(module_name, None)

    def test_untracked_path_list_fails_closed_at_the_candidate_cap(self) -> None:
        module_name = "test_change_review_untracked_candidate_cap"
        module = load_resolver(module_name)
        try:
            with tempfile.TemporaryDirectory() as temp:
                repository = Path(temp) / "repo"
                initialize_repository(repository)
                (repository / "first-untracked.txt").write_text(
                    "first\n", encoding="utf-8"
                )
                (repository / "second-untracked.txt").write_text(
                    "second\n", encoding="utf-8"
                )

                with (
                    patch.object(module, "MAX_WORKTREE_CANDIDATES", 1),
                    self.assertRaisesRegex(RuntimeError, "untracked path limit"),
                ):
                    module.untracked_paths((), repository)
        finally:
            sys.modules.pop(module_name, None)

    @unittest.skipUnless(
        hasattr(os, "mkfifo")
        and hasattr(os, "O_NONBLOCK")
        and hasattr(os, "O_NOFOLLOW"),
        "requires POSIX FIFO and no-follow support",
    )
    def test_untracked_fifo_is_opened_nonblocking_and_rejected(self) -> None:
        module_name = "test_change_review_fifo_hardening"
        module = load_resolver(module_name)
        try:
            with tempfile.TemporaryDirectory() as temp:
                repository = Path(temp) / "repo"
                initialize_repository(repository)
                fifo = repository / "race"
                os.mkfifo(fifo)
                original_open = module.os.open

                def guarded_open(
                    path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
                    flags: int,
                    mode: int = 0o777,
                    *,
                    dir_fd: int | None = None,
                ) -> int:
                    if os.fspath(path) == "race":
                        self.assertNotEqual(0, flags & os.O_NONBLOCK)
                    if dir_fd is None:
                        return cast(int, original_open(path, flags, mode))
                    return cast(int, original_open(path, flags, mode, dir_fd=dir_fd))

                with (
                    patch.object(module.os, "open", side_effect=guarded_open),
                    self.assertRaisesRegex(RuntimeError, "not a regular file"),
                ):
                    module.read_regular_file_without_following(repository, "race")
        finally:
            sys.modules.pop(module_name, None)

    @unittest.skipUnless(
        hasattr(os, "O_DIRECTORY") and hasattr(os, "O_NOFOLLOW"),
        "requires POSIX directory no-follow support",
    )
    def test_nofollow_parent_closes_root_descriptor_when_dir_fd_fails(self) -> None:
        module_name = "test_change_review_descriptor_hardening"
        module = load_resolver(module_name)
        root_descriptor: int | None = None
        closed_descriptors: list[int] = []
        try:
            with tempfile.TemporaryDirectory() as temp:
                repository = Path(temp) / "repo"
                initialize_repository(repository)
                (repository / "nested").mkdir()
                original_open = module.os.open
                original_close = module.os.close

                def unsupported_child_open(
                    path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
                    flags: int,
                    mode: int = 0o777,
                    *,
                    dir_fd: int | None = None,
                ) -> int:
                    nonlocal root_descriptor
                    if dir_fd is not None:
                        raise NotImplementedError("dir_fd unsupported")
                    descriptor = original_open(path, flags, mode)
                    root_descriptor = descriptor
                    return cast(int, descriptor)

                def recording_close(descriptor: int) -> None:
                    closed_descriptors.append(descriptor)
                    original_close(descriptor)

                with (
                    patch.object(module.os, "open", side_effect=unsupported_child_open),
                    patch.object(module.os, "close", side_effect=recording_close),
                    self.assertRaisesRegex(RuntimeError, "without following links"),
                ):
                    module.nofollow_parent_descriptor(repository, "nested/file.txt")

                self.assertIsNotNone(root_descriptor)
                assert root_descriptor is not None
                self.assertIn(root_descriptor, closed_descriptors)
        finally:
            if (
                root_descriptor is not None
                and root_descriptor not in closed_descriptors
            ):
                os.close(root_descriptor)
            sys.modules.pop(module_name, None)

    @unittest.skipUnless(
        hasattr(os, "O_DIRECTORY") and hasattr(os, "O_NOFOLLOW"),
        "requires POSIX directory no-follow support",
    )
    def test_nofollow_parent_closes_child_when_parent_close_fails(self) -> None:
        module_name = "test_change_review_descriptor_transaction"
        module = load_resolver(module_name)
        root_descriptor: int | None = None
        child_descriptor: int | None = None
        closed_descriptors: list[int] = []
        try:
            with tempfile.TemporaryDirectory() as temp:
                repository = Path(temp) / "repo"
                initialize_repository(repository)
                (repository / "nested").mkdir()
                original_open = module.os.open
                original_close = module.os.close
                fail_parent_close = True

                def recording_open(
                    path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
                    flags: int,
                    mode: int = 0o777,
                    *,
                    dir_fd: int | None = None,
                ) -> int:
                    nonlocal root_descriptor, child_descriptor
                    if dir_fd is None:
                        descriptor = original_open(path, flags, mode)
                        root_descriptor = descriptor
                        return cast(int, descriptor)
                    descriptor = original_open(path, flags, mode, dir_fd=dir_fd)
                    child_descriptor = descriptor
                    return cast(int, descriptor)

                def fail_once_when_closing_parent(descriptor: int) -> None:
                    nonlocal fail_parent_close
                    if descriptor == root_descriptor and fail_parent_close:
                        fail_parent_close = False
                        raise OSError("simulated parent close failure")
                    closed_descriptors.append(descriptor)
                    original_close(descriptor)

                with (
                    patch.object(module.os, "open", side_effect=recording_open),
                    patch.object(
                        module.os, "close", side_effect=fail_once_when_closing_parent
                    ),
                    self.assertRaisesRegex(OSError, "parent close failure"),
                ):
                    module.nofollow_parent_descriptor(repository, "nested/file.txt")

                self.assertIsNotNone(child_descriptor)
                assert child_descriptor is not None
                self.assertIn(child_descriptor, closed_descriptors)
        finally:
            for descriptor in (child_descriptor, root_descriptor):
                if descriptor is not None and descriptor not in closed_descriptors:
                    os.close(descriptor)
            sys.modules.pop(module_name, None)

    @unittest.skipUnless(
        hasattr(os, "O_DIRECTORY") and hasattr(os, "O_NOFOLLOW"),
        "requires POSIX directory no-follow support",
    )
    def test_regular_file_handoff_closes_child_when_parent_close_fails(self) -> None:
        module_name = "test_change_review_file_handoff_transaction"
        module = load_resolver(module_name)
        parent_descriptor: int | None = None
        child_descriptor: int | None = None
        closed_descriptors: list[int] = []
        try:
            with tempfile.TemporaryDirectory() as temp:
                repository = Path(temp) / "repo"
                initialize_repository(repository)
                original_open = module.os.open
                original_close = module.os.close
                fail_parent_close = True

                def recording_open(
                    path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
                    flags: int,
                    mode: int = 0o777,
                    *,
                    dir_fd: int | None = None,
                ) -> int:
                    nonlocal parent_descriptor, child_descriptor
                    if dir_fd is None:
                        descriptor = original_open(path, flags, mode)
                        parent_descriptor = descriptor
                        return cast(int, descriptor)
                    descriptor = original_open(path, flags, mode, dir_fd=dir_fd)
                    child_descriptor = descriptor
                    return cast(int, descriptor)

                def fail_once_when_closing_parent(descriptor: int) -> None:
                    nonlocal fail_parent_close
                    if descriptor == parent_descriptor and fail_parent_close:
                        fail_parent_close = False
                        raise OSError("simulated parent close failure")
                    closed_descriptors.append(descriptor)
                    original_close(descriptor)

                with (
                    patch.object(module.os, "open", side_effect=recording_open),
                    patch.object(
                        module.os, "close", side_effect=fail_once_when_closing_parent
                    ),
                    self.assertRaisesRegex(OSError, "parent close failure"),
                ):
                    module.read_regular_file_without_following(
                        repository, "tracked.txt"
                    )

                self.assertIsNotNone(child_descriptor)
                assert child_descriptor is not None
                self.assertIn(child_descriptor, closed_descriptors)
        finally:
            for descriptor in (child_descriptor, parent_descriptor):
                if descriptor is not None and descriptor not in closed_descriptors:
                    os.close(descriptor)
            sys.modules.pop(module_name, None)

    def test_metadata_record_limit_applies_to_terminated_records(self) -> None:
        module_name = "test_change_review_metadata_record_limit"
        module = load_resolver(module_name)
        try:

            class FakeProcess:
                def __init__(self) -> None:
                    self.stdout = io.BytesIO(
                        b"x" * (module.MAX_METADATA_RECORD_BYTES + 1) + b"\0"
                    )

                def poll(self) -> int:
                    return 0

                def wait(self) -> int:
                    return 0

                def kill(self) -> None:
                    self.stdout.close()

            with (
                patch.object(module.subprocess, "Popen", return_value=FakeProcess()),
                self.assertRaisesRegex(RuntimeError, "metadata record exceeds"),
            ):
                module.consume_git_nul_records(
                    ("ls-files", "-z"), Path("/temporary/repository"), lambda _: None
                )
        finally:
            sys.modules.pop(module_name, None)

    def test_content_helpers_return_bounded_fingerprints(self) -> None:
        module_name = "test_change_review_fingerprint_hardening"
        module = load_resolver(module_name)
        try:
            with tempfile.TemporaryDirectory() as temp:
                repository = Path(temp) / "repo"
                initialize_repository(repository)
                untracked = repository / "untracked.bin"
                contents = b"first\x00payload\n" * (512 * 1024)
                untracked.write_bytes(contents)

                expected_length = len(contents)
                expected_digest = module.sha256(contents).hexdigest()
                del contents
                tracemalloc.start()
                try:
                    kind, fingerprint = module.untracked_content(
                        repository, untracked.name
                    )
                    _, peak_memory = tracemalloc.get_traced_memory()
                finally:
                    tracemalloc.stop()
                fingerprint_type = getattr(module, "ContentFingerprint", ())

                self.assertEqual(b"file", kind)
                self.assertIsInstance(fingerprint, fingerprint_type)
                self.assertEqual(expected_length, fingerprint.length)
                self.assertEqual(expected_digest, fingerprint.digest)
                self.assertLess(peak_memory, 4 * 1024 * 1024)
        finally:
            sys.modules.pop(module_name, None)

    def test_tracked_diff_returns_a_content_fingerprint(self) -> None:
        module_name = "test_change_review_tracked_fingerprint_hardening"
        module = load_resolver(module_name)
        try:
            with tempfile.TemporaryDirectory() as temp:
                repository = Path(temp) / "repo"
                initialize_repository(repository)
                base = git(repository, "rev-parse", "HEAD")
                tracked = repository / "tracked.txt"
                contents = b"changed\n" * (768 * 1024)
                tracked.write_bytes(contents)
                git(repository, "commit", "--quiet", "-am", "test: change tracked")
                head = git(repository, "rev-parse", "HEAD")

                del contents
                tracemalloc.start()
                try:
                    fingerprint = module.tracked_diff(
                        "range", base, head, (), repository
                    )
                    _, peak_memory = tracemalloc.get_traced_memory()
                finally:
                    tracemalloc.stop()
                fingerprint_type = getattr(module, "ContentFingerprint", ())

                self.assertIsInstance(fingerprint, fingerprint_type)
                self.assertGreater(fingerprint.length, 0)
                self.assertEqual(64, len(fingerprint.digest))
                self.assertLess(peak_memory, 4 * 1024 * 1024)
        finally:
            sys.modules.pop(module_name, None)
