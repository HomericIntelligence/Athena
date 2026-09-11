"""Behavior tests for the issue review-exchange adapter."""

from __future__ import annotations

import copy
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Callable
from contextlib import redirect_stderr
from pathlib import Path
from types import ModuleType
from typing import Any, cast
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills/review-exchange/scripts/issue_exchange.py"
HEX_A = "a" * 64


def load_module() -> ModuleType:
    """Load the executable helper as a test module."""
    name = f"test_issue_review_exchange_{id(SCRIPT)}"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("The issue-exchange helper cannot be loaded.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class IssueReviewExchangeTests(unittest.TestCase):
    adapter: ModuleType

    @classmethod
    def setUpClass(cls) -> None:
        cls.adapter = load_module()

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema_id": "athena.issue-exchange.snapshot",
            "schema_version": 1,
            "target": {
                "provider": "github",
                "host": "github.com",
                "repository": "owner/repository",
                "issue_id": "I_kwDO7",
                "number": 210,
                "url": "https://github.com/owner/repository/issues/210",
            },
            "actor": {"id": "U_athena", "login": "reviewer"},
            "issue": {
                "state": "open",
                "title": "Bound the review exchange",
                "body": "Implement a bounded protocol.",
                "acceptance_criteria": [
                    {
                        "id": "AC-001",
                        "text": "Stop after five reviewer assessments.",
                        "source": "body",
                    }
                ],
            },
            "comments": [],
            "comments_complete": True,
        }

    def author(self) -> dict[str, str]:
        return {"id": "U_athena", "login": "reviewer"}

    def comment(self, comment_id: str, body: str) -> dict[str, Any]:
        return {
            "id": comment_id,
            "url": f"https://github.com/owner/repository/issues/210#issuecomment-{comment_id}",
            "author": {**self.author(), "is_authority": False},
            "body": body,
        }

    def target_scope(self) -> list[dict[str, str]]:
        return [
            {"kind": "path", "value": "skills/review-exchange"},
            {"kind": "workflow", "value": "issue planning"},
        ]

    def human_decisions(self) -> list[dict[str, Any]]:
        return [
            {
                "finding_id": "F-001",
                "kind": "accept_risk",
                "closure_condition": None,
            }
        ]

    def authority_body(
        self,
        snapshot: dict[str, Any],
        *,
        action: str,
        exchange_id: str,
        prior_state_sha256: str | None,
        supersedes_state_sha256: str | None,
        decisions: list[dict[str, Any]],
    ) -> str:
        normalized = self.adapter._snapshot(snapshot)
        return cast(
            str,
            self.adapter.review_exchange.canonical_json(
                {
                    "schema_id": "athena.review-exchange.authority",
                    "schema_version": 1,
                    "action": action,
                    "target": self.adapter._core_target(normalized),
                    "exchange_id": exchange_id,
                    "requirements_sha256": self.adapter._requirements_sha256(
                        normalized
                    ),
                    "prior_state_sha256": prior_state_sha256,
                    "supersedes_state_sha256": supersedes_state_sha256,
                    "decisions": decisions,
                }
            ),
        )

    def human_authority(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        inspected = self.adapter.inspect_snapshot(snapshot)
        assert inspected["envelope"] is not None
        authority = self.comment(
            "authority-1",
            self.authority_body(
                snapshot,
                action="human_decision",
                exchange_id=inspected["state"]["exchange_id"],
                prior_state_sha256=inspected["state_sha256"],
                supersedes_state_sha256=None,
                decisions=self.human_decisions(),
            ),
        )
        authority["author"]["is_authority"] = True
        return authority

    def reframe_authority(
        self, snapshot: dict[str, Any], previous: dict[str, Any]
    ) -> dict[str, Any]:
        authority = self.comment(
            "authority-1",
            self.authority_body(
                snapshot,
                action="reframe",
                exchange_id=self.adapter._reframe_exchange_id(
                    self.adapter._snapshot(snapshot), previous["state_sha256"]
                ),
                prior_state_sha256=None,
                supersedes_state_sha256=previous["state_sha256"],
                decisions=[],
            ),
        )
        authority["author"]["is_authority"] = True
        return authority

    def finding(self) -> dict[str, Any]:
        return {
            "id": "F-001",
            "severity": "major",
            "disposition": "required",
            "material_architecture": False,
            "category": None,
            "location": "skills/issue-review/SKILL.md",
            "impact": "The review can repeat without a terminal decision.",
            "evidence": ["The workflow has no reviewer-round limit."],
            "closure_condition": "The workflow stops after five assessments.",
            "introduction": "initial",
        }

    def plan_request(
        self,
        snapshot: dict[str, Any],
        *,
        responses: list[dict[str, Any]] | None = None,
        content: str = "## Plan\n\nAdd the bounded exchange.",
        scope_change_reason: str | None = None,
    ) -> dict[str, Any]:
        return {
            "snapshot": snapshot,
            "content": content,
            "event": {
                "scope": self.target_scope(),
                "scope_change_reason": scope_change_reason,
                "responses": responses or [],
            },
        }

    def review_request(
        self,
        snapshot: dict[str, Any],
        *,
        responses: list[dict[str, Any]] | None = None,
        findings: list[dict[str, Any]] | None = None,
        coverage_complete: bool = True,
        legacy_import: bool = False,
        content: str = "## Review\n\nArchitecture is aligned.",
        stop_reason: str | None = None,
    ) -> dict[str, Any]:
        return {
            "snapshot": snapshot,
            "content": content,
            "event": {
                "event_type": "reviewer_assessment",
                "coverage_complete": coverage_complete,
                "responses": responses or [],
                "new_findings": findings or [],
                "stop_reason": stop_reason,
                "legacy_import": legacy_import,
                "scope": self.target_scope(),
            },
        }

    def human_review_request(
        self,
        snapshot: dict[str, Any],
        *,
        content: str = "## Review\n\nArchitecture is aligned.",
    ) -> dict[str, Any]:
        authority = next(
            comment
            for comment in snapshot["comments"]
            if comment["id"] == "authority-1"
        )
        return {
            "snapshot": snapshot,
            "content": content,
            "event": {
                "event_type": "human_decision",
                "authority_receipt": {
                    "reference": authority["url"],
                    "sha256": self.adapter.review_exchange.sha256_text(
                        authority["body"]
                    ),
                },
                "decisions": self.human_decisions(),
            },
        }

    def reframe_plan_request(
        self, snapshot: dict[str, Any], previous: dict[str, Any]
    ) -> dict[str, Any]:
        authority = next(
            comment
            for comment in snapshot["comments"]
            if comment["id"] == "authority-1"
        )
        return {
            "snapshot": snapshot,
            "content": "## Reframed plan\n\nImplement the changed requirements.",
            "event": {
                "event_type": "reframe",
                "previous": previous,
                "authority_receipt": {
                    "reference": authority["url"],
                    "sha256": self.adapter.review_exchange.sha256_text(
                        authority["body"]
                    ),
                },
                "scope": self.target_scope(),
            },
        }

    def reframe_review_request(
        self, snapshot: dict[str, Any], previous: dict[str, Any]
    ) -> dict[str, Any]:
        authority = next(
            comment
            for comment in snapshot["comments"]
            if comment["id"] == "authority-1"
        )
        return {
            "snapshot": snapshot,
            "content": "## Reframed review\n\nThe changed requirements are reviewable.",
            "event": {
                "event_type": "reframe",
                "previous": previous,
                "authority_receipt": {
                    "reference": authority["url"],
                    "sha256": self.adapter.review_exchange.sha256_text(
                        authority["body"]
                    ),
                },
                "coverage_complete": True,
                "responses": [],
                "new_findings": [],
                "stop_reason": None,
                "legacy_import": False,
                "scope": self.target_scope(),
            },
        }

    def apply_operation(
        self, snapshot: dict[str, Any], prepared: dict[str, Any], comment_id: str
    ) -> dict[str, Any]:
        result = copy.deepcopy(snapshot)
        operation = prepared["operation"]
        assert operation is not None
        if operation["action"] == "create":
            result["comments"].append(self.comment(comment_id, operation["body"]))
        else:
            for comment in result["comments"]:
                if comment["id"] == operation["comment_id"]:
                    comment["body"] = operation["body"]
                    break
            else:
                self.fail("The update target is absent from the fixture.")
        return result

    def initial_plan_snapshot(self) -> tuple[dict[str, Any], dict[str, Any]]:
        source = self.snapshot()
        prepared = self.adapter.prepare_plan(self.plan_request(source))
        return self.apply_operation(source, prepared, "plan-1"), prepared

    def no_go_snapshot(self) -> dict[str, Any]:
        with_plan, _ = self.initial_plan_snapshot()
        prepared = self.adapter.prepare_review(
            self.review_request(with_plan, findings=[self.finding()])
        )
        return self.apply_operation(with_plan, prepared, "review-1")

    def go_snapshot(self) -> dict[str, Any]:
        no_go = self.no_go_snapshot()
        response = {
            "finding_id": "F-001",
            "kind": "fix",
            "evidence": ["The five-round guard is in the helper."],
            "tradeoff": None,
        }
        plan = self.adapter.prepare_plan(
            self.plan_request(
                no_go,
                responses=[response],
                content="## Plan\n\nAdd and verify the five-round guard.",
            )
        )
        answered = self.apply_operation(no_go, plan, "unused")
        review_response = {
            "finding_id": "F-001",
            "kind": "resolve",
            "evidence": ["The round-five behavior test passes."],
            "closure_condition": None,
        }
        review = self.adapter.prepare_review(
            self.review_request(answered, responses=[review_response])
        )
        return self.apply_operation(answered, review, "unused")

    def test_inspect_new_issue_returns_bound_plan_action(self) -> None:
        result = self.adapter.inspect_snapshot(self.snapshot())

        self.assertEqual("ready", result["status"])
        self.assertEqual("prepare_plan", result["next_action"])
        self.assertEqual(HEX_A.__len__(), len(result["requirements_sha256"]))
        self.assertIsNone(result["envelope"])

    def test_prepare_plan_creates_one_carried_author_artifact(self) -> None:
        prepared = self.adapter.prepare_plan(self.plan_request(self.snapshot()))

        self.assertEqual("ready", prepared["status"])
        self.assertEqual("create", prepared["operation"]["action"])
        self.assertEqual("plan", prepared["operation"]["artifact"])
        self.assertIn(
            "<!-- HomericIntelligence:plan-issue -->", prepared["operation"]["body"]
        )
        envelope = self.adapter.review_exchange.extract_carrier(
            prepared["operation"]["body"]
        )
        self.assertEqual("athena.review-exchange.author-event", envelope["schema_id"])
        self.assertEqual([], envelope["state"]["responses"])
        self.assertEqual("prepare_review", prepared["next_action"])

    def test_plan_only_carrier_requires_a_canonical_revision_identity(self) -> None:
        with_plan, _ = self.initial_plan_snapshot()
        plan = with_plan["comments"][0]
        envelope = self.adapter.review_exchange.extract_carrier(plan["body"])
        changed = copy.deepcopy(envelope["state"])
        changed["artifact_binding"]["revision"] = "unrelated-comment"
        visible = plan["body"].split(
            "\n\n<!-- HomericIntelligence:review-exchange:", 1
        )[0]
        plan["body"] = self.adapter.review_exchange.render_carrier(
            visible,
            self.adapter.review_exchange.make_envelope(
                changed, self.adapter.review_exchange.AUTHOR_EVENT_SCHEMA_ID
            ),
            "author-event",
        )

        inspected = self.adapter.inspect_snapshot(with_plan)
        prepared = self.adapter.prepare_review(self.review_request(with_plan))

        self.assertEqual("withheld", inspected["status"])
        self.assertEqual("plan_identity_drift", inspected["diagnostics"][0]["code"])
        self.assertEqual("withheld", prepared["status"])
        self.assertIsNone(prepared["operation"])

    def test_plan_only_requirements_change_starts_a_fresh_initial_plan(self) -> None:
        with_plan, _ = self.initial_plan_snapshot()
        old_envelope = self.adapter.review_exchange.extract_carrier(
            with_plan["comments"][0]["body"]
        )
        with_plan["issue"]["body"] = "Implement the changed bounded protocol."

        inspected = self.adapter.inspect_snapshot(with_plan)
        prepared = self.adapter.prepare_plan(self.plan_request(with_plan))
        published = self.apply_operation(with_plan, prepared, "unused")
        new_envelope = self.adapter.review_exchange.extract_carrier(
            published["comments"][0]["body"]
        )
        publication = self.adapter.verify_publication(
            {"prepared": prepared, "snapshot": published}
        )
        ready_for_review = self.adapter.inspect_snapshot(published)

        self.assertEqual("ready", inspected["status"])
        self.assertEqual("prepare_plan", inspected["next_action"])
        self.assertIsNone(inspected["envelope"])
        self.assertEqual("update", prepared["operation"]["action"])
        self.assertIsNone(new_envelope["state"]["prior_state_sha256"])
        self.assertNotEqual(
            old_envelope["state"]["exchange_id"],
            new_envelope["state"]["exchange_id"],
        )
        self.assertEqual(
            inspected["requirements_sha256"],
            new_envelope["state"]["requirements_sha256"],
        )
        self.assertEqual("verified", publication["status"])
        self.assertEqual("ready", ready_for_review["status"])
        self.assertEqual("prepare_review", ready_for_review["next_action"])

    def test_publication_verifies_exact_create_and_rejects_drift(self) -> None:
        source = self.snapshot()
        prepared = self.adapter.prepare_plan(self.plan_request(source))
        published = self.apply_operation(source, prepared, "plan-1")

        verified = self.adapter.verify_publication(
            {"prepared": prepared, "snapshot": published}
        )
        self.assertEqual("verified", verified["status"])
        self.assertEqual("plan-1", verified["receipt"]["comment_id"])

        drifted = copy.deepcopy(published)
        drifted["issue"]["title"] = "Changed requirements"
        unknown = self.adapter.verify_publication(
            {"prepared": prepared, "snapshot": drifted}
        )
        self.assertEqual("unknown_outcome", unknown["status"])
        self.assertIsNone(unknown["receipt"])

        mismatched = copy.deepcopy(published)
        mismatched["comments"][0]["body"] += "changed"
        unknown = self.adapter.verify_publication(
            {"prepared": prepared, "snapshot": mismatched}
        )
        self.assertEqual("unknown_outcome", unknown["status"])

    def test_publication_readback_rejects_duplicate_or_foreign_role_marker(
        self,
    ) -> None:
        source = self.snapshot()
        prepared = self.adapter.prepare_plan(self.plan_request(source))
        published = self.apply_operation(source, prepared, "plan-1")

        for author, body in (
            (
                {**self.author(), "is_authority": False},
                "<!-- HomericIntelligence:plan-issue -->\n\nDuplicate.",
            ),
            (
                {"id": "U_foreign", "login": "foreign", "is_authority": False},
                "<!-- HomericIntelligence:plan-issue -->\n\nForeign.",
            ),
        ):
            with self.subTest(author=author):
                conflicted = copy.deepcopy(published)
                conflict = self.comment("plan-conflict", body)
                conflict["author"] = author
                conflicted["comments"].append(conflict)

                result = self.adapter.verify_publication(
                    {"prepared": prepared, "snapshot": conflicted}
                )

                self.assertEqual("unknown_outcome", result["status"])
                self.assertEqual(
                    "publication_identity_conflict", result["diagnostics"][0]["code"]
                )

    def test_publication_rejects_a_tampered_prepared_record(self) -> None:
        source = self.snapshot()
        prepared = self.adapter.prepare_plan(self.plan_request(source))
        published = self.apply_operation(source, prepared, "plan-1")

        cases: list[dict[str, Any]] = []
        changed_body = copy.deepcopy(prepared)
        changed_body["operation"]["body"] += "changed"
        cases.append(changed_body)
        changed_hash = copy.deepcopy(prepared)
        changed_hash["operation"]["operation_sha256"] = "f" * 64
        cases.append(changed_hash)
        changed_precondition = copy.deepcopy(prepared)
        changed_precondition["precondition_sha256"] = "f" * 64
        cases.append(changed_precondition)
        changed_action = copy.deepcopy(prepared)
        changed_action["operation"]["action"] = "delete"
        cases.append(changed_action)
        changed_identity = copy.deepcopy(prepared)
        changed_identity["operation"]["comment_id"] = "unexpected"
        cases.append(changed_identity)
        changed_body_digest = copy.deepcopy(prepared)
        changed_body_digest["operation"]["body_sha256"] = "f" * 64
        cases.append(changed_body_digest)
        changed_next_action = copy.deepcopy(prepared)
        changed_next_action["next_action"] = "finalize"
        cases.append(changed_next_action)
        changed_version = copy.deepcopy(prepared)
        changed_version["schema_version"] = True
        cases.append(changed_version)
        changed_status = copy.deepcopy(prepared)
        changed_status["status"] = "withheld"
        cases.append(changed_status)
        changed_diagnostics = copy.deepcopy(prepared)
        changed_diagnostics["diagnostics"] = [
            {"code": "tampered", "message": "Not a ready record."}
        ]
        cases.append(changed_diagnostics)
        changed_provider = copy.deepcopy(prepared)
        changed_provider["target"]["provider"] = "unknown"
        cases.append(changed_provider)
        changed_authority = copy.deepcopy(prepared)
        changed_authority["authority_receipt"] = {
            "reference": "authority-1",
            "sha256": "e" * 64,
        }
        changed_authority["precondition_sha256"] = self.adapter._precondition_sha256(
            target=changed_authority["target"],
            actor_id=changed_authority["actor_id"],
            requirements_sha256=changed_authority["requirements_sha256"],
            plan=None,
            review=None,
            authority_receipt=changed_authority["authority_receipt"],
        )
        cases.append(changed_authority)
        malformed_authority = copy.deepcopy(prepared)
        malformed_authority["authority_receipt"] = {"reference": "authority-1"}
        cases.append(malformed_authority)
        unknown_field = copy.deepcopy(prepared)
        unknown_field["unknown"] = True
        cases.append(unknown_field)

        for candidate in cases:
            with (
                self.subTest(candidate=candidate),
                self.assertRaises(self.adapter.ProtocolError),
            ):
                self.adapter.verify_publication(
                    {"prepared": candidate, "snapshot": published}
                )

    def test_initial_plan_publication_rejects_an_illegal_author_event(self) -> None:
        source = self.snapshot()
        prepared = self.adapter.prepare_plan(self.plan_request(source))
        forged = copy.deepcopy(prepared)
        operation = forged["operation"]
        assert operation is not None
        envelope = self.adapter.review_exchange.extract_carrier(operation["body"])
        envelope["state"]["responses"] = [
            {
                "finding_id": "F-001",
                "kind": "contest",
                "evidence": ["No prior finding exists."],
                "tradeoff": None,
            }
        ]
        envelope = self.adapter.review_exchange.make_envelope(
            envelope["state"], self.adapter.review_exchange.AUTHOR_EVENT_SCHEMA_ID
        )
        visible = self.adapter._visible(
            self.adapter.PLAN_MARKER, "## Plan\n\nAdd the bounded exchange."
        )
        operation["body"] = self.adapter.review_exchange.render_carrier(
            visible, envelope, "author-event"
        )
        operation["body_sha256"] = self.adapter._body_sha256(operation["body"])
        operation["operation_sha256"] = self.adapter.review_exchange.sha256_json(
            {
                key: value
                for key, value in operation.items()
                if key != "operation_sha256"
            }
        )
        published = self.apply_operation(source, forged, "plan-1")

        with self.assertRaises(self.adapter.ProtocolError):
            self.adapter.verify_publication({"prepared": forged, "snapshot": published})

    def test_absent_plan_withholds_review(self) -> None:
        result = self.adapter.prepare_review(
            self.review_request(self.snapshot(), findings=[])
        )

        self.assertEqual("withheld", result["status"])
        self.assertIsNone(result["operation"])
        self.assertEqual("plan_absent", result["diagnostics"][0]["code"])

    def test_first_review_creates_canonical_state_and_no_go(self) -> None:
        with_plan, _ = self.initial_plan_snapshot()
        prepared = self.adapter.prepare_review(
            self.review_request(with_plan, findings=[self.finding()])
        )

        self.assertEqual("create", prepared["operation"]["action"])
        self.assertEqual("NO-GO", prepared["state"]["verdict"])
        self.assertTrue(prepared["state"]["go_eligible"])
        self.assertEqual(1, prepared["state"]["round"])
        self.assertEqual("F-001", prepared["state"]["findings"][0]["id"])
        self.assertIn(
            "<!-- HomericIntelligence:issue-review -->",
            prepared["operation"]["body"],
        )

        supplied_eligibility = self.review_request(with_plan)
        supplied_eligibility["event"]["go_eligible"] = False
        with self.assertRaises(self.adapter.ProtocolError):
            self.adapter.prepare_review(supplied_eligibility)

    def test_round_one_go_binds_the_initial_plan_author_event(self) -> None:
        with_plan, _ = self.initial_plan_snapshot()
        prepared = self.adapter.prepare_review(self.review_request(with_plan))
        terminal = self.apply_operation(with_plan, prepared, "review-1")

        inspected = self.adapter.inspect_snapshot(terminal)
        finalized = self.adapter.verify_finalize(
            {"snapshot": terminal, "candidate_body": "# Final plan"}
        )

        self.assertEqual("ready", inspected["status"])
        self.assertEqual("finalize", inspected["next_action"])
        self.assertEqual("ready", finalized["status"])

    def test_plan_revision_answers_all_findings_and_updates_same_comment(self) -> None:
        snapshot = self.no_go_snapshot()
        response = {
            "finding_id": "F-001",
            "kind": "fix_with_tradeoff",
            "evidence": ["The helper now stops at the bound."],
            "tradeoff": "A human must decide unresolved round-five findings.",
        }
        prepared = self.adapter.prepare_plan(
            self.plan_request(
                snapshot,
                responses=[response],
                content="## Plan\n\nAdd the bounded exchange and its round-five guard.",
            )
        )

        self.assertEqual("update", prepared["operation"]["action"])
        self.assertEqual("plan-1", prepared["operation"]["comment_id"])
        self.assertEqual("answered_tradeoff", prepared["state"]["findings"][0]["state"])
        self.assertEqual(1, prepared["state"]["round"])
        envelope = self.adapter.review_exchange.extract_carrier(
            prepared["operation"]["body"]
        )
        self.assertEqual(
            "author-event", self.adapter.review_exchange._carrier_kind(envelope)
        )

    def test_changed_plan_reanswers_terminal_sibling_with_stable_id(self) -> None:
        with_plan, _ = self.initial_plan_snapshot()
        second = self.finding()
        second["id"] = "F-002"
        second["location"] = "skills/plan-issue/SKILL.md"
        second["impact"] = "The plan can omit a required migration boundary."
        second["evidence"] = ["The migration boundary is absent from the plan."]
        second["closure_condition"] = "The plan includes the migration boundary."
        initial_review = self.adapter.prepare_review(
            self.review_request(with_plan, findings=[self.finding(), second])
        )
        no_go = self.apply_operation(with_plan, initial_review, "review-1")
        first_answers = [
            {
                "finding_id": finding_id,
                "kind": "fix",
                "evidence": [f"The plan answers {finding_id}."],
                "tradeoff": None,
            }
            for finding_id in ("F-001", "F-002")
        ]
        first_plan = self.adapter.prepare_plan(
            self.plan_request(
                no_go,
                responses=first_answers,
                content="## Plan\n\nAdd the round guard and migration boundary.",
            )
        )
        answered = self.apply_operation(no_go, first_plan, "unused")
        assessment = self.adapter.prepare_review(
            self.review_request(
                answered,
                responses=[
                    {
                        "finding_id": "F-001",
                        "kind": "resolve",
                        "evidence": ["The plan includes the round guard."],
                        "closure_condition": None,
                    },
                    {
                        "finding_id": "F-002",
                        "kind": "still_present",
                        "evidence": ["The rollback side of the boundary is absent."],
                        "closure_condition": None,
                    },
                ],
            )
        )
        partial = self.apply_operation(answered, assessment, "unused")
        active_answer = {
            "finding_id": "F-002",
            "kind": "fix",
            "evidence": ["The changed plan adds the rollback boundary."],
            "tradeoff": None,
        }

        with self.assertRaises(self.adapter.ProtocolError):
            self.adapter.prepare_plan(
                self.plan_request(
                    partial,
                    responses=[active_answer],
                    content="## Plan\n\nAdd both migration and rollback boundaries.",
                )
            )

        prepared = self.adapter.prepare_plan(
            self.plan_request(
                partial,
                responses=[
                    {
                        "finding_id": "F-001",
                        "kind": "fix",
                        "evidence": ["The changed plan keeps the round guard."],
                        "tradeoff": None,
                    },
                    active_answer,
                ],
                content="## Plan\n\nAdd both migration and rollback boundaries.",
            )
        )

        self.assertEqual("update", prepared["operation"]["action"])
        self.assertEqual("plan-1", prepared["operation"]["comment_id"])
        self.assertEqual(
            ["F-001", "F-002"],
            [finding["id"] for finding in prepared["state"]["findings"]],
        )
        self.assertEqual(
            ["answered_fix", "answered_fix"],
            [finding["state"] for finding in prepared["state"]["findings"]],
        )

    def test_plan_stops_while_reviewer_or_terminal_action_is_due(self) -> None:
        no_go = self.no_go_snapshot()
        response = {
            "finding_id": "F-001",
            "kind": "fix",
            "evidence": ["The bounded branch is implemented."],
            "tradeoff": None,
        }
        first = self.adapter.prepare_plan(
            self.plan_request(
                no_go,
                responses=[response],
                content="## Plan\n\nAdd the bounded branch to the exchange.",
            )
        )
        awaiting_review = self.apply_operation(no_go, first, "unused")

        second = self.adapter.prepare_plan(self.plan_request(awaiting_review))

        self.assertEqual("withheld", second["status"])
        self.assertIsNone(second["operation"])
        self.assertEqual("review_assessment", second["next_action"])

        terminal = self.go_snapshot()
        stopped = self.adapter.prepare_plan(self.plan_request(terminal))
        self.assertEqual("withheld", stopped["status"])
        self.assertEqual("finalize", stopped["next_action"])

    def test_continuation_updates_one_review_comment_and_reaches_go(self) -> None:
        snapshot = self.go_snapshot()
        inspected = self.adapter.inspect_snapshot(snapshot)

        self.assertEqual("ready", inspected["status"])
        self.assertEqual("finalize", inspected["next_action"])
        self.assertEqual("GO", inspected["state"]["verdict"])
        self.assertEqual(2, inspected["state"]["round"])
        reviews = [
            comment
            for comment in snapshot["comments"]
            if "<!-- HomericIntelligence:issue-review -->" in comment["body"]
        ]
        self.assertEqual(["review-1"], [comment["id"] for comment in reviews])

    def test_human_decision_updates_the_review_without_adding_a_round(self) -> None:
        no_go = self.no_go_snapshot()
        risk_request = {
            "finding_id": "F-001",
            "kind": "risk_acceptance",
            "evidence": ["The compatibility risk cannot be removed in this release."],
            "tradeoff": "The repository authority accepts the bounded compatibility risk.",
        }
        plan = self.adapter.prepare_plan(
            self.plan_request(no_go, responses=[risk_request])
        )
        answered = self.apply_operation(no_go, plan, "unused")
        answered["comments"].append(self.human_authority(answered))

        decision = self.adapter.prepare_review(self.human_review_request(answered))

        self.assertEqual("ready", decision["status"])
        self.assertEqual("update", decision["operation"]["action"])
        self.assertEqual("review-1", decision["operation"]["comment_id"])
        self.assertEqual(1, decision["state"]["round"])
        self.assertEqual("accepted_risk", decision["state"]["findings"][0]["state"])
        self.assertEqual("GO", decision["state"]["verdict"])

        published = self.apply_operation(answered, decision, "unused")
        published["comments"] = [
            comment
            for comment in published["comments"]
            if comment["id"] != "authority-1"
        ]
        unknown = self.adapter.verify_publication(
            {"prepared": decision, "snapshot": published}
        )
        self.assertEqual("unknown_outcome", unknown["status"])
        self.assertEqual(
            "publication_authority_drift", unknown["diagnostics"][0]["code"]
        )

    def test_human_decision_requires_one_exact_live_authority_receipt(self) -> None:
        no_go = self.no_go_snapshot()
        risk_request = {
            "finding_id": "F-001",
            "kind": "risk_acceptance",
            "evidence": ["The compatibility risk cannot be removed."],
            "tradeoff": "The repository authority must accept the risk.",
        }
        plan = self.adapter.prepare_plan(
            self.plan_request(no_go, responses=[risk_request])
        )
        answered = self.apply_operation(no_go, plan, "unused")
        authority = self.human_authority(answered)
        answered["comments"].append(authority)

        missing = copy.deepcopy(answered)
        missing["comments"].pop()
        missing_request = self.human_review_request(answered)
        missing_request["snapshot"] = missing
        unauthorized = copy.deepcopy(answered)
        unauthorized["comments"][-1]["author"]["is_authority"] = False
        mismatched = self.human_review_request(answered)
        mismatched["event"]["authority_receipt"]["sha256"] = "d" * 64

        with self.assertRaises(self.adapter.ProtocolError):
            self.adapter.prepare_review(missing_request)
        unauthorized_request = self.human_review_request(answered)
        unauthorized_request["snapshot"] = unauthorized
        with self.assertRaises(self.adapter.ProtocolError):
            self.adapter.prepare_review(unauthorized_request)
        with self.assertRaises(self.adapter.ProtocolError):
            self.adapter.prepare_review(mismatched)

    def test_human_decision_rejects_authority_for_a_different_action_context(
        self,
    ) -> None:
        no_go = self.no_go_snapshot()
        risk_request = {
            "finding_id": "F-001",
            "kind": "risk_acceptance",
            "evidence": ["The compatibility risk cannot be removed."],
            "tradeoff": "The repository authority must accept the risk.",
        }
        plan = self.adapter.prepare_plan(
            self.plan_request(no_go, responses=[risk_request])
        )
        answered = self.apply_operation(no_go, plan, "unused")
        correct = self.human_authority(answered)
        record = json.loads(correct["body"])
        cases: list[tuple[str, str]] = [
            ("unrelated prose", "I approve something else.")
        ]
        for label, field, value in (
            ("target", "target", {**record["target"], "repository": "other/repo"}),
            ("exchange", "exchange_id", "issue-other-exchange"),
            ("prior state", "prior_state_sha256", "e" * 64),
            (
                "finding",
                "decisions",
                [
                    {
                        **record["decisions"][0],
                        "finding_id": "F-002",
                    }
                ],
            ),
            (
                "decision",
                "decisions",
                [
                    {
                        **record["decisions"][0],
                        "kind": "select_closure",
                        "closure_condition": "Use a different closure.",
                    }
                ],
            ),
        ):
            changed = copy.deepcopy(record)
            changed[field] = value
            cases.append((label, self.adapter.review_exchange.canonical_json(changed)))

        for label, body in cases:
            with self.subTest(label=label):
                snapshot = copy.deepcopy(answered)
                authority = self.comment("authority-1", body)
                authority["author"]["is_authority"] = True
                snapshot["comments"].append(authority)

                with self.assertRaises(self.adapter.ProtocolError):
                    self.adapter.prepare_review(self.human_review_request(snapshot))

    def test_state_readers_reject_a_drifted_authority_record(self) -> None:
        no_go = self.no_go_snapshot()
        risk_request = {
            "finding_id": "F-001",
            "kind": "risk_acceptance",
            "evidence": ["The compatibility risk cannot be removed."],
            "tradeoff": "The repository authority must accept the risk.",
        }
        plan = self.adapter.prepare_plan(
            self.plan_request(no_go, responses=[risk_request])
        )
        answered = self.apply_operation(no_go, plan, "unused")
        authority = self.human_authority(answered)
        answered["comments"].append(authority)
        prepared = self.adapter.prepare_review(self.human_review_request(answered))

        wrong_record = json.loads(authority["body"])
        wrong_record["target"]["repository"] = "other/repository"
        wrong_body = self.adapter.review_exchange.canonical_json(wrong_record)
        authority["body"] = wrong_body
        published = self.apply_operation(answered, prepared, "unused")

        publication = self.adapter.verify_publication(
            {"prepared": prepared, "snapshot": published}
        )
        inspected = self.adapter.inspect_snapshot(published)
        finalized = self.adapter.verify_finalize(
            {"snapshot": published, "candidate_body": "# Final plan"}
        )

        self.assertEqual("unknown_outcome", publication["status"])
        self.assertEqual(
            "publication_authority_drift", publication["diagnostics"][0]["code"]
        )
        self.assertEqual("withheld", inspected["status"])
        self.assertEqual(
            "authority_receipt_invalid", inspected["diagnostics"][0]["code"]
        )
        self.assertEqual("withheld", finalized["status"])

    def test_inspection_rejects_a_missing_terminal_authority_receipt(self) -> None:
        no_go = self.no_go_snapshot()
        risk_request = {
            "finding_id": "F-001",
            "kind": "risk_acceptance",
            "evidence": ["The compatibility risk cannot be removed."],
            "tradeoff": "The repository authority must accept the risk.",
        }
        plan = self.adapter.prepare_plan(
            self.plan_request(no_go, responses=[risk_request])
        )
        answered = self.apply_operation(no_go, plan, "unused")
        authority = self.human_authority(answered)
        answered["comments"].append(authority)
        decision = self.adapter.prepare_review(self.human_review_request(answered))
        terminal = self.apply_operation(answered, decision, "unused")
        terminal["comments"] = [
            comment
            for comment in terminal["comments"]
            if comment["id"] != "authority-1"
        ]

        inspected = self.adapter.inspect_snapshot(terminal)

        self.assertEqual("withheld", inspected["status"])
        self.assertEqual(
            "authority_receipt_invalid", inspected["diagnostics"][0]["code"]
        )

    def test_reframe_updates_both_canonical_comments_and_starts_new_exchange(
        self,
    ) -> None:
        with_plan, _ = self.initial_plan_snapshot()
        stopped = self.adapter.prepare_review(
            self.review_request(
                with_plan,
                findings=[self.finding()],
                stop_reason="requirements_reframe",
            )
        )
        old_snapshot = self.apply_operation(with_plan, stopped, "review-1")
        previous = self.adapter.review_exchange.extract_carrier(
            old_snapshot["comments"][1]["body"]
        )
        changed = copy.deepcopy(old_snapshot)
        changed["issue"]["body"] = "Implement the reframed bounded protocol."
        authority = self.reframe_authority(changed, previous)
        changed["comments"].append(authority)

        prepared_plan = self.adapter.prepare_plan(
            self.reframe_plan_request(changed, previous)
        )
        self.assertEqual("update", prepared_plan["operation"]["action"])
        self.assertEqual("plan-1", prepared_plan["operation"]["comment_id"])
        self.assertEqual("prepare_review", prepared_plan["next_action"])
        new_plan = self.adapter.review_exchange.extract_carrier(
            prepared_plan["operation"]["body"]
        )
        self.assertEqual(
            previous["state_sha256"], new_plan["state"]["prior_state_sha256"]
        )
        self.assertNotEqual(
            previous["state"]["exchange_id"], new_plan["state"]["exchange_id"]
        )

        replanned = self.apply_operation(changed, prepared_plan, "unused")
        pending = self.adapter.inspect_snapshot(replanned)
        self.assertEqual("ready", pending["status"])
        self.assertEqual("prepare_review", pending["next_action"])
        self.assertEqual(previous, pending["envelope"])
        prepared_review = self.adapter.prepare_review(
            self.reframe_review_request(replanned, previous)
        )
        self.assertEqual("update", prepared_review["operation"]["action"])
        self.assertEqual("review-1", prepared_review["operation"]["comment_id"])
        self.assertEqual(1, prepared_review["state"]["round"])
        self.assertEqual(
            previous["state_sha256"],
            prepared_review["state"]["supersedes_state_sha256"],
        )
        self.assertEqual(
            {
                "reference": authority["url"],
                "sha256": self.adapter.review_exchange.sha256_text(authority["body"]),
            },
            prepared_review["state"]["supersession_authority_receipt"],
        )
        self.assertEqual(
            new_plan["state"]["exchange_id"],
            prepared_review["state"]["exchange_id"],
        )
        self.assertEqual(
            prepared_plan["requirements_sha256"],
            prepared_review["state"]["requirements_sha256"],
        )

        reframed = self.apply_operation(replanned, prepared_review, "unused")
        inspected = self.adapter.inspect_snapshot(reframed)
        self.assertEqual("ready", inspected["status"])
        self.assertEqual("finalize", inspected["next_action"])
        self.assertEqual("plan-1", prepared_plan["operation"]["comment_id"])
        self.assertEqual("review-1", prepared_review["operation"]["comment_id"])

        missing_authority = copy.deepcopy(reframed)
        missing_authority["comments"] = [
            comment
            for comment in missing_authority["comments"]
            if comment["id"] != "authority-1"
        ]
        withheld = self.adapter.inspect_snapshot(missing_authority)
        self.assertEqual("withheld", withheld["status"])
        self.assertEqual(
            "authority_receipt_invalid", withheld["diagnostics"][0]["code"]
        )

    def test_changed_requirements_can_reframe_a_complete_active_exchange(
        self,
    ) -> None:
        old_snapshot = self.go_snapshot()
        previous = self.adapter.review_exchange.extract_carrier(
            old_snapshot["comments"][1]["body"]
        )
        self.assertEqual("complete", previous["state"]["phase"])
        changed = copy.deepcopy(old_snapshot)
        changed["issue"]["body"] = "Implement the next bounded protocol requirements."
        changed["comments"].append(self.reframe_authority(changed, previous))

        prepared_plan = self.adapter.prepare_plan(
            self.reframe_plan_request(changed, previous)
        )
        replanned = self.apply_operation(changed, prepared_plan, "unused")
        pending = self.adapter.inspect_snapshot(replanned)
        prepared_review = self.adapter.prepare_review(
            self.reframe_review_request(replanned, previous)
        )
        reframed = self.apply_operation(replanned, prepared_review, "unused")
        inspected = self.adapter.inspect_snapshot(reframed)

        self.assertEqual("ready", pending["status"])
        self.assertEqual("prepare_review", pending["next_action"])
        self.assertEqual(previous, pending["envelope"])
        self.assertEqual("review-1", prepared_review["operation"]["comment_id"])
        self.assertEqual(1, prepared_review["state"]["round"])
        self.assertEqual(
            previous["state_sha256"],
            prepared_review["state"]["supersedes_state_sha256"],
        )
        self.assertEqual("ready", inspected["status"])
        self.assertEqual("finalize", inspected["next_action"])

    def test_changed_requirements_require_a_checkpoint_before_reframe(
        self,
    ) -> None:
        old_snapshot = self.no_go_snapshot()
        previous = self.adapter.review_exchange.extract_carrier(
            old_snapshot["comments"][1]["body"]
        )
        response = {
            "finding_id": "F-001",
            "kind": "fix",
            "evidence": ["The five-round guard is in the helper."],
            "tradeoff": None,
        }
        prepared_fix = self.adapter.prepare_plan(
            self.plan_request(
                old_snapshot,
                responses=[response],
                content="## Plan\n\nAdd and verify the five-round guard.",
            )
        )
        awaiting_review = self.apply_operation(old_snapshot, prepared_fix, "unused")
        pending = self.adapter.inspect_snapshot(awaiting_review)
        self.assertEqual("ready", pending["status"])
        self.assertEqual("prepare_review", pending["next_action"])

        changed = copy.deepcopy(awaiting_review)
        changed["issue"]["body"] = "Implement the changed bounded protocol."
        changed["comments"].append(self.reframe_authority(changed, previous))

        with self.assertRaisesRegex(
            self.adapter.ProtocolError, "checkpoint.*pending author event"
        ):
            self.adapter.prepare_plan(self.reframe_plan_request(changed, previous))

        checkpoint = self.adapter.prepare_review(
            self.review_request(
                awaiting_review,
                responses=[
                    {
                        "finding_id": "F-001",
                        "kind": "resolve",
                        "evidence": ["The round guard is now verified."],
                        "closure_condition": None,
                    }
                ],
            )
        )
        checkpointed = self.apply_operation(awaiting_review, checkpoint, "unused")
        checkpointed_previous = self.adapter.review_exchange.extract_carrier(
            checkpointed["comments"][1]["body"]
        )
        checkpointed["issue"]["body"] = "Implement the changed bounded protocol."
        checkpointed["comments"].append(
            self.reframe_authority(checkpointed, checkpointed_previous)
        )

        prepared_plan = self.adapter.prepare_plan(
            self.reframe_plan_request(checkpointed, checkpointed_previous)
        )

        self.assertEqual("ready", prepared_plan["status"])
        self.assertEqual("update", prepared_plan["operation"]["action"])

    def test_reframe_rejects_a_pending_author_event_with_a_false_source_digest(
        self,
    ) -> None:
        old_snapshot = self.no_go_snapshot()
        previous = self.adapter.review_exchange.extract_carrier(
            old_snapshot["comments"][1]["body"]
        )
        prepared_fix = self.adapter.prepare_plan(
            self.plan_request(
                old_snapshot,
                responses=[
                    {
                        "finding_id": "F-001",
                        "kind": "fix",
                        "evidence": ["The five-round guard is in the helper."],
                        "tradeoff": None,
                    }
                ],
                content="## Plan\n\nAdd and verify the five-round guard.",
            )
        )
        awaiting_review = self.apply_operation(old_snapshot, prepared_fix, "unused")
        plan = awaiting_review["comments"][0]
        plan_envelope = self.adapter.review_exchange.extract_carrier(plan["body"])
        false_source = copy.deepcopy(plan_envelope["state"])
        false_source["artifact_binding"]["sha256"] = "b" * 64
        visible = plan["body"].split(
            "\n\n<!-- HomericIntelligence:review-exchange:", 1
        )[0]
        plan["body"] = self.adapter.review_exchange.render_carrier(
            visible,
            self.adapter.review_exchange.make_envelope(
                false_source, self.adapter.review_exchange.AUTHOR_EVENT_SCHEMA_ID
            ),
            "author-event",
        )
        awaiting_review["issue"]["body"] = "Implement the changed bounded protocol."
        awaiting_review["comments"].append(
            self.reframe_authority(awaiting_review, previous)
        )

        with self.assertRaises(self.adapter.ProtocolError):
            self.adapter.prepare_plan(
                self.reframe_plan_request(awaiting_review, previous)
            )

    def test_reframe_rejects_a_synchronized_review_with_a_false_plan_digest(
        self,
    ) -> None:
        old_snapshot = self.no_go_snapshot()
        review = old_snapshot["comments"][1]
        review_envelope = self.adapter.review_exchange.extract_carrier(review["body"])
        false_source_event = copy.deepcopy(
            review_envelope["state"]["accepted_events"][0]
        )
        false_source_event["artifact_binding"]["sha256"] = "b" * 64
        false_source = self.adapter.review_exchange.reduce_request(
            {"previous": None, "event": false_source_event}
        )["envelope"]
        visible = review["body"].split(
            "\n\n<!-- HomericIntelligence:review-exchange:", 1
        )[0]
        review["body"] = self.adapter.review_exchange.render_carrier(
            visible,
            false_source,
            "state",
        )
        previous = self.adapter.review_exchange.extract_carrier(review["body"])
        old_snapshot["issue"]["body"] = "Implement the changed bounded protocol."
        old_snapshot["comments"].append(self.reframe_authority(old_snapshot, previous))

        with self.assertRaises(self.adapter.ProtocolError):
            self.adapter.prepare_plan(self.reframe_plan_request(old_snapshot, previous))

    def test_reframe_plan_publication_rechecks_the_live_authority_receipt(
        self,
    ) -> None:
        with_plan, _ = self.initial_plan_snapshot()
        stopped = self.adapter.prepare_review(
            self.review_request(
                with_plan,
                findings=[self.finding()],
                stop_reason="requirements_reframe",
            )
        )
        old_snapshot = self.apply_operation(with_plan, stopped, "review-1")
        previous = self.adapter.review_exchange.extract_carrier(
            old_snapshot["comments"][1]["body"]
        )
        changed = copy.deepcopy(old_snapshot)
        changed["issue"]["body"] = "Implement the reframed bounded protocol."
        authority = self.reframe_authority(changed, previous)
        changed["comments"].append(authority)
        prepared = self.adapter.prepare_plan(
            self.reframe_plan_request(changed, previous)
        )
        published = self.apply_operation(changed, prepared, "unused")
        published["comments"] = [
            comment
            for comment in published["comments"]
            if comment["id"] != "authority-1"
        ]

        unknown = self.adapter.verify_publication(
            {"prepared": prepared, "snapshot": published}
        )
        inspected = self.adapter.inspect_snapshot(published)

        self.assertEqual(
            {
                "reference": authority["url"],
                "sha256": self.adapter.review_exchange.sha256_text(authority["body"]),
            },
            prepared["authority_receipt"],
        )
        self.assertEqual("unknown_outcome", unknown["status"])
        self.assertEqual(
            "publication_authority_drift", unknown["diagnostics"][0]["code"]
        )
        self.assertEqual("withheld", inspected["status"])
        self.assertEqual("pending_reframe_invalid", inspected["diagnostics"][0]["code"])

    def test_reframe_plan_publication_must_supersede_the_live_review(self) -> None:
        with_plan, _ = self.initial_plan_snapshot()
        stopped = self.adapter.prepare_review(
            self.review_request(
                with_plan,
                findings=[self.finding()],
                stop_reason="requirements_reframe",
            )
        )
        old_snapshot = self.apply_operation(with_plan, stopped, "review-1")
        previous = self.adapter.review_exchange.extract_carrier(
            old_snapshot["comments"][1]["body"]
        )
        changed = copy.deepcopy(old_snapshot)
        changed["issue"]["body"] = "Implement the reframed bounded protocol."
        changed["comments"].append(self.reframe_authority(changed, previous))
        prepared = self.adapter.prepare_plan(
            self.reframe_plan_request(changed, previous)
        )

        forged_prior = "e" * 64
        forged_exchange = self.adapter._reframe_exchange_id(
            self.adapter._snapshot(changed), forged_prior
        )
        author_envelope = self.adapter.review_exchange.extract_carrier(
            prepared["operation"]["body"]
        )
        author_state = copy.deepcopy(author_envelope["state"])
        author_state["exchange_id"] = forged_exchange
        author_state["prior_state_sha256"] = forged_prior
        visible = prepared["operation"]["body"].split(
            "\n\n<!-- HomericIntelligence:review-exchange:", 1
        )[0]
        prepared["operation"]["body"] = self.adapter.review_exchange.render_carrier(
            visible,
            self.adapter.review_exchange.make_envelope(
                author_state, self.adapter.review_exchange.AUTHOR_EVENT_SCHEMA_ID
            ),
            "author-event",
        )
        prepared["operation"]["body_sha256"] = self.adapter._body_sha256(
            prepared["operation"]["body"]
        )
        operation_record = {
            key: value
            for key, value in prepared["operation"].items()
            if key != "operation_sha256"
        }
        prepared["operation"]["operation_sha256"] = (
            self.adapter.review_exchange.sha256_json(operation_record)
        )
        authority = next(
            comment for comment in changed["comments"] if comment["id"] == "authority-1"
        )
        authority_record = json.loads(authority["body"])
        authority_record["exchange_id"] = forged_exchange
        authority_record["supersedes_state_sha256"] = forged_prior
        authority["body"] = self.adapter.review_exchange.canonical_json(
            authority_record
        )
        prepared["authority_receipt"]["sha256"] = (
            self.adapter.review_exchange.sha256_text(authority["body"])
        )
        prepared["precondition_sha256"] = self.adapter._precondition_sha256(
            target=prepared["target"],
            actor_id=prepared["actor_id"],
            requirements_sha256=prepared["requirements_sha256"],
            plan={
                "id": prepared["operation"]["comment_id"],
                "author_id": prepared["actor_id"],
                "body_sha256": prepared["operation"]["expected_body_sha256"],
            },
            review=prepared["peer"],
            authority_receipt=prepared["authority_receipt"],
        )
        published = self.apply_operation(changed, prepared, "unused")

        result = self.adapter.verify_publication(
            {"prepared": prepared, "snapshot": published}
        )

        self.assertEqual("unknown_outcome", result["status"])
        self.assertIsNone(result["receipt"])

    def test_reframe_rejects_a_supplied_state_that_is_not_the_retained_review(
        self,
    ) -> None:
        with_plan, _ = self.initial_plan_snapshot()
        stopped = self.adapter.prepare_review(
            self.review_request(
                with_plan,
                findings=[self.finding()],
                stop_reason="requirements_reframe",
            )
        )
        old_snapshot = self.apply_operation(with_plan, stopped, "review-1")
        previous = self.adapter.review_exchange.extract_carrier(
            old_snapshot["comments"][1]["body"]
        )
        tampered = copy.deepcopy(previous)
        tampered["state_sha256"] = "e" * 64
        changed = copy.deepcopy(old_snapshot)
        changed["issue"]["body"] = "Changed requirements."
        changed["comments"].append(self.reframe_authority(changed, previous))

        with self.assertRaises(self.adapter.ProtocolError):
            self.adapter.prepare_plan(self.reframe_plan_request(changed, tampered))

        unauthorized = copy.deepcopy(changed)
        unauthorized["comments"][-1]["author"]["is_authority"] = False
        unauthorized_request = self.reframe_plan_request(changed, previous)
        unauthorized_request["snapshot"] = unauthorized
        with self.assertRaises(self.adapter.ProtocolError):
            self.adapter.prepare_plan(unauthorized_request)

    def test_reframe_rejects_authority_for_a_different_superseded_exchange(
        self,
    ) -> None:
        with_plan, _ = self.initial_plan_snapshot()
        stopped = self.adapter.prepare_review(
            self.review_request(
                with_plan,
                findings=[self.finding()],
                stop_reason="requirements_reframe",
            )
        )
        old_snapshot = self.apply_operation(with_plan, stopped, "review-1")
        previous = self.adapter.review_exchange.extract_carrier(
            old_snapshot["comments"][1]["body"]
        )
        changed = copy.deepcopy(old_snapshot)
        changed["issue"]["body"] = "Changed requirements."
        authority = self.reframe_authority(changed, previous)
        record = json.loads(authority["body"])
        record["supersedes_state_sha256"] = "e" * 64
        authority["body"] = self.adapter.review_exchange.canonical_json(record)
        changed["comments"].append(authority)

        with self.assertRaises(self.adapter.ProtocolError):
            self.adapter.prepare_plan(self.reframe_plan_request(changed, previous))

    def test_terminal_review_binds_the_exact_current_plan_carrier(self) -> None:
        terminal = self.go_snapshot()
        plan = terminal["comments"][0]
        envelope = self.adapter.review_exchange.extract_carrier(plan["body"])
        changed = copy.deepcopy(envelope["state"])
        changed["responses"][0]["evidence"] = ["Different answer evidence."]
        changed_envelope = self.adapter.review_exchange.make_envelope(
            changed, self.adapter.review_exchange.AUTHOR_EVENT_SCHEMA_ID
        )
        visible = plan["body"].split(
            "\n\n<!-- HomericIntelligence:review-exchange:", 1
        )[0]
        plan["body"] = self.adapter.review_exchange.render_carrier(
            visible, changed_envelope, "author-event"
        )

        inspected = self.adapter.inspect_snapshot(terminal)

        self.assertEqual("withheld", inspected["status"])
        self.assertEqual("reviewed_plan_drift", inspected["diagnostics"][0]["code"])

    def test_terminal_state_rejects_a_different_valid_author_answer(self) -> None:
        terminal = self.go_snapshot()
        no_go = self.no_go_snapshot()
        contested = self.adapter.prepare_plan(
            self.plan_request(
                no_go,
                responses=[
                    {
                        "finding_id": "F-001",
                        "kind": "contest",
                        "evidence": ["The author contests the blocker."],
                        "tradeoff": None,
                    }
                ],
                content="## Plan\n\nAdd and verify the five-round guard.",
            )
        )
        terminal["comments"][0]["body"] = contested["operation"]["body"]
        plan = terminal["comments"][0]
        review = terminal["comments"][1]
        review_envelope = self.adapter.review_exchange.extract_carrier(review["body"])
        visible = review["body"].split(
            "\n\n<!-- HomericIntelligence:review-exchange:", 1
        )[0]
        old_token = next(
            line
            for line in visible.splitlines()
            if line.startswith(self.adapter.REVIEWED_PLAN_PREFIX)
        )
        new_token = (
            f"{self.adapter.REVIEWED_PLAN_PREFIX}"
            f"token={self.adapter._source_token(plan)['token']} -->"
        )
        visible = visible.replace(old_token, new_token)
        changed_state = copy.deepcopy(review_envelope["state"])
        visible_sha256 = self.adapter.review_exchange.sha256_text(visible)
        changed_state["artifact_binding"]["visible_content_sha256"] = visible_sha256
        final_event = changed_state["accepted_events"][-1]
        final_event["artifact_binding"]["visible_content_sha256"] = visible_sha256
        final_digest = self.adapter.review_exchange._event_digest(final_event)
        changed_state["accepted_event_sha256"] = final_digest
        changed_state["progress"][-1]["accepted_event_sha256"] = final_digest
        review["body"] = self.adapter.review_exchange.render_carrier(
            visible,
            self.adapter.review_exchange.make_envelope(changed_state),
            "state",
        )

        inspected = self.adapter.inspect_snapshot(terminal)
        finalized = self.adapter.verify_finalize(
            {"snapshot": terminal, "candidate_body": "# Candidate"}
        )

        self.assertEqual("withheld", inspected["status"])
        self.assertEqual(
            "terminal_source_chain_invalid", inspected["diagnostics"][0]["code"]
        )
        self.assertEqual("withheld", finalized["status"])

    def test_inspection_rejects_missing_or_malformed_reviewed_plan_identity(
        self,
    ) -> None:
        terminal = self.go_snapshot()
        missing = copy.deepcopy(terminal)
        missing["comments"] = [missing["comments"][1]]

        review = terminal["comments"][1]
        visible, carrier_suffix = review["body"].split(
            "\n\n<!-- HomericIntelligence:review-exchange:", 1
        )
        reviewed_marker = next(
            line
            for line in visible.splitlines()
            if line.startswith(self.adapter.REVIEWED_PLAN_PREFIX)
        )
        malformed_visible = visible.replace(
            reviewed_marker, reviewed_marker[:-4] + "bad -->"
        )
        duplicate_visible = f"{visible}\n\n{reviewed_marker}"

        cases: list[tuple[dict[str, Any], str]] = [(missing, "reviewed_plan_missing")]
        for changed_visible in (malformed_visible, duplicate_visible):
            changed = copy.deepcopy(terminal)
            changed["comments"][1]["body"] = (
                f"{changed_visible}\n\n<!-- HomericIntelligence:review-exchange:"
                f"{carrier_suffix}"
            )
            cases.append((changed, "malformed_carrier"))

        for snapshot, code in cases:
            with self.subTest(code=code):
                inspected = self.adapter.inspect_snapshot(snapshot)
                self.assertEqual("withheld", inspected["status"])
                self.assertEqual(code, inspected["diagnostics"][0]["code"])

    def test_inspection_rejects_invalid_pending_and_orphan_author_events(self) -> None:
        no_go = self.no_go_snapshot()
        review_envelope = self.adapter.review_exchange.extract_carrier(
            no_go["comments"][1]["body"]
        )
        plan = no_go["comments"][0]
        plan_envelope = self.adapter.review_exchange.extract_carrier(plan["body"])
        visible = plan["body"].split(
            "\n\n<!-- HomericIntelligence:review-exchange:", 1
        )[0]

        invalid_answer = copy.deepcopy(plan_envelope["state"])
        invalid_answer["prior_state_sha256"] = review_envelope["state_sha256"]
        invalid_answer["artifact_binding"]["revision"] = "plan-1"
        invalid_answer["responses"] = []
        invalid_envelope = self.adapter.review_exchange.make_envelope(
            invalid_answer, self.adapter.review_exchange.AUTHOR_EVENT_SCHEMA_ID
        )
        invalid_snapshot = copy.deepcopy(no_go)
        invalid_snapshot["comments"][0]["body"] = (
            self.adapter.review_exchange.render_carrier(
                visible, invalid_envelope, "author-event"
            )
        )

        wrong_revision = copy.deepcopy(invalid_answer)
        wrong_revision["artifact_binding"]["revision"] = "plan-replacement"
        wrong_envelope = self.adapter.review_exchange.make_envelope(
            wrong_revision, self.adapter.review_exchange.AUTHOR_EVENT_SCHEMA_ID
        )
        wrong_snapshot = copy.deepcopy(no_go)
        wrong_snapshot["comments"][0]["body"] = (
            self.adapter.review_exchange.render_carrier(
                visible, wrong_envelope, "author-event"
            )
        )

        orphan = copy.deepcopy(invalid_snapshot)
        orphan["comments"] = [orphan["comments"][0]]
        cases = (
            (invalid_snapshot, "author_event_rejected"),
            (wrong_snapshot, "plan_identity_drift"),
            (orphan, "orphan_author_event"),
        )
        for snapshot, code in cases:
            with self.subTest(code=code):
                inspected = self.adapter.inspect_snapshot(snapshot)
                self.assertEqual("withheld", inspected["status"])
                self.assertEqual(code, inspected["diagnostics"][0]["code"])

    def test_terminal_review_rejects_same_body_plan_replacement(self) -> None:
        terminal = self.go_snapshot()
        replacement = copy.deepcopy(terminal["comments"][0])
        replacement["id"] = "plan-replacement"
        replacement["url"] = replacement["url"].replace("plan-1", "plan-replacement")
        terminal["comments"][0] = replacement

        inspected = self.adapter.inspect_snapshot(terminal)
        finalized = self.adapter.verify_finalize(
            {"snapshot": terminal, "candidate_body": "# Candidate"}
        )

        self.assertEqual("withheld", inspected["status"])
        self.assertEqual("plan_identity_drift", inspected["diagnostics"][0]["code"])
        self.assertEqual("withheld", finalized["status"])

    def test_state_readers_reject_a_forged_go_without_transition_proof(self) -> None:
        terminal = self.go_snapshot()
        review = terminal["comments"][1]
        envelope = self.adapter.review_exchange.extract_carrier(review["body"])
        forged_state = copy.deepcopy(envelope["state"])
        forged_state["prior_state_sha256"] = "f" * 64
        forged_envelope = {
            "schema_id": self.adapter.review_exchange.STATE_SCHEMA_ID,
            "schema_version": 1,
            "state": forged_state,
            "state_sha256": self.adapter.review_exchange.sha256_json(forged_state),
        }
        visible = review["body"].split(
            "\n\n<!-- HomericIntelligence:review-exchange:", 1
        )[0]
        review["body"] = (
            f"{visible}\n\n<!-- HomericIntelligence:review-exchange:v1 "
            f"kind=state sha256={forged_envelope['state_sha256']} -->\n"
            "```json\n"
            f"{self.adapter.review_exchange.canonical_json(forged_envelope)}\n"
            "```\n"
        )

        inspected = self.adapter.inspect_snapshot(terminal)
        finalized = self.adapter.verify_finalize(
            {"snapshot": terminal, "candidate_body": "# Candidate"}
        )

        self.assertEqual("withheld", inspected["status"])
        self.assertEqual("malformed_carrier", inspected["diagnostics"][0]["code"])
        self.assertEqual("withheld", finalized["status"])

    def test_declared_targets_not_plan_byte_count_control_scope_growth(self) -> None:
        no_go = self.no_go_snapshot()
        response = {
            "finding_id": "F-001",
            "kind": "fix",
            "evidence": ["The same target contains the correction."],
            "tradeoff": None,
        }
        prepared = self.adapter.prepare_plan(
            self.plan_request(
                no_go,
                responses=[response],
                content="## Plan\n\n" + ("More detail. " * 200),
            )
        )

        self.assertEqual(
            no_go["comments"][0]["id"], prepared["operation"]["comment_id"]
        )
        self.assertEqual(2, len(prepared["state"]["scope"]))

    def test_marker_identity_conflicts_fail_closed(self) -> None:
        prepared = self.adapter.prepare_plan(self.plan_request(self.snapshot()))
        body = prepared["operation"]["body"]
        cases: list[dict[str, Any]] = []
        duplicate = self.snapshot()
        duplicate["comments"] = [self.comment("p1", body), self.comment("p2", body)]
        cases.append(duplicate)
        foreign = self.snapshot()
        foreign_comment = self.comment("p1", body)
        foreign_comment["author"] = {
            "id": "U_foreign",
            "login": "foreign",
            "is_authority": False,
        }
        foreign["comments"] = [foreign_comment]
        cases.append(foreign)
        malformed = self.snapshot()
        malformed["comments"] = [
            self.comment(
                "p1",
                "<!-- HomericIntelligence:plan-issue -->\n\n"
                "<!-- HomericIntelligence:review-exchange:v1 kind=author-event sha256=bad -->",
            )
        ]
        cases.append(malformed)

        for snapshot in cases:
            with self.subTest(snapshot=snapshot):
                inspected = self.adapter.inspect_snapshot(snapshot)
                self.assertEqual("withheld", inspected["status"])
                self.assertEqual("human_decision", inspected["next_action"])

    def test_only_top_level_marker_lines_define_issue_artifacts(self) -> None:
        cases = (
            "A prose reference to <!-- HomericIntelligence:plan-issue --> is not identity.",
            "> <!-- HomericIntelligence:plan-issue -->",
            "```md\n<!-- HomericIntelligence:plan-issue -->\n```",
            "- <!-- HomericIntelligence:plan-issue -->",
            "<!-- hidden\n<!-- HomericIntelligence:plan-issue -->",
            "<pre>\n<!-- HomericIntelligence:plan-issue -->\n</pre>",
            "<script>\n<!-- HomericIntelligence:plan-issue -->\n</script>",
            "<style>\n<!-- HomericIntelligence:plan-issue -->\n</style>",
            "<textarea>\n<!-- HomericIntelligence:plan-issue -->\n</textarea>",
            "<div>\n<!-- HomericIntelligence:plan-issue -->\n</div>",
            (
                '<x-review data-kind="plan">\n'
                "<!-- HomericIntelligence:plan-issue -->\n\nVisible text."
            ),
        )
        for body in cases:
            with self.subTest(body=body):
                snapshot = self.snapshot()
                snapshot["comments"] = [self.comment("ignored", body)]

                inspected = self.adapter.inspect_snapshot(snapshot)

                self.assertEqual("ready", inspected["status"])
                self.assertEqual("prepare_plan", inspected["next_action"])
                self.assertIsNone(inspected["plan"])

    def test_legacy_aliases_are_adopted_only_as_explicit_round_one(self) -> None:
        snapshot = self.snapshot()
        snapshot["comments"] = [
            self.comment(
                "plan-legacy",
                "<!-- hephaestus-plan:canonical -->\n\nLegacy plan.",
            ),
            self.comment(
                "review-legacy",
                "<!-- athena:issue-review -->\n\nLegacy NO-GO.",
            ),
        ]

        prepared = self.adapter.prepare_review(
            self.review_request(
                snapshot,
                findings=[self.finding()],
                legacy_import=True,
            )
        )

        self.assertEqual("update", prepared["operation"]["action"])
        self.assertEqual("review-legacy", prepared["operation"]["comment_id"])
        self.assertIn(
            "<!-- HomericIntelligence:issue-review -->",
            prepared["operation"]["body"],
        )
        self.assertNotIn("<!-- athena:issue-review -->", prepared["operation"]["body"])

    def test_cross_role_and_alias_marker_conflicts_fail_closed(self) -> None:
        cases: list[list[dict[str, Any]]] = [
            [
                self.comment(
                    "both",
                    "<!-- HomericIntelligence:plan-issue -->\n"
                    "<!-- HomericIntelligence:issue-review -->",
                )
            ],
            [
                self.comment("current", "<!-- HomericIntelligence:plan-issue -->"),
                self.comment("legacy", "<!-- athena:plan-issue -->"),
            ],
            [
                self.comment(
                    "repeated",
                    "<!-- athena:plan-issue -->\n<!-- athena:plan-issue -->",
                )
            ],
        ]
        for comments in cases:
            with self.subTest(comments=comments):
                snapshot = self.snapshot()
                snapshot["comments"] = comments

                inspected = self.adapter.inspect_snapshot(snapshot)

                self.assertEqual("withheld", inspected["status"])
                self.assertEqual("human_decision", inspected["next_action"])

    def test_unrelated_comment_change_does_not_stale_preparation(self) -> None:
        source = self.snapshot()
        source["comments"] = [
            {
                "id": "other-1",
                "url": "https://example.invalid/other-1",
                "author": {
                    "id": "U_other",
                    "login": "other",
                    "is_authority": False,
                },
                "body": "Unrelated discussion.",
            }
        ]
        prepared = self.adapter.prepare_plan(self.plan_request(source))
        published = self.apply_operation(source, prepared, "plan-1")
        published["comments"][0]["body"] = "Changed unrelated discussion."

        result = self.adapter.verify_publication(
            {"prepared": prepared, "snapshot": published}
        )

        self.assertEqual("verified", result["status"])

    def test_snapshot_schema_and_identity_boundaries_fail_closed(self) -> None:
        cases: list[tuple[str, object]] = [("not an object", None)]

        missing = self.snapshot()
        del missing["comments"]
        cases.append(("missing field", missing))
        unknown = self.snapshot()
        unknown["extra"] = True
        cases.append(("unknown field", unknown))
        wrong_schema = self.snapshot()
        wrong_schema["schema_id"] = "athena.issue-exchange.unknown"
        cases.append(("schema identifier", wrong_schema))
        wrong_version = self.snapshot()
        wrong_version["schema_version"] = True
        cases.append(("schema version", wrong_version))
        wrong_provider = self.snapshot()
        wrong_provider["target"]["provider"] = "unknown"
        cases.append(("provider", wrong_provider))
        wrong_number = self.snapshot()
        wrong_number["target"]["number"] = 0
        cases.append(("issue number", wrong_number))
        wrong_actor = self.snapshot()
        wrong_actor["actor"]["id"] = ""
        cases.append(("actor", wrong_actor))
        wrong_state = self.snapshot()
        wrong_state["issue"]["state"] = "draft"
        cases.append(("issue state", wrong_state))
        wrong_criteria = self.snapshot()
        wrong_criteria["issue"]["acceptance_criteria"] = {}
        cases.append(("criteria collection", wrong_criteria))
        duplicate_criteria = self.snapshot()
        duplicate_criteria["issue"]["acceptance_criteria"] *= 2
        cases.append(("duplicate criterion", duplicate_criteria))
        wrong_comments = self.snapshot()
        wrong_comments["comments"] = {}
        cases.append(("comment collection", wrong_comments))
        duplicate_comments = self.snapshot()
        duplicate_comments["comments"] = [
            self.comment("same", "first"),
            self.comment("same", "second"),
        ]
        cases.append(("duplicate comment", duplicate_comments))

        for label, snapshot in cases:
            with (
                self.subTest(label=label),
                self.assertRaises(self.adapter.ProtocolError),
            ):
                self.adapter.inspect_snapshot(snapshot)

    def test_snapshot_requires_a_complete_comment_collection(self) -> None:
        complete = self.snapshot()
        self.assertEqual("ready", self.adapter.inspect_snapshot(complete)["status"])

        invalid = []
        incomplete = self.snapshot()
        incomplete["comments_complete"] = False
        invalid.append(incomplete)
        missing = self.snapshot()
        del missing["comments_complete"]
        invalid.append(missing)
        for snapshot in invalid:
            with self.assertRaises(self.adapter.ProtocolError):
                self.adapter.inspect_snapshot(snapshot)

        incomplete_plan = self.snapshot()
        incomplete_plan["comments_complete"] = False
        no_go = self.no_go_snapshot()
        no_go["comments_complete"] = False
        terminal = self.go_snapshot()
        terminal["comments_complete"] = False
        operations: tuple[Callable[[], object], ...] = (
            lambda: self.adapter.prepare_plan(self.plan_request(incomplete_plan)),
            lambda: self.adapter.prepare_review(self.review_request(no_go)),
            lambda: self.adapter.verify_finalize(
                {"snapshot": terminal, "candidate_body": "# Final plan"}
            ),
        )
        for operation in operations:
            with self.assertRaises(self.adapter.ProtocolError):
                operation()

    def test_prepare_inputs_reject_ambiguous_events_and_targets(self) -> None:
        malformed_event = self.plan_request(self.snapshot())
        malformed_event["event"] = []
        plan_cases: list[tuple[str, dict[str, Any]]] = [
            ("event", malformed_event),
            (
                "initial response",
                self.plan_request(
                    self.snapshot(),
                    responses=[
                        {
                            "finding_id": "F-001",
                            "kind": "fix",
                            "evidence": ["Not applicable to an initial plan."],
                            "tradeoff": None,
                        }
                    ],
                ),
            ),
            (
                "initial scope reason",
                self.plan_request(
                    self.snapshot(), scope_change_reason="No prior scope."
                ),
            ),
            (
                "visible marker",
                self.plan_request(
                    self.snapshot(),
                    content="<!-- HomericIntelligence:plan-issue -->",
                ),
            ),
        ]
        empty_scope = self.plan_request(self.snapshot())
        empty_scope["event"]["scope"] = []
        plan_cases.append(("empty scope", empty_scope))
        bad_kind = self.plan_request(self.snapshot())
        bad_kind["event"]["scope"] = [{"kind": "package", "value": "athena"}]
        plan_cases.append(("target kind", bad_kind))
        duplicate_scope = self.plan_request(self.snapshot())
        duplicate_scope["event"]["scope"] = self.target_scope()[:1] * 2
        plan_cases.append(("duplicate scope", duplicate_scope))

        for label, request in plan_cases:
            with (
                self.subTest(label=label),
                self.assertRaises(self.adapter.ProtocolError),
            ):
                self.adapter.prepare_plan(request)

        with_plan, _prepared = self.initial_plan_snapshot()
        review = self.review_request(with_plan)
        review["event"]["legacy_import"] = "yes"
        with self.assertRaises(self.adapter.ProtocolError):
            self.adapter.prepare_review(review)

    def test_inspection_rejects_carrier_role_and_binding_drift(self) -> None:
        plan_snapshot, _prepared = self.initial_plan_snapshot()
        plan_body = plan_snapshot["comments"][0]["body"]
        plan_envelope = self.adapter.review_exchange.extract_carrier(plan_body)
        visible = plan_body.split("\n\n<!-- HomericIntelligence:review-exchange:", 1)[0]

        wrong_role = copy.deepcopy(plan_envelope)
        wrong_role["schema_id"] = self.adapter.review_exchange.STATE_SCHEMA_ID
        wrong_role["state"] = self.adapter.review_exchange.reduce_request(
            {
                "previous": None,
                "event": {
                    "event_type": "reviewer_assessment",
                    "exchange_id": "issue-role-drift",
                    "prior_state_sha256": None,
                    "round": 1,
                    "surface": "issue",
                    "target": {
                        "provider": "github",
                        "repository": "owner/repository",
                        "number": 210,
                        "url": "https://github.com/owner/repository/issues/210",
                    },
                    "requirements_sha256": self.adapter._requirements_sha256(
                        self.adapter._snapshot(plan_snapshot)
                    ),
                    "supersedes_state_sha256": None,
                    "artifact_binding": plan_envelope["state"]["artifact_binding"],
                    "scope": plan_envelope["state"]["scope"],
                    "coverage_complete": True,
                    "go_eligible": True,
                    "responses": [],
                    "new_findings": [],
                    "stop_reason": None,
                },
            }
        )["envelope"]["state"]
        wrong_role = self.adapter.review_exchange.make_envelope(wrong_role["state"])
        wrong_role_body = self.adapter.review_exchange.render_carrier(
            visible, wrong_role, "state"
        )

        requirements_drift = copy.deepcopy(plan_envelope["state"])
        requirements_drift["requirements_sha256"] = "b" * 64
        drift_envelope = self.adapter.review_exchange.make_envelope(
            requirements_drift, self.adapter.review_exchange.AUTHOR_EVENT_SCHEMA_ID
        )
        drift_body = self.adapter.review_exchange.render_carrier(
            visible, drift_envelope, "author-event"
        )

        cases = (
            (wrong_role_body, "malformed_carrier"),
            (drift_body, "requirements_drift"),
        )
        for body, code in cases:
            with self.subTest(code=code):
                snapshot = copy.deepcopy(plan_snapshot)
                snapshot["comments"][0]["body"] = body
                inspected = self.adapter.inspect_snapshot(snapshot)
                self.assertEqual("withheld", inspected["status"])
                self.assertEqual(code, inspected["diagnostics"][0]["code"])

    def test_publication_verifies_updates_and_peer_preconditions(self) -> None:
        source = self.no_go_snapshot()
        response = {
            "finding_id": "F-001",
            "kind": "fix",
            "evidence": ["The bounded exchange is implemented."],
            "tradeoff": None,
        }
        prepared = self.adapter.prepare_plan(
            self.plan_request(
                source,
                responses=[response],
                content="## Plan\n\nImplement the bounded exchange and its tests.",
            )
        )
        published = self.apply_operation(source, prepared, "unused")
        verified = self.adapter.verify_publication(
            {"prepared": prepared, "snapshot": published}
        )
        self.assertEqual("verified", verified["status"])

        peer_drift = copy.deepcopy(published)
        for comment in peer_drift["comments"]:
            if comment["id"] == "review-1":
                comment["body"] += "\nchanged"
        unknown = self.adapter.verify_publication(
            {"prepared": prepared, "snapshot": peer_drift}
        )
        self.assertEqual("unknown_outcome", unknown["status"])

        with self.assertRaises(self.adapter.ProtocolError):
            self.adapter.verify_publication(
                {"prepared": {"schema_id": "wrong"}, "snapshot": published}
            )

    def test_corrective_plan_publication_rejects_a_substituted_result_state(
        self,
    ) -> None:
        source = self.no_go_snapshot()
        prepared = self.adapter.prepare_plan(
            self.plan_request(
                source,
                responses=[
                    {
                        "finding_id": "F-001",
                        "kind": "fix",
                        "evidence": ["The bounded exchange is implemented."],
                        "tradeoff": None,
                    }
                ],
                content="## Plan\n\nImplement the bounded exchange and its tests.",
            )
        )
        published = self.apply_operation(source, prepared, "unused")
        unrelated = self.adapter.inspect_snapshot(self.go_snapshot())["envelope"]
        assert unrelated is not None
        tampered = copy.deepcopy(prepared)
        tampered["state"] = unrelated["state"]
        tampered["state_sha256"] = unrelated["state_sha256"]
        tampered["next_action"] = unrelated["state"]["next_action"]

        result = self.adapter.verify_publication(
            {"prepared": tampered, "snapshot": published}
        )

        self.assertEqual("unknown_outcome", result["status"])
        self.assertIsNone(result["receipt"])

    def test_finalize_readback_rejects_identity_body_and_record_drift(self) -> None:
        snapshot = self.go_snapshot()
        prepared = self.adapter.verify_finalize(
            {"snapshot": snapshot, "candidate_body": "# Final plan"}
        )
        published = copy.deepcopy(snapshot)
        published["issue"]["body"] = prepared["operation"]["body"]

        identity_drift = copy.deepcopy(published)
        identity_drift["actor"]["id"] = "U_other"
        body_drift = copy.deepcopy(published)
        body_drift["issue"]["body"] += "changed"
        state_drift = copy.deepcopy(published)
        state_drift["issue"]["state"] = "closed"
        for drifted, code in (
            (identity_drift, "finalize_identity_drift"),
            (body_drift, "finalize_readback_mismatch"),
            (state_drift, "finalize_requirements_drift"),
        ):
            with self.subTest(code=code):
                result = self.adapter.verify_finalize(
                    {"snapshot": drifted, "prepared": prepared}
                )
                self.assertEqual("unknown_outcome", result["status"])
                self.assertEqual(code, result["diagnostics"][0]["code"])

        with self.assertRaises(self.adapter.ProtocolError):
            self.adapter.verify_finalize(None)
        with self.assertRaises(self.adapter.ProtocolError):
            self.adapter.verify_finalize(
                {"snapshot": published, "prepared": {"schema_id": "wrong"}}
            )
        malformed = copy.deepcopy(prepared)
        malformed["sources"] = None
        with self.assertRaises(self.adapter.ProtocolError):
            self.adapter.verify_finalize({"snapshot": published, "prepared": malformed})

        tampered_allowlist = copy.deepcopy(prepared)
        tampered_allowlist["deletion_allowlist"] = ["unrelated-comment"]
        with self.assertRaises(self.adapter.ProtocolError):
            self.adapter.verify_finalize(
                {"snapshot": published, "prepared": tampered_allowlist}
            )

        tampered_operation = copy.deepcopy(prepared)
        tampered_operation["operation"]["operation_sha256"] = "f" * 64
        with self.assertRaises(self.adapter.ProtocolError):
            self.adapter.verify_finalize(
                {"snapshot": published, "prepared": tampered_operation}
            )

        tampered_precondition = copy.deepcopy(prepared)
        tampered_precondition["precondition_sha256"] = "f" * 64
        with self.assertRaises(self.adapter.ProtocolError):
            self.adapter.verify_finalize(
                {"snapshot": published, "prepared": tampered_precondition}
            )

        replaced_expected_body = copy.deepcopy(prepared)
        replaced_expected_body["operation"]["expected_issue_body_sha256"] = "e" * 64
        replaced_expected_body["operation"]["operation_sha256"] = (
            self.adapter.review_exchange.sha256_json(
                {
                    key: value
                    for key, value in replaced_expected_body["operation"].items()
                    if key != "operation_sha256"
                }
            )
        )
        with self.assertRaises(self.adapter.ProtocolError):
            self.adapter.verify_finalize(
                {"snapshot": published, "prepared": replaced_expected_body}
            )

        invalid_records: list[dict[str, Any]] = []
        wrong_version = copy.deepcopy(prepared)
        wrong_version["schema_version"] = True
        invalid_records.append(wrong_version)
        wrong_status = copy.deepcopy(prepared)
        wrong_status["status"] = "withheld"
        invalid_records.append(wrong_status)
        wrong_diagnostics = copy.deepcopy(prepared)
        wrong_diagnostics["diagnostics"] = [
            {"code": "tampered", "message": "Not ready."}
        ]
        invalid_records.append(wrong_diagnostics)
        wrong_remaining = copy.deepcopy(prepared)
        wrong_remaining["remaining_comment_ids"] = ["plan-1"]
        invalid_records.append(wrong_remaining)
        wrong_requirements = copy.deepcopy(prepared)
        wrong_requirements["requirements_sha256"] = "bad"
        invalid_records.append(wrong_requirements)
        wrong_context = copy.deepcopy(prepared)
        wrong_context["requirements_context_sha256"] = "bad"
        invalid_records.append(wrong_context)
        missing_state = copy.deepcopy(prepared)
        missing_state["state"] = None
        missing_state["state_sha256"] = None
        invalid_records.append(missing_state)
        wrong_source_r = copy.deepcopy(prepared)
        wrong_source_r["sources"]["R"] = "f" * 64
        invalid_records.append(wrong_source_r)
        duplicate_sources = copy.deepcopy(prepared)
        duplicate_sources["sources"]["P"] = copy.deepcopy(
            duplicate_sources["sources"]["V"]
        )
        invalid_records.append(duplicate_sources)
        wrong_target = copy.deepcopy(prepared)
        wrong_target["target"]["provider"] = "unknown"
        invalid_records.append(wrong_target)
        wrong_actor = copy.deepcopy(prepared)
        wrong_actor["actor_id"] = ""
        invalid_records.append(wrong_actor)
        wrong_action = copy.deepcopy(prepared)
        wrong_action["operation"]["action"] = "update"
        invalid_records.append(wrong_action)
        wrong_expected_digest = copy.deepcopy(prepared)
        wrong_expected_digest["operation"]["expected_issue_body_sha256"] = "bad"
        invalid_records.append(wrong_expected_digest)
        wrong_body_digest = copy.deepcopy(prepared)
        wrong_body_digest["operation"]["body_sha256"] = "f" * 64
        invalid_records.append(wrong_body_digest)
        invalid_marker = copy.deepcopy(prepared)
        invalid_marker["operation"]["body"] = "# No finalized marker"
        invalid_marker["operation"]["body_sha256"] = (
            self.adapter.review_exchange.sha256_text(
                invalid_marker["operation"]["body"]
            )
        )
        invalid_records.append(invalid_marker)
        mismatched_final_digest = copy.deepcopy(prepared)
        mismatched_final_digest["operation"]["F"] = "f" * 64
        invalid_records.append(mismatched_final_digest)

        for invalid in invalid_records:
            with (
                self.subTest(invalid=invalid),
                self.assertRaises(self.adapter.ProtocolError),
            ):
                self.adapter.verify_finalize(
                    {"snapshot": published, "prepared": invalid}
                )

    def test_finalize_readback_rechecks_live_action_bound_authority(self) -> None:
        no_go = self.no_go_snapshot()
        risk_request = {
            "finding_id": "F-001",
            "kind": "risk_acceptance",
            "evidence": ["The compatibility risk cannot be removed."],
            "tradeoff": "The repository authority must accept the risk.",
        }
        plan = self.adapter.prepare_plan(
            self.plan_request(no_go, responses=[risk_request])
        )
        answered = self.apply_operation(no_go, plan, "unused")
        answered["comments"].append(self.human_authority(answered))
        decision = self.adapter.prepare_review(self.human_review_request(answered))
        terminal = self.apply_operation(answered, decision, "unused")
        prepared = self.adapter.verify_finalize(
            {"snapshot": terminal, "candidate_body": "# Final plan"}
        )
        published = copy.deepcopy(terminal)
        published["issue"]["body"] = prepared["operation"]["body"]
        published["comments"] = [
            comment
            for comment in published["comments"]
            if comment["id"] != "authority-1"
        ]

        result = self.adapter.verify_finalize(
            {"snapshot": published, "prepared": prepared}
        )

        self.assertEqual("unknown_outcome", result["status"])
        self.assertEqual(
            "finalize_source_chain_invalid", result["diagnostics"][0]["code"]
        )

    def test_active_legacy_review_is_adopted_in_place_as_round_one(self) -> None:
        snapshot = self.snapshot()
        snapshot["comments"] = [
            self.comment(
                "plan-legacy",
                "<!-- HomericIntelligence:plan-issue -->\n\nLegacy plan.",
            ),
            self.comment(
                "review-legacy",
                "<!-- HomericIntelligence:issue-review -->\n\nLegacy NO-GO.",
            ),
        ]
        prepared = self.adapter.prepare_review(
            self.review_request(
                snapshot,
                findings=[self.finding()],
                legacy_import=True,
            )
        )

        self.assertEqual("update", prepared["operation"]["action"])
        self.assertEqual("review-legacy", prepared["operation"]["comment_id"])
        self.assertEqual(1, prepared["state"]["round"])
        self.assertEqual("open", prepared["state"]["findings"][0]["state"])

    def test_finalization_requires_current_terminal_ledger_and_verifies_readback(
        self,
    ) -> None:
        snapshot = self.go_snapshot()
        prepared = self.adapter.verify_finalize(
            {"snapshot": snapshot, "candidate_body": "# Final plan\n\nBounded work."}
        )

        self.assertEqual("ready", prepared["status"])
        self.assertEqual("replace_body", prepared["operation"]["action"])
        self.assertEqual(["plan-1", "review-1"], prepared["deletion_allowlist"])
        self.assertIn(
            "HomericIntelligence:finalize-plan", prepared["operation"]["body"]
        )

        published = copy.deepcopy(snapshot)
        published["issue"]["body"] = prepared["operation"]["body"]
        verified = self.adapter.verify_finalize(
            {"snapshot": published, "prepared": prepared}
        )
        self.assertEqual("verified", verified["status"])
        self.assertEqual(prepared["deletion_allowlist"], verified["deletion_allowlist"])

        drifted = copy.deepcopy(published)
        drifted["comments"][0]["body"] += "drift"
        withheld = self.adapter.verify_finalize(
            {"snapshot": drifted, "prepared": prepared}
        )
        self.assertEqual("unknown_outcome", withheld["status"])

    def test_finalized_epoch_reports_partial_cleanup_for_retained_sources(self) -> None:
        terminal = self.go_snapshot()
        prepared = self.adapter.verify_finalize(
            {"snapshot": terminal, "candidate_body": "# Final plan"}
        )
        finalized = copy.deepcopy(terminal)
        finalized["issue"]["body"] = prepared["operation"]["body"]

        partial = self.adapter.verify_finalize(
            {"snapshot": finalized, "candidate_body": "# Ignored"}
        )
        clean = copy.deepcopy(finalized)
        clean["comments"] = []
        no_change = self.adapter.verify_finalize(
            {"snapshot": clean, "candidate_body": "# Ignored"}
        )

        self.assertEqual("partial_cleanup", partial["status"])
        self.assertEqual(["plan-1", "review-1"], partial["remaining_comment_ids"])
        self.assertEqual([], partial["deletion_allowlist"])
        self.assertEqual("no_change", no_change["status"])

        for retained_id in ("plan-1", "review-1"):
            with self.subTest(retained_id=retained_id):
                one_remaining = copy.deepcopy(finalized)
                one_remaining["comments"] = [
                    comment
                    for comment in one_remaining["comments"]
                    if comment["id"] == retained_id
                ]
                result = self.adapter.verify_finalize(
                    {"snapshot": one_remaining, "candidate_body": "# Ignored"}
                )
                self.assertEqual("partial_cleanup", result["status"])
                self.assertEqual([retained_id], result["remaining_comment_ids"])

        drifted = copy.deepcopy(finalized)
        drifted["comments"][0]["body"] += "drift"
        rejected = self.adapter.verify_finalize(
            {"snapshot": drifted, "candidate_body": "# Ignored"}
        )
        self.assertEqual("withheld", rejected["status"])
        self.assertEqual(
            "finalized_source_mismatch", rejected["diagnostics"][0]["code"]
        )

    def test_finalization_rejects_a_body_larger_than_the_provider_limit(self) -> None:
        terminal = self.go_snapshot()
        candidate = "x" * self.adapter.review_exchange.PROVIDER_BODY_LIMITS["github"]

        with self.assertRaises(self.adapter.ProtocolError):
            self.adapter.verify_finalize(
                {"snapshot": terminal, "candidate_body": candidate}
            )

    def test_material_edit_after_finalized_cleanup_starts_a_new_epoch(self) -> None:
        terminal = self.go_snapshot()
        prepared = self.adapter.verify_finalize(
            {"snapshot": terminal, "candidate_body": "# Final plan"}
        )
        unchanged = copy.deepcopy(terminal)
        unchanged["issue"]["body"] = prepared["operation"]["body"]
        unchanged["comments"] = []

        sealed = self.adapter.inspect_snapshot(unchanged)
        stale = copy.deepcopy(unchanged)
        stale["issue"]["body"] += "\nHuman requirement: support a second target.\n"
        rejected = self.adapter.inspect_snapshot(stale)
        replaced = copy.deepcopy(unchanged)
        replaced["issue"]["body"] = "Human requirement: support a second target."
        restart = self.adapter.inspect_snapshot(replaced)

        self.assertEqual("finalized", sealed["status"])
        self.assertEqual("withheld", rejected["status"])
        self.assertEqual("ready", restart["status"])
        self.assertEqual("prepare_plan", restart["next_action"])
        self.assertIsNone(restart["envelope"])

    def test_comment_preparation_rejects_a_body_larger_than_the_provider_limit(
        self,
    ) -> None:
        content = "x" * self.adapter.review_exchange.PROVIDER_BODY_LIMITS["github"]

        with self.assertRaises(self.adapter.ProtocolError):
            self.adapter.prepare_plan(
                self.plan_request(self.snapshot(), content=content)
            )

    def test_finalization_rejects_no_go_and_candidate_markers(self) -> None:
        no_go = self.no_go_snapshot()
        rejected = self.adapter.verify_finalize(
            {"snapshot": no_go, "candidate_body": "# Candidate"}
        )
        self.assertEqual("withheld", rejected["status"])

    def test_finalized_epoch_requires_one_exact_marker_with_valid_digest(self) -> None:
        template = (
            "# Finalized plan\n\n"
            f"<!-- athena:finalize-plan R={'a' * 64} P={'b' * 64} "
            f"V={'c' * 64} F=<F> -->\n"
        )
        digest = self.adapter.review_exchange.sha256_text(template)
        valid_body = template.replace("F=<F>", f"F={digest}")
        cases = (
            (valid_body, "finalized"),
            (valid_body.replace(digest, "d" * 64), "withheld"),
            (
                f"This prose names <!-- athena:finalize-plan R={'a' * 64} "
                + f"P={'b' * 64} V={'c' * 64} F={'d' * 64} --> only.",
                "ready",
            ),
            (
                "# Invalid\n\n<!-- HomericIntelligence:finalize-plan "
                + "R=bad P=bad V=bad F=bad -->\n",
                "withheld",
            ),
        )
        for body, status in cases:
            with self.subTest(status=status, body=body):
                snapshot = self.snapshot()
                snapshot["issue"]["body"] = body

                inspected = self.adapter.inspect_snapshot(snapshot)

                self.assertEqual(status, inspected["status"])

        go = self.go_snapshot()
        rejected = self.adapter.verify_finalize(
            {
                "snapshot": go,
                "candidate_body": (
                    "# Candidate\n\n"
                    "<!-- HomericIntelligence:finalize-plan R=x P=x V=x F=x -->"
                ),
            }
        )
        self.assertEqual("withheld", rejected["status"])

    def test_cli_commands_are_read_only_json_filters(self) -> None:
        snapshot = self.snapshot()
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "snapshot.json"
            before = json.dumps(snapshot, sort_keys=True)
            path.write_text(before, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "inspect", str(path)],
                capture_output=True,
                text=True,
                check=False,
            )
            help_result = subprocess.run(
                [sys.executable, str(SCRIPT), "--help"],
                capture_output=True,
                text=True,
                check=False,
            )
            after = path.read_text(encoding="utf-8")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            "athena.issue-exchange.inspect-result",
            json.loads(result.stdout)["schema_id"],
        )
        self.assertEqual(before, after)
        self.assertEqual(0, help_result.returncode, help_result.stderr)

    def test_cli_output_write_failure_is_one_operational_diagnostic(self) -> None:
        class FailingTextOutput:
            def __init__(self, error: BaseException) -> None:
                self.error = error

            def write(self, _value: str) -> int:
                raise self.error

        source = self.adapter.review_exchange.canonical_json(self.snapshot()).encode()
        errors = (
            OSError("output failed"),
            BrokenPipeError("pipe closed"),
            UnicodeEncodeError("ascii", "é", 0, 1, "encoding failed"),
        )
        for error in errors:
            with self.subTest(error=type(error).__name__):
                stderr = io.StringIO()
                output = FailingTextOutput(error)
                with (
                    patch.object(
                        self.adapter.review_exchange,
                        "_read_input",
                        return_value=source,
                    ),
                    patch.object(sys, "stdout", output),
                    redirect_stderr(stderr),
                ):
                    result = self.adapter.main(["inspect", "-"])

                self.assertEqual(2, result)
                self.assertEqual(1, len(stderr.getvalue().splitlines()))

    def test_cli_escapes_untrusted_control_characters_in_diagnostics(self) -> None:
        forged = "failure\nforged\x1b[2J"
        protocol_snapshot = self.snapshot()
        protocol_snapshot[forged] = True
        protocol_source = self.adapter.review_exchange.canonical_json(
            protocol_snapshot
        ).encode()
        valid_source = self.adapter.review_exchange.canonical_json(
            self.snapshot()
        ).encode()
        cases = (
            (self.adapter.ProtocolError(forged), protocol_source, 1, None),
            (self.adapter.OperationalError(forged), valid_source, 2, "read"),
            (OSError(forged), valid_source, 2, "inspect"),
        )

        for error, source, expected, boundary in cases:
            with self.subTest(error=type(error).__name__):
                stderr = io.StringIO()
                read_effect = error if boundary == "read" else None
                inspect_effect = error if boundary == "inspect" else None
                with (
                    patch.object(
                        self.adapter.review_exchange,
                        "_read_input",
                        return_value=source,
                        side_effect=read_effect,
                    ),
                    patch.object(
                        self.adapter,
                        "inspect_snapshot",
                        wraps=self.adapter.inspect_snapshot,
                        side_effect=inspect_effect,
                    ),
                    redirect_stderr(stderr),
                ):
                    result = self.adapter.main(["inspect", "-"])

                diagnostic = stderr.getvalue()
                self.assertEqual(expected, result)
                self.assertEqual(1, diagnostic.count("\n"))
                self.assertNotIn("\r", diagnostic)
                self.assertNotIn("\x1b", diagnostic)
                self.assertIn("\\n", diagnostic)
                self.assertIn("\\x1b", diagnostic)

    def test_cli_always_writes_canonical_output_as_utf8(self) -> None:
        request = self.plan_request(
            self.snapshot(), content="## Plan\n\nAdd the résumé boundary."
        )
        environment = dict(os.environ)
        environment["PYTHONIOENCODING"] = "ascii"
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "request.json"
            path.write_text(
                self.adapter.review_exchange.canonical_json(request), encoding="utf-8"
            )
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "prepare-plan", str(path)],
                capture_output=True,
                check=False,
                env=environment,
            )

        self.assertEqual(0, result.returncode, result.stderr.decode("utf-8"))
        output = json.loads(result.stdout.decode("utf-8"))
        self.assertIn("résumé", output["operation"]["body"])

    def test_reframed_review_can_enter_a_corrective_plan_round(self) -> None:
        with_plan, _ = self.initial_plan_snapshot()
        stopped = self.adapter.prepare_review(
            self.review_request(
                with_plan,
                findings=[self.finding()],
                stop_reason="requirements_reframe",
            )
        )
        old_snapshot = self.apply_operation(with_plan, stopped, "review-1")
        previous = self.adapter.review_exchange.extract_carrier(
            old_snapshot["comments"][1]["body"]
        )
        changed = copy.deepcopy(old_snapshot)
        changed["issue"]["body"] = "Implement the changed bounded protocol."
        changed["comments"].append(self.reframe_authority(changed, previous))
        prepared_plan = self.adapter.prepare_plan(
            self.reframe_plan_request(changed, previous)
        )
        replanned = self.apply_operation(changed, prepared_plan, "unused")
        reframe_review = self.reframe_review_request(replanned, previous)
        reframe_review["event"]["new_findings"] = [self.finding()]
        prepared_review = self.adapter.prepare_review(reframe_review)
        self.assertEqual(
            [previous["state"]["exchange_id"]],
            prepared_review["state"]["accepted_events"][0]["superseded_exchange_ids"],
        )
        reframed = self.apply_operation(replanned, prepared_review, "unused")

        inspected = self.adapter.inspect_snapshot(reframed)
        response = {
            "finding_id": "F-001",
            "kind": "fix",
            "evidence": ["The reframed implementation now has the round guard."],
            "tradeoff": None,
        }
        correction = self.adapter.prepare_plan(
            self.plan_request(
                reframed,
                responses=[response],
                content="## Plan\n\nCorrect the finding in the reframed plan.",
            )
        )

        self.assertEqual("ready", inspected["status"])
        self.assertEqual("prepare_plan", inspected["next_action"])
        self.assertEqual("ready", correction["status"])
        self.assertEqual("update", correction["operation"]["action"])
        self.assertEqual(
            prepared_review["state_sha256"],
            self.adapter.review_exchange.extract_carrier(
                correction["operation"]["body"]
            )["state"]["prior_state_sha256"],
        )
        corrected = self.apply_operation(reframed, correction, "unused")
        corrected_inspection = self.adapter.inspect_snapshot(corrected)
        self.assertEqual("ready", corrected_inspection["status"])
        self.assertEqual("prepare_review", corrected_inspection["next_action"])
        terminal_review = self.adapter.prepare_review(
            self.review_request(
                corrected,
                responses=[
                    {
                        "finding_id": "F-001",
                        "kind": "resolve",
                        "evidence": ["The reframed round guard test passes."],
                        "closure_condition": None,
                    }
                ],
            )
        )
        terminal = self.apply_operation(corrected, terminal_review, "unused")

        publication = self.adapter.verify_publication(
            {"prepared": terminal_review, "snapshot": terminal}
        )
        terminal_inspection = self.adapter.inspect_snapshot(terminal)
        finalized = self.adapter.verify_finalize(
            {"snapshot": terminal, "candidate_body": "# Final reframed plan"}
        )

        self.assertEqual("verified", publication["status"])
        self.assertEqual("ready", terminal_inspection["status"])
        self.assertEqual("finalize", terminal_inspection["next_action"])
        self.assertEqual("ready", finalized["status"])

    def test_pending_reframe_requires_the_explicit_reframe_event(self) -> None:
        with_plan, _ = self.initial_plan_snapshot()
        stopped = self.adapter.prepare_review(
            self.review_request(
                with_plan,
                findings=[self.finding()],
                stop_reason="requirements_reframe",
            )
        )
        old_snapshot = self.apply_operation(with_plan, stopped, "review-1")
        previous = self.adapter.review_exchange.extract_carrier(
            old_snapshot["comments"][1]["body"]
        )
        changed = copy.deepcopy(old_snapshot)
        changed["issue"]["body"] = "Implement the changed bounded protocol."
        changed["comments"].append(self.reframe_authority(changed, previous))
        prepared_plan = self.adapter.prepare_plan(
            self.reframe_plan_request(changed, previous)
        )
        pending = self.apply_operation(changed, prepared_plan, "unused")

        inspected = self.adapter.inspect_snapshot(pending)
        ordinary = self.adapter.prepare_review(self.review_request(pending))

        self.assertEqual("ready", inspected["status"])
        self.assertEqual("prepare_review", inspected["next_action"])
        self.assertEqual("pending_reframe", inspected["diagnostics"][0]["code"])
        self.assertEqual("withheld", ordinary["status"])
        self.assertEqual(
            "pending_reframe_event_required", ordinary["diagnostics"][0]["code"]
        )

    def test_pending_reframe_rejects_a_human_decision_for_the_old_exchange(
        self,
    ) -> None:
        old_snapshot = self.no_go_snapshot()
        previous = self.adapter.review_exchange.extract_carrier(
            old_snapshot["comments"][1]["body"]
        )
        changed = copy.deepcopy(old_snapshot)
        changed["issue"]["body"] = "Implement the changed bounded protocol."
        changed["comments"].append(self.reframe_authority(changed, previous))
        prepared_plan = self.adapter.prepare_plan(
            self.reframe_plan_request(changed, previous)
        )
        pending = self.apply_operation(changed, prepared_plan, "unused")
        decisions = [
            {
                "finding_id": "F-001",
                "kind": "select_closure",
                "closure_condition": "Use the authority-selected old closure.",
            }
        ]
        authority_body = self.adapter.review_exchange.canonical_json(
            {
                "schema_id": "athena.review-exchange.authority",
                "schema_version": 1,
                "action": "human_decision",
                "target": previous["state"]["target"],
                "exchange_id": previous["state"]["exchange_id"],
                "requirements_sha256": previous["state"]["requirements_sha256"],
                "prior_state_sha256": previous["state_sha256"],
                "supersedes_state_sha256": None,
                "decisions": decisions,
            }
        )
        authority = self.comment("authority-human", authority_body)
        authority["author"]["is_authority"] = True
        pending["comments"].append(authority)
        request = {
            "snapshot": pending,
            "content": "## Review\n\nAn old-exchange decision must not bypass reframe.",
            "event": {
                "event_type": "human_decision",
                "authority_receipt": {
                    "reference": authority["url"],
                    "sha256": self.adapter.review_exchange.sha256_text(
                        authority["body"]
                    ),
                },
                "decisions": decisions,
            },
        }

        prepared = self.adapter.prepare_review(request)

        self.assertEqual("withheld", prepared["status"])
        self.assertEqual(
            "pending_reframe_event_required", prepared["diagnostics"][0]["code"]
        )

    def test_human_can_select_closure_while_the_exchange_awaits_a_plan(self) -> None:
        snapshot = self.no_go_snapshot()
        inspected = self.adapter.inspect_snapshot(snapshot)
        decisions = [
            {
                "finding_id": "F-001",
                "kind": "select_closure",
                "closure_condition": "Verify both the fourth and fifth assessments.",
            }
        ]
        authority = self.comment(
            "authority-1",
            self.authority_body(
                snapshot,
                action="human_decision",
                exchange_id=inspected["state"]["exchange_id"],
                prior_state_sha256=inspected["state_sha256"],
                supersedes_state_sha256=None,
                decisions=decisions,
            ),
        )
        authority["author"]["is_authority"] = True
        snapshot["comments"].append(authority)
        request = {
            "snapshot": snapshot,
            "content": "## Review\n\nThe authority selected one closure condition.",
            "event": {
                "event_type": "human_decision",
                "authority_receipt": {
                    "reference": authority["url"],
                    "sha256": self.adapter.review_exchange.sha256_text(
                        authority["body"]
                    ),
                },
                "decisions": decisions,
            },
        }

        prepared = self.adapter.prepare_review(request)

        self.assertEqual("prepare_plan", inspected["next_action"])
        self.assertEqual("ready", prepared["status"])
        self.assertEqual(1, prepared["state"]["round"])
        self.assertEqual("author_response", prepared["state"]["next_action"])
        self.assertEqual(
            "Verify both the fourth and fifth assessments.",
            prepared["state"]["findings"][0]["closure_condition"],
        )

    def test_visible_content_rejects_all_legacy_role_markers(self) -> None:
        markers = (
            "<!-- hephaestus-plan:canonical -->",
            "<!-- athena:plan-issue -->",
            "<!-- hephaestus-plan-review:canonical -->",
            "<!-- athena:issue-review -->",
        )

        for marker in markers:
            with (
                self.subTest(marker=marker),
                self.assertRaises(self.adapter.ProtocolError),
            ):
                self.adapter.prepare_plan(
                    self.plan_request(self.snapshot(), content=f"## Plan\n\n{marker}\n")
                )

    def test_malformed_finalize_namespace_marker_is_not_treated_as_absent(
        self,
    ) -> None:
        cases = [
            (namespace, indentation)
            for namespace in ("HomericIntelligence", "athena")
            for indentation in range(4)
        ]
        for namespace, indentation in cases:
            with self.subTest(namespace=namespace, indentation=indentation):
                snapshot = self.snapshot()
                snapshot["issue"]["body"] = (
                    f"{' ' * indentation}<!-- {namespace}:finalize-plan-->\n"
                )

                inspected = self.adapter.inspect_snapshot(snapshot)

                self.assertEqual("withheld", inspected["status"])
                self.assertEqual(
                    "malformed_finalize_marker",
                    inspected["diagnostics"][0]["code"],
                )

    def test_longer_finalize_marker_names_are_not_protocol_markers(self) -> None:
        longer_marker = "<!-- HomericIntelligence:finalize-planner -->"
        snapshot = self.snapshot()
        snapshot["issue"]["body"] = longer_marker

        inspected = self.adapter.inspect_snapshot(snapshot)
        plan = self.adapter.prepare_plan(
            self.plan_request(self.snapshot(), content=f"## Plan\n\n{longer_marker}")
        )
        finalized = self.adapter.verify_finalize(
            {
                "snapshot": self.go_snapshot(),
                "candidate_body": f"# Final plan\n\n{longer_marker}",
            }
        )

        self.assertEqual("ready", inspected["status"])
        self.assertEqual("ready", plan["status"])
        self.assertEqual("ready", finalized["status"])
        self.assertEqual(
            "valid", self.adapter._finalized_status(finalized["operation"]["body"])
        )

    def test_finalization_replaces_only_its_appended_digest_placeholder(self) -> None:
        candidate = "# Final plan\n\nKeep the literal `F=<F>` example."

        prepared = self.adapter.verify_finalize(
            {"snapshot": self.go_snapshot(), "candidate_body": candidate}
        )

        self.assertEqual("ready", prepared["status"])
        self.assertIn("literal `F=<F>`", prepared["operation"]["body"])
        self.assertEqual(
            "valid", self.adapter._finalized_status(prepared["operation"]["body"])
        )

    def test_finalization_withholds_when_the_appended_marker_is_not_top_level(
        self,
    ) -> None:
        candidate = "# Final plan\n\n```text\nan unclosed fence"

        prepared = self.adapter.verify_finalize(
            {"snapshot": self.go_snapshot(), "candidate_body": candidate}
        )

        self.assertEqual("withheld", prepared["status"])
        self.assertEqual(
            "candidate_finalization_invalid", prepared["diagnostics"][0]["code"]
        )


if __name__ == "__main__":
    unittest.main()
