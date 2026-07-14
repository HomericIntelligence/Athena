#!/usr/bin/env python3
"""Collect reproducible recent-change and source-pattern evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys


def run(*arguments: str, accepted_codes: tuple[int, ...] = (0, 1)) -> str:
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
        recent_commits = run("git", "log", "--oneline", "-10")
        oldest_commit = run("git", "rev-list", "--max-parents=0", "HEAD").splitlines()[
            0
        ]
        recent_diff = run("git", "diff", "--stat", oldest_commit, "HEAD")
        pattern_matches = run(
            "rg", "--line-number", "--", arguments.pattern, arguments.source_root
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
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
