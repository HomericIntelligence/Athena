"""Behavior tests for immutable PR-review evidence binding."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Callable, Sequence
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "pr-review" / "scripts" / "collect_evidence.py"
SNAPSHOT_SCRIPT = ROOT / "skills" / "pr-review" / "scripts" / "materialize_snapshot.py"
DIFF_CONTEXT_SCRIPT = ROOT / "skills" / "pr-review" / "scripts" / "diff_context.py"
BASE_OID = "a" * 40
HEAD_OID = "b" * 40


def pull_request(
    *,
    state: str = "OPEN",
    base_oid: str = BASE_OID,
    head_oid: str = HEAD_OID,
    base_ref_name: str = "main",
    head_ref_name: str = "feature",
    title: str = "Immutable evidence",
    body: str | None = "",
    is_draft: bool = False,
    closing_issues: list[dict[str, object]] | None = None,
    url: str = "https://github.com/owner/repository/pull/9",
) -> dict[str, object]:
    """Create the minimum complete GitHub pull-request evidence object."""
    return {
        "number": 9,
        "title": title,
        "body": body,
        "state": state,
        "isDraft": is_draft,
        "author": {"login": "reviewer"},
        "baseRefName": base_ref_name,
        "headRefName": head_ref_name,
        "baseRefOid": base_oid,
        "headRefOid": head_oid,
        "statusCheckRollup": [],
        "closingIssuesReferences": closing_issues or [],
        "url": url,
    }


def linked_requirement_fixture(
    number: int = 10, issue_id: str = "I_1"
) -> tuple[dict[str, object], dict[str, object]]:
    """Create one canonical linked issue and its corresponding requirement."""
    return (
        {
            "id": issue_id,
            "number": number,
            "repository": {"name": "requirements", "owner": {"login": "owner"}},
            "url": f"https://github.com/owner/requirements/issues/{number}",
        },
        {
            "id": issue_id,
            "number": number,
            "url": f"https://github.com/owner/requirements/issues/{number}",
            "title": "Requirements",
            "body": "Acceptance criterion",
            "state": "OPEN",
        },
    )


def git(repository: Path, *arguments: str) -> str:
    """Run a deterministic Git setup command for a temporary repository."""
    result = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return result.stdout.strip()


def initialize_repository(repository: Path, changed_path: str) -> tuple[str, str]:
    """Create a base/head pair with exactly one changed path."""
    git(repository, "init", "--quiet")
    git(repository, "config", "user.name", "Athena Tests")
    git(repository, "config", "user.email", "athena-tests@example.invalid")
    (repository / "tracked.txt").write_text("base\n", encoding="utf-8")
    git(repository, "add", "tracked.txt")
    git(repository, "commit", "--quiet", "-m", "test: base")
    base_oid = git(repository, "rev-parse", "HEAD")
    (repository / changed_path).write_text("changed\n", encoding="utf-8")
    git(repository, "add", "--all")
    git(repository, "commit", "--quiet", "-m", "test: changed path")
    return base_oid, git(repository, "rev-parse", "HEAD")


def initialize_divergent_repository(
    repository: Path, changed_path: str
) -> tuple[str, str]:
    """Create equal base/head trees with a path changed in author intent only."""
    git(repository, "init", "--quiet")
    git(repository, "config", "user.name", "Athena Tests")
    git(repository, "config", "user.email", "athena-tests@example.invalid")
    (repository / changed_path).write_text("base\n", encoding="utf-8")
    git(repository, "add", changed_path)
    git(repository, "commit", "--quiet", "-m", "test: merge base")
    merge_base = git(repository, "rev-parse", "HEAD")
    git(repository, "branch", "-M", "main")
    git(repository, "checkout", "--quiet", "-b", "feature")
    (repository / changed_path).write_text("changed\n", encoding="utf-8")
    git(repository, "commit", "--all", "--quiet", "-m", "test: feature change")
    head_oid = git(repository, "rev-parse", "HEAD")
    git(repository, "checkout", "--quiet", "main")
    (repository / changed_path).write_text("changed\n", encoding="utf-8")
    git(repository, "commit", "--all", "--quiet", "-m", "test: target change")
    base_oid = git(repository, "rev-parse", "HEAD")
    if git(repository, "merge-base", base_oid, head_oid) != merge_base:
        raise AssertionError("divergent test repository lost its merge base")
    return base_oid, head_oid


def initialize_shallow_repository(
    repository: Path, changed_path: str
) -> tuple[str, str]:
    """Create a shallow clone that still contains the requested base and head."""
    with tempfile.TemporaryDirectory() as source_directory:
        source = Path(source_directory)
        initialize_repository(source, changed_path)
        result = subprocess.run(
            [
                "git",
                "clone",
                "--quiet",
                "--no-local",
                "--depth",
                "2",
                str(source),
                str(repository),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr)
    return git(repository, "rev-parse", "HEAD~1"), git(repository, "rev-parse", "HEAD")


def initialize_ambiguous_merge_base_repository(
    repository: Path, changed_path: str
) -> tuple[str, str]:
    """Create a criss-cross DAG with two equally valid merge bases."""
    git(repository, "init", "--quiet")
    git(repository, "config", "user.name", "Athena Tests")
    git(repository, "config", "user.email", "athena-tests@example.invalid")
    (repository / changed_path).write_text("initial\n", encoding="utf-8")
    git(repository, "add", changed_path)
    git(repository, "commit", "--quiet", "-m", "test: common ancestor")
    common = git(repository, "rev-parse", "HEAD")
    git(repository, "checkout", "--quiet", "-b", "feature")
    (repository / changed_path).write_text("feature\n", encoding="utf-8")
    git(repository, "commit", "--all", "--quiet", "-m", "test: feature parent")
    feature_parent = git(repository, "rev-parse", "HEAD")
    feature_tree = git(repository, "rev-parse", f"{feature_parent}^{{tree}}")
    git(repository, "checkout", "--quiet", "--detach", common)
    (repository / changed_path).write_text("target\n", encoding="utf-8")
    git(repository, "commit", "--all", "--quiet", "-m", "test: target parent")
    target_parent = git(repository, "rev-parse", "HEAD")
    target_tree = git(repository, "rev-parse", f"{target_parent}^{{tree}}")
    head_oid = git(
        repository,
        "commit-tree",
        feature_tree,
        "-p",
        feature_parent,
        "-p",
        target_parent,
        "-m",
        "test: feature merge",
    )
    base_oid = git(
        repository,
        "commit-tree",
        target_tree,
        "-p",
        target_parent,
        "-p",
        feature_parent,
        "-m",
        "test: target merge",
    )
    if set(git(repository, "merge-base", "--all", base_oid, head_oid).splitlines()) != {
        feature_parent,
        target_parent,
    }:
        raise AssertionError("test repository did not create two merge bases")
    return base_oid, head_oid


def load_collector(module_name: str) -> Any:
    """Load a fresh collector module for direct process-boundary behavior tests."""
    specification = importlib.util.spec_from_file_location(module_name, SCRIPT)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[module_name] = module
    script_directory = str(SCRIPT.parent)
    sys.path.insert(0, script_directory)
    try:
        specification.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    finally:
        sys.path.remove(script_directory)
    return module


def load_snapshot(module_name: str) -> Any:
    """Load a fresh snapshot materializer for isolated Git behavior tests."""
    specification = importlib.util.spec_from_file_location(module_name, SNAPSHOT_SCRIPT)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[module_name] = module
    script_directory = str(SNAPSHOT_SCRIPT.parent)
    sys.path.insert(0, script_directory)
    try:
        specification.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    finally:
        sys.path.remove(script_directory)
    return module


def linux_bounded_quota_available() -> bool:
    """Return whether this host enforces a bounded unprivileged tmpfs quota.

    Probes the actual unshare + tmpfs mount boundary once (not just binary
    presence) so restricted user-namespace hosts degrade to a skip instead of
    failing the end-to-end materialization test.
    """
    if not (
        sys.platform.startswith("linux")
        and shutil.which("unshare") is not None
        and shutil.which("mount") is not None
        and shutil.which("umount") is not None
    ):
        return False
    probe = subprocess.run(
        [
            "unshare",
            "-rm",
            "--",
            "sh",
            "-c",
            (
                "mkdir -p /tmp/athena-bounded-quota-probe && "
                "mount -t tmpfs -o size=64k tmpfs /tmp/athena-bounded-quota-probe && "
                "umount /tmp/athena-bounded-quota-probe"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return probe.returncode == 0


LINUX_BOUNDED_QUOTA_AVAILABLE = linux_bounded_quota_available()


class SnapshotMaterializationTests(unittest.TestCase):
    """Verify exact PR source can be acquired without trusting the caller."""

    def setUp(self) -> None:
        self.module_name = f"test_materialize_snapshot_{id(self)}"
        self.snapshot = load_snapshot(self.module_name)

    def tearDown(self) -> None:
        sys.modules.pop(self.module_name, None)

    def test_materializes_a_missing_head_from_only_the_canonical_pr_refs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            source.mkdir()
            base_oid, head_oid = initialize_divergent_repository(source, "changed.txt")
            git(source, "update-ref", "refs/pull/9/head", head_oid)
            remote = root / "remote.git"
            git(root, "init", "--bare", "--quiet", str(remote))
            git(source, "remote", "add", "origin", str(remote))
            git(source, "push", "--quiet", "origin", "main", "refs/pull/9/head")

            caller = root / "caller"
            caller.mkdir()
            git(caller, "init", "--quiet")
            git(
                caller,
                "fetch",
                "--quiet",
                str(remote),
                "refs/heads/main:refs/heads/main",
            )
            self.assertNotEqual(
                0,
                subprocess.run(
                    ["git", "cat-file", "-e", f"{head_oid}^{{commit}}"],
                    cwd=caller,
                    capture_output=True,
                    check=False,
                ).returncode,
            )

            with (
                patch.object(
                    self.snapshot, "canonical_repository_url", return_value=str(remote)
                ),
                patch.object(
                    self.snapshot,
                    "_create_quota_volume",
                    side_effect=lambda temporary_root, _: temporary_root / "source",
                ),
            ):
                materialized = self.snapshot.materialize_snapshot(
                    repository="owner/repository",
                    number=9,
                    base_ref="main",
                    base_oid=base_oid,
                    head_oid=head_oid,
                )
            self.addCleanup(self.snapshot.remove_snapshot, materialized.root)

            self.assertEqual(
                head_oid, git(materialized.source_path, "rev-parse", "HEAD")
            )
            self.assertEqual(
                base_oid,
                git(materialized.source_path, "rev-parse", "refs/athena/base"),
            )
            self.assertEqual(
                head_oid,
                git(materialized.source_path, "rev-parse", "refs/athena/pr/9/head"),
            )
            self.assertTrue((materialized.source_path / "changed.txt").is_file())
            self.assertNotEqual(
                0,
                subprocess.run(
                    ["git", "cat-file", "-e", f"{head_oid}^{{commit}}"],
                    cwd=caller,
                    capture_output=True,
                    check=False,
                ).returncode,
            )

    def test_rejects_a_fetched_pull_ref_that_does_not_match_the_captured_head(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            source.mkdir()
            base_oid, head_oid = initialize_repository(source, "changed.txt")
            git(source, "branch", "main", base_oid)
            git(source, "update-ref", "refs/pull/9/head", head_oid)
            remote = root / "remote.git"
            git(root, "init", "--bare", "--quiet", str(remote))
            git(source, "remote", "add", "origin", str(remote))
            git(source, "push", "--quiet", "origin", "main", "refs/pull/9/head")

            with (
                patch.object(
                    self.snapshot, "canonical_repository_url", return_value=str(remote)
                ),
                patch.object(
                    self.snapshot,
                    "_create_quota_volume",
                    side_effect=lambda temporary_root, _: temporary_root / "source",
                ),
                self.assertRaisesRegex(
                    RuntimeError, "fetched pull-request ref does not match"
                ),
            ):
                self.snapshot.materialize_snapshot(
                    repository="owner/repository",
                    number=9,
                    base_ref="main",
                    base_oid=base_oid,
                    head_oid="c" * 40,
                )

    def test_rejects_a_real_ambiguous_merge_base_from_canonical_refs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            source.mkdir()
            base_oid, head_oid = initialize_ambiguous_merge_base_repository(
                source, "changed.txt"
            )
            remote = root / "remote.git"
            git(root, "init", "--bare", "--quiet", str(remote))
            git(source, "remote", "add", "origin", str(remote))
            git(
                source,
                "push",
                "--quiet",
                "origin",
                f"{base_oid}:refs/heads/main",
                f"{head_oid}:refs/pull/9/head",
            )

            with (
                patch.object(
                    self.snapshot, "canonical_repository_url", return_value=str(remote)
                ),
                patch.object(
                    self.snapshot,
                    "_create_quota_volume",
                    side_effect=lambda temporary_root, _: temporary_root / "source",
                ),
                self.assertRaisesRegex(RuntimeError, "one unambiguous merge base"),
            ):
                self.snapshot.materialize_snapshot(
                    repository="owner/repository",
                    number=9,
                    base_ref="main",
                    base_oid=base_oid,
                    head_oid=head_oid,
                )

    def test_rejects_a_snapshot_larger_than_ninety_percent_of_free_space(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            snapshot_file = repository / "objects.pack"
            snapshot_file.write_bytes(b"x" * 90)

            with patch.object(
                self.snapshot.shutil,
                "disk_usage",
                return_value=SimpleNamespace(free=100),
            ):
                self.assertEqual(90, self.snapshot._repository_size(repository))
                snapshot_file.write_bytes(b"x" * 91)
                with self.assertRaisesRegex(RuntimeError, "safe size limit"):
                    self.snapshot._repository_size(repository)

    def test_does_not_rely_on_per_file_limits_for_snapshot_quota(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "snapshot"
            root.mkdir()
            calls: list[tuple[tuple[str, ...], dict[str, object]]] = []

            def git(*arguments: str, **kwargs: object) -> str:
                calls.append((arguments, kwargs))
                if arguments[0] == "init":
                    Path(arguments[-1]).mkdir()
                if arguments[:2] == ("rev-parse", "--is-shallow-repository"):
                    return "false"
                if arguments[:2] == ("rev-parse", "--verify"):
                    if arguments[-1] == "refs/athena/base^{commit}":
                        return "a" * 40
                    if arguments[-1] == "refs/athena/pr/9/head^{commit}":
                        return "b" * 40
                    if arguments[-1] == f"{'b' * 40}^{{commit}}":
                        return "b" * 40
                if arguments[0] == "merge-base":
                    return "a" * 40
                if arguments[:2] == ("rev-parse", f"{'b' * 40}^{{tree}}"):
                    return "c" * 40
                return ""

            with (
                patch.object(self.snapshot.tempfile, "mkdtemp", return_value=str(root)),
                patch.object(
                    self.snapshot, "_create_quota_volume", return_value=root / "source"
                ),
                patch.object(self.snapshot, "_git", side_effect=git),
                patch.object(self.snapshot, "_repository_size", return_value=0),
                patch.object(self.snapshot, "_verify_no_promisor_configuration"),
                patch.object(self.snapshot, "_make_read_only"),
                patch.object(
                    self.snapshot.shutil,
                    "disk_usage",
                    return_value=SimpleNamespace(free=100),
                ),
            ):
                self.snapshot.materialize_snapshot(
                    repository="owner/repository",
                    number=9,
                    base_ref="main",
                    base_oid="a" * 40,
                    head_oid="b" * 40,
                )

        fetch = next(kwargs for arguments, kwargs in calls if "fetch" in arguments)
        checkout = next(
            kwargs for arguments, kwargs in calls if "checkout" in arguments
        )
        self.assertIsNone(fetch.get("maximum_file_size"))
        self.assertIsNone(checkout.get("maximum_file_size"))
        self.assertEqual(root / "source", fetch.get("temporary_directory"))
        self.assertEqual(root / "source", checkout.get("temporary_directory"))

    def test_creates_a_sparse_volume_with_the_cumulative_snapshot_quota(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "snapshot"
            root.mkdir()
            calls: list[tuple[str, ...]] = []

            with (
                patch.object(
                    self.snapshot,
                    "_hdiutil",
                    side_effect=lambda *arguments: calls.append(arguments),
                ),
                patch.object(self.snapshot.sys, "platform", "darwin"),
                patch.object(Path, "is_mount", return_value=True),
            ):
                source = self.snapshot._create_quota_volume(root, 90 * 1024)

        self.assertEqual(root / "source", source)
        self.assertEqual(
            (
                "create",
                "-quiet",
                "-type",
                "SPARSE",
                "-size",
                "90k",
                "-fs",
                "Case-sensitive HFS+",
                "-volname",
                "Athena PR Review",
                "-nospotlight",
                str(root / "snapshot.sparseimage"),
            ),
            calls[0],
        )
        self.assertEqual(
            (
                "attach",
                "-quiet",
                "-nobrowse",
                "-mountpoint",
                str(root / "source"),
                str(root / "snapshot.sparseimage"),
            ),
            calls[1],
        )

    @unittest.skipUnless(
        sys.platform == "darwin"
        and shutil.which("dd") is not None
        and shutil.which("hdiutil") is not None,
        "requires the macOS sparse-image quota boundary",
    )
    def test_quota_volume_bounds_multiple_files_by_total_capacity(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="athena-pr-review-"))
        self.addCleanup(self.snapshot.remove_snapshot, root)
        maximum_bytes = 64 * 1024 * 1024
        try:
            source = self.snapshot._create_quota_volume(root, maximum_bytes)
        except RuntimeError as error:
            if str(error) != (
                "host cannot enforce the immutable pull-request snapshot size limit"
            ):
                raise
            self.skipTest(str(error))
        if source is None:
            self.skipTest("macOS sparse-image quota is unavailable")
        self.assertLessEqual(shutil.disk_usage(source).total, maximum_bytes)
        for name in ("one", "two"):
            result = subprocess.run(
                ["dd", "if=/dev/urandom", f"of={source / name}", "bs=1m", "count=24"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr)
        overflow = subprocess.run(
            ["dd", "if=/dev/urandom", f"of={source / 'three'}", "bs=1m", "count=24"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertNotEqual(0, overflow.returncode)
        self.assertLessEqual(
            sum(path.stat().st_size for path in source.iterdir()), maximum_bytes
        )

    def test_rejects_snapshot_acquisition_failure_modes(self) -> None:
        cases = {
            "ambiguous merge base": "ambiguous merge base",
            "promisor configuration": "partial clone configuration",
            "shallow history": "complete history",
            "timeout": "cannot materialize",
        }
        for scenario, expected_error in cases.items():
            with (
                self.subTest(scenario=scenario),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory) / "snapshot"
                root.mkdir()

                def git(
                    *arguments: str,
                    scenario: str = scenario,
                    **_: object,
                ) -> str:
                    if arguments[0] == "init":
                        Path(arguments[-1]).mkdir()
                    if "fetch" in arguments and scenario == "timeout":
                        raise subprocess.TimeoutExpired(arguments, 30)
                    if arguments[:2] == ("rev-parse", "--is-shallow-repository"):
                        return "true" if scenario == "shallow history" else "false"
                    if arguments[:2] == ("rev-parse", "--verify"):
                        if arguments[-1] == "refs/athena/base^{commit}":
                            return "a" * 40
                        if arguments[-1] == "refs/athena/pr/9/head^{commit}":
                            return "b" * 40
                        if arguments[-1] == f"{'b' * 40}^{{commit}}":
                            return "b" * 40
                    if arguments[:3] == ("config", "--local", "--get"):
                        return "origin" if scenario == "promisor configuration" else ""
                    if arguments[0] == "merge-base":
                        return (
                            "a\nb" if scenario == "ambiguous merge base" else "a" * 40
                        )
                    if arguments[:2] == ("rev-parse", f"{'b' * 40}^{{tree}}"):
                        return "c" * 40
                    return ""

                with (
                    patch.object(
                        self.snapshot.tempfile, "mkdtemp", return_value=str(root)
                    ),
                    patch.object(
                        self.snapshot,
                        "_create_quota_volume",
                        return_value=root / "source",
                    ),
                    patch.object(self.snapshot, "_git", side_effect=git),
                    patch.object(self.snapshot, "_repository_size", return_value=0),
                    patch.object(self.snapshot, "_make_read_only"),
                    patch.object(self.snapshot, "remove_snapshot"),
                    patch.object(
                        self.snapshot.shutil,
                        "disk_usage",
                        return_value=SimpleNamespace(free=100),
                    ),
                    self.assertRaisesRegex(RuntimeError, expected_error),
                ):
                    self.snapshot.materialize_snapshot(
                        repository="owner/repository",
                        number=9,
                        base_ref="main",
                        base_oid="a" * 40,
                        head_oid="b" * 40,
                    )

    def test_command_emits_a_materialized_snapshot(self) -> None:
        snapshot = self.snapshot.MaterializedSnapshot(
            root=Path("/tmp/athena-pr-review-test"),
            source_path=Path("/tmp/athena-pr-review-test/source"),
            merge_base="a" * 40,
            tree_oid="b" * 40,
        )
        output = io.StringIO()

        with (
            patch.object(self.snapshot, "materialize_snapshot", return_value=snapshot),
            patch("sys.stdout", output),
        ):
            exit_code = self.snapshot.main(
                (
                    "--repository",
                    "owner/repository",
                    "--pr-number",
                    "9",
                    "--base-ref",
                    "main",
                    "--base-oid",
                    "a" * 40,
                    "--head-oid",
                    "b" * 40,
                )
            )

        self.assertEqual(0, exit_code)
        self.assertEqual(snapshot.as_json(), json.loads(output.getvalue()))

    def test_command_reports_a_materialization_failure(self) -> None:
        errors = io.StringIO()

        with (
            patch.object(
                self.snapshot,
                "materialize_snapshot",
                side_effect=RuntimeError("snapshot failed"),
            ),
            patch("sys.stderr", errors),
        ):
            exit_code = self.snapshot.main(
                (
                    "--repository",
                    "owner/repository",
                    "--pr-number",
                    "9",
                    "--base-ref",
                    "main",
                    "--base-oid",
                    "a" * 40,
                    "--head-oid",
                    "b" * 40,
                )
            )

        self.assertEqual(1, exit_code)
        self.assertEqual("snapshot failed\n", errors.getvalue())

    def test_linux_quota_volume_mounts_a_bounded_tmpfs_when_privileged(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "snapshot"
            root.mkdir()
            calls: list[tuple[Path, int]] = []

            def mount(source_directory: Path, maximum_bytes: int) -> bool:
                source_directory.mkdir()
                calls.append((source_directory, maximum_bytes))
                return True

            with (
                patch.object(self.snapshot.sys, "platform", "linux"),
                patch.object(self.snapshot, "_mount_tmpfs", side_effect=mount),
            ):
                source = self.snapshot._create_quota_volume(root, 90 * 1024)

        self.assertEqual(root / "source", source)
        self.assertEqual([(root / "source", 90 * 1024)], calls)

    def test_linux_quota_volume_falls_back_when_the_tmpfs_mount_is_unavailable(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "snapshot"
            root.mkdir()
            with (
                patch.object(self.snapshot.sys, "platform", "linux"),
                patch.object(self.snapshot, "_mount_tmpfs", return_value=False),
            ):
                source = self.snapshot._create_quota_volume(root, 90 * 1024)

        self.assertIsNone(source)
        self.assertFalse((root / "source").exists())

    def test_mount_tmpfs_bounds_total_capacity_with_the_cumulative_quota(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "snapshot"
            root.mkdir()
            source = root / "source"
            calls: list[tuple[str, ...]] = []

            def mount(
                command: list[str], **_: object
            ) -> subprocess.CompletedProcess[str]:
                calls.append(tuple(command))
                return subprocess.CompletedProcess(command, 0)

            with (
                patch.object(self.snapshot.sys, "platform", "linux"),
                patch.object(
                    self.snapshot.shutil, "which", return_value="/usr/bin/mount"
                ),
                patch.object(self.snapshot, "run_command", side_effect=mount),
                patch.object(Path, "is_mount", return_value=True),
            ):
                mounted = self.snapshot._mount_tmpfs(source, 90 * 1024)

        self.assertTrue(mounted)
        self.assertEqual(
            (
                "mount",
                "-t",
                "tmpfs",
                "-o",
                "size=90k",
                "tmpfs",
                str(source),
            ),
            calls[0],
        )

    def test_mount_tmpfs_fails_closed_when_the_mount_does_not_take_effect(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "snapshot" / "source"
            with (
                patch.object(self.snapshot.sys, "platform", "linux"),
                patch.object(
                    self.snapshot.shutil, "which", return_value="/usr/bin/mount"
                ),
                patch.object(
                    self.snapshot,
                    "run_command",
                    return_value=subprocess.CompletedProcess([], 0),
                ),
                patch.object(Path, "is_mount", return_value=False),
            ):
                mounted = self.snapshot._mount_tmpfs(source, 90 * 1024)

        self.assertFalse(mounted)

    def test_mount_tmpfs_fails_closed_without_the_mount_command(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "source"
            with (
                patch.object(self.snapshot.sys, "platform", "linux"),
                patch.object(self.snapshot.shutil, "which", return_value=None),
            ):
                mounted = self.snapshot._mount_tmpfs(source, 90 * 1024)

        self.assertFalse(mounted)

    def test_bounded_materialize_spawns_unshare_with_the_captured_target(
        self,
    ) -> None:
        root = Path(tempfile.mkdtemp(prefix="athena-pr-review-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        (root / "source").mkdir()
        calls: list[tuple[str, ...]] = []

        def run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            calls.append(tuple(command))
            record = json.dumps(
                {
                    "source_path": str(root / "source"),
                    "merge_base": "a" * 40,
                    "tree_oid": "b" * 40,
                },
                sort_keys=True,
            )
            return subprocess.CompletedProcess(command, 0, stdout=record)

        with (
            patch.object(
                self.snapshot.shutil, "which", return_value="/usr/bin/unshare"
            ),
            patch.object(self.snapshot, "run_command", side_effect=run),
        ):
            snapshot = self.snapshot._bounded_materialize(
                root,
                90 * 1024,
                repository="owner/repository",
                number=9,
                base_ref="main",
                base_oid="a" * 40,
                head_oid="b" * 40,
            )

        self.assertEqual(str(root / "source"), str(snapshot.source_path))
        self.assertEqual("a" * 40, snapshot.merge_base)
        self.assertEqual("b" * 40, snapshot.tree_oid)
        self.assertEqual(("/usr/bin/unshare", "-rm", "--"), calls[0][:3])
        command = calls[0]
        self.assertIn("--bounded-materialize", command)
        self.assertIn("https://github.com/owner/repository.git", command)
        self.assertIn("--maximum-bytes", command)
        self.assertIn("92160", command)

    def test_bounded_materialize_fails_closed_without_unshare(self) -> None:
        with (
            patch.object(self.snapshot.shutil, "which", return_value=None),
            self.assertRaisesRegex(
                RuntimeError,
                "host cannot enforce the immutable pull-request snapshot size limit",
            ),
        ):
            self.snapshot._bounded_materialize(
                Path("/tmp/athena-pr-review-test"),
                90 * 1024,
                repository="owner/repository",
                number=9,
                base_ref="main",
                base_oid="a" * 40,
                head_oid="b" * 40,
            )

    def test_bounded_materialize_fails_closed_when_the_child_cannot_mount(
        self,
    ) -> None:
        with (
            patch.object(
                self.snapshot.shutil, "which", return_value="/usr/bin/unshare"
            ),
            patch.object(
                self.snapshot,
                "run_command",
                return_value=subprocess.CompletedProcess([], 2),
            ),
            self.assertRaisesRegex(
                RuntimeError,
                "host cannot enforce the immutable pull-request snapshot size limit",
            ),
        ):
            self.snapshot._bounded_materialize(
                Path("/tmp/athena-pr-review-test"),
                90 * 1024,
                repository="owner/repository",
                number=9,
                base_ref="main",
                base_oid="a" * 40,
                head_oid="b" * 40,
            )

    def test_bounded_materialize_rejects_a_noncanonical_child_record(
        self,
    ) -> None:
        with (
            patch.object(
                self.snapshot.shutil, "which", return_value="/usr/bin/unshare"
            ),
            patch.object(
                self.snapshot,
                "run_command",
                return_value=subprocess.CompletedProcess(
                    [], 0, stdout=json.dumps({"source_path": "/attacker/path"})
                ),
            ),
            self.assertRaisesRegex(RuntimeError, "cannot materialize"),
        ):
            self.snapshot._bounded_materialize(
                Path("/tmp/athena-pr-review-test"),
                90 * 1024,
                repository="owner/repository",
                number=9,
                base_ref="main",
                base_oid="a" * 40,
                head_oid="b" * 40,
            )

    def test_main_routes_the_internal_bounded_materialize_flag(self) -> None:
        received: list[tuple[str, ...]] = []

        def bounded_main(arguments: Sequence[str]) -> int:
            received.append(tuple(arguments))
            return 0

        with patch.object(self.snapshot, "_bounded_materialize_main", bounded_main):
            exit_code = self.snapshot.main(
                (
                    "--bounded-materialize",
                    "--root",
                    "/tmp/athena-pr-review-test",
                    "--repository-url",
                    "https://github.com/owner/repository.git",
                    "--pr-number",
                    "9",
                    "--base-ref",
                    "main",
                    "--base-oid",
                    "a" * 40,
                    "--head-oid",
                    "b" * 40,
                    "--maximum-bytes",
                    "90",
                )
            )

        self.assertEqual(0, exit_code)
        self.assertEqual(
            (
                "--root",
                "/tmp/athena-pr-review-test",
                "--repository-url",
                "https://github.com/owner/repository.git",
                "--pr-number",
                "9",
                "--base-ref",
                "main",
                "--base-oid",
                "a" * 40,
                "--head-oid",
                "b" * 40,
                "--maximum-bytes",
                "90",
            ),
            received[0],
        )

    @unittest.skipUnless(
        LINUX_BOUNDED_QUOTA_AVAILABLE,
        "requires a Linux bounded user/mount-namespace quota boundary",
    )
    def test_linux_bounded_materialization_without_a_privileged_mount(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            source.mkdir()
            base_oid, head_oid = initialize_divergent_repository(source, "changed.txt")
            git(source, "update-ref", "refs/pull/9/head", head_oid)
            remote = root / "remote.git"
            git(root, "init", "--bare", "--quiet", str(remote))
            git(source, "remote", "add", "origin", str(remote))
            git(source, "push", "--quiet", "origin", "main", "refs/pull/9/head")
            quota_consulted: list[bool] = []

            def unavailable_volume(*_: object) -> None:
                quota_consulted.append(True)

            with (
                patch.object(
                    self.snapshot,
                    "canonical_repository_url",
                    return_value=str(remote),
                ),
                patch.object(
                    self.snapshot,
                    "_create_quota_volume",
                    side_effect=unavailable_volume,
                ),
            ):
                materialized = self.snapshot.materialize_snapshot(
                    repository="owner/repository",
                    number=9,
                    base_ref="main",
                    base_oid=base_oid,
                    head_oid=head_oid,
                )
            self.addCleanup(self.snapshot.remove_snapshot, materialized.root)

            self.assertEqual([True], quota_consulted)
            self.assertEqual(
                head_oid, git(materialized.source_path, "rev-parse", "HEAD")
            )
            self.assertEqual(
                base_oid,
                git(materialized.source_path, "rev-parse", "refs/athena/base"),
            )
            self.assertEqual(
                head_oid,
                git(materialized.source_path, "rev-parse", "refs/athena/pr/9/head"),
            )
            self.assertTrue((materialized.source_path / "changed.txt").is_file())


class LinuxBoundedSnapshotBehaviorTests(unittest.TestCase):
    """Exercise Linux bounded-namespace quota paths without live mount privileges."""

    def setUp(self) -> None:
        self.module_name = f"test_linux_bounded_snapshot_{id(self)}"
        self.snapshot = load_snapshot(self.module_name)

    def tearDown(self) -> None:
        sys.modules.pop(self.module_name, None)

    def _bounded_main_arguments(self, root: Path) -> tuple[str, ...]:
        return (
            "--root",
            str(root),
            "--repository-url",
            "https://github.com/owner/repository.git",
            "--pr-number",
            "9",
            "--base-ref",
            "main",
            "--base-oid",
            "a" * 40,
            "--head-oid",
            "b" * 40,
            "--maximum-bytes",
            "90",
        )

    def test_bounded_materialize_main_emits_the_verified_record(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="athena-pr-review-")).resolve()
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        output = io.StringIO()

        def acquire(source: Path, **_: object) -> tuple[str, str]:
            (root / "bounded").mkdir(exist_ok=True)
            return ("a" * 40, "b" * 40)

        with (
            patch("sys.stdout", output),
            patch.object(self.snapshot, "_mount_tmpfs", return_value=True),
            patch.object(self.snapshot, "_acquire_into", side_effect=acquire),
            patch.object(self.snapshot.shutil, "copytree"),
            patch.object(self.snapshot, "_detach_best_effort"),
            patch.object(self.snapshot, "_make_read_only"),
        ):
            exit_code = self.snapshot._bounded_materialize_main(
                self._bounded_main_arguments(root)
            )

        self.assertEqual(0, exit_code)
        record = json.loads(output.getvalue())
        self.assertEqual("a" * 40, record["merge_base"])
        self.assertEqual("b" * 40, record["tree_oid"])
        self.assertEqual(str(root / "source"), record["source_path"])

    def test_bounded_materialize_main_refuses_paths_outside_the_managed_root(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "unmanaged"
            root.mkdir()
            errors = io.StringIO()
            with (
                patch("sys.stderr", errors),
                patch.object(self.snapshot, "_mount_tmpfs", return_value=True),
            ):
                exit_code = self.snapshot._bounded_materialize_main(
                    self._bounded_main_arguments(root)
                )

        self.assertEqual(1, exit_code)
        self.assertIn("outside the managed temporary directory", errors.getvalue())

    def test_bounded_materialize_main_fails_closed_when_the_mount_is_unavailable(
        self,
    ) -> None:
        root = Path(tempfile.mkdtemp(prefix="athena-pr-review-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        errors = io.StringIO()

        with (
            patch("sys.stderr", errors),
            patch.object(self.snapshot, "_mount_tmpfs", return_value=False),
        ):
            exit_code = self.snapshot._bounded_materialize_main(
                self._bounded_main_arguments(root)
            )

        self.assertEqual(2, exit_code)
        self.assertIn(
            "host cannot enforce the immutable pull-request snapshot size limit",
            errors.getvalue(),
        )

    def test_bounded_materialize_main_reports_acquisition_failures(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="athena-pr-review-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        errors = io.StringIO()

        with (
            patch("sys.stderr", errors),
            patch.object(self.snapshot, "_mount_tmpfs", return_value=True),
            patch.object(
                self.snapshot,
                "_acquire_into",
                side_effect=RuntimeError("fetched base ref does not match"),
            ),
            patch.object(self.snapshot, "_detach_best_effort"),
        ):
            exit_code = self.snapshot._bounded_materialize_main(
                self._bounded_main_arguments(root)
            )

        self.assertEqual(1, exit_code)
        self.assertIn("fetched base ref does not match", errors.getvalue())

    def test_mount_tmpfs_tolerates_an_existing_source_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            source.mkdir()

            def mount(
                command: list[str], **_: object
            ) -> subprocess.CompletedProcess[str]:
                return subprocess.CompletedProcess(command, 0)

            with (
                patch.object(self.snapshot.sys, "platform", "linux"),
                patch.object(
                    self.snapshot.shutil, "which", return_value="/usr/bin/mount"
                ),
                patch.object(self.snapshot, "run_command", side_effect=mount),
                patch.object(Path, "is_mount", return_value=True),
            ):
                self.assertTrue(self.snapshot._mount_tmpfs(source, 90 * 1024))

    def test_mount_tmpfs_fails_closed_when_the_source_cannot_be_created(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            with (
                patch.object(self.snapshot.sys, "platform", "linux"),
                patch.object(
                    self.snapshot.shutil, "which", return_value="/usr/bin/mount"
                ),
                patch.object(Path, "mkdir", side_effect=PermissionError("denied")),
            ):
                self.assertFalse(self.snapshot._mount_tmpfs(source, 90 * 1024))

    def test_mount_tmpfs_fails_closed_when_the_mount_command_is_unavailable(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            with (
                patch.object(self.snapshot.sys, "platform", "linux"),
                patch.object(
                    self.snapshot.shutil, "which", return_value="/usr/bin/mount"
                ),
                patch.object(
                    self.snapshot,
                    "run_command",
                    side_effect=FileNotFoundError(2, "not found", "mount"),
                ),
            ):
                self.assertFalse(self.snapshot._mount_tmpfs(source, 90 * 1024))

    def test_detach_volume_falls_back_to_a_lazy_umount(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            results: list[subprocess.CompletedProcess[str]] = [
                subprocess.CompletedProcess([], 32),
                subprocess.CompletedProcess([], 0),
            ]
            index = 0

            def run(
                *_args: object, **_kwargs: object
            ) -> subprocess.CompletedProcess[str]:
                nonlocal index
                result = results[index]
                index += 1
                return result

            with (
                patch.object(self.snapshot.sys, "platform", "linux"),
                patch.object(self.snapshot, "run_command", side_effect=run),
            ):
                self.snapshot._detach_volume(source)

    def test_detach_volume_fails_closed_when_both_umounts_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            with (
                patch.object(self.snapshot.sys, "platform", "linux"),
                patch.object(
                    self.snapshot,
                    "run_command",
                    return_value=subprocess.CompletedProcess([], 32),
                ),
                self.assertRaisesRegex(
                    RuntimeError, "cannot remove the immutable pull-request snapshot"
                ),
            ):
                self.snapshot._detach_volume(source)

    def test_detach_volume_rejects_unknown_platforms(self) -> None:
        with (
            patch.object(self.snapshot.sys, "platform", "plan9"),
            self.assertRaisesRegex(
                RuntimeError, "cannot remove the immutable pull-request snapshot"
            ),
        ):
            self.snapshot._detach_volume(Path("/tmp/source"))

    def test_require_base_ref_rejects_invalid_branch_names(self) -> None:
        for invalid in ("", "-leading-dash", "contains..two-dots"):
            with (
                self.subTest(base_ref=invalid),
                self.assertRaisesRegex(RuntimeError, "invalid pull-request base ref"),
            ):
                self.snapshot._require_base_ref(invalid)

    def test_require_base_ref_rejects_a_branch_git_cannot_check(self) -> None:
        with (
            patch.object(
                self.snapshot,
                "_git",
                side_effect=RuntimeError("cannot materialize"),
            ),
            self.assertRaisesRegex(RuntimeError, "cannot materialize"),
        ):
            self.snapshot._require_base_ref("main")

    def test_repository_size_fails_closed_when_disk_usage_is_unavailable(
        self,
    ) -> None:
        with (
            patch.object(
                self.snapshot.shutil,
                "disk_usage",
                side_effect=OSError("no such device"),
            ),
            self.assertRaisesRegex(
                RuntimeError, "cannot inspect the immutable pull-request snapshot"
            ),
        ):
            self.snapshot._repository_size(Path("/tmp/repository"))

    def test_repository_size_fails_closed_when_an_entry_cannot_be_inspected(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)

            def fail_lstat() -> os.stat_result:
                raise OSError("permission denied")

            entry = SimpleNamespace(lstat=fail_lstat)
            with (
                patch.object(Path, "rglob", return_value=[entry]),
                self.assertRaisesRegex(
                    RuntimeError,
                    "cannot inspect the immutable pull-request snapshot",
                ),
            ):
                self.snapshot._repository_size(repository, maximum_bytes=100)

    def test_verify_no_promisor_configuration_rejects_promisor_remotes(
        self,
    ) -> None:
        def git(*arguments: str, **_: object) -> str:
            if arguments[0] == "config" and arguments[-1] == "extensions.partialClone":
                return ""
            return "origin"

        with (
            patch.object(self.snapshot, "_git", side_effect=git),
            self.assertRaisesRegex(RuntimeError, "promisor configuration"),
        ):
            self.snapshot._verify_no_promisor_configuration(Path("/tmp/repository"))

    def test_make_read_only_fails_closed_when_a_chmod_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "file.txt").write_text("data", encoding="utf-8")
            with (
                patch.object(
                    Path,
                    "chmod",
                    side_effect=PermissionError("read-only filesystem"),
                ),
                self.assertRaisesRegex(
                    RuntimeError,
                    "cannot make the immutable pull-request snapshot read-only",
                ),
            ):
                self.snapshot._make_read_only(root)

    def test_bounded_materialize_surfaces_a_child_timeout(self) -> None:
        with (
            patch.object(
                self.snapshot.shutil, "which", return_value="/usr/bin/unshare"
            ),
            patch.object(
                self.snapshot,
                "run_command",
                side_effect=subprocess.TimeoutExpired([], 600),
            ),
            self.assertRaisesRegex(RuntimeError, "cannot materialize"),
        ):
            self.snapshot._bounded_materialize(
                Path("/tmp/athena-pr-review-test"),
                90 * 1024,
                repository="owner/repository",
                number=9,
                base_ref="main",
                base_oid="a" * 40,
                head_oid="b" * 40,
            )

    def test_bounded_materialize_surfaces_operating_system_failures(self) -> None:
        with (
            patch.object(
                self.snapshot.shutil, "which", return_value="/usr/bin/unshare"
            ),
            patch.object(
                self.snapshot,
                "run_command",
                side_effect=FileNotFoundError(2, "not found", "unshare"),
            ),
            self.assertRaisesRegex(
                RuntimeError,
                "host cannot enforce the immutable pull-request snapshot size limit",
            ),
        ):
            self.snapshot._bounded_materialize(
                Path("/tmp/athena-pr-review-test"),
                90 * 1024,
                repository="owner/repository",
                number=9,
                base_ref="main",
                base_oid="a" * 40,
                head_oid="b" * 40,
            )

    def test_bounded_materialize_rejects_an_unexpected_child_exit(self) -> None:
        with (
            patch.object(
                self.snapshot.shutil, "which", return_value="/usr/bin/unshare"
            ),
            patch.object(
                self.snapshot,
                "run_command",
                return_value=subprocess.CompletedProcess([], 1),
            ),
            self.assertRaisesRegex(RuntimeError, "cannot materialize"),
        ):
            self.snapshot._bounded_materialize(
                Path("/tmp/athena-pr-review-test"),
                90 * 1024,
                repository="owner/repository",
                number=9,
                base_ref="main",
                base_oid="a" * 40,
                head_oid="b" * 40,
            )

    def test_bounded_materialize_rejects_an_empty_child_record(self) -> None:
        with (
            patch.object(
                self.snapshot.shutil, "which", return_value="/usr/bin/unshare"
            ),
            patch.object(
                self.snapshot,
                "run_command",
                return_value=subprocess.CompletedProcess([], 0, stdout="\n"),
            ),
            self.assertRaisesRegex(RuntimeError, "cannot materialize"),
        ):
            self.snapshot._bounded_materialize(
                Path("/tmp/athena-pr-review-test"),
                90 * 1024,
                repository="owner/repository",
                number=9,
                base_ref="main",
                base_oid="a" * 40,
                head_oid="b" * 40,
            )

    def test_bounded_materialize_rejects_malformed_child_output(self) -> None:
        with (
            patch.object(
                self.snapshot.shutil, "which", return_value="/usr/bin/unshare"
            ),
            patch.object(
                self.snapshot,
                "run_command",
                return_value=subprocess.CompletedProcess([], 0, stdout="not json"),
            ),
            self.assertRaisesRegex(RuntimeError, "cannot materialize"),
        ):
            self.snapshot._bounded_materialize(
                Path("/tmp/athena-pr-review-test"),
                90 * 1024,
                repository="owner/repository",
                number=9,
                base_ref="main",
                base_oid="a" * 40,
                head_oid="b" * 40,
            )

    def test_materialize_snapshot_cleans_up_on_unexpected_failures(self) -> None:
        root = Path(tempfile.mkdtemp(prefix="athena-pr-review-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        removed: list[Path] = []

        with (
            patch.object(self.snapshot.tempfile, "mkdtemp", return_value=str(root)),
            patch.object(
                self.snapshot,
                "_create_quota_volume",
                side_effect=lambda temporary_root, _: temporary_root / "source",
            ),
            patch.object(
                self.snapshot,
                "_acquire_into",
                side_effect=KeyboardInterrupt,
            ),
            patch.object(
                self.snapshot,
                "remove_snapshot",
                side_effect=lambda path: removed.append(path),
            ),
            self.assertRaises(KeyboardInterrupt),
        ):
            self.snapshot.materialize_snapshot(
                repository="owner/repository",
                number=9,
                base_ref="main",
                base_oid="a" * 40,
                head_oid="b" * 40,
            )

        self.assertEqual([root], removed)


class StrictSnapshotFallbackTests(unittest.TestCase):
    """Verify strict evidence switches only missing objects to a snapshot."""

    def setUp(self) -> None:
        self.module_name = f"test_collect_evidence_snapshot_{id(self)}"
        self.collector = load_collector(self.module_name)

    def tearDown(self) -> None:
        sys.modules.pop(self.module_name, None)

    def test_collects_from_a_canonical_snapshot_when_head_is_missing_locally(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            source.mkdir()
            base_oid, head_oid = initialize_divergent_repository(source, "changed.txt")
            git(source, "update-ref", "refs/pull/9/head", head_oid)
            remote = root / "repository.git"
            git(root, "init", "--bare", "--quiet", str(remote))
            git(source, "remote", "add", "origin", str(remote))
            git(source, "push", "--quiet", "origin", "main", "refs/pull/9/head")

            caller = root / "caller"
            caller.mkdir()
            git(caller, "init", "--quiet")
            git(
                caller,
                "fetch",
                "--quiet",
                str(remote),
                "refs/heads/main:refs/heads/main",
            )
            self.assertNotEqual(
                0,
                subprocess.run(
                    ["git", "cat-file", "-e", f"{head_oid}^{{commit}}"],
                    cwd=caller,
                    capture_output=True,
                    check=False,
                ).returncode,
            )
            output = io.StringIO()
            arguments = (
                "--expected-base-oid",
                base_oid,
                "--expected-head-oid",
                head_oid,
                "--expected-host",
                "github.com",
                "--expected-repository",
                "owner/repository",
                "--expected-pr-number",
                "9",
                "--expected-pr-url",
                "https://github.com/owner/repository/pull/9",
                "9",
            )
            snapshot_module = sys.modules["materialize_snapshot"]
            original_working_directory = Path.cwd()
            try:
                os.chdir(caller)
                with (
                    patch.object(
                        self.collector,
                        "pr_metadata",
                        side_effect=[
                            pull_request(
                                base_oid=base_oid,
                                head_oid=head_oid,
                                head_ref_name="fork-owner:feature",
                            ),
                            pull_request(
                                base_oid=base_oid,
                                head_oid=head_oid,
                                head_ref_name="fork-owner:feature",
                            ),
                        ],
                    ),
                    patch.object(
                        self.collector, "head_bound_check_runs", return_value=[]
                    ),
                    patch.object(
                        snapshot_module,
                        "canonical_repository_url",
                        return_value=str(remote),
                    ),
                    patch.object(
                        snapshot_module,
                        "_create_quota_volume",
                        side_effect=lambda temporary_root, _: temporary_root / "source",
                    ),
                    patch.dict(
                        os.environ,
                        {
                            "GIT_CONFIG_GLOBAL": "/attacker/global-config",
                            "GIT_DIR": "/attacker/repository",
                        },
                    ),
                    patch("sys.stdout", output),
                ):
                    exit_code = self.collector.main(arguments)
            finally:
                os.chdir(original_working_directory)

            evidence = json.loads(output.getvalue())
            self.addCleanup(
                self.collector.remove_snapshot,
                Path(evidence["source_snapshot"]["root"]),
            )
            caller_remains_without_head = (
                subprocess.run(
                    ["git", "cat-file", "-e", f"{head_oid}^{{commit}}"],
                    cwd=caller,
                    capture_output=True,
                    check=False,
                ).returncode
                != 0
            )

        self.assertEqual(0, exit_code)
        self.assertEqual(["changed.txt"], evidence["changed_files"])
        self.assertTrue(evidence["source_snapshot"]["source_path"].endswith("/source"))
        self.assertTrue(caller_remains_without_head)

    def test_missing_head_fallback_rejects_a_real_ambiguous_merge_base(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            source.mkdir()
            base_oid, head_oid = initialize_ambiguous_merge_base_repository(
                source, "changed.txt"
            )
            remote = root / "repository.git"
            git(root, "init", "--bare", "--quiet", str(remote))
            git(source, "remote", "add", "origin", str(remote))
            git(
                source,
                "push",
                "--quiet",
                "origin",
                f"{base_oid}:refs/heads/main",
                f"{head_oid}:refs/pull/9/head",
            )
            caller = root / "caller"
            caller.mkdir()
            git(caller, "init", "--quiet")
            git(
                caller,
                "fetch",
                "--quiet",
                str(remote),
                "refs/heads/main:refs/heads/main",
            )
            self.assertNotEqual(
                0,
                subprocess.run(
                    ["git", "cat-file", "-e", f"{head_oid}^{{commit}}"],
                    cwd=caller,
                    capture_output=True,
                    check=False,
                ).returncode,
            )
            snapshot_module = sys.modules["materialize_snapshot"]
            target = self.collector.ExpectedReviewTarget(
                host="github.com",
                repository="owner/repository",
                number=9,
                url="https://github.com/owner/repository/pull/9",
            )
            original_working_directory = Path.cwd()
            try:
                os.chdir(caller)
                with (
                    patch.object(
                        snapshot_module,
                        "canonical_repository_url",
                        return_value=str(remote),
                    ),
                    patch.object(
                        snapshot_module,
                        "_create_quota_volume",
                        side_effect=lambda temporary_root, _: temporary_root / "source",
                    ),
                    self.assertRaisesRegex(RuntimeError, "one unambiguous merge base"),
                ):
                    self.collector.strict_changed_paths(
                        {"baseRefName": "main"}, (base_oid, head_oid), target
                    )
            finally:
                os.chdir(original_working_directory)


class BoundedOutputProcess:
    """Deterministic subprocess stand-in for bounded linked-comment reads."""

    def __init__(
        self,
        output: bytes = b"",
        *,
        stderr_output: bytes = b"",
        returncode: int = 0,
        poll_result: int | None = 0,
        has_stdout: bool = True,
        has_stderr: bool = True,
    ) -> None:
        self.stdout = io.BytesIO(output) if has_stdout else None
        self.stderr = io.BytesIO(stderr_output) if has_stderr else None
        self.returncode = returncode
        self.poll_result = poll_result
        self.killed = False
        self.wait_calls = 0

    def kill(self) -> None:
        """Record cancellation of an overflowing child process."""
        self.killed = True

    def poll(self) -> int | None:
        """Return the configured child state."""
        return self.poll_result

    def wait(self) -> int:
        """Return the configured process status."""
        self.wait_calls += 1
        return self.returncode


def bind_repository_identity(
    metadata_sequence: list[dict[str, object]], base_oid: str, head_oid: str
) -> list[dict[str, object]]:
    """Replace test identity sentinels with the temporary repository OIDs."""
    bound: list[dict[str, object]] = []
    for metadata in metadata_sequence:
        copy = metadata.copy()
        if copy.get("baseRefOid") == BASE_OID:
            copy["baseRefOid"] = base_oid
        if copy.get("headRefOid") == HEAD_OID:
            copy["headRefOid"] = head_oid
        bound.append(copy)
    return bound


FAKE_GH = """#!/usr/bin/env python3
import json
import os
from pathlib import Path
import re
import sys

