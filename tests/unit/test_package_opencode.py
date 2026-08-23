"""Unit tests for scripts/package_opencode.py."""

from __future__ import annotations

import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "package_opencode.py"
SPEC = importlib.util.spec_from_file_location("athena_package_opencode", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
package_opencode = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package_opencode)


class PackageOpenCodeTests(unittest.TestCase):
    """Exercise the opencode npm package staging contract."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.fixture = Path(self.temporary_directory.name) / "Athena"
        shutil.copytree(
            ROOT,
            self.fixture,
            ignore=shutil.ignore_patterns(
                ".git",
                ".venv",
                "dist",
                "build",
                "__pycache__",
                "*.pyc",
                ".coverage*",
            ),
        )

    def stage(self) -> Path:
        staged: Path = package_opencode.stage_package(
            self.fixture, self.fixture / "staged-npm"
        )
        return staged

    def test_staging_copies_plugin_legal_files_and_skill_corpus(self) -> None:
        staged = self.stage()

        manifest = json.loads((staged / "package.json").read_text(encoding="utf-8"))
        self.assertEqual("opencode-athena", manifest["name"])
        self.assertTrue((staged / "plugin.js").is_file())
        self.assertTrue((staged / "README.md").is_file())
        self.assertTrue((staged / "LICENSE").is_file())
        self.assertTrue((staged / "NOTICE").is_file())
        self.assertTrue((staged / "skills" / "_cli.py").is_file())
        self.assertTrue((staged / "skills" / "advise" / "SKILL.md").is_file())

    def test_staging_skips_generated_python_cache(self) -> None:
        cache = self.fixture / "skills" / "advise" / "scripts" / "__pycache__"
        cache.mkdir(parents=True)
        (cache / "helper.pyc").write_bytes(b"")

        staged = self.stage()

        self.assertFalse(
            (staged / "skills" / "advise" / "scripts" / "__pycache__").exists()
        )

    def test_version_mismatch_fails_closed(self) -> None:
        manifest = self.fixture / "npm" / "opencode-athena" / "package.json"
        document = json.loads(manifest.read_text(encoding="utf-8"))
        document["version"] = "9.9.9"
        manifest.write_text(json.dumps(document), encoding="utf-8")

        with self.assertRaises(package_opencode.PackageError) as context:
            self.stage()
        self.assertIn("differs from host manifests", str(context.exception))

    def test_symlinked_source_fails_closed(self) -> None:
        external = self.fixture.parent / "external-plugin.js"
        external.write_text("export default () => ({});\n", encoding="utf-8")
        entry = self.fixture / "npm" / "opencode-athena" / "plugin.js"
        entry.unlink()
        entry.symlink_to(external)

        with self.assertRaises(package_opencode.PackageError) as context:
            self.stage()
        self.assertIn("symlink", str(context.exception))

    def test_existing_output_is_replaced(self) -> None:
        output = self.fixture / "staged-npm"
        output.mkdir()
        stale = output / "stale.txt"
        stale.write_text("stale\n", encoding="utf-8")

        staged = self.stage()

        self.assertFalse(stale.exists())
        self.assertTrue((staged / "plugin.js").is_file())

    def test_cli_reports_stage_success_and_errors(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = package_opencode.main(["--root", str(self.fixture)])
        self.assertEqual(0, code)
        self.assertIn("Staged OpenCode npm package", stdout.getvalue())

        broken = self.fixture / "broken"
        shutil.copytree(
            self.fixture,
            broken,
            ignore=shutil.ignore_patterns(
                ".git", ".venv", "dist", "build", "__pycache__", "*.pyc"
            ),
        )
        manifest = broken / "npm" / "opencode-athena" / "package.json"
        document = json.loads(manifest.read_text(encoding="utf-8"))
        document["version"] = "not-semver"
        manifest.write_text(json.dumps(document), encoding="utf-8")
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = package_opencode.main(["--root", str(broken)])
        self.assertEqual(1, code)
        self.assertIn("error:", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
