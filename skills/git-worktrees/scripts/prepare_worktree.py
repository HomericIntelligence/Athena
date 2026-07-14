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


def select_path(root: Path, branch: str, requested: Path | None) -> tuple[Path, bool]:
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
    parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args()
    try:
        root = Path(git(Path.cwd(), "rev-parse", "--show-toplevel").stdout.strip())
        branch_check = git(
            root, "check-ref-format", "--branch", arguments.branch, check=False
        )
        if branch_check.returncode != 0:
            raise RuntimeError(f"invalid branch name: {arguments.branch}")
        path, project_local = select_path(root, arguments.branch, arguments.directory)
        if project_local:
            verify_ignored(root, path)
        if path.exists():
            raise RuntimeError(f"worktree path already exists: {path}")
        if not arguments.dry_run:
            git(root, "worktree", "add", str(path), "-b", arguments.branch)
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "branch": arguments.branch,
                "created": not arguments.dry_run,
                "path": str(path),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
