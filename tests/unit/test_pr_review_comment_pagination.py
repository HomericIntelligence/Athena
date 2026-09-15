"""Test bounded collection of large linked-issue comment histories."""

from __future__ import annotations

import json
import sys
import unittest
from collections.abc import Sequence
from typing import Any
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from tests.unit.test_pr_review_contract_hardening import load_collector


class CommentPages:
    """Serve ordered comments through the requested GitHub page boundaries."""

    def __init__(self, collector: Any, comments: list[dict[str, Any]]) -> None:
        self.collector = collector
        self.comments = comments
        self.requests: list[tuple[int, int]] = []

    def __call__(
        self, arguments: Sequence[str], *, maximum_bytes: int, **kwargs: Any
    ) -> bytes:
        """Enforce the output bound on each requested comment page."""
        query = parse_qs(urlsplit(arguments[-1]).query)
        size = int(query["per_page"][0])
        page = int(query["page"][0])
        self.requests.append((size, page))
        start = (page - 1) * size
        response = json.dumps(self.comments[start : start + size]).encode()
        if len(response) > maximum_bytes:
            raise self.collector.LinkedRequirementsCoverageGap(kwargs["limit_error"])
        return response


class LinkedCommentPaginationTests(unittest.TestCase):
    """Preserve complete evidence within every existing collection budget."""

    def setUp(self) -> None:
        self.module_name = f"test_comment_pagination_{id(self)}"
        self.collector = load_collector(self.module_name)

    def tearDown(self) -> None:
        sys.modules.pop(self.module_name, None)

    def test_large_history_is_complete_and_ordered(self) -> None:
        """Collect a realistic history that cannot fit in one response."""
        comments = [{"id": i, "body": "x" * 4400} for i in range(72)]
        self.assertGreater(len(json.dumps(comments).encode()), 256 * 1024)
        provider = CommentPages(self.collector, comments)
        with patch.object(self.collector, "bounded_gh_output", side_effect=provider):
            result = self.collector.paginated_issue_comments("owner/repo", 1)
        self.assertEqual(comments, result)
        self.assertGreater(len(provider.requests), 1)

    def test_full_history_requires_an_empty_terminal_page(self) -> None:
        """Verify completeness after ten full pages."""
        comments = [{"id": i} for i in range(250)]
        provider = CommentPages(self.collector, comments)
        with patch.object(self.collector, "bounded_gh_output", side_effect=provider):
            result = self.collector.paginated_issue_comments("owner/repo", 1)
        self.assertEqual(comments, result)
        self.assertEqual(11, len(provider.requests))

    def test_nonempty_eleventh_page_rejects_the_whole_history(self) -> None:
        """Do not return partial evidence beyond the page budget."""
        provider = CommentPages(self.collector, [{"id": i} for i in range(251)])
        with (
            patch.object(self.collector, "bounded_gh_output", side_effect=provider),
            self.assertRaisesRegex(
                self.collector.LinkedRequirementsCoverageGap, "page limit"
            ),
        ):
            self.collector.paginated_issue_comments("owner/repo", 1)

    def test_oversized_comment_is_rejected(self) -> None:
        """Retain the response limit for an oversized individual comment."""
        provider = CommentPages(self.collector, [{"id": 1, "body": "x" * (256 * 1024)}])
        with (
            patch.object(self.collector, "bounded_gh_output", side_effect=provider),
            self.assertRaisesRegex(
                self.collector.LinkedRequirementsCoverageGap, "byte limit"
            ),
        ):
            self.collector.paginated_issue_comments("owner/repo", 1)

    def test_later_page_respects_remaining_issue_bytes(self) -> None:
        """Reject a later page when the issue byte budget is exhausted."""
        comments = [{"id": i, "body": "x" * 100} for i in range(40)]
        provider = CommentPages(self.collector, comments)
        with (
            patch.object(self.collector, "MAX_LINKED_ISSUE_COMMENT_BYTES", 4000),
            patch.object(self.collector, "bounded_gh_output", side_effect=provider),
            self.assertRaisesRegex(
                self.collector.LinkedRequirementsCoverageGap, "byte limit"
            ),
        ):
            self.collector.paginated_issue_comments("owner/repo", 1)

    def test_later_issue_respects_aggregate_bytes(self) -> None:
        """Reject a second issue when the shared byte budget is exhausted."""
        comments = [{"id": i, "body": "x" * 100} for i in range(20)]
        provider = CommentPages(self.collector, comments)
        budget = self.collector.LinkedRequirementBudget()
        with (
            patch.object(self.collector, "MAX_LINKED_REQUIREMENT_BYTES", 4000),
            patch.object(self.collector, "bounded_gh_output", side_effect=provider),
        ):
            self.assertEqual(
                comments,
                self.collector.paginated_issue_comments("owner/repo", 1, budget),
            )
            with self.assertRaisesRegex(
                self.collector.LinkedRequirementsCoverageGap, "byte limit"
            ):
                self.collector.paginated_issue_comments("owner/repo", 2, budget)
