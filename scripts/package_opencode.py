#!/usr/bin/env python3
"""Stage the deterministic opencode npm plugin package from canonical sources."""

from __future__ import annotations

import json
import posixpath
import re
import shutil
import subprocess
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path, PurePosixPath
from typing import Final
from urllib.parse import quote, unquote, urlsplit, urlunsplit

sys.dont_write_bytecode = True
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.package_plugin import PackageError, forbidden_name
from scripts.semver import SEMVER_PATTERN
from skills._cli import argument_parser

PLUGIN_DIRECTORY: Final[PurePosixPath] = PurePosixPath("npm") / "athena-opencode"
PLUGIN_README: Final[PurePosixPath] = PLUGIN_DIRECTORY / "README.md"
PLUGIN_FILES: Final[tuple[PurePosixPath, ...]] = (
    PLUGIN_DIRECTORY / "package.json",
    PLUGIN_DIRECTORY / "plugin.js",
    PLUGIN_README,
)
LEGAL_FILES: Final[tuple[PurePosixPath, ...]] = (
    PurePosixPath("LICENSE"),
    PurePosixPath("NOTICE"),
)
SKILLS_ROOT: Final[PurePosixPath] = PurePosixPath("skills")
REQUIRED_SKILL_FILES: Final[tuple[PurePosixPath, ...]] = (
    SKILLS_ROOT / "TECHNICAL_ENGLISH.md",
)
STAGED_SUPPORT_ROOT: Final[PurePosixPath] = SKILLS_ROOT / "_support"
SUPPORT_ROOTS: Final[tuple[PurePosixPath, ...]] = (
    PurePosixPath("docs") / "dependency-resolution.md",
    PurePosixPath("docs") / "policies" / "development.md",
    PurePosixPath("docs") / "policies" / "evidence-integrity.md",
    PurePosixPath("docs") / "principles",
    PurePosixPath("docs") / "review",
)
VERSION_MANIFEST: Final[PurePosixPath] = PurePosixPath(".codex-plugin") / "plugin.json"
DEFAULT_OUTPUT: Final[PurePosixPath] = PurePosixPath("dist") / "opencode-npm"
GENERATED_SUFFIXES: Final[frozenset[str]] = frozenset({".pyc", ".pyo"})
MARKDOWN_LINK: Final[re.Pattern[str]] = re.compile(
    r"(?P<prefix>!?\[[^]]*\]\()(?P<target>[^)\s]+)(?P<suffix>\))"
)


def _relative(path: Path, repo_root: Path) -> PurePosixPath:
    return PurePosixPath(path.relative_to(repo_root).as_posix())


def _validate_source(path: Path, relative_path: PurePosixPath) -> None:
    if path.is_symlink():
        raise PackageError(
            f"The package input must not be a symbolic link: '{relative_path}'."
        )
    if path.is_dir():
        return
    if forbidden_name(relative_path):
        raise PackageError(
            f"The package input name is not permitted: '{relative_path}'."
        )
    if not path.is_file():
        raise PackageError(
            f"The package input type is not permitted: '{relative_path}'."
        )


def _read_semver(document: dict[str, object], label: str) -> str:
    version = document.get("version")
    if not isinstance(version, str) or SEMVER_PATTERN.fullmatch(version) is None:
        raise PackageError(
            f"The {label} version is not valid Semantic Versioning (SemVer): "
            f"{version!r}."
        )
    return version


def _manifest_version(path: Path, relative_path: PurePosixPath, label: str) -> str:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PackageError(
            f"The tool cannot read '{relative_path}'. "
            f"The operation returned this diagnostic.\n{error}"
        ) from error
    if not isinstance(document, dict):
        raise PackageError(f"The file '{relative_path}' must be a JSON object.")
    return _read_semver(document, label)


def _skill_sources(repo_root: Path) -> Iterator[Path]:
    for path in sorted((repo_root / SKILLS_ROOT.as_posix()).rglob("*")):
        if "__pycache__" in path.parts or path.suffix.lower() in GENERATED_SUFFIXES:
            continue
        yield path


def _support_sources(repo_root: Path) -> Iterator[tuple[Path, PurePosixPath]]:
    """Yield canonical documentation that installed skills require."""
    for relative_root in SUPPORT_ROOTS:
        root = repo_root / relative_root.as_posix()
        _validate_source(root, relative_root)
        yield root, relative_root
        if root.is_dir():
            for path in sorted(root.rglob("*")):
                yield path, _relative(path, repo_root)


