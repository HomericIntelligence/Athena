"""Behavior contracts for complete review ledgers at provider body limits."""

from __future__ import annotations

import base64
import copy
import json
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
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

    def legacy_envelope(
        self, visible: str, kind: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Build a synthetic v1 record and its expected current envelope."""
        event = self.fixtures.initial_event()
        event["artifact_binding"]["visible_content_sha256"] = self.exchange.sha256_text(
            visible
        )
        current = self.fixtures.reduce(event)["envelope"]
        if kind == "author-event":
            answer = self.fixtures.author_event(current, "fix")
            answer["artifact_binding"]["visible_content_sha256"] = (
                self.exchange.sha256_text(visible)
            )
            current = self.fixtures.reduce(answer, current)["author_event"]
        legacy = copy.deepcopy(current)
        legacy["schema_version"] = 1
        if kind == "eligibility":
            legacy["state"]["go_eligible"] = True
            legacy_event = legacy["state"]["accepted_events"][0]
            legacy_event["go_eligible"] = True
            digest = self.exchange.sha256_json(
                {
                    "schema_id": "athena.review-exchange.event",
                    "schema_version": 1,
                    "event": legacy_event,
                }
            )
            legacy["state"]["accepted_event_sha256"] = digest
            legacy["state"]["progress"][0]["accepted_event_sha256"] = digest
            legacy["state_sha256"] = self.exchange.sha256_json(legacy["state"])
        return legacy, cast(dict[str, Any], current)

    def original_document(
        self,
        visible: str,
        envelope: dict[str, Any],
        *,
        compressed: bool = False,
        payload: bytes | None = None,
    ) -> str:
        """Encode original wire bytes without the current renderer."""
        raw = (
            self.exchange.canonical_json(envelope).encode("utf-8")
            if payload is None
            else payload
        )
        kind = envelope["schema_id"].rsplit(".", 1)[-1]
        fence = "athena-json-zlib-base64-v1" if compressed else "json"
        encoded = (
            base64.b64encode(zlib.compress(raw)).decode("ascii")
            if compressed
            else raw.decode("utf-8")
        )
        return (
            f"{visible}\n\n<!-- HomericIntelligence:review-exchange:v1 "
            f"kind={kind} sha256={envelope['state_sha256']} -->\n"
            f"```{fence}\n{encoded}\n```\n"
        )

    def test_original_v1_carriers_extract_without_rewrite(self) -> None:
        """Original v1 bytes must produce the supported normalized envelope."""
        visible = "Retained review evidence."
        for kind in ("state", "author-event", "eligibility"):
            legacy, expected = self.legacy_envelope(visible, kind)
            self.assertEqual(expected, self.exchange.verify_envelope(legacy))
            for compressed in (False, True):
                for final_newline in (False, True):
                    with self.subTest(
                        kind=kind, compressed=compressed, final_newline=final_newline
                    ):
                        document = self.original_document(
                            visible, legacy, compressed=compressed
                        )
                        if not final_newline:
                            document = document.removesuffix("\n")
                        actual = self.exchange.extract_carrier(document)
                        self.assertEqual(expected, actual)
                        if kind != "author-event":
                            answer = self.fixtures.author_event(actual, "fix")
                            self.assertEqual(
                                "accepted",
                                self.fixtures.reduce(answer, actual)["status"],
                            )

    def test_v1_marker_binds_the_original_state_digest(self) -> None:
        """An upgraded digest cannot replace the original marker digest."""
        visible = "Retained review evidence."
        legacy, expected = self.legacy_envelope(visible, "eligibility")
        self.assertNotEqual(legacy["state_sha256"], expected["state_sha256"])
        for compressed in (False, True):
            document = self.original_document(visible, legacy, compressed=compressed)
            for digest in ("0" * 64, expected["state_sha256"]):
                with (
                    self.subTest(compressed=compressed, digest=digest),
                    self.assertRaises(self.exchange.ProtocolError),
                ):
                    self.exchange.extract_carrier(
                        document.replace(legacy["state_sha256"], digest, 1)
                    )

    def test_v1_carriers_keep_strict_wire_and_history_checks(self) -> None:
        """A canonical checksum does not replace state and history validation."""
        visible = "Retained review evidence."
        for kind in ("state", "eligibility"):
            legacy, _expected = self.legacy_envelope(visible, kind)
            canonical = self.exchange.canonical_json(legacy)
            cases = {
                "spacing": json.dumps(legacy).encode(),
                "duplicate key": canonical.replace(
                    "{", '{"schema_version":1,', 1
                ).encode(),
            }
            for label in ("digest", "requirements", "unknown field", "version"):
                changed = copy.deepcopy(legacy)
                if label == "digest":
                    changed["state_sha256"] = "0" * 64
                elif label == "version":
                    changed["schema_version"] = 3
                else:
                    if label == "requirements":
                        changed["state"]["requirements_sha256"] = "d" * 64
                    else:
                        changed["state"]["unexpected"] = True
                    changed["state_sha256"] = self.exchange.sha256_json(
                        changed["state"]
                    )
                cases[label] = self.exchange.canonical_json(changed).encode()
            for compressed in (False, True):
                for label, payload in cases.items():
                    wire = json.loads(payload)
                    with (
                        self.subTest(kind=kind, compressed=compressed, label=label),
                        self.assertRaises(self.exchange.ProtocolError),
                    ):
                        self.exchange.extract_carrier(
                            self.original_document(
                                visible, wire, compressed=compressed, payload=payload
                            )
                        )
                document = self.original_document(
                    visible, legacy, compressed=compressed
                )
                with self.assertRaises(self.exchange.ProtocolError):
                    self.exchange.extract_carrier(
                        document.replace(visible, "Different review evidence.", 1)
                    )

    def test_legacy_replay_rejects_equal_values_with_different_json_types(self) -> None:
        """A legacy replay must preserve JSON types at each nested field."""
        visible = "Retained review evidence."
        legacy, _expected = self.legacy_envelope(visible, "eligibility")
        cases = (
            ("round Boolean", ("round",), True),
            ("round float", ("round",), 1.0),
            ("coverage integer", ("coverage_complete",), 1),
            ("progress round float", ("progress", 0, "round"), 1.0),
            ("finding Boolean", ("findings", 0, "material_architecture"), 0),
        )
        for label, path, value in cases:
            changed = copy.deepcopy(legacy)
            parent = changed["state"]
            for key in path[:-1]:
                parent = parent[key]
            self.assertIn(path[-1], parent)
            self.assertIsNot(type(parent[path[-1]]), type(value))
            parent[path[-1]] = value
            changed["state_sha256"] = self.exchange.sha256_json(changed["state"])
            with (
                self.subTest(label=label, operation="verify"),
                self.assertRaises(self.exchange.ProtocolError),
            ):
                self.exchange.verify_envelope(changed)
            for compressed in (False, True):
                with (
                    self.subTest(label=label, compressed=compressed),
                    self.assertRaises(self.exchange.ProtocolError),
                ):
                    self.exchange.extract_carrier(
                        self.original_document(visible, changed, compressed=compressed)
                    )

    def test_version_conversion_keeps_semantic_scope_order(self) -> None:
        """Canonical JSON must not admit a scope that needs normalization."""
        visible = "Author evidence."
        legacy, _expected = self.legacy_envelope(visible, "author-event")
        legacy["state"]["scope"] = ["path:z.py", "path:a.py"]
        legacy["state_sha256"] = self.exchange.sha256_json(legacy["state"])
        for version in (1, 2):
            legacy["schema_version"] = version
            normalized = self.exchange.verify_envelope(legacy)
            self.assertEqual(["path:a.py", "path:z.py"], normalized["state"]["scope"])
            for compressed in (False, True):
                with (
                    self.subTest(version=version, compressed=compressed),
                    self.assertRaises(self.exchange.ProtocolError),
                ):
                    self.exchange.extract_carrier(
                        self.original_document(visible, legacy, compressed=compressed)
                    )

    def test_cli_extracts_original_v1_input_and_preserves_files(self) -> None:
        """CLI verify and extract must agree without a carrier rewrite."""
        visible = "Retained review evidence."
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            for kind in ("state", "author-event", "eligibility"):
                legacy, expected = self.legacy_envelope(visible, kind)
                envelope_bytes = self.exchange.canonical_json(legacy).encode("utf-8")
                carrier_bytes = self.original_document(visible, legacy).encode("utf-8")
                envelope_path = root / "envelope.json"
                carrier_path = root / "carrier.md"
                envelope_path.write_bytes(envelope_bytes)
                carrier_path.write_bytes(carrier_bytes)
                for command, path in (
                    ("verify", envelope_path),
                    ("extract", carrier_path),
                ):
                    with self.subTest(kind=kind, command=command):
                        result = subprocess.run(
                            [sys.executable, str(fixtures.SCRIPT), command, str(path)],
                            capture_output=True,
                            text=True,
                            check=False,
                            timeout=10,
                        )
                        self.assertEqual(0, result.returncode, result.stderr)
                        self.assertEqual(expected, json.loads(result.stdout))
                self.assertEqual(envelope_bytes, envelope_path.read_bytes())
                self.assertEqual(carrier_bytes, carrier_path.read_bytes())

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
