"""Behavior contracts for complete review ledgers at provider body limits."""

from __future__ import annotations

import base64
import copy
import json
import unittest
import zlib
from typing import Any, cast
from unittest.mock import patch

from tests.unit import test_review_exchange as fixtures


class ReviewCarrierTransportTests(unittest.TestCase):
    """Use the real reducer and carrier boundary with controlled evidence text."""

    def setUp(self) -> None:
        self.exchange = fixtures.load_module()
        self.fixtures = fixtures.ReviewExchangeTests()
        self.fixtures.exchange = self.exchange

    def large_history(self, visible: str) -> dict[str, Any]:
        """Build three valid events with distinct retained evidence records."""
        finding = self.fixtures.finding()
        finding["evidence"] = ["controlled initial evidence; " * 800]
        event = self.fixtures.initial_event(findings=[finding])
        event["artifact_binding"]["visible_content_sha256"] = self.exchange.sha256_text(
            visible
        )
        initial = self.fixtures.reduce(event)["envelope"]
        answer = self.fixtures.author_event(initial, "fix")
        answer["artifact_binding"]["visible_content_sha256"] = (
            self.exchange.sha256_text(visible)
        )
        answer["responses"][0]["evidence"] = ["controlled author evidence; " * 600]
        answered = self.fixtures.reduce(answer, initial)["envelope"]
        review = self.fixtures.review_event(
            answered, "partial", evidence=["controlled current evidence; " * 600]
        )
        return cast(dict[str, Any], self.fixtures.reduce(review, answered)["envelope"])

    def test_large_history_round_trips_without_losing_events(self) -> None:
        """An oversized plain envelope must fit without changing its history."""
        visible = "The correction still needs the remaining required evidence."
        envelope = self.large_history(visible)
        original = copy.deepcopy(envelope)
        self.assertEqual(3, len(envelope["state"]["accepted_events"]))
        self.assertGreater(
            len(self.exchange.canonical_json(envelope).encode("utf-8")),
            self.exchange.PROVIDER_BODY_LIMITS["github"],
        )

        rendered = self.exchange.render_carrier(visible, envelope, "state")
        extracted = self.exchange.extract_carrier(rendered)

        self.assertLessEqual(
            len(rendered.encode("utf-8")),
            self.exchange.PROVIDER_BODY_LIMITS["github"],
        )
        self.assertEqual(original, extracted)
        self.assertEqual(original, envelope)
        next_answer = self.fixtures.author_event(original, "fix")
        self.assertEqual(
            self.fixtures.reduce(next_answer, original),
            self.fixtures.reduce(next_answer, extracted),
        )

    def compressed_document(
        self, visible: str, envelope: dict[str, Any], raw: bytes
    ) -> str:
        """Encode a controlled transport to exercise the public reader boundary."""
        payload = base64.b64encode(raw).decode("ascii")
        return (
            f"{visible}\n\n<!-- HomericIntelligence:review-exchange:v1 "
            f"kind=state sha256={envelope['state_sha256']} -->\n"
            f"```athena-json-zlib-base64-v1\n{payload}\n```\n"
        )

    def test_small_carrier_preserves_the_original_wire_bytes(self) -> None:
        """The new renderer must preserve the existing machine-consumed format."""
        visible = "Legacy review."
        event = self.fixtures.initial_event()
        event["artifact_binding"]["visible_content_sha256"] = self.exchange.sha256_text(
            visible
        )
        envelope = self.fixtures.reduce(event)["envelope"]
        original = (
            f"{visible}\n\n<!-- HomericIntelligence:review-exchange:v1 "
            f"kind=state sha256={envelope['state_sha256']} -->\n```json\n"
            f"{self.exchange.canonical_json(envelope)}\n```\n"
        )
        self.assertEqual(
            original, self.exchange.render_carrier(visible, envelope, "state")
        )
        self.assertEqual(envelope, self.exchange.extract_carrier(original))

    def test_large_author_event_preserves_its_original_envelope(self) -> None:
        """Author-event carriers use the same complete transport contract."""
        initial = self.fixtures.initial_state()
        visible = "Author response with complete retained evidence."
        event = self.fixtures.author_event(initial, "fix")
        event["artifact_binding"]["visible_content_sha256"] = self.exchange.sha256_text(
            visible
        )
        event["responses"][0]["evidence"] = ["controlled author diagnostic; " * 2500]
        envelope = self.fixtures.reduce(event, initial)["author_event"]
        self.assertGreater(len(self.exchange.canonical_json(envelope)), 65_536)
        body = self.exchange.render_carrier(visible, envelope, "author-event")
        self.assertLessEqual(len(body.encode()), 65_536)
        self.assertEqual(envelope, self.exchange.extract_carrier(body))

    def test_reader_accepts_other_valid_compression_streams(self) -> None:
        """A producer's compressor version must not change envelope identity."""
        visible = "Review evidence."
        envelope = self.large_history(visible)
        raw = self.exchange.canonical_json(envelope).encode("utf-8")
        for level in (0, 1, 9):
            with self.subTest(level=level):
                document = self.compressed_document(
                    visible, envelope, zlib.compress(raw, level)
                )
                if len(document.encode()) > 65_536:
                    with self.assertRaises(self.exchange.ProtocolError):
                        self.exchange.extract_carrier(document)
                else:
                    self.assertEqual(envelope, self.exchange.extract_carrier(document))

    def test_compressed_payload_rejects_invalid_or_extra_streams(self) -> None:
        """Only one complete bounded stream can reach JSON verification."""
        visible = "Review evidence."
        envelope = self.large_history(visible)
        raw = self.exchange.canonical_json(envelope).encode("utf-8")
        compressed = zlib.compress(raw)
        cases = {
            "empty": b"",
            "invalid": b"not zlib",
            "truncated": compressed[:-1],
            "concatenated": compressed + compressed,
            "trailing": compressed + b"trailing bytes",
            "expanded size": zlib.compress(b"x" * (self.exchange.MAX_INPUT_BYTES + 1)),
        }
        for label, payload in cases.items():
            with (
                self.subTest(label=label),
                patch.object(
                    self.exchange,
                    "parse_json_bytes",
                    side_effect=AssertionError(
                        "JSON reached before transport validation"
                    ),
                ),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.exchange.extract_carrier(
                    self.compressed_document(visible, envelope, payload)
                )

    def test_compressed_payload_preserves_canonical_json_and_digests(self) -> None:
        """Compression must not admit ambiguous JSON or a changed state."""
        visible = "Review evidence."
        envelope = self.large_history(visible)
        canonical = self.exchange.canonical_json(envelope)
        changed = copy.deepcopy(envelope)
        changed["state"]["accepted_events"][0]["new_findings"][0]["evidence"] = [
            "changed"
        ]
        cases = {
            "whitespace": json.dumps(envelope).encode(),
            "duplicate key": canonical.replace(
                "{", '{"schema_id":"duplicate",', 1
            ).encode(),
            "changed ledger": self.exchange.canonical_json(changed).encode(),
            "nonfinite": b'{"state":NaN}',
            "invalid UTF8": b"\xff",
            "invalid JSON": b"{",
        }
        for label, payload in cases.items():
            with (
                self.subTest(label=label),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.exchange.extract_carrier(
                    self.compressed_document(visible, envelope, zlib.compress(payload))
                )

    def test_transport_rejects_base64_fence_and_visible_tampering(self) -> None:
        """The new fence retains marker, visible-content, and finality checks."""
        visible = "Review evidence."
        envelope = self.large_history(visible)
        body = self.exchange.render_carrier(visible, envelope, "state")
        prefix, _payload = body.split("```athena-json-zlib-base64-v1\n", 1)
        cases = [
            prefix + "```athena-json-zlib-base64-v1\nAB==\n```\n",
            prefix + "```athena-json-zlib-base64-v1\n$not-base64\n```\n",
            prefix + "```athena-json-zlib-base64-v1\né\n```\n",
            body.replace("base64-v1", "base64-v2"),
            body.replace("Review evidence.", "Altered evidence."),
            body.replace("kind=state", "kind=author-event"),
            body.replace(envelope["state_sha256"], "0" * 64, 1),
            body + "trailing text",
            body + body,
        ]
        for candidate in cases:
            with (
                self.subTest(tail=candidate[-60:]),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.exchange.extract_carrier(candidate)

    def test_render_preserves_the_decoded_input_bound(self) -> None:
        """Highly compressible oversized input must remain unpublishable."""
        visible = "Review evidence."
        finding = self.fixtures.finding()
        finding["evidence"] = ["x" * self.exchange.MAX_INPUT_BYTES]
        event = self.fixtures.initial_event(findings=[finding])
        event["artifact_binding"]["visible_content_sha256"] = self.exchange.sha256_text(
            visible
        )
        envelope = self.fixtures.reduce(event)["envelope"]
        with self.assertRaisesRegex(self.exchange.ProtocolError, "larger than 1 MiB"):
            self.exchange.render_carrier(visible, envelope, "state")


if __name__ == "__main__":
    unittest.main()