arguments = sys.argv[1:]


def option_values(name):
    indexes = [index for index, argument in enumerate(arguments) if argument == name]
    if any(
        index + 1 == len(arguments) or arguments[index + 1].startswith("--")
        for index in indexes
    ):
        return None
    return [arguments[index + 1] for index in indexes]


def has_exact_option(name, expected):
    return option_values(name) == [expected]


def is_linked_issue_comments_request():
    return any(
        "/issues/" in argument and "/comments" in argument
        for argument in arguments
    )


def is_canonical_linked_issue_comments_request():
    endpoint = (
        r"repos/owner/requirements/issues/[1-9][0-9]*/comments"
        r"\\?per_page=100&page=[1-9][0-9]*"
    )
    return (
        len(arguments) == 6
        and arguments[:1] == ["api"]
        and has_exact_option("--hostname", "github.com")
        and has_exact_option("--method", "GET")
        and re.fullmatch(endpoint, arguments[-1]) is not None
    )


def is_head_bound_check_runs_request():
    endpoint = (
        r"repos/owner/repository/commits/[0-9a-f]{40}/check-runs"
        r"\\?per_page=100&page=[1-9][0-9]*"
    )
    return (
        arguments[:1] == ["api"]
        and has_exact_option("--hostname", "github.com")
        and has_exact_option("--method", "GET")
        and has_exact_option("-H", "Accept: application/vnd.github+json")
        and re.fullmatch(endpoint, arguments[-1]) is not None
    )


