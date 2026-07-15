"""Validate pull-request identifiers shared by PR review helpers."""

from __future__ import annotations

import re
from urllib.parse import urlparse


PR_URL = re.compile(r"https://github\.com/[^/\s]+/[^/\s]+/pull/[1-9][0-9]*/?")


def validate_pr_identifier(value: str) -> None:
    """Require a positive PR number or canonical GitHub pull-request URL."""
    if (value.isascii() and value.isdigit() and int(value) > 0) or PR_URL.fullmatch(
        value
    ):
        return
    raise RuntimeError(f"invalid pull-request identifier: {value!r}")


def repository_from_pr_url(url: str, number: int) -> str:
    """Return owner/repository after validating a canonical PR URL and number."""
    parsed_url = urlparse(url)
    path_parts = parsed_url.path.strip("/").split("/")
    if (
        parsed_url.hostname != "github.com"
        or len(path_parts) != 4
        or path_parts[2] != "pull"
        or path_parts[3] != str(number)
    ):
        raise RuntimeError(f"GitHub returned invalid pull-request URL: {url}")
    return "/".join(path_parts[:2])
