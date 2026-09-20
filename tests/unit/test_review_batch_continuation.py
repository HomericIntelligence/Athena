"""Behavior tests for bounded review batches and reassessment."""

from __future__ import annotations

import io
import unittest
from hashlib import sha256
from types import ModuleType

from tests.unit import test_pr_review_go_delivery as delivery_tests
from tests.unit.test_review_exchange import ReviewExchangeTests


class ReviewBatchContinuationTests(unittest.TestCase):
    fixture: ReviewExchangeTests
    exchange: ModuleType

    @classmethod
    def setUpClass(cls) -> None:
        ReviewExchangeTests.setUpClass()
        cls.fixture = ReviewExchangeTests()
        cls.exchange = cls.fixture.exchange

    def test_reassessment_allows_sixth_review(self) -> None:
        state = self.fixture.initial_state()
        for number in range(2, 7):
            answered = self.fixture.reduce(
                self.fixture.author_event(state, "fix"), state
            )["envelope"]
            event = self.fixture.review_event(
                answered,
                "resolve" if number == 6 else "still_present",
                round_number=number,
            )
            if number == 5:
                event["reassessment"] = (
                    "The new regression isolates the remaining failure; apply the local correction."
                )
            state = self.fixture.reduce(event, answered)["envelope"]
            if number == 5:
                delivery = delivery_tests.load_module()
                inferred = delivery._infer_reviewer_event(answered, state, None)
                replayed = self.fixture.reduce(inferred, answered)["envelope"]
                self.assertEqual(state, replayed)
        self.assertEqual("GO", state["state"]["verdict"])
        self.assertEqual(6, state["state"]["round"])
        self.assertEqual(state, self.exchange.verify_envelope(state))

    def batch_stream(
        self, count: int, *, complete: bool = True, changed_source: bool = False
    ) -> io.BytesIO:
        lines = []
        digest = sha256()
        for index in range(1, count + 1):
            findings = [
                self.fixture.finding(
                    f"F-{n:03d}", disposition="suggestion", severity="minor"
                )
                for n in range(1, 51)
            ]
            for finding in findings:
                finding["evidence"] = ["verified source " * 300]
            event = self.fixture.initial_event(
                findings=findings, exchange_id=f"review-batch-{index}"
            )
            if changed_source and index == count:
                event["artifact_binding"]["revision"] = "other-revision"
            envelope = self.fixture.reduce(event)["envelope"]
            encoded = self.exchange.canonical_json(envelope).encode()
            self.assertLess(len(encoded), self.exchange.MAX_INPUT_BYTES)
            digest.update(encoded + b"\n")
            lines.append(encoded)
        if complete:
            lines.append(
                self.exchange.canonical_json(
                    {
                        "schema_id": "athena.review-exchange.batch-end",
                        "schema_version": 1,
                        "batch_count": count,
                        "batches_sha256": digest.hexdigest(),
                    }
                ).encode()
            )
        return io.BytesIO(b"\n".join(lines) + b"\n")

    def test_prepare_batches_preserves_all_findings(self) -> None:
        template = self.fixture.initial_event(findings=[], exchange_id="prepared")
        lines = [self.exchange.canonical_json({"event": template})]
        lines.extend(
            self.exchange.canonical_json(
                self.fixture.finding(
                    f"F-{number:03d}", disposition="suggestion", severity="minor"
                )
            )
            for number in range(1, 126)
        )
        output = io.BytesIO()
        self.exchange.prepare_batches(
            io.BytesIO(("\n".join(lines) + "\n").encode()), output
        )
        output.seek(0)
        result = self.exchange.verify_batches(output)
        self.assertEqual(125, result["finding_count"])
        self.assertEqual(2, result["batch_count"])
        self.assertEqual("GO", result["verdict"])

    def test_complete_stream_exceeds_individual_bounds(self) -> None:
        stream = self.batch_stream(4)
        self.assertGreater(len(stream.getvalue()), self.exchange.MAX_INPUT_BYTES)
        result = self.exchange.verify_batches(stream)
        self.assertEqual("GO", result["verdict"])
        self.assertEqual(200, result["finding_count"])
        self.assertEqual(4, result["batch_count"])

    def test_incomplete_stream_cannot_report_go(self) -> None:
        result = self.exchange.verify_batches(self.batch_stream(2, complete=False))
        self.assertEqual("NO-GO", result["verdict"])
        self.assertFalse(result["complete"])

    def test_source_drift_is_rejected(self) -> None:
        with self.assertRaisesRegex(self.exchange.ProtocolError, "binding"):
            self.exchange.verify_batches(self.batch_stream(2, changed_source=True))

    def test_duplicate_or_missing_batch_is_rejected(self) -> None:
        stream = self.batch_stream(2)
        lines = stream.getvalue().splitlines(keepends=True)
        with self.assertRaises(self.exchange.ProtocolError):
            self.exchange.verify_batches(io.BytesIO(lines[0] + lines[0] + lines[-1]))
        with self.assertRaises(self.exchange.ProtocolError):
            self.exchange.verify_batches(io.BytesIO(lines[0] + lines[-1]))


if __name__ == "__main__":
    unittest.main()
