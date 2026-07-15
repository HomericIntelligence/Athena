"""Pull-request commit and issue-link policy."""

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
        raise ValueError("commit pagination returned no pages")
    commits: list[dict[str, Any]] = []
    total_count: int | None = None
    for page_number, page in enumerate(pages, start=1):
        try:
            connection = page["data"]["repository"]["pullRequest"]["commits"]
            nodes = connection["nodes"]
            page_info = connection["pageInfo"]
        except (KeyError, TypeError) as error:
            raise ValueError(
                f"commit pagination page {page_number} is malformed: {error}"
            ) from error
        if not isinstance(nodes, list):
            raise ValueError(f"commit pagination page {page_number} has invalid nodes")
        if not isinstance(page_info, dict) or not isinstance(
            page_info.get("hasNextPage"), bool
        ):
            raise ValueError(
                f"commit pagination page {page_number} has invalid pageInfo"
            )
        if any(
            not isinstance(node, dict) or not isinstance(node.get("commit"), dict)
            for node in nodes
        ):
            raise ValueError(
                f"commit pagination page {page_number} has invalid commit node"
            )
        page_total = connection.get("totalCount")
        if not isinstance(page_total, int):
            raise ValueError(
                f"commit pagination page {page_number} has invalid totalCount"
            )
        if total_count is None:
            total_count = page_total
        elif page_total != total_count:
            raise ValueError("commit count changed during pagination")
        commits.extend(nodes)
        has_next = page_info.get("hasNextPage")
        if page_number < len(pages) and not has_next:
            raise ValueError("commit pagination returned an unexpected extra page")
        if page_number == len(pages) and has_next:
            raise ValueError("commit pagination stopped before the final page")
    if total_count is None or len(commits) != total_count:
        raise ValueError(
            f"commit pagination incomplete: expected {total_count}, got {len(commits)}"
        )
    return commits


def evaluate_pull_request(
    *, body: str, author: str, commits: list[dict[str, Any]]
) -> list[str]:
    """Return all pull-request policy violations."""
    errors: list[str] = []
    if author != "dependabot[bot]" and ISSUE_LINK.search(body) is None:
        errors.append("PR body must contain a standalone 'Closes #N' line")
    for node in commits:
        commit = node.get("commit", {})
        oid = str(commit.get("oid", "<unknown>"))
        message = str(commit.get("message", ""))
        signature = commit.get("signature") or {}
        if not signature.get("isValid", False):
            errors.append(f"{oid}: commit signature is missing or invalid")
        if (
            author != "dependabot[bot]"
            and CONVENTIONAL_SUBJECT.match(message.splitlines()[0] if message else "")
            is None
        ):
            errors.append(f"{oid}: subject is not Conventional Commits")
        if author != "dependabot[bot]" and DCO_TRAILER.search(message) is None:
            errors.append(f"{oid}: DCO Signed-off-by trailer is missing")
    return errors
