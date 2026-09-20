"""Test bounded collection of large linked-issue comment histories."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from collections.abc import Sequence
from hashlib import sha256
from pathlib import Path
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

    def test_batch_cursor_preserves_comments_after_ten_pages(self) -> None:
        comments = [{"id": i, "body": "text"} for i in range(251)]
        provider = CommentPages(self.collector, comments)
        with patch.object(self.collector, "bounded_gh_output", side_effect=provider):
            first = self.collector.issue_comment_batch("owner/repo", 1)
            second = self.collector.issue_comment_batch(
                "owner/repo", 1, first.next_page
            )
        self.assertEqual(11, first.next_page)
        self.assertIsNone(second.next_page)
        self.assertEqual(comments, [*first.comments, *second.comments])

    def test_disk_digest_matches_complete_canonical_content(self) -> None:
        comments = [{"id": i, "body": "text"} for i in range(251)]
        provider = CommentPages(self.collector, comments)
        issue = {"body": "body", "state": "OPEN", "title": "Title"}
        canonical = self.collector.canonical_json
        expected = {
            **issue,
            "comments": [
                json.loads(value)
                for value in sorted(
                    canonical(comment, "comment") for comment in comments
                )
            ],
        }
        with patch.object(self.collector, "bounded_gh_output", side_effect=provider):
            actual = self.collector.issue_content_digest("owner/repo", 1, issue)
        self.assertEqual(
            sha256(canonical(expected, "issue").encode()).hexdigest(), actual
        )

    def test_repeated_comment_page_stops_with_a_checkpoint(self) -> None:
        page = [{"id": i, "body": "same"} for i in range(25)]
        issue = {"body": "body", "state": "OPEN", "title": "Title"}
        with (
            patch.object(
                self.collector,
                "bounded_gh_output",
                return_value=json.dumps(page).encode(),
            ) as provider,
            self.assertRaises(self.collector.CommentDigestCheckpoint) as raised,
        ):
            self.collector.issue_content_digest("owner/repo", 1, issue)
        checkpoint = raised.exception.checkpoint_path
        self.addCleanup(checkpoint.unlink)
        self.assertTrue(checkpoint.is_file())
        self.assertLessEqual(provider.call_count, 10)
        self.assertIn("repeated a comment identity", str(raised.exception))

    def test_comment_checkpoint_resumes_to_the_complete_digest(self) -> None:
        comments = [{"id": i, "body": "text"} for i in range(251)]
        provider = CommentPages(self.collector, comments)
        issue = {"body": "body", "state": "OPEN", "title": "Title"}
        with patch.object(self.collector, "bounded_gh_output", side_effect=provider):
            with self.assertRaises(self.collector.CommentDigestCheckpoint) as raised:
                self.collector.issue_content_digest(
                    "owner/repo", 1, issue, maximum_batches=1
                )
            checkpoint = raised.exception.checkpoint_path
            self.addCleanup(checkpoint.unlink)
            self.assertEqual(11, raised.exception.next_page)
            resumed = self.collector.issue_content_digest(
                "owner/repo",
                1,
                issue,
                checkpoint_path=checkpoint,
            )
            complete = self.collector.issue_content_digest("owner/repo", 1, issue)
            with self.assertRaisesRegex(RuntimeError, "issue binding"):
                self.collector.issue_content_digest(
                    "owner/repo", 2, issue, checkpoint_path=checkpoint
                )
        self.assertEqual(complete, resumed)

    def test_collector_coordinator_continues_and_revalidates_final_history(
        self,
    ) -> None:
        comments = [{"id": i, "body": "text"} for i in range(251)]
        provider = CommentPages(self.collector, comments)
        issue = {"body": "body", "state": "OPEN", "title": "Title"}
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory) / "issue.sqlite"
            with patch.object(
                self.collector, "bounded_gh_output", side_effect=provider
            ):
                first = self.collector.complete_issue_content_digest(
                    "owner/repo",
                    1,
                    issue,
                    checkpoint_path=checkpoint,
                    maximum_batches=1,
                )
                calls = len(provider.requests)
                cached = self.collector.complete_issue_content_digest(
                    "owner/repo",
                    1,
                    issue,
                    checkpoint_path=checkpoint,
                )
                self.assertEqual(calls, len(provider.requests))
                comments[-1]["body"] = "changed after initial collection"
                final = self.collector.complete_issue_content_digest(
                    "owner/repo",
                    1,
                    issue,
                    checkpoint_path=checkpoint,
                    restart_completed=True,
                    maximum_batches=1,
                )
            self.assertEqual(first, cached)
            self.assertNotEqual(first, final)
            self.assertGreater(len(provider.requests), calls)

    def test_new_final_invocation_refreshes_an_interrupted_prefix(self) -> None:
        comments = [{"id": i, "body": "original"} for i in range(251)]
        provider = CommentPages(self.collector, comments)
        issue = {"body": "body", "state": "OPEN", "title": "Title"}
        with patch.object(self.collector, "bounded_gh_output", side_effect=provider):
            initial = self.collector.issue_content_digest("owner/repo", 1, issue)
            with self.assertRaises(self.collector.CommentDigestCheckpoint) as raised:
                self.collector.issue_content_digest(
                    "owner/repo",
                    1,
                    issue,
                    maximum_batches=1,
                )
            checkpoint = raised.exception.checkpoint_path
            self.addCleanup(checkpoint.unlink)
            self.assertEqual(11, raised.exception.next_page)
            comments[0]["body"] = "edited while final verification was paused"
            requests_before_resume = len(provider.requests)
            final = self.collector.complete_issue_content_digest(
                "owner/repo",
                1,
                issue,
                checkpoint_path=checkpoint,
                restart_completed=True,
                maximum_batches=1,
            )
            expected = self.collector.issue_content_digest("owner/repo", 1, issue)
        self.assertEqual((25, 1), provider.requests[requests_before_resume])
        self.assertEqual(expected, final)
        self.assertNotEqual(initial, final)

    def test_collector_deadline_preserves_public_resume_path(self) -> None:
        comments = [{"id": 1, "body": "text"}]
        provider = CommentPages(self.collector, comments)
        issue = {"body": "body", "state": "OPEN", "title": "Title"}
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory) / "issue.sqlite"
            with patch.object(
                self.collector, "bounded_gh_output", side_effect=provider
            ):
                with (
                    patch.object(
                        self.collector.time, "monotonic", side_effect=[0.0, 1.0]
                    ),
                    self.assertRaises(self.collector.CommentDigestCheckpoint) as raised,
                ):
                    self.collector.complete_issue_content_digest(
                        "owner/repo",
                        1,
                        issue,
                        checkpoint_path=checkpoint,
                        operation_seconds=0.5,
                    )
                self.assertEqual(checkpoint, raised.exception.checkpoint_path)
                self.assertTrue(checkpoint.is_file())
                actual = self.collector.complete_issue_content_digest(
                    "owner/repo",
                    1,
                    issue,
                    checkpoint_path=checkpoint,
                )
                expected = self.collector.issue_content_digest("owner/repo", 1, issue)
            self.assertEqual(expected, actual)

    def test_comment_deadlines_reject_values_outside_the_operation_bound(self) -> None:
        for value in ("nan", "inf", "-inf", "0", "-1", "3601"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.collector.positive_comment_operation_seconds(value)
        self.assertEqual(
            3600.0, self.collector.positive_comment_operation_seconds("3600")
        )

    def test_linked_requirements_forward_the_authorized_comment_deadline(self) -> None:
        issue = {
            "id": "I_1",
            "number": 1,
            "url": "https://github.com/owner/repo/issues/1",
            "title": "Title",
            "body": "Body",
            "state": "OPEN",
        }
        metadata: dict[str, Any] = {"closingIssuesReferences": []}
        with (
            patch.object(self.collector, "linked_issue_metadata", return_value=issue),
            patch.object(
                self.collector, "complete_issue_content_digest", return_value="a" * 64
            ) as collect,
        ):
            self.collector.linked_requirements(
                metadata,
                requirement_issues=[issue["url"]],
                comment_operation_seconds=3600.0,
            )
        self.assertEqual(3600.0, collect.call_args.kwargs["operation_seconds"])

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
