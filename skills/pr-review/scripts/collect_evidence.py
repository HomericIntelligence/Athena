#!/usr/bin/env python3
"""Collect GitHub PR metadata, changed paths, and current check output."""

from __future__ import annotations

import json
import subprocess
import sys


FIELDS = (
    "number,title,body,state,isDraft,author,baseRefName,headRefName,commits,files,"
    "reviews,statusCheckRollup,closingIssuesReferences,url"
)


def gh(*arguments: str) -> str:
    result = subprocess.run(
        ["gh", *arguments], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"gh {' '.join(arguments)} failed")
    return result.stdout


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: collect_evidence.py PR_NUMBER_OR_URL", file=sys.stderr)
        return 64
    pull_request = sys.argv[1]
    try:
        metadata = json.loads(gh("pr", "view", pull_request, "--json", FIELDS))
        changed_files = [
            line
            for line in gh("pr", "diff", pull_request, "--name-only").splitlines()
            if line
        ]
        checks = gh("pr", "checks", pull_request)
    except (RuntimeError, json.JSONDecodeError) as error:
        print(error, file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "changed_files": changed_files,
                "checks": checks,
                "pull_request": metadata,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
