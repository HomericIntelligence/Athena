#!/usr/bin/env python3
"""Create the deterministic opencode npm plugin package from canonical sources."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path, PurePosixPath
from typing import Final

sys.dont_write_bytecode = True
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.package_plugin import PackageError, forbidden_name
from scripts.semver import SEMVER_PATTERN
from skills._cli import argument_parser

PLUGIN_DIRECTORY: Final[PurePosixPath] = PurePosixPath("npm") / "athena-opencode"
PLUGIN_FILES: Final[tuple[PurePosixPath, ...]] = (
    PLUGIN_DIRECTORY / "package.json",
    PLUGIN_DIRECTORY / "plugin.js",
    PLUGIN_DIRECTORY / "README.md",
)
LEGAL_FILES: Final[tuple[PurePosixPath, ...]] = (
    PurePosixPath("LICENSE"),
    PurePosixPath("NOTICE"),
)
SKILLS_ROOT: Final[PurePosixPath] = PurePosixPath("skills")
REQUIRED_SKILL_FILES: Final[tuple[PurePosixPath, ...]] = (
    SKILLS_ROOT / "TECHNICAL_ENGLISH.md",
)
VERSION_MANIFEST: Final[PurePosixPath] = PurePosixPath(".codex-plugin") / "plugin.json"
DEFAULT_OUTPUT: Final[PurePosixPath] = PurePosixPath("dist") / "opencode-npm"
GENERATED_SUFFIXES: Final[frozenset[str]] = frozenset({".pyc", ".pyo"})


def _relative(path: Path, repo_root: Path) -> PurePosixPath:
    return PurePosixPath(path.relative_to(repo_root).as_posix())


def _validate_source(path: Path, relative_path: PurePosixPath) -> None:
    if path.is_symlink():
        raise PackageError(
            f"refusing forbidden package input (symlink): {relative_path}"
        )
    if path.is_dir():
        return
    if forbidden_name(relative_path):
        raise PackageError(f"refusing forbidden package input (name): {relative_path}")
    if not path.is_file():
        raise PackageError(f"refusing forbidden package input (type): {relative_path}")


def _read_semver(document: dict[str, object], label: str) -> str:
    version = document.get("version")
    if not isinstance(version, str) or SEMVER_PATTERN.fullmatch(version) is None:
        raise PackageError(f"{label} version is not valid SemVer: {version!r}")
    return version


def _manifest_version(path: Path, relative_path: PurePosixPath, label: str) -> str:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PackageError(f"cannot read {relative_path}: {error}") from error
    if not isinstance(document, dict):
        raise PackageError(f"{relative_path} must be a JSON object")
    return _read_semver(document, label)


def _skill_sources(repo_root: Path) -> Iterator[Path]:
    for path in sorted((repo_root / SKILLS_ROOT.as_posix()).rglob("*")):
        if "__pycache__" in path.parts or path.suffix.lower() in GENERATED_SUFFIXES:
            continue
        yield path


def stage_package(repo_root: Path, output_directory: Path | None = None) -> Path:
    """Validate inputs and copy the publishable npm package into the output directory."""
    repo_root = repo_root.resolve()
    destination = (
        output_directory.resolve() if output_directory else repo_root / DEFAULT_OUTPUT
    )
    manifest_version = _manifest_version(
        repo_root / VERSION_MANIFEST.as_posix(), VERSION_MANIFEST, "Codex"
    )
    plugin_manifest = PLUGIN_DIRECTORY / "package.json"
    package_version = _manifest_version(
        repo_root / plugin_manifest.as_posix(),
        plugin_manifest,
        "OpenCode plugin",
    )
    if package_version != manifest_version:
        raise PackageError(
            "OpenCode plugin version differs from host manifests: "
            f"{package_version!r} != {manifest_version!r}"
        )
    sources = [
        *((repo_root / item.as_posix(), item) for item in PLUGIN_FILES),
        *((repo_root / item.as_posix(), item) for item in LEGAL_FILES),
    ]
    for source_path, relative_path in sources:
        _validate_source(source_path, relative_path)
    for relative_path in REQUIRED_SKILL_FILES:
        source_path = repo_root / relative_path.as_posix()
        _validate_source(source_path, relative_path)
        if not source_path.is_file():
            raise PackageError(
                f"required package input must be a file: {relative_path}"
            )
    for path in _skill_sources(repo_root):
        _validate_source(path, _relative(path, repo_root))

    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    for source_path, relative_path in sources:
        target = destination / relative_path.name
        shutil.copyfile(source_path, target)
    for path in _skill_sources(repo_root):
        relative_path = _relative(path, repo_root)
        target = destination / relative_path.as_posix()
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
    return destination


def main(argv: Sequence[str] | None = None) -> int:
    """Stage the opencode npm plugin package."""
    parser = argument_parser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, help="Repository root. By default, use the Git root."
    )
    parser.add_argument(
        "--output",
        type=Path,
        help=f"Output directory. By default, use {DEFAULT_OUTPUT}.",
    )
    arguments = parser.parse_args(argv)
    try:
        repo_root = arguments.root.resolve() if arguments.root else _git_root()
        staged = stage_package(repo_root, arguments.output)
    except (PackageError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Staged OpenCode npm package at {staged}")
    return 0


def _git_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip()).resolve()


if __name__ == "__main__":
    raise SystemExit(main())
