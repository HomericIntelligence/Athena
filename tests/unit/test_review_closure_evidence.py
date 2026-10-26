"""A closure must rest on evidence that supports it."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any, cast

from tests.unit import test_review_exchange as fixtures

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/review_exchange/comet_pr_1510"
AUTHOR_BODY = "author_review_body.md"
TERMINAL_BODY = "terminal_reviewer_body.md"
CARRIER_SEPARATOR = "\n\n<!-- HomericIntelligence:review-exchange:v1"
FINDING_EVIDENCE = "The failing case returns 0."
AUTHOR_EVIDENCE = "The correction is in revision-2."
CLOSURE_EVIDENCE = "The sent plan now meets the closure condition."

# The identity of the immutable pull request that supplied the carriers.
REVIEWED_HEAD = "ebdea81d01b66b7fec40f4e55e7169cce21cff2c"
ROUND_1_STATE = "c22b33db4462594369cfe1c05321c059efe21a429fcf8b10c1cda7893c15dba6"
AUTHOR_REVIEW_ID = 5204713543
AUTHOR_EVENT_STATE = "e4c82dd8303b2b116d5ef6292306b68794c1f76ea7f41665445cfbd662beff9a"
AUTHOR_VISIBLE = "8023ede1a568f6c42e4722f52d6c098c9e1af7d85bec2459b0f524a192ffd2cd"
AUTHOR_BODY_SHA256 = "900c4be6f68d7979684ea48b3677fa0c2fbbcd04c6cf3d6e5352f8abb84b0752"
TERMINAL_REVIEW_ID = 5204741339
TERMINAL_VISIBLE = "4e693e4f0993ed84541999019e58170dafda2f8d628697b61e23906fa9dfa8da"
TERMINAL_BODY_SHA256 = (
    "c665e4080d014964f555078d13369538fe7ad8bdadad052d82afcd8b2dfec0cb"
)
TERMINAL_STATE = "2c2feb9599906cf31fc90ccaabf3cdcb3967164a806ad017876af83f8dad8c78"
FINDING_ID = "comet-pr-1510-a3e3994d/F-001"


def as_object(value: Any) -> dict[str, Any]:
    """Return one mapping that a fixture loaded."""
    return cast(dict[str, Any], value)


class ClosureEvidenceTests(unittest.TestCase):
    """The common reducer must reject a closure its evidence does not support."""

    exchange: ModuleType

    @classmethod
    def setUpClass(cls) -> None:
        cls.exchange = fixtures.load_module()

    def setUp(self) -> None:
        self.builders = fixtures.ReviewExchangeTests()
        self.builders.exchange = self.exchange
        self.manifest = as_object(
            json.loads((FIXTURE / "manifest.json").read_text(encoding="utf-8"))
        )

    def document(self, name: str) -> str:
        """Return one immutable carrier document."""
        return (FIXTURE / name).read_text(encoding="utf-8")

    def parts(self, document: str) -> tuple[str, dict[str, Any]]:
        """Return the visible content and the encoded envelope of one carrier."""
        visible, separator, payload = document.partition(CARRIER_SEPARATOR)
        if not separator:
            raise AssertionError("The carrier document has no final carrier.")
        body = payload.split("\n```json\n", 1)[1]
        return visible, as_object(json.loads(body.rsplit("\n```", 1)[0]))

    def rebuild(
        self,
        document: str,
        change_state: Any,
        *,
        visible: str | None = None,
    ) -> str:
        """Render a carrier whose envelope and bound visible content changed."""
        original_visible, original = self.parts(document)
        state = copy.deepcopy(original["state"])
        change_state(state)
        rendered = original_visible if visible is None else visible
        state["artifact_binding"]["visible_content_sha256"] = self.exchange.sha256_text(
            rendered
        )
        envelope = self.exchange.make_envelope(state, original["schema_id"])
        rendered_document: str = self.exchange.render_carrier(
            rendered, envelope, original["schema_id"].rsplit(".", 1)[-1]
        )
        return rendered_document

    def answered_state(self) -> dict[str, Any]:
        """Reduce one exchange up to its author answer."""
        initial = self.builders.initial_state()
        return as_object(
            self.builders.reduce(self.builders.author_event(initial, "fix"), initial)[
                "envelope"
            ]
        )

    def closure_state(self, resolve_evidence: list[str]) -> dict[str, Any]:
        """Reduce one exchange that closes its only finding."""
        answered = self.answered_state()
        return as_object(
            self.builders.reduce(
                self.builders.review_event(
                    answered, "resolve", evidence=resolve_evidence
                ),
                answered,
            )["envelope"]
        )

    def tampered(self, envelope: dict[str, Any], change_state: Any) -> dict[str, Any]:
        """Return one state envelope whose stored state was changed."""
        state = copy.deepcopy(envelope["state"])
        change_state(state)
        return {
            "schema_id": envelope["schema_id"],
            "schema_version": envelope["schema_version"],
            "state": state,
            "state_sha256": self.exchange.sha256_json(state),
        }

    def test_1510_fixture_pins_every_immutable_carrier_digest(self) -> None:
        for name, review_id, visible, body in (
            (AUTHOR_BODY, AUTHOR_REVIEW_ID, AUTHOR_VISIBLE, AUTHOR_BODY_SHA256),
            (TERMINAL_BODY, TERMINAL_REVIEW_ID, TERMINAL_VISIBLE, TERMINAL_BODY_SHA256),
        ):
            with self.subTest(carrier=name):
                document = self.document(name)
                content, _ = self.parts(document)
                entry = as_object(
                    next(
                        item
                        for item in self.manifest["carriers"]
                        if item["body"] == name
                    )
                )
                self.assertEqual(review_id, entry["review_id"])
                self.assertEqual(visible, self.exchange.sha256_text(content))
                self.assertEqual(body, self.exchange.sha256_text(document))
        self.assertEqual(REVIEWED_HEAD, self.manifest["reviewed_head"])
        self.assertEqual(ROUND_1_STATE, self.manifest["round_1_state_sha256"])
        self.assertEqual(AUTHOR_EVENT_STATE, self.manifest["author_event_state_sha256"])
        self.assertEqual(TERMINAL_STATE, self.manifest["terminal_state_sha256"])
        self.assertEqual(FINDING_ID, self.manifest["finding_id"])

    def test_1510_author_visible_completion_conflicts_with_structured_evidence(
        self,
    ) -> None:
        document = self.document(AUTHOR_BODY)
        content, original = self.parts(document)
        self.assertEqual(AUTHOR_VISIBLE, self.exchange.sha256_text(content))

        with self.assertRaises(self.exchange.ProtocolError) as caught:
            self.exchange.extract_carrier_pair(document)

        self.assertIn(
            "contradict the structured response evidence", str(caught.exception)
        )
        # The envelope and the visible-content digest are sound. Only the claim
        # that the carrier makes conflicts with its structured response.
        verified = self.exchange.verify_envelope(original)
        self.assertEqual(AUTHOR_EVENT_STATE, verified["state_sha256"])

    def test_1510_changed_visible_claims_remove_the_author_conflict(self) -> None:
        rebuilt = self.rebuild(
            self.document(AUTHOR_BODY),
            lambda state: None,
            visible=(
                "F-001 is fixed.\n\n"
                "The Issue 9 dictionary check was unavailable in this environment.\n"
            ),
        )

        _original, envelope = self.exchange.extract_carrier_pair(rebuilt)

        self.assertEqual("author_response", envelope["state"]["event_type"])
        self.assertEqual(
            REVIEWED_HEAD, envelope["state"]["artifact_binding"]["revision"]
        )

    def test_1510_changed_response_evidence_removes_the_author_conflict(self) -> None:
        def complete_check(state: dict[str, Any]) -> None:
            responses = state["responses"]
            responses[0]["evidence"][-1] = (
                "The full Issue 9 dictionary check ran on all four changed paths."
            )

        rebuilt = self.rebuild(self.document(AUTHOR_BODY), complete_check)

        _original, envelope = self.exchange.extract_carrier_pair(rebuilt)

        self.assertEqual(
            "The full Issue 9 dictionary check ran on all four changed paths.",
            envelope["state"]["responses"][0]["evidence"][-1],
        )

    def test_visible_claim_stays_valid_when_the_carrier_records_the_check_ran(
        self,
    ) -> None:
        def record_run(state: dict[str, Any]) -> None:
            state["responses"][0]["evidence"].append(
                "The external Issue 9 dictionary check ran and found no violations."
            )

        rebuilt = self.rebuild(
            self.document(AUTHOR_BODY),
            record_run,
            visible=(
                "F-001 is fixed.\n\n"
                "The external run completed the Issue 9 dictionary check with no "
                "violations.\n"
            ),
        )

        _original, envelope = self.exchange.extract_carrier_pair(rebuilt)

        self.assertEqual("author_response", envelope["state"]["event_type"])

    def test_visible_claim_for_another_check_stays_valid(self) -> None:
        rebuilt = self.rebuild(
            self.document(AUTHOR_BODY),
            lambda state: None,
            visible=(
                "F-001 is fixed.\n\n"
                "The Issue 9 dictionary check was unavailable.\n\n"
                "The Ruff checks pass on this head.\n"
            ),
        )

        _original, envelope = self.exchange.extract_carrier_pair(rebuilt)

        self.assertEqual(
            REVIEWED_HEAD, envelope["state"]["artifact_binding"]["revision"]
        )

    def test_1510_resolve_repeats_adverse_evidence(self) -> None:
        document = self.document(TERMINAL_BODY)
        content, original = self.parts(document)
        self.assertEqual(TERMINAL_VISIBLE, self.exchange.sha256_text(content))
        self.assertEqual(TERMINAL_STATE, original["state_sha256"])
        introduced = original["state"]["accepted_events"][0]["new_findings"][0]
        resolution = original["state"]["accepted_events"][2]["responses"][0]
        self.assertEqual("resolve", resolution["kind"])
        self.assertEqual(introduced["evidence"], resolution["evidence"])

        with self.assertRaises(self.exchange.ProtocolError) as caught:
            self.exchange.extract_carrier_pair(document)

        self.assertIn("must add closure evidence", str(caught.exception))

    def test_resolve_requires_evidence_that_supports_the_closure(self) -> None:
        cases = (
            ("introducing evidence only", [FINDING_EVIDENCE]),
            ("introducing and author evidence", [FINDING_EVIDENCE, AUTHOR_EVIDENCE]),
            ("one fresh closure item", [CLOSURE_EVIDENCE]),
        )
        for label, evidence in cases:
            with self.subTest(evidence=label):
                if label == "one fresh closure item":
                    closed = self.closure_state(evidence)
                    self.assertEqual(
                        "resolved", closed["state"]["findings"][0]["state"]
                    )
                    self.assertIn(
                        CLOSURE_EVIDENCE,
                        closed["state"]["findings"][0]["reviewer_response"]["evidence"],
                    )
                    continue
                answered = self.answered_state()
                with self.assertRaises(self.exchange.ProtocolError) as caught:
                    self.builders.reduce(
                        self.builders.review_event(
                            answered, "resolve", evidence=evidence
                        ),
                        answered,
                    )
                self.assertIn("closure evidence", str(caught.exception))

    def test_resolve_evidence_binds_head_and_condition(self) -> None:
        closed = self.closure_state([CLOSURE_EVIDENCE])
        self.assertEqual(
            closed["state"]["artifact_binding"]["revision"],
            closed["state"]["findings"][0]["author_response"]["artifact_revision"],
        )
        self.assertEqual(
            self.builders.finding()["closure_condition"],
            closed["state"]["findings"][0]["closure_condition"],
        )
        changes = (
            (
                "author artifact revision",
                lambda state: state["findings"][0]["author_response"].update(
                    {"artifact_revision": "revision-other"}
                ),
            ),
            (
                "state artifact revision",
                lambda state: state["artifact_binding"].update(
                    {"revision": "revision-other"}
                ),
            ),
            (
                "closure condition",
                lambda state: state["findings"][0].update(
                    {"closure_condition": "A different observable condition."}
                ),
            ),
            (
                "closure evidence",
                lambda state: state["findings"][0]["reviewer_response"].update(
                    {"evidence": [FINDING_EVIDENCE, AUTHOR_EVIDENCE]}
                ),
            ),
        )
        for label, change_state in changes:
            with (
                self.subTest(change=label),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.exchange.verify_envelope(self.tampered(closed, change_state))

    def test_changed_source_bindings_fail(self) -> None:
        closed = self.closure_state([CLOSURE_EVIDENCE])

        def change_binding(
            state: dict[str, Any], index: int, field: str, value: str
        ) -> None:
            state["accepted_events"][index]["artifact_binding"][field] = value

        for index in (0, 1):
            for field, value in (("revision", "revision-other"), ("sha256", "8" * 64)):
                with (
                    self.subTest(event=index, field=field),
                    self.assertRaises(self.exchange.ProtocolError),
                ):
                    self.exchange.verify_envelope(
                        self.tampered(
                            closed,
                            lambda state, i=index, f=field, v=value: change_binding(
                                state, i, f, v
                            ),
                        )
                    )
