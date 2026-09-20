#!/usr/bin/env python3
"""Prepare an isolated Git worktree."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING or __package__ not in {None, ""}:
    from skills._cli import argument_parser, run_command
else:
    _cli_path = Path(__file__).resolve().parents[2] / "_cli.py"
    _cli_spec = importlib.util.spec_from_file_location(
        "athena_installed_cli", _cli_path
    )
    if _cli_spec is None or _cli_spec.loader is None:
        raise RuntimeError(
            f"The installed Athena CLI helper is unavailable: '{_cli_path}'."
        )
    _cli = importlib.util.module_from_spec(_cli_spec)
    _cli_spec.loader.exec_module(_cli)
    argument_parser = _cli.argument_parser
    run_command = _cli.run_command


def git(
    cwd: Path, *arguments: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    result = run_command(
        ["git", *arguments], cwd=cwd, capture_output=True, text=True, check=False
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip() or f"The git {' '.join(arguments)} command failed."
        )
    return result


def reject_symlinks_below(trust_root: Path, target: Path) -> None:
    """Reject symbolic links in a caller-controlled path below a trusted root."""
    lexical_root = trust_root.absolute()
    lexical_target = target.absolute()
    try:
        lexical_target.relative_to(lexical_root)
    except ValueError as error:
        raise RuntimeError(
            f"The worktree path is outside the trusted root: '{lexical_root}'."
        ) from error
    for component in (*reversed(lexical_target.parents), lexical_target):
        if component.is_symlink():
            raise RuntimeError(
                f"A component of the worktree path is a symbolic link: '{component}'."
            )


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
        path = base / branch
        reject_symlinks_below(base, path)
        return path.resolve(), path.resolve().is_relative_to(root)
    primary = primary_project_root(root)
    directory = primary / ".worktrees"
    reject_symlinks_below(primary, directory / branch)
    return (directory / branch).resolve(), True


def primary_project_root(root: Path) -> Path:
    """Return the primary checkout from Git's worktree records."""
    records = git(root, "worktree", "list", "--porcelain", "-z").stdout
    first = records.split("\0", maxsplit=1)[0]
    if not first.startswith("worktree "):
        raise RuntimeError("Git did not identify the primary project checkout.")
    return Path(first.removeprefix("worktree ")).resolve()


def ensure_ignored(root: Path, path: Path) -> None:
    """Ignore a project-local directory without a tracked file change."""
    relative = path.relative_to(root)
    directory = relative.parts[0]
    if directory != ".worktrees":
        verify_ignored(root, path)
        return
    probe = Path(directory) / ".athena-ignore-probe"
    if git(root, "check-ignore", "-q", "--", str(probe), check=False).returncode == 0:
        return
    exclude = Path(git(root, "rev-parse", "--git-path", "info/exclude").stdout.strip())
    if not exclude.is_absolute():
        exclude = root / exclude
    exclude.parent.mkdir(parents=True, exist_ok=True)
    with exclude.open("a", encoding="utf-8") as stream:
        stream.write("\n/.worktrees/\n")
    verify_ignored(root, path)


def verify_ignored(root: Path, path: Path) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return
    probe = relative.parent / ".athena-ignore-probe"
    result = git(root, "check-ignore", "-q", "--", str(probe), check=False)
    if result.returncode != 0:
        raise RuntimeError(
            "Git did not confirm that it ignores the project-local worktree directory: "
            f"'{relative.parent}'."
        )


def main() -> int:
    parser = argument_parser(description=__doc__)
    parser.add_argument("branch")
    path_selection = parser.add_mutually_exclusive_group()
    path_selection.add_argument("--directory", type=Path)
    path_selection.add_argument("--path", type=Path)
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
            raise RuntimeError(f"The branch name is not valid: '{arguments.branch}'.")
        if (arguments.path is None) != (arguments.path_root is None):
            raise RuntimeError("Specify '--path' and '--path-root' together.")
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
            ignore_root = (
                primary_project_root(root)
                if arguments.directory is None and arguments.path is None
                else root
            )
            if arguments.dry_run:
                if not path.is_relative_to(ignore_root / ".worktrees"):
                    verify_ignored(ignore_root, path)
            else:
                ensure_ignored(ignore_root, path)
        if path.exists():
            raise RuntimeError(f"The worktree path already exists: '{path}'.")
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
    except (OSError, RuntimeError) as error:
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
