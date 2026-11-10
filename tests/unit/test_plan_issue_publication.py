"""Behavior tests for the controlled plan-issue publication adapter."""

from __future__ import annotations

import contextlib
import copy
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any, cast
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills/plan-issue/scripts/publish_plan.py"


def load_module() -> ModuleType:
    """Load the publication adapter as a test module."""
    name = f"test_plan_issue_publication_{id(SCRIPT)}"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("The plan-issue publication adapter cannot be loaded.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def multiline_plan() -> str:
    """Return a multiline plan with repeated Markdown heading levels."""
    return (
        "## Context\n\n"
        "The plan needs exact publication.\n\n"
        "### Repeated heading\n\n"
        "First repeated section.\n\n"
        "### Repeated heading\n\n"
        "Second repeated section.\n\n"
        "## Change\n\n"
        "### Step heading\n\n"
        "Add the adapter.\n\n"
        "### Step heading\n\n"
        "Harden the receipt path.\n\n"
        "## Verification\n\n"
        "Run the focused tests.\n"
    )


@contextlib.contextmanager
def _chdir(target: Path) -> Any:
    previous = Path.cwd()
    os.chdir(target)
    try:
        yield
    finally:
        os.chdir(previous)


class FakeForge:
    """Deterministic in-memory forge with exact write capture."""

    def __init__(
        self,
        snapshot: dict[str, Any],
        *,
        strip_final_line_feed: bool = False,
        lose_response: bool = False,
        lose_response_before_write: bool = False,
        fail_on_readback: bool = False,
        forbid_writes: bool = False,
        extra_comments: list[dict[str, Any]] | None = None,
        replace_stored_body_with: str | None = None,
    ) -> None:
        self._snapshot = copy.deepcopy(snapshot)
        self.strip_final_line_feed = strip_final_line_feed
        self.replace_stored_body_with = replace_stored_body_with
        self.lose_response = lose_response
        self.lose_response_before_write = lose_response_before_write
        self.fail_on_readback = fail_on_readback
        self.forbid_writes = forbid_writes
        self.extra_comments = list(extra_comments or [])
        self.create_calls: list[str] = []
        self.update_calls: list[tuple[str, str]] = []
        self.snapshot_reads = 0

    def snapshot(self) -> dict[str, Any]:
        self.snapshot_reads += 1
        if self.fail_on_readback and self.create_calls:
            raise RuntimeError("The provider readback failed.")
        return copy.deepcopy(self._snapshot)

    def create_comment(self, body: str) -> tuple[str, str]:
        self._guard()
        self.create_calls.append(body)
        if self.lose_response_before_write:
            raise RuntimeError("The provider response was lost.")
        stored = body[:-1] if self.strip_final_line_feed else body
        if self.replace_stored_body_with is not None:
            stored = self.replace_stored_body_with
        comment = self._comment("1001", stored)
        self._snapshot["comments"].append(comment)
        for extra in self.extra_comments:
            self._snapshot["comments"].append(copy.deepcopy(extra))
        if self.lose_response:
            raise RuntimeError("The provider response was lost after the write.")
        return comment["id"], comment["url"]

    def update_comment(self, comment_id: str, body: str) -> tuple[str, str]:
        self._guard()
        self.update_calls.append((comment_id, body))
        if self.lose_response_before_write:
            raise RuntimeError("The provider response was lost.")
        stored = body[:-1] if self.strip_final_line_feed else body
        for comment in self._snapshot["comments"]:
            if comment["id"] == comment_id:
                comment["body"] = stored
                if self.lose_response:
                    raise RuntimeError(
                        "The provider response was lost after the write."
                    )
                return comment_id, comment["url"]
        raise AssertionError("The update target is absent from the fixture.")

    def _guard(self) -> None:
        if self.forbid_writes:
            raise AssertionError("The recovery path must not write.")

    def _comment(
        self,
        comment_id: str,
        body: str,
        *,
        author_id: str = "U_athena",
        login: str = "reviewer",
    ) -> dict[str, Any]:
        return {
            "id": comment_id,
            "url": (
                "https://github.com/owner/repository"
                f"/issues/210#issuecomment-{comment_id}"
            ),
            "author": {"id": author_id, "login": login, "is_authority": False},
            "body": body,
        }

    def comment(
        self,
        comment_id: str,
        body: str,
        *,
        author_id: str = "U_athena",
        login: str = "reviewer",
    ) -> dict[str, Any]:
        return self._comment(comment_id, body, author_id=author_id, login=login)


class PlanIssuePublicationTests(unittest.TestCase):
    adapter: ModuleType

    @classmethod
    def setUpClass(cls) -> None:
        cls.adapter = load_module()

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema_id": "athena.issue-exchange.snapshot",
            "schema_version": 1,
            "target": {
                "provider": "github",
                "host": "github.com",
                "repository": "owner/repository",
                "issue_id": "I_kwDO7",
                "number": 210,
                "url": "https://github.com/owner/repository/issues/210",
            },
            "actor": {"id": "U_athena", "login": "reviewer"},
            "issue": {
                "state": "open",
                "title": "Bound the review exchange",
                "body": "Implement a bounded protocol.",
                "acceptance_criteria": [
                    {
                        "id": "AC-001",
                        "text": "Stop after five reviewer assessments.",
                        "source": "body",
                    }
                ],
            },
            "comments": [],
            "comments_complete": True,
        }

    def comment(
        self,
        comment_id: str,
        body: str,
        *,
        author_id: str = "U_athena",
        login: str = "reviewer",
    ) -> dict[str, Any]:
        return {
            "id": comment_id,
            "url": (
                "https://github.com/owner/repository"
                f"/issues/210#issuecomment-{comment_id}"
            ),
            "author": {
                "id": author_id,
                "login": login,
                "is_authority": False,
            },
            "body": body,
        }

    def plan_request(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        return {
            "snapshot": snapshot,
            "content": (
                "## Plan\n\nAdd the bounded exchange.\n\n"
                "## Verification\n\nRun the focused tests."
            ),
            "event": {
                "scope": [
                    {"kind": "path", "value": "skills/review-exchange"},
                    {"kind": "path", "value": "skills/plan-issue"},
                    {"kind": "workflow", "value": "issue planning"},
                ],
                "scope_change_reason": None,
                "responses": [],
            },
        }

    def prepared_create(self) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            self.adapter.issue_exchange.prepare_plan(
                self.plan_request(self.snapshot())
            ),
        )

    def prepared_update(self) -> tuple[dict[str, Any], dict[str, Any]]:
        source = self.snapshot()
        first = self.adapter.issue_exchange.prepare_plan(self.plan_request(source))
        with_plan = copy.deepcopy(source)
        with_plan["comments"].append(self.comment("1001", first["operation"]["body"]))
        changed = copy.deepcopy(with_plan)
        changed["issue"]["body"] = "Implement the changed bounded protocol."
        second = self.adapter.issue_exchange.prepare_plan(self.plan_request(changed))
        return second, changed

    def test_create_submits_the_exact_body_exactly_once(self) -> None:
        prepared = self.prepared_create()
        body = prepared["operation"]["body"]
        forge = FakeForge(self.snapshot())
        with tempfile.TemporaryDirectory() as directory:
            receipt_path = str(Path(directory) / "attempt.json")
            result = self.adapter.publish(prepared, receipt_path, forge=forge)

        self.assertTrue(body.endswith("\n"))
        self.assertEqual([body], forge.create_calls)
        self.assertEqual([], forge.update_calls)
        self.assertEqual("verified", result["status"])
        self.assertEqual(False, result["retry_allowed"])

    def test_update_submits_the_exact_body_once_with_the_prepared_identity(
        self,
    ) -> None:
        prepared, changed = self.prepared_update()
        operation = prepared["operation"]
        forge = FakeForge(changed)
        with tempfile.TemporaryDirectory() as directory:
            receipt_path = str(Path(directory) / "attempt.json")
            result = self.adapter.publish(prepared, receipt_path, forge=forge)

        self.assertEqual("update", operation["action"])
        self.assertEqual("1001", operation["comment_id"])
        self.assertTrue(operation["body"].endswith("\n"))
        self.assertEqual([("1001", operation["body"])], forge.update_calls)
        self.assertEqual([], forge.create_calls)
        self.assertEqual("verified", result["status"])

    def test_matching_fresh_snapshot_permits_exactly_one_write(self) -> None:
        prepared = self.prepared_create()
        fresh = self.snapshot()

        preflight = self.adapter.issue_exchange.publication_preflight(
            {"prepared": prepared, "snapshot": fresh}
        )

        self.assertEqual("matched", preflight["status"])
        forge = FakeForge(fresh)
        with tempfile.TemporaryDirectory() as directory:
            receipt_path = str(Path(directory) / "attempt.json")
            result = self.adapter.publish(prepared, receipt_path, forge=forge)
        self.assertEqual("verified", result["status"])
        self.assertEqual(1, len(forge.create_calls))
        self.assertEqual(0, len(forge.update_calls))

    def _no_write(
        self,
        fresh: dict[str, Any],
        preflight_code: str,
    ) -> FakeForge:
        prepared = self.prepared_create()
        forge = FakeForge(fresh)
        with tempfile.TemporaryDirectory() as directory:
            receipt_path = str(Path(directory) / "attempt.json")
            result = self.adapter.publish(prepared, receipt_path, forge=forge)

        self.assertEqual("no_write", result["status"])
        self.assertEqual(preflight_code, result["preflight_code"])
        self.assertEqual(False, result["retry_allowed"])
        self.assertEqual([], forge.create_calls)
        self.assertEqual([], forge.update_calls)
        return forge

    def test_preflight_no_write_on_stale_issue_body(self) -> None:
        fresh = self.snapshot()
        fresh["issue"]["body"] = "Implement the changed bounded protocol."

        self._no_write(fresh, "preflight_requirements_drift")

    def test_preflight_no_write_on_foreign_actor(self) -> None:
        fresh = self.snapshot()
        fresh["actor"] = {"id": "U_other", "login": "other"}

        self._no_write(fresh, "preflight_actor_drift")

    def test_preflight_no_write_on_foreign_plan_marker(self) -> None:
        fresh = self.snapshot()
        fresh["comments"].append(
            self.comment(
                "9001",
                "<!-- HomericIntelligence:plan-issue -->\n\nForeign plan.\n",
                author_id="U_other",
                login="other",
            )
        )

        self._no_write(fresh, "preflight_foreign_marker")

    def test_preflight_no_write_on_duplicate_actor_plan_marker(self) -> None:
        fresh = self.snapshot()
        fresh["comments"].append(
            self.comment(
                "9001",
                "<!-- HomericIntelligence:plan-issue -->\n\nFirst plan.\n",
            )
        )
        fresh["comments"].append(
            self.comment(
                "9002",
                "<!-- HomericIntelligence:plan-issue -->\n\nSecond plan.\n",
            )
        )

        self._no_write(fresh, "preflight_duplicate_plan_marker")

    def test_preflight_no_write_on_incomplete_comments(self) -> None:
        fresh = self.snapshot()
        fresh["comments_complete"] = False

        self._no_write(fresh, "preflight_incomplete_snapshot")

    def test_preflight_no_write_on_target_mismatch(self) -> None:
        fresh = self.snapshot()
        fresh["target"]["number"] = 211

        self._no_write(fresh, "preflight_target_drift")

    def test_receipt_persists_binding_after_verified_create(self) -> None:
        prepared = self.prepared_create()
        forge = FakeForge(self.snapshot())
        with tempfile.TemporaryDirectory() as directory:
            receipt_path = Path(directory) / "attempt.json"
            result = self.adapter.publish(prepared, str(receipt_path), forge=forge)
            document = json.loads(receipt_path.read_text(encoding="utf-8"))

        self.assertEqual("verified", result["status"])
        operation = prepared["operation"]
        self.assertEqual("athena.plan-issue.publication-receipt", document["schema_id"])
        self.assertEqual("post_response", document["stage"])
        self.assertEqual("create", document["action"])
        self.assertEqual("plan", document["artifact"])
        self.assertEqual(operation["operation_sha256"], document["operation_sha256"])
        self.assertEqual(operation["body_sha256"], document["submitted_body_sha256"])
        self.assertEqual(prepared["actor_id"], document["actor_id"])
        self.assertEqual(
            prepared["requirements_sha256"], document["requirements_sha256"]
        )
        self.assertEqual(
            prepared["precondition_sha256"], document["precondition_sha256"]
        )
        self.assertEqual("1001", document["comment_id"])
        self.assertTrue(document["url"].endswith("#issuecomment-1001"))
        self.assertEqual(0, document["comment_count"])
        self.assertEqual([], document["comments"])
        self.assertEqual(0, document["foreign_marker_comment_count"])
        self.assertEqual(64, len(document["marker_comment_sha256"]))
        self.assertEqual(receipt_path.name, Path(result["receipt_path"]).name)
        self.assertEqual("post_response", result["receipt_stage"])
        self.assertEqual(True, result["receipt_has_comment_identity"])

    def test_readback_with_only_final_line_feed_removed_is_unknown_outcome(
        self,
    ) -> None:
        prepared = self.prepared_create()
        forge = FakeForge(self.snapshot(), strip_final_line_feed=True)
        with tempfile.TemporaryDirectory() as directory:
            receipt_path = Path(directory) / "attempt.json"
            result = self.adapter.publish(prepared, str(receipt_path), forge=forge)
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

        self.assertEqual("unknown_outcome", result["status"])
        self.assertEqual(False, result["retry_allowed"])
        self.assertEqual("post_response", result["receipt_stage"])
        self.assertEqual("1001", result["comment_id"])
        self.assertTrue(str(result["url"]).endswith("#issuecomment-1001"))
        self.assertTrue(result["receipt_has_comment_identity"])
        self.assertEqual(str(receipt_path), result["receipt_path"])
        self.assertTrue(result["diagnostics"])
        self.assertEqual("post_response", receipt["stage"])
        self.assertEqual("1001", receipt["comment_id"])

    def _verified_receipt(
        self, directory: str
    ) -> tuple[dict[str, Any], str, FakeForge]:
        prepared = self.prepared_create()
        forge = FakeForge(self.snapshot())
        receipt_path = str(Path(directory) / "attempt.json")
        result = self.adapter.publish(prepared, receipt_path, forge=forge)
        self.assertEqual("verified", result["status"])
        return prepared, receipt_path, forge

    def _recover(
        self,
        prepared: dict[str, Any],
        receipt_path: str,
        mutated: dict[str, Any],
    ) -> dict[str, Any]:
        recovery_forge = FakeForge(mutated, forbid_writes=True)
        return cast(
            dict[str, Any],
            self.adapter.recover(prepared, receipt_path, forge=recovery_forge),
        )

    def _published_snapshot(self, forge: FakeForge) -> dict[str, Any]:
        return copy.deepcopy(forge._snapshot)

    def test_recovery_with_known_id_classifies_exact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            prepared, receipt_path, forge = self._verified_receipt(directory)
            receipt_before = Path(receipt_path).read_bytes()

            result = self._recover(
                prepared, receipt_path, self._published_snapshot(forge)
            )

            self.assertEqual("exact", result["status"])
            self.assertEqual("exact", result["recovery"])
            self.assertEqual("1001", result["comment_id"])
            self.assertEqual(False, result["retry_allowed"])
            self.assertEqual("post_response", result["receipt_stage"])
            self.assertEqual(receipt_before, Path(receipt_path).read_bytes())

    def test_recovery_with_known_id_classifies_changed_bytes_as_malformed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            prepared, receipt_path, forge = self._verified_receipt(directory)
            mutated = self._published_snapshot(forge)
            comment = mutated["comments"][0]
            comment["body"] = comment["body"].replace(
                "Add the bounded exchange.", "Add the changed exchange."
            )

            result = self._recover(prepared, receipt_path, mutated)

            self.assertEqual("malformed", result["status"])
            self.assertEqual("malformed", result["recovery"])
            self.assertEqual("1001", result["comment_id"])
            self.assertEqual(False, result["retry_allowed"])

    def test_recovery_with_known_id_classifies_missing_id_as_ambiguous(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            prepared, receipt_path, forge = self._verified_receipt(directory)
            mutated = self._published_snapshot(forge)
            mutated["comments"] = []

            result = self._recover(prepared, receipt_path, mutated)

            self.assertEqual("ambiguous", result["status"])
            self.assertEqual(
                "recovery_missing_retained_id", result["diagnostics"][0]["code"]
            )
            self.assertEqual(False, result["retry_allowed"])

    def test_recovery_with_known_id_classifies_foreign_owner_as_ambiguous(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            prepared, receipt_path, forge = self._verified_receipt(directory)
            mutated = self._published_snapshot(forge)
            mutated["comments"][0]["author"] = {
                "id": "U_other",
                "login": "other",
                "is_authority": False,
            }

            result = self._recover(prepared, receipt_path, mutated)

            self.assertEqual("ambiguous", result["status"])
            self.assertEqual("recovery_foreign_owner", result["diagnostics"][0]["code"])
            self.assertEqual(False, result["retry_allowed"])

    def test_recovery_with_known_id_classifies_conflicting_role_as_ambiguous(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            prepared, receipt_path, forge = self._verified_receipt(directory)
            mutated = self._published_snapshot(forge)
            body = mutated["comments"][0]["body"]
            mutated["comments"][0]["body"] = (
                "<!-- HomericIntelligence:issue-review -->\n" + body
            )

            result = self._recover(prepared, receipt_path, mutated)

            self.assertEqual("ambiguous", result["status"])
            self.assertEqual(
                "recovery_conflicting_role", result["diagnostics"][0]["code"]
            )
            self.assertEqual(False, result["retry_allowed"])

    def _lost_response_recovery(
        self,
        forge: FakeForge,
        prepared: dict[str, Any],
        receipt_path: str,
    ) -> dict[str, Any]:
        recovery_forge = FakeForge(forge._snapshot, forbid_writes=True)
        return cast(
            dict[str, Any],
            self.adapter.recover(prepared, receipt_path, forge=recovery_forge),
        )

    def _lost_response(
        self,
        **forge_options: Any,
    ) -> tuple[dict[str, Any], str, FakeForge, dict[str, Any]]:
        prepared = self.prepared_create()
        if forge_options.get("extra_from_body"):
            body = prepared["operation"]["body"]
            forge_options["extra_comments"] = [
                self.comment("1002", body),
            ]
            del forge_options["extra_from_body"]
        forge = FakeForge(self.snapshot(), **forge_options)
        with tempfile.TemporaryDirectory() as directory:
            receipt_path = str(Path(directory) / "attempt.json")
            result = self.adapter.publish(prepared, receipt_path, forge=forge)
            receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
            recovery = self._lost_response_recovery(forge, prepared, receipt_path)
            receipt_after = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
        self.assertEqual("unknown_outcome", result["status"])
        self.assertEqual(False, result["retry_allowed"])
        self.assertEqual("pre_write", result["receipt_stage"])
        self.assertIsNone(result["comment_id"])
        self.assertEqual("pre_write", receipt["stage"])
        self.assertIsNone(receipt["comment_id"])
        self.assertEqual("pre_write", receipt_after["stage"])
        return prepared, receipt_path, forge, recovery

    def test_lost_response_with_no_candidate_classifies_absent(self) -> None:
        _prepared, _path, _forge, recovery = self._lost_response(
            lose_response_before_write=True
        )

        self.assertEqual("absent", recovery["status"])
        self.assertEqual("absent", recovery["recovery"])
        self.assertEqual("recovery_absent", recovery["diagnostics"][0]["code"])
        self.assertEqual(False, recovery["retry_allowed"])

    def test_lost_response_with_one_exact_candidate_classifies_exact(
        self,
    ) -> None:
        _prepared, _path, _forge, recovery = self._lost_response(lose_response=True)

        self.assertEqual("exact", recovery["status"])
        self.assertEqual("exact", recovery["recovery"])
        self.assertEqual("1001", recovery["comment_id"])
        self.assertEqual(False, recovery["retry_allowed"])

    def test_lost_response_with_one_attributable_malformed_candidate(
        self,
    ) -> None:
        _prepared, _path, _forge, recovery = self._lost_response(
            lose_response=True, strip_final_line_feed=True
        )

        self.assertEqual("malformed", recovery["status"])
        self.assertEqual("malformed", recovery["recovery"])
        self.assertEqual("1001", recovery["comment_id"])
        self.assertEqual(False, recovery["retry_allowed"])

    def test_lost_response_with_multiple_candidates_classifies_ambiguous(
        self,
    ) -> None:
        _prepared, _path, _forge, recovery = self._lost_response(
            lose_response=True, extra_from_body=True
        )

        self.assertEqual("ambiguous", recovery["status"])
        self.assertEqual(
            "recovery_multiple_candidates", recovery["diagnostics"][0]["code"]
        )
        self.assertEqual(False, recovery["retry_allowed"])

    def test_lost_response_with_foreign_candidate_classifies_ambiguous(
        self,
    ) -> None:
        foreign = self.comment(
            "1002",
            "<!-- HomericIntelligence:plan-issue -->\n\nForeign plan.\n",
            author_id="U_other",
            login="other",
        )
        _prepared, _path, _forge, recovery = self._lost_response(
            lose_response=True, extra_comments=[foreign]
        )

        self.assertEqual("ambiguous", recovery["status"])
        self.assertEqual("recovery_foreign_marker", recovery["diagnostics"][0]["code"])
        self.assertEqual(False, recovery["retry_allowed"])

    def test_invalid_prepared_schema_stops_before_any_forge_contact(self) -> None:
        prepared = self.prepared_create()
        invalid = {**prepared, "schema_version": 2}
        forge = FakeForge(self.snapshot())
        with tempfile.TemporaryDirectory() as directory:
            receipt_path = str(Path(directory) / "attempt.json")
            with self.assertRaises(self.adapter.PublicationError):
                self.adapter.publish(invalid, receipt_path, forge=forge)

        self.assertEqual(0, forge.snapshot_reads)
        self.assertEqual([], forge.create_calls)
        self.assertEqual([], forge.update_calls)

    def test_altered_body_digest_stops_before_any_forge_contact(self) -> None:
        prepared = copy.deepcopy(self.prepared_create())
        prepared["operation"]["body_sha256"] = "0" * 64
        forge = FakeForge(self.snapshot())
        with tempfile.TemporaryDirectory() as directory:
            receipt_path = str(Path(directory) / "attempt.json")
            with self.assertRaises(self.adapter.PublicationError):
                self.adapter.publish(prepared, receipt_path, forge=forge)

        self.assertEqual(0, forge.snapshot_reads)
        self.assertEqual([], forge.create_calls)
        self.assertEqual([], forge.update_calls)

    def test_unsupported_action_stops_before_any_forge_contact(self) -> None:
        prepared = copy.deepcopy(self.prepared_create())
        prepared["operation"]["action"] = "delete"
        forge = FakeForge(self.snapshot())
        with tempfile.TemporaryDirectory() as directory:
            receipt_path = str(Path(directory) / "attempt.json")
            with self.assertRaises(self.adapter.PublicationError):
                self.adapter.publish(prepared, receipt_path, forge=forge)

        self.assertEqual(0, forge.snapshot_reads)
        self.assertEqual([], forge.create_calls)
        self.assertEqual([], forge.update_calls)

    def test_provider_error_causes_no_dependent_effect(self) -> None:
        prepared = self.prepared_create()
        forge = FakeForge(self.snapshot(), lose_response_before_write=True)
        with tempfile.TemporaryDirectory() as directory:
            receipt_path = str(Path(directory) / "attempt.json")
            result = self.adapter.publish(prepared, receipt_path, forge=forge)

        self.assertEqual("unknown_outcome", result["status"])
        self.assertEqual(False, result["retry_allowed"])
        self.assertEqual("pre_write", result["receipt_stage"])
        self.assertEqual(1, len(forge.create_calls))
        self.assertEqual([], forge.update_calls)

    def test_provider_readback_error_causes_no_dependent_effect(self) -> None:
        prepared = self.prepared_create()
        forge = FakeForge(self.snapshot(), fail_on_readback=True)
        with tempfile.TemporaryDirectory() as directory:
            receipt_path = Path(directory) / "attempt.json"
            result = self.adapter.publish(prepared, str(receipt_path), forge=forge)
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

        self.assertEqual("unknown_outcome", result["status"])
        self.assertEqual(False, result["retry_allowed"])
        self.assertEqual("post_response", result["receipt_stage"])
        self.assertEqual(1, len(forge.create_calls))
        self.assertEqual([], forge.update_calls)
        self.assertEqual("post_response", receipt["stage"])

    def test_multiline_plan_with_large_target_set_preserves_sections_and_digest_domains(
        self,
    ) -> None:
        content = multiline_plan()
        request = self.plan_request(self.snapshot())
        request["content"] = content
        request["event"]["scope"] = [
            {"kind": "path", "value": f"skills/module-{index:03d}"}
            for index in range(50)
        ]
        prepared = self.adapter.issue_exchange.prepare_plan(request)

        body = prepared["operation"]["body"]
        visible = f"{self.adapter.issue_exchange.PLAN_MARKER}\n\n{content.rstrip()}"
        bare_digest = self.adapter.review_exchange.sha256_text(content)
        marked_digest = self.adapter.review_exchange.sha256_text(visible)

        # The bare-draft and marked-visible digests are distinct valid bindings.
        self.assertNotEqual(bare_digest, marked_digest)
        self.assertTrue(body.startswith(visible))
        _origin, envelope = self.adapter.review_exchange.extract_carrier_pair(body)
        artifact = envelope["state"]["artifact_binding"]
        self.assertEqual(marked_digest, artifact["visible_content_sha256"])
        self.assertEqual(marked_digest, artifact["sha256"])
        self.assertEqual(f"pending:{marked_digest}", artifact["revision"])

        # No section is duplicated or moved.
        for heading in (
            "## Context",
            "### Repeated heading",
            "## Change",
            "### Step heading",
            "## Verification",
        ):
            with self.subTest(heading=heading):
                self.assertEqual(content.count(heading), body.count(heading))
        ordered = [
            body.index(marker)
            for marker in (
                "## Context",
                "First repeated section.",
                "Second repeated section.",
                "## Change",
                "Add the adapter.",
                "Harden the receipt path.",
                "## Verification",
            )
        ]
        self.assertEqual(sorted(ordered), ordered)

        forge = FakeForge(self.snapshot())
        with tempfile.TemporaryDirectory() as directory:
            receipt_path = str(Path(directory) / "attempt.json")
            result = self.adapter.publish(prepared, receipt_path, forge=forge)
        self.assertEqual("verified", result["status"])

    def test_prewrite_inventory_comes_from_the_fresh_snapshot(self) -> None:
        module = load_module()
        prepared = module.issue_exchange.prepare_plan(
            self.plan_request(self.snapshot())
        )
        captured: dict[str, Any] = {}
        real_inventory = module.issue_exchange.plan_marker_inventory

        def spy(value: dict[str, Any]) -> dict[str, Any]:
            captured["snapshot"] = copy.deepcopy(value["snapshot"])
            return real_inventory(value)

        module.issue_exchange.plan_marker_inventory = spy
        fresh = self.snapshot()
        fresh["comments"].append(
            self.comment("1500", "Release notes without any role markers.\n")
        )
        forge = FakeForge(fresh)
        with tempfile.TemporaryDirectory() as directory:
            receipt_path = str(Path(directory) / "attempt.json")
            result = module.publish(prepared, receipt_path, forge=forge)
            receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))

        self.assertEqual("verified", result["status"])
        self.assertEqual(fresh, captured["snapshot"])
        self.assertNotEqual(self.snapshot(), captured["snapshot"])
        self.assertEqual(
            ["1500"], [comment["id"] for comment in captured["snapshot"]["comments"]]
        )
        self.assertEqual([], receipt["comments"])
        self.assertEqual(0, receipt["comment_count"])

    def test_successful_create_records_identity_before_readback(self) -> None:
        prepared = self.prepared_create()
        receipt_path_box: dict[str, str] = {}
        observed: dict[str, Any] = {}

        class ReadbackSpyForge(FakeForge):
            def snapshot(self) -> dict[str, Any]:
                if self.create_calls:
                    receipt = json.loads(
                        Path(receipt_path_box["path"]).read_text(encoding="utf-8")
                    )
                    observed.update(receipt)
                return super().snapshot()

        forge = ReadbackSpyForge(self.snapshot())
        with tempfile.TemporaryDirectory() as directory:
            receipt_path_box["path"] = str(Path(directory) / "attempt.json")
            result = self.adapter.publish(
                prepared, receipt_path_box["path"], forge=forge
            )

        self.assertEqual("verified", result["status"])
        self.assertEqual("post_response", observed["stage"])
        self.assertEqual("1001", observed["comment_id"])
        self.assertTrue(str(observed["url"]).endswith("#issuecomment-1001"))

    def test_crash_after_provider_response_keeps_the_atomic_receipt_readable(
        self,
    ) -> None:
        prepared = self.prepared_create()
        forge = FakeForge(self.snapshot())
        with tempfile.TemporaryDirectory() as directory:
            receipt_path = Path(directory) / "attempt.json"
            with mock.patch.object(
                self.adapter, "_update_receipt", side_effect=OSError("crash")
            ):
                result = self.adapter.publish(prepared, str(receipt_path), forge=forge)
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

        self.assertEqual("unknown_outcome", result["status"])
        self.assertEqual(
            "receipt_post_write_unrecorded", result["diagnostics"][0]["code"]
        )
        self.assertEqual("pre_write", result["receipt_stage"])
        self.assertEqual(False, result["receipt_has_comment_identity"])
        self.assertEqual(False, result["retry_allowed"])
        self.assertEqual("pre_write", receipt["stage"])
        self.assertIsNone(receipt["comment_id"])
        self.assertIsNone(receipt["url"])

    def test_lost_response_recovery_with_incomplete_snapshot_is_ambiguous(
        self,
    ) -> None:
        prepared = self.prepared_create()
        forge = FakeForge(self.snapshot(), lose_response=True)
        with tempfile.TemporaryDirectory() as directory:
            receipt_path = str(Path(directory) / "attempt.json")
            result = self.adapter.publish(prepared, receipt_path, forge=forge)
            self.assertEqual("unknown_outcome", result["status"])
            mutated = copy.deepcopy(forge._snapshot)
            mutated["comments_complete"] = False
            recovery = self._recover(prepared, receipt_path, mutated)

        self.assertEqual("ambiguous", recovery["status"])
        self.assertEqual(
            "recovery_incomplete_snapshot", recovery["diagnostics"][0]["code"]
        )
        self.assertEqual(False, recovery["retry_allowed"])

    def test_lost_response_recovery_with_changed_prewrite_item_is_ambiguous(
        self,
    ) -> None:
        prepared = self.prepared_create()
        forge = FakeForge(self.snapshot(), lose_response=True)
        with tempfile.TemporaryDirectory() as directory:
            receipt_path = str(Path(directory) / "attempt.json")
            result = self.adapter.publish(prepared, receipt_path, forge=forge)
            self.assertEqual("unknown_outcome", result["status"])
            receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
            # The matched create carried no actor-owned pre-write plan records.
            self.assertEqual([], receipt["comments"])
            prewrite = self.snapshot()
            prewrite["comments"] = [
                self.comment(
                    "1500",
                    "<!-- HomericIntelligence:plan-issue -->\n\nRetained plan.\n",
                )
            ]
            inventory = self.adapter.issue_exchange.plan_marker_inventory(
                {"snapshot": prewrite, "artifact": "plan"}
            )
            receipt["comments"] = inventory["comments"]
            receipt["comment_count"] = inventory["comment_count"]
            receipt["marker_comment_sha256"] = inventory["marker_comment_sha256"]
            Path(receipt_path).write_text(
                json.dumps(receipt, separators=(",", ":")) + "\n", encoding="utf-8"
            )
            mutated = self.snapshot()
            mutated["comments"] = [
                self.comment(
                    "1500",
                    "<!-- HomericIntelligence:plan-issue -->\n\nChanged retained plan.\n",
                )
            ]
            recovery = self._recover(prepared, receipt_path, mutated)

        self.assertEqual("ambiguous", recovery["status"])
        self.assertEqual(
            "recovery_prewrite_inventory_changed", recovery["diagnostics"][0]["code"]
        )
        self.assertEqual(False, recovery["retry_allowed"])

    def test_lost_response_recovery_with_unprovable_binding_is_ambiguous(
        self,
    ) -> None:
        candidate = (
            "<!-- HomericIntelligence:plan-issue -->\n\n"
            "Opaque changed body with no carrier.\n"
        )
        recovery = self._recovery_with_forced_candidate(candidate)

        self.assertEqual("ambiguous", recovery["status"])
        self.assertEqual(
            "recovery_unprovable_binding", recovery["diagnostics"][0]["code"]
        )
        self.assertEqual(False, recovery["retry_allowed"])

    def _recovery_with_forced_candidate(self, candidate_body: str) -> dict[str, Any]:
        prepared = self.prepared_create()
        forge = FakeForge(
            self.snapshot(),
            lose_response=True,
            replace_stored_body_with=candidate_body,
        )
        with tempfile.TemporaryDirectory() as directory:
            receipt_path = str(Path(directory) / "attempt.json")
            result = self.adapter.publish(prepared, receipt_path, forge=forge)
            self.assertEqual("unknown_outcome", result["status"])
            recovery = self._lost_response_recovery(forge, prepared, receipt_path)
        return recovery

    def test_duplicate_heading_changed_body_is_not_attributable(self) -> None:
        prepared = self.prepared_create()
        body = prepared["operation"]["body"]
        lines = body.splitlines(keepends=True)
        for index, line in enumerate(lines):
            if line.startswith("## "):
                lines.insert(index, line)
                break
        else:
            self.fail("The prepared body has no Markdown level-2 heading.")
        candidate = "".join(lines)

        recovery = self._recovery_with_forced_candidate(candidate)

        self.assertEqual("ambiguous", recovery["status"])
        self.assertEqual("1001", recovery["comment_id"])
        self.assertEqual(
            "recovery_unprovable_binding", recovery["diagnostics"][0]["code"]
        )
        self.assertEqual(False, recovery["retry_allowed"])

    def test_duplicate_heading_changed_body_without_carrier_is_ambiguous(
        self,
    ) -> None:
        prepared = self.prepared_create()
        body = prepared["operation"]["body"]
        lines = body.splitlines(keepends=True)
        for index, line in enumerate(lines):
            if line.startswith("## "):
                lines.insert(index, line)
                break
        else:
            self.fail("The prepared body has no Markdown level-2 heading.")
        candidate = self._without_carrier("".join(lines))

        recovery = self._recovery_with_forced_candidate(candidate)

        self.assertEqual("ambiguous", recovery["status"])
        self.assertEqual(
            "recovery_unprovable_binding", recovery["diagnostics"][0]["code"]
        )
        self.assertEqual(False, recovery["retry_allowed"])

    def test_displaced_paragraph_changed_body_is_not_attributable(
        self,
    ) -> None:
        prepared = self.prepared_create()
        candidate = self._with_displaced_paragraph(prepared["operation"]["body"])

        recovery = self._recovery_with_forced_candidate(candidate)

        self.assertEqual("ambiguous", recovery["status"])
        self.assertEqual("1001", recovery["comment_id"])
        self.assertEqual(
            "recovery_unprovable_binding", recovery["diagnostics"][0]["code"]
        )
        self.assertEqual(False, recovery["retry_allowed"])

    def test_displaced_paragraph_changed_body_without_carrier_is_ambiguous(
        self,
    ) -> None:
        prepared = self.prepared_create()
        candidate = self._without_carrier(
            self._with_displaced_paragraph(prepared["operation"]["body"])
        )

        recovery = self._recovery_with_forced_candidate(candidate)

        self.assertEqual("ambiguous", recovery["status"])
        self.assertEqual(
            "recovery_unprovable_binding", recovery["diagnostics"][0]["code"]
        )
        self.assertEqual(False, recovery["retry_allowed"])

    def _with_displaced_paragraph(self, body: str) -> str:
        blocks = body.split("\n\n")
        first = blocks.index("Add the bounded exchange.")
        second = blocks.index("Run the focused tests.")
        blocks[first], blocks[second] = blocks[second], blocks[first]
        return "\n\n".join(blocks)

    def _without_carrier(self, body: str) -> str:
        marker_index = body.index("<!-- HomericIntelligence:review-exchange:v1 ")
        return body[:marker_index].rstrip("\n") + "\n"

    def test_prepared_and_marked_digests_are_distinct_valid_bindings(self) -> None:
        content = multiline_plan()
        request = self.plan_request(self.snapshot())
        request["content"] = content
        prepared = self.adapter.issue_exchange.prepare_plan(request)
        body = prepared["operation"]["body"]
        visible = f"{self.adapter.issue_exchange.PLAN_MARKER}\n\n{content.rstrip()}"
        bare_digest = self.adapter.review_exchange.sha256_text(content)
        marked_digest = self.adapter.review_exchange.sha256_text(visible)
        carried_digest = self.adapter.review_exchange.sha256_text(body)
        operation = {
            "action": "create",
            "artifact": "plan",
            "comment_id": None,
            "expected_body_sha256": None,
            "body": body,
            "body_sha256": prepared["operation"]["body_sha256"],
        }
        operation_digest = self.adapter.review_exchange.sha256_json(operation)

        # Each digest is a valid binding in its own domain.
        self.assertEqual(carried_digest, prepared["operation"]["body_sha256"])
        self.assertEqual(operation_digest, prepared["operation"]["operation_sha256"])
        self.assertEqual(
            4, len({bare_digest, marked_digest, carried_digest, operation_digest})
        )
        _origin, envelope = self.adapter.review_exchange.extract_carrier_pair(body)
        artifact = envelope["state"]["artifact_binding"]
        self.assertEqual(marked_digest, artifact["visible_content_sha256"])
        self.assertEqual(marked_digest, artifact["sha256"])
        self.assertEqual(f"pending:{marked_digest}", artifact["revision"])
        self.assertEqual("prepare_review", prepared["next_action"])

    def test_next_action_is_bound_exactly_not_normalized(self) -> None:
        prepared = self.prepared_create()
        for next_action in ("prepare_review ", "Prepare_Review", "prepare-review"):
            with self.subTest(next_action=next_action):
                tampered = copy.deepcopy(prepared)
                tampered["next_action"] = next_action
                with self.assertRaises(self.adapter.review_exchange.ProtocolError):
                    self.adapter.issue_exchange.validate_prepared_document(tampered)

    def test_altered_operation_digest_stops_before_any_forge_contact(self) -> None:
        prepared = copy.deepcopy(self.prepared_create())
        prepared["operation"]["operation_sha256"] = "1" * 64
        forge = FakeForge(self.snapshot())
        with tempfile.TemporaryDirectory() as directory:
            receipt_path = str(Path(directory) / "attempt.json")
            with self.assertRaises(self.adapter.PublicationError):
                self.adapter.publish(prepared, receipt_path, forge=forge)

        self.assertEqual(0, forge.snapshot_reads)
        self.assertEqual([], forge.create_calls)
        self.assertEqual([], forge.update_calls)

    def test_stale_update_digest_returns_no_write_with_zero_provider_writes(
        self,
    ) -> None:
        prepared, changed = self.prepared_update()
        stale = copy.deepcopy(changed)
        stale["comments"][0]["body"] = stale["comments"][0]["body"] + "\n"
        forge = FakeForge(stale)
        with tempfile.TemporaryDirectory() as directory:
            receipt_path = str(Path(directory) / "attempt.json")
            result = self.adapter.publish(prepared, receipt_path, forge=forge)

        self.assertEqual("no_write", result["status"])
        self.assertEqual("preflight_retained_plan_drift", result["preflight_code"])
        self.assertEqual(False, result["retry_allowed"])
        self.assertEqual([], forge.create_calls)
        self.assertEqual([], forge.update_calls)
        self.assertEqual(1, forge.snapshot_reads)

    def test_invalid_utf8_prepared_document_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            document = Path(directory) / "prepared.json"
            document.write_bytes(
                b'{"status": "ready", "diagnostics": []}' + b"\xff\xfe"
            )
            with self.assertRaises(self.adapter.PublicationError):
                self.adapter.load_prepared_document(str(document))

    def test_unsafe_receipt_paths_are_rejected_before_any_forge_contact(
        self,
    ) -> None:
        prepared = self.prepared_create()
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            real_file = base / "real.json"
            real_file.write_text("{}\n", encoding="utf-8")
            non_directory = base / "not-a-directory"
            non_directory.write_text("not a directory\n", encoding="utf-8")
            world_writable = base / "world-writable"
            world_writable.mkdir()
            world_writable.chmod(0o777)
            symlink_to_file = base / "link.json"
            symlink_to_file.symlink_to(real_file)
            cases = {
                "empty name": "",
                "NUL byte": "bad\0name.json",
                "missing parent": str(base / "missing" / "attempt.json"),
                "non-directory parent": str(non_directory / "attempt.json"),
                "world-writable parent": str(world_writable / "attempt.json"),
                "symlink final component": str(symlink_to_file),
            }
            for name, receipt_path in cases.items():
                with self.subTest(case=name):
                    forge = FakeForge(self.snapshot())
                    with self.assertRaises(self.adapter.PublicationError):
                        self.adapter.publish(prepared, receipt_path, forge=forge)
                    self.assertEqual(0, forge.snapshot_reads)
                    self.assertEqual([], forge.create_calls)
                    self.assertEqual([], forge.update_calls)

    def test_receipt_path_rejects_symlink_and_non_directory_components_below_cwd(
        self,
    ) -> None:
        prepared = self.prepared_create()
        with tempfile.TemporaryDirectory() as directory:
            working = Path(directory)
            real = working / "real"
            real.mkdir()
            nested = real / "nested"
            nested.mkdir()
            (working / "link").symlink_to(real)
            (real / "sub_link").symlink_to(real)
            (working / "file").write_text("not a directory\n", encoding="utf-8")
            with _chdir(working):
                cases = {
                    "relative symlink component": "link/attempt.json",
                    "relative nested symlink component": "real/sub_link/attempt.json",
                    "relative non-directory component": "file/attempt.json",
                    "absolute under cwd symlink component": str(
                        Path.cwd() / "link" / "attempt.json"
                    ),
                }
                for name, receipt_path in cases.items():
                    with self.subTest(case=name):
                        forge = FakeForge(self.snapshot())
                        with self.assertRaises(self.adapter.PublicationError):
                            self.adapter.publish(prepared, receipt_path, forge=forge)
                        self.assertEqual(0, forge.snapshot_reads)
                        self.assertEqual([], forge.create_calls)
                        self.assertEqual([], forge.update_calls)
                # The positive control: a real directory chain is accepted.
                forge = FakeForge(self.snapshot())
                result = self.adapter.publish(
                    prepared, "real/nested/attempt.json", forge=forge
                )
                self.assertEqual("verified", result["status"])

    def test_transport_survives_a_non_utf8_host_locale(self) -> None:
        request = self.plan_request(self.snapshot())
        request["content"] = (
            "## Plan\n\n"
            "Non-ASCII body: héllo ✓ — naïve café 𝄞\n\n"
            "## Verification\n\n"
            "Run the focused tests.\n"
        )
        prepared = self.adapter.issue_exchange.prepare_plan(request)
        body = prepared["operation"]["body"]
        self.assertTrue(any(ord(character) > 127 for character in body))
        expected_payload = self.adapter.review_exchange.canonical_json(
            {"body": body}
        ).encode("utf-8")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            capture = root / "stdin.bin"
            fake_gh = root / "gh"
            fake_gh.write_text(
                f"#!{sys.executable}\n"
                "import json\n"
                "import os\n"
                "import sys\n"
                "data = sys.stdin.buffer.read()\n"
                "with open(os.environ['ATHENA_TEST_STDIN_CAPTURE'], 'wb') as stream:\n"
                "    stream.write(data)\n"
                'print(json.dumps({"id": 1001, "html_url": '
                '"https://github.com/owner/repository/issues/210#issuecomment-1001"}))\n',
                encoding="utf-8",
            )
            fake_gh.chmod(0o755)
            environment = {
                "LC_ALL": "C",
                "LANG": "C",
                "PYTHONUTF8": "0",
                "PYTHONCOERCECLOCALE": "0",
                "ATHENA_TEST_STDIN_CAPTURE": str(capture),
                "PATH": f"{directory}{os.pathsep}{os.environ['PATH']}",
            }
            forge = self.adapter.GitHubForge(prepared["target"])
            with mock.patch.dict(os.environ, environment, clear=False):
                comment_id, url = forge.create_comment(body)

            captured = capture.read_bytes()

        self.assertEqual("1001", comment_id)
        self.assertTrue(url.endswith("#issuecomment-1001"))
        self.assertEqual(expected_payload, captured)
        self.assertEqual(body, json.loads(captured.decode("utf-8"))["body"])

    def test_parser_framing_tolerance_does_not_relax_publication_identity(
        self,
    ) -> None:
        prepared = self.prepared_create()
        body = prepared["operation"]["body"]

        original, envelope = self.adapter.review_exchange.extract_carrier_pair(body)
        original_without_newline, envelope_without_newline = (
            self.adapter.review_exchange.extract_carrier_pair(body[:-1])
        )

        self.assertEqual(original, original_without_newline)
        self.assertEqual(envelope, envelope_without_newline)
        self.assertNotEqual(
            self.adapter.review_exchange.sha256_text(body),
            self.adapter.review_exchange.sha256_text(body[:-1]),
        )


if __name__ == "__main__":
    unittest.main()
