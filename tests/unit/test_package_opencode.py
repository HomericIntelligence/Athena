"""Unit tests for scripts/package_opencode.py."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from . import package_markdown_helpers as md

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.nightly
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

    def artifact_snapshot(self, artifact: Path) -> dict[str, bytes | None]:
        """Return the artifact path inventory and exact file content."""
        return {
            path.relative_to(artifact).as_posix(): None
            if path.is_dir()
            else path.read_bytes()
            for path in sorted(artifact.rglob("*"))
        }

    def assert_local_links_resolve(self, artifact_root: Path) -> None:
        """Require each local Markdown target to exist in the artifact."""
        artifact_root = artifact_root.resolve()
        checked = 0
        unresolved: list[str] = []
        for markdown_path in sorted(artifact_root.rglob("*.md")):
            for target, fragment in md.local_markdown_targets(
                markdown_path.read_text(encoding="utf-8")
            ):
                checked += 1
                resolved = (
                    (markdown_path.parent / target).resolve()
                    if target
                    else markdown_path
                )
                source = markdown_path.relative_to(artifact_root)
                if not resolved.is_relative_to(artifact_root):
                    unresolved.append(f"{source} -> {target} (outside artifact)")
                elif not resolved.exists():
                    unresolved.append(f"{source} -> {target} (target does not exist)")
                elif fragment and resolved.suffix.casefold() == ".md":
                    anchors = md.markdown_anchors(resolved.read_text(encoding="utf-8"))
                    if fragment.casefold() not in anchors:
                        unresolved.append(
                            f"{source} -> {target}#{fragment} (anchor does not exist)"
                        )

        self.assertGreater(checked, 0, "The artifact has no local Markdown links.")
        self.assertEqual([], unresolved)

    def test_staging_copies_plugin_legal_files_and_skill_corpus(self) -> None:
        staged = self.stage()

        manifest = json.loads((staged / "package.json").read_text(encoding="utf-8"))
        self.assertEqual("@homericintelligence/athena-opencode", manifest["name"])
        self.assertTrue((staged / "plugin.js").is_file())
        self.assertTrue((staged / "README.md").is_file())
        self.assertTrue((staged / "LICENSE").is_file())
        self.assertTrue((staged / "NOTICE").is_file())
        self.assertTrue((staged / "skills" / "_cli.py").is_file())
        self.assertTrue((staged / "skills" / "advise" / "SKILL.md").is_file())
        self.assertTrue(
            (staged / "skills" / "pr-review" / "scripts" / "delivery.py").is_file()
        )

    def test_staged_local_markdown_links_resolve_inside_the_package(self) -> None:
        """The staged package contains each local Markdown link target."""
        self.assert_local_links_resolve(self.stage())

    @unittest.skipUnless(shutil.which("node"), "Skill inventory requires Node.js")
    def test_bundled_skill_inventory_excludes_support_content(self) -> None:
        """Only directories with a skill entrypoint appear in the plugin inventory."""
        staged = self.stage()
        script = (
            f"import {{ bundledSkillNames }} from "
            f"{json.dumps((staged / 'plugin.js').as_uri())};"
            "process.stdout.write(JSON.stringify(bundledSkillNames()));"
        )

        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        expected = sorted(
            path.parent.name for path in (staged / "skills").glob("*/SKILL.md")
        )
        self.assertEqual(expected, json.loads(result.stdout))

    @unittest.skipUnless(shutil.which("node"), "Plugin installation requires Node.js")
    def test_installed_local_markdown_links_resolve_inside_the_package(self) -> None:
        """The installed package contains each local Markdown link target."""
        staged = self.stage()
        config_home = self.fixture.parent / "xdg-config"
        environment = os.environ.copy()
        environment["XDG_CONFIG_HOME"] = str(config_home)
        script = (
            f"import {{ syncSkills }} from {json.dumps((staged / 'plugin.js').as_uri())};"
            "process.stdout.write(syncSkills());"
        )

        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            capture_output=True,
            check=False,
            env=environment,
            text=True,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        installed = Path(result.stdout)
        self.assertTrue(installed.resolve().is_relative_to(config_home.resolve()))
        self.assert_local_links_resolve(installed)

    @unittest.skipUnless(shutil.which("node"), "Plugin definition requires Node.js")
    def test_default_export_is_an_opencode_v2_plugin_definition(self) -> None:
        """The staged default export carries an id and a setup function."""
        staged = self.stage()
        script = (
            f"import definition from {json.dumps((staged / 'plugin.js').as_uri())};"
            "const value = definition == null ? null : {"
            "export: typeof definition,"
            "id: definition.id ?? null,"
            "setup: typeof definition.setup"
            "};"
            "process.stdout.write(JSON.stringify(value));"
        )

        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            {
                "export": "object",
                "id": "@homericintelligence/athena-opencode",
                "setup": "function",
            },
            json.loads(result.stdout),
        )

    @unittest.skipUnless(shutil.which("node"), "Plugin definition requires Node.js")
    def test_definition_needs_no_runtime_dependency(self) -> None:
        """The staged entry point loads from a package that has no dependencies."""
        staged = self.stage()
        manifest = json.loads((staged / "package.json").read_text(encoding="utf-8"))
        self.assertIn(manifest.get("dependencies"), (None, {}))
        script = (
            f"import definition from {json.dumps((staged / 'plugin.js').as_uri())};"
            "process.stdout.write(JSON.stringify("
            "{id: definition.id, setup: typeof definition.setup}));"
        )

        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            {"id": "@homericintelligence/athena-opencode", "setup": "function"},
            json.loads(result.stdout),
        )

    @unittest.skipUnless(shutil.which("node"), "Plugin installation requires Node.js")
    def test_setup_installs_the_skill_corpus(self) -> None:
        """The V2 setup hook installs the bundled skills under the config home."""
        staged = self.stage()
        config_home = self.fixture.parent / "xdg-config-setup"
        environment = os.environ.copy()
        environment["XDG_CONFIG_HOME"] = str(config_home)
        script = (
            f"import({json.dumps((staged / 'plugin.js').as_uri())}).then("
            "async (module) => { await module.default.setup();"
            "process.stdout.write(JSON.stringify(module.bundledSkillNames())); });"
        )

        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            capture_output=True,
            check=False,
            env=environment,
            text=True,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        bundles = json.loads(result.stdout.strip().splitlines()[-1])
        installed_root = config_home / "opencode" / "skills" / "athena"
        self.assertTrue((installed_root / "_cli.py").is_file())
        installed = sorted(
            path.parent.name for path in installed_root.glob("*/SKILL.md")
        )
        self.assertEqual(bundles, installed)
        self.assertNotEqual([], installed)

    @unittest.skipUnless(shutil.which("node"), "Plugin installation requires Node.js")
    def test_setup_warns_and_stays_loaded_when_installation_fails(self) -> None:
        """A failed skill copy warns without rejecting the V2 setup hook."""
        staged = self.stage()
        config_home = self.fixture.parent / "xdg-config-blocked"
        blocker = config_home / "opencode"
        blocker.parent.mkdir(parents=True)
        blocker.write_text("blocked", encoding="utf-8")
        environment = os.environ.copy()
        environment["XDG_CONFIG_HOME"] = str(config_home)
        script = (
            f"import({json.dumps((staged / 'plugin.js').as_uri())}).then("
            "(module) => module.default.setup());"
        )

        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            capture_output=True,
            check=False,
            env=environment,
            text=True,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("[athena-opencode]", result.stderr)
        self.assertIn("could not install the skills", result.stderr)

    def test_staged_skill_policy_links_resolve_inside_the_skill_corpus(self) -> None:
        """Installed skills can read the policy without repository docs or a network."""
        staged = self.stage()
        skills_root = (staged / "skills").resolve()

        for markdown_path in sorted(skills_root.rglob("*.md")):
            if markdown_path == skills_root / "TECHNICAL_ENGLISH.md":
                continue
            targets = md.technical_english_targets(
                markdown_path.read_text(encoding="utf-8")
            )
            if markdown_path.name == "SKILL.md":
                self.assertTrue(targets, f"{markdown_path} has no policy link")
            for target in targets:
                with self.subTest(markdown=markdown_path, target=target):
                    resolved = (markdown_path.parent / target).resolve()
                    self.assertTrue(resolved.is_relative_to(skills_root))
                    self.assertTrue(resolved.is_file())

    def test_source_and_staged_readme_policy_links_resolve_locally(self) -> None:
        """The source and relocated package README can read the shipped policy."""
        staged = self.stage()
        locations = (
            (
                "source",
                self.fixture / "npm" / "athena-opencode" / "README.md",
                self.fixture.resolve(),
            ),
            ("staged", staged / "README.md", staged.resolve()),
        )

        for label, readme, package_root in locations:
            targets = md.technical_english_targets(readme.read_text(encoding="utf-8"))
            self.assertTrue(targets, f"{label} README has no policy link")
            for target in targets:
                with self.subTest(location=label, target=target):
                    resolved = (readme.parent / target).resolve()
                    self.assertTrue(resolved.is_relative_to(package_root))
                    self.assertTrue(resolved.is_file())

    def test_missing_technical_english_policy_fails_staging(self) -> None:
        """Staging fails closed when the installed writing policy is unavailable."""
        (self.fixture / "skills" / "TECHNICAL_ENGLISH.md").unlink(missing_ok=True)

        with self.assertRaises(package_opencode.PackageError) as context:
            self.stage()

        self.assertIn("skills/TECHNICAL_ENGLISH.md", str(context.exception))

    def test_staging_skips_generated_python_cache(self) -> None:
        cache = self.fixture / "skills" / "advise" / "scripts" / "__pycache__"
        cache.mkdir(parents=True)
        (cache / "helper.pyc").write_bytes(b"")

        staged = self.stage()

        self.assertFalse(
            (staged / "skills" / "advise" / "scripts" / "__pycache__").exists()
        )

    def test_version_mismatch_fails_closed(self) -> None:
        manifest = self.fixture / "npm" / "athena-opencode" / "package.json"
        document = json.loads(manifest.read_text(encoding="utf-8"))
        document["version"] = "9.9.9"
        manifest.write_text(json.dumps(document), encoding="utf-8")

        with self.assertRaises(package_opencode.PackageError):
            self.stage()

    def test_symlinked_source_fails_closed(self) -> None:
        external = self.fixture.parent / "external-plugin.js"
        external.write_text("export default () => ({});\n", encoding="utf-8")
        entry = self.fixture / "npm" / "athena-opencode" / "plugin.js"
        entry.unlink()
        entry.symlink_to(external)

        with self.assertRaises(package_opencode.PackageError):
            self.stage()

    def test_symlinked_support_document_fails_closed(self) -> None:
        external = self.fixture.parent / "external-guidance.md"
        external.write_text("external guidance\n", encoding="utf-8")
        entry = self.fixture / "docs" / "dependency-resolution.md"
        entry.unlink()
        entry.symlink_to(external)

        with self.assertRaises(package_opencode.PackageError):
            self.stage()

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
        self.assertIn(str(self.fixture / "dist" / "opencode-npm"), stdout.getvalue())

        broken = self.fixture / "broken"
        shutil.copytree(
            self.fixture,
            broken,
            ignore=shutil.ignore_patterns(
                ".git", ".venv", "dist", "build", "__pycache__", "*.pyc"
            ),
        )
        manifest = broken / "npm" / "athena-opencode" / "package.json"
        document = json.loads(manifest.read_text(encoding="utf-8"))
        document["version"] = "not-semver"
        manifest.write_text(json.dumps(document), encoding="utf-8")
        error_output = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(error_output):
            code = package_opencode.main(["--root", str(broken)])
        self.assertEqual(1, code)
        self.assertTrue(error_output.getvalue().strip())


if __name__ == "__main__":
    unittest.main()
