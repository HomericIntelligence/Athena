#!/usr/bin/env python3
"""Select, validate, and optionally create an isolated Git worktree."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def git(
    cwd: Path, *arguments: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *arguments], cwd=cwd, capture_output=True, text=True, check=False
    )
    if check and result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(arguments)} failed")
    return result


def reject_symlinks_below(trust_root: Path, target: Path) -> None:
    """Reject symlinks in the caller-controlled path below a trusted root."""
    lexical_root = trust_root.absolute()
    lexical_target = target.absolute()
    try:
        relative = lexical_target.relative_to(lexical_root)
    except ValueError as error:
        raise RuntimeError(
            f"worktree path escapes trusted root {lexical_root}"
        ) from error
    current = lexical_root
    if current.is_symlink():
        raise RuntimeError(f"worktree trusted root is a symlink: {current}")
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise RuntimeError(f"worktree path component is a symlink: {current}")


def select_path(
    root: Path,
    branch: str,
    requested: Path | None,
    exact_path: Path | None,
    path_root: Path | None,
) -> tuple[Path, bool]:
    if exact_path is not None:
        path = exact_path if exact_path.is_absolute() else root / exact_path
        trust_root = path_root if path_root is not None else path.parent
        if not trust_root.is_absolute():
            trust_root = root / trust_root
        reject_symlinks_below(trust_root, path)
        resolved_path = path.resolve()
        return resolved_path, resolved_path.is_relative_to(root)
    if requested is not None:
        base = requested if requested.is_absolute() else root / requested
        if base.is_symlink():
            raise RuntimeError(f"worktree base directory is a symlink: {base}")
        path = base / branch
        return path.resolve(), path.resolve().is_relative_to(root)
    for directory_name in (".worktrees", "worktrees"):
        directory = root / directory_name
        if directory.is_dir():
            if directory.is_symlink():
                raise RuntimeError(
                    f"project-local worktree directory is a symlink: {directory}"
                )
            return (directory / branch).resolve(), True
    project = root.name
    return Path(tempfile.gettempdir()) / f"{project}-{branch}", False


def verify_ignored(root: Path, path: Path) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return
    probe = relative.parent / ".athena-ignore-probe"
    result = git(root, "check-ignore", "-q", "--", str(probe), check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"project-local worktree directory {relative.parent} is not ignored"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("branch")
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--path", type=Path)
    parser.add_argument("--path-root", type=Path)
    parser.add_argument("--start-point", required=True)
    parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args()
    try:
        root = Path(git(Path.cwd(), "rev-parse", "--show-toplevel").stdout.strip())
        branch_check = git(
            root, "check-ref-format", "--branch", arguments.branch, check=False
        )
        if branch_check.returncode != 0:
            raise RuntimeError(f"invalid branch name: {arguments.branch}")
        if (arguments.path is None) != (arguments.path_root is None):
            raise RuntimeError("--path and --path-root must be provided together")
        path, project_local = select_path(
            root,
            arguments.branch,
            arguments.directory,
            arguments.path,
            arguments.path_root,
        )
        start_sha = git(
            root,
            "rev-parse",
            "--verify",
            f"{arguments.start_point}^{{commit}}",
        ).stdout.strip()
        if project_local:
            verify_ignored(root, path)
        if path.exists():
            raise RuntimeError(f"worktree path already exists: {path}")
        if not arguments.dry_run:
            git(
                root,
                "worktree",
                "add",
                str(path),
                "-b",
                arguments.branch,
                start_sha,
            )
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "branch": arguments.branch,
                "created": not arguments.dry_run,
                "path": str(path),
                "start_sha": start_sha,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
