#!/usr/bin/env python3
"""Collect reproducible recent-change and source-pattern evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys


EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def run(*arguments: str, accepted_codes: tuple[int, ...] = (0,)) -> str:
    result = subprocess.run(arguments, capture_output=True, text=True, check=False)
    if result.returncode not in accepted_codes:
        raise RuntimeError(result.stderr.strip() or f"{' '.join(arguments)} failed")
    return result.stdout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pattern")
    parser.add_argument("--source-root", default=".")
    arguments = parser.parse_args()
    try:
        try:
            recent_revisions = run(
                "git", "rev-list", "--max-count=10", "HEAD"
            ).splitlines()
        except RuntimeError as error:
            raise RuntimeError(f"cannot resolve HEAD: {error}") from error
        if not recent_revisions:
            raise RuntimeError("cannot resolve HEAD: repository has no commits")
        recent_commits = run("git", "log", "--oneline", "-10")
        oldest_parent = run(
            "git",
            "rev-parse",
            "--verify",
            f"{recent_revisions[-1]}^",
            accepted_codes=(0, 128),
        ).strip()
        recent_range = f"{oldest_parent or EMPTY_TREE}..HEAD"
        recent_diff = run("git", "diff", "--stat", recent_range)
        pattern_matches = run(
            "git",
            "grep",
            "--line-number",
            "-e",
            arguments.pattern,
            "--",
            arguments.source_root,
            accepted_codes=(0, 1),
        )
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "pattern_matches": pattern_matches,
                "recent_commits": recent_commits,
                "recent_diff": recent_diff,
                "recent_range": recent_range,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