def _rewrite_local_markdown_links(
    markdown: str,
    *,
    source_path: Path,
    staged_path: PurePosixPath,
    source_to_staged: dict[Path, PurePosixPath],
) -> str:
    """Rebase local links from canonical sources to staged package paths."""

    def replace(match: re.Match[str]) -> str:
        target = match.group("target")
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or not parsed.path:
            return match.group(0)
        source_target = (source_path.parent / unquote(parsed.path)).resolve()
        mapped_target = source_to_staged.get(source_target)
        if mapped_target is None:
            raise PackageError(
                f"The local Markdown link '{target}' in '{source_path}' does not "
                "have a staged package target."
            )
        relative_target = posixpath.relpath(
            mapped_target.as_posix(), staged_path.parent.as_posix()
        )
        staged_target = urlunsplit(
            (
                "",
                "",
                quote(relative_target, safe="/._~-"),
                parsed.query,
                parsed.fragment,
            )
        )
        return f"{match.group('prefix')}{staged_target}{match.group('suffix')}"

    return MARKDOWN_LINK.sub(replace, markdown)


def _copy_staged_file(
    source_path: Path,
    target: Path,
    staged_path: PurePosixPath,
    source_to_staged: dict[Path, PurePosixPath],
) -> None:
    """Copy one package file and rebase its local Markdown links."""
    if source_path.suffix.casefold() != ".md":
        shutil.copyfile(source_path, target)
        return
    markdown = source_path.read_text(encoding="utf-8")
    rewritten = _rewrite_local_markdown_links(
        markdown,
        source_path=source_path,
        staged_path=staged_path,
        source_to_staged=source_to_staged,
    )
    target.write_text(rewritten, encoding="utf-8")


def _staging_entries(
    repo_root: Path,
) -> tuple[list[tuple[Path, PurePosixPath]], dict[Path, PurePosixPath]]:
    """Return validated source-to-package entries and their link map."""
    entries = [
        *(
            (repo_root / item.as_posix(), PurePosixPath(item.name))
            for item in PLUGIN_FILES
        ),
        *(
            (repo_root / item.as_posix(), PurePosixPath(item.name))
            for item in LEGAL_FILES
        ),
        *((path, _relative(path, repo_root)) for path in _skill_sources(repo_root)),
        *(
            (path, STAGED_SUPPORT_ROOT / relative_path)
            for path, relative_path in _support_sources(repo_root)
        ),
    ]
    source_to_staged: dict[Path, PurePosixPath] = {}
    staged_paths: set[PurePosixPath] = set()
    for source_path, staged_path in entries:
        source_relative = _relative(source_path, repo_root)
        _validate_source(source_path, source_relative)
        resolved_source = source_path.resolve()
        if resolved_source in source_to_staged:
            raise PackageError(f"The package input is duplicated: '{source_relative}'.")
        if staged_path in staged_paths:
            raise PackageError(f"The package output is duplicated: '{staged_path}'.")
        source_to_staged[resolved_source] = staged_path
        staged_paths.add(staged_path)
    return entries, source_to_staged


def stage_package(repo_root: Path, output_directory: Path | None = None) -> Path:
    """Validate the sources and stage the publishable npm package."""
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
        "opencode plugin",
    )
    if package_version != manifest_version:
        raise PackageError(
            f"The opencode plugin version {package_version!r} does not match the "
            f"host-manifest version {manifest_version!r}."
        )
    for relative_path in REQUIRED_SKILL_FILES:
        source_path = repo_root / relative_path.as_posix()
        _validate_source(source_path, relative_path)
        if not source_path.is_file():
            raise PackageError(
                f"The required package input must be a file: '{relative_path}'."
            )
    entries, source_to_staged = _staging_entries(repo_root)

    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    for source_path, staged_path in entries:
        target = destination / staged_path.as_posix()
        if source_path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            _copy_staged_file(
                source_path,
                target,
                staged_path,
                source_to_staged,
            )
    return destination


def main(argv: Sequence[str] | None = None) -> int:
    """Stage the opencode npm plugin package."""
    parser = argument_parser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        help="Use this repository root. By default, use the Git root.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help=f"Use this staging directory. By default, use '{DEFAULT_OUTPUT}'.",
    )
    arguments = parser.parse_args(argv)
    try:
        repo_root = arguments.root.resolve() if arguments.root else _git_root()
        staged = stage_package(repo_root, arguments.output)
    except (PackageError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"The tool staged the opencode npm package at '{staged}'.")
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
