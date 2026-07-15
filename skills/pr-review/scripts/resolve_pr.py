#!/usr/bin/env python3
"""Resolve an explicit PR or the sole open PR for the current branch."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from pr_identity import validate_pr_identifier
from skills._cli import argument_parser


FIELDS = "number,url,state,headRefName,baseRefName"


def command(*arguments: str) -> str:
    result = subprocess.run(arguments, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        message = result.stderr.strip() or f"command failed: {' '.join(arguments)}"
        raise RuntimeError(message)
    return result.stdout


def load_object(output: str) -> dict[str, Any]:
    value = json.loads(output)
    if not isinstance(value, dict):
        raise RuntimeError("GitHub returned an invalid pull-request object")
    return value


def resolve(explicit: str | None) -> dict[str, Any]:
    if explicit:
        validate_pr_identifier(explicit)
        pull_request = load_object(
            command("gh", "pr", "view", explicit, "--json", FIELDS)
        )
        if pull_request.get("state") != "OPEN":
            raise RuntimeError(f"pull request {explicit} is not open")
        return pull_request

    branch = command("git", "branch", "--show-current").strip()
    if not branch:
        raise RuntimeError("current checkout is detached; provide a PR number or URL")
    raw_candidates = json.loads(
        command(
            "gh",
            "pr",
            "list",
            "--state",
            "open",
            "--head",
            branch,
            "--json",
            FIELDS,
            "--limit",
            "2",
        )
    )
    if not isinstance(raw_candidates, list):
        raise RuntimeError("GitHub returned an invalid pull-request list")
    candidates = [item for item in raw_candidates if isinstance(item, dict)]
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise LookupError(f"no open pull request found for branch {branch!r}")
    rendered = "\n".join(
        f"  #{candidate.get('number')}: {candidate.get('url')}"
        for candidate in candidates
    )
    raise ValueError(f"multiple open pull requests found for {branch!r}:\n{rendered}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argument_parser(description=__doc__)
    parser.add_argument("pull_request", nargs="?", metavar="PR_NUMBER_OR_URL")
    arguments = parser.parse_args(argv)
    try:
        pull_request = resolve(arguments.pull_request)
    except json.JSONDecodeError as error:
        print(error, file=sys.stderr)
        return 1
    except LookupError as error:
        print(error, file=sys.stderr)
        return 2
    except ValueError as error:
        print(error, file=sys.stderr)
        return 3
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1
    print(json.dumps(pull_request, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
