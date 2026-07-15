"""Unit tests for the deterministic Athena plugin archive builder."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from hashlib import sha256
import io
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from scripts.package_plugin import (
    ARCHIVE_ROOTS,
    PackageError,
    build_package,
    inspect_archive,
    main,
    read_plugin_version,
)


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
    for member in (
        "skills/repo-review/SKILL.md",
        "skills/pr-review/SKILL.md",
        "docs/dependency-resolution.md",
    ):
        path = root / member
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"fixture for {member}\n", encoding="utf-8")


def write_archive(path: Path, member: tarfile.TarInfo, data: bytes = b"") -> None:
    """Write one deliberately controlled member to a gzip tar archive."""
    with tarfile.open(path, mode="w:gz") as archive:
        archive.addfile(member, io.BytesIO(data) if member.isfile() else None)


class PackagePluginTests(unittest.TestCase):
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

    def test_missing_required_member_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            create_repository(root)
            (root / "skills" / "pr-review" / "SKILL.md").unlink()

            with self.assertRaisesRegex(PackageError, "missing required members"):
                build_package(root)

    def test_source_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            create_repository(root)
            (root / "docs" / "link").symlink_to(root / "README.md")

            with self.assertRaisesRegex(PackageError, "symlink"):
                build_package(root)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO fixtures require POSIX")
    def test_source_special_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            create_repository(root)
            os.mkfifo(root / "docs" / "events")

            with self.assertRaisesRegex(PackageError, "type"):
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

                with self.assertRaisesRegex(PackageError, "name"):
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
            member = tarfile.TarInfo("../escape")
            member.size = 1
            write_archive(archive_path, member, b"x")

            with self.assertRaisesRegex(PackageError, "unsafe path"):
                inspect_archive(archive_path)

    def test_inspection_rejects_links_and_special_members(self) -> None:
        cases = ((tarfile.SYMTYPE, "link"), (tarfile.FIFOTYPE, "special member"))
        for member_type, message in cases:
            with (
                self.subTest(member_type=member_type),
                tempfile.TemporaryDirectory() as temporary_directory,
            ):
                archive_path = Path(temporary_directory) / "unsafe.tar.gz"
                member = tarfile.TarInfo("docs/unsafe")
                member.type = member_type
                write_archive(archive_path, member)

                with self.assertRaisesRegex(PackageError, message):
                    inspect_archive(archive_path)

    def test_inspection_rejects_disallowed_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_path = Path(temporary_directory) / "unsafe.tar.gz"
            member = tarfile.TarInfo("scripts/unsafe.txt")
            member.size = 1
            write_archive(archive_path, member, b"x")

            with self.assertRaisesRegex(PackageError, "disallowed member"):
                inspect_archive(archive_path)

    def test_inspection_rejects_corrupt_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_path = Path(temporary_directory) / "corrupt.tar.gz"
            archive_path.write_bytes(b"not a tar archive")

            with self.assertRaisesRegex(PackageError, "cannot inspect archive"):
                inspect_archive(archive_path)

    def test_inspection_rejects_duplicate_members(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_path = Path(temporary_directory) / "duplicate.tar.gz"
            member = tarfile.TarInfo("docs/duplicate.txt")
            member.size = 1
            with tarfile.open(archive_path, mode="w:gz") as archive:
                archive.addfile(member, io.BytesIO(b"a"))
                archive.addfile(member, io.BytesIO(b"b"))

            with self.assertRaisesRegex(PackageError, "duplicate members"):
                inspect_archive(archive_path)

    def test_inspection_rejects_forbidden_member(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_path = Path(temporary_directory) / "forbidden.tar.gz"
            member = tarfile.TarInfo("docs/.env")
            member.size = 1
            write_archive(archive_path, member, b"x")

            with self.assertRaisesRegex(PackageError, "forbidden member"):
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
                    with self.assertRaisesRegex(PackageError, "version"):
                        read_plugin_version(root)

    def test_cli_validates_and_builds_explicit_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            create_repository(root)
            output = io.StringIO()

            with patch("scripts.package_plugin._validate_repository") as validate:
                with redirect_stdout(output):
                    result = main(["--root", str(root)])

            self.assertEqual(0, result)
            validate.assert_called_once_with(root.resolve())
            self.assertIn("athena-plugin-1.2.3.tar.gz", output.getvalue())

    def test_cli_reports_validation_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            errors = io.StringIO()

            with patch(
                "scripts.package_plugin._validate_repository",
                side_effect=PackageError("repository validation failed"),
            ):
                with redirect_stderr(errors):
                    result = main(["--root", str(root)])

            self.assertEqual(1, result)
            self.assertIn("repository validation failed", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
