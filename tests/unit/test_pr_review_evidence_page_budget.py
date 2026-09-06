"""Test the aggregate byte budget for head-bound check-run evidence."""

from __future__ import annotations

import json
import sys
import unittest
from collections.abc import Sequence
from typing import Any
from unittest.mock import patch

from tests.unit.test_pr_review_contract_hardening import HEAD_OID, load_collector


class BoundedResponder:
    """Return canned pages while enforcing the requested byte budget."""

    def __init__(self, collector: Any, responses: list[bytes]) -> None:
        self.collector = collector
        self.responses = iter(responses)
        self.calls: list[int] = []

    def __call__(
        self,
        _arguments: Sequence[str],
        *,
        maximum_bytes: int,
        **_kwargs: Any,
    ) -> bytes:
        """Return the next page or raise when it exceeds its requested bound."""
        self.calls.append(maximum_bytes)
        response = next(self.responses)
        if len(response) > maximum_bytes:
            raise self.collector.CheckEvidenceCoverageGap(
                "The GitHub check-run response exceeds the safe byte limit."
            )
        return response


class CheckRunPageBudgetTests(unittest.TestCase):
    """Require large valid pages and bounded aggregate check-run evidence."""

    def setUp(self) -> None:
        self.module_name = f"test_collect_evidence_budget_{id(self)}"
        self.collector = load_collector(self.module_name)

    def tearDown(self) -> None:
        sys.modules.pop(self.module_name, None)

    @staticmethod
    def _run(run_id: int, name: str = "required-check") -> dict[str, Any]:
        """Create a valid check run with a realistic large output summary."""
        return {
            "id": run_id,
            "name": name,
            "head_sha": HEAD_OID,
            "status": "completed",
            "conclusion": "success",
            "output": {
                "title": f"{name} result",
                "summary": "Job completed with diagnostic details. " * 100,
            },
        }

    @staticmethod
    def _page(total_count: int, runs: list[dict[str, Any]]) -> bytes:
        """Serialize one GitHub check-run page."""
        return json.dumps(
            {"total_count": total_count, "check_runs": runs},
            separators=(",", ":"),
        ).encode()

    def _bounded_responder(self, responses: list[bytes]) -> BoundedResponder:
        """Create a typed canned-page responder."""
        return BoundedResponder(self.collector, responses)

    def test_large_valid_page_uses_aggregate_budget(self) -> None:
        """Collect 75 runs when one valid page is larger than 256 KiB."""
        response = self._page(75, [self._run(run_id) for run_id in range(1, 76)])
        self.assertGreater(len(response), 256 * 1024)
        self.assertLess(len(response), self.collector.MAX_CHECK_RUN_BYTES)
        responder = self._bounded_responder([response])

        with patch.object(self.collector, "bounded_gh_output", side_effect=responder):
            runs = self.collector.head_bound_check_runs("owner/repository", HEAD_OID)

        self.assertEqual(list(range(1, 76)), [run["id"] for run in runs])
        self.assertEqual([self.collector.MAX_CHECK_RUN_BYTES], responder.calls)

    def test_multipage_completeness_preserves_response_order(self) -> None:
        """Collect all runs from pages larger than the former page budget."""
        first = [self._run(run_id) for run_id in range(1, 41)]
        second = [self._run(run_id) for run_id in range(41, 76)]
        responses = [self._page(75, first), self._page(75, second)]
        self.assertGreater(sum(map(len, responses)), 256 * 1024)
        responder = self._bounded_responder(responses)

        with patch.object(self.collector, "bounded_gh_output", side_effect=responder):
            runs = self.collector.head_bound_check_runs("owner/repository", HEAD_OID)

        self.assertEqual(list(range(1, 76)), [run["id"] for run in runs])
        self.assertEqual(2, len(responder.calls))
        self.assertEqual(
            self.collector.MAX_CHECK_RUN_BYTES - len(responses[0]), responder.calls[1]
        )

    def test_duplicate_suite_reruns_are_deterministic(self) -> None:
        """Keep distinct reruns with the same check name in provider order."""
        response = self._page(
            2,
            [self._run(20, "build"), self._run(21, "build")],
        )
        responder = self._bounded_responder([response])

        with patch.object(self.collector, "bounded_gh_output", side_effect=responder):
            runs = self.collector.head_bound_check_runs("owner/repository", HEAD_OID)

        self.assertEqual([20, 21], [run["id"] for run in runs])
        self.assertEqual(["build", "build"], [run["name"] for run in runs])

    def test_aggregate_budget_gap_remains_fail_closed(self) -> None:
        """Reject a response larger than the aggregate budget."""
        response = self._page(1, [self._run(1)])
        responder = self._bounded_responder([response])

        with (
            patch.object(self.collector, "MAX_CHECK_RUN_BYTES", len(response) - 1),
            patch.object(self.collector, "bounded_gh_output", side_effect=responder),
            self.assertRaisesRegex(
                self.collector.CheckEvidenceCoverageGap, "safe byte limit"
            ),
        ):
            self.collector.head_bound_check_runs("owner/repository", HEAD_OID)

    def test_later_page_that_exceeds_remaining_budget_fails_closed(self) -> None:
        """Reject a later page when it exceeds the remaining aggregate budget."""
        first = self._page(2, [self._run(1)])
        second = self._page(2, [self._run(2)])
        responder = self._bounded_responder([first, second])

        with (
            patch.object(
                self.collector,
                "MAX_CHECK_RUN_BYTES",
                len(first) + len(second) - 1,
            ),
            patch.object(self.collector, "bounded_gh_output", side_effect=responder),
            self.assertRaisesRegex(
                self.collector.CheckEvidenceCoverageGap, "safe byte limit"
            ),
        ):
            self.collector.head_bound_check_runs("owner/repository", HEAD_OID)


if __name__ == "__main__":
    unittest.main()
