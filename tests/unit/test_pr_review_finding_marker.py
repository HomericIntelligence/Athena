"""Behavior tests for the shared finding-marker gate and legacy recovery."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any, cast
from unittest.mock import patch

from tests.unit import test_pr_review_go_delivery as fixtures

ROOT = Path(__file__).resolve().parents[2]
PUBLISHER_SCRIPT = ROOT / "skills" / "pr-review" / "scripts" / "publish_round.py"
MARKER = (
    "<!-- HomericIntelligence:review-finding:v1 exchange={exchange} id={finding} -->"
)


def load_publisher() -> ModuleType:
    """Load the round publisher as a test module."""
    sys.path.insert(0, str(PUBLISHER_SCRIPT.parent))
    try:
        name = f"test_publish_round_{id(PUBLISHER_SCRIPT)}"
        spec = importlib.util.spec_from_file_location(name, PUBLISHER_SCRIPT)
        if spec is None or spec.loader is None:
            raise RuntimeError("The round publisher cannot be loaded.")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(PUBLISHER_SCRIPT.parent))


class FakePublisherForge:
    """Record one round publication and expose its exact readback."""

    def __init__(self, module: ModuleType, binding: Any, body: str) -> None:
        self.delivery = module.deliver_go
        self.module = module
        self.binding = binding
        self.body = body
        self.calls: list[tuple[str, tuple[dict[str, Any], ...]]] = []
        self.reviews: list[Any] = []
        self.threads: dict[str, Any] = {}

    def publish_round_batch(
        self, body: str, head_oid: str, comments: tuple[dict[str, Any], ...]
    ) -> str:
        """Record the atomic batch write and return the created review identity."""
        self.calls.append((body, tuple(dict(comment) for comment in comments)))
        review = self.delivery.ReviewRecord(
            id="round-review",
            body=body,
            head_oid=head_oid,
            author="reviewer",
            viewer_did_author=True,
            includes_created_edit=False,
            state="COMMENTED",
            submitted_at="2026-01-01T00:05:00Z",
        )
        self.reviews = [review]
        review_id: str = review.id
        for index, comment in enumerate(comments, start=1):
            comment_id = f"root-{index}"
            self.threads[comment_id] = self.delivery.ReviewThread(
                id=f"thread-{index}",
                is_resolved=False,
                comments=(
                    self.delivery.ReviewComment(
                        id=comment_id,
                        body=comment["body"],
                        author="reviewer",
                        viewer_did_author=True,
                        review_head_oid=head_oid,
                        review_id=review.id,
                        path=comment["path"],
                        side=comment["side"],
                        line=comment["line"],
                        original_line=comment["line"],
                    ),
                ),
                viewer_can_reply=True,
                viewer_can_resolve=True,
            )
        return review_id

    def snapshot(self) -> Any:
        """Return the exact readback for the recorded publication."""
        return self.delivery.PullRequestSnapshot(
            repository=self.binding.repository,
            number=self.binding.number,
            url=self.binding.url,
            state="OPEN",
            is_draft=False,
            base_oid=self.binding.base_oid,
            head_oid=self.binding.head_oid,
            labels=frozenset(),
            threads=tuple(self.threads.values()),
            reviews=tuple(self.reviews),
        )


class PrReviewFindingMarkerTests(unittest.TestCase):
    delivery: ModuleType
    publisher: ModuleType

    @classmethod
    def setUpClass(cls) -> None:
        fixtures.PrReviewGoDeliveryTests.setUpClass()
        cls.delivery = fixtures.PrReviewGoDeliveryTests.delivery
        cls.publisher = load_publisher()

    def setUp(self) -> None:
        self.fixture = fixtures.PrReviewGoDeliveryTests()
        self.fixture.setUp()
        self.exchange = self.delivery.review_exchange
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)

    # ------------------------------------------------------------------
    # Shared placement rule.
    # ------------------------------------------------------------------
    def marker(self, finding: str = "F-001", exchange: str = "exchange-7") -> str:
        """Return one well-formed marker line."""
        return str(MARKER.format(exchange=exchange, finding=finding))

    def batch(
        self,
        *,
        exchange_id: str = "exchange-7",
        bodies: tuple[str, ...] | None = None,
        comments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Return one inline finding batch document."""
        if comments is None:
            bodies = bodies or (
                f"First finding.\n\n{self.marker('F-001', exchange_id)}",
            )
            comments = [
                {
                    "path": "src/example.py",
                    "side": "RIGHT",
                    "line": index + 1,
                    "body": body,
                }
                for index, body in enumerate(bodies)
            ]
        return {
            "schema_id": "athena.review-exchange.finding-batch",
            "schema_version": 1,
            "exchange_id": exchange_id,
            "comments": comments,
        }

    def placement_cases(self) -> list[tuple[str, str, str]]:
        """Return malformed and well-formed bodies with their expected diagnostics."""
        marker = self.marker()
        native = '<span class="finding">This finding is inside an HTML block.</span>'
        return [
            ("marker-first-line", f"{marker}\n\nThe finding text.", "not final"),
            (
                "marker-mid-body",
                f"First line.\n{marker}\nLast line.",
                "not final",
            ),
            (
                "marker-repeated",
                f"Text.\n{marker}\n{marker}",
                "malformed or repeated",
            ),
            (
                "marker-in-open-fence",
                f"Text.\n\n```text\n{marker}\n",
                "inside an open Markdown block",
            ),
            (
                "marker-indented-in-list",
                f"Text.\n\n- item\n  {marker}",
                "malformed or repeated",
            ),
            (
                "marker-not-top-level",
                f"<div>\n{native}\n</div>\n{marker}",
                "not a top-level line",
            ),
            ("no-marker", "The finding text without a marker.", ""),
            ("well-formed", f"Text.\n\n{marker}", ""),
        ]

    def test_shared_placement_rule_accepts_and_rejects_exact_bodies(self) -> None:
        """The shared rule accepts only one final top-level marker line."""
        for name, body, expected in self.placement_cases():
            with self.subTest(case=name):
                if expected:
                    with self.assertRaises(self.exchange.ProtocolError) as caught:
                        self.exchange.verify_finding_marker(body)
                    self.assertIn(expected, str(caught.exception))
                else:
                    identity = self.exchange.verify_finding_marker(body)
                    self.assertEqual(
                        None if "without a marker" in body else ("exchange-7", "F-001"),
                        identity,
                    )

    def test_delivery_marker_adapter_preserves_every_diagnostic(self) -> None:
        """The delivery adapter reports the shared rule without new wording."""
        for name, body, expected in self.placement_cases():
            if not expected:
                continue
            with self.subTest(case=name):
                comment = self.delivery.ReviewComment(
                    id="root", body=body, author="reviewer"
                )
                with self.assertRaises(self.delivery.DeliveryError) as caught:
                    self.delivery._finding_marker(comment)
                self.assertIn(expected, str(caught.exception))

    def test_shared_marker_rule_rejects_a_non_text_body(self) -> None:
        """A non-text body is not a marker carrier."""
        with self.assertRaises(self.exchange.ProtocolError):
            self.exchange.verify_finding_marker(cast(Any, object()))

    # ------------------------------------------------------------------
    # Pre-publication batch gate.
    # ------------------------------------------------------------------
    def batch_cases(self) -> list[tuple[str, dict[str, Any], str]]:
        """Return invalid batch documents with their expected diagnostics."""
        oversized = "x" * (self.exchange.PROVIDER_BODY_LIMITS["github"] + 1)
        marker = self.marker()
        cases = [
            (
                "batch-marker-uses-another-exchange",
                self.batch(
                    exchange_id="other-exchange",
                    bodies=(f"Text.\n\n{self.marker()}",),
                ),
                "no exact exchange finding marker",
            ),
            (
                "no-marker",
                self.batch(
                    comments=[
                        {"path": "a.py", "side": "RIGHT", "line": 1, "body": "Text."}
                    ]
                ),
                "no exact exchange finding marker",
            ),
            (
                "duplicate-finding-ids",
                self.batch(
                    bodies=(
                        f"First.\n\n{marker}",
                        f"Second.\n\n{marker}",
                    )
                ),
                "unique and ordered",
            ),
            (
                "unsorted-finding-ids",
                self.batch(
                    bodies=(
                        f"First.\n\n{self.marker('F-002')}",
                        f"Second.\n\n{self.marker('F-001')}",
                    )
                ),
                "unique and ordered",
            ),
            (
                "oversized-body",
                self.batch(
                    comments=[
                        {
                            "path": "a.py",
                            "side": "RIGHT",
                            "line": 1,
                            "body": f"{marker}\n\n{oversized}",
                        }
                    ]
                ),
                "exceeds the GitHub body limit",
            ),
            (
                "absolute-path",
                self.batch(
                    comments=[
                        {
                            "path": "/etc/passwd",
                            "side": "RIGHT",
                            "line": 1,
                            "body": f"Text.\n\n{marker}",
                        }
                    ]
                ),
                "not repository-relative",
            ),
            (
                "invalid-side",
                self.batch(
                    comments=[
                        {
                            "path": "a.py",
                            "side": "BOTH",
                            "line": 1,
                            "body": f"Text.\n\n{marker}",
                        }
                    ]
                ),
                "unsupported value",
            ),
            (
                "zero-line",
                self.batch(
                    comments=[
                        {
                            "path": "a.py",
                            "side": "RIGHT",
                            "line": 0,
                            "body": f"Text.\n\n{marker}",
                        }
                    ]
                ),
                "at least 1",
            ),
            ("unknown-field", {**self.batch(), "extra": 1}, "invalid fields"),
            (
                "unsupported-schema",
                {**self.batch(), "schema_id": "athena.review-exchange.other"},
                "schema is not supported",
            ),
        ]
        cases[0] = (
            "marker-exchange-id-mismatch",
            self.batch(
                exchange_id="other-exchange",
                bodies=(f"Text.\n\n{self.marker()}",),
            ),
            "no exact exchange finding marker",
        )
        return cases

    def test_prepublication_gate_accepts_a_well_formed_batch(self) -> None:
        """One ordered, bounded, marked batch passes the shared gate."""
        result = self.exchange.verify_finding_batch(
            self.batch(
                bodies=(
                    f"First.\n\n{self.marker('F-001')}",
                    f"Second.\n\n{self.marker('F-002')}",
                )
            )
        )

        self.assertEqual(
            "athena.review-exchange.finding-batch-result", result["schema_id"]
        )
        self.assertEqual(2, result["comment_count"])
        self.assertEqual(["F-001", "F-002"], result["finding_ids"])
        self.assertRegex(str(result["bodies_sha256"]), r"^[0-9a-f]{64}$")

    def test_prepublication_gate_accepts_an_empty_comment_array(self) -> None:
        """A round with no new inline findings keeps an empty comment array."""
        result = self.exchange.verify_finding_batch(self.batch(comments=[]))

        self.assertEqual(0, result["comment_count"])
        self.assertEqual([], result["finding_ids"])

    def test_prepublication_gate_rejects_each_invalid_batch(self) -> None:
        """Every malformed batch is rejected while it is still correctable."""
        for name, document, expected in self.batch_cases():
            with self.subTest(case=name):
                with self.assertRaises(self.exchange.ProtocolError) as caught:
                    self.exchange.verify_finding_batch(document)
                self.assertIn(expected, str(caught.exception))

    def test_prepublication_gate_rejects_too_many_comments(self) -> None:
        """A batch above the finding limit is rejected."""
        marker = self.marker()
        document = self.batch(
            comments=[
                {
                    "path": "a.py",
                    "side": "RIGHT",
                    "line": index + 1,
                    "body": f"Text.\n\n{marker}",
                }
                for index in range(self.exchange.MAX_FINDINGS + 1)
            ]
        )

        with self.assertRaises(self.exchange.ProtocolError) as caught:
            self.exchange.verify_finding_batch(document)

        self.assertIn("too many inline findings", str(caught.exception))

    def test_verify_finding_batch_cli_exits_nonzero_and_publishes_nothing(self) -> None:
        """A nonzero subcommand exit prints one diagnostic and no result."""
        output = io.StringIO()
        errors = io.StringIO()
        document = self.batch(
            comments=[{"path": "a.py", "side": "RIGHT", "line": 1, "body": "Text."}]
        )
        with (
            patch.object(self.publisher.deliver_go, "GitHubForge") as forge,
            redirect_stdout(output),
            redirect_stderr(errors),
        ):
            status = self.exchange.main(
                ["verify-finding-batch", self.write_json(document)]
            )

        self.assertEqual(1, status)
        self.assertEqual("", output.getvalue())
        self.assertEqual(1, len(errors.getvalue().strip().splitlines()))
        forge.assert_not_called()

    def test_verify_finding_batch_cli_prints_the_result_document(self) -> None:
        """A well-formed batch prints its canonical result document."""
        output = io.StringIO()
        with redirect_stdout(output):
            status = self.exchange.main(
                ["verify-finding-batch", self.write_json(self.batch())]
            )

        self.assertEqual(0, status)
        self.assertEqual(
            1, self.exchange.verify_finding_batch(self.batch())["comment_count"]
        )
        self.assertEqual(1, json.loads(output.getvalue())["comment_count"])

    # ------------------------------------------------------------------
    # Round publisher.
    # ------------------------------------------------------------------
    def write_json(self, document: Any, name: str = "document.json") -> str:
        """Write one canonical JSON document and return its path."""
        path = Path(self.temporary.name) / name
        path.write_text(self.exchange.canonical_json(document) + "\n", encoding="utf-8")
        return str(path)

    def write_text(self, text: str, name: str) -> str:
        """Write one UTF-8 document and return its path."""
        path = Path(self.temporary.name) / name
        path.write_text(text, encoding="utf-8")
        return str(path)

    def publisher_inputs(self, *, batch: dict[str, Any] | None = None) -> list[str]:
        """Return the publisher arguments for one round-1 reviewer carrier."""
        binding, _threads, manifest = self.fixture.round_three_manifest()
        initial = self.exchange.extract_carrier(
            self.fixture.carrier_history[manifest.state_envelope["state_sha256"]][
                0
            ].body
        )
        revision = initial["state"]["artifact_binding"]["revision"]
        self.publisher_binding = replace(binding, head_oid=revision)
        self.publisher_manifest = manifest
        carrier = self.exchange.render_carrier("Round 1 review.", initial, "state")
        return [
            "--target-repository",
            binding.repository,
            "--expected-pr-url",
            binding.url,
            "--expected-base-oid",
            binding.base_oid,
            "--expected-head-oid",
            revision,
            "--state-carrier-file",
            self.write_text(carrier, "carrier.md"),
            "--batch-file",
            self.write_json(batch if batch is not None else self.batch(), "batch.json"),
            str(binding.number),
        ]

    def run_publisher(
        self,
        batch: dict[str, Any] | None = None,
        *,
        forge_class: type[FakePublisherForge] = FakePublisherForge,
    ) -> tuple[int, str, str]:
        """Run the publisher with a recording forge and capture its streams."""
        arguments = self.publisher_inputs(batch=batch)
        binding = self.publisher_binding
        carrier = Path(
            arguments[arguments.index("--state-carrier-file") + 1]
        ).read_text(encoding="utf-8")
        recorder = forge_class(self.publisher, binding, carrier)
        self.recorder = recorder
        output, errors = io.StringIO(), io.StringIO()
        with (
            patch.object(
                self.publisher.deliver_go, "GitHubForge", return_value=recorder
            ),
            redirect_stdout(output),
            redirect_stderr(errors),
        ):
            status = self.publisher.main(arguments)
        return status, output.getvalue(), errors.getvalue()

    def test_publisher_publishes_and_verifies_one_well_formed_batch(self) -> None:
        """A valid batch makes one atomic write and verifies the readback."""
        batch = self.batch(
            bodies=(
                f"First.\n\n{self.marker('F-001', 'exchange-7')}",
                f"Second.\n\n{self.marker('F-002', 'exchange-7')}",
            )
        )
        status, output, errors = self.run_publisher(batch)

        self.assertEqual(0, status, errors)
        self.assertEqual(1, len(self.recorder.calls))
        document = json.loads(output)
        self.assertEqual("published", document["status"])
        self.assertEqual(2, document["comment_count"])
        self.assertEqual("round-review", document["review_id"])

    def test_publisher_refuses_every_malformed_batch_without_a_write(self) -> None:
        """Each malformed batch is refused before any provider call."""
        cases: dict[str, Callable[[], dict[str, Any]]] = {
            "marker-first-line": lambda: self.batch(
                bodies=(f"{self.marker()}\n\nThe finding text.",)
            ),
            "marker-repeated": lambda: self.batch(
                bodies=(f"Text.\n{self.marker()}\n{self.marker()}",)
            ),
            "marker-in-open-fence": lambda: self.batch(
                bodies=(f"Text.\n\n```text\n{self.marker()}\n",)
            ),
            "marker-indented-in-list": lambda: self.batch(
                bodies=(f"Text.\n\n- item\n  {self.marker()}",)
            ),
            "marker-not-top-level": lambda: self.batch(
                bodies=(f"<div>\n<span>Text.</span>\n</div>\n{self.marker()}",)
            ),
            "no-marker": lambda: self.batch(
                comments=[{"path": "a.py", "side": "RIGHT", "line": 1, "body": "Text."}]
            ),
            "marker-exchange-id-mismatch": lambda: self.batch(
                exchange_id="other-exchange"
            ),
            "duplicate-finding-ids": lambda: self.batch(
                bodies=(f"First.\n\n{self.marker()}", f"Second.\n\n{self.marker()}")
            ),
            "unsorted-finding-ids": lambda: self.batch(
                bodies=(
                    f"First.\n\n{self.marker('F-002')}",
                    f"Second.\n\n{self.marker('F-001')}",
                )
            ),
        }
        for name, build in cases.items():
            with self.subTest(case=name):
                status, output, errors = self.run_publisher(build())
                self.assertEqual(1, status)
                self.assertEqual("", output)
                self.assertEqual(1, len(errors.strip().splitlines()))
                self.assertEqual([], self.recorder.calls)

    def test_publisher_refuses_a_batch_for_another_exchange(self) -> None:
        """A batch whose exchange differs from the carrier is refused pre-write."""
        status, output, errors = self.run_publisher(self.batch(exchange_id="other"))

        self.assertEqual(1, status)
        self.assertEqual("", output)
        self.assertIn("different exchange ID", errors)
        self.assertEqual([], self.recorder.calls)

    def test_publisher_refuses_an_unbound_carrier_without_a_write(self) -> None:
        """A carrier that is not the requested review head is refused."""
        arguments = self.publisher_inputs()
        path = Path(arguments[arguments.index("--state-carrier-file") + 1])
        body = path.read_text(encoding="utf-8")
        envelope = self.exchange.extract_carrier(body)
        other = self.exchange.reduce_request(
            {
                "previous": None,
                "event": {
                    **envelope["state"]["accepted_events"][0],
                    "artifact_binding": {
                        **envelope["state"]["artifact_binding"],
                        "revision": "d" * 40,
                    },
                },
            }
        )["envelope"]
        path.write_text(
            self.exchange.render_carrier("Round 1 review.", other, "state"),
            encoding="utf-8",
        )
        recorder = FakePublisherForge(self.publisher, self.publisher_binding, "unused")
        output, errors = io.StringIO(), io.StringIO()
        with (
            patch.object(
                self.publisher.deliver_go, "GitHubForge", return_value=recorder
            ),
            redirect_stdout(output),
            redirect_stderr(errors),
        ):
            status = self.publisher.main(arguments)

        self.assertEqual(1, status)
        self.assertIn("not bound to the requested pull request", errors.getvalue())
        self.assertEqual([], recorder.calls)

    def test_publisher_withholds_when_the_readback_body_changes(self) -> None:
        """A readback that does not match the published body withholds the result."""

        class DriftingForge(FakePublisherForge):
            def publish_round_batch(
                self, body: str, head_oid: str, comments: tuple[dict[str, Any], ...]
            ) -> str:
                """Publish one batch whose stored body later drifts."""
                review_id = super().publish_round_batch(body, head_oid, comments)
                self.reviews = [replace(self.reviews[0], body=body + "\ndrift")]
                return review_id

        status, output, errors = self.run_publisher(forge_class=DriftingForge)

        self.assertEqual(1, status)
        self.assertEqual("", output)
        self.assertIn("changed during readback", errors)

    def test_publisher_withholds_when_a_readback_root_is_missing(self) -> None:
        """A batch whose readback lacks one root withholds the result."""

        class DroppingForge(FakePublisherForge):
            def publish_round_batch(
                self, body: str, head_oid: str, comments: tuple[dict[str, Any], ...]
            ) -> str:
                """Publish one batch and drop its readback threads."""
                review_id = super().publish_round_batch(body, head_oid, comments)
                self.threads.clear()
                return review_id

        status, _output, errors = self.run_publisher(forge_class=DroppingForge)

        self.assertEqual(1, status)
        self.assertIn("exact inline batch", errors)

    def run_with_arguments(self, arguments: list[str]) -> tuple[int, str, str]:
        """Run the publisher with prepared arguments and a recording forge."""
        recorder = FakePublisherForge(self.publisher, self.publisher_binding, "unused")
        self.recorder = recorder
        output, errors = io.StringIO(), io.StringIO()
        with (
            patch.object(
                self.publisher.deliver_go, "GitHubForge", return_value=recorder
            ),
            redirect_stdout(output),
            redirect_stderr(errors),
        ):
            status = self.publisher.main(arguments)
        return status, output.getvalue(), errors.getvalue()

    def test_publisher_refuses_an_unreadable_or_invalid_carrier(self) -> None:
        """A missing or malformed state carrier is refused before any write."""
        arguments = self.publisher_inputs()
        index = arguments.index("--state-carrier-file") + 1
        cases = {
            "missing": (str(Path(self.temporary.name) / "absent.md"), "cannot be read"),
            "malformed": (self.write_text("not a carrier", "bad.md"), "is invalid"),
        }
        for name, (path, message) in cases.items():
            with self.subTest(case=name):
                changed = list(arguments)
                changed[index] = path
                status, output, errors = self.run_with_arguments(changed)
                self.assertEqual(1, status)
                self.assertEqual("", output)
                self.assertIn(message, errors)
                self.assertEqual([], self.recorder.calls)

    def test_publisher_refuses_an_anchor_source_without_an_annex(self) -> None:
        """An anchor source needs a publication anchor annex in the carrier."""
        arguments = [*self.publisher_inputs(), "--anchor-source", "anchors.json"]
        status, output, errors = self.run_with_arguments(arguments)

        self.assertEqual(1, status)
        self.assertEqual("", output)
        self.assertIn("no publication anchor annex", errors)
        self.assertEqual([], self.recorder.calls)

    def test_publisher_withholds_for_each_invalid_readback(self) -> None:
        """Each readback that differs from the publication withholds the result."""

        def drift(change: Callable[[Any], None]) -> type[FakePublisherForge]:
            class DriftForge(FakePublisherForge):
                def publish_round_batch(
                    self,
                    body: str,
                    head_oid: str,
                    comments: tuple[dict[str, Any], ...],
                ) -> str:
                    """Publish one batch, then change its readback."""
                    review_id = super().publish_round_batch(body, head_oid, comments)
                    change(self)
                    return review_id

            return DriftForge

        def drop_review(forge: Any) -> None:
            forge.reviews = []

        def foreign_author(forge: Any) -> None:
            forge.reviews = [replace(forge.reviews[0], viewer_did_author=False)]

        def invalid_side(forge: Any) -> None:
            for key, thread in forge.threads.items():
                root = replace(thread.comments[0], side="MIDDLE")
                forge.threads[key] = replace(thread, comments=(root,))

        def no_marker(forge: Any) -> None:
            for key, thread in forge.threads.items():
                root = replace(thread.comments[0], body="Text without a marker.")
                forge.threads[key] = replace(thread, comments=(root,))

        def other_review_root(forge: Any) -> None:
            for key, thread in forge.threads.items():
                root = replace(thread.comments[0], review_id="other-review")
                forge.threads[key] = replace(thread, comments=(root,))
            forge.threads["empty"] = replace(
                next(iter(forge.threads.values())), comments=()
            )

        cases = {
            "no-review": (drop_review, "no unique readback record"),
            "foreign-author": (foreign_author, "changed during readback"),
            "invalid-side": (invalid_side, "invalid readback anchor"),
            "no-marker": (no_marker, "no exact exchange finding marker"),
            "other-review-root": (other_review_root, "exact inline batch"),
        }
        for name, (change, message) in cases.items():
            with self.subTest(case=name):
                status, output, errors = self.run_publisher(forge_class=drift(change))
                self.assertEqual(1, status)
                self.assertEqual("", output)
                self.assertIn(message, errors)

    def test_publisher_checks_the_anchor_annex_and_inline_comment_shape(self) -> None:
        """The annex must bind the reviewed identity and each comment must be valid."""
        self.publisher_inputs()
        binding = self.publisher_binding
        delivery_error = self.publisher.deliver_go.DeliveryError
        annex = {"head_oid": binding.head_oid, "base_oid": binding.base_oid}
        with patch.object(
            self.publisher.anchor_proofs, "visible_manifest", return_value=annex
        ):
            self.publisher._verify_anchor_annex("visible", Path("a.json"), binding)
            with self.assertRaisesRegex(delivery_error, "not bound"):
                self.publisher._verify_anchor_annex(
                    "visible",
                    None,
                    replace(binding, base_oid="e" * 40),
                )
        with (
            patch.object(
                self.publisher.anchor_proofs,
                "visible_manifest",
                side_effect=ValueError("x"),
            ),
            self.assertRaisesRegex(delivery_error, "x"),
        ):
            self.publisher._verify_anchor_annex("visible", None, binding)
        with self.assertRaisesRegex(delivery_error, "invalid inline comment"):
            self.publisher._readback_anchor(
                {"path": "a.py", "side": "MIDDLE", "line": 1, "body": "Text."}
            )

    # ------------------------------------------------------------------
    # Legacy malformed-batch recovery.
    # ------------------------------------------------------------------
    def misplaced_batch_fixture(self) -> tuple[Any, Any, Any, dict[str, Any]]:
        """Return one two-root malformed round-1 batch and its forge."""
        binding, threads, manifest = self.fixture.round_three_manifest()
        malformed = []
        for thread, number in zip(threads, (1, 2), strict=True):
            root = thread.comments[0]
            malformed.append(
                replace(
                    root,
                    body=(f"{self.marker(f'F-00{number}')}\n\nFinding {number}."),
                    author_association="NONE",
                    published_at="2026-01-01T00:00:01Z",
                    full_database_id=str(40 + number),
                )
            )
        repaired_threads = tuple(
            replace(thread, comments=(root,))
            for thread, root in zip(threads, malformed, strict=True)
        )
        forge = fixtures.FakeForge(self.delivery, threads=repaired_threads)
        forge.head_oid = binding.head_oid
        self.fixture.add_history(forge, manifest)
        self.malformed_threads = repaired_threads
        self.round_one_state = self.exchange.extract_carrier(forge.reviews[0].body)
        return forge, binding, manifest, self.round_one_state

    def repaired_manifest(
        self, forge: Any, manifest: Any, receipts: tuple[dict[str, Any], ...]
    ) -> Any:
        """Return the closure ledger prepared after the recorded repairs."""
        entries = tuple(
            replace(
                entry,
                conversation_sha256=self.delivery.conversation_sha256(
                    forge.threads[entry.thread_id]
                ),
            )
            for entry in manifest.entries
        )
        self.assertEqual(
            "athena.pr-review.misplaced-finding-marker-recoveries",
            self.delivery.MISPLACED_MARKER_RECOVERIES_SCHEMA_ID,
        )
        return replace(manifest, entries=entries)

    def repair_both_roots(self, forge: Any, binding: Any) -> tuple[dict[str, Any], ...]:
        """Repair both malformed roots and return their receipts."""
        receipts = []
        for thread in self.malformed_threads:
            receipts.append(
                self.delivery.repair_misplaced_finding_marker(
                    forge, binding, thread.comments[0].id
                )
            )
        return tuple(receipts)

    @staticmethod
    def receipts_document(
        binding: Any, receipts: tuple[dict[str, Any], ...]
    ) -> dict[str, Any]:
        """Return the canonical misplaced-marker receipt set."""
        return {
            "schema_id": "athena.pr-review.misplaced-finding-marker-recoveries",
            "schema_version": 1,
            "binding": {
                "repository": binding.repository,
                "number": binding.number,
                "url": binding.url,
                "base_oid": binding.base_oid,
                "head_oid": binding.head_oid,
            },
            "receipts": [dict(receipt) for receipt in receipts],
        }

    def recovery_cases(
        self,
    ) -> list[tuple[str, Callable[[tuple[dict[str, Any], ...], Any], dict[str, Any]]]]:
        """Return receipt mutations that must fail closed."""
        return [
            (
                "foreign-root",
                lambda receipts, binding: self.replace_root_id(receipts, "absent-root"),
            ),
            (
                "mismatched-binding",
                lambda receipts, binding: self.rebind(receipts, binding),
            ),
            (
                "off-chain-state-digest",
                lambda receipts, binding: self.replace_field(
                    receipts, "state_sha256", "0" * 64
                ),
            ),
            (
                "changed-canonical-body",
                lambda receipts, binding: self.replace_field(
                    receipts, "canonical_body", "Changed finding text."
                ),
            ),
            (
                "wrong-defect",
                lambda receipts, binding: self.replace_field(
                    receipts, "defect", "unknown_defect"
                ),
            ),
        ]

    def replace_root_id(
        self, receipts: tuple[dict[str, Any], ...], root_id: str
    ) -> dict[str, Any]:
        """Return receipts whose first root identity does not exist."""
        document = self.receipts_document(
            self.delivery.ReviewBinding(
                repository="owner/repository",
                number=7,
                url="https://github.com/owner/repository/pull/7",
                base_oid="a" * 40,
                head_oid="b" * 40,
            ),
            receipts,
        )
        document["receipts"] = [
            {**receipt, "root_id": root_id} if index == 0 else dict(receipt)
            for index, receipt in enumerate(document["receipts"])
        ]
        return document

    def rebind(
        self, receipts: tuple[dict[str, Any], ...], binding: Any
    ) -> dict[str, Any]:
        """Return receipts bound to a different pull request."""
        document = self.receipts_document(binding, receipts)
        document["binding"] = {**document["binding"], "number": 9}
        return document

    def default_binding(self) -> Any:
        """Return the fixture binding for standalone receipt documents."""
        return self.delivery.ReviewBinding(
            repository="owner/repository",
            number=7,
            url="https://github.com/owner/repository/pull/7",
            base_oid="a" * 40,
            head_oid="b" * 40,
        )

    def replace_field(
        self, receipts: tuple[dict[str, Any], ...], field: str, value: Any
    ) -> dict[str, Any]:
        """Return receipts with one changed scalar field."""
        document = self.receipts_document(self.default_binding(), receipts)
        document["receipts"] = [
            {**dict(receipt), field: value} if index == 0 else dict(receipt)
            for index, receipt in enumerate(document["receipts"])
        ]
        return document

    def test_recovery_repairs_a_two_root_batch_and_delivers_terminal_go(self) -> None:
        """Two repaired roots let a converged exchange receive GO delivery."""
        forge, binding, manifest, _state = self.misplaced_batch_fixture()
        receipts = self.repair_both_roots(forge, binding)
        prepared = self.repaired_manifest(forge, manifest, receipts)

        result = self.delivery.deliver_go_v1(
            forge,
            binding,
            prepared,
            misplaced_marker_recoveries=self.receipts_document(binding, receipts),
        )

        self.assertEqual("delivered", result.status)
        self.assertIn("state:implementation-go", forge.labels)
        self.assertEqual(2, len(receipts))
        self.assertEqual(
            ["marker_not_final", "marker_not_final"],
            [receipt["defect"] for receipt in receipts],
        )

    def test_repair_moves_only_the_marker_to_the_final_line(self) -> None:
        """The canonical repair changes marker placement and no other byte."""
        forge, binding, _manifest, _state = self.misplaced_batch_fixture()
        thread = self.malformed_threads[0]
        root_id = thread.comments[0].id
        original = forge.threads[thread.id].comments[0].body

        receipt = self.delivery.repair_misplaced_finding_marker(forge, binding, root_id)

        self.assertEqual(
            f"Finding 1.\n\n{self.marker('F-001')}", receipt["canonical_body"]
        )
        self.assertEqual(original, receipt["original_body"])
        self.assertEqual("marker_not_final", receipt["defect"])
        self.assertEqual(
            receipt["canonical_body"], forge.threads[thread.id].comments[0].body
        )

    def test_repair_refuses_an_already_final_marker(self) -> None:
        """A root whose marker is already final is not repairable."""
        forge, binding, _manifest, _state = self.misplaced_batch_fixture()
        thread = self.malformed_threads[0]
        root_id = thread.comments[0].id
        forge.threads[thread.id] = replace(
            forge.threads[thread.id],
            comments=(
                replace(
                    forge.threads[thread.id].comments[0],
                    body=f"Finding 1.\n\n{self.marker('F-001')}",
                ),
            ),
        )
        forge.events.clear()

        with self.assertRaises(self.delivery.DeliveryError) as caught:
            self.delivery.repair_misplaced_finding_marker(forge, binding, root_id)

        self.assertIn("already final", str(caught.exception))
        self.assertNotIn(f"edit:{root_id}", forge.events)

    def test_repair_refuses_a_second_edit(self) -> None:
        """A second repair of the same root is refused."""
        forge, binding, _manifest, _state = self.misplaced_batch_fixture()
        thread = self.malformed_threads[0]
        root_id = thread.comments[0].id
        self.delivery.repair_misplaced_finding_marker(forge, binding, root_id)
        forge.events.clear()

        with self.assertRaises(self.delivery.DeliveryError) as caught:
            self.delivery.repair_misplaced_finding_marker(forge, binding, root_id)

        self.assertIn(
            "misplaced-marker recovery marker is already final", str(caught.exception)
        )
        self.assertNotIn(f"edit:{root_id}", forge.events)

    def test_repair_refuses_a_foreign_root(self) -> None:
        """An unknown or ambiguous root ID cannot be repaired."""
        forge, binding, _manifest, _state = self.misplaced_batch_fixture()

        with self.assertRaises(self.delivery.DeliveryError) as caught:
            self.delivery.repair_misplaced_finding_marker(forge, binding, "absent-root")

        self.assertIn("absent or ambiguous", str(caught.exception))

    def test_recovery_refuses_a_root_that_matches_no_receipt(self) -> None:
        """An edited root without a matching receipt fails closed."""
        forge, binding, manifest, _state = self.misplaced_batch_fixture()
        receipts = self.repair_both_roots(forge, binding)
        prepared = self.repaired_manifest(forge, manifest, receipts)
        forge.events.clear()

        result = self.delivery.deliver_go_v1(
            forge,
            binding,
            prepared,
            misplaced_marker_recoveries=self.receipts_document(binding, receipts),
        )

        self.assertEqual("delivered", result.status)
        thread = self.malformed_threads[0]
        forge.threads[thread.id] = replace(
            forge.threads[thread.id],
            comments=(
                replace(
                    forge.threads[thread.id].comments[0],
                    body=f"Finding 1.\n\n{self.marker('F-001')}\n\nExtra text.",
                ),
            ),
        )
        forge.events.clear()

        with self.assertRaises(self.delivery.DeliveryError):
            self.delivery.deliver_go_v1(
                forge,
                binding,
                prepared,
                misplaced_marker_recoveries=self.receipts_document(binding, receipts),
            )

        self.assertNotIn("labels", forge.events)

    def test_recovery_refuses_each_invalid_receipt_set(self) -> None:
        """Every invalid receipt set is refused before any write."""
        forge, binding, manifest, _state = self.misplaced_batch_fixture()
        receipts = self.repair_both_roots(forge, binding)
        prepared = self.repaired_manifest(forge, manifest, receipts)
        forge.events.clear()

        for name, mutate in self.recovery_cases():
            with self.subTest(case=name):
                forge.events.clear()
                with self.assertRaises(self.delivery.DeliveryError):
                    self.delivery.deliver_go_v1(
                        forge,
                        binding,
                        prepared,
                        misplaced_marker_recoveries=mutate(receipts, binding),
                    )
                self.assertNotIn("labels", forge.events)
                self.assertNotIn("terminal", forge.events)

    def test_recovery_refuses_an_unused_receipt(self) -> None:
        """A supplied receipt that matches no live root is refused."""
        forge, binding, manifest, _state = self.misplaced_batch_fixture()
        receipts = self.repair_both_roots(forge, binding)
        prepared = self.repaired_manifest(forge, manifest, receipts)
        spare = {**receipts[0], "root_id": "absent-root", "root_database_id": 999}
        forge.events.clear()

        with self.assertRaises(self.delivery.DeliveryError) as caught:
            self.delivery.deliver_go_v1(
                forge,
                binding,
                prepared,
                misplaced_marker_recoveries=self.receipts_document(
                    binding, (*receipts, spare)
                ),
            )

        self.assertIn("recovery receipt is unused", str(caught.exception))
        self.assertNotIn("labels", forge.events)
        self.assertNotIn("terminal", forge.events)

    def test_recovery_receipt_validator_rejects_non_canonical_bodies(self) -> None:
        """A canonical body that changes other bytes is refused."""
        forge, binding, _manifest, _state = self.misplaced_batch_fixture()
        thread = self.malformed_threads[0]
        root_id = thread.comments[0].id
        receipt = self.delivery.repair_misplaced_finding_marker(forge, binding, root_id)
        changed = "Finding 1."
        tampered = {
            **receipt,
            "canonical_body": changed,
            "canonical_body_sha256": hashlib.sha256(
                changed.encode("utf-8")
            ).hexdigest(),
        }

        with self.assertRaises(self.delivery.DeliveryError) as caught:
            self.delivery._validated_misplaced_marker_receipt(tampered, binding)

        self.assertIn("changes more than marker placement", str(caught.exception))

    def test_recovery_receipt_validator_rejects_a_changed_body_digest(self) -> None:
        """A receipt whose canonical digest does not match its body is refused."""
        forge, binding, _manifest, _state = self.misplaced_batch_fixture()
        thread = self.malformed_threads[0]
        receipt = self.delivery.repair_misplaced_finding_marker(
            forge, binding, thread.comments[0].id
        )

        with self.assertRaises(self.delivery.DeliveryError) as caught:
            self.delivery._validated_misplaced_marker_receipt(
                {**receipt, "canonical_body_sha256": "0" * 64}, binding
            )

        self.assertIn("recovery receipt is invalid", str(caught.exception))

    def test_receipt_loader_rejects_a_repeated_root(self) -> None:
        """Two receipts for one root are refused."""
        forge, binding, _manifest, _state = self.misplaced_batch_fixture()
        receipts = self.repair_both_roots(forge, binding)
        document = self.receipts_document(binding, receipts)

        with self.assertRaises(self.delivery.DeliveryError) as caught:
            self.delivery.load_misplaced_marker_recoveries(
                {**document, "receipts": [receipts[0], receipts[0]]}, binding
            )

        self.assertIn("repeat a root", str(caught.exception))

    # ------------------------------------------------------------------
    # CLI wiring.
    # ------------------------------------------------------------------
    def test_main_routes_the_misplaced_marker_repair(self) -> None:
        """The repair flag routes to the repair operation and prints its receipt."""
        forge = object()
        receipt = {"defect": "marker_not_final"}
        output = io.StringIO()
        with (
            patch.object(self.delivery, "GitHubForge", return_value=forge),
            patch.object(
                self.delivery,
                "repair_misplaced_finding_marker",
                return_value=receipt,
            ) as repair,
            redirect_stdout(output),
        ):
            status = self.delivery.main(
                [
                    "--target-repository",
                    "owner/repository",
                    "--expected-pr-url",
                    "https://github.com/owner/repository/pull/7",
                    "--expected-base-oid",
                    "a" * 40,
                    "--expected-head-oid",
                    "b" * 40,
                    "--repair-misplaced-finding-marker",
                    "root-1",
                    "7",
                ]
            )

        self.assertEqual(0, status)
        repair.assert_called_once_with(
            forge,
            self.delivery._binding_from_args(
                self.delivery.argparse.Namespace(
                    target_repository="owner/repository",
                    target_host="github.com",
                    pull_request="7",
                    expected_pr_url="https://github.com/owner/repository/pull/7",
                    base_oid="a" * 40,
                    head_oid="b" * 40,
                )
            ),
            "root-1",
        )
        self.assertEqual({"defect": "marker_not_final"}, json.loads(output.getvalue()))

    def test_main_withholds_the_misplaced_recovery_set_outside_final_delivery(
        self,
    ) -> None:
        """A recovery set is valid only for final GO or NO-GO delivery."""
        for flag, value in (
            ("--prepare-manifest", None),
            ("--verify-legacy-go", "/bound/legacy.json"),
        ):
            with self.subTest(mode=flag):
                errors = io.StringIO()
                with (
                    patch.object(self.delivery, "GitHubForge", return_value=object()),
                    redirect_stdout(io.StringIO()),
                    redirect_stderr(errors),
                ):
                    status = self.delivery.main(
                        [
                            "--target-repository",
                            "owner/repository",
                            "--expected-pr-url",
                            "https://github.com/owner/repository/pull/7",
                            "--expected-base-oid",
                            "a" * 40,
                            "--expected-head-oid",
                            "b" * 40,
                            flag,
                            *([value] if value is not None else []),
                            "--misplaced-marker-recovery",
                            "/bound/recoveries.json",
                            "7",
                        ]
                    )

                self.assertEqual(1, status)
                self.assertIn("misplaced-marker recovery set", errors.getvalue())


class PrReviewFindingMarkerProcessTests(unittest.TestCase):
    """Process-level checks for the new packaged helper."""

    def test_publisher_reports_help_and_version(self) -> None:
        """The packaged publisher exposes the shared CLI contract."""
        for arguments in (["--help"], ["--version"]):
            with self.subTest(arguments=arguments):
                completed = subprocess.run(
                    [sys.executable, str(PUBLISHER_SCRIPT), *arguments],
                    capture_output=True,
                    text=True,
                    check=False,
                )

                self.assertEqual(0, completed.returncode, completed.stderr)
                self.assertTrue(completed.stdout.strip())


if __name__ == "__main__":
    unittest.main()
