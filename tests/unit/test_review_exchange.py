"""Behavior tests for the bounded two-sided review exchange."""

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
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import ModuleType
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills/review-exchange/scripts/review_exchange.py"
HEX_A = "a" * 64
HEX_B = "b" * 64
HEX_C = "c" * 64


def load_module() -> ModuleType:
    """Load the executable helper as a test module."""
    name = f"test_review_exchange_{id(SCRIPT)}"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("The review-exchange helper cannot be loaded.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class ReviewExchangeTests(unittest.TestCase):
    exchange: ModuleType

    @classmethod
    def setUpClass(cls) -> None:
        cls.exchange = load_module()

    def artifact(
        self, revision: str = "revision-1", visible: str = HEX_A
    ) -> dict[str, Any]:
        return {
            "revision": revision,
            "sha256": HEX_B,
            "visible_content_sha256": visible,
        }

    def target(self) -> dict[str, Any]:
        return {
            "provider": "github",
            "repository": "owner/repository",
            "number": 7,
            "url": "https://github.com/owner/repository/pull/7",
        }

    def finding(
        self,
        finding_id: str = "F-001",
        *,
        severity: str = "major",
        disposition: str = "required",
        introduction: str = "initial",
        material_architecture: bool = False,
    ) -> dict[str, Any]:
        return {
            "id": finding_id,
            "severity": severity,
            "disposition": disposition,
            "category": None,
            "material_architecture": material_architecture,
            "location": "src/example.py:7",
            "impact": "The result can be incorrect.",
            "evidence": ["The failing case returns 0."],
            "closure_condition": (
                "The failing case returns 1." if disposition == "required" else None
            ),
            "introduction": introduction,
        }

    def initial_event(
        self,
        *,
        findings: list[dict[str, Any]] | None = None,
        coverage_complete: bool = True,
        go_eligible: bool = True,
        stop_reason: str | None = None,
        exchange_id: str = "exchange-7",
        requirements_sha256: str = HEX_C,
        supersedes_state_sha256: str | None = None,
    ) -> dict[str, Any]:
        return {
            "event_type": "reviewer_assessment",
            "exchange_id": exchange_id,
            "prior_state_sha256": None,
            "round": 1,
            "surface": "pull_request",
            "target": self.target(),
            "requirements_sha256": requirements_sha256,
            "supersedes_state_sha256": supersedes_state_sha256,
            "artifact_binding": self.artifact(),
            "scope": ["path:src/example.py"],
            "coverage_complete": coverage_complete,
            "go_eligible": go_eligible,
            "responses": [],
            "new_findings": findings if findings is not None else [self.finding()],
            "stop_reason": stop_reason,
        }

    def reduce(
        self, event: dict[str, Any], previous: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            self.exchange.reduce_request({"previous": previous, "event": event}),
        )

    def initial_state(self) -> dict[str, Any]:
        return cast(dict[str, Any], self.reduce(self.initial_event())["envelope"])

    def author_event(
        self,
        state: dict[str, Any],
        kind: str,
        *,
        revision: str | None = None,
        scope: list[str] | None = None,
    ) -> dict[str, Any]:
        if revision is None:
            revision = f"revision-{state['state']['round'] + 1}"
        return {
            "event_type": "author_response",
            "exchange_id": "exchange-7",
            "prior_state_sha256": state["state_sha256"],
            "artifact_binding": self.artifact(revision),
            "scope": scope or ["path:src/example.py"],
            "scope_change_reason": None,
            "responses": [
                {
                    "finding_id": "F-001",
                    "kind": kind,
                    "evidence": ["The correction is in revision-2."],
                    "tradeoff": (
                        "The strict path rejects legacy input."
                        if kind in {"fix_with_tradeoff", "risk_acceptance"}
                        else None
                    ),
                }
            ],
        }

    def answered_state(self, kind: str = "fix") -> dict[str, Any]:
        state = self.initial_state()
        return cast(
            dict[str, Any],
            self.reduce(self.author_event(state, kind), state)["envelope"],
        )

    def review_event(
        self,
        state: dict[str, Any],
        action: str,
        *,
        round_number: int = 2,
        evidence: list[str] | None = None,
        closure_condition: str | None = None,
        findings: list[dict[str, Any]] | None = None,
        coverage_complete: bool = True,
        go_eligible: bool = True,
        stop_reason: str | None = None,
    ) -> dict[str, Any]:
        return {
            "event_type": "reviewer_assessment",
            "exchange_id": "exchange-7",
            "prior_state_sha256": state["state_sha256"],
            "round": round_number,
            "artifact_binding": state["state"]["artifact_binding"],
            "scope": state["state"]["scope"],
            "coverage_complete": coverage_complete,
            "go_eligible": go_eligible,
            "responses": [
                {
                    "finding_id": "F-001",
                    "kind": action,
                    "evidence": evidence or ["The current artifact was checked."],
                    "closure_condition": closure_condition,
                }
            ],
            "new_findings": findings or [],
            "stop_reason": stop_reason,
        }

    def human_event(
        self,
        state: dict[str, Any],
        kind: str,
        *,
        finding_id: str = "F-001",
        closure_condition: str | None = None,
    ) -> dict[str, Any]:
        return {
            "event_type": "human_decision",
            "exchange_id": state["state"]["exchange_id"],
            "prior_state_sha256": state["state_sha256"],
            "artifact_binding": state["state"]["artifact_binding"],
            "authority_receipt": {
                "reference": "policy/decision/9",
                "sha256": HEX_C,
            },
            "decisions": [
                {
                    "finding_id": finding_id,
                    "kind": kind,
                    "closure_condition": closure_condition,
                }
            ],
        }

    def reframe_event(
        self,
        state: dict[str, Any],
        *,
        exchange_id: str = "exchange-8",
        requirements_sha256: str = HEX_A,
        go_eligible: bool = True,
        superseded_exchange_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        if superseded_exchange_ids is None:
            genesis = state["state"]["accepted_events"][0]
            superseded_exchange_ids = [
                *genesis.get("superseded_exchange_ids", []),
                state["state"]["exchange_id"],
            ]
        return {
            "event_type": "reframe",
            "exchange_id": exchange_id,
            "prior_state_sha256": state["state_sha256"],
            "round": 1,
            "surface": state["state"]["surface"],
            "target": state["state"]["target"],
            "requirements_sha256": requirements_sha256,
            "supersedes_state_sha256": state["state_sha256"],
            "superseded_exchange_ids": superseded_exchange_ids,
            "authority_receipt": {
                "reference": "policy/reframe/11",
                "sha256": HEX_B,
            },
            "artifact_binding": self.artifact("revision-reframed"),
            "scope": ["path:src/example.py"],
            "coverage_complete": True,
            "go_eligible": go_eligible,
            "responses": [],
            "new_findings": [],
            "stop_reason": None,
        }

    def authority_record(
        self,
        action: str,
        *,
        target: dict[str, Any] | None = None,
        exchange_id: str = "exchange-7",
        requirements_sha256: str = HEX_C,
        prior_state_sha256: str | None,
        supersedes_state_sha256: str | None = None,
        decisions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return {
            "schema_id": "athena.review-exchange.authority",
            "schema_version": 1,
            "action": action,
            "target": target or self.target(),
            "exchange_id": exchange_id,
            "requirements_sha256": requirements_sha256,
            "prior_state_sha256": prior_state_sha256,
            "supersedes_state_sha256": supersedes_state_sha256,
            "decisions": decisions or [],
        }

    def authority_receipt(self, body: str) -> dict[str, str]:
        return {
            "reference": "policy/authority/17",
            "sha256": self.exchange.sha256_text(body),
        }

    def test_initial_assessment_records_stable_state_and_go_rules(self) -> None:
        no_go = self.reduce(self.initial_event())
        go = self.reduce(self.initial_event(findings=[]))

        self.assertEqual("awaiting_author", no_go["envelope"]["state"]["phase"])
        self.assertEqual("NO-GO", no_go["envelope"]["state"]["verdict"])
        self.assertEqual("F-001", no_go["envelope"]["state"]["findings"][0]["id"])
        self.assertEqual(1, no_go["envelope"]["state"]["round"])
        self.assertEqual("complete", go["envelope"]["state"]["phase"])
        self.assertEqual("GO", go["envelope"]["state"]["verdict"])
        self.assertEqual("finalize", go["envelope"]["state"]["next_action"])

    def test_ci_free_assessment_needs_one_later_eligible_review_for_go(self) -> None:
        conditional = self.reduce(self.initial_event(findings=[], go_eligible=False))[
            "envelope"
        ]

        self.assertEqual("complete", conditional["state"]["phase"])
        self.assertEqual("CONDITIONAL GO", conditional["state"]["verdict"])
        self.assertEqual("none", conditional["state"]["next_action"])
        self.assertFalse(conditional["state"]["go_eligible"])

        repeated = self.review_event(
            conditional,
            "resolve",
            round_number=2,
            go_eligible=False,
        )
        repeated["responses"] = []
        with self.assertRaises(self.exchange.ProtocolError):
            self.reduce(repeated, conditional)

        eligible = {**repeated, "go_eligible": True}
        upgraded = self.reduce(eligible, conditional)["envelope"]

        self.assertEqual("GO", upgraded["state"]["verdict"])
        self.assertEqual("finalize", upgraded["state"]["next_action"])
        self.assertTrue(upgraded["state"]["go_eligible"])
        self.assertEqual(2, upgraded["state"]["round"])

    def test_round_five_ineligible_assessment_requires_a_human_decision(self) -> None:
        state = self.reduce(
            self.initial_event(findings=[], coverage_complete=False, go_eligible=False)
        )["envelope"]
        for round_number in range(2, 5):
            event = self.review_event(
                state,
                "resolve",
                round_number=round_number,
                coverage_complete=False,
                go_eligible=False,
            )
            event["responses"] = []
            state = self.reduce(event, state)["envelope"]
        round_five = self.review_event(
            state,
            "resolve",
            round_number=5,
            go_eligible=False,
        )
        round_five["responses"] = []
        exhausted = self.reduce(round_five, state)["envelope"]
        self.assertEqual("decision_required", exhausted["state"]["phase"])
        self.assertEqual("NO-GO", exhausted["state"]["verdict"])
        self.assertEqual("human_decision", exhausted["state"]["next_action"])

        upgrade = self.review_event(
            exhausted,
            "resolve",
            round_number=5,
            go_eligible=True,
        )
        upgrade["responses"] = []
        with self.assertRaises(self.exchange.ProtocolError):
            self.reduce(upgrade, exhausted)

    def test_author_human_and_reframe_preserve_go_eligibility_rules(self) -> None:
        prior = self.reduce(self.initial_event(go_eligible=False))["envelope"]
        answered = self.reduce(
            self.author_event(prior, "risk_acceptance", revision="revision-1"), prior
        )["envelope"]
        accepted = self.reduce(self.human_event(answered, "accept_risk"), answered)[
            "envelope"
        ]

        self.assertFalse(answered["state"]["go_eligible"])
        self.assertEqual("CONDITIONAL GO", accepted["state"]["verdict"])
        self.assertFalse(accepted["state"]["go_eligible"])

        reframed = self.reduce(self.reframe_event(accepted), accepted)["envelope"]
        self.assertEqual("GO", reframed["state"]["verdict"])
        self.assertTrue(reframed["state"]["go_eligible"])

    def test_issue_state_requires_go_eligibility(self) -> None:
        event = self.initial_event(findings=[], go_eligible=False)
        event["surface"] = "issue"

        with self.assertRaises(self.exchange.ProtocolError):
            self.reduce(event)

    def test_reviewer_and_reframe_events_require_boolean_go_eligibility(self) -> None:
        initial = self.initial_event()
        missing = {key: value for key, value in initial.items() if key != "go_eligible"}
        with self.assertRaises(self.exchange.ProtocolError):
            self.reduce(missing)
        with self.assertRaises(self.exchange.ProtocolError):
            self.reduce({**initial, "go_eligible": "yes"})

        prior = self.reduce(self.initial_event(stop_reason="requirements_reframe"))[
            "envelope"
        ]
        reframe = self.reframe_event(prior)
        del reframe["go_eligible"]
        with self.assertRaises(self.exchange.ProtocolError):
            self.reduce(reframe, prior)

    def test_state_replay_rejects_forged_go_eligibility(self) -> None:
        conditional = self.reduce(self.initial_event(findings=[], go_eligible=False))[
            "envelope"
        ]
        forged = copy.deepcopy(conditional)
        forged["state"].update(
            go_eligible=True,
            verdict="GO",
            next_action="finalize",
        )
        forged["state_sha256"] = self.exchange.sha256_json(forged["state"])

        with self.assertRaises(self.exchange.ProtocolError):
            self.exchange.verify_envelope(forged)

    def test_nonblocking_findings_cannot_force_another_exchange_step(self) -> None:
        observation = self.finding(severity="minor", disposition="suggestion")
        observation["closure_condition"] = None
        finding_dependent_reasons = (
            "closure_conflict",
            "replacement_blocker",
            "scope_growth_without_progress",
            "no_consensus",
        )

        for stop_reason in finding_dependent_reasons:
            with (
                self.subTest(stop_reason=stop_reason),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.reduce(
                    self.initial_event(findings=[observation], stop_reason=stop_reason)
                )

        reframed = self.reduce(
            self.initial_event(
                findings=[observation], stop_reason="requirements_reframe"
            )
        )["envelope"]
        self.assertEqual("decision_required", reframed["state"]["phase"])

    def test_minor_finding_rejects_nit_and_fyi_dispositions(self) -> None:
        for disposition in ("nit", "FYI"):
            with (
                self.subTest(disposition=disposition),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.reduce(
                    self.initial_event(
                        findings=[
                            self.finding(
                                severity="minor",
                                disposition=disposition,
                            )
                        ]
                    )
                )

    def test_simplification_category_is_retained_and_strict(self) -> None:
        simplification = self.finding()
        simplification["category"] = "simplification"

        state = self.reduce(self.initial_event(findings=[simplification]))["envelope"][
            "state"
        ]

        self.assertEqual("simplification", state["findings"][0]["category"])

        unsupported = {**simplification, "category": "performance"}
        with self.assertRaises(self.exchange.ProtocolError):
            self.reduce(self.initial_event(findings=[unsupported]))

    def test_author_response_table_preserves_round(self) -> None:
        cases = (
            ("fix", "answered_fix"),
            ("fix_with_tradeoff", "answered_tradeoff"),
            ("contest", "contested"),
            ("risk_acceptance", "answered_tradeoff"),
        )
        for action, expected in cases:
            prior = self.initial_state()
            with self.subTest(action=action):
                result = self.reduce(self.author_event(prior, action), prior)
                state = result["envelope"]["state"]
                self.assertEqual(expected, state["findings"][0]["state"])
                self.assertEqual(1, state["round"])
                self.assertEqual("awaiting_reviewer", state["phase"])
                self.assertIsNotNone(result["author_event"])

    def test_pull_request_author_can_reanswer_on_a_new_head(self) -> None:
        initial = self.initial_state()
        first = self.reduce(self.author_event(initial, "fix"), initial)["envelope"]
        refresh = self.author_event(
            first,
            "fix_with_tradeoff",
            revision="revision-3",
        )

        result = self.reduce(refresh, first)
        state = result["envelope"]["state"]

        self.assertEqual("awaiting_reviewer", state["phase"])
        self.assertEqual("review_assessment", state["next_action"])
        self.assertEqual(1, state["round"])
        self.assertEqual(first["state"]["progress"], state["progress"])
        self.assertFalse(state["coverage_complete"])
        self.assertEqual("revision-3", state["artifact_binding"]["revision"])
        self.assertEqual("answered_tradeoff", state["findings"][0]["state"])
        self.assertEqual(
            "revision-3",
            state["findings"][0]["author_response"]["artifact_revision"],
        )
        self.assertEqual(3, len(state["accepted_events"]))
        self.assertEqual("author_reanswered", result["decision"]["reason"])
        self.assertIsNotNone(result["author_event"])

        replay = self.reduce(refresh, result["envelope"])
        self.assertEqual("replayed", replay["status"])
        self.assertEqual(result["envelope"], replay["envelope"])

    def test_pull_request_author_can_refresh_evidence_and_conditional_states(
        self,
    ) -> None:
        cases = (
            (
                "awaiting_evidence",
                self.reduce(self.initial_event(findings=[], coverage_complete=False))[
                    "envelope"
                ],
            ),
            (
                "conditional_complete",
                self.reduce(self.initial_event(findings=[], go_eligible=False))[
                    "envelope"
                ],
            ),
        )
        for label, previous in cases:
            refresh = self.author_event(previous, "fix", revision="revision-2")
            refresh["responses"] = []
            with self.subTest(state=label):
                result = self.reduce(refresh, previous)
                state = result["envelope"]["state"]
                self.assertEqual("awaiting_evidence", state["phase"])
                self.assertEqual("NO-GO", state["verdict"])
                self.assertEqual("review_assessment", state["next_action"])
                self.assertFalse(state["coverage_complete"])
                self.assertEqual(previous["state"]["round"], state["round"])
                self.assertEqual(previous["state"]["progress"], state["progress"])
                self.assertEqual("artifact_refreshed", result["decision"]["reason"])

    def test_changed_pr_head_requires_terminal_finding_revalidation(self) -> None:
        initial = self.reduce(self.initial_event(go_eligible=False))["envelope"]
        corrected = self.reduce(self.author_event(initial, "fix"), initial)
        resolved = self.reduce(
            self.review_event(
                corrected["envelope"],
                "resolve",
                go_eligible=False,
            ),
            corrected["envelope"],
        )["envelope"]
        self.assertEqual("CONDITIONAL GO", resolved["state"]["verdict"])

        missing = self.author_event(resolved, "fix", revision="revision-3")
        missing["responses"] = []
        with self.assertRaises(self.exchange.ProtocolError):
            self.reduce(missing, resolved)

        refresh = self.author_event(resolved, "fix", revision="revision-3")
        refreshed = self.reduce(refresh, resolved)["envelope"]

        self.assertEqual("awaiting_reviewer", refreshed["state"]["phase"])
        self.assertEqual("answered_fix", refreshed["state"]["findings"][0]["state"])
        self.assertIsNone(refreshed["state"]["findings"][0]["reviewer_response"])
        self.assertEqual(
            "revision-3",
            refreshed["state"]["findings"][0]["author_response"]["artifact_revision"],
        )

        kept = self.reduce(
            self.review_event(
                refreshed,
                "resolve",
                round_number=3,
                evidence=["The changed head still satisfies the closure condition."],
            ),
            refreshed,
        )["envelope"]
        self.assertEqual("GO", kept["state"]["verdict"])
        self.assertEqual("resolved", kept["state"]["findings"][0]["state"])
        self.assertEqual(3, kept["state"]["findings"][0]["reviewer_response"]["round"])

        regressed = self.reduce(
            self.review_event(
                refreshed,
                "still_present",
                round_number=3,
                evidence=["The changed head reproduces the original failure."],
            ),
            refreshed,
        )["envelope"]
        self.assertEqual("F-001", regressed["state"]["findings"][0]["id"])
        self.assertEqual("still_present", regressed["state"]["findings"][0]["state"])
        self.assertEqual("decision_required", regressed["state"]["phase"])
        self.assertEqual("human_decision", regressed["state"]["next_action"])

    def test_changed_pr_head_revalidates_withdrawn_finding(self) -> None:
        initial = self.reduce(self.initial_event(go_eligible=False))["envelope"]
        contested = self.reduce(self.author_event(initial, "contest"), initial)[
            "envelope"
        ]
        withdrawn = self.reduce(
            self.review_event(
                contested,
                "accept",
                go_eligible=False,
                evidence=["The original contest is valid."],
            ),
            contested,
        )["envelope"]
        self.assertEqual("withdrawn", withdrawn["state"]["findings"][0]["state"])

        refresh = self.author_event(withdrawn, "contest", revision="revision-3")
        refreshed = self.reduce(refresh, withdrawn)["envelope"]

        self.assertEqual("contested", refreshed["state"]["findings"][0]["state"])
        self.assertIsNone(refreshed["state"]["findings"][0]["reviewer_response"])
        kept = self.reduce(
            self.review_event(
                refreshed,
                "accept",
                round_number=3,
                evidence=["The contest remains valid on the changed head."],
            ),
            refreshed,
        )["envelope"]
        self.assertEqual("GO", kept["state"]["verdict"])
        self.assertEqual("withdrawn", kept["state"]["findings"][0]["state"])

    def test_changed_pr_head_clears_accepted_risk_authority(self) -> None:
        initial = self.reduce(self.initial_event(go_eligible=False))["envelope"]
        requested = self.reduce(
            self.author_event(
                initial,
                "risk_acceptance",
                revision=initial["state"]["artifact_binding"]["revision"],
            ),
            initial,
        )["envelope"]
        accepted = self.reduce(self.human_event(requested, "accept_risk"), requested)[
            "envelope"
        ]
        self.assertEqual("CONDITIONAL GO", accepted["state"]["verdict"])

        refresh = self.author_event(
            accepted,
            "risk_acceptance",
            revision="revision-2",
        )
        refreshed = self.reduce(refresh, accepted)["envelope"]
        finding = refreshed["state"]["findings"][0]

        self.assertEqual("answered_tradeoff", finding["state"])
        self.assertIsNone(finding["authority_receipt"])
        self.assertEqual("revision-2", finding["author_response"]["artifact_revision"])
        with self.assertRaises(self.exchange.ProtocolError):
            self.reduce(
                self.review_event(
                    refreshed,
                    "resolve",
                    round_number=2,
                ),
                refreshed,
            )

        reauthorized = self.reduce(
            self.human_event(refreshed, "accept_risk"), refreshed
        )["envelope"]
        self.assertEqual("awaiting_evidence", reauthorized["state"]["phase"])
        self.assertEqual("accepted_risk", reauthorized["state"]["findings"][0]["state"])
        self.assertIsNotNone(reauthorized["state"]["findings"][0]["authority_receipt"])
        final_review = self.review_event(
            reauthorized,
            "resolve",
            round_number=2,
        )
        final_review["responses"] = []
        complete = self.reduce(final_review, reauthorized)["envelope"]
        self.assertEqual("GO", complete["state"]["verdict"])
        self.assertEqual(
            "revision-2", complete["state"]["artifact_binding"]["revision"]
        )
        self.assertEqual("accepted_risk", complete["state"]["findings"][0]["state"])

    def test_changed_pr_head_does_not_revalidate_nonblocking_findings(self) -> None:
        observation = self.finding(severity="minor", disposition="suggestion")
        observation["closure_condition"] = None
        conditional = self.reduce(
            self.initial_event(findings=[observation], go_eligible=False)
        )["envelope"]
        refresh = self.author_event(conditional, "fix", revision="revision-2")
        refresh["responses"] = []

        refreshed = self.reduce(refresh, conditional)["envelope"]

        self.assertEqual("awaiting_evidence", refreshed["state"]["phase"])
        self.assertEqual("nonblocking", refreshed["state"]["findings"][0]["state"])
        self.assertIsNone(refreshed["state"]["findings"][0]["author_response"])
        self.assertIsNone(refreshed["state"]["findings"][0]["reviewer_response"])

    def test_normal_pr_correction_revalidates_closed_sibling_findings(self) -> None:
        second = self.finding("F-002")
        second["location"] = "src/second.py:9"
        second["impact"] = "The second result can be incorrect."
        second["evidence"] = ["The second failing case returns 0."]
        initial = self.reduce(self.initial_event(findings=[self.finding(), second]))[
            "envelope"
        ]
        first_answer = self.author_event(initial, "fix")
        first_answer["responses"].append(
            {
                "finding_id": "F-002",
                "kind": "fix",
                "evidence": ["The second correction is in revision-2."],
                "tradeoff": None,
            }
        )
        answered = self.reduce(first_answer, initial)["envelope"]
        assessment = self.review_event(answered, "resolve")
        assessment["responses"].append(
            {
                "finding_id": "F-002",
                "kind": "still_present",
                "evidence": ["The second failure remains."],
                "closure_condition": None,
            }
        )
        partial = self.reduce(assessment, answered)["envelope"]
        self.assertEqual("resolved", partial["state"]["findings"][0]["state"])
        self.assertEqual("still_present", partial["state"]["findings"][1]["state"])

        missing_revalidation = self.author_event(partial, "fix", revision="revision-3")
        missing_revalidation["responses"][0]["finding_id"] = "F-002"
        with self.assertRaises(self.exchange.ProtocolError):
            self.reduce(missing_revalidation, partial)

        complete_answer = copy.deepcopy(missing_revalidation)
        complete_answer["responses"].insert(
            0,
            {
                "finding_id": "F-001",
                "kind": "fix",
                "evidence": ["The first correction remains in revision-3."],
                "tradeoff": None,
            },
        )
        revalidated = self.reduce(complete_answer, partial)["envelope"]

        self.assertEqual(
            ["answered_fix", "answered_fix"],
            [finding["state"] for finding in revalidated["state"]["findings"]],
        )
        self.assertTrue(
            all(
                finding["reviewer_response"] is None
                for finding in revalidated["state"]["findings"]
            )
        )

    def test_reopened_terminal_sibling_without_net_progress_stops_early(self) -> None:
        second = self.finding("F-002")
        second["location"] = "src/second.py:9"
        second["impact"] = "The second result can be incorrect."
        second["evidence"] = ["The second failing case returns 0."]
        initial = self.reduce(self.initial_event(findings=[self.finding(), second]))[
            "envelope"
        ]
        first_answer = self.author_event(initial, "fix")
        first_answer["responses"].append(
            {
                "finding_id": "F-002",
                "kind": "fix",
                "evidence": ["The second correction is in revision-2."],
                "tradeoff": None,
            }
        )
        answered = self.reduce(first_answer, initial)["envelope"]
        assessment = self.review_event(answered, "resolve")
        assessment["responses"].append(
            {
                "finding_id": "F-002",
                "kind": "still_present",
                "evidence": ["The second failure remains."],
                "closure_condition": None,
            }
        )
        partial = self.reduce(assessment, answered)["envelope"]

        next_answer = self.author_event(partial, "fix", revision="revision-3")
        next_answer["responses"].append(
            {
                "finding_id": "F-002",
                "kind": "fix",
                "evidence": ["The second correction is in revision-3."],
                "tradeoff": None,
            }
        )
        revalidated = self.reduce(next_answer, partial)["envelope"]
        next_assessment = self.review_event(
            revalidated,
            "still_present",
            round_number=3,
            evidence=["The first failure has returned in revision-3."],
        )
        next_assessment["responses"].append(
            {
                "finding_id": "F-002",
                "kind": "resolve",
                "evidence": ["The second failure is corrected in revision-3."],
                "closure_condition": None,
            }
        )

        stopped = self.reduce(next_assessment, revalidated)

        self.assertEqual("decision_required", stopped["envelope"]["state"]["phase"])
        self.assertEqual("replacement_blocker", stopped["decision"]["reason"])

    def test_reopened_terminal_sibling_can_continue_after_net_progress(self) -> None:
        findings = [self.finding()]
        for finding_id in ("F-002", "F-003"):
            finding = self.finding(finding_id)
            finding["location"] = f"src/{finding_id.lower()}.py:9"
            finding["impact"] = f"The {finding_id} result can be incorrect."
            finding["evidence"] = [f"The {finding_id} failing case returns 0."]
            findings.append(finding)
        initial = self.reduce(self.initial_event(findings=findings))["envelope"]
        first_answer = self.author_event(initial, "fix")
        for finding_id in ("F-002", "F-003"):
            first_answer["responses"].append(
                {
                    "finding_id": finding_id,
                    "kind": "fix",
                    "evidence": [f"The {finding_id} correction is in revision-2."],
                    "tradeoff": None,
                }
            )
        answered = self.reduce(first_answer, initial)["envelope"]
        assessment = self.review_event(answered, "resolve")
        for finding_id in ("F-002", "F-003"):
            assessment["responses"].append(
                {
                    "finding_id": finding_id,
                    "kind": "still_present",
                    "evidence": [f"The {finding_id} failure remains."],
                    "closure_condition": None,
                }
            )
        partial = self.reduce(assessment, answered)["envelope"]

        next_answer = self.author_event(partial, "fix", revision="revision-3")
        for finding_id in ("F-002", "F-003"):
            next_answer["responses"].append(
                {
                    "finding_id": finding_id,
                    "kind": "fix",
                    "evidence": [f"The {finding_id} correction is in revision-3."],
                    "tradeoff": None,
                }
            )
        revalidated = self.reduce(next_answer, partial)["envelope"]
        next_assessment = self.review_event(
            revalidated,
            "still_present",
            round_number=3,
            evidence=["The first failure has returned in revision-3."],
        )
        for finding_id in ("F-002", "F-003"):
            next_assessment["responses"].append(
                {
                    "finding_id": finding_id,
                    "kind": "resolve",
                    "evidence": [f"The {finding_id} failure is corrected."],
                    "closure_condition": None,
                }
            )

        continued = self.reduce(next_assessment, revalidated)

        self.assertEqual("awaiting_author", continued["envelope"]["state"]["phase"])
        self.assertEqual("required_findings", continued["decision"]["reason"])
        self.assertEqual(1, continued["decision"]["required_remaining"])

    def test_changed_issue_plan_revalidates_closed_sibling_findings(self) -> None:
        second = self.finding("F-002")
        second["location"] = "plan:second boundary"
        second["impact"] = "The second boundary is incomplete."
        second["evidence"] = ["The second boundary has no migration step."]
        initial_event = self.initial_event(findings=[self.finding(), second])
        initial_event["surface"] = "issue"
        initial = self.reduce(initial_event)["envelope"]

        first_answer = self.author_event(
            initial,
            "fix",
            revision=initial["state"]["artifact_binding"]["revision"],
        )
        first_answer["artifact_binding"]["sha256"] = HEX_C
        first_answer["responses"].append(
            {
                "finding_id": "F-002",
                "kind": "fix",
                "evidence": ["The plan adds the second migration step."],
                "tradeoff": None,
            }
        )
        answered = self.reduce(first_answer, initial)["envelope"]
        assessment = self.review_event(answered, "resolve")
        assessment["responses"].append(
            {
                "finding_id": "F-002",
                "kind": "still_present",
                "evidence": ["The second rollback step is still absent."],
                "closure_condition": None,
            }
        )
        partial = self.reduce(assessment, answered)["envelope"]

        missing_revalidation = self.author_event(
            partial,
            "fix",
            revision=partial["state"]["artifact_binding"]["revision"],
        )
        missing_revalidation["artifact_binding"]["sha256"] = HEX_A
        missing_revalidation["responses"][0]["finding_id"] = "F-002"
        with self.assertRaises(self.exchange.ProtocolError):
            self.reduce(missing_revalidation, partial)

        complete_answer = copy.deepcopy(missing_revalidation)
        complete_answer["responses"].insert(
            0,
            {
                "finding_id": "F-001",
                "kind": "fix",
                "evidence": ["The first boundary remains complete in the new plan."],
                "tradeoff": None,
            },
        )
        revalidated = self.reduce(complete_answer, partial)["envelope"]

        self.assertEqual("awaiting_reviewer", revalidated["state"]["phase"])
        self.assertEqual(
            ["answered_fix", "answered_fix"],
            [finding["state"] for finding in revalidated["state"]["findings"]],
        )
        self.assertEqual(
            ["F-001", "F-002"],
            [finding["id"] for finding in revalidated["state"]["findings"]],
        )

    def test_artifact_refresh_requires_a_new_pr_revision_and_complete_answers(
        self,
    ) -> None:
        answered = self.answered_state()
        evidence = self.reduce(
            self.initial_event(findings=[], coverage_complete=False)
        )["envelope"]
        issue_event = self.initial_event(findings=[], coverage_complete=False)
        issue_event["surface"] = "issue"
        issue = self.reduce(issue_event)["envelope"]
        complete = self.reduce(self.initial_event(findings=[]))["envelope"]

        same_head_answer = self.author_event(
            answered,
            "fix",
            revision=answered["state"]["artifact_binding"]["revision"],
        )
        same_head_answer["artifact_binding"]["sha256"] = HEX_C
        missing_answer = self.author_event(answered, "fix", revision="revision-3")
        missing_answer["responses"] = []
        unexpected_answer = self.author_event(evidence, "fix", revision="revision-2")
        issue_refresh = self.author_event(issue, "fix", revision="revision-2")
        issue_refresh["responses"] = []
        go_refresh = self.author_event(complete, "fix", revision="revision-2")
        go_refresh["responses"] = []

        cases = (
            ("same head", same_head_answer, answered),
            ("missing active answer", missing_answer, answered),
            ("unexpected answer", unexpected_answer, evidence),
            ("issue refresh", issue_refresh, issue),
            ("terminal GO", go_refresh, complete),
        )
        for label, event, previous in cases:
            with (
                self.subTest(case=label),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.reduce(event, previous)

    def test_artifact_refresh_keeps_the_five_assessment_limit(self) -> None:
        state = self.reduce(
            self.initial_event(findings=[], coverage_complete=False, go_eligible=False)
        )["envelope"]
        for round_number in (2, 3):
            review = self.review_event(
                state,
                "resolve",
                round_number=round_number,
                coverage_complete=False,
                go_eligible=False,
            )
            review["responses"] = []
            state = self.reduce(review, state)["envelope"]
        conditional_review = self.review_event(
            state,
            "resolve",
            round_number=4,
            go_eligible=False,
        )
        conditional_review["responses"] = []
        conditional = self.reduce(conditional_review, state)["envelope"]

        refresh = self.author_event(conditional, "fix", revision="revision-5")
        refresh["responses"] = []
        refreshed = self.reduce(refresh, conditional)["envelope"]

        self.assertEqual(4, refreshed["state"]["round"])
        self.assertEqual(4, len(refreshed["state"]["progress"]))
        final_review = self.review_event(
            refreshed,
            "resolve",
            round_number=5,
            go_eligible=True,
        )
        final_review["responses"] = []
        complete = self.reduce(final_review, refreshed)["envelope"]
        self.assertEqual("GO", complete["state"]["verdict"])
        self.assertEqual(5, complete["state"]["round"])

        after_go = self.author_event(complete, "fix", revision="revision-6")
        after_go["responses"] = []
        with self.assertRaises(self.exchange.ProtocolError):
            self.reduce(after_go, complete)

        sixth = self.review_event(
            complete,
            "resolve",
            round_number=6,
            go_eligible=True,
        )
        sixth["responses"] = []
        with self.assertRaises(self.exchange.ProtocolError):
            self.reduce(sixth, complete)

    def test_artifact_refresh_cannot_continue_a_decision_required_state(self) -> None:
        state = self.reduce(self.initial_event(findings=[], coverage_complete=False))[
            "envelope"
        ]
        for round_number in range(2, 6):
            review = self.review_event(
                state,
                "resolve",
                round_number=round_number,
                coverage_complete=False,
            )
            review["responses"] = []
            state = self.reduce(review, state)["envelope"]
        self.assertEqual("decision_required", state["state"]["phase"])

        refresh = self.author_event(state, "fix", revision="revision-6")
        refresh["responses"] = []
        with self.assertRaises(self.exchange.ProtocolError):
            self.reduce(refresh, state)

    def test_pull_request_fix_requires_a_new_head_revision(self) -> None:
        for kind in ("fix", "fix_with_tradeoff"):
            prior = self.initial_state()
            event = self.author_event(prior, kind, revision="revision-1")
            event["artifact_binding"]["sha256"] = HEX_C
            with (
                self.subTest(surface="pull_request", kind=kind),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.reduce(event, prior)

        issue_event = self.initial_event()
        issue_event["surface"] = "issue"
        issue_prior = self.reduce(issue_event)["envelope"]
        issue_fix = self.author_event(issue_prior, "fix", revision="revision-1")
        issue_fix["artifact_binding"]["sha256"] = HEX_C

        result = self.reduce(issue_fix, issue_prior)

        self.assertEqual("accepted", result["status"])

    def test_reviewer_fix_response_table(self) -> None:
        cases = (
            ("resolve", "resolved", "complete"),
            ("partial", "partial", "awaiting_author"),
            ("still_present", "still_present", "awaiting_author"),
            ("withdraw", "withdrawn", "complete"),
            ("escalate", "escalated", "decision_required"),
        )
        for action, expected_state, expected_phase in cases:
            prior = self.answered_state()
            with self.subTest(action=action):
                result = self.reduce(self.review_event(prior, action), prior)
                state = result["envelope"]["state"]
                self.assertEqual(expected_state, state["findings"][0]["state"])
                self.assertEqual(expected_phase, state["phase"])
                self.assertEqual(2, state["round"])

    def test_reviewer_contest_response_table(self) -> None:
        cases = (
            ("accept", "withdrawn", "complete", None),
            (
                "counter",
                "countered",
                "awaiting_author",
                "A regression test must cover both branches.",
            ),
            ("refute", "still_present", "awaiting_author", None),
            ("escalate", "escalated", "decision_required", None),
        )
        for action, expected_state, expected_phase, condition in cases:
            prior = self.answered_state("contest")
            evidence = ["New runtime evidence contradicts the contest."]
            with self.subTest(action=action):
                event = self.review_event(
                    prior,
                    action,
                    evidence=evidence,
                    closure_condition=condition,
                )
                state = self.reduce(event, prior)["envelope"]["state"]
                self.assertEqual(expected_state, state["findings"][0]["state"])
                self.assertEqual(expected_phase, state["phase"])
                if action == "counter":
                    self.assertEqual(
                        condition, state["findings"][0]["closure_condition"]
                    )

    def test_contest_response_requires_evidence_new_to_both_parties(self) -> None:
        initial = self.initial_state()
        contested = self.reduce(self.author_event(initial, "contest"), initial)[
            "envelope"
        ]
        author_evidence = contested["state"]["findings"][0]["author_response"][
            "evidence"
        ]

        for action in ("counter", "refute"):
            event = self.review_event(
                contested,
                action,
                evidence=author_evidence,
                closure_condition=(
                    "The selected behavior must cover both branches."
                    if action == "counter"
                    else None
                ),
            )
            with (
                self.subTest(action=action),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.reduce(event, contested)

    def test_illegal_transition_table_is_rejected(self) -> None:
        cases: list[tuple[str, dict[str, Any], dict[str, Any] | None]] = []
        initial = self.initial_state()
        incomplete = self.author_event(initial, "fix")
        incomplete["responses"] = []
        cases.append(("incomplete author coverage", incomplete, initial))

        answered = self.answered_state()
        wrong_review = self.review_event(answered, "accept")
        cases.append(("contest action after fix", wrong_review, answered))

        contested = self.answered_state("contest")
        bare = self.review_event(
            contested,
            "refute",
            evidence=["The failing case returns 0."],
        )
        cases.append(("bare restatement", bare, contested))

        stale = self.author_event(initial, "fix")
        stale["prior_state_sha256"] = HEX_A
        cases.append(("stale prior state", stale, initial))

        skipped = self.review_event(answered, "resolve", round_number=3)
        cases.append(("skipped round", skipped, answered))

        terminal = self.reduce(self.initial_event(findings=[]))["envelope"]
        after_terminal = self.review_event(terminal, "resolve")
        after_terminal["responses"] = []
        cases.append(("terminal transition", after_terminal, terminal))

        for label, event, previous in cases:
            with (
                self.subTest(label=label),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.reduce(event, previous)

    def test_late_finding_policy_distinguishes_required_and_follow_up(self) -> None:
        corrected = self.finding("F-002", introduction="introduced_by_correction")
        corrected["location"] = "src/correction.py:9"
        newly_evidenced = self.finding("F-002", introduction="new_evidence")
        newly_evidenced["location"] = "src/evidence.py:11"
        newly_evidenced["evidence"] = ["A new failing trace identifies this defect."]
        missed = self.finding("F-002", introduction="missed_high_risk")
        missed["location"] = "src/missed.py:13"
        allowed = (
            corrected,
            newly_evidenced,
            missed,
        )
        for finding in allowed:
            prior = self.answered_state()
            event = self.review_event(prior, "resolve", findings=[finding])
            with self.subTest(introduction=finding["introduction"]):
                state = self.reduce(event, prior)["envelope"]["state"]
                self.assertEqual("F-002", state["findings"][1]["id"])
                self.assertEqual("open", state["findings"][1]["state"])

        prior = self.answered_state()
        invalid = self.finding(
            "F-002",
            severity="minor",
            introduction="missed_high_risk",
        )
        with self.assertRaises(self.exchange.ProtocolError):
            self.reduce(self.review_event(prior, "resolve", findings=[invalid]), prior)

        follow_up = self.finding(
            "F-002",
            severity="minor",
            disposition="suggestion",
            introduction="nonblocking_follow_up",
        )
        follow_up["location"] = "src/follow_up.py:21"
        follow_up["impact"] = "The diagnostic can be clearer."
        follow_up["evidence"] = ["A low-risk diagnostic omits the field name."]
        state = self.reduce(
            self.review_event(prior, "resolve", findings=[follow_up]), prior
        )["envelope"]["state"]
        self.assertEqual("nonblocking", state["findings"][1]["state"])
        self.assertEqual("GO", state["verdict"])

    def test_late_security_and_correctness_bases_are_required(self) -> None:
        for introduction in ("missed_security", "missed_correctness"):
            prior = self.answered_state()
            finding = self.finding("F-002", severity="minor", introduction=introduction)
            finding["location"] = f"src/{introduction}.py:17"
            finding["impact"] = f"The {introduction} defect remains."
            finding["evidence"] = [f"New {introduction} evidence is available."]

            with self.subTest(introduction=introduction):
                state = self.reduce(
                    self.review_event(prior, "resolve", findings=[finding]), prior
                )["envelope"]["state"]
                self.assertEqual(introduction, state["findings"][1]["introduction"])
                self.assertEqual("required", state["findings"][1]["disposition"])

                nonblocking = {**finding, "disposition": "suggestion"}
                nonblocking["closure_condition"] = None
                with self.assertRaises(self.exchange.ProtocolError):
                    self.reduce(
                        self.review_event(prior, "resolve", findings=[nonblocking]),
                        prior,
                    )

    def test_late_finding_cannot_relabel_old_evidence_or_claim_no_correction(
        self,
    ) -> None:
        initial = self.initial_state()
        contested = self.reduce(self.author_event(initial, "contest"), initial)[
            "envelope"
        ]
        duplicate = self.finding("F-002", introduction="new_evidence")
        no_new_evidence = self.finding("F-002", introduction="new_evidence")
        no_new_evidence["location"] = "src/other.py:12"
        no_new_evidence["impact"] = "A second result can be incorrect."
        claimed_correction = self.finding(
            "F-002", introduction="introduced_by_correction"
        )
        claimed_correction["location"] = "src/other.py:12"

        cases = (
            ("duplicate identity", duplicate),
            ("old evidence", no_new_evidence),
            ("no correction", claimed_correction),
        )
        for label, finding in cases:
            event = self.review_event(
                contested,
                "accept",
                evidence=["The contest is accepted."],
                findings=[finding],
            )
            with (
                self.subTest(label=label),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.reduce(event, contested)

        first = self.finding("F-002", introduction="new_evidence")
        first["location"] = "src/new_trace.py:8"
        first["evidence"] = ["A newly available trace shows the failure."]
        second = {**first, "id": "F-003"}
        duplicate_batch = self.review_event(
            contested,
            "accept",
            evidence=["The contest is accepted."],
            findings=[first, second],
        )
        with self.assertRaises(self.exchange.ProtocolError):
            self.reduce(duplicate_batch, contested)

    def test_correction_provenance_survives_a_resolved_evidence_gap(self) -> None:
        answered = self.answered_state("fix")
        evidence_gap_event = self.review_event(
            answered,
            "resolve",
            coverage_complete=False,
        )
        evidence_gap = self.reduce(evidence_gap_event, answered)["envelope"]
        self.assertEqual("awaiting_evidence", evidence_gap["state"]["phase"])

        late = self.finding("F-002", introduction="introduced_by_correction")
        late["location"] = "src/correction.py:19"
        late["impact"] = "The correction exposes a second invalid result."
        late["evidence"] = ["The corrected path now reaches the invalid branch."]
        reassessment = self.review_event(
            evidence_gap,
            "resolve",
            round_number=3,
            findings=[late],
        )
        reassessment["responses"] = []

        result = self.reduce(reassessment, evidence_gap)["envelope"]

        self.assertEqual(
            ["F-001", "F-002"],
            [finding["id"] for finding in result["state"]["findings"]],
        )
        self.assertEqual(
            "introduced_by_correction",
            result["state"]["findings"][1]["introduction"],
        )

    def test_duplicate_nonsequential_and_excess_finding_ids_are_rejected(self) -> None:
        cases = (
            [self.finding(), self.finding()],
            [self.finding("F-002")],
            [self.finding(f"F-{number:03d}") for number in range(1, 102)],
        )
        for findings in cases:
            with (
                self.subTest(count=len(findings)),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.reduce(self.initial_event(findings=findings))

    def test_scope_growth_without_progress_stops_early(self) -> None:
        initial = self.initial_state()
        author = self.author_event(
            initial,
            "fix",
            scope=["path:src/example.py", "module:new-boundary"],
        )
        author["scope_change_reason"] = "The correction needs the shared boundary."
        answered = self.reduce(author, initial)["envelope"]

        result = self.reduce(self.review_event(answered, "still_present"), answered)

        self.assertEqual("decision_required", result["envelope"]["state"]["phase"])
        self.assertEqual("human_decision", result["envelope"]["state"]["next_action"])
        self.assertEqual("scope_growth_without_progress", result["decision"]["reason"])

    def test_zero_finding_scope_growth_after_refresh_can_complete(self) -> None:
        cases = (
            (
                "awaiting evidence",
                self.reduce(self.initial_event(findings=[], coverage_complete=False))[
                    "envelope"
                ],
            ),
            (
                "conditional complete",
                self.reduce(self.initial_event(findings=[], go_eligible=False))[
                    "envelope"
                ],
            ),
        )
        for label, previous in cases:
            refresh = self.author_event(
                previous,
                "fix",
                revision="revision-scope-growth",
                scope=["module:new-boundary", "path:src/example.py"],
            )
            refresh["scope_change_reason"] = "The changed head adds one review target."
            refresh["responses"] = []
            refreshed = self.reduce(refresh, previous)["envelope"]
            review = self.review_event(
                refreshed,
                "resolve",
                round_number=2,
                go_eligible=True,
            )
            review["responses"] = []

            with self.subTest(state=label):
                result = self.reduce(review, refreshed)
                self.assertEqual("complete", result["envelope"]["state"]["phase"])
                self.assertEqual("GO", result["envelope"]["state"]["verdict"])
                self.assertEqual("complete", result["decision"]["reason"])

    def test_evidence_merges_use_constant_time_membership_and_keep_order(self) -> None:
        class MeasuredEvidence(list[str]):
            membership_work = 0

            def __contains__(self, value: object) -> bool:
                type(self).membership_work += len(self)
                return super().__contains__(value)

        existing = [f"prior evidence {index}" for index in range(2_000)]
        additions = [
            *existing[-200:],
            *(f"new evidence {index}" for index in range(500)),
        ]
        expected = [*existing, *(f"new evidence {index}" for index in range(500))]

        initial = self.initial_state()
        initial["state"]["findings"][0]["evidence"] = MeasuredEvidence(existing)
        author = self.author_event(initial, "fix")
        author["responses"][0]["evidence"] = additions
        normalized_author = self.exchange._continued_author_event(author)
        author_state, _record, _reason = self.exchange._author_reduce(
            initial["state"],
            normalized_author,
            HEX_A,
        )

        self.assertEqual(0, MeasuredEvidence.membership_work)
        self.assertEqual(expected, author_state["findings"][0]["evidence"])

        MeasuredEvidence.membership_work = 0
        finding = self.answered_state()["state"]["findings"][0]
        finding["evidence"] = MeasuredEvidence(existing)
        self.exchange._apply_reviewer_response(
            finding,
            {
                "kind": "resolve",
                "evidence": additions,
                "closure_condition": None,
            },
            2,
        )

        self.assertEqual(0, MeasuredEvidence.membership_work)
        self.assertEqual(expected, finding["evidence"])

    def test_scope_target_replacement_without_progress_stops_early(self) -> None:
        initial_result = self.reduce(
            {
                **self.initial_event(),
                "scope": ["path:src/example.py", "module:old-boundary"],
            }
        )
        initial = initial_result["envelope"]
        author = self.author_event(
            initial,
            "fix",
            scope=["path:src/example.py", "module:new-boundary"],
        )
        author["scope_change_reason"] = "The correction replaces one boundary."
        answered = self.reduce(author, initial)["envelope"]

        result = self.reduce(self.review_event(answered, "still_present"), answered)

        self.assertEqual("decision_required", result["envelope"]["state"]["phase"])
        self.assertEqual("scope_growth_without_progress", result["decision"]["reason"])
        self.assertEqual(
            ["module:old-boundary", "path:src/example.py"],
            result["envelope"]["state"]["progress"][0]["scope"],
        )

    def test_round_five_can_go_but_cannot_continue(self) -> None:
        state = self.initial_state()
        for round_number in range(2, 5):
            answered = self.reduce(self.author_event(state, "fix"), state)["envelope"]
            state = self.reduce(
                self.review_event(answered, "still_present", round_number=round_number),
                answered,
            )["envelope"]

        answered = self.reduce(self.author_event(state, "fix"), state)["envelope"]
        failed = self.reduce(
            self.review_event(answered, "still_present", round_number=5), answered
        )
        self.assertEqual("decision_required", failed["envelope"]["state"]["phase"])
        self.assertEqual("review_limit", failed["decision"]["reason"])

        state = self.initial_state()
        for round_number in range(2, 5):
            answered = self.reduce(self.author_event(state, "fix"), state)["envelope"]
            state = self.reduce(
                self.review_event(answered, "still_present", round_number=round_number),
                answered,
            )["envelope"]
        answered = self.reduce(self.author_event(state, "fix"), state)["envelope"]
        passed = self.reduce(
            self.review_event(answered, "resolve", round_number=5), answered
        )
        self.assertEqual("GO", passed["envelope"]["state"]["verdict"])

    def test_exact_event_replay_is_idempotent(self) -> None:
        prior = self.initial_state()
        event = self.author_event(prior, "fix")
        first = self.reduce(event, prior)
        replay = self.reduce(event, first["envelope"])

        self.assertEqual("replayed", replay["status"])
        self.assertEqual(first["envelope"], replay["envelope"])

    def test_initial_reviewer_event_replay_is_idempotent(self) -> None:
        event = self.initial_event()
        first = self.reduce(event)

        replay = self.reduce(event, first["envelope"])

        self.assertEqual("replayed", replay["status"])
        self.assertEqual(first["envelope"], replay["envelope"])

    def test_corrective_reviewer_event_with_late_finding_replays(self) -> None:
        answered = self.answered_state()
        late = self.finding("F-002", introduction="introduced_by_correction")
        late["location"] = "src/correction.py:19"
        late["impact"] = "The correction exposes a second invalid result."
        late["evidence"] = ["The corrected path now reaches the invalid branch."]
        event = self.review_event(answered, "resolve", findings=[late])
        first = self.reduce(event, answered)

        replay = self.reduce(event, first["envelope"])

        self.assertEqual("replayed", replay["status"])
        self.assertEqual(first["envelope"], replay["envelope"])

    def test_human_event_replay_is_idempotent(self) -> None:
        prior = self.answered_state("risk_acceptance")
        event = self.human_event(prior, "accept_risk")
        first = self.reduce(event, prior)

        replay = self.reduce(event, first["envelope"])

        self.assertEqual("replayed", replay["status"])
        self.assertEqual(first["envelope"], replay["envelope"])

    def test_reframe_event_replay_is_idempotent(self) -> None:
        prior = self.reduce(self.initial_event(stop_reason="requirements_reframe"))[
            "envelope"
        ]
        event = self.reframe_event(prior)
        first = self.reduce(event, prior)

        replay = self.reduce(event, first["envelope"])

        self.assertEqual("replayed", replay["status"])
        self.assertEqual(first["envelope"], replay["envelope"])

    def test_state_carries_and_replays_its_complete_event_history(self) -> None:
        initial_event = self.initial_event()
        initial = self.reduce(initial_event)["envelope"]
        author_event = self.author_event(initial, "fix")
        answered = self.reduce(author_event, initial)["envelope"]
        reviewer_event = self.review_event(answered, "resolve")
        completed = self.reduce(reviewer_event, answered)["envelope"]

        history = completed["state"].get("accepted_events")
        self.assertIsInstance(history, list)
        assert isinstance(history, list)
        self.assertEqual(3, len(history))
        self.assertEqual(
            ["reviewer_assessment", "author_response", "reviewer_assessment"],
            [event["event_type"] for event in history],
        )
        self.assertEqual(completed, self.exchange.verify_envelope(completed))

        forged_final = copy.deepcopy(completed)
        forged_final["state"]["prior_state_sha256"] = HEX_A
        forged_final["state_sha256"] = self.exchange.sha256_json(forged_final["state"])
        with self.assertRaises(self.exchange.ProtocolError):
            self.exchange.verify_envelope(forged_final)

        forged_intermediate = copy.deepcopy(completed)
        forged_intermediate["state"]["accepted_events"][1]["prior_state_sha256"] = HEX_A
        forged_intermediate["state_sha256"] = self.exchange.sha256_json(
            forged_intermediate["state"]
        )
        with self.assertRaises(self.exchange.ProtocolError):
            self.exchange.verify_envelope(forged_intermediate)

        oversized = copy.deepcopy(completed)
        oversized["state"]["accepted_events"] = [history[0]] * (
            self.exchange.MAX_ACCEPTED_EVENTS + 1
        )
        oversized["state_sha256"] = self.exchange.sha256_json(oversized["state"])
        with self.assertRaises(self.exchange.ProtocolError):
            self.exchange.verify_envelope(oversized)

    def test_malformed_artifact_in_conditional_history_is_a_protocol_error(
        self,
    ) -> None:
        conditional = self.reduce(self.initial_event(findings=[], go_eligible=False))[
            "envelope"
        ]
        malformed_event = self.author_event(
            conditional,
            "fix",
            revision="revision-2",
        )
        malformed_event["responses"] = []
        malformed_event["artifact_binding"] = 7
        forged = copy.deepcopy(conditional)
        forged["state"]["accepted_events"].append(malformed_event)
        forged["state_sha256"] = self.exchange.sha256_json(forged["state"])

        with self.assertRaises(self.exchange.ProtocolError):
            self.exchange.verify_envelope(forged)

    def test_authoritative_risk_acceptance_does_not_add_a_round(self) -> None:
        initial = self.initial_state()
        response = self.author_event(initial, "risk_acceptance", revision="revision-1")
        response["artifact_binding"]["visible_content_sha256"] = HEX_B
        state = self.reduce(response, initial)["envelope"]
        event = self.human_event(state, "accept_risk")

        result = self.reduce(event, state)

        self.assertEqual(1, result["envelope"]["state"]["round"])
        self.assertEqual(
            "accepted_risk", result["envelope"]["state"]["findings"][0]["state"]
        )
        self.assertEqual("GO", result["envelope"]["state"]["verdict"])

    def test_risk_acceptance_invalidates_coverage_after_artifact_or_scope_change(
        self,
    ) -> None:
        def changed_revision(event: dict[str, Any]) -> None:
            del event

        def changed_digest(event: dict[str, Any]) -> None:
            event["artifact_binding"] = self.artifact("revision-1")
            event["artifact_binding"]["sha256"] = HEX_A

        def changed_scope(event: dict[str, Any]) -> None:
            event["artifact_binding"] = self.artifact("revision-1")
            event["scope"] = ["path:src/example.py", "path:src/second.py"]
            event["scope_change_reason"] = "The accepted risk includes a second path."

        cases = (
            ("artifact revision", changed_revision),
            ("artifact digest", changed_digest),
            ("scope", changed_scope),
        )
        for label, change in cases:
            initial = self.initial_state()
            event = self.author_event(initial, "risk_acceptance")
            change(event)

            answered = self.reduce(event, initial)["envelope"]
            accepted = self.reduce(self.human_event(answered, "accept_risk"), answered)[
                "envelope"
            ]

            with self.subTest(label=label):
                self.assertFalse(answered["state"]["coverage_complete"])
                self.assertEqual("awaiting_evidence", accepted["state"]["phase"])
                self.assertEqual("NO-GO", accepted["state"]["verdict"])

    def test_authority_can_close_escalated_risk_but_cannot_resume_round_five(
        self,
    ) -> None:
        requested = self.answered_state("risk_acceptance")
        escalated = self.reduce(self.review_event(requested, "escalate"), requested)[
            "envelope"
        ]

        accepted = self.reduce(self.human_event(escalated, "accept_risk"), escalated)[
            "envelope"
        ]

        self.assertEqual("complete", accepted["state"]["phase"])
        self.assertEqual(2, accepted["state"]["round"])

        state = self.initial_state()
        for round_number in range(2, 6):
            answered = self.reduce(self.author_event(state, "fix"), state)["envelope"]
            state = self.reduce(
                self.review_event(answered, "still_present", round_number=round_number),
                answered,
            )["envelope"]
        with self.assertRaises(self.exchange.ProtocolError):
            self.reduce(
                self.human_event(
                    state,
                    "select_closure",
                    closure_condition="A human-selected closure condition.",
                ),
                state,
            )

    def test_selected_closure_authority_persists_through_resolution(self) -> None:
        decision_required = self.reduce(
            self.initial_event(stop_reason="closure_conflict")
        )["envelope"]
        selected = self.reduce(
            self.human_event(
                decision_required,
                "select_closure",
                closure_condition="The human-selected behavior returns 1.",
            ),
            decision_required,
        )["envelope"]

        answered = self.reduce(self.author_event(selected, "fix"), selected)["envelope"]
        resolved = self.reduce(self.review_event(answered, "resolve"), answered)[
            "envelope"
        ]

        for envelope in (selected, answered, resolved):
            with self.subTest(state=envelope["state"]["findings"][0]["state"]):
                finding = envelope["state"]["findings"][0]
                self.assertEqual(2, finding["closure_revision"])
                self.assertIsNotNone(finding["authority_receipt"])
                self.assertEqual(envelope, self.exchange.verify_envelope(envelope))

    def test_human_decision_preserves_artifact_identity(self) -> None:
        state = self.answered_state("risk_acceptance")
        changed_visible = copy.deepcopy(self.human_event(state, "accept_risk"))
        changed_visible["artifact_binding"]["visible_content_sha256"] = HEX_C

        result = self.reduce(changed_visible, state)["envelope"]

        self.assertEqual(
            HEX_C,
            result["state"]["artifact_binding"]["visible_content_sha256"],
        )

        changed_artifact = copy.deepcopy(self.human_event(state, "accept_risk"))
        changed_artifact["artifact_binding"]["revision"] = "different-revision"
        with self.assertRaises(self.exchange.ProtocolError):
            self.reduce(changed_artifact, state)

    def test_human_decision_rejects_terminal_findings_in_a_mixed_state(self) -> None:
        first = self.finding("F-001")
        second = self.finding("F-002")
        second["location"] = "src/other.py:9"
        second["impact"] = "A second result can be incorrect."
        second["evidence"] = ["The second failing case returns 0."]
        initial = self.reduce(self.initial_event(findings=[first, second]))["envelope"]

        def answer_pair(first_kind: str) -> dict[str, Any]:
            event = self.author_event(initial, first_kind)
            event["responses"].append(
                {
                    "finding_id": "F-002",
                    "kind": "fix",
                    "evidence": ["The second correction is in revision-2."],
                    "tradeoff": None,
                }
            )
            return cast(dict[str, Any], self.reduce(event, initial)["envelope"])

        risk_answered = answer_pair("risk_acceptance")
        withdrawn_event = self.review_event(risk_answered, "withdraw")
        withdrawn_event["responses"].append(
            {
                "finding_id": "F-002",
                "kind": "still_present",
                "evidence": ["The second defect remains."],
                "closure_condition": None,
            }
        )
        withdrawn = self.reduce(withdrawn_event, risk_answered)["envelope"]
        accepted = self.reduce(
            self.human_event(risk_answered, "accept_risk"), risk_answered
        )["envelope"]

        fix_answered = answer_pair("fix")
        resolved_event = self.review_event(fix_answered, "resolve")
        resolved_event["responses"].append(
            {
                "finding_id": "F-002",
                "kind": "still_present",
                "evidence": ["The second defect remains."],
                "closure_condition": None,
            }
        )
        resolved = self.reduce(resolved_event, fix_answered)["envelope"]

        for state_name, state in (
            ("withdrawn", withdrawn),
            ("resolved", resolved),
            ("accepted_risk", accepted),
        ):
            for decision in ("accept_risk", "select_closure"):
                event = self.human_event(
                    state,
                    decision,
                    closure_condition=(
                        "A replacement terminal closure."
                        if decision == "select_closure"
                        else None
                    ),
                )
                with (
                    self.subTest(state=state_name, decision=decision),
                    self.assertRaises(self.exchange.ProtocolError),
                ):
                    self.reduce(event, state)

    def test_human_decision_resumes_the_remaining_response_role(self) -> None:
        first = self.finding("F-001")
        second = self.finding("F-002")
        second["location"] = "src/other.py:9"
        second["impact"] = "A second result can be incorrect."
        second["evidence"] = ["The second failing case returns 0."]

        conflicted = self.reduce(
            self.initial_event(findings=[first, second], stop_reason="closure_conflict")
        )["envelope"]
        selected = self.reduce(
            self.human_event(
                conflicted,
                "select_closure",
                closure_condition="The selected first closure.",
            ),
            conflicted,
        )["envelope"]
        self.assertEqual("awaiting_author", selected["state"]["phase"])
        self.assertEqual("author_response", selected["state"]["next_action"])

        reviewable = self.reduce(self.initial_event(findings=[first, second]))[
            "envelope"
        ]
        answered = self.author_event(reviewable, "risk_acceptance")
        answered["responses"].append(
            {
                "finding_id": "F-002",
                "kind": "fix",
                "evidence": ["The second correction is in revision-2."],
                "tradeoff": None,
            }
        )
        awaiting_reviewer = self.reduce(answered, reviewable)["envelope"]
        accepted = self.reduce(
            self.human_event(awaiting_reviewer, "accept_risk"),
            awaiting_reviewer,
        )["envelope"]
        self.assertEqual("awaiting_reviewer", accepted["state"]["phase"])
        self.assertEqual("review_assessment", accepted["state"]["next_action"])

        review = self.review_event(awaiting_reviewer, "escalate")
        review["responses"].append(
            {
                "finding_id": "F-002",
                "kind": "still_present",
                "evidence": ["The second defect remains."],
                "closure_condition": None,
            }
        )
        escalated = self.reduce(review, awaiting_reviewer)["envelope"]
        selected_second = self.reduce(
            self.human_event(
                escalated,
                "select_closure",
                finding_id="F-002",
                closure_condition="The selected second closure.",
            ),
            escalated,
        )["envelope"]
        self.assertEqual("decision_required", selected_second["state"]["phase"])
        self.assertEqual("human_decision", selected_second["state"]["next_action"])

    def test_requirements_reframe_starts_a_superseding_exchange(self) -> None:
        old = self.reduce(self.initial_event(stop_reason="requirements_reframe"))[
            "envelope"
        ]
        new = self.reduce(self.reframe_event(old), old)["envelope"]

        self.assertEqual(old["state_sha256"], new["state"]["supersedes_state_sha256"])
        self.assertEqual(
            {"reference": "policy/reframe/11", "sha256": HEX_B},
            new["state"]["supersession_authority_receipt"],
        )
        self.assertEqual("exchange-8", new["state"]["exchange_id"])
        self.assertEqual(
            ["exchange-7"],
            new["state"]["accepted_events"][0]["superseded_exchange_ids"],
        )

    def test_reframe_ancestry_is_exact_and_exchange_ids_are_never_reused(self) -> None:
        first = self.reduce(self.initial_event(stop_reason="requirements_reframe"))[
            "envelope"
        ]
        second_event = self.reframe_event(first)
        second = self.reduce(second_event, first)["envelope"]
        third_event = self.reframe_event(
            second,
            exchange_id="exchange-9",
            requirements_sha256=HEX_B,
        )
        third = self.reduce(third_event, second)["envelope"]

        self.assertEqual(
            ["exchange-7", "exchange-8"],
            third["state"]["accepted_events"][0]["superseded_exchange_ids"],
        )

        reused = self.reframe_event(
            third,
            exchange_id="exchange-7",
            requirements_sha256=HEX_C,
        )
        missing_ancestor = self.reframe_event(
            second,
            exchange_id="exchange-9",
            requirements_sha256=HEX_B,
            superseded_exchange_ids=["exchange-8"],
        )
        reordered = self.reframe_event(
            second,
            exchange_id="exchange-9",
            requirements_sha256=HEX_B,
            superseded_exchange_ids=["exchange-8", "exchange-7"],
        )
        duplicate = self.reframe_event(
            second,
            exchange_id="exchange-9",
            requirements_sha256=HEX_B,
            superseded_exchange_ids=["exchange-7", "exchange-7", "exchange-8"],
        )
        missing = self.reframe_event(
            second,
            exchange_id="exchange-9",
            requirements_sha256=HEX_B,
        )
        missing.pop("superseded_exchange_ids")

        for label, event, previous in (
            ("reused exchange", reused, third),
            ("missing ancestor", missing_ancestor, second),
            ("reordered ancestry", reordered, second),
            ("duplicate ancestry", duplicate, second),
            ("missing ancestry", missing, second),
        ):
            with (
                self.subTest(case=label),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.reduce(event, previous)

        replay = self.reduce(third_event, third)
        self.assertEqual("replayed", replay["status"])
        self.assertEqual(third, replay["envelope"])

    def test_reframe_authority_is_required_and_strictly_paired(self) -> None:
        requested = self.answered_state("fix")
        escalated = self.reduce(self.review_event(requested, "escalate"), requested)[
            "envelope"
        ]

        missing_authority = self.reframe_event(escalated)
        missing_authority.pop("authority_receipt")
        with self.assertRaises(self.exchange.ProtocolError):
            self.reduce(missing_authority, escalated)

        reframed = self.reduce(self.reframe_event(escalated), escalated)["envelope"]
        missing_stored_authority = copy.deepcopy(reframed)
        missing_stored_authority["state"]["supersession_authority_receipt"] = None
        missing_stored_authority["state_sha256"] = self.exchange.sha256_json(
            missing_stored_authority["state"]
        )
        with self.assertRaises(self.exchange.ProtocolError):
            self.exchange.verify_envelope(missing_stored_authority)

        fresh_with_authority = self.initial_state()
        fresh_with_authority["state"]["supersession_authority_receipt"] = {
            "reference": "policy/reframe/11",
            "sha256": HEX_B,
        }
        fresh_with_authority["state_sha256"] = self.exchange.sha256_json(
            fresh_with_authority["state"]
        )
        with self.assertRaises(self.exchange.ProtocolError):
            self.exchange.verify_envelope(fresh_with_authority)

    def test_authority_record_parser_and_context_are_strict(self) -> None:
        parser = self.exchange.parse_authority_record
        verifier = self.exchange.verify_authority_record
        self.assertTrue(callable(parser))
        self.assertTrue(callable(verifier))
        decisions = [
            {
                "finding_id": "F-001",
                "kind": "accept_risk",
                "closure_condition": None,
            }
        ]
        expected = self.authority_record(
            "human_decision",
            prior_state_sha256=HEX_B,
            decisions=decisions,
        )
        body = self.exchange.canonical_json(expected)
        receipt = self.authority_receipt(body)

        self.assertEqual(expected, parser(body))
        self.assertEqual(expected, verifier(body, receipt, expected))

        invalid_record = {**expected, "unexpected": True}
        invalid_bodies = (
            json.dumps(expected),
            self.exchange.canonical_json(invalid_record),
            body + "\n",
        )
        for invalid_body in invalid_bodies:
            with (
                self.subTest(invalid_body=invalid_body[-40:]),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                parser(invalid_body)

        context_changes: list[tuple[str, dict[str, Any]]] = []
        other_target = copy.deepcopy(expected)
        other_target["target"] = {**expected["target"], "number": 8}
        context_changes.append(("target", other_target))
        context_changes.append(("exchange", {**expected, "exchange_id": "exchange-8"}))
        other_finding = copy.deepcopy(expected)
        other_finding["decisions"][0]["finding_id"] = "F-002"
        context_changes.append(("finding", other_finding))
        context_changes.append(
            (
                "action",
                self.authority_record(
                    "reframe",
                    exchange_id="exchange-8",
                    requirements_sha256=HEX_A,
                    prior_state_sha256=None,
                    supersedes_state_sha256=HEX_C,
                ),
            )
        )
        for label, changed in context_changes:
            changed_body = self.exchange.canonical_json(changed)
            with (
                self.subTest(label=label),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                verifier(changed_body, self.authority_receipt(changed_body), expected)

        with self.assertRaises(self.exchange.ProtocolError):
            verifier(body, {**receipt, "sha256": HEX_A}, expected)

    def test_authority_record_matches_human_and_reframe_events(self) -> None:
        verifier = self.exchange.verify_authority_record_for_event
        state_verifier = self.exchange.verify_authority_record_for_state
        self.assertTrue(callable(verifier))
        self.assertTrue(callable(state_verifier))

        prior = self.answered_state("risk_acceptance")
        human = self.human_event(prior, "accept_risk")
        human_record = self.authority_record(
            "human_decision",
            target=prior["state"]["target"],
            exchange_id=prior["state"]["exchange_id"],
            requirements_sha256=prior["state"]["requirements_sha256"],
            prior_state_sha256=prior["state_sha256"],
            decisions=human["decisions"],
        )
        human_body = self.exchange.canonical_json(human_record)
        human["authority_receipt"] = self.authority_receipt(human_body)
        human_result = self.reduce(human, prior)["envelope"]

        self.assertEqual(
            human_record,
            verifier(human_body, human["authority_receipt"], human, human_result),
        )
        self.assertEqual(
            human_record,
            state_verifier(
                human_body,
                human["authority_receipt"],
                human_result,
            ),
        )

        old = self.reduce(self.initial_event(stop_reason="requirements_reframe"))[
            "envelope"
        ]
        reframe = self.reframe_event(old)
        reframe_record = self.authority_record(
            "reframe",
            target=reframe["target"],
            exchange_id=reframe["exchange_id"],
            requirements_sha256=reframe["requirements_sha256"],
            prior_state_sha256=None,
            supersedes_state_sha256=old["state_sha256"],
        )
        reframe_body = self.exchange.canonical_json(reframe_record)
        reframe["authority_receipt"] = self.authority_receipt(reframe_body)
        reframe_result = self.reduce(reframe, old)["envelope"]

        self.assertEqual(
            reframe_record,
            verifier(
                reframe_body,
                reframe["authority_receipt"],
                reframe,
                reframe_result,
            ),
        )
        self.assertEqual(
            reframe_record,
            state_verifier(
                reframe_body,
                reframe["authority_receipt"],
                reframe_result,
            ),
        )

    def test_human_authority_record_cannot_be_reused_for_a_newer_state(self) -> None:
        first_request = self.answered_state("risk_acceptance")
        first_human = self.human_event(first_request, "accept_risk")
        record = self.authority_record(
            "human_decision",
            target=first_request["state"]["target"],
            exchange_id=first_request["state"]["exchange_id"],
            requirements_sha256=first_request["state"]["requirements_sha256"],
            prior_state_sha256=first_request["state_sha256"],
            decisions=first_human["decisions"],
        )
        body = self.exchange.canonical_json(record)
        receipt = self.authority_receipt(body)
        first_human["authority_receipt"] = receipt
        first_result = self.reduce(first_human, first_request)["envelope"]
        self.assertEqual(
            record,
            self.exchange.verify_authority_record_for_event(
                body,
                receipt,
                first_human,
                first_result,
            ),
        )

        still_present = self.reduce(
            self.review_event(first_request, "still_present"),
            first_request,
        )["envelope"]
        later_request = self.reduce(
            self.author_event(still_present, "risk_acceptance"),
            still_present,
        )["envelope"]
        later_human = self.human_event(later_request, "accept_risk")
        later_human["authority_receipt"] = receipt
        later_result = self.reduce(later_human, later_request)["envelope"]

        stale_verifiers: tuple[Callable[[], object], ...] = (
            lambda: self.exchange.verify_authority_record_for_event(
                body,
                receipt,
                later_human,
                later_result,
            ),
            lambda: self.exchange.verify_authority_record_for_state(
                body,
                receipt,
                later_result,
            ),
        )
        for verify_stale in stale_verifiers:
            with self.assertRaises(self.exchange.ProtocolError):
                verify_stale()

    def test_counter_clears_only_its_selected_closure_receipt(self) -> None:
        first = self.finding("F-001")
        second = self.finding("F-002")
        second["location"] = "src/other.py:9"
        second["impact"] = "A second result can be incorrect."
        second["evidence"] = ["The second failing case returns 0."]
        prior = self.reduce(
            self.initial_event(findings=[first, second], stop_reason="closure_conflict")
        )["envelope"]
        human = self.human_event(
            prior,
            "select_closure",
            closure_condition="The first selected closure.",
        )
        human["decisions"].append(
            {
                "finding_id": "F-002",
                "kind": "select_closure",
                "closure_condition": "The second selected closure.",
            }
        )
        record = self.authority_record(
            "human_decision",
            target=prior["state"]["target"],
            exchange_id=prior["state"]["exchange_id"],
            requirements_sha256=prior["state"]["requirements_sha256"],
            prior_state_sha256=prior["state_sha256"],
            decisions=human["decisions"],
        )
        body = self.exchange.canonical_json(record)
        receipt = self.authority_receipt(body)
        human["authority_receipt"] = receipt
        selected = self.reduce(human, prior)["envelope"]

        author = self.author_event(selected, "contest")
        author["responses"].append(
            {
                "finding_id": "F-002",
                "kind": "contest",
                "evidence": ["The second closure conflicts with the interface."],
                "tradeoff": None,
            }
        )
        contested = self.reduce(author, selected)["envelope"]
        reviewer = self.review_event(
            contested,
            "counter",
            evidence=["New evidence requires a first replacement closure."],
            closure_condition="The first countered closure.",
        )
        reviewer["responses"].append(
            {
                "finding_id": "F-002",
                "kind": "accept",
                "evidence": ["The second contest is accepted."],
                "closure_condition": None,
            }
        )
        countered = self.reduce(reviewer, contested)["envelope"]

        self.assertIsNone(countered["state"]["findings"][0]["authority_receipt"])
        self.assertEqual(
            receipt,
            countered["state"]["findings"][1]["authority_receipt"],
        )
        self.assertEqual(
            record,
            self.exchange.verify_authority_record_for_state(body, receipt, countered),
        )

        incomplete_record = self.authority_record(
            "human_decision",
            target=prior["state"]["target"],
            exchange_id=prior["state"]["exchange_id"],
            requirements_sha256=prior["state"]["requirements_sha256"],
            prior_state_sha256=prior["state_sha256"],
            decisions=[human["decisions"][0]],
        )
        incomplete_body = self.exchange.canonical_json(incomplete_record)
        incomplete_receipt = self.authority_receipt(incomplete_body)
        forged = copy.deepcopy(countered)
        forged["state"]["findings"][1]["authority_receipt"] = incomplete_receipt
        forged["state_sha256"] = self.exchange.sha256_json(forged["state"])
        with self.assertRaises(self.exchange.ProtocolError):
            self.exchange.verify_authority_record_for_state(
                incomplete_body,
                incomplete_receipt,
                forged,
            )

    def test_requirements_reframe_requires_verified_distinct_predecessor(self) -> None:
        old = self.reduce(self.initial_event(stop_reason="requirements_reframe"))[
            "envelope"
        ]
        cases: list[tuple[str, dict[str, Any], dict[str, Any] | None]] = []

        fresh_claim = self.initial_event(
            findings=[], supersedes_state_sha256=old["state_sha256"]
        )
        cases.append(("unverified supersession", fresh_claim, None))
        same_exchange = self.reframe_event(old, exchange_id="exchange-7")
        cases.append(("same exchange", same_exchange, old))
        same_requirements = self.reframe_event(old, requirements_sha256=HEX_C)
        cases.append(("same requirements", same_requirements, old))
        wrong_digest = self.reframe_event(old)
        wrong_digest["supersedes_state_sha256"] = HEX_B
        cases.append(("wrong superseded digest", wrong_digest, old))
        changed_target = self.reframe_event(old)
        changed_target["target"] = {**old["state"]["target"], "number": 8}
        cases.append(("changed target", changed_target, old))

        for label, event, previous in cases:
            with (
                self.subTest(label=label),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.reduce(event, previous)

    def test_authoritative_reframe_accepts_each_retained_exchange_phase(self) -> None:
        awaiting_author = self.initial_state()
        awaiting_reviewer = self.answered_state("fix")
        awaiting_evidence = self.reduce(
            self.initial_event(findings=[], coverage_complete=False)
        )["envelope"]
        decision_required = self.reduce(
            self.initial_event(stop_reason="requirements_reframe")
        )["envelope"]
        complete = self.reduce(self.initial_event(findings=[]))["envelope"]

        for phase, previous in (
            ("awaiting_author", awaiting_author),
            ("awaiting_reviewer", awaiting_reviewer),
            ("awaiting_evidence", awaiting_evidence),
            ("decision_required", decision_required),
            ("complete", complete),
        ):
            with self.subTest(phase=phase):
                self.assertEqual(phase, previous["state"]["phase"])
                reframed = self.reduce(self.reframe_event(previous), previous)[
                    "envelope"
                ]
                self.assertEqual(
                    previous["state_sha256"],
                    reframed["state"]["supersedes_state_sha256"],
                )
                self.assertEqual("exchange-8", reframed["state"]["exchange_id"])

    def test_native_legacy_finding_identity_is_pr_only_and_stable(self) -> None:
        native = self.finding("native:PRRC_kwDO-a/b+=", introduction="initial")
        state = self.reduce(self.initial_event(findings=[native]))["envelope"]
        response = self.author_event(state, "fix")
        response["responses"][0]["finding_id"] = native["id"]

        answered = self.reduce(response, state)["envelope"]

        self.assertEqual(native["id"], answered["state"]["findings"][0]["id"])
        self.assertEqual(1, len(answered["state"]["findings"]))

        versioned = self.finding("F-001", introduction="introduced_by_correction")
        versioned["location"] = "src/versioned.py:17"
        continued = self.review_event(answered, "resolve", findings=[versioned])
        continued["responses"][0]["finding_id"] = native["id"]
        mixed = self.reduce(continued, answered)["envelope"]
        self.assertEqual(
            [native["id"], "F-001"],
            [finding["id"] for finding in mixed["state"]["findings"]],
        )

        issue_event = self.initial_event(findings=[native])
        issue_event["surface"] = "issue"
        later_native = self.finding(
            "native:late-comment", introduction="introduced_by_correction"
        )
        later_event = self.review_event(answered, "resolve", findings=[later_native])
        later_event["responses"][0]["finding_id"] = native["id"]
        for label, event, previous in (
            ("issue native", issue_event, None),
            ("late native", later_event, answered),
        ):
            with (
                self.subTest(label=label),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.reduce(event, previous)

    def test_verify_rejects_impossible_stored_finding_transitions(self) -> None:
        original = self.initial_state()
        cases: list[tuple[str, dict[str, Any]]] = []

        required_nonblocking = copy.deepcopy(original)
        required_nonblocking["state"]["findings"][0]["state"] = "nonblocking"
        required_nonblocking["state"].update(
            phase="complete", verdict="GO", next_action="finalize"
        )
        cases.append(("required nonblocking", required_nonblocking))

        unresolved_resolution = copy.deepcopy(original)
        unresolved_resolution["state"]["findings"][0]["state"] = "resolved"
        unresolved_resolution["state"].update(
            phase="complete", verdict="GO", next_action="finalize"
        )
        cases.append(("resolution without responses", unresolved_resolution))

        future_introduction = copy.deepcopy(original)
        future_introduction["state"]["findings"][0]["introduced_round"] = 2
        cases.append(("future introduction", future_introduction))

        answered = self.answered_state()
        missing_response_evidence = copy.deepcopy(answered)
        response_evidence = missing_response_evidence["state"]["findings"][0][
            "author_response"
        ]["evidence"][0]
        missing_response_evidence["state"]["findings"][0]["evidence"].remove(
            response_evidence
        )
        cases.append(("missing response evidence", missing_response_evidence))

        contested = self.answered_state("contest")
        countered = self.reduce(
            self.review_event(
                contested,
                "counter",
                evidence=["New counter evidence."],
                closure_condition="The revised closure condition.",
            ),
            contested,
        )["envelope"]
        mismatched_counter = copy.deepcopy(countered)
        mismatched_counter["state"]["findings"][0]["reviewer_response"][
            "closure_condition"
        ] = "A different closure condition."
        cases.append(("mismatched counter closure", mismatched_counter))

        answered_with_unearned_authority = copy.deepcopy(answered)
        answered_with_unearned_authority["state"]["findings"][0][
            "authority_receipt"
        ] = {"reference": "policy/decision/9", "sha256": HEX_C}
        cases.append(("unearned answered authority", answered_with_unearned_authority))

        resolved = self.reduce(self.review_event(answered, "resolve"), answered)[
            "envelope"
        ]
        resolved_with_unearned_authority = copy.deepcopy(resolved)
        resolved_with_unearned_authority["state"]["findings"][0][
            "authority_receipt"
        ] = {"reference": "policy/decision/9", "sha256": HEX_C}
        cases.append(("unearned resolved authority", resolved_with_unearned_authority))

        withdrawn = self.reduce(
            self.review_event(contested, "accept", evidence=["The contest is valid."]),
            contested,
        )["envelope"]
        withdrawn_with_unearned_authority = copy.deepcopy(withdrawn)
        withdrawn_with_unearned_authority["state"]["findings"][0][
            "authority_receipt"
        ] = {"reference": "policy/decision/9", "sha256": HEX_C}
        cases.append(
            ("unearned withdrawn authority", withdrawn_with_unearned_authority)
        )

        escalated = self.reduce(self.review_event(answered, "escalate"), answered)[
            "envelope"
        ]
        escalated_with_unearned_authority = copy.deepcopy(escalated)
        escalated_with_unearned_authority["state"]["findings"][0][
            "authority_receipt"
        ] = {"reference": "policy/decision/9", "sha256": HEX_C}
        cases.append(
            ("unearned escalated authority", escalated_with_unearned_authority)
        )

        same_round_resolution = copy.deepcopy(original)
        same_round_finding = same_round_resolution["state"]["findings"][0]
        same_round_finding["evidence"].extend(
            ["The author changed the artifact.", "The reviewer checked the change."]
        )
        same_round_finding.update(
            state="resolved",
            author_response={
                "kind": "fix",
                "evidence": ["The author changed the artifact."],
                "tradeoff": None,
                "artifact_revision": "revision-1",
            },
            reviewer_response={
                "kind": "resolve",
                "evidence": ["The reviewer checked the change."],
                "closure_condition": None,
                "round": 1,
            },
        )
        same_round_resolution["state"].update(
            phase="complete", verdict="GO", next_action="finalize"
        )
        same_round_resolution["state"]["progress"][0]["required_remaining"] = 0
        cases.append(("same-round reviewer response", same_round_resolution))

        for label, envelope in cases:
            envelope["state_sha256"] = self.exchange.sha256_json(envelope["state"])
            with (
                self.subTest(label=label),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.exchange.verify_envelope(envelope)

    def test_verify_rejects_forged_introduction_bases(self) -> None:
        initial = self.initial_state()
        round_one_new_evidence = copy.deepcopy(initial)
        round_one_new_evidence["state"]["findings"][0]["introduction"] = "new_evidence"
        round_one_follow_up = copy.deepcopy(initial)
        round_one_follow_up["state"]["findings"][0]["introduction"] = (
            "nonblocking_follow_up"
        )

        answered = self.answered_state()
        late_required = self.finding("F-002", introduction="missed_high_risk")
        late_required["location"] = "src/late.py:9"
        late_required["impact"] = "A late major defect remains."
        late_required["evidence"] = ["A late failing case is now available."]
        required_state = self.reduce(
            self.review_event(answered, "resolve", findings=[late_required]), answered
        )["envelope"]

        later_initial = copy.deepcopy(required_state)
        later_initial["state"]["findings"][1]["introduction"] = "initial"
        required_follow_up = copy.deepcopy(required_state)
        required_follow_up["state"]["findings"][1]["introduction"] = (
            "nonblocking_follow_up"
        )
        low_risk_missed = copy.deepcopy(required_state)
        low_risk_missed["state"]["findings"][1]["severity"] = "minor"

        follow_up = self.finding(
            "F-002",
            severity="minor",
            disposition="suggestion",
            introduction="nonblocking_follow_up",
        )
        follow_up["location"] = "src/follow_up.py:13"
        follow_up["impact"] = "A diagnostic can be clearer."
        follow_up["evidence"] = ["The diagnostic omits one field name."]
        nonblocking_state = self.reduce(
            self.review_event(answered, "resolve", findings=[follow_up]), answered
        )["envelope"]
        nonblocking_new_evidence = copy.deepcopy(nonblocking_state)
        nonblocking_new_evidence["state"]["findings"][1]["introduction"] = (
            "new_evidence"
        )

        cases = [
            ("round-one new evidence", round_one_new_evidence),
            ("round-one follow-up", round_one_follow_up),
            ("later initial", later_initial),
            ("required follow-up", required_follow_up),
            ("low-risk missed-high-risk", low_risk_missed),
            ("nonblocking new evidence", nonblocking_new_evidence),
        ]
        for introduction in ("missed_security", "missed_correctness"):
            nonblocking_special = copy.deepcopy(nonblocking_state)
            nonblocking_special["state"]["findings"][1]["introduction"] = introduction
            cases.append((f"nonblocking {introduction}", nonblocking_special))

        for label, envelope in cases:
            envelope["state_sha256"] = self.exchange.sha256_json(envelope["state"])
            with (
                self.subTest(label=label),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.exchange.verify_envelope(envelope)

    def test_progress_is_bounded_and_matches_the_current_reviewer_state(self) -> None:
        initial = self.initial_state()
        over_limit = copy.deepcopy(initial)
        over_limit["state"]["progress"][0]["required_remaining"] = 101
        changed_scope = copy.deepcopy(initial)
        changed_scope["state"]["scope"] = ["module:forged-boundary"]
        changed_count = copy.deepcopy(initial)
        changed_count["state"]["progress"][0]["required_remaining"] = 0

        for label, envelope in (
            ("required count over limit", over_limit),
            ("current scope mismatch", changed_scope),
            ("current required count mismatch", changed_count),
        ):
            envelope["state_sha256"] = self.exchange.sha256_json(envelope["state"])
            with (
                self.subTest(label=label),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.exchange.verify_envelope(envelope)

        author = self.author_event(
            initial,
            "fix",
            scope=["path:src/example.py", "module:new-boundary"],
        )
        author["scope_change_reason"] = "The correction adds a shared boundary."
        changed_by_author = self.reduce(author, initial)["envelope"]
        self.assertEqual(
            changed_by_author,
            self.exchange.verify_envelope(changed_by_author),
        )

    def test_envelope_validation_rejects_digest_and_unknown_fields(self) -> None:
        envelope = self.initial_state()
        reordered = {
            "state_sha256": envelope["state_sha256"],
            "state": envelope["state"],
            "schema_version": 1,
            "schema_id": "athena.review-exchange.state",
        }
        self.assertEqual(envelope, self.exchange.verify_envelope(reordered))

        cases = []
        tampered = copy.deepcopy(envelope)
        tampered["state"]["round_limit"] = 4
        cases.append(tampered)
        extra = copy.deepcopy(envelope)
        extra["unexpected"] = True
        cases.append(extra)
        state_extra = copy.deepcopy(envelope)
        state_extra["state"]["unexpected"] = True
        state_extra["state_sha256"] = self.exchange.sha256_json(state_extra["state"])
        cases.append(state_extra)
        wrong_version = copy.deepcopy(envelope)
        wrong_version["schema_version"] = 2
        cases.append(wrong_version)
        for value in cases:
            with (
                self.subTest(value=value),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.exchange.verify_envelope(value)

    def test_envelope_state_must_be_an_exact_json_object(self) -> None:
        valid = self.initial_state()
        invalid_states: tuple[tuple[str, object, str], ...] = (
            ("null", None, HEX_A),
            ("number", 7, HEX_A),
            ("string", "state", HEX_A),
            (
                "pair list",
                list(valid["state"].items()),
                self.exchange.sha256_json(valid["state"]),
            ),
        )

        for label, invalid_state, digest in invalid_states:
            envelope = {
                **valid,
                "state": invalid_state,
                "state_sha256": digest,
            }
            with (
                self.subTest(label=label, boundary="API"),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.exchange.verify_envelope(envelope)

            with tempfile.TemporaryDirectory() as temporary_directory:
                path = Path(temporary_directory) / "envelope.json"
                path.write_text(
                    self.exchange.canonical_json(envelope), encoding="utf-8"
                )
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), "verify", str(path)],
                    capture_output=True,
                    text=True,
                    check=False,
                )

            with self.subTest(label=label, boundary="CLI"):
                self.assertEqual(1, result.returncode)
                self.assertEqual("", result.stdout)
                self.assertEqual(1, len(result.stderr.splitlines()))
                self.assertNotIn("Traceback", result.stderr)

    def test_carrier_round_trip_binds_visible_content(self) -> None:
        visible = "## Review\n\nThe correction is complete."
        event = self.initial_event(findings=[])
        event["artifact_binding"]["visible_content_sha256"] = self.exchange.sha256_text(
            visible
        )
        envelope = self.reduce(event)["envelope"]

        rendered = self.exchange.render_carrier(visible, envelope, "state")
        extracted = self.exchange.extract_carrier(rendered)

        self.assertEqual(envelope, extracted)
        self.assertTrue(rendered.endswith("```\n"))

        invalid_documents = (
            rendered + "trailing text",
            rendered + "\n" + rendered,
            rendered.replace("The correction", "A correction", 1),
            rendered.replace("kind=state", "kind=author-event", 1),
            rendered.replace(envelope["state_sha256"], HEX_A, 1),
            rendered.rsplit("```", maxsplit=1)[0],
        )
        for document in invalid_documents:
            with (
                self.subTest(document=document[-80:]),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.exchange.extract_carrier(document)

    def test_carrier_accepts_both_closing_fence_endings_and_rejects_trailing_content(
        self,
    ) -> None:
        state_visible = "## Review\n\nThe correction is complete."
        state_event = self.initial_event(findings=[])
        state_event["artifact_binding"]["visible_content_sha256"] = (
            self.exchange.sha256_text(state_visible)
        )
        state_envelope = self.reduce(state_event)["envelope"]

        author_visible = "Author response."
        author_state = self.initial_state()
        author_event = self.author_event(author_state, "fix")
        author_event["artifact_binding"]["visible_content_sha256"] = (
            self.exchange.sha256_text(author_visible)
        )
        author_envelope = cast(
            dict[str, Any], self.reduce(author_event, author_state)["author_event"]
        )

        cases = (
            ("state", state_visible, state_envelope),
            ("author-event", author_visible, author_envelope),
        )
        for kind, visible, envelope in cases:
            with self.subTest(kind=kind):
                rendered = self.exchange.render_carrier(visible, envelope, kind)
                self.assertTrue(rendered.endswith("```\n"))
                without_final_newline = rendered[:-1]
                self.assertEqual(rendered, without_final_newline + "\n")
                self.assertEqual(envelope, self.exchange.extract_carrier(rendered))
                self.assertEqual(
                    envelope,
                    self.exchange.extract_carrier(without_final_newline),
                )
                for candidate in (
                    rendered + "trailing text",
                    without_final_newline + "trailing text",
                    rendered + "\n",
                    rendered + " ",
                    without_final_newline + " ",
                ):
                    with (
                        self.subTest(candidate=candidate[-32:]),
                        self.assertRaises(self.exchange.ProtocolError),
                    ):
                        self.exchange.extract_carrier(candidate)

    def test_carrier_marker_cannot_be_inside_an_unclosed_fence(self) -> None:
        visible = "## Review\n\n```text\nThe review fence is not closed."
        event = self.initial_event(findings=[])
        event["artifact_binding"]["visible_content_sha256"] = self.exchange.sha256_text(
            visible
        )
        envelope = self.reduce(event)["envelope"]
        marker = (
            "<!-- HomericIntelligence:review-exchange:v1 "
            f"kind=state sha256={envelope['state_sha256']} -->"
        )
        forged = (
            f"{visible}\n\n{marker}\n```json\n"
            f"{self.exchange.canonical_json(envelope)}\n```\n"
        )

        with self.assertRaises(self.exchange.ProtocolError):
            self.exchange.extract_carrier(forged)
        with self.assertRaises(self.exchange.ProtocolError):
            self.exchange.render_carrier(visible, envelope, "state")

        balanced = f"{visible}\n```"
        balanced_event = self.initial_event(findings=[])
        balanced_event["artifact_binding"]["visible_content_sha256"] = (
            self.exchange.sha256_text(balanced)
        )
        balanced_envelope = self.reduce(balanced_event)["envelope"]
        rendered = self.exchange.render_carrier(balanced, balanced_envelope, "state")
        self.assertEqual(
            balanced_envelope,
            self.exchange.extract_carrier(rendered),
        )

    def test_carrier_rejects_an_unclosed_fence_after_lone_cr_line_endings(
        self,
    ) -> None:
        visible = "## Review\r\r~~~text\rThe review fence is not closed."
        event = self.initial_event(findings=[])
        event["artifact_binding"]["visible_content_sha256"] = self.exchange.sha256_text(
            visible
        )
        envelope = self.reduce(event)["envelope"]
        marker = (
            "<!-- HomericIntelligence:review-exchange:v1 "
            f"kind=state sha256={envelope['state_sha256']} -->"
        )
        forged = (
            f"{visible}\n\n{marker}\n```json\n"
            f"{self.exchange.canonical_json(envelope)}\n```\n"
        )

        with self.assertRaises(self.exchange.ProtocolError):
            self.exchange.render_carrier(visible, envelope, "state")
        with self.assertRaises(self.exchange.ProtocolError):
            self.exchange.extract_carrier(forged)

    def test_carrier_marker_must_be_top_level_in_the_complete_document(
        self,
    ) -> None:
        visible = "The review ends with an unmatched `"
        finding = self.finding()
        finding["evidence"] = ["The later envelope contains a matching ` run."]
        event = self.initial_event(findings=[finding])
        event["artifact_binding"]["visible_content_sha256"] = self.exchange.sha256_text(
            visible
        )
        envelope = self.reduce(event)["envelope"]

        with self.assertRaises(self.exchange.ProtocolError):
            self.exchange.render_carrier(visible, envelope, "state")

    def test_carrier_marker_cannot_be_inside_an_unclosed_raw_html_block(
        self,
    ) -> None:
        visible_values = (
            "## Review\n\n<!-- The review comment is not closed.",
            "## Review\n\n<!-- closed --> <!-- a second comment is not closed",
            "## Review\n\n<script>\nconst status = 'not closed';",
            "## Review\n\n<script></script><script>",
            "## Review\n\n<script>\nx = 1;\n</ script >",
            "## Review\n\n<?review processing is not closed",
            "## Review\n\n<!REVIEW is not closed",
            "## Review\n\n<![CDATA[review data is not closed",
            "## Review\n\n<details>\n<summary>Review</summary>",
            "## Review\n\n<div>\nThe review container is not closed.",
            "## Review\n\n<details><!-- </details> -->",
            "## Review\n\n<details>\n<!--\n</details>\n-->",
            '## Review\n\n<details>\n<script>\n"</details>"\n</script>',
            '## Review\n\n<details>\n<pre>\n"</details>"\n</pre>',
            '## Review\n\n<details>\n<textarea>\n"</details>"\n</textarea>',
            "## Review\n\n<script></script><details>",
            "## Review text <details>",
        )
        for visible in visible_values:
            event = self.initial_event(findings=[])
            event["artifact_binding"]["visible_content_sha256"] = (
                self.exchange.sha256_text(visible)
            )
            envelope = self.reduce(event)["envelope"]
            marker = (
                "<!-- HomericIntelligence:review-exchange:v1 "
                f"kind=state sha256={envelope['state_sha256']} -->"
            )
            forged = (
                f"{visible}\n\n{marker}\n```json\n"
                f"{self.exchange.canonical_json(envelope)}\n```\n"
            )

            with (
                self.subTest(visible=visible),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.exchange.extract_carrier(forged)
            with (
                self.subTest(visible=visible),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.exchange.render_carrier(visible, envelope, "state")

    def test_carrier_round_trip_ignores_marker_like_evidence_data(self) -> None:
        visible = "## Review\n\nThe required finding is visible."
        finding = self.finding()
        finding["evidence"] = [
            (
                "The parser saw <!-- HomericIntelligence:review-exchange:v1 "
                f"kind=state sha256={HEX_A} --> as data."
            )
        ]
        event = self.initial_event(findings=[finding])
        event["artifact_binding"]["visible_content_sha256"] = self.exchange.sha256_text(
            visible
        )
        envelope = self.reduce(event)["envelope"]

        rendered = self.exchange.render_carrier(visible, envelope, "state")

        self.assertEqual(envelope, self.exchange.extract_carrier(rendered))

    def test_shared_markdown_scanner_returns_only_top_level_lines(self) -> None:
        scanner = self.exchange.top_level_markdown_lines
        self.assertTrue(callable(scanner))
        body = (
            "top\n"
            "```text\ninside fence\n```\n"
            "<!-- inside comment\nmarker\n-->\n"
            "<script>\ninside script\n</script>\n"
            "last"
        )

        lines = scanner(body, require_closed=True)

        self.assertEqual(["top", "last"], [line for _start, _end, line in lines])

        marker = "<!-- HomericIntelligence:plan-issue -->"
        self.assertEqual(
            [marker],
            [line for _start, _end, line in scanner(marker, require_closed=True)],
        )

        fenced_marker = f"```json\n{marker}\n```\n{marker}"
        self.assertEqual(
            [marker],
            [
                line
                for _start, _end, line in scanner(fenced_marker, require_closed=True)
            ],
        )

        multiline_code = f"`open\n{marker}\nclosed`\nafter"
        scanned = [
            line for _start, _end, line in scanner(multiline_code, require_closed=True)
        ]
        self.assertNotIn(marker, scanned)
        self.assertIn("after", scanned)

        with self.assertRaises(self.exchange.ProtocolError):
            scanner(f"`open\n\n{marker}", require_closed=True)

    def test_shared_markdown_scanner_rejects_live_html_containers(self) -> None:
        scanner = self.exchange.top_level_markdown_lines
        visible_values = (
            "<details/>",
            "<details/>\n\nafter",
            "<details />",
            "<details open/>",
            "text <details/>",
            "<details\nopen>",
            "<details\x0copen>",
            "` <details>",
            "` <details> ``",
            "`` <details> ```",
            "\\` <details> `",
        )
        for visible in visible_values:
            with (
                self.subTest(visible=visible),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                scanner(visible, require_closed=True)

        inline_code = "`<details>`\nvisible"
        self.assertEqual(
            ["`<details>`", "visible"],
            [line for _start, _end, line in scanner(inline_code, require_closed=True)],
        )

        void_tag = "<img>\n\nvisible"
        self.assertIn(
            "visible",
            [line for _start, _end, line in scanner(void_tag, require_closed=True)],
        )

        indented_code = "    <details>\n\nvisible"
        self.assertIn(
            "visible",
            [
                line
                for _start, _end, line in scanner(indented_code, require_closed=True)
            ],
        )

    def test_carrier_rejects_misnested_html_container_closures(self) -> None:
        visible_values = (
            "<details><p></details>",
            "<details><table></details>",
        )
        for visible in visible_values:
            event = self.initial_event(findings=[])
            event["artifact_binding"]["visible_content_sha256"] = (
                self.exchange.sha256_text(visible)
            )
            envelope = self.reduce(event)["envelope"]
            marker = (
                "<!-- HomericIntelligence:review-exchange:v1 "
                f"kind=state sha256={envelope['state_sha256']} -->"
            )
            forged = (
                f"{visible}\n\n{marker}\n```json\n"
                f"{self.exchange.canonical_json(envelope)}\n```\n"
            )
            with (
                self.subTest(visible=visible, operation="scan"),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.exchange.top_level_markdown_lines(visible, require_closed=True)
            with (
                self.subTest(visible=visible, operation="render"),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.exchange.render_carrier(visible, envelope, "state")
            with (
                self.subTest(visible=visible, operation="extract"),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.exchange.extract_carrier(forged)

    def test_shared_markdown_scanner_resumes_after_persistent_html(self) -> None:
        scanner = self.exchange.top_level_markdown_lines
        cases = (
            "<!-- hidden -->\nafter",
            "<!-- hidden --!>\nafter",
            "<?hidden?>\nafter",
            "<![CDATA[hidden]]>\nafter",
            "<!HIDDEN value>\nafter",
            "<!-- closed --> <!-- open\nhidden\n-->\nafter",
        )
        for body in cases:
            with self.subTest(body=body):
                self.assertEqual(
                    ["after"],
                    [line for _start, _end, line in scanner(body, require_closed=True)],
                )

    def test_carrier_scanner_uses_commonmark_code_span_and_html_precedence(
        self,
    ) -> None:
        visible_values = (
            "`safe\n\\`\n<pre>\n`",
            '<a title="`">\n<pre>\n`` `',
            '<a title="`"><pre>\\`',
        )
        for visible in visible_values:
            event = self.initial_event(findings=[])
            event["artifact_binding"]["visible_content_sha256"] = (
                self.exchange.sha256_text(visible)
            )
            envelope = self.reduce(event)["envelope"]
            marker = (
                "<!-- HomericIntelligence:review-exchange:v1 "
                f"kind=state sha256={envelope['state_sha256']} -->"
            )
            forged = (
                f"{visible}\n\n{marker}\n```json\n"
                f"{self.exchange.canonical_json(envelope)}\n```\n"
            )
            with (
                self.subTest(visible=visible, operation="render"),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.exchange.render_carrier(visible, envelope, "state")
            with (
                self.subTest(visible=visible, operation="extract"),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.exchange.extract_carrier(forged)
            with (
                self.subTest(visible=visible, operation="scan"),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.exchange.top_level_markdown_lines(visible, require_closed=True)

    def test_carrier_rejects_code_delimiters_after_html_block_precedence(
        self,
    ) -> None:
        visible_values = (
            "<pre>\nx ` </pre>\n<pre>\n`",
            "<script>\nx ` </script>\n<script>\n`",
            "<style>\nx ` </style>\n<style>\n`",
            "<textarea>\nx ` </textarea>\n<textarea>\n`",
            "<!--\nx ` -->\n<pre>\n`",
            "<pre>\nx ` </pre><pre> `",
            "<!--\nx ` --><pre> `",
            "<!--\nx ` --!><pre> `",
            "<details>\nx </details> ` <pre> `",
            "<div>\nx </div> ` <pre> `",
            "<a>\nx </a> ` <pre> `",
            "<!-- x --> ` <pre> `",
            "<!-- x --!> ` <pre> `",
            "<pre></pre> ` <pre> `",
            "<details></details> ` <pre> `",
            '<a title=">`"> <pre> `',
            "<a title='>`'> <pre> `",
            '<a title="<`>"> <pre> `',
            '<a title="\n>`"> <pre> `',
            '<img\nsrc="x"\nalt="`">\n`` <pre> `',
            "<hr\nx>\n` <pre> `",
            "<hr\r\nx>\r\n` <pre> `",
            "<hr>\n~~~\n<pre>\n~~~",
            "<hr\nx>\n~~~\n<pre>\n~~~",
            "<hr>\n    <pre>",
            "<hr>\n\t<pre>",
            "<div></div>\n    <pre>",
        )
        for visible in visible_values:
            event = self.initial_event(findings=[])
            event["artifact_binding"]["visible_content_sha256"] = (
                self.exchange.sha256_text(visible)
            )
            envelope = self.reduce(event)["envelope"]
            marker = (
                "<!-- HomericIntelligence:review-exchange:v1 "
                f"kind=state sha256={envelope['state_sha256']} -->"
            )
            forged = (
                f"{visible}\n\n{marker}\n```json\n"
                f"{self.exchange.canonical_json(envelope)}\n```\n"
            )

            with (
                self.subTest(visible=visible, operation="render"),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.exchange.render_carrier(visible, envelope, "state")
            with (
                self.subTest(visible=visible, operation="extract"),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.exchange.extract_carrier(forged)

            with (
                self.subTest(visible=visible, operation="scan"),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.exchange.top_level_markdown_lines(visible, require_closed=True)

    def test_carrier_scanner_preserves_code_that_contains_html_syntax(self) -> None:
        visible_values = (
            '```html\n<a title="`">\n```\nafter',
            '~~~html\n<a title="`">\n~~~\nafter',
            '`` <a title="`"> ``\nafter',
            "    <pre> `code-like tick`\n\nafter",
        )
        for visible in visible_values:
            event = self.initial_event(findings=[])
            event["artifact_binding"]["visible_content_sha256"] = (
                self.exchange.sha256_text(visible)
            )
            envelope = self.reduce(event)["envelope"]

            with self.subTest(visible=visible):
                rendered = self.exchange.render_carrier(visible, envelope, "state")
                self.assertEqual(envelope, self.exchange.extract_carrier(rendered))

    def test_carrier_rejects_an_incomplete_type6_html_tag(self) -> None:
        visible_values = (
            "<details",
            "<details\n\n",
            "<div\n\n",
            "<details\r\r",
            "<details\r\n\r\n",
            '<details title="\n>',
            "<details title='\n>",
            '<div title="\r\n>',
        )
        for visible in visible_values:
            event = self.initial_event(findings=[])
            event["artifact_binding"]["visible_content_sha256"] = (
                self.exchange.sha256_text(visible)
            )
            envelope = self.reduce(event)["envelope"]
            marker = (
                "<!-- HomericIntelligence:review-exchange:v1 "
                f"kind=state sha256={envelope['state_sha256']} -->"
            )
            forged = (
                f"{visible}\n\n{marker}\n```json\n"
                f"{self.exchange.canonical_json(envelope)}\n```\n"
            )

            with (
                self.subTest(visible=visible, operation="render"),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.exchange.render_carrier(visible, envelope, "state")
            with (
                self.subTest(visible=visible, operation="extract"),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.exchange.extract_carrier(forged)
            with (
                self.subTest(visible=visible, operation="scan"),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.exchange.top_level_markdown_lines(visible, require_closed=True)

    def test_shared_markdown_scanner_rejects_unicode_line_separators(self) -> None:
        marker = "<!-- HomericIntelligence:plan-issue -->"
        separators = ("\v", "\f", "\x85", "\u2028", "\u2029")
        for separator in separators:
            body = f"prefix{separator}{marker}"
            with self.subTest(separator=ord(separator)):
                self.assertNotIn(
                    marker,
                    [
                        line
                        for _start, _end, line in self.exchange.top_level_markdown_lines(
                            body, require_closed=True
                        )
                    ],
                )

    def test_provider_body_limit_is_enforced(self) -> None:
        limit = self.exchange.PROVIDER_BODY_LIMITS["github"]
        visible = "x" * limit
        event = self.initial_event(findings=[])
        event["artifact_binding"]["visible_content_sha256"] = self.exchange.sha256_text(
            visible
        )
        envelope = self.reduce(event)["envelope"]
        with self.assertRaises(self.exchange.ProtocolError):
            self.exchange.render_carrier(visible, envelope, "state")

    def test_carrier_scanner_has_bounded_work_near_the_provider_limit(self) -> None:
        counters = {"text": 0, "spans": 0}

        class MeasuredText(str):
            text_budget: int

            def __new__(cls, value: str, text_budget: int) -> Any:
                instance: Any = super().__new__(cls, value)
                instance.text_budget = text_budget
                return instance

            def charge(self, amount: int) -> None:
                counters["text"] += amount
                if counters["text"] > self.text_budget:
                    raise AssertionError("The scanner exceeded its text-work budget.")

            def find(self, sub: str, start: Any = 0, end: Any = None) -> int:
                stop = len(self) if end is None else end
                self.charge(max(0, stop - start))
                return super().find(sub, start, stop)

            def __getitem__(self, key: Any) -> Any:
                result = super().__getitem__(key)
                if isinstance(key, slice) and isinstance(result, str):
                    self.charge(len(result))
                    return MeasuredText(result, self.text_budget)
                return result

        class MeasuredSpans(list[tuple[int, int]]):
            def __init__(self, values: list[tuple[int, int]], budget: int) -> None:
                super().__init__(values)
                self.budget = budget

            def charge(self) -> None:
                counters["spans"] += 1
                if counters["spans"] > self.budget:
                    raise AssertionError("The scanner exceeded its span-visit budget.")

            def __iter__(self):  # type: ignore[no-untyped-def]
                for value in super().__iter__():
                    self.charge()
                    yield value

            def __getitem__(self, key):  # type: ignore[no-untyped-def]
                self.charge()
                return super().__getitem__(key)

        single_line_spans = "`x` " * 4_000 + "\n"
        multiline_spans = "`open\nclose`\n" * 3_000
        visible = single_line_spans + multiline_spans
        visible += "x" * (62_000 - len(visible))
        text_budget = len(visible) * 80
        span_budget = len(visible) * 4
        measured = MeasuredText(visible, text_budget)
        dynamic_exchange: Any = self.exchange
        original = dynamic_exchange._multiline_code_spans

        def measured_spans(
            body: str,
        ) -> tuple[MeasuredSpans, tuple[int, ...]]:
            spans, unmatched = original(body)
            return MeasuredSpans(spans, span_budget), unmatched

        dynamic_exchange._multiline_code_spans = measured_spans
        try:
            self.exchange.top_level_markdown_lines(measured, require_closed=True)
        finally:
            dynamic_exchange._multiline_code_spans = original

        self.assertGreater(counters["text"], 0)
        self.assertLessEqual(counters["text"], text_budget)
        self.assertGreater(counters["spans"], 0)
        self.assertLessEqual(counters["spans"], span_budget)

        event = self.initial_event(findings=[])
        event["artifact_binding"]["visible_content_sha256"] = self.exchange.sha256_text(
            visible
        )
        envelope = self.reduce(event)["envelope"]
        rendered = self.exchange.render_carrier(visible, envelope, "state")

        self.assertGreater(len(rendered.encode("utf-8")), 63_000)
        self.assertLessEqual(
            len(rendered.encode("utf-8")),
            self.exchange.PROVIDER_BODY_LIMITS["github"],
        )
        self.assertEqual(envelope, self.exchange.extract_carrier(rendered))

    def test_carrier_scanner_batches_incomplete_html_parser_work(self) -> None:
        parser = self.exchange.HTMLParser
        original_feed = parser.feed
        original_close = parser.close
        work = 0
        work_budget = 0

        def charge(amount: int) -> None:
            nonlocal work
            work += amount
            if work > work_budget:
                raise AssertionError("The HTML parser exceeded its work budget.")

        def measured_feed(instance: Any, data: str) -> None:
            charge(len(instance.rawdata) + len(data))
            original_feed(instance, data)

        def measured_close(instance: Any) -> None:
            pending = cast(list[str], getattr(instance, "_pending", []))
            charge(len(instance.rawdata) + sum(map(len, pending)))
            original_close(instance)

        parser.feed = measured_feed
        parser.close = measured_close
        try:
            cases = (
                ("unfinished tag", "<a\n", "x" * 48 + "\n"),
                (
                    "unfinished quoted value",
                    '<a value="\n',
                    "x" * 47 + ">\n",
                ),
            )
            for label, prefix, continuation in cases:
                with self.subTest(label=label):
                    visible = prefix + (continuation * 1_300)
                    work = 0
                    work_budget = len(visible) * 4
                    scanned = self.exchange.top_level_markdown_lines(
                        visible, require_closed=True
                    )

                    self.assertEqual(1_301, len(scanned))
                    self.assertGreater(work, len(visible))
                    self.assertLessEqual(work, work_budget)
        finally:
            parser.feed = original_feed
            parser.close = original_close

    def test_html_end_tags_use_constant_time_open_tag_membership(self) -> None:
        class MeasuredStack(list[str]):
            membership_work = 0

            def __contains__(self, value: object) -> bool:
                type(self).membership_work += len(self)
                return super().__contains__(value)

        parser = self.exchange._HTMLContainerParser()
        parser.stack = MeasuredStack()
        size = 2_000
        for index in range(size):
            parser.handle_starttag(f"node-{index}", [])
        expected = list(parser.stack)

        for index in range(size):
            parser.handle_endtag(f"absent-{index}")

        self.assertEqual(0, MeasuredStack.membership_work)
        self.assertEqual(expected, parser.stack)
        with self.assertRaises(self.exchange.ProtocolError):
            parser.handle_endtag("node-0")
        parser.handle_endtag(f"node-{size - 1}")
        self.assertEqual(expected[:-1], parser.stack)

    def test_duplicate_json_keys_and_nonfinite_values_are_rejected(self) -> None:
        values = (
            b'{"previous":null,"previous":null,"event":{}}',
            b'{"previous":null,"event":NaN}',
        )
        for value in values:
            with (
                self.subTest(value=value),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.exchange.parse_json_bytes(value)

    def test_large_json_integer_is_a_protocol_rejection(self) -> None:
        value = b'{"value":' + (b"9" * 5000) + b"}"

        try:
            self.exchange.parse_json_bytes(value)
        except self.exchange.ProtocolError:
            pass
        except ValueError as error:
            self.fail(f"A plain ValueError escaped: {error}")
        else:
            self.fail("The overlong integer was accepted.")

        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "large-integer.json"
            path.write_bytes(value)
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "verify", str(path)],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(1, result.returncode)
        self.assertEqual("", result.stdout)
        self.assertEqual(1, len(result.stderr.splitlines()))
        self.assertNotIn("Traceback", result.stderr)

    def test_lone_json_surrogate_is_a_protocol_rejection(self) -> None:
        value = b'{"value":"\\ud800"}'

        with self.assertRaises(self.exchange.ProtocolError):
            self.exchange.parse_json_bytes(value)

        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "surrogate.json"
            path.write_bytes(value)
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "verify", str(path)],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(1, result.returncode)
        self.assertEqual("", result.stdout)
        self.assertEqual(1, len(result.stderr.splitlines()))
        self.assertNotIn("Traceback", result.stderr)

    def test_primitive_schema_boundaries_fail_closed(self) -> None:
        operations: tuple[tuple[str, Callable[[], object]], ...] = (
            ("noncanonical value", lambda: self.exchange.canonical_json(object())),
            (
                "oversized input",
                lambda: self.exchange.parse_json_bytes(
                    b"x" * (self.exchange.MAX_INPUT_BYTES + 1)
                ),
            ),
            ("invalid UTF-8", lambda: self.exchange.parse_json_bytes(b"\xff")),
            ("invalid JSON", lambda: self.exchange.parse_json_bytes(b"{")),
            (
                "object type",
                lambda: self.exchange._object([], "value", frozenset()),
            ),
            ("blank string", lambda: self.exchange._string(" ", "value")),
            ("invalid digest", lambda: self.exchange._digest("bad", "value")),
            (
                "integer minimum",
                lambda: self.exchange._integer(False, "value", minimum=0),
            ),
            (
                "integer maximum",
                lambda: self.exchange._integer(2, "value", maximum=1),
            ),
            ("Boolean type", lambda: self.exchange._boolean(1, "value")),
            (
                "enum value",
                lambda: self.exchange._enum("bad", "value", frozenset({"good"})),
            ),
            ("string-list type", lambda: self.exchange._strings({}, "value")),
            ("empty string list", lambda: self.exchange._strings([], "value")),
            (
                "duplicate string list",
                lambda: self.exchange._strings(["same", "same"], "value"),
            ),
        )
        for label, operation in operations:
            with (
                self.subTest(label=label),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                operation()

    def test_finding_and_response_schema_boundaries_fail_closed(self) -> None:
        finding_cases = (
            {"id": "F-000"},
            {
                "severity": "major",
                "disposition": "suggestion",
                "closure_condition": None,
            },
            {"severity": "nit", "disposition": "suggestion", "closure_condition": None},
            {"closure_condition": None},
            {
                "severity": "minor",
                "disposition": "suggestion",
                "closure_condition": "An optional condition.",
            },
        )
        for changes in finding_cases:
            finding = self.finding()
            finding.update(changes)
            with (
                self.subTest(changes=changes),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.exchange._finding_input(finding, "finding")

        author_cases = (
            {"kind": "fix_with_tradeoff", "tradeoff": None},
            {"kind": "fix", "tradeoff": "An inapplicable trade-off."},
        )
        for changes in author_cases:
            response = {
                "finding_id": "F-001",
                "kind": "fix",
                "evidence": ["Evidence."],
                "tradeoff": None,
            }
            response.update(changes)
            with (
                self.subTest(changes=changes),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.exchange._author_response(response, "response")

        reviewer_cases = (
            {"kind": "counter", "closure_condition": None},
            {"kind": "resolve", "closure_condition": "Inapplicable."},
        )
        for changes in reviewer_cases:
            response = {
                "finding_id": "F-001",
                "kind": "resolve",
                "evidence": ["Evidence."],
                "closure_condition": None,
            }
            response.update(changes)
            with (
                self.subTest(changes=changes),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.exchange._reviewer_response(response, "response")

        response = {
            "finding_id": "F-001",
            "kind": "fix",
            "evidence": ["Evidence."],
            "tradeoff": None,
        }
        response_cases: tuple[tuple[str, object], ...] = (
            ("non-list", {}),
            ("duplicate", [response, response]),
        )
        for label, value in response_cases:
            with (
                self.subTest(label=label),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.exchange._unique_responses(
                    value, "responses", self.exchange._author_response
                )

        new_finding_cases: tuple[tuple[str, object, int], ...] = (
            ("non-list", {}, 1),
            ("initial basis in round two", [self.finding("F-002")], 2),
            (
                "later basis in round one",
                [self.finding(introduction="new_evidence")],
                1,
            ),
            (
                "required low-risk follow-up",
                [self.finding("F-002", introduction="nonblocking_follow_up")],
                2,
            ),
            (
                "nonblocking wrong basis",
                [
                    self.finding(
                        "F-002",
                        severity="minor",
                        disposition="suggestion",
                        introduction="new_evidence",
                    )
                ],
                2,
            ),
        )
        for label, value, round_number in new_finding_cases:
            with (
                self.subTest(label=label),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.exchange._new_findings(
                    value,
                    "findings",
                    existing_count=0 if round_number == 1 else 1,
                    round_number=round_number,
                )

    def test_stored_state_invariants_fail_closed(self) -> None:
        valid = self.initial_state()["state"]
        cases: list[tuple[str, dict[str, Any]]] = []

        nonblocking = copy.deepcopy(valid["findings"][0])
        nonblocking.update(
            severity="minor",
            disposition="suggestion",
            closure_condition=None,
        )
        cases.append(("nonblocking state", {**valid, "findings": [nonblocking]}))

        accepted_without_authority = copy.deepcopy(valid["findings"][0])
        accepted_without_authority["state"] = "accepted_risk"
        cases.append(
            (
                "accepted risk authority",
                {**valid, "findings": [accepted_without_authority]},
            )
        )
        cases.append(("finding collection", {**valid, "findings": {}}))
        cases.append(
            (
                "finding limit",
                {**valid, "findings": [valid["findings"][0]] * 101},
            )
        )
        wrong_id = copy.deepcopy(valid["findings"][0])
        wrong_id["id"] = "F-002"
        cases.append(("stable state ID", {**valid, "findings": [wrong_id]}))
        cases.append(("progress collection", {**valid, "progress": {}}))
        cases.append(("progress sequence", {**valid, "progress": []}))
        cases.append(
            (
                "missing GO eligibility",
                {key: value for key, value in valid.items() if key != "go_eligible"},
            )
        )
        cases.append(("phase tuple", {**valid, "verdict": "GO"}))
        cases.append(
            (
                "GO with active finding",
                {
                    **valid,
                    "phase": "complete",
                    "verdict": "GO",
                    "next_action": "finalize",
                },
            )
        )
        clean = self.reduce(self.initial_event(findings=[]))["envelope"]["state"]
        cases.append(
            (
                "conditional tuple with eligible state",
                {
                    **clean,
                    "verdict": "CONDITIONAL GO",
                    "next_action": "none",
                },
            )
        )
        cases.append(
            (
                "author without finding",
                {
                    **clean,
                    "phase": "awaiting_author",
                    "verdict": "NO-GO",
                    "next_action": "author_response",
                },
            )
        )
        cases.append(
            (
                "evidence state mismatch",
                {
                    **valid,
                    "phase": "awaiting_evidence",
                    "next_action": "review_assessment",
                },
            )
        )
        cases.append(("round limit", {**valid, "round_limit": 6}))

        for label, state in cases:
            with (
                self.subTest(label=label),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.exchange._validate_state(state)

        author_state = self.reduce(
            self.author_event(self.initial_state(), "fix"), self.initial_state()
        )["author_event"]["state"]
        with self.assertRaises(self.exchange.ProtocolError):
            self.exchange._validate_author_event_record(
                {**author_state, "event_type": "reviewer_assessment"}
            )
        with self.assertRaises(self.exchange.ProtocolError):
            self.exchange.make_envelope(valid, "unsupported")

    def test_cli_verify_render_and_extract_round_trip(self) -> None:
        visible = "## Review\n\nNo required finding remains."
        event = self.initial_event(findings=[])
        event["artifact_binding"]["visible_content_sha256"] = self.exchange.sha256_text(
            visible
        )
        envelope = self.reduce(event)["envelope"]
        render_request = {
            "visible_content": visible,
            "envelope": envelope,
            "kind": "state",
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            envelope_path = root / "envelope.json"
            envelope_path.write_text(
                self.exchange.canonical_json(envelope), encoding="utf-8"
            )
            render_path = root / "render.json"
            render_path.write_text(
                self.exchange.canonical_json(render_request), encoding="utf-8"
            )
            verified_stdout = io.StringIO()
            with redirect_stdout(verified_stdout):
                verified = self.exchange.main(["verify", str(envelope_path)])
            rendered_stdout = io.StringIO()
            with redirect_stdout(rendered_stdout):
                rendered = self.exchange.main(["render", str(render_path)])
            carrier_path = root / "carrier.md"
            carrier_path.write_text(rendered_stdout.getvalue(), encoding="utf-8")
            extracted_stdout = io.StringIO()
            with redirect_stdout(extracted_stdout):
                extracted = self.exchange.main(["extract", str(carrier_path)])

        self.assertEqual(0, verified)
        self.assertEqual(0, rendered)
        self.assertEqual(0, extracted)
        self.assertEqual(
            self.exchange.canonical_json(envelope), verified_stdout.getvalue().strip()
        )
        self.assertEqual(
            self.exchange.canonical_json(envelope), extracted_stdout.getvalue().strip()
        )

    def test_cli_supports_file_and_stdin_and_classifies_failures(self) -> None:
        request = {"previous": None, "event": self.initial_event(findings=[])}
        encoded = self.exchange.canonical_json(request)
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "request.json"
            path.write_text(encoded, encoding="utf-8")
            from_file = subprocess.run(
                [sys.executable, str(SCRIPT), "reduce", str(path)],
                capture_output=True,
                text=True,
                check=False,
            )
            from_stdin = subprocess.run(
                [sys.executable, str(SCRIPT), "reduce", "-"],
                input=encoded,
                capture_output=True,
                text=True,
                check=False,
            )
            missing = subprocess.run(
                [sys.executable, str(SCRIPT), "verify", str(path.parent / "missing")],
                capture_output=True,
                text=True,
                check=False,
            )
            invalid = path.parent / "invalid.json"
            invalid.write_text("{}", encoding="utf-8")
            invalid_stdout = io.StringIO()
            invalid_stderr = io.StringIO()
            with redirect_stdout(invalid_stdout), redirect_stderr(invalid_stderr):
                rejected = self.exchange.main(["verify", str(invalid)])

        self.assertEqual(0, from_file.returncode, from_file.stderr)
        self.assertEqual(from_file.stdout, from_stdin.stdout)
        self.assertEqual(2, missing.returncode)
        self.assertNotIn("Traceback", missing.stderr)
        self.assertEqual(1, rejected)
        self.assertEqual("", invalid_stdout.getvalue())

    def test_cli_escapes_untrusted_control_characters_in_one_diagnostic(
        self,
    ) -> None:
        event = self.initial_event(findings=[])
        event["surface"] = "pull_request\nforged\x1b[2J"
        request = {"previous": None, "event": event}
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "request.json"
            path.write_text(self.exchange.canonical_json(request), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "reduce", str(path)],
                capture_output=True,
                check=False,
            )

        self.assertEqual(1, result.returncode)
        self.assertEqual(b"", result.stdout)
        self.assertEqual(1, result.stderr.count(b"\n"))
        self.assertNotIn(b"\r", result.stderr)
        self.assertNotIn(b"\x1b", result.stderr)
        self.assertIn(b"\\n", result.stderr)
        self.assertIn(b"\\x1b", result.stderr)

    def test_cli_classifies_output_write_failures_as_operational(self) -> None:
        class BrokenOutput(io.StringIO):
            def __init__(self, error: BaseException) -> None:
                super().__init__()
                self.error = error

            def write(self, value: str) -> int:
                del value
                raise self.error

        envelope = self.reduce(self.initial_event(findings=[]))["envelope"]
        errors = (
            BrokenPipeError("the output is closed"),
            OSError("the output failed"),
            UnicodeEncodeError("ascii", "é", 0, 1, "encoding failed"),
        )
        for error in errors:
            with tempfile.TemporaryDirectory() as temporary_directory:
                path = Path(temporary_directory) / "envelope.json"
                path.write_text(
                    self.exchange.canonical_json(envelope), encoding="utf-8"
                )
                error_output = io.StringIO()
                result: int | None = None
                with (
                    self.subTest(error=type(error).__name__),
                    redirect_stdout(BrokenOutput(error)),
                    redirect_stderr(error_output),
                ):
                    result = self.exchange.main(["verify", str(path)])

            self.assertEqual(2, result)
            self.assertEqual(1, len(error_output.getvalue().splitlines()))
            self.assertNotIn("Traceback", error_output.getvalue())

    def test_cli_writes_rendered_content_as_utf8(self) -> None:
        visible = "## Review\n\nRésumé complete."
        event = self.initial_event(findings=[])
        event["artifact_binding"]["visible_content_sha256"] = self.exchange.sha256_text(
            visible
        )
        envelope = self.reduce(event)["envelope"]
        request = {
            "visible_content": visible,
            "envelope": envelope,
            "kind": "state",
        }
        environment = dict(os.environ)
        environment["PYTHONIOENCODING"] = "ascii"
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "render.json"
            path.write_text(self.exchange.canonical_json(request), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "render", str(path)],
                capture_output=True,
                check=False,
                env=environment,
            )

        self.assertEqual(0, result.returncode)
        self.assertIn("Résumé complete.", result.stdout.decode("utf-8"))

    def test_cli_classifies_a_short_output_write_as_operational(self) -> None:
        class ShortBinaryOutput:
            def write(self, value: bytes) -> int:
                return len(value) - 1

            def flush(self) -> None:
                pass

        class Output:
            def __init__(self) -> None:
                self.buffer = ShortBinaryOutput()

        envelope = self.reduce(self.initial_event(findings=[]))["envelope"]
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "envelope.json"
            path.write_text(self.exchange.canonical_json(envelope), encoding="utf-8")
            error_output = io.StringIO()
            with (
                redirect_stdout(cast(Any, Output())),
                redirect_stderr(error_output),
            ):
                result = self.exchange.main(["verify", str(path)])

        self.assertEqual(2, result)
        self.assertEqual(1, len(error_output.getvalue().splitlines()))


if __name__ == "__main__":
    unittest.main()
