"""Behavior tests for the canonical issue-snapshot producer."""

from __future__ import annotations

import copy
import importlib.util
import io
import json
import subprocess
import sys
import time
import unittest
from collections.abc import Callable, Sequence
from contextlib import ExitStack, nullcontext, redirect_stderr, redirect_stdout
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills/review-exchange/scripts/mk_issue_snapshot.py"
REDUCER = ROOT / "skills/review-exchange/scripts/issue_exchange.py"
REPOSITORY = "owner/repository"
NUMBER = 210
ISSUE_URL = f"https://github.com/{REPOSITORY}/issues/{NUMBER}"
REQUIRED_TIMEOUT = 30.0

GOLDEN_BODY = (
    "## Describe the problem\n"
    "\n"
    "A snapshot producer does not exist.\n"
    "\n"
    "## Acceptance Criteria\n"
    "\n"
    "- [ ] One authoritative producer exists.\n"
    "- The reducer accepts its output.\n"
    "  - An indented line is not a criterion.\n"
    "1) Ordered items are criteria.\n"
    "*  \n"
    "\n"
    "### Not a boundary\n"
    "\n"
    "- This item is still inside the section.\n"
    "\n"
    "## Notes\n"
    "\n"
    "- This item is outside the section.\n"
    "\n"
)


def load_module(path: Path) -> ModuleType:
    """Load one executable helper as a test module."""
    name = f"test_mk_issue_snapshot_{path.name}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"The helper cannot be loaded: '{path}'.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class Dispatcher:
    """Answer provider requests from one pinned fixture."""

    def __init__(
        self,
        *,
        actor: dict[str, Any] | None = None,
        issue: dict[str, Any] | None = None,
        pages: Sequence[Sequence[dict[str, Any]]] | None = None,
        permissions: dict[str, Any] | None = None,
        page_bytes: bytes | None = None,
        stderr_bytes: bytes = b"",
        timeout_path: str | None = None,
    ) -> None:
        self.actor = {"id": 42, "login": "reviewer"} if actor is None else actor
        self.issue = default_issue() if issue is None else issue
        self.pages: list[list[dict[str, Any]]] = (
            [[]] if pages is None else [list(page) for page in pages]
        )
        self.permissions = {} if permissions is None else permissions
        self.page_bytes = page_bytes
        self.stderr_bytes = stderr_bytes
        self.timeout_path = timeout_path
        self.calls: list[str] = []

    def __call__(self, arguments: Sequence[str], **kwargs: Any) -> Any:
        """Answer one `gh api` request from the fixture."""
        if kwargs.get("text") is not False:
            raise AssertionError("The producer must read provider bytes.")
        if kwargs.get("timeout") != REQUIRED_TIMEOUT:
            raise AssertionError("The producer must bound every request.")
        path = arguments[-1]
        self.calls.append(path)
        if self.timeout_path == path:
            raise subprocess.TimeoutExpired(list(arguments), REQUIRED_TIMEOUT)
        if self.page_bytes is not None:
            return completed(0, self.page_bytes, self.stderr_bytes)
        if path == "user":
            return completed(0, self._encode(self.actor), self.stderr_bytes)
        if path == f"repos/{REPOSITORY}/issues/{NUMBER}":
            return completed(0, self._encode(self.issue), self.stderr_bytes)
        if "/issues/" in path and "/comments?" in path:
            page = int(path.rsplit("page=", maxsplit=1)[1])
            values = self.pages[page - 1] if page <= len(self.pages) else []
            return completed(0, self._encode(values), self.stderr_bytes)
        if "/collaborators/" in path and path.endswith("/permission"):
            return completed(*self._permission(path), stderr=self.stderr_bytes)
        raise AssertionError(f"The producer requested an unexpected path: '{path}'.")

    def _permission(self, path: str) -> tuple[int, bytes]:
        """Return one repository permission response."""
        login = path.split("/collaborators/", maxsplit=1)[1].rsplit(
            "/permission", maxsplit=1
        )[0]
        value = self.permissions.get(login)
        if value is None:
            return 1, b""
        if isinstance(value, str):
            return 0, self._encode({"permission": value})
        return 0, self._encode(value)

    def _encode(self, value: object) -> bytes:
        return json.dumps(value).encode("utf-8")


