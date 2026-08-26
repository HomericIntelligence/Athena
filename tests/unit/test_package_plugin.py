"""Unit tests for the deterministic Athena plugin archive builder."""

from __future__ import annotations

import io
import json
import os
import posixpath
import re
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

from scripts.package_plugin import (
    ARCHIVE_ROOTS,
    REQUIRED_MEMBERS,
    PackageError,
    build_package,
    inspect_archive,
    main,
    read_plugin_version,
)

ROOT = Path(__file__).resolve().parents[2]
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


def create_repository(root: Path, *, version: str = "1.2.3") -> None:
    """Create the smallest repository satisfying the package contract."""
    for archive_root in ARCHIVE_ROOTS:
        path = root / archive_root
        if Path(archive_root).suffix or archive_root.endswith(".md"):
            path.write_text(f"{archive_root}\n", encoding="utf-8")
        else:
            path.mkdir(parents=True)

    (root / ".codex-plugin" / "plugin.json").write_text(
        f'{{"name": "athena", "version": "{version}"}}\n',
        encoding="utf-8",
    )
    (root / "package.json").write_text(
        (
            '{"name":"@homericintelligence/athena","version":"'
            f'{version}","keywords":["pi-package"],"pi":{{"skills":["./skills"]}}}}\n'
        ),
        encoding="utf-8",
    )
    for member in sorted(REQUIRED_MEMBERS - {"package.json"}):
        path = root / member
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"fixture for {member}\n", encoding="utf-8")


def write_archive(path: Path, member: tarfile.TarInfo, data: bytes = b"") -> None:
    """Write one deliberately controlled member to a gzip tar archive."""
    with tarfile.open(path, mode="w:gz") as archive:
        archive.addfile(member, io.BytesIO(data) if member.isfile() else None)


def write_complete_archive(
    path: Path,
    extras: tuple[tuple[tarfile.TarInfo, bytes], ...] = (),
) -> None:
    """Write a complete package archive and the specified test members."""
    with tarfile.open(path, mode="w:gz") as archive:
        for name in sorted(REQUIRED_MEMBERS):
            member = tarfile.TarInfo(name)
            member.size = 1
            archive.addfile(member, io.BytesIO(b"x"))
        for member, data in extras:
            archive.addfile(member, io.BytesIO(data) if member.isfile() else None)


class PackagePluginTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Pi helper contracts require Node.js")
    def test_pi_package_root_finder_ignores_ci_runtime_manifest(self) -> None:
        """A Git installation resolves its Pi package, not a nested npm manifest for continuous integration."""
        finder = ROOT / "scripts" / "find_pi_package_root.mjs"
        with tempfile.TemporaryDirectory() as temporary_directory:
            install_root = Path(temporary_directory) / "git"
            package_root = install_root / "github.com" / "example" / "athena"
            (package_root / "skills" / "advise").mkdir(parents=True)
            (package_root / "package.json").write_text(
                '{"pi":{"skills":["./skills"]}}\n', encoding="utf-8"
            )
            ci_runtime = package_root / "ci" / "pi-runtime"
            ci_runtime.mkdir(parents=True)
            (ci_runtime / "package.json").write_text("{}\n", encoding="utf-8")

            result = subprocess.run(
                ["node", str(finder), str(install_root)],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(
                package_root.resolve(), Path(result.stdout.strip()).resolve()
            )

    @unittest.skipUnless(shutil.which("node"), "Pi helper contracts require Node.js")
    def test_pi_rpc_inventory_verifier_requires_exact_package_provenance(self) -> None:
        """Package skill discovery accepts only the expected package-origin commands."""
        verifier = ROOT / "scripts" / "verify_pi_package.mjs"
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "package"
            for skill in ("advise", "learn", "pr-review"):
                skill_path = root / "skills" / skill
                skill_path.mkdir(parents=True)
                (skill_path / "SKILL.md").write_text("fixture\n", encoding="utf-8")
            inventory = Path(temporary_directory) / "commands.jsonl"
            commands = [
                {
                    "name": f"skill:{skill}",
                    "source": "skill",
                    "sourceInfo": {"origin": "package", "baseDir": str(root)},
                }
                for skill in ("advise", "learn", "pr-review")
            ]
            inventory.write_text(
                json.dumps(
                    {
                        "id": "skills",
                        "type": "response",
                        "command": "get_commands",
                        "success": True,
                        "data": {"commands": commands},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            accepted = subprocess.run(
                ["node", str(verifier), str(root), str(inventory)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, accepted.returncode, accepted.stderr)

            rejected_commands = [
                {
                    "name": "skill:advise",
                    "source": "skill",
                    "sourceInfo": {"origin": "user", "baseDir": str(root)},
                },
                *commands[1:],
            ]
            inventory.write_text(
                json.dumps(
                    {
                        "id": "skills",
                        "type": "response",
                        "command": "get_commands",
                        "success": True,
                        "data": {"commands": rejected_commands},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            rejected = subprocess.run(
                ["node", str(verifier), str(root), str(inventory)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(0, rejected.returncode)

    @unittest.skipUnless(shutil.which("node"), "Pi helper contracts require Node.js")
    def test_ci_subagent_probe_reports_the_registered_active_package_tool(self) -> None:
        """The continuous-integration probe produces structured package-origin tool evidence."""
        probe = (ROOT / "scripts" / "ci_pi_subagent_probe.mjs").as_uri()
        script = f"""
import probe from {json.dumps(probe)};
let registration;
probe({{
  registerCommand: (name, value) => {{ registration = {{ name, value }}; }},
  getAllTools: () => [{{
    name: "subagent",
    sourceInfo: {{ origin: "package", source: "npm:pi-subagents@0.37.2" }},
  }}],
  getActiveTools: () => ["subagent"],
}});
let notification;
await registration.value.handler("", {{
  ui: {{ notify: (message, type) => {{ notification = {{ message, type }}; }} }},
}});
const payload = JSON.parse(notification.message);
if (
  registration.name !== "ci-verify-subagent-tool" ||
  notification.type !== "info" ||
  payload.tool?.name !== "subagent" ||
  payload.tool.active !== true ||
  payload.tool.sourceInfo?.origin !== "package"
) {{
  throw new Error("invalid pi-subagents probe evidence");
}}
"""
        result = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)

    def test_build_is_byte_reproducible_and_writes_checksum(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            create_repository(root)

            first_archive, first_checksum = build_package(root)
            first_bytes = first_archive.read_bytes()
            first_checksum_text = first_checksum.read_text(encoding="utf-8")
            first_archive.unlink()
            first_checksum.unlink()
            second_archive, second_checksum = build_package(root)

            self.assertEqual(first_bytes, second_archive.read_bytes())
            self.assertEqual(
                first_checksum_text, second_checksum.read_text(encoding="utf-8")
            )
            self.assertEqual(
                f"{sha256(first_bytes).hexdigest()}  athena-plugin-1.2.3.tar.gz\n",
                first_checksum_text,
            )

    def test_archive_metadata_is_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            create_repository(root)
            executable = root / "skills" / "tool"
            executable.write_text("executable fixture\n", encoding="utf-8")
            executable.chmod(0o751)

            archive_path, _ = build_package(root)

            with tarfile.open(archive_path, mode="r:gz") as archive:
                members = archive.getmembers()
            self.assertTrue(members)
            for member in members:
                self.assertEqual(
                    (0, 0, "root", "root", 0),
                    (
                        member.uid,
                        member.gid,
                        member.uname,
                        member.gname,
                        member.mtime,
                    ),
                )
                expected_mode = (
                    0o755 if member.isdir() or member.name == "skills/tool" else 0o644
                )
                self.assertEqual(expected_mode, member.mode)

    def test_archive_contains_only_allowlisted_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            create_repository(root)
            (root / "unrelated.txt").write_text("must not ship\n", encoding="utf-8")

            archive_path, _ = build_package(root)

            with tarfile.open(archive_path, mode="r:gz") as archive:
                names = {member.name for member in archive.getmembers()}
            self.assertNotIn("unrelated.txt", names)
            self.assertTrue(
                all(name.split("/", 1)[0] in ARCHIVE_ROOTS for name in names)
            )

    def test_archive_contains_the_native_pi_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            create_repository(root)

            archive_path, _ = build_package(root)

            with tarfile.open(archive_path, mode="r:gz") as archive:
                manifest = archive.extractfile("package.json")
                assert manifest is not None
                package = json.load(manifest)
            self.assertEqual("@homericintelligence/athena", package["name"])
            self.assertEqual(["./skills"], package["pi"]["skills"])

    def test_archive_contains_the_opencode_plugin_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            create_repository(root)

            archive_path, _ = build_package(root)

            with tarfile.open(archive_path, mode="r:gz") as archive:
                entry = archive.extractfile("npm/athena-opencode/plugin.js")
                assert entry is not None
                self.assertIn("fixture for", entry.read().decode("utf-8"))

    def test_source_archive_contains_finalize_plan_skill(self) -> None:
        """The finalization workflow is available to every packaged harness."""
        archive_path, checksum_path = build_package(ROOT)
        self.addCleanup(archive_path.unlink, missing_ok=True)
        self.addCleanup(checksum_path.unlink, missing_ok=True)

        with tarfile.open(archive_path, mode="r:gz") as archive:
            self.assertIsNotNone(archive.getmember("skills/finalize-plan/SKILL.md"))

    def test_source_archive_requires_the_principles_catalog(self) -> None:
        """Every packaged harness receives the shared principles authority."""
        member = "docs/principles/README.md"
        self.assertIn(member, REQUIRED_MEMBERS)

        archive_path, checksum_path = build_package(ROOT)
        self.addCleanup(archive_path.unlink, missing_ok=True)
        self.addCleanup(checksum_path.unlink, missing_ok=True)

        with tarfile.open(archive_path, mode="r:gz") as archive:
            self.assertIsNotNone(archive.getmember(member))

    def test_source_archive_requires_the_technical_english_policy(self) -> None:
        """Every packaged harness receives the shared writing policy."""
        member = "skills/TECHNICAL_ENGLISH.md"
        self.assertIn(member, REQUIRED_MEMBERS)

        archive_path, checksum_path = build_package(ROOT)
        self.addCleanup(archive_path.unlink, missing_ok=True)
        self.addCleanup(checksum_path.unlink, missing_ok=True)

        with tarfile.open(archive_path, mode="r:gz") as archive:
            names = {item.name for item in archive.getmembers()}
            self.assertIn(member, names)
            for name in sorted(names):
                if not name.startswith("skills/") or not name.endswith(".md"):
                    continue
                if name == member:
                    continue
                source = archive.extractfile(name)
                assert source is not None
                targets = technical_english_targets(source.read().decode("utf-8"))
                if name.endswith("/SKILL.md"):
                    self.assertTrue(targets, f"{name} has no policy link")
                for target in targets:
                    with self.subTest(markdown=name, target=target):
                        resolved = posixpath.normpath(
                            f"{posixpath.dirname(name)}/{target}"
                        )
                        self.assertTrue(resolved.startswith("skills/"))
                        self.assertIn(resolved, names)

    def test_source_archive_local_markdown_links_resolve_inside_archive(self) -> None:
        """The portable archive contains each local Markdown link target."""
        archive_path, checksum_path = build_package(ROOT)
        self.addCleanup(archive_path.unlink, missing_ok=True)
        self.addCleanup(checksum_path.unlink, missing_ok=True)

        with tarfile.open(archive_path, mode="r:gz") as archive:
            names = {member.name.rstrip("/") for member in archive.getmembers()}
            checked = 0
            unresolved: list[str] = []
            for name in sorted(names):
                if not name.endswith(".md"):
                    continue
                source = archive.extractfile(name)
                assert source is not None
                for target, fragment in local_markdown_targets(
                    source.read().decode("utf-8")
                ):
                    checked += 1
                    resolved = (
                        posixpath.normpath(
                            posixpath.join(posixpath.dirname(name), target)
                        )
                        if target
                        else name
                    )
                    if resolved == ".." or resolved.startswith(("/", "../")):
                        unresolved.append(f"{name} -> {target} (outside archive)")
                    elif resolved not in names:
                        unresolved.append(f"{name} -> {target} (target does not exist)")
                    elif fragment and resolved.endswith(".md"):
                        target_source = archive.extractfile(resolved)
                        assert target_source is not None
                        anchors = markdown_anchors(target_source.read().decode("utf-8"))
                        if fragment.casefold() not in anchors:
                            unresolved.append(
                                f"{name} -> {target}#{fragment} (anchor does not exist)"
                            )

        self.assertGreater(checked, 0, "The archive has no local Markdown links.")
        self.assertEqual([], unresolved)

    def test_source_python_cache_directories_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            create_repository(root)
            cache = root / "skills" / "__pycache__"
            cache.mkdir()
            (cache / "_cli.cpython-313.pyc").write_bytes(b"generated cache")

            archive_path, _ = build_package(root)

            with tarfile.open(archive_path, mode="r:gz") as archive:
                names = {member.name for member in archive.getmembers()}
            self.assertFalse(any("__pycache__" in name for name in names))

    def test_missing_required_member_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            create_repository(root)
            (root / "skills" / "change-review" / "SKILL.md").unlink()

            with self.assertRaises(PackageError):
                build_package(root)

    def test_source_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            create_repository(root)
            (root / "docs" / "link").symlink_to(root / "README.md")

            with self.assertRaises(PackageError):
                build_package(root)

    @unittest.skipUnless(
        hasattr(os, "mkfifo"),
        "Named-pipe fixtures require Portable Operating System Interface support.",
    )
    def test_source_special_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            create_repository(root)
            os.mkfifo(root / "docs" / "events")

            with self.assertRaises(PackageError):
                build_package(root)

    def test_sensitive_and_generated_artifacts_are_rejected(self) -> None:
        for member in (
            "docs/.env",
            "docs/id_rsa",
            "docs/token.pem",
            "docs/helper.py",
            "docs/helper.pyc",
        ):
            with (
                self.subTest(member=member),
                tempfile.TemporaryDirectory() as temporary_directory,
            ):
                root = Path(temporary_directory)
                create_repository(root)
                path = root / member
                path.write_text("sensitive fixture\n", encoding="utf-8")

                with self.assertRaises(PackageError):
                    build_package(root)

    def test_skill_python_script_is_packaged_as_executable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            create_repository(root)
            script = root / "skills" / "repo-review" / "scripts" / "review.py"
            script.parent.mkdir()
            script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            script.chmod(0o755)

            archive_path, _ = build_package(root)

            with tarfile.open(archive_path, mode="r:gz") as archive:
                member = archive.getmember("skills/repo-review/scripts/review.py")
            self.assertEqual(0o755, member.mode)

    def test_secret_documentation_name_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            create_repository(root)
            (root / "docs" / "secret-management.md").write_text(
                "documentation fixture\n", encoding="utf-8"
            )

            archive_path, _ = build_package(root)

            with tarfile.open(archive_path, mode="r:gz") as archive:
                self.assertIsNotNone(archive.getmember("docs/secret-management.md"))

    def test_inspection_rejects_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_path = Path(temporary_directory) / "unsafe.tar.gz"
            member = tarfile.TarInfo("docs/../escape")
            member.size = 1
            write_complete_archive(archive_path, ((member, b"x"),))

            with self.assertRaises(PackageError):
                inspect_archive(archive_path)

    def test_inspection_rejects_links_and_special_members(self) -> None:
        for member_type in (tarfile.SYMTYPE, tarfile.FIFOTYPE):
            with (
                self.subTest(member_type=member_type),
                tempfile.TemporaryDirectory() as temporary_directory,
            ):
                archive_path = Path(temporary_directory) / "unsafe.tar.gz"
                member = tarfile.TarInfo("docs/unsafe")
                member.type = member_type
                write_complete_archive(archive_path, ((member, b""),))

                with self.assertRaises(PackageError):
                    inspect_archive(archive_path)

    def test_inspection_rejects_disallowed_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_path = Path(temporary_directory) / "unsafe.tar.gz"
            member = tarfile.TarInfo("scripts/unsafe.txt")
            member.size = 1
            write_complete_archive(archive_path, ((member, b"x"),))

            with self.assertRaises(PackageError):
                inspect_archive(archive_path)

    def test_inspection_rejects_corrupt_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_path = Path(temporary_directory) / "corrupt.tar.gz"
            archive_path.write_bytes(b"not a tar archive")

            with self.assertRaises(PackageError):
                inspect_archive(archive_path)

    def test_inspection_rejects_duplicate_members(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_path = Path(temporary_directory) / "duplicate.tar.gz"
            first = tarfile.TarInfo("docs/duplicate.txt")
            first.size = 1
            second = tarfile.TarInfo("docs/duplicate.txt")
            second.size = 1
            write_complete_archive(
                archive_path,
                ((first, b"a"), (second, b"b")),
            )

            with self.assertRaises(PackageError):
                inspect_archive(archive_path)

    def test_inspection_rejects_forbidden_member(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_path = Path(temporary_directory) / "forbidden.tar.gz"
            member = tarfile.TarInfo("docs/.env")
            member.size = 1
            write_complete_archive(archive_path, ((member, b"x"),))

            with self.assertRaises(PackageError):
                inspect_archive(archive_path)

    def test_plugin_version_supports_semver_and_rejects_unsafe_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            create_repository(root, version="2.0.0-rc.1+build.5")
            self.assertEqual("2.0.0-rc.1+build.5", read_plugin_version(root))

            for invalid in ("", "1.2", "../escape", "v1.2.3"):
                with self.subTest(version=invalid):
                    (root / ".codex-plugin" / "plugin.json").write_text(
                        f'{{"name": "athena", "version": "{invalid}"}}\n',
                        encoding="utf-8",
                    )
                    with self.assertRaises(PackageError):
                        read_plugin_version(root)

    def test_cli_validates_and_builds_explicit_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            create_repository(root)
            output = io.StringIO()

            with (
                patch("scripts.package_plugin._validate_repository") as validate,
                redirect_stdout(output),
            ):
                result = main(["--root", str(root)])

            self.assertEqual(0, result)
            validate.assert_called_once_with(root.resolve())
            self.assertIn("athena-plugin-1.2.3.tar.gz", output.getvalue())

    def test_cli_reports_validation_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            errors = io.StringIO()

            with (
                patch(
                    "scripts.package_plugin._validate_repository",
                    side_effect=PackageError("validation-sentinel-42"),
                ),
                redirect_stderr(errors),
            ):
                result = main(["--root", str(root)])

            self.assertEqual(1, result)
            self.assertIn("validation-sentinel-42", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