if arguments[:2] == ["pr", "view"]:
    if (
        os.environ.get("ATHENA_TEST_FORBID_AMBIENT_TARGET") == "1"
        and not has_exact_option("--repo", "github.com/owner/repository")
    ):
        print("strict review must use the retained GitHub target", file=sys.stderr)
        raise SystemExit(9)
    state_path = Path(os.environ["ATHENA_TEST_GH_STATE"])
    count = int(state_path.read_text(encoding="utf-8")) if state_path.exists() else 0
    state_path.write_text(str(count + 1), encoding="utf-8")
    sequence = json.loads(os.environ["ATHENA_TEST_GH_PR_SEQUENCE"])
    print(json.dumps(sequence[min(count, len(sequence) - 1)]))
elif arguments[:2] == ["repo", "view"]:
    if os.environ.get("ATHENA_TEST_FORBID_AMBIENT_TARGET") == "1":
        print("strict review must not query an ambient repository", file=sys.stderr)
        raise SystemExit(10)
    print(json.dumps({"nameWithOwner": "owner/repository"}))
elif arguments[:2] == ["issue", "view"]:
    if (
        os.environ.get("ATHENA_TEST_FORBID_AMBIENT_TARGET") == "1"
        and not has_exact_option("--repo", "github.com/owner/requirements")
    ):
        print("linked issue reads must use the canonical GitHub target", file=sys.stderr)
        raise SystemExit(11)
    body_bytes = os.environ.get("ATHENA_TEST_GH_ISSUE_BODY_BYTES")
    if body_bytes is not None:
        number = int(arguments[2])
        print(
            json.dumps(
                {
                    "id": "I_1",
                    "number": number,
                    "url": f"https://github.com/owner/requirements/issues/{number}",
                    "title": "Requirements",
                    "body": "x" * int(body_bytes),
                    "state": "OPEN",
                }
            )
        )
        raise SystemExit(0)
    state_path = Path(os.environ["ATHENA_TEST_GH_ISSUE_STATE"])
    count = int(state_path.read_text(encoding="utf-8")) if state_path.exists() else 0
    state_path.write_text(str(count + 1), encoding="utf-8")
    sequence = json.loads(os.environ["ATHENA_TEST_GH_ISSUE_SEQUENCE"])
    print(json.dumps(sequence[min(count, len(sequence) - 1)]))
