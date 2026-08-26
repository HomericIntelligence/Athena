"""Unit tests for scripts/package_opencode.py."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "package_opencode.py"
SPEC = importlib.util.spec_from_file_location("athena_package_opencode", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
package_opencode = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package_opencode)

MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def technical_english_targets(markdown: str) -> list[str]:
    """Return local links to the shipped technical-English policy."""
    targets: list[str] = []
    for target in MARKDOWN_LINK.findall(markdown):
        path = target.split("#", 1)[0]
        normalized_name = Path(path).name.lower().replace("-", "_")
        if normalized_name == "technical_english.md":
            targets.append(path)
    return targets


def local_markdown_targets(markdown: str) -> list[tuple[str, str]]:
    """Return paths and fragments from local Markdown links."""
    targets: list[tuple[str, str]] = []
    for target in MARKDOWN_LINK.findall(markdown):
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or (not parsed.path and not parsed.fragment):
            continue
        targets.append((unquote(parsed.path), unquote(parsed.fragment)))
    return targets


def markdown_anchors(markdown: str) -> set[str]:
    """Return GitHub-style anchors for the headings in a Markdown document."""
    anchors: set[str] = set()
    counts: dict[str, int] = {}
    for line in markdown.splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if match is None:
            continue
        heading = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", match.group(1))
        heading = heading.replace("`", "")
        base = re.sub(r"[^\w -]", "", heading.casefold()).replace(" ", "-")
        occurrence = counts.get(base, 0)
        counts[base] = occurrence + 1
        anchors.add(base if occurrence == 0 else f"{base}-{occurrence}")
    return anchors


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

    def assert_local_links_resolve(self, artifact_root: Path) -> None:
        """Require each local Markdown target to exist in the artifact."""
        artifact_root = artifact_root.resolve()
        checked = 0
        unresolved: list[str] = []
        for markdown_path in sorted(artifact_root.rglob("*.md")):
            for target, fragment in local_markdown_targets(
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
                    anchors = markdown_anchors(resolved.read_text(encoding="utf-8"))
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

    def test_staged_skill_policy_links_resolve_inside_the_skill_corpus(self) -> None:
        """Installed skills can read the policy without repository docs or a network."""
        staged = self.stage()
        skills_root = (staged / "skills").resolve()

        for markdown_path in sorted(skills_root.rglob("*.md")):
            if markdown_path == skills_root / "TECHNICAL_ENGLISH.md":
                continue
            targets = technical_english_targets(
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
            targets = technical_english_targets(readme.read_text(encoding="utf-8"))
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