def completed(
    returncode: int, stdout: bytes, stderr: bytes = b""
) -> subprocess.CompletedProcess[bytes]:
    """Return one completed provider process."""
    return subprocess.CompletedProcess(["gh"], returncode, stdout, stderr)


def default_issue(body: str = GOLDEN_BODY) -> dict[str, Any]:
    """Return one pinned provider issue record."""
    return {
        "number": NUMBER,
        "node_id": "I_kwDOAbCdEf",
        "state": "open",
        "title": "Bind one issue snapshot producer",
        "body": body,
        "html_url": ISSUE_URL,
    }


def provider_comment(
    comment_id: int,
    login: str,
    association: str,
    author_id: int,
) -> dict[str, Any]:
    """Return one pinned provider comment record."""
    return {
        "id": comment_id,
        "html_url": f"{ISSUE_URL}#issuecomment-{comment_id}",
        "author_association": association,
        "user": {"id": author_id, "login": login},
        "body": f"comment {comment_id}",
    }


class ProducerHarness(unittest.TestCase):
    """Run the producer in process with a fixture dispatcher."""

    producer: ModuleType
    reducer: ModuleType

    @classmethod
    def setUpClass(cls) -> None:
        cls.producer = load_module(SCRIPT)
        cls.reducer = load_module(REDUCER)

    def build(
        self,
        dispatcher: Dispatcher,
        *,
        deadline_offset: float = 120.0,
    ) -> dict[str, Any]:
        """Build one snapshot document through the fixture dispatcher."""
        with patch.object(self.producer, "run_command", dispatcher):
            snapshot = self.producer.build_snapshot(
                REPOSITORY,
                NUMBER,
                "github.com",
                time.monotonic() + deadline_offset,
            )
        assert isinstance(snapshot, dict)
        return snapshot

    def run_main(
        self,
        dispatcher: Dispatcher,
        *arguments: str,
        monotonic: list[float] | None = None,
    ) -> tuple[int, str, str]:
        """Run the command-line entry point with the fixture dispatcher."""
        output, errors = io.StringIO(), io.StringIO()
        clock = (
            nullcontext()
            if monotonic is None
            else patch.object(time, "monotonic", side_effect=monotonic)
        )
        with ExitStack() as stack:
            stack.enter_context(patch.object(self.producer, "run_command", dispatcher))
            stack.enter_context(redirect_stdout(output))
            stack.enter_context(redirect_stderr(errors))
            stack.enter_context(clock)
            code = self.producer.main(list(arguments))
        return code, output.getvalue(), errors.getvalue()


def _clock(count: int = 64) -> list[float]:
    """Return a monotonic clock that jumps past every deadline."""
    return [0.0, *[1_000_000.0] * count]


