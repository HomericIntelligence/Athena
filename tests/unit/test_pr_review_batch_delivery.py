"""Delivery requires complete, source-bound review batches."""

from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from types import ModuleType
from typing import Any

from tests.unit import test_pr_review_go_delivery as fixtures


class PrReviewBatchDeliveryTests(unittest.TestCase):
    delivery: ModuleType

    @classmethod
    def setUpClass(cls) -> None:
        fixtures.PrReviewGoDeliveryTests.setUpClass()
        cls.delivery = fixtures.PrReviewGoDeliveryTests.delivery

    def setUp(self) -> None:
        self.fixture = fixtures.PrReviewGoDeliveryTests()
        self.fixture.setUp()
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)

    def fixture_batches(self, *, complete: bool = True) -> tuple[Any, Any, list[Any]]:
        exchange = self.delivery.review_exchange
        seed, _ = self.fixture.terminal_inline_manifest()
        visible = self.delivery.terminal_visible_content(self.fixture.binding(), ())
        template = seed.state_envelope["state"]["accepted_events"][0]
        envelopes = []
        for number in (1, 2):
            event = {
                **template,
                "exchange_id": f"task-batch-{number}",
                "new_findings": [],
                "artifact_binding": {
                    **template["artifact_binding"],
                    "visible_content_sha256": exchange.sha256_text(visible),
                },
            }
            envelopes.append(
                exchange.reduce_request({"previous": None, "event": event})["envelope"]
            )
        digest = sha256()
        lines = []
        for envelope in envelopes:
            line = exchange.canonical_json(envelope).encode() + b"\n"
            digest.update(line)
            lines.append(line)
        if complete:
            lines.append(
                (
                    exchange.canonical_json(
                        {
                            "schema_id": "athena.review-exchange.batch-end",
                            "schema_version": 1,
                            "batch_count": 2,
                            "batches_sha256": digest.hexdigest(),
                        }
                    )
                    + "\n"
                ).encode()
            )
        path = Path(self.temporary.name) / "batches.jsonl"
        path.write_bytes(b"".join(lines))
        manifest = replace(
            seed,
            state_envelope=envelopes[-1],
            comments=(),
            batch_manifest_path=path,
            batch_manifest_sha256=digest.hexdigest(),
        )
        forge = fixtures.FakeForge(self.delivery, threads=())
        forge.reviews.append(
            self.fixture.carrier_record("batch-1", envelopes[0], visible)
        )
        return forge, manifest, envelopes

    def test_complete_published_batches_allow_terminal_delivery(self) -> None:
        forge, manifest, _ = self.fixture_batches()
        result = self.delivery.deliver_go_v1(forge, self.fixture.binding(), manifest)
        self.assertEqual("delivered", result.status)
        self.assertIn("state:implementation-go", forge.labels)

    def test_missing_batch_receipt_withholds_before_mutation(self) -> None:
        forge, manifest, _ = self.fixture_batches(complete=False)
        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(forge, self.fixture.binding(), manifest)
        self.assertEqual(1, len(forge.reviews))
        self.assertNotIn("state:implementation-go", forge.labels)

    def test_batch_evidence_cannot_authorize_an_unrelated_exchange(self) -> None:
        forge, manifest, envelopes = self.fixture_batches()
        event = dict(envelopes[0]["state"]["accepted_events"][0])
        event["exchange_id"] = "unrelated"
        other = self.delivery.review_exchange.reduce_request(
            {"previous": None, "event": event}
        )["envelope"]
        forge.reviews.append(
            self.fixture.carrier_record(
                "unrelated", other, manifest.terminal_visible_content
            )
        )
        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(forge, self.fixture.binding(), manifest)
        self.assertEqual(2, len(forge.reviews))
        self.assertNotIn("state:implementation-go", forge.labels)

    def test_batch_stream_digest_is_bound_to_manifest(self) -> None:
        forge, manifest, _ = self.fixture_batches()
        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(
                forge,
                self.fixture.binding(),
                replace(manifest, batch_manifest_sha256="0" * 64),
            )
        self.assertEqual(1, len(forge.reviews))

    def test_foreign_open_thread_still_blocks_batch_delivery(self) -> None:
        forge, manifest, _ = self.fixture_batches()
        thread = self.fixture.thread()
        forge.threads[thread.id] = thread
        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(forge, self.fixture.binding(), manifest)
        self.assertEqual(1, len(forge.reviews))

    def test_every_other_batch_must_have_an_exact_published_carrier(self) -> None:
        forge, manifest, _ = self.fixture_batches()
        forge.reviews.clear()
        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(forge, self.fixture.binding(), manifest)
        self.assertEqual([], forge.reviews)

    def test_changed_source_and_incomplete_coverage_cannot_deliver(self) -> None:
        for mode in ("source", "coverage"):
            with self.subTest(mode=mode):
                forge, manifest, envelopes = self.fixture_batches()
                exchange = self.delivery.review_exchange
                event = dict(envelopes[0]["state"]["accepted_events"][0])
                if mode == "source":
                    event["artifact_binding"] = {
                        **event["artifact_binding"],
                        "sha256": "4" * 64,
                    }
                else:
                    event["coverage_complete"] = False
                envelopes[0] = exchange.reduce_request(
                    {"previous": None, "event": event}
                )["envelope"]
                lines = [
                    exchange.canonical_json(item).encode() + b"\n" for item in envelopes
                ]
                digest = sha256(b"".join(lines)).hexdigest()
                lines.append(
                    (
                        exchange.canonical_json(
                            {
                                "schema_id": "athena.review-exchange.batch-end",
                                "schema_version": 1,
                                "batch_count": 2,
                                "batches_sha256": digest,
                            }
                        )
                        + "\n"
                    ).encode()
                )
                manifest.batch_manifest_path.write_bytes(b"".join(lines))
                with self.assertRaises(self.delivery.DeliveryError):
                    self.delivery.deliver_go_v1(
                        forge,
                        self.fixture.binding(),
                        replace(manifest, batch_manifest_sha256=digest),
                    )
                self.assertEqual(1, len(forge.reviews))
                self.assertNotIn("state:implementation-go", forge.labels)

    def test_manifest_preserves_optional_batch_reference(self) -> None:
        _, manifest, _ = self.fixture_batches()
        document = self.delivery.closure_manifest_document(
            self.fixture.binding(), manifest
        )
        path = Path(self.temporary.name) / "closure.json"
        path.write_text(self.delivery.review_exchange.canonical_json(document))
        loaded = self.delivery.load_response_manifest(path, self.fixture.binding())
        self.assertEqual(manifest.batch_manifest_path, loaded.batch_manifest_path)
        self.assertEqual(manifest.batch_manifest_sha256, loaded.batch_manifest_sha256)
