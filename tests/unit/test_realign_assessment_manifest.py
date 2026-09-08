"""Behavior tests for realign assessment-source binding."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from functools import lru_cache
from io import StringIO
from pathlib import Path
from types import ModuleType
from typing import Any, cast
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "skills/realign/scripts/resolve_assessment.py"


def git(repository: Path, *arguments: str) -> str:
    """Run one deterministic Git fixture command."""
    result = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def commit_file(repository: Path, path: str, contents: str, message: str) -> str:
    """Write and commit one fixture file."""
    destination = repository / path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(contents, encoding="utf-8")
    git(repository, "add", "--", path)
    git(repository, "commit", "-m", message)
    return git(repository, "rev-parse", "HEAD")


@lru_cache(maxsize=1)
def load_helper() -> ModuleType:
    """Load the repository helper after the artifact-presence assertion."""
    if not HELPER.is_file():
        raise AssertionError(f"missing realign assessment helper: {HELPER}")
    spec = importlib.util.spec_from_file_location("realign_assessment", HELPER)
    if spec is None or spec.loader is None:
        raise AssertionError("cannot load the realign assessment helper")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def valid_report(
    helper: ModuleType, repository: Path, source: dict[str, Any], path: str
) -> tuple[dict[str, Any], str]:
    """Build one complete source-bound repair report and approval digest."""
    if source["source_kind"] == "selected_commit_tree":
        content = helper.snapshot_file_entry(repository, source, path).content
    else:
        content = (repository / path).read_bytes()
    receipt = {
        "source_digest": source["source_digest"],
        "argv": ["just", "test"],
        "environment": {"boundary": "host-enforced"},
        "exit_status": 0,
        "stdout": "passed\n",
        "stderr": "",
    }
    report = {
        "schema_version": 1,
        "source": source,
        "validation": helper.validation_manifest(
            available=True,
            source_digest=source["source_digest"],
            receipts=[receipt],
        ),
        "candidates": [
            {
                "id": "RLG-001",
                "paths": [path],
                "route": "realign",
                "status": "open",
                "dependencies": [],
                "evidence": [
                    {
                        "path": path,
                        "content_sha256": hashlib.sha256(content).hexdigest(),
                    }
                ],
                "correction": {"summary": "Apply the approved correction."},
            }
        ],
    }
    return report, helper.assessment_report_digest(report)


class RealignAssessmentManifestTests(unittest.TestCase):
    """Verify selected-commit and worktree source contracts."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.repository = Path(self.temporary_directory.name)
        git(self.repository, "init", "-b", "main")
        git(self.repository, "config", "user.name", "Athena Test")
        git(self.repository, "config", "user.email", "athena@example.invalid")
        git(self.repository, "config", "commit.gpgSign", "false")
        git(self.repository, "config", "tag.gpgSign", "false")

    def test_selected_commit_can_be_assessed_from_different_checkout(self) -> None:
        helper = load_helper()
        selected = commit_file(self.repository, "source.txt", "selected\n", "selected")
        commit_file(self.repository, "source.txt", "current\n", "current")

        binding = helper.resolve_source_binding(
            self.repository, reference=selected, target="source.txt"
        )
        entry = helper.snapshot_file_entry(self.repository, binding, "source.txt")

        self.assertEqual("selected_commit_tree", binding["source_kind"])
        self.assertEqual(selected, binding["commit_oid"])
        self.assertEqual(b"selected\n", entry.content)

    def test_dirty_worktree_is_excluded_from_selected_commit_assessment(self) -> None:
        helper = load_helper()
        selected = commit_file(self.repository, "source.txt", "committed\n", "base")
        (self.repository / "source.txt").write_text("dirty\n", encoding="utf-8")
        (self.repository / "untracked.txt").write_text("untracked\n", encoding="utf-8")

        binding = helper.resolve_source_binding(
            self.repository, reference=selected, target="."
        )
        inventory = helper.inventory_manifest(self.repository, binding)
        entry = helper.snapshot_file_entry(self.repository, binding, "source.txt")

        self.assertEqual(b"committed\n", entry.content)
        self.assertEqual(
            ["source.txt"], [item["path"] for item in inventory["entries"]]
        )
        self.assertNotIn("overlay_digest", binding)

    def test_branch_and_tag_selectors_bind_recorded_oid_not_later_ref_state(
        self,
    ) -> None:
        helper = load_helper()
        first = commit_file(self.repository, "source.txt", "first\n", "first")
        git(self.repository, "branch", "selected", first)
        git(self.repository, "tag", "selected-tag", first)

        branch_binding = helper.resolve_source_binding(
            self.repository, reference="selected", target="source.txt"
        )
        tag_binding = helper.resolve_source_binding(
            self.repository, reference="selected-tag", target="source.txt"
        )
        second = commit_file(self.repository, "source.txt", "second\n", "second")
        git(self.repository, "branch", "-f", "selected", second)
        git(self.repository, "tag", "-f", "selected-tag", second)

        self.assertEqual(first, branch_binding["commit_oid"])
        self.assertEqual(first, tag_binding["commit_oid"])
        self.assertEqual(
            b"first\n",
            helper.snapshot_file_entry(
                self.repository, branch_binding, "source.txt"
            ).content,
        )

    def test_default_worktree_source_reports_overlay_identity(self) -> None:
        helper = load_helper()
        commit_file(self.repository, "source.txt", "base\n", "base")
        (self.repository / "source.txt").write_text("dirty one\n", encoding="utf-8")
        (self.repository / "untracked.txt").write_text("untracked\n", encoding="utf-8")

        first = helper.resolve_source_binding(self.repository, target=".")
        (self.repository / "source.txt").write_text("dirty two\n", encoding="utf-8")
        second = helper.resolve_source_binding(self.repository, target=".")

        self.assertEqual("worktree_overlay", first["source_kind"])
        self.assertEqual(first["head_oid"], second["head_oid"])
        self.assertNotEqual(first["overlay_digest"], second["overlay_digest"])
        self.assertIn("untracked.txt", first["overlay_paths"])

    def test_worktree_guidance_read_rejects_drift_and_binds_out_of_target_path(
        self,
    ) -> None:
        helper = load_helper()
        commit_file(self.repository, "source.txt", "base\n", "base")
        (self.repository / "AGENTS.md").write_text("guidance one\n", encoding="utf-8")
        binding = helper.resolve_source_binding(
            self.repository,
            target="source.txt",
            evidence_paths=["AGENTS.md"],
        )
        self.assertIn("AGENTS.md", binding["overlay_paths"])

        (self.repository / "AGENTS.md").write_text("guidance two\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "stale"):
            helper.guidance_snapshot_manifest(self.repository, binding, ["AGENTS.md"])

    def test_worktree_inventory_rejects_head_movement_after_binding(self) -> None:
        helper = load_helper()
        commit_file(self.repository, "source.txt", "base\n", "base")
        binding = helper.resolve_source_binding(self.repository)
        commit_file(self.repository, "second.txt", "second\n", "second")

        with self.assertRaisesRegex(RuntimeError, "stale"):
            helper.inventory_manifest(self.repository, binding)

    def test_initial_worktree_binding_rejects_an_unstable_capture(self) -> None:
        helper = load_helper()
        commit_file(self.repository, "source.txt", "base\n", "base")
        head_oid = git(self.repository, "rev-parse", "HEAD")
        first = helper._worktree_inventory(self.repository, head_oid, ".")
        second = json.loads(json.dumps(first))
        second["overlay_digest"] = "0" * 64

        with (
            patch.object(helper, "_worktree_inventory", side_effect=[first, second]),
            self.assertRaisesRegex(RuntimeError, "stable|changed"),
        ):
            helper.resolve_source_binding(self.repository)

    def test_unavailable_validation_keeps_static_assessment_and_blocks_repair_eligibility(
        self,
    ) -> None:
        helper = load_helper()

        manifest = helper.validation_manifest(
            available=False, reason="The execution boundary is unavailable."
        )

        self.assertEqual("unavailable", manifest["status"])
        self.assertTrue(manifest["static_assessment"]["continue"])
        self.assertFalse(manifest["repair_eligibility"])
        self.assertEqual([], manifest["receipts"])

    def test_selected_commit_guidance_and_architecture_reads_use_selected_tree(
        self,
    ) -> None:
        helper = load_helper()
        commit_file(self.repository, "AGENTS.md", "selected guidance\n", "guidance")
        selected = commit_file(
            self.repository,
            "docs/architecture.md",
            "selected architecture\n",
            "architecture",
        )
        (self.repository / "AGENTS.md").write_text("dirty guidance\n", encoding="utf-8")
        (self.repository / "docs/architecture.md").write_text(
            "dirty architecture\n", encoding="utf-8"
        )
        binding = helper.resolve_source_binding(
            self.repository,
            reference=selected,
            evidence_paths=["AGENTS.md", "docs/architecture.md"],
        )

        entries = helper.guidance_snapshot_manifest(
            self.repository, binding, ["AGENTS.md", "docs/architecture.md"]
        )

        observed = {entry["path"]: entry for entry in entries}
        self.assertEqual(
            hashlib.sha256(b"selected guidance\n").hexdigest(),
            observed["AGENTS.md"]["content_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(b"selected architecture\n").hexdigest(),
            observed["docs/architecture.md"]["content_sha256"],
        )
        self.assertEqual(
            {"selected_commit_tree"},
            {entry["source_kind"] for entry in entries},
        )

    def test_selected_commit_guidance_requires_a_declared_bound_scope(self) -> None:
        helper = load_helper()
        commit_file(self.repository, "source.txt", "source\n", "source")
        selected = commit_file(self.repository, "AGENTS.md", "guidance\n", "guidance")
        undeclared = helper.resolve_source_binding(
            self.repository, reference=selected, target="source.txt"
        )

        with self.assertRaisesRegex(RuntimeError, "outside the bound"):
            helper.guidance_snapshot_manifest(
                self.repository, undeclared, ["AGENTS.md"]
            )

        declared = helper.resolve_source_binding(
            self.repository,
            reference=selected,
            target="source.txt",
            evidence_paths=["AGENTS.md"],
        )
        manifest = helper.guidance_snapshot_manifest(
            self.repository, declared, ["AGENTS.md"]
        )
        self.assertEqual(["AGENTS.md"], [entry["path"] for entry in manifest])

    def test_source_entries_label_selected_commit_and_worktree_sources(self) -> None:
        helper = load_helper()
        selected = commit_file(self.repository, "AGENTS.md", "guidance\n", "base")

        selected_binding = helper.resolve_source_binding(
            self.repository, reference=selected
        )
        worktree_binding = helper.resolve_source_binding(
            self.repository, evidence_paths=["AGENTS.md"]
        )
        selected_entry = helper.guidance_snapshot_manifest(
            self.repository, selected_binding, ["AGENTS.md"]
        )[0]
        worktree_entry = helper.guidance_snapshot_manifest(
            self.repository, worktree_binding, ["AGENTS.md"]
        )[0]

        self.assertEqual("selected_commit_tree", selected_entry["source_kind"])
        self.assertEqual(selected, selected_entry["commit_oid"])
        self.assertEqual("worktree_overlay", worktree_entry["source_kind"])
        self.assertEqual(selected, worktree_entry["head_oid"])

    def test_repair_preflight_rejects_stale_source_or_overlapping_candidate_paths(
        self,
    ) -> None:
        helper = load_helper()
        selected = commit_file(self.repository, "source.txt", "base\n", "base")
        selected_binding = helper.resolve_source_binding(
            self.repository, reference=selected
        )
        selected_report, selected_digest = valid_report(
            helper, self.repository, selected_binding, "source.txt"
        )
        (self.repository / "source.txt").write_text("overlap\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "overlap"):
            helper.repair_preflight(
                self.repository,
                selected_report,
                ["RLG-001"],
                approved_report_digest=selected_digest,
            )

        (self.repository / "source.txt").write_text("base\n", encoding="utf-8")
        preflight = helper.repair_preflight(
            self.repository,
            selected_report,
            ["RLG-001"],
            approved_report_digest=selected_digest,
        )
        self.assertEqual(selected, preflight["isolated_worktree_start_oid"])

        worktree_binding = helper.resolve_source_binding(self.repository)
        worktree_report, worktree_digest = valid_report(
            helper, self.repository, worktree_binding, "source.txt"
        )
        (self.repository / "source.txt").write_text("stale\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "stale"):
            helper.repair_preflight(
                self.repository,
                worktree_report,
                ["RLG-001"],
                approved_report_digest=worktree_digest,
            )

    def test_untrusted_paths_are_confined_before_tree_or_repair_access(self) -> None:
        helper = load_helper()
        for raw_path in (
            "",
            ".",
            "../escape",
            "inside/../escape",
            "/absolute",
            "C:\\absolute",
            "\\\\server\\share",
            ":(glob)**",
            "bad\x00path",
        ):
            with self.subTest(raw_path=raw_path), self.assertRaises(RuntimeError):
                helper.normalize_repo_tree_path(raw_path)

        (self.repository / "target.txt").write_text("target\n", encoding="utf-8")
        os.symlink("target.txt", self.repository / "link.txt")
        git(self.repository, "add", "target.txt", "link.txt")
        git(self.repository, "commit", "-m", "symlink")
        selected = git(self.repository, "rev-parse", "HEAD")
        binding = helper.resolve_source_binding(self.repository, reference=selected)
        with self.assertRaisesRegex(RuntimeError, "symbolic link"):
            helper.snapshot_file_entry(self.repository, binding, "link.txt")

        git(
            self.repository,
            "update-index",
            "--add",
            "--cacheinfo",
            f"160000,{selected},vendor",
        )
        git(self.repository, "commit", "-m", "submodule entry")
        submodule_binding = helper.resolve_source_binding(
            self.repository, reference="HEAD"
        )
        with self.assertRaisesRegex(RuntimeError, "submodule"):
            helper.snapshot_file_entry(self.repository, submodule_binding, "vendor")

    def test_unsafe_or_unresolved_selectors_fail_before_source_access(self) -> None:
        helper = load_helper()
        commit_file(self.repository, "source.txt", "base\n", "base")
        for selector in (
            "",
            "-option",
            "HEAD..HEAD",
            "HEAD:path",
            "HEAD@{1}",
            "HEAD^@",
            "HEAD^!",
            "missing-ref",
        ):
            with self.subTest(selector=selector), self.assertRaises(RuntimeError):
                helper.resolve_source_binding(
                    self.repository, reference=selector, target="source.txt"
                )

    def test_worktree_inventory_records_deleted_files_and_symbolic_links(self) -> None:
        helper = load_helper()
        commit_file(self.repository, "deleted.txt", "delete me\n", "file")
        (self.repository / "target.txt").write_text("target\n", encoding="utf-8")
        os.symlink("target.txt", self.repository / "link.txt")
        (self.repository / "deleted.txt").unlink()

        binding = helper.resolve_source_binding(self.repository)
        inventory = helper.inventory_manifest(self.repository, binding)
        observed = {entry["path"]: entry for entry in inventory["entries"]}

        self.assertEqual("absent", observed["deleted.txt"]["kind"])
        self.assertEqual("symlink", observed["link.txt"]["kind"])
        self.assertEqual("target.txt", observed["link.txt"]["target"])
        with self.assertRaisesRegex(RuntimeError, "symbolic link"):
            helper.guidance_snapshot_manifest(self.repository, binding, ["link.txt"])

    def test_validation_status_requires_honest_receipts(self) -> None:
        helper = load_helper()
        with self.assertRaisesRegex(RuntimeError, "requires a reason"):
            helper.validation_manifest(available=False)

        with self.assertRaisesRegex(RuntimeError, "receipt"):
            helper.validation_manifest(
                available=True,
                source_digest="a" * 64,
                receipts=[{"status": "success", "command": "test"}],
            )

        receipt = {
            "source_digest": "a" * 64,
            "argv": ["just", "test"],
            "environment": {"boundary": "host-enforced"},
            "exit_status": 0,
            "stdout": "passed\n",
            "stderr": "",
        }
        for field in tuple(receipt):
            incomplete_receipt = dict(receipt)
            del incomplete_receipt[field]
            with (
                self.subTest(missing_receipt_field=field),
                self.assertRaisesRegex(RuntimeError, "receipt|source digest"),
            ):
                helper.validation_manifest(
                    available=True,
                    source_digest="a" * 64,
                    receipts=[incomplete_receipt],
                )
        successful = helper.validation_manifest(
            available=True, source_digest="a" * 64, receipts=[receipt]
        )
        failed = helper.validation_manifest(
            available=True,
            source_digest="a" * 64,
            receipts=[{**receipt, "exit_status": 1, "stderr": "failed\n"}],
        )
        empty = helper.validation_manifest(available=True, source_digest="a" * 64)

        self.assertTrue(successful["repair_eligibility"])
        self.assertFalse(failed["repair_eligibility"])
        self.assertFalse(empty["repair_eligibility"])

    def test_repair_preflight_rejects_ineligible_or_incomplete_report(self) -> None:
        helper = load_helper()
        selected = commit_file(self.repository, "source.txt", "base\n", "base")
        source = helper.resolve_source_binding(self.repository, reference=selected)
        incomplete = {
            "schema_version": 1,
            "source": source,
            "validation": helper.validation_manifest(
                available=False, reason="No safe execution boundary."
            ),
            "candidates": [{"id": "RLG-001", "paths": ["source.txt"]}],
        }

        with self.assertRaisesRegex(RuntimeError, "repair-eligible|candidate"):
            helper.repair_preflight(
                self.repository,
                incomplete,
                ["RLG-001"],
                approved_report_digest=helper.assessment_report_digest(incomplete),
            )

    def test_inventory_enforces_path_count_and_file_byte_limits(self) -> None:
        helper = load_helper()
        limits = cast(Any, helper)
        commit_file(self.repository, "one.txt", "1\n", "one")
        (self.repository / "two.txt").write_text("22\n", encoding="utf-8")
        original_path_limit = limits.MAX_PATH_COUNT
        original_file_limit = limits.MAX_FILE_BYTES
        original_total_limit = limits.MAX_TOTAL_BYTES
        original_git_limit = limits.MAX_GIT_OUTPUT_BYTES
        self.addCleanup(setattr, helper, "MAX_PATH_COUNT", original_path_limit)
        self.addCleanup(setattr, helper, "MAX_FILE_BYTES", original_file_limit)
        self.addCleanup(setattr, helper, "MAX_TOTAL_BYTES", original_total_limit)
        self.addCleanup(setattr, helper, "MAX_GIT_OUTPUT_BYTES", original_git_limit)

        limits.MAX_PATH_COUNT = 2
        helper.resolve_source_binding(self.repository)
        limits.MAX_PATH_COUNT = 1
        with self.assertRaisesRegex(RuntimeError, "path limit"):
            helper.resolve_source_binding(self.repository)

        limits.MAX_PATH_COUNT = original_path_limit
        limits.MAX_FILE_BYTES = 3
        helper.resolve_source_binding(self.repository)
        limits.MAX_FILE_BYTES = 2
        with self.assertRaisesRegex(RuntimeError, "file byte limit"):
            helper.resolve_source_binding(self.repository)

        limits.MAX_FILE_BYTES = original_file_limit
        limits.MAX_TOTAL_BYTES = 5
        helper.resolve_source_binding(self.repository)
        limits.MAX_TOTAL_BYTES = 4
        with self.assertRaisesRegex(RuntimeError, "aggregate byte limit"):
            helper.resolve_source_binding(self.repository)

        limits.MAX_TOTAL_BYTES = original_total_limit
        root_output = limits._git_bytes(self.repository, "rev-parse", "--show-toplevel")
        limits.MAX_GIT_OUTPUT_BYTES = len(root_output)
        self.assertEqual(
            root_output,
            limits._git_bytes(self.repository, "rev-parse", "--show-toplevel"),
        )
        limits.MAX_GIT_OUTPUT_BYTES = len(root_output) - 1
        with self.assertRaisesRegex(RuntimeError, "output limit"):
            limits._git_bytes(self.repository, "rev-parse", "--show-toplevel")

    def test_git_read_timeout_includes_process_exit_after_output_closes(self) -> None:
        helper = load_helper()
        limits = cast(Any, helper)
        original_timeout = limits.GIT_TIMEOUT_SECONDS
        self.addCleanup(setattr, helper, "GIT_TIMEOUT_SECONDS", original_timeout)
        limits.GIT_TIMEOUT_SECONDS = 0.3
        bin_directory = self.repository / "bin"
        bin_directory.mkdir()
        fake_git = bin_directory / "git"
        fake_git.write_text(
            "#!/usr/bin/env python3\n"
            "import os\n"
            "import time\n"
            "os.close(1)\n"
            "os.close(2)\n"
            "time.sleep(1)\n",
            encoding="utf-8",
        )
        fake_git.chmod(0o755)

        started = time.monotonic()
        with (
            patch.dict(
                os.environ,
                {"PATH": f"{bin_directory}{os.pathsep}{os.environ['PATH']}"},
            ),
            self.assertRaisesRegex(RuntimeError, "time limit"),
        ):
            limits._git_bytes(self.repository, "rev-parse", "--show-toplevel")

        self.assertLess(time.monotonic() - started, 0.7)

    def test_git_reader_error_cannot_become_partial_success(self) -> None:
        helper = load_helper()
        limits = cast(Any, helper)

        class FailingStream:
            def read(self, size: int) -> bytes:
                del size
                raise OSError("synthetic pipe read failure")

            def close(self) -> None:
                return None

        class EmptyStream:
            def read(self, size: int) -> bytes:
                del size
                return b""

            def close(self) -> None:
                return None

        class FakeProcess:
            def __init__(self) -> None:
                self.stdout = FailingStream()
                self.stderr = EmptyStream()
                self.returncode: int | None = None
                self.killed = False

            def poll(self) -> int | None:
                return self.returncode

            def kill(self) -> None:
                self.killed = True
                self.returncode = -9

            def wait(self, timeout: float | None = None) -> int:
                del timeout
                if self.returncode is None:
                    self.returncode = 0
                return self.returncode

        process = FakeProcess()
        with (
            patch.object(limits.subprocess, "Popen", return_value=process),
            self.assertRaisesRegex(RuntimeError, "read.*failed") as raised,
        ):
            limits._git_bytes(self.repository, "status", "--porcelain=v1")

        self.assertIsInstance(raised.exception.__cause__, OSError)
        self.assertTrue(process.killed)

    def test_git_failure_reports_when_the_process_cannot_be_reaped(self) -> None:
        helper = load_helper()
        limits = cast(Any, helper)

        class EmptyStream:
            def read(self, size: int) -> bytes:
                del size
                return b""

            def close(self) -> None:
                return None

        class FakeProcess:
            def __init__(self) -> None:
                self.stdout = EmptyStream()
                self.stderr = EmptyStream()
                self.killed = False

            def poll(self) -> None:
                return None

            def kill(self) -> None:
                self.killed = True

            def wait(self, timeout: float | None = None) -> int:
                raise subprocess.TimeoutExpired(
                    "git", timeout if timeout is not None else 0.0
                )

        process = FakeProcess()
        with (
            patch.object(limits.subprocess, "Popen", return_value=process),
            self.assertRaisesRegex(RuntimeError, "reap") as raised,
        ):
            limits._git_bytes(self.repository, "status", "--porcelain=v1")

        self.assertIsInstance(raised.exception.__cause__, RuntimeError)
        self.assertTrue(process.killed)

    def test_repair_preflight_binds_candidate_content_scope_and_dependencies(
        self,
    ) -> None:
        helper = load_helper()
        commit_file(self.repository, "source.txt", "base\n", "base")
        (self.repository / "outside.txt").write_text("outside\n", encoding="utf-8")
        source = helper.resolve_source_binding(self.repository, target="source.txt")
        report, report_digest = valid_report(
            helper, self.repository, source, "source.txt"
        )

        changed = json.loads(json.dumps(report))
        changed["candidates"][0]["correction"]["summary"] = "Different correction."
        with self.assertRaisesRegex(RuntimeError, "approved assessment report"):
            helper.repair_preflight(
                self.repository,
                changed,
                ["RLG-001"],
                approved_report_digest=report_digest,
            )

        outside = json.loads(json.dumps(report))
        outside_candidate = outside["candidates"][0]
        outside_candidate["paths"] = ["outside.txt"]
        outside_candidate["evidence"] = [
            {
                "path": "outside.txt",
                "content_sha256": hashlib.sha256(b"outside\n").hexdigest(),
            }
        ]
        with self.assertRaisesRegex(RuntimeError, "outside the assessed scope"):
            helper.repair_preflight(
                self.repository,
                outside,
                ["RLG-001"],
                approved_report_digest=helper.assessment_report_digest(outside),
            )

        dependent = json.loads(json.dumps(report))
        dependent["candidates"][0]["dependencies"] = ["RLG-002"]
        with self.assertRaisesRegex(RuntimeError, "dependency"):
            helper.repair_preflight(
                self.repository,
                dependent,
                ["RLG-001"],
                approved_report_digest=helper.assessment_report_digest(dependent),
            )

        resolved = json.loads(json.dumps(report))
        prerequisite = json.loads(json.dumps(resolved["candidates"][0]))
        prerequisite["id"] = "RLG-002"
        prerequisite["status"] = "resolved"
        resolved["candidates"][0]["dependencies"] = ["RLG-002"]
        resolved["candidates"].append(prerequisite)
        result = helper.repair_preflight(
            self.repository,
            resolved,
            ["RLG-001"],
            approved_report_digest=helper.assessment_report_digest(resolved),
        )
        self.assertEqual("eligible", result["status"])

    def test_repair_preflight_requires_the_supported_report_schema(self) -> None:
        helper = load_helper()
        selected = commit_file(self.repository, "source.txt", "base\n", "base")
        source = helper.resolve_source_binding(self.repository, reference=selected)
        report, _ = valid_report(helper, self.repository, source, "source.txt")

        for value in (None, True, "1", 0, 2):
            changed = json.loads(json.dumps(report))
            if value is None:
                del changed["schema_version"]
            else:
                changed["schema_version"] = value
            with (
                self.subTest(schema_version=value),
                self.assertRaisesRegex(RuntimeError, "schema version"),
            ):
                helper.repair_preflight(
                    self.repository,
                    changed,
                    ["RLG-001"],
                    approved_report_digest=helper.assessment_report_digest(changed),
                )

    def test_repair_preflight_rejects_cycles_and_orders_dependencies(self) -> None:
        helper = load_helper()
        selected = commit_file(self.repository, "source.txt", "base\n", "base")
        source = helper.resolve_source_binding(self.repository, reference=selected)
        report, _ = valid_report(helper, self.repository, source, "source.txt")

        self_dependent = json.loads(json.dumps(report))
        self_dependent["candidates"][0]["dependencies"] = ["RLG-001"]
        with self.assertRaisesRegex(RuntimeError, "dependency"):
            helper.repair_preflight(
                self.repository,
                self_dependent,
                ["RLG-001"],
                approved_report_digest=helper.assessment_report_digest(self_dependent),
            )

        cyclic = json.loads(json.dumps(report))
        second_candidate = json.loads(json.dumps(cyclic["candidates"][0]))
        second_candidate["id"] = "RLG-002"
        second_candidate["dependencies"] = ["RLG-001"]
        cyclic["candidates"][0]["dependencies"] = ["RLG-002"]
        cyclic["candidates"].append(second_candidate)
        with self.assertRaisesRegex(RuntimeError, "cyclic"):
            helper.repair_preflight(
                self.repository,
                cyclic,
                ["RLG-001", "RLG-002"],
                approved_report_digest=helper.assessment_report_digest(cyclic),
            )

        ordered = json.loads(json.dumps(report))
        prerequisite = json.loads(json.dumps(ordered["candidates"][0]))
        prerequisite["id"] = "RLG-002"
        ordered["candidates"][0]["dependencies"] = ["RLG-002"]
        ordered["candidates"].append(prerequisite)
        result = helper.repair_preflight(
            self.repository,
            ordered,
            ["RLG-001", "RLG-002"],
            approved_report_digest=helper.assessment_report_digest(ordered),
        )
        self.assertEqual(["RLG-002", "RLG-001"], result["candidate_ids"])

    def test_repair_preflight_rejects_invalid_candidate_and_source_contracts(
        self,
    ) -> None:
        helper = load_helper()
        selected = commit_file(self.repository, "source.txt", "base\n", "base")
        source = helper.resolve_source_binding(self.repository, reference=selected)
        report, report_digest = valid_report(
            helper, self.repository, source, "source.txt"
        )
        for candidate_ids in ([], ["RLG-001", "RLG-001"], ["all"], ["RLG-999"]):
            with (
                self.subTest(candidate_ids=candidate_ids),
                self.assertRaises(RuntimeError),
            ):
                helper.repair_preflight(
                    self.repository,
                    report,
                    candidate_ids,
                    approved_report_digest=report_digest,
                )

        malformed_reports: tuple[dict[str, object], ...] = (
            {},
            {"source": source, "candidates": "not-a-list"},
            {"source": source, "candidates": ["not-an-object"]},
            {
                "source": source,
                "candidates": [{"id": "RLG-001", "paths": []}],
            },
            {
                "source": source,
                "candidates": [
                    {"id": "RLG-001", "paths": ["source.txt"]},
                    {"id": "RLG-001", "paths": ["source.txt"]},
                ],
            },
        )
        for malformed in malformed_reports:
            with (
                self.subTest(report=malformed),
                self.assertRaises((RuntimeError, TypeError)),
            ):
                helper.repair_preflight(
                    self.repository,
                    malformed,
                    ["RLG-001"],
                    approved_report_digest=helper.assessment_report_digest(malformed),
                )

        stale_source = dict(source)
        stale_source["tree_oid"] = "0" * 40
        with self.assertRaisesRegex(RuntimeError, "stale"):
            helper.repair_preflight(
                self.repository,
                {**report, "source": stale_source},
                ["RLG-001"],
                approved_report_digest=helper.assessment_report_digest(
                    {**report, "source": stale_source}
                ),
            )
        with self.assertRaisesRegex(RuntimeError, "source kind"):
            helper.inventory_manifest(
                self.repository, {"source_kind": "unknown", "target": "."}
            )

    def test_snapshot_reads_reject_missing_paths_and_worktree_bindings(self) -> None:
        helper = load_helper()
        selected = commit_file(self.repository, "source.txt", "base\n", "base")
        selected_binding = helper.resolve_source_binding(
            self.repository, reference=selected
        )
        worktree_binding = helper.resolve_source_binding(self.repository)

        with self.assertRaisesRegex(RuntimeError, "selected-commit binding"):
            helper.snapshot_file_entry(self.repository, worktree_binding, "source.txt")
        with self.assertRaisesRegex(RuntimeError, "not one file"):
            helper.snapshot_file_entry(self.repository, selected_binding, "missing.txt")

    def test_selected_repair_preflight_verifies_complete_source_binding(self) -> None:
        helper = load_helper()
        selected = commit_file(self.repository, "source.txt", "base\n", "base")
        source = helper.resolve_source_binding(self.repository, reference=selected)
        report, _ = valid_report(helper, self.repository, source, "source.txt")

        for field, value in (
            ("source_digest", "0" * 64),
            ("repository_root", "/different/repository"),
            ("selector", 7),
        ):
            changed_source = dict(source)
            changed_source[field] = value
            with (
                self.subTest(field=field),
                self.assertRaises((RuntimeError, TypeError)),
            ):
                changed_report = {**report, "source": changed_source}
                helper.repair_preflight(
                    self.repository,
                    changed_report,
                    ["RLG-001"],
                    approved_report_digest=helper.assessment_report_digest(
                        changed_report
                    ),
                )

    def test_repository_root_input_must_name_the_repository_root(self) -> None:
        helper = load_helper()
        commit_file(self.repository, "nested/source.txt", "base\n", "base")

        with self.assertRaisesRegex(RuntimeError, "not the repository root"):
            helper.resolve_source_binding(self.repository / "nested")

    def test_assessment_mode_is_read_only_and_does_not_invoke_write_capabilities(
        self,
    ) -> None:
        helper = load_helper()
        selected = commit_file(self.repository, "source.txt", "base\n", "base")
        (self.repository / "source.txt").write_text("dirty\n", encoding="utf-8")
        (self.repository / "untracked.txt").write_text("untracked\n", encoding="utf-8")
        before_status = subprocess.run(
            ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
            cwd=self.repository,
            check=True,
            capture_output=True,
        ).stdout
        before_refs = git(self.repository, "show-ref")

        selected_binding = helper.resolve_source_binding(
            self.repository, reference=selected
        )
        helper.inventory_manifest(self.repository, selected_binding)
        helper.guidance_snapshot_manifest(
            self.repository, selected_binding, ["source.txt"]
        )
        helper.resolve_source_binding(self.repository)

        after_status = subprocess.run(
            ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
            cwd=self.repository,
            check=True,
            capture_output=True,
        ).stdout
        self.assertEqual(before_status, after_status)
        self.assertEqual(before_refs, git(self.repository, "show-ref"))

    def test_cli_emits_one_bound_static_assessment_manifest(self) -> None:
        commit_file(self.repository, "source.txt", "base\n", "base")

        result = subprocess.run(
            [sys.executable, str(HELPER), "bind", "source.txt", "--ref", "HEAD"],
            cwd=self.repository,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        document = json.loads(result.stdout)
        self.assertEqual("selected_commit_tree", document["source"]["source_kind"])
        self.assertEqual("unavailable", document["validation"]["status"])
        self.assertTrue(document["validation"]["static_assessment"]["continue"])

    def test_cli_verifies_repair_preflight_and_reports_invalid_json(self) -> None:
        helper = load_helper()
        selected = commit_file(self.repository, "source.txt", "base\n", "base")
        source = helper.resolve_source_binding(self.repository, reference=selected)
        report, report_digest = valid_report(
            helper, self.repository, source, "source.txt"
        )
        report_path = self.repository / "report.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        original_directory = Path.cwd()
        self.addCleanup(os.chdir, original_directory)
        os.chdir(self.repository)

        output = StringIO()
        with redirect_stdout(output):
            returncode = helper.main(
                [
                    "repair-preflight",
                    str(report_path),
                    "--candidate",
                    "RLG-001",
                    "--approved-report-digest",
                    report_digest,
                ]
            )
        self.assertEqual(0, returncode)
        self.assertEqual("eligible", json.loads(output.getvalue())["status"])

        report_path.write_text("not-json\n", encoding="utf-8")
        errors = StringIO()
        with redirect_stderr(errors):
            returncode = helper.main(
                [
                    "repair-preflight",
                    str(report_path),
                    "--candidate",
                    "RLG-001",
                    "--approved-report-digest",
                    report_digest,
                ]
            )
        self.assertEqual(1, returncode)
        self.assertIn("error:", errors.getvalue())
        self.assertNotIn("Traceback", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
