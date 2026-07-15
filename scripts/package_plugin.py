#!/usr/bin/env python3
"""Build and verify Athena's deterministic AI-harness plugin archive."""

from __future__ import annotations

import argparse
import gzip
from hashlib import sha256
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
from typing import Final, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.semver import SEMVER_PATTERN


ARCHIVE_ROOTS: Final[tuple[str, ...]] = (
    ".agents",
    ".claude-plugin",
    ".codex-plugin",
    "AGENTS.md",
    "CLAUDE.md",
    "LICENSE",
    "NOTICE",
    "README.md",
    "SECURITY.md",
    "assets",
    "docs",
    "skills",
)
REQUIRED_MEMBERS: Final[frozenset[str]] = frozenset(
    {
        "skills/repo-review/SKILL.md",
        "skills/pr-review/SKILL.md",
        "docs/dependency-resolution.md",
    }
)
GENERATED_PYTHON_SUFFIXES: Final[frozenset[str]] = frozenset({".pyc", ".pyo"})
SENSITIVE_NAMES: Final[frozenset[str]] = frozenset(
    {
        ".npmrc",
        ".pypirc",
        "credentials.json",
        "credentials.yaml",
        "credentials.yml",
        "id_ed25519",
        "id_rsa",
        "secrets.json",
        "secrets.yaml",
        "secrets.yml",
    }
)
SENSITIVE_SUFFIXES: Final[frozenset[str]] = frozenset({".key", ".p12", ".pem", ".pfx"})


class PackageError(RuntimeError):
    """Raised when repository content violates the package contract."""


def forbidden_name(path: PurePosixPath) -> bool:
    """Return whether a portable archive member is misplaced or sensitive."""
    lowered_parts = tuple(part.lower() for part in path.parts)
    lowered_name = path.name.lower()
    suffix = path.suffix.lower()
    skill_script = (
        len(path.parts) >= 4
        and path.parts[0] == "skills"
        and path.parts[2] == "scripts"
    )
    return (
        "__pycache__" in lowered_parts
        or suffix in GENERATED_PYTHON_SUFFIXES
        or (suffix == ".py" and not skill_script)
        or lowered_name in SENSITIVE_NAMES
        or lowered_name == ".env"
        or lowered_name.startswith(".env.")
        or suffix in SENSITIVE_SUFFIXES
    )


def read_plugin_version(repo_root: Path) -> str:
    """Read and validate the SemVer used in the package filename."""
    manifest = repo_root / ".codex-plugin" / "plugin.json"
    try:
        document = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PackageError(
            f"cannot read plugin version from {manifest}: {error}"
        ) from error
    version = document.get("version") if isinstance(document, dict) else None
    if not isinstance(version, str) or SEMVER_PATTERN.fullmatch(version) is None:
        raise PackageError(f"plugin version is not valid SemVer: {version!r}")
    return version


def _validate_source(path: Path, relative_path: PurePosixPath) -> None:
    if path.is_symlink():
        raise PackageError(
            f"refusing forbidden archive input (symlink): {relative_path}"
        )
    if forbidden_name(relative_path):
        raise PackageError(f"refusing forbidden archive input (name): {relative_path}")
    if not path.is_file() and not path.is_dir():
        raise PackageError(f"refusing forbidden archive input (type): {relative_path}")


def paths_to_archive(repo_root: Path) -> list[tuple[Path, PurePosixPath]]:
    """Return validated source paths in reproducible archive order."""
    paths: list[tuple[Path, PurePosixPath]] = []
    for root_name in ARCHIVE_ROOTS:
        root = repo_root / root_name
        relative_root = PurePosixPath(root_name)
        _validate_source(root, relative_root)
        paths.append((root, relative_root))
        if root.is_dir():
            for path in root.rglob("*"):
                relative_path = PurePosixPath(path.relative_to(repo_root).as_posix())
                _validate_source(path, relative_path)
                paths.append((path, relative_path))
    return sorted(paths, key=lambda item: item[1].as_posix())


