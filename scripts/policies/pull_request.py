"""This module defines the pull-request commit and issue-link policy."""

from __future__ import annotations

import re
from typing import Any

CONVENTIONAL_SUBJECT = re.compile(
    r"^(feat|fix|docs|refactor|test|chore|revert|ci|build|perf)"
    r"(\([a-z0-9._/-]+\))?!?: .+"
)
ISSUE_LINK = re.compile(r"(?m)^Closes #[0-9]+\s*$")
DCO_TRAILER = re.compile(r"(?mi)^Signed-off-by: .+ <.+>$")


def flatten_commit_pages(pages: object) -> list[dict[str, Any]]:
    """Validate GraphQL pagination and return every commit node."""
    if not isinstance(pages, list) or not pages:
        raise ValueError("GitHub returned no commit pages.")
    commits: list[dict[str, Any]] = []
    total_count: int | None = None
    for page_number, page in enumerate(pages, start=1):
        try:
            connection = page["data"]["repository"]["pullRequest"]["commits"]
            nodes = connection["nodes"]
            page_info = connection["pageInfo"]
        except (KeyError, TypeError) as error:
            raise ValueError(
                f"GitHub returned commit page {page_number}, which is not valid. "
                f"The operation returned this diagnostic.\n{error}"
            ) from error
        if not isinstance(nodes, list):
            raise TypeError(
                f"GitHub commit page {page_number} has a nodes field that is not valid."
            )
        if not isinstance(page_info, dict) or not isinstance(
            page_info.get("hasNextPage"), bool
        ):
            raise TypeError(
                f"GitHub commit page {page_number} has a pageInfo field that is not valid."
            )
        if any(
            not isinstance(node, dict) or not isinstance(node.get("commit"), dict)
            for node in nodes
        ):
            raise ValueError(
                f"GitHub commit page {page_number} has a commit node that is not valid."
            )
        page_total = connection.get("totalCount")
        if not isinstance(page_total, int):
            raise TypeError(
                f"GitHub commit page {page_number} has a totalCount field that is not valid."
            )
        if total_count is None:
            total_count = page_total
        elif page_total != total_count:
            raise ValueError("The commit count changed during pagination.")
        commits.extend(nodes)
        has_next = page_info.get("hasNextPage")
        if page_number < len(pages) and not has_next:
            raise ValueError(
                "GitHub commit pagination returned an unexpected extra page."
            )
        if page_number == len(pages) and has_next:
            raise ValueError("GitHub commit pagination stopped before the final page.")
    if total_count is None or len(commits) != total_count:
        raise ValueError(
            "GitHub returned incomplete commit pagination. The commit pages report "
            f"a total of {total_count} commits. GitHub returned {len(commits)} commit records."
        )
    return commits


def evaluate_pull_request(
    *,
    body: str,
    author: str,
    commits: list[dict[str, Any]],
    require_issue_link: bool = False,
) -> list[str]:
    """Return all pull-request policy violations."""
    errors: list[str] = []
    if (
        author != "dependabot[bot]"
        and require_issue_link
        and ISSUE_LINK.search(body) is None
    ):
        errors.append("The pull-request body must contain a separate 'Closes #N' line.")
    for node in commits:
        commit = node.get("commit", {})
        oid = str(commit.get("oid", "<unknown>"))
        message = str(commit.get("message", ""))
        signature = commit.get("signature") or {}
        if not signature.get("isValid", False):
            errors.append(f"{oid}: The commit signature is missing or is not valid.")
        if (
            author != "dependabot[bot]"
            and CONVENTIONAL_SUBJECT.match(message.splitlines()[0] if message else "")
            is None
        ):
            errors.append(f"{oid}: The subject does not follow Conventional Commits.")
        if author != "dependabot[bot]" and DCO_TRAILER.search(message) is None:
            errors.append(
                f"{oid}: The Developer Certificate of Origin (DCO) "
                "Signed-off-by trailer is missing."
            )
    return errors
