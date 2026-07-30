#!/usr/bin/env python3
"""Resolve an explicit PR or the sole open PR for the current branch."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from pr_identity import (
    canonical_pull_request_url,
    pull_request_number,
    require_commit_oid,
    require_github_host,
    require_github_repository,
    repository_from_pr_url,
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
    """A forge target supplied without ambient CLI or checkout inference."""

    host: str
    repository: str

    def repository_argument(self) -> str:
        """Return the fully qualified repository target accepted by gh."""
        return f"{self.host}/{self.repository}"


def command(*arguments: str) -> str:
    result = run_command(arguments, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        message = result.stderr.strip() or f"command failed: {' '.join(arguments)}"
        raise RuntimeError(message)
    return result.stdout


def current_branch() -> str:
    """Return the current branch through the hermetic Git read boundary."""
    result = run_command(
        ["git", *git_read_arguments(), "branch", "--show-current"],
        capture_output=True,
        env=git_read_environment(),
        text=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or "git branch --show-current failed"
        raise RuntimeError(message)
    return result.stdout.strip()


def load_object(output: str) -> dict[str, Any]:
    value = json.loads(output)
    if not isinstance(value, dict):
        raise RuntimeError("GitHub returned an invalid pull-request object")
    return value


def target_from_arguments(
    parser: Any,
    identifier: str | None,
    host: str | None,
    repository: str | None,
) -> RepositoryTarget:
    """Resolve a trusted target from explicit flags or one canonical PR URL."""

    def identity_from_url(value: str) -> tuple[int, str]:
        try:
            number = pull_request_number(value)
            return number, repository_from_pr_url(value, number)
        except RuntimeError as error:
            parser.error(f"invalid pull-request URL: {error}")
        raise AssertionError("argument parser returned after a URL error")

    if (host is None) != (repository is None):
        parser.error("--target-host and --target-repository must be supplied together")
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
                parser.error("pull-request URL does not match --target-repository")
        return target
    if identifier is not None and identifier.startswith("https://"):
        _, repository = identity_from_url(identifier)
        return RepositoryTarget(
            host="github.com",
            repository=repository,
        )
    parser.error(
        "numeric pull requests and branch discovery require --target-host and "
        "--target-repository"
    )
    raise AssertionError("argument parser returned after a target error")


def _resolve_open_pr(identifier: str, target: RepositoryTarget) -> dict[str, Any]:
    """Return the complete metadata for one explicitly identified open PR."""
    validate_pr_identifier(identifier)
    number = pull_request_number(identifier)
    if identifier.startswith("https://"):
        supplied_repository = repository_from_pr_url(identifier, number)
        if supplied_repository.casefold() != target.repository.casefold():
            raise RuntimeError("pull-request URL does not match the retained target")
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
        raise RuntimeError(f"pull request {identifier} is not open")
    if pull_request.get("number") != number:
        raise RuntimeError("GitHub returned a pull request different from the request")
    for field in ("baseRefOid", "headRefOid"):
        require_commit_oid(
            pull_request.get(field), f"GitHub immutable PR revision {field}"
        )
    return pull_request


def _validate_repository_identity(
    pull_request: dict[str, Any], target: RepositoryTarget
) -> None:
    """Reject a PR URL that differs from the retained explicit forge target."""
    number = pull_request.get("number")
    url = pull_request.get("url")
    if not isinstance(number, int) or not isinstance(url, str):
        raise RuntimeError("GitHub returned incomplete pull-request identity")
    pull_repository = repository_from_pr_url(url, number)
    if pull_repository.casefold() != target.repository.casefold():
        raise RuntimeError(
            f"pull request {url} does not belong to target repository {target.repository}"
        )
    if url != canonical_pull_request_url(target.repository, number):
        raise RuntimeError(f"GitHub returned invalid pull-request URL: {url}")
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
        raise RuntimeError("current checkout is detached; provide a PR number or URL")
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
        raise RuntimeError("GitHub returned an invalid pull-request list")
    candidates = [item for item in raw_candidates if isinstance(item, dict)]
    if len(candidates) == 1:
        number = candidates[0].get("number")
        if not isinstance(number, int) or number < 1:
            raise RuntimeError("GitHub returned an invalid pull-request candidate")
        return _resolve_open_pr(str(number), target)
    if not candidates:
        raise LookupError(f"no open pull request found for branch {branch!r}")
    rendered = "\n".join(
        f"  #{candidate.get('number')}: {candidate.get('url')}"
        for candidate in candidates
    )
    raise ValueError(f"multiple open pull requests found for {branch!r}:\n{rendered}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argument_parser(description=__doc__)
    parser.add_argument(
        "--target-host",
        metavar="HOST",
        help="canonical GitHub host from the configured forge capability",
    )
    parser.add_argument(
        "--target-repository",
        metavar="OWNER/REPOSITORY",
        help="canonical GitHub repository from the configured forge capability",
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
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1
    print(json.dumps(pull_request, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
