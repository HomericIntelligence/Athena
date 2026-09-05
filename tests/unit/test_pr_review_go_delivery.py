"""Behavior tests for pull-request GO delivery."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "pr-review" / "scripts" / "deliver_go.py"


def load_module() -> ModuleType:
    """Load the executable helper as a test module."""
    name = f"test_pr_review_go_delivery_{id(SCRIPT)}"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("The GO-delivery helper cannot be loaded.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class FakeForge:
    """Record delivery operations and expose mutable forge state."""

    def __init__(self, module: ModuleType, *, threads: tuple[Any, ...]) -> None:
        self.module = module
        self.head_oid = "b" * 40
        self.labels = {"state:implementation-no-go", "enhancement"}
        self.threads = {thread.id: thread for thread in threads}
        self.events: list[str] = []
        self.fail_reply = False
        self.fail_resolve = False
        self.drift_head_after_resolve = False
        self.add_late_thread_after_resolve = False
        self.keep_no_go_after_label = False
        self.race_comment_after_reply = False
        self.drift_head_on_label = False

    def snapshot(self) -> Any:
        self.events.append("read")
        return self.module.PullRequestSnapshot(
            repository="owner/repository",
            number=7,
            url="https://github.com/owner/repository/pull/7",
            state="OPEN",
            is_draft=False,
            base_oid="a" * 40,
            head_oid=self.head_oid,
            labels=frozenset(self.labels),
            threads=tuple(self.threads.values()),
        )

    def reply(self, thread_id: str, body: str) -> None:
        self.events.append(f"reply:{thread_id}")
        if self.fail_reply:
            raise RuntimeError("reply failed")
        thread = self.threads[thread_id]
        comment = self.module.ReviewComment(id="reply-1", body=body, author="reviewer")
        self.threads[thread_id] = self.module.ReviewThread(
            id=thread.id,
            is_resolved=thread.is_resolved,
            comments=(*thread.comments, comment),
        )
        if self.race_comment_after_reply:
            updated = self.threads[thread_id]
            race = self.module.ReviewComment(
                id="raced-comment", body="new concern", author="other-reviewer"
            )
            self.threads[thread_id] = self.module.ReviewThread(
                id=updated.id,
                is_resolved=updated.is_resolved,
                comments=(*updated.comments, race),
            )

    def resolve(self, thread_id: str) -> None:
        self.events.append(f"resolve:{thread_id}")
        if self.fail_resolve:
            raise RuntimeError("resolve failed")
        thread = self.threads[thread_id]
        self.threads[thread_id] = self.module.ReviewThread(
            id=thread.id,
            is_resolved=True,
            comments=thread.comments,
        )
        if self.drift_head_after_resolve:
            self.head_oid = "c" * 40
        if self.add_late_thread_after_resolve:
            self.threads["late"] = self.module.ReviewThread(
                id="late",
                is_resolved=False,
                comments=(
                    self.module.ReviewComment(
                        id="late-comment", body="late finding", author="reviewer"
                    ),
                ),
            )

    def set_implementation_go(self) -> None:
        self.events.append("labels")
        if self.drift_head_on_label:
            self.head_oid = "c" * 40
        self.labels.add("state:implementation-go")
        if not self.keep_no_go_after_label:
            self.labels.discard("state:implementation-no-go")


class PrReviewGoDeliveryTests(unittest.TestCase):
    delivery: ModuleType

    @classmethod
    def setUpClass(cls) -> None:
        cls.delivery = load_module()

    def binding(self) -> Any:
        return self.delivery.ReviewBinding(
            repository="owner/repository",
            number=7,
            url="https://github.com/owner/repository/pull/7",
            base_oid="a" * 40,
            head_oid="b" * 40,
        )

    def thread(self) -> Any:
        return self.delivery.ReviewThread(
            id="thread-1",
            is_resolved=False,
            comments=(
                self.delivery.ReviewComment(
                    id="comment-1", body="original finding", author="reviewer"
                ),
            ),
        )

    def github_snapshot_json(self) -> str:
        return json.dumps(
            {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "baseRefOid": "a" * 40,
                            "headRefOid": "b" * 40,
                            "isDraft": False,
                            "labels": {
                                "nodes": [
                                    {"name": "state:implementation-no-go"},
                                    {"name": "enhancement"},
                                ],
                                "pageInfo": {"hasNextPage": False},
                            },
                            "number": 7,
                            "reviewThreads": {
                                "nodes": [
                                    {
                                        "comments": {
                                            "nodes": [
                                                {
                                                    "author": {"login": "reviewer"},
                                                    "body": "finding",
                                                    "id": "comment-1",
                                                }
                                            ],
                                            "pageInfo": {"hasNextPage": False},
                                        },
                                        "id": "thread-1",
                                        "isResolved": False,
                                    }
                                ],
                                "pageInfo": {"hasNextPage": False},
                            },
                            "state": "OPEN",
                            "url": "https://github.com/owner/repository/pull/7",
                        }
                    }
                }
            }
        )

    def plan(self, thread: Any) -> Any:
        return self.delivery.ThreadResponse(
            thread_id=thread.id,
            conversation_sha256=self.delivery.conversation_sha256(thread),
            body="Verified on the reviewed head: the issue is fixed by the new guard.",
        )

    def test_reply_precedes_resolution_and_exclusive_label_delivery(self) -> None:
        thread = self.thread()
        forge = FakeForge(self.delivery, threads=(thread,))

        result = self.delivery.deliver_go(forge, self.binding(), (self.plan(thread),))

        self.assertEqual("delivered", result.status)
        self.assertEqual(("thread-1",), result.resolved_thread_ids)
        self.assertLess(
            forge.events.index("reply:thread-1"), forge.events.index("resolve:thread-1")
        )
        self.assertLess(
            forge.events.index("resolve:thread-1"), forge.events.index("labels")
        )
        self.assertEqual({"state:implementation-go", "enhancement"}, forge.labels)
        self.assertGreater(forge.events.count("read"), 3)

    def test_delivery_keeps_go_when_review_readiness_changes(self) -> None:
        reviewed_source = {
            "base_oid": "a" * 40,
            "head_oid": "b" * 40,
            "paths": ("reviewed.txt",),
        }
        ci_evidence = {"required-checks-gate": "SUCCESS"}
        scenarios = {
            "REVIEW_REQUIRED": {
                "ci_evidence": ci_evidence,
                "merge_readiness": {"review_decision": "REVIEW_REQUIRED"},
                "reviewed_source": reviewed_source,
            },
            "APPROVED": {
                "ci_evidence": ci_evidence,
                "merge_readiness": {"review_decision": "APPROVED"},
                "reviewed_source": reviewed_source,
            },
        }
        delivery_statuses: dict[str, str] = {}

        for review_decision, scenario in scenarios.items():
            with self.subTest(review_decision=review_decision):
                self.assertEqual(reviewed_source, scenario["reviewed_source"])
                self.assertEqual(ci_evidence, scenario["ci_evidence"])
                forge = FakeForge(self.delivery, threads=(self.thread(),))
                result = self.delivery.deliver_go(
                    forge, self.binding(), (self.plan(self.thread()),)
                )

                self.assertEqual("delivered", result.status)
                self.assertEqual(
                    {"state:implementation-go", "enhancement"}, forge.labels
                )
                delivery_statuses[review_decision] = result.status

        self.assertEqual(
            scenarios["REVIEW_REQUIRED"]["reviewed_source"],
            scenarios["APPROVED"]["reviewed_source"],
        )
        self.assertEqual(
            scenarios["REVIEW_REQUIRED"]["ci_evidence"],
            scenarios["APPROVED"]["ci_evidence"],
        )
        self.assertEqual(
            delivery_statuses["REVIEW_REQUIRED"], delivery_statuses["APPROVED"]
        )
        self.assertNotEqual(
            scenarios["REVIEW_REQUIRED"]["merge_readiness"],
            scenarios["APPROVED"]["merge_readiness"],
        )

    def test_missing_thread_response_prevents_all_mutations(self) -> None:
        forge = FakeForge(self.delivery, threads=(self.thread(),))

        with self.assertRaisesRegex(self.delivery.DeliveryError, "response manifest"):
            self.delivery.deliver_go(forge, self.binding(), ())

        self.assertEqual(["read"], forge.events)

    def test_prepare_manifest_is_read_only_and_binds_complete_conversation(
        self,
    ) -> None:
        thread = self.thread()
        forge = FakeForge(self.delivery, threads=(thread,))

        manifest = self.delivery.prepare_response_manifest(forge, self.binding())

        self.assertEqual(["read"], forge.events)
        self.assertEqual("thread-1", manifest["responses"][0]["thread_id"])
        self.assertEqual(
            self.delivery.conversation_sha256(thread),
            manifest["responses"][0]["conversation_sha256"],
        )
        self.assertEqual(
            "original finding", manifest["responses"][0]["comments"][0]["body"]
        )

    def test_reply_failure_prevents_resolution_and_label(self) -> None:
        thread = self.thread()
        forge = FakeForge(self.delivery, threads=(thread,))
        forge.fail_reply = True

        with self.assertRaisesRegex(self.delivery.DeliveryError, "reply"):
            self.delivery.deliver_go(forge, self.binding(), (self.plan(thread),))

        self.assertNotIn("resolve:thread-1", forge.events)
        self.assertNotIn("labels", forge.events)

    def test_resolution_failure_prevents_label(self) -> None:
        thread = self.thread()
        forge = FakeForge(self.delivery, threads=(thread,))
        forge.fail_resolve = True

        with self.assertRaisesRegex(self.delivery.DeliveryError, "resolve"):
            self.delivery.deliver_go(forge, self.binding(), (self.plan(thread),))

        self.assertNotIn("labels", forge.events)

    def test_comment_race_after_reply_prevents_resolution_and_label(self) -> None:
        thread = self.thread()
        forge = FakeForge(self.delivery, threads=(thread,))
        forge.race_comment_after_reply = True

        with self.assertRaisesRegex(self.delivery.DeliveryError, "exact posted"):
            self.delivery.deliver_go(forge, self.binding(), (self.plan(thread),))

        self.assertNotIn("resolve:thread-1", forge.events)
        self.assertNotIn("labels", forge.events)

    def test_head_drift_after_resolution_prevents_label(self) -> None:
        thread = self.thread()
        forge = FakeForge(self.delivery, threads=(thread,))
        forge.drift_head_after_resolve = True

        with self.assertRaisesRegex(self.delivery.DeliveryError, "identity"):
            self.delivery.deliver_go(forge, self.binding(), (self.plan(thread),))

        self.assertNotIn("labels", forge.events)

    def test_late_thread_after_resolution_prevents_label(self) -> None:
        thread = self.thread()
        forge = FakeForge(self.delivery, threads=(thread,))
        forge.add_late_thread_after_resolve = True

        with self.assertRaisesRegex(self.delivery.DeliveryError, "unresolved"):
            self.delivery.deliver_go(forge, self.binding(), (self.plan(thread),))

        self.assertNotIn("labels", forge.events)

    def test_nonexclusive_label_readback_is_not_delivered_or_compensated(self) -> None:
        thread = self.thread()
        forge = FakeForge(self.delivery, threads=(thread,))
        forge.keep_no_go_after_label = True

        with self.assertRaisesRegex(self.delivery.DeliveryError, "exclusive"):
            self.delivery.deliver_go(forge, self.binding(), (self.plan(thread),))

        self.assertEqual(1, forge.events.count("labels"))

    def test_preexisting_go_is_not_accepted_as_delivery_proof(self) -> None:
        forge = FakeForge(self.delivery, threads=())
        forge.labels = {"state:implementation-go", "enhancement"}

        with self.assertRaisesRegex(self.delivery.DeliveryError, "cannot prove"):
            self.delivery.deliver_go(forge, self.binding(), ())

        self.assertEqual(["read"], forge.events)

    def test_existing_go_with_an_open_thread_is_rejected_without_mutation(self) -> None:
        forge = FakeForge(self.delivery, threads=(self.thread(),))
        forge.labels = {"state:implementation-go", "enhancement"}

        with self.assertRaisesRegex(self.delivery.DeliveryError, "GO label"):
            self.delivery.deliver_go(forge, self.binding(), ())

        self.assertEqual(["read"], forge.events)

    def test_interrupted_exact_response_is_resolved_without_a_duplicate(self) -> None:
        original = self.thread()
        original_plan = self.plan(original)
        delivered_body = self.delivery._delivery_body(self.binding(), original_plan)
        replied = self.delivery.ReviewThread(
            id=original.id,
            is_resolved=False,
            comments=(
                *original.comments,
                self.delivery.ReviewComment(
                    id="prior-response", body=delivered_body, author="reviewer"
                ),
            ),
        )
        recovery_plan = self.delivery.ThreadResponse(
            thread_id=replied.id,
            conversation_sha256=self.delivery.conversation_sha256(replied),
            body=original_plan.body,
        )
        forge = FakeForge(self.delivery, threads=(replied,))

        result = self.delivery.deliver_go(forge, self.binding(), (recovery_plan,))

        self.assertEqual("delivered", result.status)
        self.assertNotIn("reply:thread-1", forge.events)
        self.assertIn("resolve:thread-1", forge.events)
        self.assertIn("labels", forge.events)

    def test_head_race_during_label_write_cannot_report_delivery(self) -> None:
        thread = self.thread()
        forge = FakeForge(self.delivery, threads=(thread,))
        forge.drift_head_on_label = True

        with self.assertRaisesRegex(self.delivery.DeliveryError, "identity"):
            self.delivery.deliver_go(forge, self.binding(), (self.plan(thread),))

        self.assertEqual(1, forge.events.count("labels"))

    def test_executable_reports_a_missing_github_capability(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest = root / "responses.json"
            manifest.write_text(
                json.dumps(
                    {
                        "binding": {
                            "base_oid": "a" * 40,
                            "head_oid": "b" * 40,
                            "number": 1,
                            "repository": "owner/repository",
                            "url": "https://github.com/owner/repository/pull/1",
                        },
                        "responses": [],
                    }
                ),
                encoding="utf-8",
            )
            bin_directory = root / "bin"
            bin_directory.mkdir()
            (bin_directory / "python3").symlink_to(sys.executable)
            environment = os.environ.copy()
            environment["PATH"] = str(bin_directory)
            result = subprocess.run(
                [
                    str(SCRIPT),
                    "--target-host",
                    "github.com",
                    "--target-repository",
                    "owner/repository",
                    "--expected-base-oid",
                    "a" * 40,
                    "--expected-head-oid",
                    "b" * 40,
                    "--expected-pr-url",
                    "https://github.com/owner/repository/pull/1",
                    "--responses-file",
                    str(manifest),
                    "1",
                ],
                cwd=root,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(1, result.returncode)
        self.assertIn("gh", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_github_adapter_uses_explicit_host_and_parses_complete_snapshot(
        self,
    ) -> None:
        calls: list[tuple[str, ...]] = []

        def fake_gh(*arguments: str) -> str:
            calls.append(arguments)
            return self.github_snapshot_json()

        with patch.object(self.delivery, "_gh", side_effect=fake_gh):
            snapshot = self.delivery.GitHubForge(self.binding()).snapshot()

        self.assertEqual("thread-1", snapshot.threads[0].id)
        self.assertEqual("finding", snapshot.threads[0].comments[0].body)
        self.assertIn("state:implementation-no-go", snapshot.labels)
        self.assertIn("--hostname", calls[0])
        self.assertIn("github.com", calls[0])
        self.assertIn("owner=owner", calls[0])
        self.assertIn("name=repository", calls[0])
        self.assertIn("number=7", calls[0])

    def test_github_adapter_posts_bound_reply_and_resolution_mutations(self) -> None:
        calls: list[tuple[str, ...]] = []

        def fake_gh(*arguments: str) -> str:
            calls.append(arguments)
            return json.dumps({"data": {}})

        forge = self.delivery.GitHubForge(self.binding())
        with patch.object(self.delivery, "_gh", side_effect=fake_gh):
            forge.reply("thread-1", "response")
            forge.resolve("thread-1")

        self.assertIn("addPullRequestReviewThreadReply", calls[0][5])
        self.assertIn("threadId=thread-1", calls[0])
        self.assertIn("body=response", calls[0])
        self.assertIn("resolveReviewThread", calls[1][5])

    def test_github_adapter_changes_only_exclusive_implementation_labels(self) -> None:
        calls: list[tuple[str, ...]] = []
        forge = self.delivery.GitHubForge(self.binding())
        snapshot = self.delivery.PullRequestSnapshot(
            repository="owner/repository",
            number=7,
            url="https://github.com/owner/repository/pull/7",
            state="OPEN",
            is_draft=False,
            base_oid="a" * 40,
            head_oid="b" * 40,
            labels=frozenset({"state:implementation-no-go", "enhancement"}),
            threads=(),
        )

        def fake_gh(*arguments: str) -> str:
            calls.append(arguments)
            return ""

        with (
            patch.object(forge, "snapshot", return_value=snapshot),
            patch.object(self.delivery, "_gh", side_effect=fake_gh),
        ):
            forge.set_implementation_go()

        self.assertEqual(
            (
                "issue",
                "edit",
                "7",
                "--repo",
                "github.com/owner/repository",
                "--add-label",
                "state:implementation-go",
                "--remove-label",
                "state:implementation-no-go",
            ),
            calls[0],
        )

    def test_manifest_loader_accepts_bound_document_and_rejects_drift(self) -> None:
        thread = self.thread()
        document: dict[str, Any] = {
            "binding": {
                "base_oid": "a" * 40,
                "head_oid": "b" * 40,
                "number": 7,
                "repository": "owner/repository",
                "url": "https://github.com/owner/repository/pull/7",
            },
            "responses": [
                {
                    "body": "verified",
                    "conversation_sha256": self.delivery.conversation_sha256(thread),
                    "thread_id": "thread-1",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "manifest.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            responses = self.delivery.load_response_manifest(path, self.binding())
            document["binding"]["head_oid"] = "c" * 40
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(self.delivery.DeliveryError, "not bound"):
                self.delivery.load_response_manifest(path, self.binding())
            path.write_text(json.dumps({"responses": []}), encoding="utf-8")
            with self.assertRaisesRegex(self.delivery.DeliveryError, "not bound"):
                self.delivery.load_response_manifest(path, self.binding())

        self.assertEqual("verified", responses[0].body)

    def test_argument_binding_accepts_number_and_rejects_url_drift(self) -> None:
        arguments = Namespace(
            base_oid="a" * 40,
            expected_pr_url="https://github.com/owner/repository/pull/7",
            head_oid="b" * 40,
            pull_request="7",
            target_repository="owner/repository",
        )
        self.assertEqual(self.binding(), self.delivery._binding_from_args(arguments))
        arguments.pull_request = "https://github.com/other/repository/pull/7"
        with self.assertRaisesRegex(self.delivery.DeliveryError, "target repository"):
            self.delivery._binding_from_args(arguments)

    def test_main_prepares_manifest_and_reports_delivery_error(self) -> None:
        output = io.StringIO()
        with (
            patch.object(self.delivery, "GitHubForge", return_value=object()),
            patch.object(
                self.delivery,
                "prepare_response_manifest",
                return_value={"responses": []},
            ),
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
                    "--prepare-manifest",
                    "7",
                ]
            )
        self.assertEqual(0, status)
        self.assertEqual({"responses": []}, json.loads(output.getvalue()))

        errors = io.StringIO()
        with redirect_stderr(errors):
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
                    "--responses-file",
                    "/missing/manifest.json",
                    "7",
                ]
            )
        self.assertEqual(1, status)
        self.assertIn("cannot be read", errors.getvalue())

    def test_main_reports_verified_delivery_result(self) -> None:
        output = io.StringIO()
        forge = object()
        with (
            patch.object(self.delivery, "GitHubForge", return_value=forge),
            patch.object(self.delivery, "load_response_manifest", return_value=()),
            patch.object(
                self.delivery,
                "deliver_go",
                return_value=self.delivery.DeliveryResult("delivered", ("thread-1",)),
            ) as deliver,
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
                    "--responses-file",
                    "/bound/manifest.json",
                    "7",
                ]
            )

        self.assertEqual(0, status)
        self.assertEqual(
            {
                "label": "state:implementation-go",
                "resolved_thread_ids": ["thread-1"],
                "status": "delivered",
            },
            json.loads(output.getvalue()),
        )
        deliver.assert_called_once()


if __name__ == "__main__":
    unittest.main()
