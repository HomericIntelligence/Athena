"""Exercise helpers from installed artifacts without the source checkout."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

import pytest

from scripts.package_opencode import stage_package
from scripts.package_plugin import build_package

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.nightly


@unittest.skipUnless(shutil.which("node"), "Installation requires Node.js")
class InstalledSkillHelperTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source"
        shutil.copytree(
            ROOT,
            self.source,
            ignore=shutil.ignore_patterns(
                ".git",
                ".venv",
                "dist",
                "__pycache__",
                ".coverage*",
                ".mypy_cache",
                ".ruff_cache",
                ".pytest_cache",
            ),
        )
        self.cwd = self.root / "unrelated"
        self.cwd.mkdir()
        self.environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("PYTHON")
        }
        self.environment["XDG_CONFIG_HOME"] = str(self.root / "config")

    def corpus_snapshot(self, corpus: Path) -> dict[str, bytes | None]:
        """Return the installed path inventory and exact file content."""
        return {
            path.relative_to(corpus).as_posix(): None
            if path.is_dir()
            else path.read_bytes()
            for path in sorted(corpus.rglob("*"))
        }

    def install(self) -> Path:
        staged = stage_package(self.source, self.root / "staged")
        script = (
            f"import {{ syncSkills }} from {json.dumps((staged / 'plugin.js').as_uri())};"
            "process.stdout.write(syncSkills());"
        )
        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=self.cwd,
            env=self.environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return Path(result.stdout)

    def run_helper(
        self,
        corpus: Path,
        relative: str,
        *arguments: str,
        input_text: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(corpus / relative), *arguments],
            cwd=self.cwd,
            env=self.environment,
            input=input_text,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )

    def assert_review_exchange_runtime(self, corpus: Path) -> None:
        reduction_request = {
            "previous": None,
            "event": {
                "event_type": "reviewer_assessment",
                "exchange_id": "installed-exchange",
                "prior_state_sha256": None,
                "round": 1,
                "surface": "pull_request",
                "target": {
                    "provider": "github",
                    "repository": "example/project",
                    "number": 7,
                    "url": "https://github.com/example/project/pull/7",
                },
                "requirements_sha256": "a" * 64,
                "supersedes_state_sha256": None,
                "artifact_binding": {
                    "revision": "head-7",
                    "sha256": "b" * 64,
                    "visible_content_sha256": "c" * 64,
                },
                "scope": ["path:src/example.py"],
                "coverage_complete": True,
                "go_eligible": True,
                "responses": [],
                "new_findings": [],
                "stop_reason": None,
            },
        }
        reduced = self.run_helper(
            corpus,
            "review-exchange/scripts/review_exchange.py",
            "reduce",
            "-",
            input_text=json.dumps(reduction_request),
        )
        self.assertEqual(0, reduced.returncode, reduced.stderr)
        reduction_result = json.loads(reduced.stdout)
        self.assertEqual("accepted", reduction_result["status"])
        envelope = reduction_result["envelope"]
        self.assertEqual("GO", envelope["state"]["verdict"])

        verified = self.run_helper(
            corpus,
            "review-exchange/scripts/review_exchange.py",
            "verify",
            "-",
            input_text=json.dumps(envelope),
        )
        self.assertEqual(0, verified.returncode, verified.stderr)
        self.assertEqual(envelope, json.loads(verified.stdout))

        issue_snapshot = {
            "schema_id": "athena.issue-exchange.snapshot",
            "schema_version": 1,
            "target": {
                "provider": "github",
                "host": "github.com",
                "repository": "example/project",
                "issue_id": "I_7",
                "number": 7,
                "url": "https://github.com/example/project/issues/7",
            },
            "actor": {"id": "actor-7", "login": "reviewer"},
            "issue": {
                "state": "open",
                "title": "Bound the review exchange",
                "body": "Implement the bounded exchange.",
                "acceptance_criteria": [],
            },
            "comments": [],
            "comments_complete": True,
        }
        inspected = self.run_helper(
            corpus,
            "review-exchange/scripts/issue_exchange.py",
            "inspect",
            "-",
            input_text=json.dumps(issue_snapshot),
        )
        self.assertEqual(0, inspected.returncode, inspected.stderr)
        inspection_result = json.loads(inspected.stdout)
        self.assertEqual("ready", inspection_result["status"])
        self.assertEqual("prepare_plan", inspection_result["next_action"])

    def test_installed_selector_help_without_repository_imports(self) -> None:
        corpus = self.install()
        result = self.run_helper(
            corpus, "advise/scripts/list_retrievable_skills.py", "--help"
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("knowledge_root", result.stdout)

    def test_review_exchange_runtime_does_not_modify_the_installed_corpus(
        self,
    ) -> None:
        corpus = self.install()
        before = self.corpus_snapshot(corpus)

        self.assert_review_exchange_runtime(corpus)

        self.assertEqual(before, self.corpus_snapshot(corpus))

    def test_installed_resolver_reports_its_artifact_version(self) -> None:
        corpus = self.install()
        version = json.loads((self.source / ".codex-plugin/plugin.json").read_text())[
            "version"
        ]
        result = self.run_helper(
            corpus, "advise/scripts/resolve_knowledge_checkout.py", "--version"
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(f"resolve_knowledge_checkout.py {version}\n", result.stdout)

    def test_all_installed_helpers_use_their_own_corpus(self) -> None:
        helpers = sorted(
            path.relative_to(self.source / "skills").as_posix()
            for path in (self.source / "skills").glob("*/scripts/*.py")
            if path.read_text().startswith("#!/usr/bin/env python3\n")
        )
        self.assertIn("advise/scripts/list_retrievable_skills.py", helpers)
        self.assertIn("advise/scripts/resolve_knowledge_checkout.py", helpers)
        self.assertIn("pr-review/scripts/collect_evidence.py", helpers)
        self.assertIn("realign/scripts/resolve_assessment.py", helpers)
        self.assertIn("review-exchange/scripts/issue_exchange.py", helpers)
        self.assertIn("review-exchange/scripts/review_exchange.py", helpers)
        versions = ("1.2.3-rc.1+build.42", "2.0.0+second")
        installations: list[tuple[Path, str]] = []
        for index, version in enumerate(versions):
            for relative in (
                ".codex-plugin/plugin.json",
                "npm/athena-opencode/package.json",
            ):
                path = self.source / relative
                manifest = json.loads(path.read_text())
                manifest["version"] = version
                path.write_text(json.dumps(manifest), encoding="utf-8")
            self.environment["XDG_CONFIG_HOME"] = str(self.root / f"config-{index}")
            neighbor = (
                self.root / f"config-{index}" / "opencode/skills/neighbor/SKILL.md"
            )
            neighbor.parent.mkdir(parents=True)
            neighbor.write_text("Retain this neighboring skill.\n", encoding="utf-8")
            installations.append((self.install(), version))
            self.assertEqual("Retain this neighboring skill.\n", neighbor.read_text())
        self.source.rename(self.root / "unavailable-source")
        (self.root / "staged").rename(self.root / "unavailable-staging")
        sentinel = self.cwd / "skills"
        sentinel.mkdir()
        (sentinel / "__init__.py").write_text(
            "raise RuntimeError('Unrelated skills package')\n"
        )
        (self.cwd / "_cli.py").write_text(
            "raise RuntimeError('Unrelated CLI module')\n"
        )
        self.environment["PYTHONPATH"] = str(self.cwd)
        for corpus, version in installations:
            for helper in helpers:
                for argument in ("--help", "--version"):
                    with self.subTest(corpus=corpus, helper=helper, argument=argument):
                        result = self.run_helper(corpus, helper, argument)
                        self.assertEqual(0, result.returncode, result.stderr)
                        if argument == "--version":
                            self.assertEqual(
                                f"{Path(helper).name} {version}\n", result.stdout
                            )
            with self.subTest(corpus=corpus, operation="review-exchange-runtime"):
                self.assert_review_exchange_runtime(corpus)
        knowledge = self.root / "knowledge/skills"
        knowledge.mkdir(parents=True)
        for name in ("z.md", "a.md", "a.notes.md", "a.history.md"):
            (knowledge / name).write_text("fixture\n", encoding="utf-8")
        result = self.run_helper(
            installations[0][0],
            "advise/scripts/list_retrievable_skills.py",
            str(knowledge.parent),
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("skills/a.md\nskills/z.md\n", result.stdout)

    def test_invalid_installed_metadata_never_uses_parent_metadata(self) -> None:
        corpus = self.install()
        parent = corpus.parent / ".codex-plugin/plugin.json"
        parent.parent.mkdir()
        parent.write_text('{"version":"99.0.0"}\n', encoding="utf-8")
        metadata = corpus / "_plugin.json"
        for contents in (
            None,
            b"invalid",
            b"\xff",
            b"[]",
            b"{}",
            b'{"version":null}',
            b'{"version":7}',
            b'{"version":""}',
            b'{"version":"  "}',
        ):
            with self.subTest(contents=contents):
                if contents is None:
                    metadata.unlink()
                else:
                    metadata.write_bytes(contents)
                result = self.run_helper(
                    corpus, "advise/scripts/resolve_knowledge_checkout.py", "--version"
                )
                self.assertEqual(1, result.returncode)
                self.assertEqual("", result.stdout)
                self.assertTrue(result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                help_result = self.run_helper(
                    corpus, "advise/scripts/resolve_knowledge_checkout.py", "--help"
                )
                self.assertEqual(0, help_result.returncode, help_result.stderr)

    def test_generated_metadata_conflict_preserves_existing_output(self) -> None:
        from scripts.package_plugin import PackageError

        staged = self.root / "staged"
        staged.mkdir()
        sentinel = staged / "keep.txt"
        sentinel.write_text("existing output\n", encoding="utf-8")
        (self.source / "skills/_plugin.json").write_text('{"version":"99.0.0"}\n')
        with self.assertRaises(PackageError):
            stage_package(self.source, staged)
        self.assertEqual("existing output\n", sentinel.read_text())

    def test_portable_archive_helpers_keep_their_version_contract(self) -> None:
        archive, _ = build_package(self.source, self.root / "archives")
        extracted = self.root / "portable"
        with tarfile.open(archive) as bundle:
            bundle.extractall(extracted, filter="data")
        self.source.rename(self.root / "unavailable-source")
        sentinel = self.cwd / "skills"
        sentinel.mkdir()
        (sentinel / "__init__.py").write_text(
            "raise RuntimeError('Unrelated skills package')\n"
        )
        (self.cwd / "_cli.py").write_text(
            "raise RuntimeError('Unrelated CLI module')\n"
        )
        self.environment["PYTHONPATH"] = str(self.cwd)
        corpus = extracted / "skills"
        version = json.loads((extracted / ".codex-plugin/plugin.json").read_text())[
            "version"
        ]
        for helper in sorted(corpus.glob("*/scripts/*.py")):
            if not helper.read_text().startswith("#!/usr/bin/env python3\n"):
                continue
            for argument in ("--help", "--version"):
                with self.subTest(helper=helper.name, argument=argument):
                    result = self.run_helper(
                        corpus, helper.relative_to(corpus).as_posix(), argument
                    )
                    self.assertEqual(0, result.returncode, result.stderr)
                    if argument == "--version":
                        self.assertEqual(f"{helper.name} {version}\n", result.stdout)
        self.assert_review_exchange_runtime(corpus)
