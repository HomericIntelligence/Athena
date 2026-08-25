#!/usr/bin/env python3
"""Resolve an explicit pull request or the only open pull request for the current branch."""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from pr_identity import (
    canonical_pull_request_url,
    pull_request_number,
    repository_from_pr_url,
    require_commit_oid,
    require_github_host,
    require_github_repository,
    validate_pr_identifier,
)

from skills._cli import (
    argument_parser,
    git_read_arguments,
    git_read_environment,
    run_command,
)

FIELDS = "number,url,state,headRefName,baseRefName,headRefOid,baseRefOid"


@dataclass(frozen=True)
class RepositoryTarget:
    """The workflow gets this forge target from explicit input.

    It does not infer the target from the checkout.
    """

    host: str
    repository: str

    def repository_argument(self) -> str:
        """Return the fully qualified repository target for the GitHub CLI."""
        return f"{self.host}/{self.repository}"


def command(*arguments: str) -> str:
    result = run_command(arguments, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        message = result.stderr.strip() or (
            f"The command failed. Command: {' '.join(arguments)}"
        )
        raise RuntimeError(message)
    return result.stdout


def current_branch() -> str:
    """Return the current branch through the isolated Git read boundary."""
    result = run_command(
        ["git", *git_read_arguments(), "branch", "--show-current"],
        capture_output=True,
        env=git_read_environment(),
        text=True,
        check=False,
    )
    if result.returncode != 0:
        message = (
            result.stderr.strip() or "The git branch --show-current command failed."
        )
        raise RuntimeError(message)
    return result.stdout.strip()


def load_object(output: str) -> dict[str, Any]:
    value = json.loads(output)
    if not isinstance(value, dict):
        raise TypeError("GitHub returned a pull-request object that is not valid.")
    return value


def target_from_arguments(
    parser: Any,
    identifier: str | None,
    host: str | None,
    repository: str | None,
) -> RepositoryTarget:
    """Resolve a trusted target from explicit options or one canonical pull-request URL."""

    def identity_from_url(value: str) -> tuple[int, str]:
        try:
            number = pull_request_number(value)
            return number, repository_from_pr_url(value, number)
        except RuntimeError as error:
            parser.error(f"The pull-request URL is not valid: {error}")
        raise AssertionError("The argument parser returned after a URL error.")

    if (host is None) != (repository is None):
        parser.error("Specify --target-host and --target-repository together.")
    if host is not None and repository is not None:
        try:
            target = RepositoryTarget(
                host=require_github_host(host, "--target-host"),
                repository=require_github_repository(repository, "--target-repository"),
            )
        except RuntimeError as error:
            parser.error(str(error))
        if identifier is not None and identifier.startswith("https://"):
            _, supplied_repository = identity_from_url(identifier)
            if supplied_repository.casefold() != target.repository.casefold():
                parser.error(
                    "The pull-request URL does not match '--target-repository'."
                )
        return target
    if identifier is not None and identifier.startswith("https://"):
        _, repository = identity_from_url(identifier)
        return RepositoryTarget(
            host="github.com",
            repository=repository,
        )
    parser.error(
        "For a numeric pull-request identifier or branch discovery, specify "
        "'--target-host' and '--target-repository'."
    )
    raise AssertionError("The argument parser returned after a target error.")


def _resolve_open_pr(identifier: str, target: RepositoryTarget) -> dict[str, Any]:
    """Return complete metadata for one explicitly identified pull request."""
    validate_pr_identifier(identifier)
    number = pull_request_number(identifier)
    if identifier.startswith("https://"):
        supplied_repository = repository_from_pr_url(identifier, number)
        if supplied_repository.casefold() != target.repository.casefold():
            raise RuntimeError(
                "The pull-request URL does not match the retained target."
            )
    pull_request = load_object(
        command(
            "gh",
            "pr",
            "view",
            str(number),
            "--repo",
            target.repository_argument(),
            "--json",
            FIELDS,
        )
    )
    if pull_request.get("state") != "OPEN":
        raise RuntimeError(f"The pull request is not open: '{identifier}'.")
    if pull_request.get("number") != number:
        raise RuntimeError(
            "GitHub returned a pull request that differs from the request."
        )
    for field in ("baseRefOid", "headRefOid"):
        require_commit_oid(
            pull_request.get(field), f"GitHub immutable pull-request revision {field}"
        )
    return pull_request


def _validate_repository_identity(
    pull_request: dict[str, Any], target: RepositoryTarget
) -> None:
    """Reject a pull-request URL that differs from the retained forge target."""
    number = pull_request.get("number")
    url = pull_request.get("url")
    if not isinstance(number, int) or not isinstance(url, str):
        raise TypeError("GitHub returned an incomplete pull-request identity.")
    pull_repository = repository_from_pr_url(url, number)
    if pull_repository.casefold() != target.repository.casefold():
        raise RuntimeError(
            f"The pull request {url} is not in the target repository "
            f"'{target.repository}'."
        )
    if url != canonical_pull_request_url(target.repository, number):
        raise RuntimeError(
            f"GitHub returned a pull-request URL that is not valid: '{url}'."
        )
    pull_request["review_target"] = {
        "host": target.host,
        "kind": "github",
        "number": number,
        "repository": target.repository,
        "url": url,
    }


def resolve(explicit: str | None, target: RepositoryTarget) -> dict[str, Any]:
    if explicit:
        return _resolve_open_pr(explicit, target)

    branch = current_branch()
    if not branch:
        raise RuntimeError(
            "The current checkout is detached. Specify a pull-request number or URL."
        )
    raw_candidates = json.loads(
        command(
            "gh",
            "pr",
            "list",
            "--repo",
            target.repository_argument(),
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
        raise TypeError("GitHub returned a pull-request list that is not valid.")
    candidates = [item for item in raw_candidates if isinstance(item, dict)]
    if len(candidates) == 1:
        number = candidates[0].get("number")
        if not isinstance(number, int) or number < 1:
            raise RuntimeError(
                "GitHub returned a pull-request candidate that is not valid."
            )
        return _resolve_open_pr(str(number), target)
    if not candidates:
        raise LookupError(f"GitHub found no open pull request for branch {branch!r}.")
    rendered = "\n".join(
        f"  #{candidate.get('number')}: {candidate.get('url')}"
        for candidate in candidates
    )
    raise ValueError(
        f"GitHub found multiple open pull requests for {branch!r}.\n{rendered}"
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argument_parser(description=__doc__)
    parser.add_argument(
        "--target-host",
        metavar="HOST",
        help="Use the canonical GitHub host from the configured forge capability.",
    )
    parser.add_argument(
        "--target-repository",
        metavar="OWNER/REPOSITORY",
        help="Use the canonical GitHub repository from the configured forge capability.",
    )
    parser.add_argument("pull_request", nargs="?", metavar="PR_NUMBER_OR_URL")
    arguments = parser.parse_args(argv)
    target = target_from_arguments(
        parser,
        arguments.pull_request,
        arguments.target_host,
        arguments.target_repository,
    )
    try:
        pull_request = resolve(arguments.pull_request, target)
        _validate_repository_identity(pull_request, target)
    except json.JSONDecodeError as error:
        print(error, file=sys.stderr)
        return 1
    except LookupError as error:
        print(error, file=sys.stderr)
        return 2
    except ValueError as error:
        print(error, file=sys.stderr)
        return 3
    except (RuntimeError, TypeError) as error:
        print(error, file=sys.stderr)
        return 1
    print(json.dumps(pull_request, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
