#!/usr/bin/env python3
"""Collect GitHub PR metadata, changed paths, and current check output."""

from __future__ import annotations

from pathlib import Path
import json
import sys
from typing import Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from pr_identity import repository_from_pr_url, validate_pr_identifier
from skills._cli import argument_parser, run_command


# Keep this query below GitHub's GraphQL complexity budget. Fetch changed files
# separately through the paginated REST endpoint rather than selecting commits
# or files here.
FIELDS = (
    "number,title,body,state,isDraft,author,baseRefName,headRefName,"
    "reviews,statusCheckRollup,closingIssuesReferences,url"
)


def metadata_error(metadata: object) -> str | None:
    """Return a diagnostic when GitHub returns partial PR metadata."""
    if not isinstance(metadata, dict):
        return "PR metadata must be a JSON object"
    required_types = {
        "number": int,
        "title": str,
        "author": dict,
        "baseRefName": str,
        "headRefName": str,
        "statusCheckRollup": list,
        "url": str,
    }
    invalid = [
        field
        for field, expected_type in required_types.items()
        if not isinstance(metadata.get(field), expected_type)
    ]
    author = metadata.get("author")
    if not isinstance(author, dict) or not isinstance(author.get("login"), str):
        invalid.append("author.login")
    if invalid:
        return "GitHub returned incomplete or invalid PR metadata fields: " + ", ".join(
            sorted(set(invalid))
        )
    return None


def gh(*arguments: str, accepted_codes: tuple[int, ...] = (0,)) -> str:
    result = run_command(
        ["gh", *arguments], capture_output=True, text=True, check=False
    )
    if result.returncode not in accepted_codes:
        raise RuntimeError(result.stderr.strip() or f"gh {' '.join(arguments)} failed")
    return result.stdout


def main(argv: Sequence[str] | None = None) -> int:
    parser = argument_parser(description=__doc__)
    parser.add_argument("pull_request", metavar="PR_NUMBER_OR_URL")
    arguments = parser.parse_args(argv)
    pull_request = arguments.pull_request
    try:
        validate_pr_identifier(pull_request)
        metadata = json.loads(gh("pr", "view", pull_request, "--json", FIELDS))
        metadata_problem = metadata_error(metadata)
        if metadata_problem:
            print(
                json.dumps(
                    {
                        "error": "incomplete PR metadata",
                        "details": metadata_problem,
                    },
                    sort_keys=True,
                )
            )
            return 1
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
                "changed_paths": changed_files,
                "checks": checks,
                "pull_request": metadata,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
