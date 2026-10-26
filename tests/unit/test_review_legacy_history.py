"""Original version-1 histories retain their complete review chain."""

from __future__ import annotations

import base64
import copy
import unittest
import zlib
from dataclasses import replace
from types import ModuleType
from typing import Any

from tests.unit import test_pr_review_go_delivery as delivery_fixtures
from tests.unit import test_review_exchange as fixtures


def original_document(
    visible: str, envelope: dict[str, Any], *, compressed: bool
) -> str:
    """Encode synthetic historical bytes without the current renderer."""
    import json

    raw = json.dumps(
        envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    payload = (
        base64.b64encode(zlib.compress(raw.encode())).decode() if compressed else raw
    )
    fence = "athena-json-zlib-base64-v1" if compressed else "json"
    kind = envelope["schema_id"].rsplit(".", 1)[-1]
    return (
        f"{visible}\n\n<!-- HomericIntelligence:review-exchange:v1 "
        f"kind={kind} sha256={envelope['state_sha256']} -->\n"
        f"```{fence}\n{payload}\n```\n"
    )


def legacy_prefixes(
    exchange: ModuleType, terminal: dict[str, Any], *, go_eligible: bool = True
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Project ordinary synthetic events onto the original version-1 format."""
    states: dict[str, dict[str, Any]] = {}
    authors: dict[str, dict[str, Any]] = {}
    prior: dict[str, Any] | None = None
    old_prior: dict[str, Any] | None = None
    old_events: list[dict[str, Any]] = []
    event_digests: dict[str, str] = {}
    for event in terminal["state"]["accepted_events"]:
        result = exchange.reduce_request({"previous": prior, "event": event})
        current = result["envelope"]
        old_event = copy.deepcopy(event)
        old_event["prior_state_sha256"] = (
            None if old_prior is None else old_prior["state_sha256"]
        )
        if old_event["event_type"] == "reviewer_assessment":
            old_event["go_eligible"] = go_eligible
        old_events.append(old_event)
        old_digest = exchange.sha256_json(
            {
                "schema_id": "athena.review-exchange.event",
                "schema_version": 1,
                "event": old_event,
            }
        )
        event_digests[current["state"]["accepted_event_sha256"]] = old_digest
        old_state = copy.deepcopy(current["state"])
        old_state["go_eligible"] = go_eligible
        old_state["accepted_events"] = copy.deepcopy(old_events)
        old_state["prior_state_sha256"] = old_event["prior_state_sha256"]
        old_state["accepted_event_sha256"] = old_digest
        for progress in old_state["progress"]:
            progress["accepted_event_sha256"] = event_digests[
                progress["accepted_event_sha256"]
            ]
        old_envelope = {
            "schema_id": current["schema_id"],
            "schema_version": 1,
            "state": old_state,
            "state_sha256": exchange.sha256_json(old_state),
        }
        states[current["state_sha256"]] = old_envelope
        if result["author_event"] is not None:
            author = copy.deepcopy(result["author_event"])
            author["schema_version"] = 1
            author["state"]["prior_state_sha256"] = old_event["prior_state_sha256"]
            author["state_sha256"] = exchange.sha256_json(author["state"])
            authors[result["author_event"]["state_sha256"]] = author
        prior, old_prior = current, old_envelope
    return states, authors


class LegacyHistoryTests(unittest.TestCase):
    """The migration must prove old bytes before it changes digest links."""

    def setUp(self) -> None:
        self.exchange = fixtures.load_module()
        self.fixtures = fixtures.ReviewExchangeTests()
        self.fixtures.exchange = self.exchange

    def history(self) -> list[dict[str, Any]]:
        initial = self.fixtures.initial_state()
        answer = self.fixtures.reduce(
            self.fixtures.author_event(initial, "fix"), initial
        )["envelope"]
        partial = self.fixtures.reduce(
            self.fixtures.review_event(answer, "partial"), answer
        )["envelope"]
        second = self.fixtures.reduce(
            self.fixtures.author_event(partial, "fix"), partial
        )["envelope"]
        complete = self.fixtures.reduce(
            self.fixtures.review_event(second, "resolve", round_number=3), second
        )["envelope"]
        return [initial, answer, partial, second, complete]

    def test_complete_ordinary_legacy_prefixes_preserve_all_state(self) -> None:
        history = self.history()
        originals, _ = legacy_prefixes(self.exchange, history[-1])
        for expected in history:
            original = originals[expected["state_sha256"]]
            saved = copy.deepcopy(original)
            with self.subTest(events=len(expected["state"]["accepted_events"])):
                self.assertEqual(expected, self.exchange.verify_envelope(original))
                self.assertEqual(saved, original)

    def test_plain_and_compressed_history_preserve_original_carrier(self) -> None:
        visible = "Retained review evidence."
        initial_event = self.fixtures.initial_event()
        initial_event["artifact_binding"]["visible_content_sha256"] = (
            self.exchange.sha256_text(visible)
        )
        initial = self.fixtures.reduce(initial_event)["envelope"]
        event = self.fixtures.author_event(initial, "fix")
        event["artifact_binding"]["visible_content_sha256"] = self.exchange.sha256_text(
            visible
        )
        answered = self.fixtures.reduce(event, initial)["envelope"]
        review = self.fixtures.review_event(answered, "partial")
        expected = self.fixtures.reduce(review, answered)["envelope"]
        originals, _ = legacy_prefixes(self.exchange, expected)
        original = originals[expected["state_sha256"]]
        for compressed in (False, True):
            document = original_document(visible, original, compressed=compressed)
            with self.subTest(compressed=compressed):
                self.assertEqual(expected, self.exchange.extract_carrier(document))
                self.assertIn(original["state_sha256"], document)

    def test_legacy_history_rejects_changed_state_links_and_json_types(self) -> None:
        expected = self.history()[2]
        originals, _ = legacy_prefixes(self.exchange, expected)
        original = originals[expected["state_sha256"]]
        cases = (
            (("round",), 2.0),
            (("progress", 0, "round"), True),
            (("findings", 0, "closure_revision"), True),
            (("findings", 0, "closure_condition"), "A different closure."),
            (("requirements_sha256",), "d" * 64),
            (("accepted_events", 1, "prior_state_sha256"), "d" * 64),
            (("accepted_events", 2, "round"), 2.0),
            (("accepted_events", 2, "go_eligible"), 1),
            (("accepted_events",), original["state"]["accepted_events"][1:]),
            (("accepted_events",), original["state"]["accepted_events"][:-1]),
        )
        for path, value in cases:
            changed = copy.deepcopy(original)
            parent = changed["state"]
            for key in path[:-1]:
                parent = parent[key]
            parent[path[-1]] = value
            changed["state_sha256"] = self.exchange.sha256_json(changed["state"])
            with (
                self.subTest(path=path),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.exchange.verify_envelope(changed)

    def test_unsupported_legacy_authority_and_conditional_histories_stay_closed(
        self,
    ) -> None:
        partial = self.history()[2]
        conditional, _ = legacy_prefixes(self.exchange, partial, go_eligible=False)
        initial = self.fixtures.initial_state()
        answer = self.fixtures.reduce(
            self.fixtures.author_event(initial, "risk_acceptance"), initial
        )["envelope"]
        human = self.fixtures.reduce(
            self.fixtures.human_event(answer, "accept_risk"), answer
        )["envelope"]
        authority, _ = legacy_prefixes(self.exchange, human)
        for original in (
            conditional[partial["state_sha256"]],
            authority[human["state_sha256"]],
        ):
            with (
                self.subTest(phase=original["state"]["phase"]),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.exchange.verify_envelope(original)


class LegacyDeliveryTests(unittest.TestCase):
    """Published v1 edges must lead to the same current delivery decision."""

    def setUp(self) -> None:
        self.delivery = delivery_fixtures.load_module()
        self.fixtures = delivery_fixtures.PrReviewGoDeliveryTests()
        self.fixtures.delivery = self.delivery
        self.fixtures.setUp()

    def historical_case(self, case: str) -> tuple[Any, Any, Any]:
        if case == "refresh":
            forge, binding, manifest = self.fixtures.chained_author_manifest()
        else:
            binding, threads, manifest = self.fixtures.round_three_manifest()
            forge = delivery_fixtures.FakeForge(self.delivery, threads=threads)
            forge.head_oid = "c" * 40
            self.fixtures.add_history(forge, manifest)
        exchange = self.delivery.review_exchange
        states, authors = legacy_prefixes(exchange, manifest.state_envelope)
        records = []
        for record in forge.reviews:
            envelope = exchange.extract_carrier(record.body)
            original = (
                states if envelope["schema_id"] == exchange.STATE_SCHEMA_ID else authors
            )[envelope["state_sha256"]]
            visible = record.body.split(
                "\n\n<!-- HomericIntelligence:review-exchange:v1", 1
            )[0]
            records.append(
                replace(
                    record, body=original_document(visible, original, compressed=True)
                )
            )
        forge.reviews[:] = records
        return forge, binding, manifest

    def test_delivery_replays_original_review_and_author_carriers(self) -> None:
        for case in ("refresh", "round three"):
            with self.subTest(case=case):
                forge, binding, manifest = self.historical_case(case)
                originals = tuple(forge.reviews)
                result = self.delivery.deliver_go_v1(forge, binding, manifest)
                self.assertEqual("delivered", result.status)
                self.assertEqual(originals, tuple(forge.reviews[:-1]))
                self.assertEqual(1, forge.events.count("terminal"))
                self.assertEqual(1, forge.events.count("labels"))
                self.assertTrue(
                    all(thread.is_resolved for thread in forge.threads.values())
                )

    def test_migration_keeps_forge_identity_order_and_missing_edge_checks(self) -> None:
        for defect in (
            "foreign",
            "edited",
            "head",
            "order",
            "missing author",
            "duplicate",
        ):
            forge, binding, manifest = self.historical_case("round three")
            if defect == "foreign":
                forge.reviews[0] = replace(forge.reviews[0], viewer_did_author=False)
            elif defect == "edited":
                forge.reviews[0] = replace(forge.reviews[0], includes_created_edit=True)
            elif defect == "head":
                forge.reviews[0] = replace(forge.reviews[0], head_oid="d" * 40)
            elif defect == "order":
                forge.reviews[-1] = replace(
                    forge.reviews[-1], submitted_at="2025-01-01T00:00:00Z"
                )
            elif defect == "missing author":
                del forge.reviews[1]
            else:
                forge.reviews.append(replace(forge.reviews[0], id="duplicate"))
            with (
                self.subTest(defect=defect),
                self.assertRaises(self.delivery.DeliveryError),
            ):
                self.delivery.deliver_go_v1(forge, binding, manifest)
            self.assertNotIn("terminal", forge.events)
            self.assertNotIn("labels", forge.events)

    def test_current_author_event_can_continue_a_verified_legacy_state(self) -> None:
        forge, binding, manifest = self.historical_case("round three")
        current_records = self.fixtures.carrier_history[
            manifest.state_envelope["state_sha256"]
        ]
        forge.reviews[-1] = current_records[-1]
        result = self.delivery.deliver_go_v1(forge, binding, manifest)
        self.assertEqual("delivered", result.status)
        self.assertEqual(1, forge.events.count("labels"))

    def test_old_digest_cannot_authorize_a_current_event_or_changed_answer(
        self,
    ) -> None:
        for defect in (
            "current version",
            "requirements",
            "target",
            "prior digest",
            "answer",
        ):
            forge, binding, manifest = self.historical_case("round three")
            record = forge.reviews[1]
            # The independent raw decoder retains the old edge under test.
            payload = record.body.split("```athena-json-zlib-base64-v1\n", 1)[1].split(
                "\n", 1
            )[0]
            import json

            original = json.loads(zlib.decompress(base64.b64decode(payload)))
            if defect == "current version":
                original["schema_version"] = 2
            elif defect == "requirements":
                original["state"]["requirements_sha256"] = "d" * 64
            elif defect == "target":
                original["state"]["target"]["number"] = 8
                original["state"]["target"]["url"] = (
                    "https://github.com/owner/repository/pull/8"
                )
            elif defect == "prior digest":
                original["state"]["prior_state_sha256"] = "d" * 64
            else:
                original["state"]["responses"][0]["evidence"] = [
                    "A changed author answer."
                ]
            original["state_sha256"] = self.delivery.review_exchange.sha256_json(
                original["state"]
            )
            visible = record.body.split(
                "\n\n<!-- HomericIntelligence:review-exchange:v1", 1
            )[0]
            forge.reviews[1] = replace(
                record, body=original_document(visible, original, compressed=True)
            )
            with (
                self.subTest(defect=defect),
                self.assertRaises(self.delivery.DeliveryError),
            ):
                self.delivery.deliver_go_v1(forge, binding, manifest)
            self.assertNotIn("terminal", forge.events)
            self.assertNotIn("labels", forge.events)

    def test_compressed_recovery_does_not_equate_different_source_envelopes(
        self,
    ) -> None:
        proof, record = self.fixtures.no_go_proof()
        exchange = self.delivery.review_exchange
        current = proof.state_envelope
        legacy, _ = legacy_prefixes(exchange, current)
        visible = record.body.split(
            "\n\n<!-- HomericIntelligence:review-exchange:v1", 1
        )[0]
        left = original_document(visible, current, compressed=True)
        right = original_document(
            visible, legacy[current["state_sha256"]], compressed=True
        )
        self.assertEqual(
            exchange.extract_carrier(left), exchange.extract_carrier(right)
        )
        self.assertFalse(self.delivery._same_compressed_carrier(left, right))
