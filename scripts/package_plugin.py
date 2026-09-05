#!/usr/bin/env python3
"""Build and verify the deterministic Athena plugin archive."""

from __future__ import annotations

import gzip
import io
import json
import subprocess
import sys
import tarfile
from collections.abc import Sequence
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Final

sys.dont_write_bytecode = True
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.semver import SEMVER_PATTERN
from skills._cli import argument_parser

ARCHIVE_ROOTS: Final[tuple[str, ...]] = (
    ".agents",
    ".claude-plugin",
    ".codex-plugin",
    "AGENTS.md",
    "CLAUDE.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "NOTICE",
    "npm",
    "package.json",
    "README.md",
    "SECURITY.md",
    "assets",
    "docs",
    "skills",
)
REQUIRED_MEMBERS: Final[frozenset[str]] = frozenset(
    {
        "skills/repo-review/SKILL.md",
        "CONTRIBUTING.md",
        "skills/pr-review/SKILL.md",
        "skills/pr-review/references/criteria.md",
        "skills/pr-review/references/delivery.md",
        "skills/pr-review/references/evidence.md",
        "skills/pr-review/references/prevalidated.md",
        "skills/pr-review/scripts/deliver_go.py",
        "skills/change-review/SKILL.md",
        "skills/change-review/scripts/resolve_scope.py",
        "skills/change-review/references/scope-resolution.md",
        "skills/issue-review/SKILL.md",
        "skills/plan-issue/SKILL.md",
        "skills/finalize-plan/SKILL.md",
        "docs/dependency-resolution.md",
        "docs/principles/README.md",
        "skills/TECHNICAL_ENGLISH.md",
        "docs/review/common.md",
        "docs/review/README.md",
        "docs/review/design-docs.md",
        "docs/review/language-routing.md",
        "docs/review/behavior-first-testing.md",
        "docs/review/issue-planning.md",
        "docs/review/repository-scorecard.md",
        "npm/athena-opencode/package.json",
        "npm/athena-opencode/plugin.js",
        "package.json",
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
    """This error identifies repository content that violates the package contract."""


class PackageOperationalError(PackageError):
    """This error identifies a failure that prevented package inspection."""


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
    shared_cli = path == PurePosixPath("skills/_cli.py")
    return (
        "__pycache__" in lowered_parts
        or suffix in GENERATED_PYTHON_SUFFIXES
        or (suffix == ".py" and not skill_script and not shared_cli)
        or lowered_name in SENSITIVE_NAMES
        or lowered_name == ".env"
        or lowered_name.startswith(".env.")
        or suffix in SENSITIVE_SUFFIXES
    )


def read_plugin_version(repo_root: Path) -> str:
    """Read and validate the Semantic Versioning (SemVer) value in the plugin manifest."""
    manifest = repo_root / ".codex-plugin" / "plugin.json"
    try:
        document = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise PackageOperationalError(
            f"The tool cannot read the plugin version from '{manifest}'. "
            f"The operation returned this diagnostic.\n{error}"
        ) from error
    version = document.get("version") if isinstance(document, dict) else None
    if not isinstance(version, str) or SEMVER_PATTERN.fullmatch(version) is None:
        raise PackageError(
            "The plugin version is not valid Semantic Versioning (SemVer): "
            f"{version!r}."
        )
    return version


def _validate_source(path: Path, relative_path: PurePosixPath) -> None:
    if path.is_symlink():
        raise PackageError(
            f"The archive input must not be a symbolic link: '{relative_path}'."
        )
    if forbidden_name(relative_path):
        raise PackageError(
            f"The archive input name is not permitted: '{relative_path}'."
        )
    if not path.is_file() and not path.is_dir():
        raise PackageError(
            f"The archive input type is not permitted: '{relative_path}'."
        )


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
                if "__pycache__" in relative_path.parts:
                    continue
                _validate_source(path, relative_path)
                paths.append((path, relative_path))
    return sorted(paths, key=lambda item: item[1].as_posix())


def inspect_archive(archive_path: Path) -> None:
    """Fail unless an archive is safe, allowlisted, unique, and complete."""
    try:
        with tarfile.open(archive_path, mode="r:gz") as archive:
            members = archive.getmembers()
    except (OSError, tarfile.TarError) as error:
        raise PackageOperationalError(
            f"The tool cannot inspect archive '{archive_path}'. "
            f"The operation returned this diagnostic.\n{error}"
        ) from error

    names = [member.name for member in members]
    if len(names) != len(set(names)):
        raise PackageError("The archive contains duplicate members.")
    for member in members:
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts:
            raise PackageError(f"The archive contains an unsafe path: '{member.name}'.")
        if not path.parts or path.parts[0] not in ARCHIVE_ROOTS:
            raise PackageError(
                f"The archive contains a member that is not permitted: '{member.name}'."
            )
        if forbidden_name(path):
            raise PackageError(
                f"The archive contains a forbidden member: '{member.name}'."
            )
        if member.issym() or member.islnk():
            raise PackageError(f"The archive contains a link: '{member.name}'.")
        if not member.isfile() and not member.isdir():
            raise PackageError(
                f"The archive contains a special member: '{member.name}'."
            )
    missing = sorted(REQUIRED_MEMBERS.difference(names))
    if missing:
        raise PackageError(
            "The archive is missing these required members: "
            + ", ".join(f"'{name}'" for name in missing)
            + "."
        )


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
        if result.returncode == 2:
            raise PackageOperationalError(
                "The repository validation could not complete."
            )
        raise PackageError("The repository validation failed.")


def main(argv: Sequence[str] | None = None) -> int:
    """Validate the repository and build its plugin distribution."""
    parser = argument_parser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        help="Use this repository root. By default, use the Git root.",
    )
    arguments = parser.parse_args(argv)
    try:
        repo_root = _repository_root(arguments.root)
        _validate_repository(repo_root)
        archive_path, checksum_path = build_package(repo_root)
    except PackageOperationalError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    except PackageError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except (OSError, subprocess.SubprocessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(f"The tool built '{archive_path}' and '{checksum_path}'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