class GoldenSnapshotTests(ProducerHarness):
    """The producer emits the exact pinned snapshot document."""

    def test_golden_snapshot_matches_the_pinned_fixture(self) -> None:
        dispatcher = Dispatcher(
            pages=[
                [
                    provider_comment(9001, "owner-one", "OWNER", 7),
                    provider_comment(9002, "member-one", "MEMBER", 8),
                ]
            ],
            permissions={"owner-one": "admin", "member-one": "maintain"},
        )
        code, output, errors = self.run_main(
            dispatcher, "--repo", REPOSITORY, "--number", str(NUMBER)
        )
        self.assertEqual(0, code)
        self.assertEqual("", errors)
        self.assertEqual(
            {
                "schema_id": "athena.issue-exchange.snapshot",
                "schema_version": 1,
                "target": {
                    "provider": "github",
                    "host": "github.com",
                    "repository": REPOSITORY,
                    "issue_id": "I_kwDOAbCdEf",
                    "number": NUMBER,
                    "url": ISSUE_URL,
                },
                "actor": {"id": "42", "login": "reviewer"},
                "issue": {
                    "state": "open",
                    "title": "Bind one issue snapshot producer",
                    "body": GOLDEN_BODY,
                    "acceptance_criteria": [
                        {
                            "id": "AC-001",
                            "text": "One authoritative producer exists.",
                            "source": "body",
                        },
                        {
                            "id": "AC-002",
                            "text": "The reducer accepts its output.",
                            "source": "body",
                        },
                        {
                            "id": "AC-003",
                            "text": "Ordered items are criteria.",
                            "source": "body",
                        },
                        {
                            "id": "AC-004",
                            "text": "This item is still inside the section.",
                            "source": "body",
                        },
                    ],
                },
                "comments": [
                    {
                        "id": "9001",
                        "url": f"{ISSUE_URL}#issuecomment-9001",
                        "author": {
                            "id": "7",
                            "login": "owner-one",
                            "is_authority": True,
                        },
                        "body": "comment 9001",
                    },
                    {
                        "id": "9002",
                        "url": f"{ISSUE_URL}#issuecomment-9002",
                        "author": {
                            "id": "8",
                            "login": "member-one",
                            "is_authority": True,
                        },
                        "body": "comment 9002",
                    },
                ],
                "comments_complete": True,
            },
            json.loads(output),
        )

    def test_output_is_canonical_json_with_one_final_newline(self) -> None:
        code, output, _errors = self.run_main(
            Dispatcher(), "--repo", REPOSITORY, "--number", str(NUMBER)
        )
        self.assertEqual(0, code)
        self.assertTrue(output.endswith("\n"))
        self.assertEqual(
            output,
            json.dumps(
                json.loads(output),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
        )


class AcceptanceCriteriaTests(ProducerHarness):
    """The acceptance-criteria rules are pinned."""

    def test_acceptance_criteria_follow_the_pinned_rules(self) -> None:
        cases: tuple[tuple[str, str, list[str]], ...] = (
            (
                "level_two_heading",
                "## Acceptance Criteria\n\n- one\n",
                ["one"],
            ),
            (
                "level_three_heading",
                "### Acceptance Criteria\n\n- one\n",
                ["one"],
            ),
            (
                "level_six_heading",
                "###### Acceptance Criteria\n\n- one\n",
                ["one"],
            ),
            (
                "level_one_heading_is_not_a_candidate",
                "# Acceptance Criteria\n\n- one\n",
                [],
            ),
            (
                "level_seven_heading_is_not_a_candidate",
                "####### Acceptance Criteria\n\n- one\n",
                [],
            ),
            (
                "heading_without_a_space_is_not_a_candidate",
                "##Acceptance Criteria\n\n- one\n",
                [],
            ),
            (
                "trailing_colon_and_case_are_folded",
                "## ACCEPTANCE CRITERIA:\n\n- one\n",
                ["one"],
            ),
            (
                "ac_alias_is_accepted",
                "## AC\n\n- one\n",
                ["one"],
            ),
            (
                "the_first_matching_heading_wins",
                "## Acceptance criteria\n\n- first\n\n## AC\n\n- second\n",
                ["first"],
            ),
            (
                "nested_items_are_ignored",
                "## Acceptance criteria\n\n- one\n  - nested\n",
                ["one"],
            ),
            (
                "task_checkboxes_are_removed",
                "## AC\n\n- [ ] open\n- [x] done\n- [X] upper\n",
                ["open", "done", "upper"],
            ),
            (
                "an_empty_item_is_not_a_criterion",
                "## AC\n\n- \n- one\n",
                ["one"],
            ),
            (
                "a_non_item_line_is_ignored",
                "## AC\n\none line\n- one\n",
                ["one"],
            ),
            (
                "a_deeper_heading_does_not_end_the_section",
                "## AC\n\n- one\n### detail\n- two\n",
                ["one", "two"],
            ),
            (
                "a_same_or_higher_heading_ends_the_section",
                "### AC\n\n- one\n## detail\n- two\n",
                ["one"],
            ),
            (
                "a_multi_digit_ordered_marker_is_criterion_text",
                "## AC\n\n1234567890) many\n",
                [],
            ),
            (
                "an_ordered_marker_is_a_criterion",
                "## AC\n\n1) one\n2. two\n10) ten\n",
                ["one", "two", "ten"],
            ),
        )
        for name, body, expected in cases:
            with self.subTest(case=name):
                criteria = self.producer._acceptance_criteria(body)
                self.assertEqual(expected, [item["text"] for item in criteria])
                self.assertEqual(
                    [f"AC-{index:03d}" for index in range(1, len(expected) + 1)],
                    [item["id"] for item in criteria],
                )
                self.assertEqual(
                    ["body"] * len(expected), [i["source"] for i in criteria]
                )

    def test_missing_acceptance_criteria_section_yields_an_empty_list(self) -> None:
        code, output, errors = self.run_main(
            Dispatcher(issue=default_issue("No section here.\n")),
            "--repo",
            REPOSITORY,
            "--number",
            str(NUMBER),
        )
        self.assertEqual(0, code)
        self.assertEqual("", errors)
        self.assertEqual([], json.loads(output)["issue"]["acceptance_criteria"])

    def test_null_issue_body_becomes_an_empty_body_accepted_by_the_reducer(
        self,
    ) -> None:
        issue = default_issue()
        issue["body"] = None
        dispatcher = Dispatcher(issue=issue)
        code, output, errors = self.run_main(
            dispatcher, "--repo", REPOSITORY, "--number", str(NUMBER)
        )
        self.assertEqual(0, code)
        self.assertEqual("", errors)
        snapshot = json.loads(output)
        self.assertEqual("", snapshot["issue"]["body"])
        self.assertEqual([], snapshot["issue"]["acceptance_criteria"])
        inspection = self.reducer.inspect_snapshot(snapshot)
        self.assertEqual("ready", inspection["status"])
        self.assertEqual("prepare_plan", inspection["next_action"])
        self.assertEqual(
            self.reducer._requirements_sha256(self.reducer._snapshot(snapshot)),
            inspection["requirements_sha256"],
        )


class AuthorityTests(ProducerHarness):
    """Authority needs the association and the repository permission."""

    def test_authority_requires_the_association_and_the_permission(self) -> None:
        cases = (
            ("owner_with_admin", "OWNER", "ADMIN", True),
            ("owner_with_write", "OWNER", "WRITE", False),
            ("member_with_maintain", "MEMBER", "MAINTAIN", True),
            ("collaborator_with_write", "COLLABORATOR", "WRITE", False),
            ("contributor_with_admin", "CONTRIBUTOR", "ADMIN", False),
        )
        for name, association, permission, expected in cases:
            with self.subTest(case=name):
                snapshot = self.build(
                    Dispatcher(
                        pages=[[provider_comment(9001, "login-one", association, 7)]],
                        permissions={"login-one": permission.lower()},
                    )
                )
                self.assertEqual(
                    expected, snapshot["comments"][0]["author"]["is_authority"]
                )

    def test_authority_lookups_are_cached_per_login(self) -> None:
        dispatcher = Dispatcher(
            pages=[
                [
                    provider_comment(9001, "login-one", "OWNER", 7),
                    provider_comment(9002, "login-one", "OWNER", 7),
                ]
            ],
            permissions={"login-one": "admin"},
        )
        self.build(dispatcher)
        permission_calls = [
            path
            for path in dispatcher.calls
            if "/collaborators/" in path and path.endswith("/permission")
        ]
        self.assertEqual(
            ["repos/owner/repository/collaborators/login-one/permission"],
            permission_calls,
        )

    def test_authority_lookups_are_bounded(self) -> None:
        pages = [
            [
                provider_comment(9000 + index, f"login-{index}", "OWNER", 100 + index)
                for index in range(3)
            ]
        ]
        with patch.object(self.producer, "MAX_AUTHORITY_LOOKUPS", 2):
            code, output, errors = self.run_main(
                Dispatcher(pages=pages, permissions={"login-0": "admin"}),
                "--repo",
                REPOSITORY,
                "--number",
                str(NUMBER),
            )
        self.assertEqual(2, code)
        self.assertEqual("", output)
        self.assertNotIn("Traceback", errors)

    def test_authority_lookup_fails_closed(self) -> None:
        cases: tuple[tuple[str, dict[str, Any]], ...] = (
            ("rejected_request", {}),
            ("response_without_permission", {"login-one": {}}),
        )
        for name, permissions in cases:
            with self.subTest(case=name):
                code, output, errors = self.run_main(
                    Dispatcher(
                        pages=[[provider_comment(9001, "login-one", "OWNER", 7)]],
                        permissions=permissions,
                    ),
                    "--repo",
                    REPOSITORY,
                    "--number",
                    str(NUMBER),
                )
                self.assertEqual(2, code)
                self.assertEqual("", output)
                self.assertNotIn("Traceback", errors)
                self.assertIn(
                    "The snapshot producer needs repository administration read.",
                    errors,
                )


class PaginationTests(ProducerHarness):
    """Comment pagination is exhaustive, ordered, and bounded."""

    def test_comment_pagination_is_exhaustive_and_order_preserving(self) -> None:
        first_page = [
            provider_comment(1000 + index, f"login-{index}", "NONE", 2000 + index)
            for index in range(100)
        ]
        second_page = [
            provider_comment(3000 + index, f"login-{index}", "NONE", 4000 + index)
            for index in range(3)
        ]
        dispatcher = Dispatcher(pages=[first_page, second_page, first_page])
        snapshot = self.build(dispatcher)
        page_calls = [
            path.rsplit("page=", maxsplit=1)[1]
            for path in dispatcher.calls
            if "/comments?" in path
        ]
        self.assertEqual(["1", "2"], page_calls)
        self.assertEqual(
            [str(1000 + index) for index in range(100)]
            + [str(3000 + index) for index in range(3)],
            [comment["id"] for comment in snapshot["comments"]],
        )
        self.assertIs(True, snapshot["comments_complete"])

    def test_reached_bounds_fail_without_a_complete_snapshot(self) -> None:
        full_page = [
            provider_comment(5000 + index, f"login-{index}", "NONE", 6000 + index)
            for index in range(100)
        ]
        cases: tuple[tuple[str, Dispatcher, dict[str, Any]], ...] = (
            ("page_cap", Dispatcher(pages=[full_page] * 5), {"MAX_COMMENT_PAGES": 2}),
            ("comment_cap", Dispatcher(pages=[full_page]), {"MAX_COMMENTS": 10}),
            ("oversized_page", Dispatcher(pages=[full_page]), {"MAX_PAGE_BYTES": 8}),
            (
                "oversized_standard_error",
                Dispatcher(pages=[full_page], stderr_bytes=b"detail"),
                {"MAX_STDERR_BYTES": 2},
            ),
            ("request_timeout", Dispatcher(timeout_path="user"), {}),
            ("accumulated_response_cap", Dispatcher(), {"MAX_TOTAL_BYTES": 8}),
        )
        for name, dispatcher, constants in cases:
            with self.subTest(case=name):
                with (
                    nullcontext()
                    if not constants
                    else patch.multiple(self.producer, **constants)
                ):
                    code, output, errors = self.run_main(
                        dispatcher, "--repo", REPOSITORY, "--number", str(NUMBER)
                    )
                self.assertEqual(2, code)
                self.assertEqual("", output)
                self.assertNotIn("Traceback", errors)
                self.assertTrue(errors.strip())

    def test_reached_deadline_fails_without_a_complete_snapshot(self) -> None:
        code, output, errors = self.run_main(
            Dispatcher(),
            "--repo",
            REPOSITORY,
            "--number",
            str(NUMBER),
            monotonic=_clock(),
        )
        self.assertEqual(2, code)
        self.assertEqual("", output)
        self.assertIn("deadline", errors)
        self.assertNotIn("Traceback", errors)

    def test_request_timeout_reports_the_named_message(self) -> None:
        code, _output, errors = self.run_main(
            Dispatcher(timeout_path="user"),
            "--repo",
            REPOSITORY,
            "--number",
            str(NUMBER),
        )
        self.assertEqual(2, code)
        self.assertIn("safe request deadline", errors)


class LocatorTests(ProducerHarness):
    """The locator surface is bounded."""

    def test_gitlab_locator_fails_with_a_clear_operational_error(self) -> None:
        code, output, errors = self.run_main(
            Dispatcher(),
            "--repo",
            "owner/repository",
            "--number",
            str(NUMBER),
            "--provider",
            "gitlab",
        )
        self.assertEqual(2, code)
        self.assertEqual("", output)
        self.assertIn("gitlab", errors)
        self.assertIn("adapter", errors)
        self.assertNotIn("Traceback", errors)

    def test_failure_paths_report_operations_without_a_traceback(self) -> None:
        cases: tuple[tuple[str, Callable[[], tuple[int, str, str]], int], ...] = (
            (
                "invalid_utf8",
                lambda: self.run_main(
                    Dispatcher(page_bytes=b"\xff\xfe"),
                    "--repo",
                    REPOSITORY,
                    "--number",
                    str(NUMBER),
                ),
                2,
            ),
            (
                "malformed_json",
                lambda: self.run_main(
                    Dispatcher(page_bytes=b"{not json"),
                    "--repo",
                    REPOSITORY,
                    "--number",
                    str(NUMBER),
                ),
                2,
            ),
            (
                "comment_url_fragment_mismatch",
                lambda: self.run_main(
                    Dispatcher(
                        pages=[
                            [
                                {
                                    "id": 9001,
                                    "html_url": f"{ISSUE_URL}#issuecomment-1",
                                    "author_association": "NONE",
                                    "user": {"id": 7, "login": "login-one"},
                                    "body": "body",
                                }
                            ]
                        ]
                    ),
                    "--repo",
                    REPOSITORY,
                    "--number",
                    str(NUMBER),
                ),
                2,
            ),
            (
                "issue_url_mismatch",
                lambda: self.run_main(
                    Dispatcher(
                        issue={
                            **default_issue(),
                            "html_url": "https://github.com/x/y/issues/1",
                        }
                    ),
                    "--repo",
                    REPOSITORY,
                    "--number",
                    str(NUMBER),
                ),
                2,
            ),
            (
                "option_like_repository_value",
                lambda: self.run_main(
                    Dispatcher(), "--repo=--hostname", "--number", str(NUMBER)
                ),
                1,
            ),
            (
                "non_positive_number",
                lambda: self.run_main(
                    Dispatcher(), "--repo", REPOSITORY, "--number", "0"
                ),
                1,
            ),
            (
                "wrong_host",
                lambda: self.run_main(
                    Dispatcher(),
                    "--repo",
                    REPOSITORY,
                    "--number",
                    str(NUMBER),
                    "--host",
                    "gitlab.com",
                ),
                1,
            ),
        )
        for name, run, expected in cases:
            with self.subTest(case=name):
                code, _output, errors = run()
                self.assertEqual(expected, code)
                self.assertTrue(errors.strip())
                self.assertNotIn("Traceback", errors)


class DigestStabilityTests(ProducerHarness):
    """Two builds of one issue bind one requirements digest."""

    def fixtures(self) -> tuple[tuple[str, Dispatcher, Dispatcher], ...]:
        """Return the fixture families that must bind one digest."""
        comments = [
            provider_comment(9001, "owner-one", "OWNER", 7),
            provider_comment(9002, "member-one", "MEMBER", 8),
        ]
        return (
            (
                "with_acceptance_criteria",
                Dispatcher(
                    pages=[comments],
                    permissions={"owner-one": "admin", "member-one": "maintain"},
                ),
                Dispatcher(
                    pages=[comments],
                    permissions={"owner-one": "admin", "member-one": "maintain"},
                ),
            ),
            (
                "without_acceptance_criteria",
                Dispatcher(issue=default_issue("No section here.\n")),
                Dispatcher(issue=default_issue("No section here.\n")),
            ),
            ("without_comments", Dispatcher(), Dispatcher()),
        )

    def test_two_builds_bind_the_same_requirements_digest(self) -> None:
        for name, first, second in self.fixtures():
            with self.subTest(case=name):
                self.assertEqual(
                    self.reducer._requirements_sha256(self.build(first)),
                    self.reducer._requirements_sha256(self.build(second)),
                )

    def test_historic_producer_variants_bind_different_requirements_digests(
        self,
    ) -> None:
        canonical = self.build(Dispatcher())
        numeric_identity = copy.deepcopy(canonical)
        numeric_identity["target"]["issue_id"] = "5736299292"
        heading_rule = copy.deepcopy(canonical)
        # A producer that matched only level-two headings binds no criteria for
        # a body whose section uses a deeper heading.
        heading_rule["issue"]["body"] = GOLDEN_BODY.replace(
            "## Acceptance Criteria", "### Acceptance Criteria", 1
        )
        heading_rule["issue"]["acceptance_criteria"] = []
        for variant in (numeric_identity, heading_rule):
            with self.subTest(variant=variant["target"]["issue_id"]):
                self.assertNotEqual(
                    self.reducer._requirements_sha256(canonical),
                    self.reducer._requirements_sha256(variant),
                )


if __name__ == "__main__":
    unittest.main()
