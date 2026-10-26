"""Compressed-carrier recovery through the real delivery and controlled forge."""

from __future__ import annotations

import base64
import copy
import unittest
import zlib
from dataclasses import replace
from typing import Any
from unittest.mock import patch

from tests.unit import test_issue_review_exchange as issue_fixtures
from tests.unit import test_pr_review_go_delivery as fixtures


def alternate_compression(body: str) -> str:
    """Represent the same envelope with a different valid compressor output."""
    prefix, payload = body.split("```athena-json-zlib-base64-v1\n", 1)
    encoded, suffix = payload.split("\n", 1)
    raw = zlib.decompress(base64.b64decode(encoded, validate=True))
    alternate = base64.b64encode(zlib.compress(raw, level=1)).decode("ascii")
    return prefix + "```athena-json-zlib-base64-v1\n" + alternate + "\n" + suffix


class CompressedDeliveryTests(unittest.TestCase):
    """A different compressed representation cannot change delivery authority."""

    def setUp(self) -> None:
        self.delivery = fixtures.load_module()
        self.fixtures = fixtures.PrReviewGoDeliveryTests()
        self.fixtures.delivery = self.delivery
        self.fixtures.setUp()

    def test_no_go_recovers_a_valid_compressed_original(self) -> None:
        """An independently encoded original carrier still binds exact proof."""
        proof, record = self.fixtures.no_go_proof(
            finding_evidence=("controlled retained evidence; " * 1500,)
        )
        alternate = alternate_compression(record.body)
        self.assertNotEqual(record.body, alternate)
        self.assertEqual(
            proof.state_envelope,
            self.delivery.review_exchange.extract_carrier(alternate),
        )
        forge = fixtures.FakeForge(
            self.delivery,
            threads=self.fixtures.carrier_threads(
                proof.state_envelope, proof.review_id
            ),
        )
        forge.labels = {"state:implementation-go"}
        forge.reviews.append(replace(record, body=alternate))

        result = self.delivery.deliver_no_go(forge, self.fixtures.binding(), proof)

        self.assertEqual("delivered", result.status)
        self.assertEqual(1, forge.events.count("labels:no-go"))
        self.assertEqual(alternate, forge.reviews[0].body)

    def test_go_recovery_does_not_republish_a_compressed_terminal(self) -> None:
        """Recovery verifies the original body rather than recompressing it."""
        thread = self.fixtures.owned_thread()
        manifest = self.fixtures.v1_manifest(
            thread, state_finding_evidence=("controlled retained evidence; " * 1500,)
        )
        forge = fixtures.FakeForge(self.delivery, threads=(thread,))
        self.fixtures.add_history(forge, manifest)
        first = self.delivery.deliver_go_v1(forge, self.fixtures.binding(), manifest)
        self.assertEqual("delivered", first.status)
        terminal = forge.reviews[-1]
        alternate = alternate_compression(terminal.body)
        self.assertNotEqual(terminal.body, alternate)
        forge.reviews[-1] = replace(terminal, body=alternate)
        prior_events = list(forge.events)

        replay = self.delivery.deliver_go_v1(forge, self.fixtures.binding(), manifest)

        self.assertEqual("already_delivered", replay.status)
        self.assertEqual(
            [
                event
                for event in prior_events
                if event != "read" and event != "requirements:verify"
            ],
            [
                event
                for event in forge.events
                if event != "read" and event != "requirements:verify"
            ],
        )
        self.assertEqual(alternate, forge.reviews[-1].body)

    def test_compression_does_not_relax_original_review_authority(self) -> None:
        """Encoding cannot authorize a foreign, edited, duplicate, or stale review."""
        proof, record = self.fixtures.no_go_proof(
            finding_evidence=("controlled retained evidence; " * 1500,)
        )
        alternate = replace(record, body=alternate_compression(record.body))
        cases = {
            "foreign actor": (replace(alternate, viewer_did_author=False),),
            "edited": (replace(alternate, includes_created_edit=True),),
            "edit timestamp": (
                replace(alternate, last_edited_at="2026-01-02T00:00:00Z"),
            ),
            "stale head": (replace(alternate, head_oid="c" * 40),),
            "wrong kind": (replace(alternate, state="APPROVED"),),
            "duplicate": (alternate, replace(alternate, id="duplicate")),
            "visible tampering": (
                replace(
                    alternate, body=alternate.body.replace("Round 1", "Round 2", 1)
                ),
            ),
        }
        for label, records in cases.items():
            with self.subTest(label=label):
                forge = fixtures.FakeForge(
                    self.delivery,
                    threads=self.fixtures.carrier_threads(
                        proof.state_envelope, proof.review_id
                    ),
                )
                forge.labels = {"state:implementation-go"}
                forge.reviews.extend(records)
                with self.assertRaises(self.delivery.DeliveryError):
                    self.delivery.deliver_no_go(forge, self.fixtures.binding(), proof)
                self.assertNotIn("labels:no-go", forge.events)
                self.assertEqual({"state:implementation-go"}, forge.labels)

    def test_no_go_rechecks_exact_original_bytes_after_label_write(self) -> None:
        """Even an equivalent encoding cannot replace the captured original."""
        proof, record = self.fixtures.no_go_proof(
            finding_evidence=("controlled retained evidence; " * 1500,)
        )
        forge = fixtures.FakeForge(
            self.delivery,
            threads=self.fixtures.carrier_threads(
                proof.state_envelope, proof.review_id
            ),
        )
        forge.labels = {"state:implementation-go"}
        forge.reviews.append(replace(record, body=alternate_compression(record.body)))
        original_write = forge.set_implementation_no_go

        def change_body_after_write() -> None:
            original_write()
            forge.reviews[0] = record

        with (
            patch.object(forge, "set_implementation_no_go", change_body_after_write),
            self.assertRaisesRegex(
                self.delivery.DeliveryError, "carrier changed"
            ) as caught,
        ):
            self.delivery.deliver_no_go(forge, self.fixtures.binding(), proof)
        self.assertEqual("partial", caught.exception.report.status)
        self.assertTrue(caught.exception.report.recovery_read_required)

    def test_new_publication_still_requires_exact_prepared_bytes(self) -> None:
        """A changed posted body is not accepted as an equivalent recovery."""
        thread = self.fixtures.owned_thread()
        manifest = self.fixtures.v1_manifest(
            thread, state_finding_evidence=("controlled retained evidence; " * 1500,)
        )
        forge = fixtures.FakeForge(self.delivery, threads=(thread,))
        self.fixtures.add_history(forge, manifest)
        original_publish = forge.publish_terminal

        def publish_with_changed_body(
            body: str, head_oid: str, comments: tuple[Any, ...]
        ) -> None:
            original_publish(body, head_oid, comments)
            record = forge.reviews[-1]
            forge.reviews[-1] = replace(record, body=alternate_compression(record.body))

        with (
            patch.object(forge, "publish_terminal", publish_with_changed_body),
            self.assertRaises(self.delivery.DeliveryError) as caught,
        ):
            self.delivery.deliver_go_v1(forge, self.fixtures.binding(), manifest)
        self.assertEqual("partial", caught.exception.report.status)
        self.assertNotIn("labels", forge.events)

    def test_closure_reads_retain_the_selected_terminal_identity(self) -> None:
        """A carrier replacement must stop delivery before thread resolution."""
        for phase, change in (
            ("reply", "compression"),
            ("before resolution", "compression"),
            ("reply", "review ID"),
        ):
            with self.subTest(phase=phase, change=change):
                self.assert_closure_replacement_rejected(phase, change)

    def assert_closure_replacement_rejected(self, phase: str, change: str) -> None:
        """Keep each callback bound to one controlled forge and replacement."""
        thread = self.fixtures.owned_thread()
        manifest = self.fixtures.v1_manifest(
            thread,
            state_finding_evidence=("controlled retained evidence; " * 1500,),
        )
        forge = fixtures.FakeForge(self.delivery, threads=(thread,))
        self.fixtures.add_history(forge, manifest)
        original_reply = forge.reply
        original_snapshot = forge.snapshot
        reply_read = False
        replaced = False

        def replace_terminal() -> None:
            nonlocal replaced
            terminal = forge.reviews[-1]
            if change == "compression":
                alternate = alternate_compression(terminal.body)
                self.assertNotEqual(terminal.body, alternate)
                self.assertEqual(
                    self.delivery.review_exchange.extract_carrier(terminal.body),
                    self.delivery.review_exchange.extract_carrier(alternate),
                )
                forge.reviews[-1] = replace(terminal, body=alternate)
            else:
                forge.reviews[-1] = replace(terminal, id="replacement-review")
            replaced = True

        def reply_with_replacement(thread_id: str, body: str) -> None:
            original_reply(thread_id, body)
            if phase == "reply":
                replace_terminal()

        def snapshot_with_replacement() -> Any:
            nonlocal reply_read
            if phase == "before resolution" and f"reply:{thread.id}" in forge.events:
                if reply_read and not replaced:
                    replace_terminal()
                reply_read = True
            return original_snapshot()

        with (
            patch.object(forge, "reply", reply_with_replacement),
            patch.object(forge, "snapshot", snapshot_with_replacement),
            self.assertRaises(self.delivery.DeliveryError) as caught,
        ):
            self.delivery.deliver_go_v1(forge, self.fixtures.binding(), manifest)
        self.assertTrue(replaced)
        self.assertEqual("partial", caught.exception.report.status)
        self.assertNotIn(f"resolve:{thread.id}", forge.events)
        self.assertFalse(forge.threads[thread.id].is_resolved)
        self.assertNotIn("labels", forge.events)

    def test_compressed_recovery_retains_conversation_digest(self) -> None:
        """A new encoding cannot bypass the retained source-thread receipt."""
        thread = self.fixtures.owned_thread()
        manifest = self.fixtures.v1_manifest(
            thread, state_finding_evidence=("controlled retained evidence; " * 1500,)
        )
        forge = fixtures.FakeForge(self.delivery, threads=(thread,))
        self.fixtures.add_history(forge, manifest)
        self.delivery.deliver_go_v1(forge, self.fixtures.binding(), manifest)
        terminal = forge.reviews[-1]
        forge.reviews[-1] = replace(terminal, body=alternate_compression(terminal.body))
        current = forge.threads[thread.id]
        forge.threads[thread.id] = replace(
            current,
            comments=(
                replace(current.comments[0], body="Changed original"),
                *current.comments[1:],
            ),
        )
        old_events = list(forge.events)
        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(forge, self.fixtures.binding(), manifest)
        self.assertEqual(1, old_events.count("labels"))
        self.assertEqual(old_events.count("labels"), forge.events.count("labels"))

    def test_plain_recovery_keeps_its_exact_body_requirement(self) -> None:
        """The legacy accepted fence-ending variant is not an exact proof body."""
        proof, record = self.fixtures.no_go_proof()
        without_newline = record.body.removesuffix("\n")
        self.assertEqual(
            proof.state_envelope,
            self.delivery.review_exchange.extract_carrier(without_newline),
        )
        forge = fixtures.FakeForge(
            self.delivery,
            threads=self.fixtures.carrier_threads(
                proof.state_envelope, proof.review_id
            ),
        )
        forge.labels = {"state:implementation-go"}
        forge.reviews.append(replace(record, body=without_newline))
        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_no_go(forge, self.fixtures.binding(), proof)
        self.assertNotIn("labels:no-go", forge.events)

    def test_issue_publication_retains_exact_compressed_body_receipt(self) -> None:
        """The issue consumer verifies raw prepared bytes after publication."""
        fixture = issue_fixtures.IssueReviewExchangeTests()
        adapter = issue_fixtures.load_module()
        fixture.adapter = adapter
        source = fixture.no_go_snapshot()
        prepared = adapter.prepare_plan(
            fixture.plan_request(
                source,
                content="## Plan\n\nAdd and verify the five-round guard.",
                responses=[
                    {
                        "finding_id": "F-001",
                        "kind": "fix",
                        "evidence": ["controlled retained issue evidence; " * 2000],
                        "tradeoff": None,
                    }
                ],
            )
        )
        body = prepared["operation"]["body"]
        alternate = alternate_compression(body)
        self.assertNotEqual(body, alternate)
        self.assertEqual(
            adapter.review_exchange.extract_carrier(body),
            adapter.review_exchange.extract_carrier(alternate),
        )
        published = fixture.apply_operation(source, prepared, "unused")
        verified = adapter.verify_publication(
            {"prepared": prepared, "snapshot": published}
        )
        self.assertEqual("verified", verified["status"])

        changed = copy.deepcopy(published)
        comment = next(item for item in changed["comments"] if item["body"] == body)
        comment["body"] = alternate
        unknown = adapter.verify_publication(
            {"prepared": prepared, "snapshot": changed}
        )
        self.assertEqual("unknown_outcome", unknown["status"])
        self.assertIsNone(unknown["receipt"])


if __name__ == "__main__":
    unittest.main()
