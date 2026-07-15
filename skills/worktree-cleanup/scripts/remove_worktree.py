#!/usr/bin/env python3
"""Safely remove one clean, non-current registered worktree after approval."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


def git(cwd: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=cwd, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(arguments)} failed")
    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--expected-head", required=True)
    arguments = parser.parse_args()
    try:
        root = Path(git(Path.cwd(), "rev-parse", "--show-toplevel").strip())
        target = arguments.path.resolve()
        current = Path.cwd().resolve()
        if current == target or target in current.parents:
            raise RuntimeError("refusing to remove the current worktree")
        registered = {
            Path(line.removeprefix("worktree ")).resolve()
            for line in git(root, "worktree", "list", "--porcelain").splitlines()
            if line.startswith("worktree ")
        }
        if target not in registered:
            raise RuntimeError(f"not a registered worktree: {target}")
        if git(target, "status", "--short").strip():
            raise RuntimeError(f"worktree is not clean: {target}")
        head = git(target, "rev-parse", "--verify", "HEAD").strip()
        if head != arguments.expected_head:
            raise RuntimeError(
                f"worktree HEAD changed: expected {arguments.expected_head}, found {head}"
            )
        git(root, "worktree", "remove", str(target))
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1
    print(f"removed {target} at {head}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