elif arguments[:1] == ["api"]:
    if is_head_bound_check_runs_request():
        pages = json.loads(os.environ.get("ATHENA_TEST_GH_CHECK_RUN_PAGES", "[]"))
        page = int(arguments[-1].rsplit("=", maxsplit=1)[-1])
        if page <= len(pages):
            response = pages[page - 1]
        elif pages and isinstance(pages[0], dict):
            response = {"total_count": pages[0].get("total_count"), "check_runs": []}
        else:
            response = []
        print(json.dumps(response))
    elif is_linked_issue_comments_request():
        if not is_canonical_linked_issue_comments_request():
            print("linked issue comments must use the canonical request target", file=sys.stderr)
            raise SystemExit(8)
        body_bytes = os.environ.get("ATHENA_TEST_GH_COMMENT_BODY_BYTES")
        if body_bytes is not None:
            print(json.dumps([{"id": 1, "body": "x" * int(body_bytes)}]))
            raise SystemExit(0)
        comment_count = os.environ.get("ATHENA_TEST_GH_COMMENT_COUNT")
        if comment_count is not None:
            print(
                json.dumps(
                    [
                        {"id": index, "body": "Comment"}
                        for index in range(int(comment_count))
                    ]
                )
            )
            raise SystemExit(0)
        state_path = os.environ.get("ATHENA_TEST_GH_COMMENT_STATE")
        sequence_raw = os.environ.get("ATHENA_TEST_GH_COMMENT_SEQUENCE")
        if state_path is None or sequence_raw is None:
            print("[]")
        else:
            path = Path(state_path)
            count = int(path.read_text(encoding="utf-8")) if path.exists() else 0
            path.write_text(str(count + 1), encoding="utf-8")
            sequence = json.loads(sequence_raw)
            print(json.dumps(sequence[min(count, len(sequence) - 1)]))
    elif os.environ.get("ATHENA_TEST_FORBID_GH_API") == "1":
        print("strict review must not query the provider file list", file=sys.stderr)
        raise SystemExit(7)
