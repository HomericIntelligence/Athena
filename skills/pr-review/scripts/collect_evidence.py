#!/usr/bin/env python3
"""Collect GitHub PR metadata, changed paths, and current check output."""

from __future__ import annotations

import json
import subprocess
import sys

from pr_identity import repository_from_pr_url, validate_pr_identifier


FIELDS = (
    "number,title,body,state,isDraft,author,baseRefName,headRefName,commits,files,"
    "reviews,statusCheckRollup,closingIssuesReferences,url"
)


def gh(*arguments: str, accepted_codes: tuple[int, ...] = (0,)) -> str:
    result = subprocess.run(
        ["gh", *arguments], capture_output=True, text=True, check=False
    )
    if result.returncode not in accepted_codes:
        raise RuntimeError(result.stderr.strip() or f"gh {' '.join(arguments)} failed")
    return result.stdout


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: collect_evidence.py PR_NUMBER_OR_URL", file=sys.stderr)
        return 64
    pull_request = sys.argv[1]
    try:
        validate_pr_identifier(pull_request)
        metadata = json.loads(gh("pr", "view", pull_request, "--json", FIELDS))
        repository_data = json.loads(gh("repo", "view", "--json", "nameWithOwner"))
        repository = repository_data.get("nameWithOwner")
        number = metadata.get("number")
        url = metadata.get("url")
        if (
            not isinstance(repository, str)
            or not isinstance(number, int)
            or not isinstance(url, str)
        ):
            raise RuntimeError("GitHub returned incomplete repository or PR identity")
        pull_repository = repository_from_pr_url(url, number)
        if pull_repository.casefold() != repository.casefold():
            raise RuntimeError(
                f"pull request {url} does not belong to current repository {repository}"
            )
        changed_files = [
            line
            for line in gh(
                "api",
                "--paginate",
                f"repos/{repository}/pulls/{number}/files",
                "--jq",
                ".[].filename",
            ).splitlines()
            if line
        ]
        checks = json.loads(
            gh(
                "pr",
                "checks",
                pull_request,
                "--json",
                "name,state,startedAt,completedAt,link,workflow",
                accepted_codes=(0, 1, 8),
            )
        )
        if not isinstance(checks, list):
            raise RuntimeError("GitHub returned invalid check evidence")
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
