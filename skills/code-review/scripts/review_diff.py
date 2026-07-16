#!/usr/bin/env python3
"""Discover the tracked remote/default branch and print the review diff."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from skills._cli import argument_parser, run_command


def git(*arguments: str, check: bool = True) -> str:
    result = run_command(
        ["git", *arguments], check=check, capture_output=True, text=True
    )
    return result.stdout.strip()


def discover_remote() -> str:
    branch = git("branch", "--show-current")
    configured = git("config", "--get", f"branch.{branch}.remote", check=False)
    if configured and configured != ".":
        return configured
    remotes = git("remote").splitlines()
    if "origin" in remotes:
        return "origin"
    if len(remotes) == 1:
        return remotes[0]
    raise RuntimeError("cannot choose a review remote; configure the branch upstream")


def discover_default_branch(remote: str) -> str:
    output = git("ls-remote", "--symref", remote, "HEAD")
    for line in output.splitlines():
        if line.startswith("ref: refs/heads/") and line.endswith("\tHEAD"):
            return line.removeprefix("ref: refs/heads/").removesuffix("\tHEAD")
    raise RuntimeError(f"cannot resolve the default branch for remote {remote}")


def review_metadata() -> dict[str, str]:
    remote = discover_remote()
    default_branch = discover_default_branch(remote)
    git("fetch", remote, default_branch)
    base_ref = f"{remote}/{default_branch}"
    base = git("merge-base", "HEAD", base_ref)
    return {
        "remote": remote,
        "default_branch": default_branch,
        "base_ref": base_ref,
        "merge_base": base,
        "diff_range": f"{base}...HEAD",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argument_parser(description=__doc__)
    parser.add_argument("--metadata-only", action="store_true")
    arguments = parser.parse_args(argv)
    try:
        metadata = review_metadata()
        if arguments.metadata_only:
            print(json.dumps(metadata, sort_keys=True))
            return 0
        print(json.dumps(metadata, sort_keys=True))
        run_command(["git", "diff", metadata["diff_range"], "--stat"], check=True)
        run_command(["git", "diff", metadata["diff_range"]], check=True)
    except (RuntimeError, subprocess.SubprocessError) as error:
        parser.exit(1, f"error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
