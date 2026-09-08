"""Behavior tests for realign assessment-source binding."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from functools import lru_cache
from io import StringIO
from pathlib import Path
from types import ModuleType

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
        binding = helper.resolve_source_binding(self.repository, reference=selected)

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

    def test_source_entries_label_selected_commit_and_worktree_sources(self) -> None:
        helper = load_helper()
        selected = commit_file(self.repository, "AGENTS.md", "guidance\n", "base")

        selected_binding = helper.resolve_source_binding(
            self.repository, reference=selected
        )
        worktree_binding = helper.resolve_source_binding(self.repository)
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
        selected_report = {
            "source": selected_binding,
            "candidates": [{"id": "RLG-001", "paths": ["source.txt"]}],
        }
        (self.repository / "source.txt").write_text("overlap\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "overlap"):
            helper.repair_preflight(self.repository, selected_report, ["RLG-001"])

        (self.repository / "source.txt").write_text("base\n", encoding="utf-8")
        preflight = helper.repair_preflight(
            self.repository, selected_report, ["RLG-001"]
        )
        self.assertEqual(selected, preflight["isolated_worktree_start_oid"])

        worktree_binding = helper.resolve_source_binding(self.repository)
        worktree_report = {
            "source": worktree_binding,
            "candidates": [{"id": "RLG-001", "paths": ["source.txt"]}],
        }
        (self.repository / "source.txt").write_text("stale\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "stale"):
            helper.repair_preflight(self.repository, worktree_report, ["RLG-001"])

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

        successful = helper.validation_manifest(
            available=True, receipts=[{"status": "success", "command": "test"}]
        )
        failed = helper.validation_manifest(
            available=True, receipts=[{"status": "failed", "command": "test"}]
        )
        empty = helper.validation_manifest(available=True)

        self.assertTrue(successful["repair_eligibility"])
        self.assertFalse(failed["repair_eligibility"])
        self.assertFalse(empty["repair_eligibility"])

    def test_repair_preflight_rejects_invalid_candidate_and_source_contracts(
        self,
    ) -> None:
        helper = load_helper()
        selected = commit_file(self.repository, "source.txt", "base\n", "base")
        source = helper.resolve_source_binding(self.repository, reference=selected)
        report = {
            "source": source,
            "candidates": [{"id": "RLG-001", "paths": ["source.txt"]}],
        }
        for candidate_ids in ([], ["RLG-001", "RLG-001"], ["all"], ["RLG-999"]):
            with (
                self.subTest(candidate_ids=candidate_ids),
                self.assertRaises(RuntimeError),
            ):
                helper.repair_preflight(self.repository, report, candidate_ids)

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
                helper.repair_preflight(self.repository, malformed, ["RLG-001"])

        stale_source = dict(source)
        stale_source["tree_oid"] = "0" * 40
        with self.assertRaisesRegex(RuntimeError, "stale"):
            helper.repair_preflight(
                self.repository,
                {"source": stale_source, "candidates": report["candidates"]},
                ["RLG-001"],
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
        candidate = [{"id": "RLG-001", "paths": ["source.txt"]}]

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
                helper.repair_preflight(
                    self.repository,
                    {"source": changed_source, "candidates": candidate},
                    ["RLG-001"],
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
        report_path = self.repository / "report.json"
        report_path.write_text(
            json.dumps(
                {
                    "source": source,
                    "candidates": [{"id": "RLG-001", "paths": ["source.txt"]}],
                }
            ),
            encoding="utf-8",
        )
        original_directory = Path.cwd()
        self.addCleanup(os.chdir, original_directory)
        os.chdir(self.repository)

        output = StringIO()
        with redirect_stdout(output):
            returncode = helper.main(
                ["repair-preflight", str(report_path), "--candidate", "RLG-001"]
            )
        self.assertEqual(0, returncode)
        self.assertEqual("eligible", json.loads(output.getvalue())["status"])

        report_path.write_text("not-json\n", encoding="utf-8")
        errors = StringIO()
        with redirect_stderr(errors):
            returncode = helper.main(
                ["repair-preflight", str(report_path), "--candidate", "RLG-001"]
            )
        self.assertEqual(1, returncode)
        self.assertIn("error:", errors.getvalue())
        self.assertNotIn("Traceback", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