def inspect_archive(archive_path: Path) -> None:
    """Fail unless an archive is safe, allowlisted, unique, and complete."""
    try:
        with tarfile.open(archive_path, mode="r:gz") as archive:
            members = archive.getmembers()
    except (OSError, tarfile.TarError) as error:
        raise PackageError(f"cannot inspect archive {archive_path}: {error}") from error

    names = [member.name for member in members]
    if len(names) != len(set(names)):
        raise PackageError("archive contains duplicate members")
    for member in members:
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts:
            raise PackageError(f"archive contains unsafe path: {member.name}")
        if not path.parts or path.parts[0] not in ARCHIVE_ROOTS:
            raise PackageError(f"archive contains disallowed member: {member.name}")
        if forbidden_name(path):
            raise PackageError(f"archive contains forbidden member: {member.name}")
        if member.issym() or member.islnk():
            raise PackageError(f"archive contains link: {member.name}")
        if not member.isfile() and not member.isdir():
            raise PackageError(f"archive contains special member: {member.name}")
    missing = sorted(REQUIRED_MEMBERS.difference(names))
    if missing:
        raise PackageError(f"archive is missing required members: {', '.join(missing)}")


def _archive_bytes(repo_root: Path) -> bytes:
    tar_buffer = io.BytesIO()
    with tarfile.open(
        fileobj=tar_buffer, mode="w", format=tarfile.PAX_FORMAT
    ) as archive:
        for source_path, archive_path in paths_to_archive(repo_root):
            info = archive.gettarinfo(str(source_path), arcname=archive_path.as_posix())
            info.uid = 0
            info.gid = 0
            info.uname = "root"
            info.gname = "root"
            info.mtime = 0
            info.pax_headers = {}
            info.mode = 0o755 if info.isdir() or (info.mode & 0o111) else 0o644
            if info.isfile():
                with source_path.open("rb") as source:
                    archive.addfile(info, source)
            else:
                archive.addfile(info)

    gzip_buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=gzip_buffer, mtime=0) as archive:
        archive.write(tar_buffer.getvalue())
    return gzip_buffer.getvalue()


def build_package(
    repo_root: Path, output_directory: Path | None = None
) -> tuple[Path, Path]:
    """Build, inspect, and checksum the deterministic Athena plugin archive."""
    repo_root = repo_root.resolve()
    version = read_plugin_version(repo_root)
    destination = output_directory or repo_root / "dist"
    destination.mkdir(parents=True, exist_ok=True)
    archive_path = destination / f"athena-plugin-{version}.tar.gz"
    checksum_path = archive_path.with_name(f"{archive_path.name}.sha256")
    archive_path.unlink(missing_ok=True)
    checksum_path.unlink(missing_ok=True)
    archive_path.write_bytes(_archive_bytes(repo_root))
    inspect_archive(archive_path)
    digest = sha256(archive_path.read_bytes()).hexdigest()
    checksum_path.write_text(f"{digest}  {archive_path.name}\n", encoding="utf-8")
    return archive_path, checksum_path


def _repository_root(explicit_root: Path | None) -> Path:
    if explicit_root is not None:
        return explicit_root.resolve()
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip()).resolve()


def _validate_repository(repo_root: Path) -> None:
    validator = repo_root / "scripts" / "validate_skills.py"
    result = subprocess.run(
        [sys.executable, str(validator), "--quiet", "--root", str(repo_root)],
        cwd=repo_root,
        check=False,
    )
    if result.returncode != 0:
        raise PackageError("repository validation failed")


def main(argv: Sequence[str] | None = None) -> int:
    """Validate the repository and build its plugin distribution."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, help="repository root (defaults to Git root)"
    )
    arguments = parser.parse_args(argv)
    try:
        repo_root = _repository_root(arguments.root)
        _validate_repository(repo_root)
        archive_path, checksum_path = build_package(repo_root)
    except (PackageError, OSError, subprocess.SubprocessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Built {archive_path} and {checksum_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