elif arguments[:2] == ["pr", "checks"]:
    print("[]")
else:
    print(f"unexpected gh invocation: {arguments}", file=sys.stderr)
    raise SystemExit(2)
"""


def run_fake_gh(*arguments: str) -> subprocess.CompletedProcess[str]:
    """Run the fixture under strict target binding with isolated state."""
    with tempfile.TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        executable = root / "gh"
        executable.write_text(FAKE_GH, encoding="utf-8")
        executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
        environment = os.environ.copy()
        environment.update(
            {
                "ATHENA_TEST_FORBID_AMBIENT_TARGET": "1",
                "ATHENA_TEST_GH_STATE": str(root / "pr-state"),
                "ATHENA_TEST_GH_PR_SEQUENCE": json.dumps([pull_request()]),
                "ATHENA_TEST_GH_ISSUE_BODY_BYTES": "0",
            }
        )
        return subprocess.run(
            [sys.executable, str(executable), *arguments],
            capture_output=True,
            env=environment,
            text=True,
            check=False,
        )


class FakeGhArgumentValidationTests(unittest.TestCase):
    """Keep strict integration fixtures from accepting malformed target commands."""

    def test_rejects_duplicate_or_valueless_repository_options(self) -> None:
        cases = (
            (
                (
                    "pr",
                    "view",
                    "9",
                    "--repo",
                    "github.com/owner/repository",
                    "--repo",
                    "attacker.invalid/owner/repository",
                ),
                9,
            ),
            (("pr", "view", "9", "--repo", "--json", "number"), 9),
            (
                (
                    "issue",
                    "view",
                    "10",
                    "--repo",
                    "github.com/owner/requirements",
                    "--repo",
                    "attacker.invalid/owner/requirements",
                ),
                11,
            ),
            (("issue", "view", "10", "--repo", "--json", "id"), 11),
        )

        for arguments, expected_code in cases:
            with self.subTest(arguments=arguments):
                result = run_fake_gh(*arguments)

                self.assertEqual(expected_code, result.returncode)

    def test_requires_the_exact_linked_issue_comment_target(self) -> None:
        valid = (
            "api",
            "--hostname",
            "github.com",
            "--method",
            "GET",
            "repos/owner/requirements/issues/10/comments?per_page=100&page=1",
        )
        invalid = (
            (
                "api",
                "--hostname",
                "github.com",
                "--hostname",
                "attacker.invalid",
                "--method",
                "GET",
                "repos/owner/requirements/issues/10/comments?per_page=100&page=1",
            ),
            (
                "api",
                "--hostname",
                "github.com",
                "--method",
                "GET",
                "repos/attacker/requirements/issues/10/comments?per_page=100&page=1",
            ),
            (
                "api",
                "--hostname",
                "github.com",
                "--method",
                "GET",
                "repos/owner/requirements/issues/10/comments?per_page=100",
            ),
        )

        self.assertEqual(0, run_fake_gh(*valid).returncode)
        for arguments in invalid:
            with self.subTest(arguments=arguments):
                self.assertEqual(8, run_fake_gh(*arguments).returncode)


class BoundedLinkedCommentReaderTests(unittest.TestCase):
    """Exercise bounded provider-output failure behavior without live GitHub I/O."""

    def setUp(self) -> None:
        self.module_name = f"test_collect_evidence_bounded_{id(self)}"
        self.collector = load_collector(self.module_name)

    def tearDown(self) -> None:
        sys.modules.pop(self.module_name, None)

    def test_streams_a_bounded_successful_provider_response(self) -> None:
        process = BoundedOutputProcess(b"[{}]")

        with patch.object(self.collector.subprocess, "Popen", return_value=process):
            response = self.collector.bounded_gh_output(
                ("api", "example"),
                maximum_bytes=4,
                limit_error="must not overflow",
            )

        self.assertEqual(b"[{}]", response)
        self.assertEqual(1, process.wait_calls)
        self.assertFalse(process.killed)

    def test_reports_an_unavailable_gh_command(self) -> None:
        with (
            patch.object(
                self.collector.subprocess,
                "Popen",
                side_effect=FileNotFoundError(2, "not found", "gh"),
            ),
            self.assertRaisesRegex(RuntimeError, "required command unavailable: gh"),
        ):
            self.collector.bounded_gh_output(
                ("api", "example"),
                maximum_bytes=4,
                limit_error="must not overflow",
            )

    def test_rejects_a_provider_process_without_stdout(self) -> None:
        process = BoundedOutputProcess(has_stdout=False)

        with (
            patch.object(self.collector.subprocess, "Popen", return_value=process),
            self.assertRaisesRegex(RuntimeError, "did not provide linked issue"),
        ):
            self.collector.bounded_gh_output(
                ("api", "example"),
                maximum_bytes=4,
                limit_error="must not overflow",
            )

        self.assertTrue(process.killed)
        self.assertEqual(1, process.wait_calls)

    def test_cancels_a_provider_process_when_output_exceeds_the_limit(self) -> None:
        process = BoundedOutputProcess(b"overflow", poll_result=None)

        with (
            patch.object(self.collector.subprocess, "Popen", return_value=process),
            self.assertRaisesRegex(
                self.collector.LinkedRequirementsCoverageGap, "safe byte limit"
            ),
        ):
            self.collector.bounded_gh_output(
                ("api", "example"),
                maximum_bytes=4,
                limit_error="safe byte limit",
            )

        self.assertTrue(process.killed)
        self.assertEqual(1, process.wait_calls)

    def test_surfaces_a_nonzero_provider_exit_with_bounded_stderr(self) -> None:
        process = BoundedOutputProcess(
            stderr_output=b"provider rejected request\n", returncode=1
        )

        with (
            patch.object(self.collector.subprocess, "Popen", return_value=process),
            self.assertRaisesRegex(RuntimeError, "provider rejected request"),
        ):
            self.collector.bounded_gh_output(
                ("api", "example"),
                maximum_bytes=4,
                limit_error="must not overflow",
            )

    def test_cancels_a_provider_process_when_stderr_exceeds_the_limit(self) -> None:
        process = BoundedOutputProcess(stderr_output=b"overflow", poll_result=None)

        with (
            patch.object(
                self.collector,
                "MAX_LINKED_ISSUE_COMMENT_STDERR_BYTES",
                4,
                create=True,
            ),
            patch.object(self.collector.subprocess, "Popen", return_value=process),
            self.assertRaisesRegex(
                self.collector.LinkedRequirementsCoverageGap, "safe stderr limit"
            ),
        ):
            self.collector.bounded_gh_output(
                ("api", "example"),
                maximum_bytes=4,
                limit_error="must not overflow",
            )

        self.assertTrue(process.killed)
        self.assertEqual(1, process.wait_calls)

    def test_cancels_a_provider_process_that_misses_its_deadline(self) -> None:
        process = BoundedOutputProcess(poll_result=None)

        with (
            patch.object(
                self.collector,
                "LINKED_ISSUE_COMMENT_REQUEST_TIMEOUT_SECONDS",
                0,
                create=True,
            ),
            patch.object(self.collector.subprocess, "Popen", return_value=process),
            self.assertRaisesRegex(
                self.collector.LinkedRequirementsCoverageGap, "provider deadline"
            ),
        ):
            self.collector.bounded_gh_output(
                ("api", "example"),
                maximum_bytes=4,
                limit_error="must not overflow",
            )

        self.assertTrue(process.killed)
        self.assertEqual(1, process.wait_calls)

    def test_wraps_operating_system_failures_from_the_provider_reader(self) -> None:
        with (
            patch.object(
                self.collector.subprocess,
                "Popen",
                side_effect=PermissionError("denied"),
            ),
            self.assertRaisesRegex(
                RuntimeError, "cannot collect linked issue comments"
            ),
        ):
            self.collector.bounded_gh_output(
                ("api", "example"),
                maximum_bytes=4,
                limit_error="must not overflow",
            )

    def test_rejects_malformed_linked_comment_pages(self) -> None:
        cases = (
            (b"not json", RuntimeError, "invalid linked issue comment pages"),
            (b'{"id": 1}', TypeError, "invalid linked issue comment pages"),
            (b"[1]", RuntimeError, "invalid linked issue comment"),
        )
        for response, error_type, message in cases:
            with (
                self.subTest(response=response),
                patch.object(
                    self.collector, "bounded_gh_output", return_value=response
                ),
                self.assertRaisesRegex(error_type, message),
            ):
                self.collector.paginated_issue_comments("owner/requirements", 10)

    def test_fails_closed_before_reading_when_comment_bytes_are_exhausted(self) -> None:
        with (
            patch.object(self.collector, "MAX_LINKED_ISSUE_COMMENT_BYTES", 0),
            patch.object(
                self.collector,
                "bounded_gh_output",
                side_effect=AssertionError("reader must not run"),
            ),
            self.assertRaisesRegex(
                self.collector.LinkedRequirementsCoverageGap, "safe byte limit"
            ),
        ):
            self.collector.paginated_issue_comments("owner/requirements", 10)

    def test_fails_closed_when_the_next_nonempty_page_exceeds_the_page_budget(
        self,
    ) -> None:
        with (
            patch.object(self.collector, "LINKED_ISSUE_COMMENT_PAGE_SIZE", 1),
            patch.object(self.collector, "MAX_LINKED_ISSUE_COMMENT_PAGES", 1),
            patch.object(
                self.collector,
                "bounded_gh_output",
                side_effect=(b"[{}]", b"[{}]"),
            ),
            self.assertRaisesRegex(
                self.collector.LinkedRequirementsCoverageGap, "safe page limit"
            ),
        ):
            self.collector.paginated_issue_comments("owner/requirements", 10)

    def test_fails_closed_when_comment_count_exceeds_the_budget(self) -> None:
        with (
            patch.object(self.collector, "MAX_LINKED_ISSUE_COMMENTS", 0),
            patch.object(self.collector, "bounded_gh_output", return_value=b"[{}]"),
            self.assertRaisesRegex(
                self.collector.LinkedRequirementsCoverageGap, "safe comment limit"
            ),
        ):
            self.collector.paginated_issue_comments("owner/requirements", 10)

    def test_shared_budget_bounds_aggregate_comment_pages(self) -> None:
        budget = self.collector.LinkedRequirementBudget()

        with (
            patch.object(self.collector, "MAX_LINKED_REQUIREMENT_PAGES", 1),
            patch.object(self.collector, "bounded_gh_output", return_value=b"[]"),
            self.assertRaisesRegex(
                self.collector.LinkedRequirementsCoverageGap,
                "aggregate page limit",
            ),
        ):
            self.collector.paginated_issue_comments("owner/requirements", 10, budget)
            self.collector.paginated_issue_comments("owner/requirements", 11, budget)

    def test_shared_budget_bounds_aggregate_comment_count(self) -> None:
        budget = self.collector.LinkedRequirementBudget()

        with (
            patch.object(self.collector, "MAX_LINKED_REQUIREMENT_COMMENTS", 1),
            patch.object(self.collector, "bounded_gh_output", return_value=b"[{}]"),
            self.assertRaisesRegex(
                self.collector.LinkedRequirementsCoverageGap,
                "aggregate comment limit",
            ),
        ):
            self.collector.paginated_issue_comments("owner/requirements", 10, budget)
            self.collector.paginated_issue_comments("owner/requirements", 11, budget)

    def test_shared_budget_bounds_aggregate_comment_bytes(self) -> None:
        budget = self.collector.LinkedRequirementBudget()

        with (
            patch.object(self.collector, "MAX_LINKED_REQUIREMENT_BYTES", 2),
            patch.object(self.collector, "bounded_gh_output", return_value=b"[]"),
            self.assertRaisesRegex(
                self.collector.LinkedRequirementsCoverageGap,
                "aggregate byte limit",
            ),
        ):
            self.collector.paginated_issue_comments("owner/requirements", 10, budget)
            self.collector.paginated_issue_comments("owner/requirements", 11, budget)


class HeadBoundCheckEvidenceTests(unittest.TestCase):
    """Require bounded, fail-closed GitHub check-run collection."""

    def setUp(self) -> None:
        self.module_name = f"test_collect_evidence_checks_{id(self)}"
        self.collector = load_collector(self.module_name)

    def tearDown(self) -> None:
        sys.modules.pop(self.module_name, None)

    def test_preserves_a_bounded_provider_failure_as_a_coverage_gap(self) -> None:
        with (
            patch.object(
                self.collector,
                "bounded_gh_output",
                side_effect=self.collector.CheckEvidenceCoverageGap(
                    "check-run response exceeds the safe byte limit"
                ),
            ),
            patch.object(
                self.collector,
                "gh",
                return_value=json.dumps(
                    [
                        {
                            "total_count": 1,
                            "check_runs": [
                                {
                                    "id": 1,
                                    "name": "required-checks",
                                    "head_sha": HEAD_OID,
                                    "status": "completed",
                                    "conclusion": "success",
                                }
                            ],
                        }
                    ]
                ),
            ),
            self.assertRaisesRegex(
                self.collector.CheckEvidenceCoverageGap, "safe byte limit"
            ),
        ):
            self.collector.head_bound_check_runs("owner/repository", HEAD_OID)

    def test_rejects_check_runs_that_exceed_the_page_limit(self) -> None:
        responses = (
            json.dumps(
                {
                    "total_count": 2,
                    "check_runs": [
                        {
                            "id": 1,
                            "name": "first-check",
                            "head_sha": HEAD_OID,
                            "status": "completed",
                            "conclusion": "success",
                        }
                    ],
                }
            ).encode(),
            json.dumps(
                {
                    "total_count": 2,
                    "check_runs": [
                        {
                            "id": 2,
                            "name": "second-check",
                            "head_sha": HEAD_OID,
                            "status": "completed",
                            "conclusion": "success",
                        }
                    ],
                }
            ).encode(),
        )

        with (
            patch.object(self.collector, "MAX_CHECK_RUN_PAGES", 1),
            patch.object(self.collector, "bounded_gh_output", side_effect=responses),
            self.assertRaisesRegex(
                self.collector.CheckEvidenceCoverageGap, "safe page limit"
            ),
        ):
            self.collector.head_bound_check_runs("owner/repository", HEAD_OID)


class BoundedChangedPathReaderTests(unittest.TestCase):
    """Exercise bounded immutable path collection without a live Git process."""

    def setUp(self) -> None:
        self.module_name = f"test_collect_evidence_paths_{id(self)}"
        self.collector = load_collector(self.module_name)

    def tearDown(self) -> None:
        sys.modules.pop(self.module_name, None)

    def test_streams_a_bounded_path_manifest(self) -> None:
        process = BoundedOutputProcess(b"alpha\0beta\0")

        with patch.object(self.collector.subprocess, "Popen", return_value=process):
            paths = self.collector.immutable_range_paths(BASE_OID, HEAD_OID)

        self.assertEqual([b"alpha", b"beta"], paths)
        self.assertEqual(1, process.wait_calls)
        self.assertFalse(process.killed)

    def test_fails_closed_when_a_path_manifest_exceeds_the_byte_limit(self) -> None:
        process = BoundedOutputProcess(b"alpha\0", poll_result=None)

        with (
            patch.object(self.collector, "MAX_CHANGED_PATH_MANIFEST_BYTES", 4),
            patch.object(self.collector.subprocess, "Popen", return_value=process),
            self.assertRaisesRegex(
                self.collector.ChangedPathCoverageGap, "safe byte limit"
            ),
        ):
            self.collector.immutable_range_paths(BASE_OID, HEAD_OID)

        self.assertTrue(process.killed)
        self.assertEqual(1, process.wait_calls)

    def test_fails_closed_when_a_path_manifest_exceeds_the_path_limit(self) -> None:
        process = BoundedOutputProcess(b"alpha\0beta\0", poll_result=None)

        with (
            patch.object(self.collector, "MAX_CHANGED_PATHS", 1),
            patch.object(self.collector.subprocess, "Popen", return_value=process),
            self.assertRaisesRegex(
                self.collector.ChangedPathCoverageGap, "safe path limit"
            ),
        ):
            self.collector.immutable_range_paths(BASE_OID, HEAD_OID)

        self.assertTrue(process.killed)
        self.assertEqual(1, process.wait_calls)

    def test_fails_closed_when_a_path_manifest_misses_its_deadline(self) -> None:
        process = BoundedOutputProcess(poll_result=None)

        with (
            patch.object(self.collector, "CHANGED_PATH_REQUEST_TIMEOUT_SECONDS", 0),
            patch.object(self.collector.subprocess, "Popen", return_value=process),
            self.assertRaisesRegex(
                self.collector.ChangedPathCoverageGap, "provider deadline"
            ),
        ):
            self.collector.immutable_range_paths(BASE_OID, HEAD_OID)

        self.assertTrue(process.killed)
        self.assertEqual(1, process.wait_calls)

    def test_reports_a_path_capacity_gap_as_structured_evidence(self) -> None:
        arguments = (
            "--expected-base-oid",
            BASE_OID,
            "--expected-head-oid",
            HEAD_OID,
            "--expected-host",
            "github.com",
            "--expected-repository",
            "owner/repository",
            "--expected-pr-number",
            "9",
            "--expected-pr-url",
            "https://github.com/owner/repository/pull/9",
            "9",
        )
        output = io.StringIO()

        with (
            patch.object(self.collector, "pr_metadata", return_value=pull_request()),
            patch.object(
                self.collector, "local_immutable_objects_available", return_value=True
            ),
            patch.object(
                self.collector,
                "immutable_changed_paths",
                side_effect=self.collector.ChangedPathCoverageGap("safe path limit"),
            ),
            patch("sys.stdout", output),
        ):
            exit_code = self.collector.main(arguments)

        self.assertEqual(1, exit_code)
        self.assertEqual(
            {
                "details": "safe path limit",
                "error": "changed path coverage gap",
            },
            json.loads(output.getvalue()),
        )


class ImmutableEvidenceTests(unittest.TestCase):
    def run_collector(
        self,
        metadata_sequence: list[dict[str, object]],
        *,
        changed_path: str = "changed.txt",
        repository_initializer: Callable[[Path, str], tuple[str, str]] = (
            initialize_repository
        ),
        replace_head_with_base: bool = False,
        linked_issue_sequence: list[dict[str, object]] | None = None,
        linked_comment_sequence: list[object] | None = None,
        linked_comment_body_bytes: int | None = None,
        linked_comment_count: int | None = None,
        linked_issue_body_bytes: int | None = None,
        head_bound_check_pages: list[object] | None = None,
        expected_target: bool = True,
        hostile_target_environment: bool = False,
    ) -> tuple[subprocess.CompletedProcess[str], int, str, str]:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            base_oid, head_oid = repository_initializer(root, changed_path)
            if replace_head_with_base:
                git(root, "replace", head_oid, base_oid)
            bin_directory = root / "bin"
            bin_directory.mkdir()
            gh_path = bin_directory / "gh"
            gh_path.write_text(FAKE_GH, encoding="utf-8")
            gh_path.chmod(gh_path.stat().st_mode | stat.S_IXUSR)
            environment = os.environ.copy()
            environment["PATH"] = f"{bin_directory}{os.pathsep}{environment['PATH']}"
            state_path = root / "gh-state"
            environment["ATHENA_TEST_GH_STATE"] = str(state_path)
            environment["ATHENA_TEST_GH_PR_SEQUENCE"] = json.dumps(
                bind_repository_identity(metadata_sequence, base_oid, head_oid)
            )
            if linked_issue_sequence is not None:
                issue_state_path = root / "gh-issue-state"
                environment["ATHENA_TEST_GH_ISSUE_STATE"] = str(issue_state_path)
                environment["ATHENA_TEST_GH_ISSUE_SEQUENCE"] = json.dumps(
                    linked_issue_sequence
                )
            if linked_comment_sequence is not None:
                comment_state_path = root / "gh-comment-state"
                environment["ATHENA_TEST_GH_COMMENT_STATE"] = str(comment_state_path)
                environment["ATHENA_TEST_GH_COMMENT_SEQUENCE"] = json.dumps(
                    linked_comment_sequence
                )
            if linked_comment_body_bytes is not None:
                environment["ATHENA_TEST_GH_COMMENT_BODY_BYTES"] = str(
                    linked_comment_body_bytes
                )
            if linked_comment_count is not None:
                environment["ATHENA_TEST_GH_COMMENT_COUNT"] = str(linked_comment_count)
            if linked_issue_body_bytes is not None:
                environment["ATHENA_TEST_GH_ISSUE_BODY_BYTES"] = str(
                    linked_issue_body_bytes
                )
            if head_bound_check_pages is not None:
                environment["ATHENA_TEST_GH_CHECK_RUN_PAGES"] = json.dumps(
                    head_bound_check_pages
                ).replace(HEAD_OID, head_oid)
            environment["ATHENA_TEST_FORBID_GH_API"] = "1"
            if hostile_target_environment:
                environment["GH_HOST"] = "attacker.invalid"
                environment["GH_REPO"] = "attacker/repository"
                environment["ATHENA_TEST_FORBID_AMBIENT_TARGET"] = "1"
            expected_arguments = [
                "--expected-base-oid",
                base_oid,
                "--expected-head-oid",
                head_oid,
            ]
            if expected_target:
                expected_arguments.extend(
                    (
                        "--expected-host",
                        "github.com",
                        "--expected-repository",
                        "owner/repository",
                        "--expected-pr-number",
                        "9",
                        "--expected-pr-url",
                        "https://github.com/owner/repository/pull/9",
                    )
                )
            command = [
                sys.executable,
                str(SCRIPT),
                *expected_arguments,
                "9",
            ]
            if os.environ.get("ATHENA_COVERAGE") == "1":
                command = [
                    sys.executable,
                    "-m",
                    "coverage",
                    "run",
                    "--branch",
                    "--parallel-mode",
                    str(SCRIPT),
                    *expected_arguments,
                    "9",
                ]
                environment["COVERAGE_FILE"] = str(ROOT / ".coverage")
            result = subprocess.run(
                command,
                cwd=root,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            call_count = (
                int(state_path.read_text(encoding="utf-8"))
                if state_path.exists()
                else 0
            )
            return result, call_count, base_oid, head_oid

    def test_emits_stably_revalidated_immutable_identity(self) -> None:
        result, call_count, base_oid, head_oid = self.run_collector(
            [pull_request(), pull_request()]
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(2, call_count)
        evidence = json.loads(result.stdout)
        identity = evidence["reviewed_identity"]
        self.assertEqual("github.com", identity["forge_host"])
        self.assertEqual(base_oid, identity["base_oid"])
        self.assertEqual(head_oid, identity["head_oid"])
        self.assertEqual(["changed.txt"], evidence["changed_files"])
        self.assertEqual(
            "Immutable evidence", evidence["reviewed_scope"]["fields"]["title"]
        )
        self.assertEqual("main", evidence["reviewed_scope"]["fields"]["baseRefName"])
        self.assertEqual("feature", evidence["reviewed_scope"]["fields"]["headRefName"])
        self.assertEqual(0, evidence["reviewed_linked_requirements"]["count"])
        self.assertEqual("coverage_gap", evidence["check_evidence"]["status"])

    def test_collects_check_runs_bound_to_the_reviewed_head(self) -> None:
        result, _, _, head_oid = self.run_collector(
            [pull_request(), pull_request()],
            head_bound_check_pages=[
                {
                    "total_count": 1,
                    "check_runs": [
                        {
                            "id": 1,
                            "name": "required-checks",
                            "head_sha": HEAD_OID,
                            "status": "completed",
                            "conclusion": "success",
                        }
                    ],
                }
            ],
        )

        self.assertEqual(0, result.returncode, result.stderr)
        evidence = json.loads(result.stdout)
        self.assertEqual("head_bound", evidence["check_evidence"]["status"])
        self.assertEqual(head_oid, evidence["check_evidence"]["head_oid"])
        self.assertEqual(1, evidence["check_evidence"]["count"])
        self.assertEqual("required-checks", evidence["checks"][0]["name"])

    def test_treats_missing_head_bound_check_evidence_as_a_coverage_gap(self) -> None:
        result, _, _, _ = self.run_collector(
            [pull_request(), pull_request()], head_bound_check_pages=[]
        )

        self.assertEqual(0, result.returncode, result.stderr)
        evidence = json.loads(result.stdout)
        self.assertEqual([], evidence["checks"])
        self.assertEqual("coverage_gap", evidence["check_evidence"]["status"])
        self.assertIn("malformed check-run page", evidence["check_evidence"]["reason"])

    def test_treats_stale_check_runs_as_a_coverage_gap(self) -> None:
        result, _, _, _ = self.run_collector(
            [pull_request(), pull_request()],
            head_bound_check_pages=[
                {
                    "total_count": 1,
                    "check_runs": [
                        {
                            "id": 1,
                            "name": "required-checks",
                            "head_sha": BASE_OID,
                            "status": "completed",
                            "conclusion": "success",
                        }
                    ],
                }
            ],
        )

        self.assertEqual(0, result.returncode, result.stderr)
        evidence = json.loads(result.stdout)
        self.assertEqual([], evidence["checks"])
        self.assertEqual("coverage_gap", evidence["check_evidence"]["status"])
        self.assertIn("different head OID", evidence["check_evidence"]["reason"])

    def test_treats_mixed_head_check_runs_as_a_coverage_gap(self) -> None:
        result, _, _, _ = self.run_collector(
            [pull_request(), pull_request()],
            head_bound_check_pages=[
                {
                    "total_count": 2,
                    "check_runs": [
                        {
                            "id": 1,
                            "name": "current-check",
                            "head_sha": HEAD_OID,
                            "status": "completed",
                            "conclusion": "success",
                        },
                        {
                            "id": 2,
                            "name": "stale-check",
                            "head_sha": BASE_OID,
                            "status": "completed",
                            "conclusion": "success",
                        },
                    ],
                }
            ],
        )

        self.assertEqual(0, result.returncode, result.stderr)
        evidence = json.loads(result.stdout)
        self.assertEqual([], evidence["checks"])
        self.assertEqual("coverage_gap", evidence["check_evidence"]["status"])
        self.assertIn("different head OID", evidence["check_evidence"]["reason"])

    def test_treats_partial_check_runs_as_a_coverage_gap(self) -> None:
        result, _, _, _ = self.run_collector(
            [pull_request(), pull_request()],
            head_bound_check_pages=[
                {
                    "total_count": 2,
                    "check_runs": [
                        {
                            "id": 1,
                            "name": "required-checks",
                            "head_sha": HEAD_OID,
                            "status": "completed",
                            "conclusion": "success",
                        }
                    ],
                }
            ],
        )

        self.assertEqual(0, result.returncode, result.stderr)
        evidence = json.loads(result.stdout)
        self.assertEqual([], evidence["checks"])
        self.assertEqual("coverage_gap", evidence["check_evidence"]["status"])
        self.assertIn("partial", evidence["check_evidence"]["reason"])

    def test_treats_malformed_check_runs_as_a_coverage_gap(self) -> None:
        result, _, _, _ = self.run_collector(
            [pull_request(), pull_request()],
            head_bound_check_pages=[
                {
                    "total_count": 1,
                    "check_runs": [
                        {
                            "id": 1,
                            "name": "required-checks",
                            "status": "completed",
                            "conclusion": "success",
                        }
                    ],
                }
            ],
        )

        self.assertEqual(0, result.returncode, result.stderr)
        evidence = json.loads(result.stdout)
        self.assertEqual([], evidence["checks"])
        self.assertEqual("coverage_gap", evidence["check_evidence"]["status"])
        self.assertIn("incomplete", evidence["check_evidence"]["reason"])

    def test_requires_an_explicit_review_target_for_strict_evidence(self) -> None:
        result, call_count, _, _ = self.run_collector(
            [pull_request()], expected_target=False
        )

        self.assertEqual(2, result.returncode)
        self.assertEqual(0, call_count)

    def test_uses_the_retained_target_despite_hostile_gh_environment(self) -> None:
        reference = {
            "id": "I_1",
            "number": 10,
            "repository": {"name": "requirements", "owner": {"login": "owner"}},
            "url": "https://github.com/owner/requirements/issues/10",
        }
        requirement = {
            "id": "I_1",
            "number": 10,
            "url": "https://github.com/owner/requirements/issues/10",
            "title": "Requirements",
            "body": "Acceptance criterion",
            "state": "OPEN",
        }
        result, call_count, _, _ = self.run_collector(
            [
                pull_request(closing_issues=[reference]),
                pull_request(closing_issues=[reference]),
            ],
            linked_issue_sequence=[requirement, requirement],
            linked_comment_sequence=[[], []],
            expected_target=True,
            hostile_target_environment=True,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(2, call_count)

    def test_rejects_a_noncanonical_provider_url_in_strict_mode(self) -> None:
        noncanonical = "https://github.com/owner/repository/pull/9?source=attacker"
        result, call_count, _, _ = self.run_collector([pull_request(url=noncanonical)])

        self.assertEqual(1, result.returncode)
        self.assertEqual(1, call_count)

    def test_rejects_missing_immutable_identity(self) -> None:
        metadata = pull_request()
        metadata.pop("headRefOid")

        result, call_count, _, _ = self.run_collector([metadata])

        self.assertEqual(1, result.returncode)
        self.assertEqual(1, call_count)

    def test_rejects_non_open_pull_request(self) -> None:
        result, call_count, _, _ = self.run_collector([pull_request(state="CLOSED")])

        self.assertEqual(1, result.returncode)
        self.assertEqual(1, call_count)

    def test_rejects_missing_open_state(self) -> None:
        metadata = pull_request()
        metadata.pop("state")

        result, call_count, _, _ = self.run_collector([metadata])

        self.assertEqual(1, result.returncode)
        self.assertEqual(1, call_count)

    def test_rejects_missing_review_scope_fields(self) -> None:
        for field in ("body", "isDraft", "closingIssuesReferences"):
            with self.subTest(field=field):
                metadata = pull_request()
                metadata.pop(field)

                result, call_count, _, _ = self.run_collector([metadata])

                self.assertEqual(1, result.returncode)
                self.assertEqual(1, call_count)

    def test_rejects_identity_that_differs_from_resolved_revisions(self) -> None:
        result, call_count, _, _ = self.run_collector([pull_request(head_oid="c" * 40)])

        self.assertEqual(1, result.returncode)
        self.assertEqual(1, call_count)

    def test_rejects_identity_that_changes_while_collecting_evidence(self) -> None:
        result, call_count, _, _ = self.run_collector(
            [pull_request(), pull_request(head_oid="c" * 40)]
        )

        self.assertEqual(1, result.returncode)
        self.assertEqual(2, call_count)

    def test_rejects_scope_that_changes_while_collecting_evidence(self) -> None:
        result, call_count, _, _ = self.run_collector(
            [pull_request(), pull_request(title="Changed review scope")]
        )

        self.assertEqual(1, result.returncode)
        self.assertEqual(2, call_count)

    def test_rejects_branch_scope_that_changes_while_collecting_evidence(self) -> None:
        result, call_count, _, _ = self.run_collector(
            [pull_request(), pull_request(base_ref_name="release")]
        )

        self.assertEqual(1, result.returncode)
        self.assertEqual(2, call_count)

    def test_rejects_source_branch_scope_that_changes_while_collecting_evidence(
        self,
    ) -> None:
        result, call_count, _, _ = self.run_collector(
            [pull_request(), pull_request(head_ref_name="renamed-feature")]
        )

        self.assertEqual(1, result.returncode)
        self.assertEqual(2, call_count)

    def test_rejects_linked_requirement_content_that_changes_while_collecting(
        self,
    ) -> None:
        reference = {
            "id": "I_1",
            "number": 10,
            "repository": {"name": "requirements", "owner": {"login": "owner"}},
            "url": "https://github.com/owner/requirements/issues/10",
        }
        initial_requirement = {
            "id": "I_1",
            "number": 10,
            "url": "https://github.com/owner/requirements/issues/10",
            "title": "Requirements",
            "body": "Initial acceptance criterion",
            "state": "OPEN",
            "comments": [],
        }
        changed_requirement = initial_requirement | {
            "body": "Changed acceptance criterion"
        }

        result, call_count, _, _ = self.run_collector(
            [
                pull_request(closing_issues=[reference]),
                pull_request(closing_issues=[reference]),
            ],
            linked_issue_sequence=[initial_requirement, changed_requirement],
        )

        self.assertEqual(1, result.returncode)
        self.assertEqual(2, call_count)

    def test_rejects_an_incomplete_linked_issue_reference(self) -> None:
        result, call_count, _, _ = self.run_collector(
            [pull_request(closing_issues=[{"number": 10}])]
        )

        self.assertEqual(1, result.returncode)
        self.assertEqual(1, call_count)

    def test_rejects_a_noncanonical_linked_issue_url(self) -> None:
        reference = {
            "id": "I_1",
            "number": 10,
            "repository": {"name": "requirements", "owner": {"login": "owner"}},
            "url": "https://github.com/owner/requirements/issues/10?source=attacker",
        }
        result, call_count, _, _ = self.run_collector(
            [pull_request(closing_issues=[reference])]
        )

        self.assertEqual(1, result.returncode)
        self.assertEqual(1, call_count)

    def test_rejects_a_boolean_linked_issue_number(self) -> None:
        reference = {
            "id": "I_1",
            "number": True,
            "repository": {"name": "requirements", "owner": {"login": "owner"}},
            "url": "https://github.com/owner/requirements/issues/True",
        }
        requirement = {
            "id": "I_1",
            "number": True,
            "url": "https://github.com/owner/requirements/issues/True",
            "title": "Requirements",
            "body": "Acceptance criterion",
            "state": "OPEN",
        }
        result, call_count, _, _ = self.run_collector(
            [
                pull_request(closing_issues=[reference]),
                pull_request(closing_issues=[reference]),
            ],
            linked_issue_sequence=[requirement, requirement],
        )

        self.assertEqual(1, result.returncode)
        self.assertEqual(1, call_count)

    def test_rejects_a_linked_issue_response_with_a_different_id(self) -> None:
        reference = {
            "id": "I_linked",
            "number": 10,
            "repository": {"name": "requirements", "owner": {"login": "owner"}},
            "url": "https://github.com/owner/requirements/issues/10",
        }
        mismatched_requirement = {
            "id": "I_different",
            "number": 10,
            "url": "https://github.com/owner/requirements/issues/10",
            "title": "Requirements",
            "body": "Acceptance criterion",
            "state": "OPEN",
        }
        result, call_count, _, _ = self.run_collector(
            [pull_request(closing_issues=[reference])],
            linked_issue_sequence=[mismatched_requirement],
        )

        self.assertEqual(1, result.returncode)
        self.assertEqual(1, call_count)

    def test_emits_a_stable_linked_requirements_binding(self) -> None:
        reference = {
            "id": "I_1",
            "number": 10,
            "repository": {"name": "requirements", "owner": {"login": "owner"}},
            "url": "https://github.com/owner/requirements/issues/10",
        }
        requirement = {
            "id": "I_1",
            "number": 10,
            "url": "https://github.com/owner/requirements/issues/10",
            "title": "Requirements",
            "body": "Acceptance criterion",
            "state": "OPEN",
        }
        comments = [{"id": 1, "body": "Canonical plan"}]

        result, call_count, _, _ = self.run_collector(
            [
                pull_request(closing_issues=[reference]),
                pull_request(closing_issues=[reference]),
            ],
            linked_issue_sequence=[requirement, requirement],
            linked_comment_sequence=[comments, comments],
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(2, call_count)
        binding = json.loads(result.stdout)["reviewed_linked_requirements"]
        self.assertEqual(1, binding["count"])
        self.assertRegex(binding["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            {
                "content_sha256": binding["items"][0]["content_sha256"],
                "id": "I_1",
                "number": 10,
                "repository": "owner/requirements",
                "url": "https://github.com/owner/requirements/issues/10",
            },
            binding["items"][0],
        )
        self.assertRegex(binding["items"][0]["content_sha256"], r"^[0-9a-f]{64}$")

    def test_rejects_linked_requirement_comments_that_change_while_collecting(
        self,
    ) -> None:
        reference = {
            "id": "I_1",
            "number": 10,
            "repository": {"name": "requirements", "owner": {"login": "owner"}},
            "url": "https://github.com/owner/requirements/issues/10",
        }
        requirement = {
            "id": "I_1",
            "number": 10,
            "url": "https://github.com/owner/requirements/issues/10",
            "title": "Requirements",
            "body": "Acceptance criterion",
            "state": "OPEN",
        }

        result, call_count, _, _ = self.run_collector(
            [
                pull_request(closing_issues=[reference]),
                pull_request(closing_issues=[reference]),
            ],
            linked_issue_sequence=[requirement, requirement],
            linked_comment_sequence=[[], [{"id": 1, "body": "Changed plan"}]],
        )

        self.assertEqual(1, result.returncode)
        self.assertEqual(2, call_count)

    def test_bounds_linked_issue_comment_pages_as_a_structured_coverage_gap(
        self,
    ) -> None:
        reference, requirement = linked_requirement_fixture()
        page = [{"id": index, "body": "Comment"} for index in range(100)]

        result, call_count, _, _ = self.run_collector(
            [pull_request(closing_issues=[reference])],
            linked_issue_sequence=[requirement],
            linked_comment_sequence=[page] * 10,
        )

        self.assertEqual(1, result.returncode)
        self.assertEqual(1, call_count)
        error = json.loads(result.stdout)
        self.assertEqual("linked issue requirements coverage gap", error["error"])
        self.assertIn("page limit", error["details"])
        self.assertEqual("", result.stderr)

    def test_bounds_linked_issue_comment_count_as_a_structured_coverage_gap(
        self,
    ) -> None:
        reference, requirement = linked_requirement_fixture()

        result, call_count, _, _ = self.run_collector(
            [pull_request(closing_issues=[reference])],
            linked_issue_sequence=[requirement],
            linked_comment_count=1001,
        )

        self.assertEqual(1, result.returncode)
        self.assertEqual(1, call_count)
        error = json.loads(result.stdout)
        self.assertEqual("linked issue requirements coverage gap", error["error"])
        self.assertIn("comment limit", error["details"])
        self.assertEqual("", result.stderr)

    def test_bounds_linked_issue_comment_bytes_as_a_structured_coverage_gap(
        self,
    ) -> None:
        reference, requirement = linked_requirement_fixture()

        result, call_count, _, _ = self.run_collector(
            [pull_request(closing_issues=[reference])],
            linked_issue_sequence=[requirement],
            linked_comment_body_bytes=2 * 1024 * 1024,
        )

        self.assertEqual(1, result.returncode)
        self.assertEqual(1, call_count)
        error = json.loads(result.stdout)
        self.assertEqual("linked issue requirements coverage gap", error["error"])
        self.assertIn("byte limit", error["details"])
        self.assertEqual("", result.stderr)

    def test_bounds_linked_issue_metadata_response_as_a_structured_coverage_gap(
        self,
    ) -> None:
        reference, _ = linked_requirement_fixture()

        result, call_count, _, _ = self.run_collector(
            [pull_request(closing_issues=[reference])],
            linked_issue_body_bytes=2 * 1024 * 1024,
        )

        self.assertEqual(1, result.returncode)
        self.assertEqual(1, call_count)
        error = json.loads(result.stdout)
        self.assertEqual("linked issue requirements coverage gap", error["error"])
        self.assertIn("metadata byte limit", error["details"])
        self.assertEqual("", result.stderr)

    def test_rejects_malformed_linked_comment_pages_end_to_end(self) -> None:
        reference, requirement = linked_requirement_fixture()
        cases = (
            ({"id": 1}, "GitHub returned invalid linked issue comment pages\n"),
            (
                ["not-a-comment-object"],
                "GitHub returned an invalid linked issue comment\n",
            ),
        )
        for page, expected_error in cases:
            with self.subTest(page=page):
                result, call_count, _, _ = self.run_collector(
                    [pull_request(closing_issues=[reference])],
                    linked_issue_sequence=[requirement],
                    linked_comment_sequence=[page],
                )

                self.assertEqual(1, result.returncode)
                self.assertEqual(1, call_count)
                self.assertEqual("", result.stdout)
                self.assertEqual(expected_error, result.stderr)

    def test_bounds_linked_requirements_across_final_revalidation(self) -> None:
        fixtures = [
            linked_requirement_fixture(number, f"I_{index:02d}")
            for index, number in enumerate(range(10, 23))
        ]
        references = [reference for reference, _ in fixtures]
        requirements = [requirement for _, requirement in fixtures]

        result, call_count, _, _ = self.run_collector(
            [
                pull_request(closing_issues=references),
                pull_request(closing_issues=references),
            ],
            linked_issue_sequence=[*requirements, *requirements],
            linked_comment_sequence=[[]] * 26,
        )

        self.assertEqual(1, result.returncode)
        self.assertEqual(2, call_count)
        error = json.loads(result.stdout)
        self.assertEqual("linked issue requirements coverage gap", error["error"])
        self.assertIn("aggregate request limit", error["details"])
        self.assertEqual("", result.stderr)

    def test_reports_final_partial_pr_metadata_as_a_structured_error(self) -> None:
        initial = pull_request()
        final = pull_request()
        final["headRefName"] = None

        result, call_count, _, _ = self.run_collector([initial, final])

        self.assertEqual(1, result.returncode)
        self.assertEqual(2, call_count)
        self.assertEqual(
            {
                "error": "incomplete PR metadata",
                "details": (
                    "GitHub returned incomplete or invalid PR metadata fields: "
                    + "headRefName"
                ),
            },
            json.loads(result.stdout),
        )
        self.assertEqual("", result.stderr)

    def test_emits_final_revalidated_metadata(self) -> None:
        initial = pull_request()
        initial["reviews"] = [{"id": "initial"}]
        final = pull_request()
        final["reviews"] = [{"id": "final"}]

        result, _, _, _ = self.run_collector([initial, final])

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            [{"id": "final"}], json.loads(result.stdout)["pull_request"]["reviews"]
        )

    def test_immutable_changed_paths_ignore_replacement_refs(self) -> None:
        result, call_count, _, _ = self.run_collector(
            [pull_request(), pull_request()],
            changed_path="replacement.txt",
            replace_head_with_base=True,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(2, call_count)
        self.assertEqual(
            ["replacement.txt"], json.loads(result.stdout)["changed_files"]
        )

    def test_binds_the_union_of_author_intent_and_current_target_paths(self) -> None:
        """A target-equivalent tree must not hide a feature's changed path."""
        result, call_count, _, _ = self.run_collector(
            [pull_request(), pull_request()],
            repository_initializer=initialize_divergent_repository,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(2, call_count)
        self.assertEqual(["changed.txt"], json.loads(result.stdout)["changed_files"])

    def test_rejects_shallow_history_before_binding_changed_paths(self) -> None:
        result, call_count, _, _ = self.run_collector(
            [pull_request()],
            repository_initializer=initialize_shallow_repository,
        )

        self.assertEqual(1, result.returncode)
        self.assertEqual(1, call_count)
        self.assertIn("non-shallow", result.stderr)

    def test_rejects_an_ambiguous_merge_base_before_binding_paths(self) -> None:
        result, call_count, _, _ = self.run_collector(
            [pull_request()],
            repository_initializer=initialize_ambiguous_merge_base_repository,
        )

        self.assertEqual(1, result.returncode)
        self.assertEqual(1, call_count)
        self.assertIn("unambiguous merge base", result.stderr)

    def test_diff_context_rejects_an_ambiguous_merge_base(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repository"
            repository.mkdir()
            base_oid, head_oid = initialize_ambiguous_merge_base_repository(
                repository, "changed.txt"
            )
            result = subprocess.run(
                [sys.executable, str(DIFF_CONTEXT_SCRIPT), base_oid, head_oid],
                cwd=repository,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(1, result.returncode)
        self.assertIn("unambiguous merge base", result.stderr)

    def test_binds_a_newline_path_without_querying_provider_file_metadata(self) -> None:
        path = "line\nbreak.py"
        result, call_count, _, _ = self.run_collector(
            [pull_request(), pull_request()], changed_path=path
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(2, call_count)
        evidence = json.loads(result.stdout)
        self.assertEqual([path], evidence["changed_files"])
        self.assertEqual(
            sha256(path.encode("utf-8") + b"\0").hexdigest(),
            evidence["changed_path_manifest"]["sha256"],
        )


if __name__ == "__main__":
    unittest.main()
