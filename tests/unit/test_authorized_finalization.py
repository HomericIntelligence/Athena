"""Action-bound issue finalization keeps foreign comments unchanged."""

from __future__ import annotations

import copy
import unittest
from types import ModuleType
from typing import Any

from tests.unit import test_issue_review_exchange as fixtures


class AuthorizedFinalizationTests(unittest.TestCase):
    fixture: fixtures.IssueReviewExchangeTests
    adapter: ModuleType

    @classmethod
    def setUpClass(cls) -> None:
        fixtures.IssueReviewExchangeTests.setUpClass()
        cls.fixture = fixtures.IssueReviewExchangeTests()
        cls.adapter = cls.fixture.adapter

    def authorized_request(self) -> dict[str, Any]:
        snapshot = self.fixture.go_snapshot()
        for comment in snapshot["comments"]:
            comment["author"]["id"] = "U_foreign"
        candidate = "# Final plan"
        normalized = self.adapter._snapshot(snapshot)
        plans = self.adapter._role_comments(normalized, self.adapter.PLAN_MARKERS)
        reviews = self.adapter._role_comments(normalized, self.adapter.REVIEW_MARKERS)
        record = {
            "schema_id": "athena.issue-exchange.finalize-authority",
            "schema_version": 1,
            "action": "finalize_foreign_sources",
            "target": self.adapter._core_target(normalized),
            "actor_id": snapshot["actor"]["id"],
            "plan": self.adapter._artifact_summary(plans[0]),
            "review": self.adapter._artifact_summary(reviews[0]),
            "issue_body_sha256": self.adapter._body_sha256(snapshot["issue"]["body"]),
            "candidate_body_sha256": self.adapter._body_sha256(candidate),
        }
        body = self.adapter.review_exchange.canonical_json(record)
        authority = self.fixture.comment("authority", body)
        authority["author"]["is_authority"] = True
        snapshot["comments"].append(authority)
        return {
            "snapshot": snapshot,
            "candidate_body": candidate,
            "source_authority_receipt": {
                "reference": authority["url"],
                "sha256": self.adapter._body_sha256(body),
            },
        }

    def test_explicit_authority_allows_body_update_without_foreign_cleanup(
        self,
    ) -> None:
        request = self.authorized_request()
        original_comments = copy.deepcopy(request["snapshot"]["comments"])
        prepared = self.adapter.verify_finalize(request)
        self.assertEqual("ready", prepared["status"])
        self.assertEqual([], prepared["deletion_allowlist"])
        snapshot = request["snapshot"]
        snapshot["issue"]["body"] = prepared["operation"]["body"]
        verified = self.adapter.verify_finalize(
            {"snapshot": snapshot, "prepared": prepared}
        )
        self.assertEqual("verified", verified["status"])
        self.assertEqual([], verified["deletion_allowlist"])
        self.assertEqual(original_comments, snapshot["comments"])
        completed = self.adapter.verify_finalize(
            {"snapshot": snapshot, "candidate_body": "Ignored"}
        )
        self.assertEqual("no_change", completed["status"])

    def test_foreign_sources_without_authority_remain_withheld(self) -> None:
        request = self.authorized_request()
        del request["source_authority_receipt"]
        result = self.adapter.verify_finalize(request)
        self.assertEqual("withheld", result["status"])

    def test_authority_cannot_be_reused_for_changed_update(self) -> None:
        for field in ("candidate", "actor", "source", "issue", "authority"):
            with self.subTest(field=field):
                request = self.authorized_request()
                snapshot = request["snapshot"]
                if field == "candidate":
                    request["candidate_body"] += " changed"
                elif field == "actor":
                    snapshot["actor"]["id"] = "U_other"
                elif field == "source":
                    snapshot["comments"][0]["author"]["id"] = "U_other"
                elif field == "issue":
                    snapshot["issue"]["body"] += " changed"
                else:
                    snapshot["comments"][-1]["author"]["is_authority"] = False
                with self.assertRaises(self.adapter.ProtocolError):
                    self.adapter.verify_finalize(request)

    def test_readback_revalidates_authority_after_body_update(self) -> None:
        request = self.authorized_request()
        prepared = self.adapter.verify_finalize(request)
        snapshot = request["snapshot"]
        snapshot["issue"]["body"] = prepared["operation"]["body"]
        snapshot["comments"][-1]["author"]["is_authority"] = False
        result = self.adapter.verify_finalize(
            {"snapshot": snapshot, "prepared": prepared}
        )
        self.assertEqual("unknown_outcome", result["status"])
        self.assertEqual([], result["deletion_allowlist"])


if __name__ == "__main__":
    unittest.main()
