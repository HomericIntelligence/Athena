"""Validate pull-request identifiers shared by PR review helpers."""

from __future__ import annotations

import re
from urllib.parse import urlparse


PR_URL = re.compile(r"https://github\.com/[^/\s]+/[^/\s]+/pull/[1-9][0-9]*")
COMMIT_OID = re.compile(r"[0-9a-f]{40}\Z")
GITHUB_REPOSITORY = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9._-]+\Z")
GITHUB_HOST = "github.com"


def validate_pr_identifier(value: str) -> None:
    """Require a positive PR number or canonical GitHub pull-request URL."""
    if (value.isascii() and value.isdigit() and int(value) > 0) or PR_URL.fullmatch(
        value
    ):
        return
    raise RuntimeError(f"invalid pull-request identifier: {value!r}")


def require_commit_oid(value: object, label: str) -> str:
    """Return one canonical immutable commit OID or fail closed."""
    if not isinstance(value, str) or COMMIT_OID.fullmatch(value) is None:
        raise RuntimeError(f"{label} must be a lowercase 40-hex Git commit OID")
    return value


def require_github_repository(value: object, label: str) -> str:
    """Return a canonical owner/repository target or reject unsafe input."""
    if not isinstance(value, str) or GITHUB_REPOSITORY.fullmatch(value) is None:
        raise RuntimeError(f"{label} must be a canonical GitHub owner/repository")
    return value


def require_github_host(value: object, label: str) -> str:
    """Return the supported canonical GitHub hostname or fail closed."""
    if value != GITHUB_HOST:
        raise RuntimeError(f"{label} must be {GITHUB_HOST}")
    return GITHUB_HOST


def canonical_pull_request_url(repository: object, number: object) -> str:
    """Return one exact public-GitHub pull-request URL from trusted identity."""
    canonical_repository = require_github_repository(repository, "repository")
    if isinstance(number, bool) or not isinstance(number, int) or number < 1:
        raise RuntimeError("pull-request number must be a positive integer")
    return f"https://{GITHUB_HOST}/{canonical_repository}/pull/{number}"


def pull_request_number(value: str) -> int:
    """Return the positive number encoded by a validated PR identifier."""
    validate_pr_identifier(value)
    if value.isdigit():
        return int(value)
    path = urlparse(value).path.rstrip("/")
    return int(path.rsplit("/", maxsplit=1)[-1])


def require_canonical_pull_request_url(
    value: object, repository: object, number: object, label: str
) -> str:
    """Require the exact canonical URL for a retained pull-request identity."""
    canonical_url = canonical_pull_request_url(repository, number)
    if value != canonical_url:
        raise RuntimeError(f"{label} must be the canonical GitHub pull-request URL")
    return canonical_url


def repository_from_pr_url(url: str, number: int) -> str:
    """Return owner/repository after validating a canonical PR URL and number."""
    parsed_url = urlparse(url)
    path_parts = parsed_url.path.strip("/").split("/")
    if len(path_parts) != 4 or path_parts[2] != "pull" or path_parts[3] != str(number):
        raise RuntimeError(f"GitHub returned invalid pull-request URL: {url}")
    repository = "/".join(path_parts[:2])
    if url != canonical_pull_request_url(repository, number):
        raise RuntimeError(f"GitHub returned invalid pull-request URL: {url}")
    return repository
